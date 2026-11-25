/* SPDX-License-Identifier: GPL-2.0 */
#pragma once

/* Rotate the starting representative without searching the system CPU mask. */
static __always_inline s32 pick_idle_from_list(struct task_struct *p, const u32 *cpus, u32 count,
                                               const struct cpumask *online, u32 scan_limit)
{
    if (!count || count > NEW_A_MAX_CPUS)
        return -1;
    u32 start = (u32)BPF_CORE_READ(p, pid) % count;
#ifdef __clang__
#pragma clang loop unroll(disable)
#endif
    for (u32 offset = 0; offset < scan_limit; offset++) {
        if (offset >= count)
            break;
        u32 index = start + offset;
        if (index >= count)
            index -= count;
        if (index >= NEW_A_MAX_CPUS)
            break;
        u32 cpu = cpus[index];
        if (cpu < NEW_A_MAX_CPUS && bpf_cpumask_test_cpu(cpu, p->cpus_ptr) &&
            bpf_cpumask_test_cpu(cpu, online) && scx_bpf_test_and_clear_cpu_idle((s32)cpu))
            return (s32)cpu;
    }
    return -1;
}

#ifdef NEW_A_PREFILL_PAIR
#define NEWA_PREFILL_SCAN_LIMIT 32

/* Both experimental arms use this exit path, including SCX's idle-local insertion. */
static __always_inline s32 newa_pair_select(struct task_struct *p, s32 prev_cpu, u64 wake_flags,
                                            bool prefer_pcores)
{
    u32 key = 0, phase = control_state.current_phase;
    s32 cpu = -1;
    bool is_idle = false;

    if (prefer_pcores && phase == LLAMA_SCX_PHASE_PREFILL && control_state.selected_tgid &&
        BPF_CORE_READ(p, tgid) == control_state.selected_tgid && !BPF_CORE_READ(p, migration_disabled)) {
        const struct newa_dispatch_topology *config = bpf_map_lookup_elem(&new_a_topology, &key);
        if (config && config->tiers.enabled && config->prefill_pcore_count &&
            config->prefill_pcore_count == config->tiers.count[0]) {
            const struct cpumask *online = scx_bpf_get_online_cpumask();
            cpu = pick_idle_from_list(p, config->tiers.cpus[0], config->prefill_pcore_count,
                                      online, NEWA_PREFILL_SCAN_LIMIT);
            scx_bpf_put_cpumask(online);
            struct handoff_counters *stats = bpf_map_lookup_elem(&handoff_stats, &key);
            if (stats) {
                stats->prefill_attempts[phase & 3]++;
                if (cpu >= 0)
                    stats->prefill_hits[phase & 3]++;
            }
        }
    }
    if (cpu >= 0) {
        is_idle = true;
        observe_selection(0);
    } else {
        cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);
        observe_selection(3);
    }
    if (is_idle)
        scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
    return cpu;
}
#endif

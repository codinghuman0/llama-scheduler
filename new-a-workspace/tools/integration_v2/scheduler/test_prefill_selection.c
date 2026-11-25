/* SPDX-License-Identifier: GPL-2.0 */
/* Exercise the production selector on the host with deterministic kernel helper doubles. */
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "handoff-policy.h"
#include "state-receiver.h"

typedef __u32 u32;
typedef __s32 s32;
typedef __u64 u64;
struct cpumask { bool cpu[NEW_A_MAX_CPUS]; };
struct task_struct { u32 pid, tgid, migration_disabled; const struct cpumask *cpus_ptr; };
#define BPF_CORE_READ(p, field) ((p)->field)
#define SCX_DSQ_LOCAL 1
#define SCX_SLICE_DFL 2

static struct newa_dispatch_topology config;
static struct handoff_counters counters;
static struct llama_scx_control_state control_state;
static int new_a_topology, handoff_stats;
static struct cpumask online, allowed, idle;
static struct task_struct worker = { .pid = 100, .tgid = 99, .cpus_ptr = &allowed };
static u32 idle_checks, acquisitions, releases, fallback_calls, local_inserts, observed_tier;
static bool default_idle;

static void *bpf_map_lookup_elem(const int *map, const u32 *key)
{
    assert(*key == 0);
    return map == &new_a_topology ? (void *)&config : (void *)&counters;
}
static const struct cpumask *scx_bpf_get_online_cpumask(void) { acquisitions++; return &online; }
static void scx_bpf_put_cpumask(const struct cpumask *mask) { assert(mask == &online); releases++; }
static bool bpf_cpumask_test_cpu(u32 cpu, const struct cpumask *mask)
{
    assert(cpu < NEW_A_MAX_CPUS);
    return mask->cpu[cpu];
}
static bool scx_bpf_test_and_clear_cpu_idle(s32 cpu)
{
    assert(allowed.cpu[cpu] && online.cpu[cpu]);
    idle_checks++;
    bool available = idle.cpu[cpu];
    idle.cpu[cpu] = false;
    return available;
}
static s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev, u64 flags, bool *is_idle)
{
    assert(p == &worker && prev == 8 && flags == 7);
    fallback_calls++;
    *is_idle = default_idle;
    return prev;
}
static void observe_selection(u32 tier) { observed_tier = tier; }
static void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq, u64 slice, u64 flags)
{
    assert(p == &worker && dsq == SCX_DSQ_LOCAL && slice == SCX_SLICE_DFL && !flags);
    local_inserts++;
}
#include "idle-selection.h"

static void check(int candidate, bool can_attempt)
{
    bool attempt = NEW_A_PREFILL_PAIR && can_attempt;
    bool hit = attempt && candidate >= 0;
    memset(&counters, 0, sizeof(counters));
    idle_checks = acquisitions = releases = fallback_calls = local_inserts = 0;
    observed_tier = 99;
    assert(newa_pair_select(&worker, 8, 7, NEW_A_PREFILL_PAIR) == (hit ? candidate : 8));
    assert(acquisitions == (u32)attempt && releases == acquisitions && idle_checks <= NEWA_PREFILL_SCAN_LIMIT);
    assert(fallback_calls == (u32)!hit && local_inserts == (u32)(hit || default_idle));
    assert(observed_tier == (hit ? 0u : 3u));
    for (u32 i = 0; i < 4; i++) {
        assert(counters.prefill_attempts[i] == (u64)(attempt && i == LLAMA_SCX_PHASE_PREFILL));
        assert(counters.prefill_hits[i] == (u64)(hit && i == LLAMA_SCX_PHASE_PREFILL));
    }
}

int main(void)
{
    struct newa_state_receiver rx = { .run_id = 11 };
    struct server_scx_state_v2 event = { 2, LLAMA_SCX_PHASE_PREFILL, 1, 0, 11, 1 };
    config.tiers.enabled = 1;
    config.tiers.count[0] = config.prefill_pcore_count = 4;
    for (u32 i = 0; i < 4; i++) config.tiers.cpus[0][i] = 2 * i;
    memset(allowed.cpu, 1, sizeof(allowed.cpu));
    memset(online.cpu, 1, sizeof(online.cpu));
    control_state.selected_tgid = 99;
    assert(newa_state_accept(&rx, &event, 99));
    control_state.current_phase = rx.phase;
    /* Candidate 0 is outside cpus_ptr, 2 offline, 4 busy, only P6 is available. */
    allowed.cpu[0] = online.cpu[2] = false;
    idle.cpu[0] = idle.cpu[2] = idle.cpu[6] = idle.cpu[8] = true;
    check(6, true);
    check(-1, true);
    default_idle = true;
    check(-1, true);
    worker.migration_disabled = 1;
    check(-1, false);
    worker.migration_disabled = 0;
    worker.tgid++;
    check(-1, false);
    worker.tgid--;
    control_state.selected_tgid = 0;
    check(-1, false);
    control_state.selected_tgid = worker.tgid;
    config.prefill_pcore_count = 0; /* AMD retains a nonempty physical tier. */
    check(-1, false);
    config.prefill_pcore_count = 4;
    for (u32 phase = 0; phase < 4; phase++) {
        if (phase == LLAMA_SCX_PHASE_PREFILL) continue;
        control_state.current_phase = phase;
        check(-1, false);
    }
    event.sequence += 2;
    assert(!newa_state_accept(&rx, &event, 99));
    control_state.current_phase = rx.active ? rx.phase : LLAMA_SCX_PHASE_UNKNOWN;
    check(-1, false);
    control_state.current_phase = LLAMA_SCX_PHASE_PREFILL;
    worker.pid = 63;
    config.tiers.count[0] = config.prefill_pcore_count = 64;
    memset(&idle, 0, sizeof(idle));
    for (u32 i = 0; i < 64; i++) config.tiers.cpus[0][i] = i + 32;
    idle.cpu[63] = true; /* 33rd candidate after wrapping, beyond the 32-probe cap. */
    check(-1, true);
    assert(idle_checks == (NEW_A_PREFILL_PAIR ? NEWA_PREFILL_SCAN_LIMIT : 0));
    puts(NEW_A_PREFILL_PAIR ? "prefill-pcore selector PASS" : "neutral selector PASS");
    return 0;
}

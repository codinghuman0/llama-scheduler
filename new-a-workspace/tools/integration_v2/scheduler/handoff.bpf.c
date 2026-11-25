/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Derived from Linux v6.17 tools/sched_ext/scx_simple.bpf.c and Portable Base.
 * NEW_A idle selection follows the ba6cdd4 tier selector.
 * Copyright (c) 2022 Meta Platforms, Inc. and affiliates.
 * Copyright (c) 2022 Tejun Heo <tj@kernel.org>
 * Copyright (c) 2022 David Vernet <dvernet@meta.com>
 */
#define BPF_NO_KFUNC_PROTOTYPES
#define LLAMA_SCX_BPF
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmissing-declarations"
#include "vmlinux.h"
#pragma clang diagnostic pop
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "llama_scx_state.h"
#include "new_a.h"
#include "state-receiver.h"
#include "handoff-policy.h"

char _license[] SEC("license") = "GPL";
volatile struct llama_scx_control_state control_state SEC(".data") = {};
static u64 vtime_now;
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __type(key, u32);
    __type(value, struct newa_state_receiver);
    __uint(max_entries, 1);
} newa_state_rx SEC(".maps");
#define SHARED_DSQ 0

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__type(key, u32);
	__uint(map_flags, BPF_F_RDONLY_PROG);
	__type(value, struct newa_dispatch_topology);
	__uint(max_entries, 1);
} new_a_topology SEC(".maps");

s32 scx_bpf_create_dsq(u64 dsq_id, s32 node) __ksym;
s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev_cpu, u64 wake_flags, bool *is_idle) __ksym;
void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id, u64 slice, u64 enq_flags) __ksym;
void scx_bpf_dsq_insert_vtime(struct task_struct *p, u64 dsq_id, u64 slice, u64 vtime, u64 enq_flags) __ksym;
bool scx_bpf_dsq_move_to_local(u64 dsq_id) __ksym;
bool bpf_cpumask_test_cpu(u32 cpu, const struct cpumask *cpumask) __ksym;
bool scx_bpf_test_and_clear_cpu_idle(s32 cpu) __ksym;
const struct cpumask *scx_bpf_get_online_cpumask(void) __ksym;
void scx_bpf_put_cpumask(const struct cpumask *cpumask) __ksym;

#define BPF_STRUCT_OPS(name, args...) SEC("struct_ops/" #name) BPF_PROG(name, ##args)
#define BPF_STRUCT_OPS_SLEEPABLE(name, args...) SEC("struct_ops.s/" #name) BPF_PROG(name, ##args)

static __always_inline bool time_before(u64 a, u64 b)
{
	return (s64)(a - b) < 0;
}

#ifdef NEW_A_DIAGNOSTICS
s32 scx_bpf_task_cpu(const struct task_struct *p) __ksym;
u32 bpf_cpumask_weight(const struct cpumask *cpumask) __ksym;

struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(map_flags, BPF_F_RDONLY_PROG);
	__type(key, u32);
	__type(value, struct new_a_diagnostic_config);
	__uint(max_entries, 1);
} new_a_diagnostic_config SEC(".maps");

struct new_a_task_observation {
	u64 start_ns;
	u32 last_cpu_plus_one;
};

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__type(key, u32);
	__type(value, struct new_a_stats);
	__uint(max_entries, 1);
} new_a_stats SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_TASK_STORAGE);
	__uint(map_flags, BPF_F_NO_PREALLOC);
	__type(key, int);
	__type(value, struct new_a_task_observation);
} new_a_tasks SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__type(key, u32);
	__type(value, struct new_a_event);
	__uint(max_entries, NEW_A_EVENT_CAPACITY);
} new_a_events SEC(".maps");

static __always_inline int read_mask(u64 *destination, const struct cpumask *mask, u32 mask_bits)
{
	const void *bits = __builtin_preserve_access_index(&mask->bits);
	int error;

	_Static_assert(NEW_A_MASK_WORDS == 16, "mask copy must cover all words");
	/* Keep helper lengths and destination offsets constant. */
#define READ_MASK_WORD(word) do { \
	if ((word) * 64 >= mask_bits) \
		return 0; \
	error = bpf_probe_read_kernel(&destination[word], sizeof(destination[word]), \
		(const char *)bits + (word) * sizeof(destination[word])); \
	if (error) \
		return error; \
} while (0)
	READ_MASK_WORD(0);
	READ_MASK_WORD(1);
	READ_MASK_WORD(2);
	READ_MASK_WORD(3);
	READ_MASK_WORD(4);
	READ_MASK_WORD(5);
	READ_MASK_WORD(6);
	READ_MASK_WORD(7);
	READ_MASK_WORD(8);
	READ_MASK_WORD(9);
	READ_MASK_WORD(10);
	READ_MASK_WORD(11);
	READ_MASK_WORD(12);
	READ_MASK_WORD(13);
	READ_MASK_WORD(14);
	READ_MASK_WORD(15);
#undef READ_MASK_WORD
	return 0;
}

static __always_inline void observe_event(struct task_struct *p, struct new_a_stats *stats,
					  u32 kind, u32 callback, u64 now, const struct cpumask *requested)
{
	u64 slot = __sync_fetch_and_add(&stats->events_attempted, 1);
	u32 key = (u32)slot;
	struct new_a_event *event;
	const struct cpumask *allowed = p->cpus_ptr;
	u32 config_key = 0;
	struct new_a_diagnostic_config *config = bpf_map_lookup_elem(&new_a_diagnostic_config, &config_key);
	u32 mask_bits = config ? config->mask_bits : 0;

	if (slot >= NEW_A_EVENT_CAPACITY) {
		stats->events_dropped++;
		return;
	}
	event = bpf_map_lookup_elem(&new_a_events, &key);
	if (!event) {
		stats->events_dropped++;
		return;
	}
	event->timestamp_ns = now;
	event->actor_pid_tgid = bpf_get_current_pid_tgid();
	event->task_start_time = BPF_CORE_READ(p, start_time);
	event->sequence = key;
	event->kind = kind;
	event->callback = callback;
	event->tgid = BPF_CORE_READ(p, tgid);
	event->tid = BPF_CORE_READ(p, pid);
	event->callback_cpu = bpf_get_smp_processor_id();
	event->task_cpu = scx_bpf_task_cpu(p);
	event->nr_cpus_allowed = BPF_CORE_READ(p, nr_cpus_allowed);
	event->migration_disabled = BPF_CORE_READ(p, migration_disabled);
	event->migration_pending = BPF_CORE_READ(p, migration_pending) != NULL;
	event->on_cpu = BPF_CORE_READ(p, on_cpu);
	event->on_rq = BPF_CORE_READ(p, on_rq);
	event->mask_bits = 0;
	event->allowed_weight = bpf_cpumask_weight(allowed);
	event->regular_weight = bpf_cpumask_weight(&p->cpus_mask);
	if (!mask_bits || mask_bits > NEW_A_MAX_CPUS || mask_bits > sizeof(allowed->bits) * 8) {
		event->allowed_read_error = -22;
		event->regular_read_error = -22;
		if (requested)
			event->requested_read_error = -22;
	} else {
		event->mask_bits = mask_bits;
		event->allowed_read_error = read_mask(event->allowed, allowed, mask_bits);
		event->regular_read_error = read_mask(event->regular, &p->cpus_mask, mask_bits);
		if (requested) {
			event->requested_weight = bpf_cpumask_weight(requested);
			event->requested_read_error = read_mask(event->requested, requested, mask_bits);
		}
	}
	event->callback_allowed = bpf_cpumask_test_cpu(event->callback_cpu, allowed);
	event->task_allowed = event->task_cpu >= 0 ? bpf_cpumask_test_cpu((u32)event->task_cpu, allowed) : -1;
}

static __always_inline void observe_selection(u32 tier)
{
	u32 key = 0;
	struct new_a_stats *stats = bpf_map_lookup_elem(&new_a_stats, &key);

	if (stats && tier < 4)
		stats->selected[tier]++;
}

static __always_inline void observe_phase(u32 phase)
{
	u32 key = 0;
	struct new_a_stats *stats = bpf_map_lookup_elem(&new_a_stats, &key);

	if (stats && phase < 4)
		stats->phase_seen |= 1ULL << phase;
}

static __always_inline void observe_runtime(struct task_struct *p, bool running)
{
	u32 key = 0, cpu = bpf_get_smp_processor_id();
	struct new_a_stats *stats = bpf_map_lookup_elem(&new_a_stats, &key);
	struct new_a_task_observation *task;
#ifndef NEW_A_RUNTIME_LITE
	u64 now = bpf_ktime_get_ns();
#else
	u64 now = 0;
#endif

	if (!stats)
		return;
	task = bpf_task_storage_get(&new_a_tasks, p, 0, BPF_LOCAL_STORAGE_GET_F_CREATE);
	if (!task) {
		stats->tracking_failures++;
		observe_event(p, stats, NEW_A_EVENT_TRACKING_FAILURE,
			      running ? NEW_A_CALLBACK_RUNNING : NEW_A_CALLBACK_STOPPING, now ? now : bpf_ktime_get_ns(), NULL);
		return;
	}
	if (running) {
		stats->running++;
		if (!bpf_cpumask_test_cpu(cpu, p->cpus_ptr)) {
			stats->mask_violations++;
			observe_event(p, stats, NEW_A_EVENT_MASK_VIOLATION, NEW_A_CALLBACK_RUNNING, now ? now : bpf_ktime_get_ns(), NULL);
		}
		if (task->last_cpu_plus_one && task->last_cpu_plus_one != cpu + 1)
			stats->migrations++;
		task->last_cpu_plus_one = cpu + 1;
#ifndef NEW_A_RUNTIME_LITE
		task->start_ns = now;
#endif
	} else {
		stats->stopping++;
#ifndef NEW_A_RUNTIME_LITE
		if (task->start_ns)
			stats->runtime_ns += now - task->start_ns;
		task->start_ns = 0;
#endif
	}
}

void BPF_STRUCT_OPS(new_a_set_cpumask, struct task_struct *p, const struct cpumask *cpumask)
{
	u32 key = 0;
	struct new_a_stats *stats;

	if (BPF_CORE_READ(p, tgid) != control_state.selected_tgid)
		return;
	stats = bpf_map_lookup_elem(&new_a_stats, &key);
	if (stats)
		observe_event(p, stats, NEW_A_EVENT_SET_CPUMASK, NEW_A_CALLBACK_SET_CPUMASK, bpf_ktime_get_ns(), cpumask);
}
#else
#define observe_selection(tier) do { (void)(tier); } while (0)
#define observe_runtime(p, running) do { } while (0)
#define observe_phase(phase) do { } while (0)
#endif

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __type(key, u32);
    __type(value, struct handoff_counters);
    __uint(max_entries, 1);
} handoff_stats SEC(".maps");

#include "idle-selection.h"

#ifdef NEW_A_LOCALITY
/* Reuse the archived locality-v2 restriction to the preferred tier. */
static __always_inline s32 pick_previous_idle(struct task_struct *p, s32 previous,
                                              const struct new_a_topology *topology,
                                              const struct cpumask *online)
{
    u32 count = topology->count[0];

    if (previous < 0 || previous >= NEW_A_MAX_CPUS || !count || count > NEW_A_MAX_CPUS ||
        !bpf_cpumask_test_cpu((u32)previous, p->cpus_ptr) ||
        !bpf_cpumask_test_cpu((u32)previous, online))
        return -1;
#pragma clang loop unroll(disable)
    for (u32 index = 0; index < NEW_A_MAX_CPUS; index++) {
        if (index >= count)
            break;
        if (topology->cpus[0][index] == (u32)previous)
            return scx_bpf_test_and_clear_cpu_idle(previous) ? previous : -1;
    }
    return -1;
}
#endif

s32 BPF_STRUCT_OPS(llama_select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags)
{
#ifdef NEW_A_PREFILL_PAIR
	return newa_pair_select(p, prev_cpu, wake_flags, NEW_A_PREFILL_PAIR);
#else
	u32 key = 0;
	const struct newa_dispatch_topology *config = bpf_map_lookup_elem(&new_a_topology, &key);
	bool is_idle = false;
	s32 cpu = -1;
	u32 tier = 3;

	if (config && config->tiers.enabled && !BPF_CORE_READ(p, migration_disabled)) {
		const struct new_a_topology *topology = &config->tiers;
		const struct cpumask *online = scx_bpf_get_online_cpumask();

#ifdef NEW_A_LOCALITY
		u32 phase = control_state.current_phase;
		if (newa_locality_eligible(phase, control_state.selected_tgid, BPF_CORE_READ(p, tgid), NEW_A_LOCALITY == 2)) {
			cpu = pick_previous_idle(p, prev_cpu, topology, online);
			struct handoff_counters *stats = bpf_map_lookup_elem(&handoff_stats, &key);
			if (stats) {
				stats->locality_attempts[phase & 3]++;
				if (cpu >= 0)
					stats->locality_hits[phase & 3]++;
			}
		}
#endif
		if (cpu < 0)
			cpu = pick_idle_from_list(p, topology->cpus[0], topology->count[0], online, NEW_A_MAX_CPUS);
		if (cpu >= 0)
			tier = 0;
		if (cpu < 0) {
			cpu = pick_idle_from_list(p, topology->cpus[1], topology->count[1], online, NEW_A_MAX_CPUS);
			if (cpu >= 0)
				tier = 1;
		}
		if (cpu < 0) {
			cpu = pick_idle_from_list(p, topology->cpus[2], topology->count[2], online, NEW_A_MAX_CPUS);
			if (cpu >= 0)
				tier = 2;
		}
		scx_bpf_put_cpumask(online);
		if (cpu >= 0)
			is_idle = true;
	}
	if (cpu < 0)
		cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);
	observe_selection(tier);
	if (is_idle)
		scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
	return cpu;
#endif
}

#ifdef NEW_A_IDLE_HANDOFF
void scx_bpf_kick_cpu(s32 cpu, u64 flags) __ksym;
#endif

#ifndef NEW_A_PREFILL_PAIR
static __always_inline bool handoff_idle(struct task_struct *p, u64 enq_flags)
{
    u32 key = 0, phase = control_state.current_phase;
    struct handoff_counters *stats;

    if (!newa_decode_handoff_eligible(phase, control_state.selected_tgid, BPF_CORE_READ(p, tgid),
                                      BPF_CORE_READ(p, migration_disabled), !!(enq_flags & SCX_ENQ_REENQ)))
        return false;
    stats = bpf_map_lookup_elem(&handoff_stats, &key);
    if (stats)
        stats->attempts[phase]++;
#ifdef NEW_A_IDLE_HANDOFF
    const struct newa_dispatch_topology *config = bpf_map_lookup_elem(&new_a_topology, &key);
    if (config && config->tiers.enabled) {
        const struct new_a_topology *topology = &config->tiers;
        const struct cpumask *online = scx_bpf_get_online_cpumask();
        s32 cpu = pick_idle_from_list(p, topology->cpus[0], topology->count[0], online, NEW_A_MAX_CPUS);
        scx_bpf_put_cpumask(online);
        if (cpu >= 0) {
            scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL_ON | (u32)cpu, SCX_SLICE_DFL, enq_flags);
            scx_bpf_kick_cpu(cpu, SCX_KICK_IDLE);
            if (stats)
                stats->moved[phase]++;
            return true;
        }
    }
#else
    (void)enq_flags;
#endif
    return false;
}
#endif

void BPF_STRUCT_OPS(llama_enqueue, struct task_struct *p, u64 enq_flags)
{
	u64 vtime = p->scx.dsq_vtime;

#ifndef NEW_A_PREFILL_PAIR
	if (handoff_idle(p, enq_flags))
		return;
#endif

	if (time_before(vtime, vtime_now - SCX_SLICE_DFL))
		vtime = vtime_now - SCX_SLICE_DFL;
	scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime, enq_flags);
}

void BPF_STRUCT_OPS(llama_dispatch, s32 cpu, struct task_struct *prev)
{
	scx_bpf_dsq_move_to_local(SHARED_DSQ);
}

void BPF_STRUCT_OPS(llama_running, struct task_struct *p)
{
	observe_runtime(p, true);
#if defined(NEW_A_PREFILL_PAIR) && !defined(NEW_A_RUNTIME_LITE)
	if (control_state.selected_tgid && BPF_CORE_READ(p, tgid) == control_state.selected_tgid) {
		u32 key = 0, phase = control_state.current_phase;
		struct handoff_counters *stats = bpf_map_lookup_elem(&handoff_stats, &key);
		if (stats && phase <= LLAMA_SCX_PHASE_MIXED)
			stats->running_starts[phase & 3]++;
	}
#endif
	if (time_before(vtime_now, p->scx.dsq_vtime))
		vtime_now = p->scx.dsq_vtime;
}

void BPF_STRUCT_OPS(llama_stopping, struct task_struct *p, bool runnable)
{
	observe_runtime(p, false);
	p->scx.dsq_vtime += (SCX_SLICE_DFL - p->scx.slice) * 100 / p->scx.weight;
}

void BPF_STRUCT_OPS(llama_enable, struct task_struct *p)
{
	p->scx.dsq_vtime = vtime_now;
}

s32 BPF_STRUCT_OPS_SLEEPABLE(llama_init)
{
	return scx_bpf_create_dsq(SHARED_DSQ, -1);
}

void BPF_STRUCT_OPS(llama_exit, struct scx_exit_info *ei)
{
	control_state.exit_kind = ei->kind;
}

SEC("uprobe")
int BPF_UPROBE(llama_phase, __u32 phase)
{
	__u32 tgid = bpf_get_current_pid_tgid() >> 32;

	if (tgid != control_state.selected_tgid || phase > LLAMA_SCX_PHASE_MIXED)
		return 0;
	control_state.current_phase = phase;
	observe_phase(phase);
	return 0;
}

SEC("uprobe")
int BPF_UPROBE(llama_phase_state_v2, const struct server_scx_state_v2 *pointer)
{
    u64 instance = bpf_get_current_pid_tgid();
    u32 key = 0;
    struct server_scx_state_v2 event;
    struct newa_state_receiver *receiver;

    if ((u32)(instance >> 32) != control_state.selected_tgid)
        return 0;
    receiver = bpf_map_lookup_elem(&newa_state_rx, &key);
    if (!receiver)
        return 0;
    if ((u32)instance != (u32)(instance >> 32) || bpf_probe_read_user(&event, sizeof(event), pointer))
        newa_state_invalidate(receiver);
    else if (newa_state_accept(receiver, &event, (u32)instance) && receiver->active)
        observe_phase(receiver->phase);
    control_state.current_phase = receiver->active ? receiver->phase : LLAMA_SCX_PHASE_UNKNOWN;
    return 0;
}

SEC(".struct_ops.link")
struct sched_ext_ops llama_ops = {
	.select_cpu = (void *)llama_select_cpu,
	.enqueue = (void *)llama_enqueue,
	.dispatch = (void *)llama_dispatch,
	.running = (void *)llama_running,
	.stopping = (void *)llama_stopping,
	.enable = (void *)llama_enable,
	.init = (void *)llama_init,
	.exit = (void *)llama_exit,
#ifdef NEW_A_DIAGNOSTICS
	.set_cpumask = (void *)new_a_set_cpumask,
#endif
	.flags = SCX_OPS_SWITCH_PARTIAL,
	.name = "llama_new_a",
};

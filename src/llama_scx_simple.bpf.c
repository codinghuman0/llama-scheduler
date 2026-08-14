/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Renamed baseline derived from Linux v6.17 tools/sched_ext/scx_simple.bpf.c.
 * Instrumentation below observes existing decisions only.  It never changes a
 * CPU choice, DSQ, queue order, vtime calculation, slice, or wake-up path.
 */
#define BPF_NO_KFUNC_PROTOTYPES
#define LLAMA_BPF
#include "vmlinux.h"
#include <linux/errno.h>
#include <bpf/bpf_core_read.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "llama_instrumentation.h"

char LICENSE[] SEC("license") = "GPL";
const volatile bool fifo_sched;

#define SHARED_DSQ 0
#define EXIT_DUMP_LEN 32768

struct exit_record {
	s32 kind;
	s64 exit_code;
	char reason[128];
	char message[1024];
};

struct exit_record exit_record SEC(".data");
char exit_dump[EXIT_DUMP_LEN] SEC(".data");

/* Existing baseline counters retained for the original loader status line. */
struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(u64));
	__uint(max_entries, 2); /* [local, shared DSQ] */
} stats SEC(".maps");

/* High-frequency aggregate counters are per-CPU and bounded to one key. */
struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(struct llama_cpu_stats));
	__uint(max_entries, 1);
} instrumentation_cpu_stats SEC(".maps");

/* Live tracking is bounded; completed records survive disable for final output. */
struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(key_size, sizeof(struct llama_task_key));
	__uint(value_size, sizeof(struct llama_task_live));
	__uint(max_entries, LLAMA_MAX_TRACKED_TASKS);
} live_task_stats SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(key_size, sizeof(struct llama_task_key));
	__uint(value_size, sizeof(struct llama_task_record));
	__uint(max_entries, LLAMA_MAX_TRACKED_TASKS);
} completed_task_stats SEC(".maps");

/* Low-frequency enable/disable bookkeeping only; spin lock avoids global races. */
struct {
	__uint(type, BPF_MAP_TYPE_ARRAY);
	__uint(key_size, sizeof(u32));
	__uint(value_size, sizeof(struct llama_tracking_state));
	__uint(max_entries, 1);
} tracking_state SEC(".maps");

static u64 vtime_now;

/* Kfunc signatures validated against recorded Ubuntu 7.0.0-28-generic BTF; source basis is Linux v6.17. */
s32 scx_bpf_create_dsq(u64 dsq_id, s32 node) __ksym;
s32 scx_bpf_select_cpu_dfl(struct task_struct *p, s32 prev_cpu,
			   u64 wake_flags, bool *is_idle) __ksym;
void scx_bpf_dsq_insert(struct task_struct *p, u64 dsq_id, u64 slice,
			u64 enq_flags) __ksym;
void scx_bpf_dsq_insert_vtime(struct task_struct *p, u64 dsq_id, u64 slice,
				      u64 vtime, u64 enq_flags) __ksym;
bool scx_bpf_dsq_move_to_local(u64 dsq_id) __ksym;

#define BPF_STRUCT_OPS(name, args...) \
	SEC("struct_ops/" #name) BPF_PROG(name, ##args)
#define BPF_STRUCT_OPS_SLEEPABLE(name, args...) \
	SEC("struct_ops.s/" #name) BPF_PROG(name, ##args)

static __always_inline bool time_before(u64 a, u64 b)
{
	return (s64)(a - b) < 0;
}

static __always_inline void stat_inc(u32 index)
{
	u64 *count = bpf_map_lookup_elem(&stats, &index);
	if (count)
		(*count)++;
}

static __always_inline struct llama_cpu_stats *cpu_stats(void)
{
	u32 key = 0;

	return bpf_map_lookup_elem(&instrumentation_cpu_stats, &key);
}

#define CPU_STAT_INC(member) do { \
	struct llama_cpu_stats *cpu_stats__ = cpu_stats(); \
	if (cpu_stats__) \
		cpu_stats__->member++; \
} while (0)

#define CPU_STAT_ADD(member, value) do { \
	struct llama_cpu_stats *cpu_stats__ = cpu_stats(); \
	if (cpu_stats__) \
		cpu_stats__->member += (value); \
} while (0)

static __always_inline void task_key(struct task_struct *p,
				     struct llama_task_key *key)
{
	key->pid = BPF_CORE_READ(p, pid);
	key->reserved = 0;
	key->start_time = BPF_CORE_READ(p, start_time);
}

static __always_inline struct llama_task_live *lookup_live(struct task_struct *p,
						    struct llama_task_key *key)
{
	struct llama_task_live *live;

	task_key(p, key);
	live = bpf_map_lookup_elem(&live_task_stats, key);
	if (!live)
		CPU_STAT_INC(task_lookup_failures);
	return live;
}

static __always_inline void tracking_add(void)
{
	u32 key = 0;
	struct llama_tracking_state *state = bpf_map_lookup_elem(&tracking_state, &key);

	if (!state) {
		CPU_STAT_INC(tracking_state_lookup_failures);
		return;
	}
	bpf_spin_lock(&state->lock);
	state->current_tracked_tasks++;
	if (state->peak_tracked_tasks < state->current_tracked_tasks)
		state->peak_tracked_tasks = state->current_tracked_tasks;
	bpf_spin_unlock(&state->lock);
}

static __always_inline void tracking_remove(void)
{
	u32 key = 0;
	struct llama_tracking_state *state = bpf_map_lookup_elem(&tracking_state, &key);

	if (!state) {
		CPU_STAT_INC(tracking_state_lookup_failures);
		return;
	}
	bpf_spin_lock(&state->lock);
	if (state->current_tracked_tasks)
		state->current_tracked_tasks--;
	bpf_spin_unlock(&state->lock);
}

static __always_inline void track_enable(struct task_struct *p)
{
	struct llama_task_key key;
	struct llama_task_live initial = {
		.last_cpu = LLAMA_INVALID_CPU,
	};
	int err;

	task_key(p, &key);
	err = bpf_map_update_elem(&live_task_stats, &key, &initial, BPF_NOEXIST);
	if (!err) {
		tracking_add();
		return;
	}
	/* A duplicate identity is stale/duplicate bookkeeping; replacement is neutral. */
	if (err == -EEXIST)
		err = bpf_map_update_elem(&live_task_stats, &key, &initial, BPF_ANY);
	if (err) {
		CPU_STAT_INC(task_update_failures);
		if (err == -ENOSPC)
			CPU_STAT_INC(task_capacity_failures);
	}
}

static __always_inline void track_disable(struct task_struct *p)
{
	struct llama_task_key key;
	struct llama_task_live *live;
	struct llama_task_record record = {};
	int err;

	task_key(p, &key);
	live = bpf_map_lookup_elem(&live_task_stats, &key);
	if (!live)
		return;
	bpf_spin_lock(&live->lock);
	record.last_cpu = live->last_cpu;
	record.enqueue_count = live->enqueue_count;
	record.running_count = live->running_count;
	record.stopping_count = live->stopping_count;
	record.runtime_ns = live->runtime_ns;
	record.queue_wait_ns = live->queue_wait_ns;
	record.migration_count = live->migration_count;
	bpf_spin_unlock(&live->lock);
	err = bpf_map_update_elem(&completed_task_stats, &key, &record, BPF_ANY);
	if (err) {
		CPU_STAT_INC(completed_record_failures);
		if (err == -ENOSPC)
			CPU_STAT_INC(task_capacity_failures);
	}
	err = bpf_map_delete_elem(&live_task_stats, &key);
	if (err) {
		CPU_STAT_INC(task_cleanup_failures);
		return;
	}
	tracking_remove();
}

s32 BPF_STRUCT_OPS(llama_simple_select_cpu, struct task_struct *p,
			   s32 prev_cpu, u64 wake_flags)
{
	bool is_idle = false;
	s32 cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);

	if (is_idle) {
		stat_inc(0);
		CPU_STAT_INC(direct_local_insertions);
		scx_bpf_dsq_insert(p, SCX_DSQ_LOCAL, SCX_SLICE_DFL, 0);
	}
	return cpu;
}

void BPF_STRUCT_OPS(llama_simple_enqueue, struct task_struct *p,
			    u64 enq_flags)
{
	struct llama_task_key key;
	struct llama_task_live *live;
	u64 now = bpf_ktime_get_ns();

	CPU_STAT_INC(enqueue_count);
	live = lookup_live(p, &key);
	if (live) {
		bpf_spin_lock(&live->lock);
		live->enqueue_count++;
		/* Latest enqueue wins when a task is re-enqueued before it runs. */
		live->last_enqueue_ns = now;
		bpf_spin_unlock(&live->lock);
	}
	CPU_STAT_INC(shared_dsq_insertions);
	stat_inc(1);
	if (fifo_sched) {
		scx_bpf_dsq_insert(p, SHARED_DSQ, SCX_SLICE_DFL, enq_flags);
	} else {
		u64 vtime = p->scx.dsq_vtime;

		if (time_before(vtime, vtime_now - SCX_SLICE_DFL))
			vtime = vtime_now - SCX_SLICE_DFL;
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime,
					 enq_flags);
	}
}

void BPF_STRUCT_OPS(llama_simple_dispatch, s32 cpu, struct task_struct *prev)
{
	CPU_STAT_INC(dispatch_callbacks);
	scx_bpf_dsq_move_to_local(SHARED_DSQ);
}

void BPF_STRUCT_OPS(llama_simple_running, struct task_struct *p)
{
	struct llama_task_key key;
	struct llama_task_live *live;
	u64 now = bpf_ktime_get_ns();
	u64 waited = 0;
	bool migrated = false;
	u32 cpu = bpf_get_smp_processor_id();

	CPU_STAT_INC(running_callbacks);
	live = lookup_live(p, &key);
	if (live) {
		bpf_spin_lock(&live->lock);
		live->running_count++;
		if (live->last_enqueue_ns) {
			waited = now - live->last_enqueue_ns;
			live->queue_wait_ns += waited;
			live->last_enqueue_ns = 0;
		}
		if (live->last_cpu != LLAMA_INVALID_CPU && live->last_cpu != cpu) {
			live->migration_count++;
			migrated = true;
		}
		live->last_cpu = cpu;
		live->last_running_ns = now;
		bpf_spin_unlock(&live->lock);
	}
	if (waited)
		CPU_STAT_ADD(queue_wait_ns, waited);
	if (migrated)
		CPU_STAT_INC(migration_count);
	if (!fifo_sched && time_before(vtime_now, p->scx.dsq_vtime))
		vtime_now = p->scx.dsq_vtime;
}

void BPF_STRUCT_OPS(llama_simple_stopping, struct task_struct *p, bool runnable)
{
	struct llama_task_key key;
	struct llama_task_live *live;
	u64 now = bpf_ktime_get_ns();
	u64 runtime = 0;

	CPU_STAT_INC(stopping_callbacks);
	live = lookup_live(p, &key);
	if (live) {
		bpf_spin_lock(&live->lock);
		live->stopping_count++;
		if (live->last_running_ns) {
			runtime = now - live->last_running_ns;
			live->runtime_ns += runtime;
			live->last_running_ns = 0;
		}
		bpf_spin_unlock(&live->lock);
	}
	if (runtime)
		CPU_STAT_ADD(runtime_ns, runtime);
	if (!fifo_sched)
		p->scx.dsq_vtime += (SCX_SLICE_DFL - p->scx.slice) * 100 /
			p->scx.weight;
}

void BPF_STRUCT_OPS(llama_simple_enable, struct task_struct *p)
{
	track_enable(p);
	p->scx.dsq_vtime = vtime_now;
}

void BPF_STRUCT_OPS(llama_simple_disable, struct task_struct *p)
{
	track_disable(p);
}

s32 BPF_STRUCT_OPS_SLEEPABLE(llama_simple_init)
{
	return scx_bpf_create_dsq(SHARED_DSQ, -1);
}

void BPF_STRUCT_OPS(llama_simple_exit, struct scx_exit_info *info)
{
	exit_record.kind = info->kind;
	exit_record.exit_code = info->exit_code;
	bpf_probe_read_kernel_str(exit_record.reason, sizeof(exit_record.reason),
				  info->reason);
	bpf_probe_read_kernel_str(exit_record.message, sizeof(exit_record.message),
				  info->msg);
	bpf_probe_read_kernel_str(exit_dump, sizeof(exit_dump), info->dump);
}

SEC(".struct_ops.link")
struct sched_ext_ops llama_simple_ops = {
	.select_cpu = (void *)llama_simple_select_cpu,
	.enqueue = (void *)llama_simple_enqueue,
	.dispatch = (void *)llama_simple_dispatch,
	.running = (void *)llama_simple_running,
	.stopping = (void *)llama_simple_stopping,
	.enable = (void *)llama_simple_enable,
	.disable = (void *)llama_simple_disable,
	.init = (void *)llama_simple_init,
	.exit = (void *)llama_simple_exit,
	.flags = SCX_OPS_SWITCH_PARTIAL,
	.name = "llama_simple",
};

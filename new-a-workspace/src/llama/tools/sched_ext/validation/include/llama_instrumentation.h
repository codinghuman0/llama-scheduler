/* SPDX-License-Identifier: GPL-2.0 */
#ifndef LLAMA_INSTRUMENTATION_H
#define LLAMA_INSTRUMENTATION_H

#include "llama_phase.h"

#define LLAMA_INSTRUMENTATION_SCHEMA_VERSION 1
#define LLAMA_MAX_TRACKED_TASKS 1024
#define LLAMA_INVALID_CPU ((__u32)-1)

struct llama_phase_observation {
	__u64 select_cpu;
	__u64 enqueue;
	__u64 running;
	__u64 stopping;
};

#ifdef LLAMA_BPF
#define LLAMA_SPIN_LOCK struct bpf_spin_lock
#else
#define LLAMA_SPIN_LOCK __u32
#endif

struct llama_task_key {
	__u32 pid;
	__u32 reserved;
	__u64 start_time;
};

/* Exportable final statistics; no lock so userspace can read it directly. */
struct llama_task_record {
	__u32 last_cpu;
	__u32 reserved;
	__u64 enqueue_count;
	__u64 running_count;
	__u64 stopping_count;
	__u64 runtime_ns;
	__u64 queue_wait_ns;
	__u64 migration_count;
};

/* Live values are protected because callbacks can observe one task on different CPUs. */
struct llama_task_live {
	LLAMA_SPIN_LOCK lock;
	__u32 last_cpu;
	__u64 last_enqueue_ns;
	__u64 last_running_ns;
	__u64 enqueue_count;
	__u64 running_count;
	__u64 stopping_count;
	__u64 runtime_ns;
	__u64 queue_wait_ns;
	__u64 migration_count;
};

struct llama_cpu_stats {
	__u64 enqueue_count;
	__u64 direct_local_insertions;
	__u64 shared_dsq_insertions;
	__u64 dispatch_callbacks;
	__u64 running_callbacks;
	__u64 stopping_callbacks;
	__u64 runtime_ns;
	__u64 queue_wait_ns;
	__u64 migration_count;
	__u64 task_lookup_failures;
	__u64 task_update_failures;
	__u64 task_capacity_failures;
	__u64 task_cleanup_failures;
	__u64 tracking_state_lookup_failures;
	__u64 completed_record_failures;
};

struct llama_tracking_state {
	LLAMA_SPIN_LOCK lock;
	__u64 current_tracked_tasks;
	__u64 peak_tracked_tasks;
};

#endif /* LLAMA_INSTRUMENTATION_H */

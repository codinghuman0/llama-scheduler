/* SPDX-License-Identifier: GPL-2.0 */
#ifndef LLAMA_NEW_A_H
#define LLAMA_NEW_A_H

#ifndef LLAMA_SCX_BPF
#include <linux/types.h>
#endif

#define NEW_A_MAX_CPUS 1024
#define NEW_A_MAGIC 0x4e455741

struct new_a_topology {
	__u32 magic;
	__u32 enabled;
	__u32 count[3];
	__u32 cpus[3][NEW_A_MAX_CPUS];
};

#ifdef NEW_A_DIAGNOSTICS
#define NEW_A_EVENT_CAPACITY 32
#define NEW_A_MASK_WORDS (NEW_A_MAX_CPUS / 64)

struct new_a_diagnostic_config {
	__u32 mask_bits;
};

enum new_a_event_kind {
	NEW_A_EVENT_MASK_VIOLATION = 1,
	NEW_A_EVENT_TRACKING_FAILURE = 2,
	NEW_A_EVENT_SET_CPUMASK = 3,
};

enum new_a_callback {
	NEW_A_CALLBACK_RUNNING = 1,
	NEW_A_CALLBACK_STOPPING = 2,
	NEW_A_CALLBACK_SET_CPUMASK = 3,
};

struct new_a_event {
	__u64 timestamp_ns;
	__u64 actor_pid_tgid;
	__u64 task_start_time;
	__u32 sequence;
	__u32 kind;
	__u32 callback;
	__u32 tgid;
	__u32 tid;
	__u32 callback_cpu;
	__s32 task_cpu;
	__u32 nr_cpus_allowed;
	__u32 migration_disabled;
	__u32 migration_pending;
	__u32 on_cpu;
	__u32 on_rq;
	__u32 mask_bits;
	__u32 allowed_weight;
	__u32 regular_weight;
	__u32 requested_weight;
	__s32 allowed_read_error;
	__s32 regular_read_error;
	__s32 requested_read_error;
	__s32 callback_allowed;
	__s32 task_allowed;
	__u64 allowed[NEW_A_MASK_WORDS];
	__u64 regular[NEW_A_MASK_WORDS];
	__u64 requested[NEW_A_MASK_WORDS];
};

struct new_a_stats {
	__u64 selected[4];
	__u64 running;
	__u64 stopping;
	__u64 runtime_ns;
	__u64 migrations;
	__u64 mask_violations;
	__u64 tracking_failures;
	__u64 phase_seen;
	__u64 events_attempted;
	__u64 events_dropped;
};
#endif

#endif

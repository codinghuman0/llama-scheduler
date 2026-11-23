/* SPDX-License-Identifier: GPL-2.0 */
#ifndef LLAMA_PHASE_H
#define LLAMA_PHASE_H

#ifndef LLAMA_BPF
#include <linux/types.h>
#endif

#define LLAMA_SCX_EVENT_VERSION 1
#define LLAMA_PHASE_COUNT 4
#define LLAMA_PHASE_STATE_MAX 64

enum llama_phase {
	LLAMA_PHASE_UNKNOWN = 0,
	LLAMA_PHASE_PREFILL = 1,
	LLAMA_PHASE_DECODE = 2,
	LLAMA_PHASE_MIXED = 3,
};

enum llama_phase_source {
	LLAMA_PHASE_SOURCE_NONE = 0,
	LLAMA_PHASE_SOURCE_SOCKET = 1,
	LLAMA_PHASE_SOURCE_UPROBE = 2,
};

/* Semantic marker values are a source ABI and are translated explicitly. */
enum llama_scx_phase_v1 {
	LLAMA_SCX_PHASE_V1_UNKNOWN = 0,
	LLAMA_SCX_PHASE_V1_PREFILL = 1,
	LLAMA_SCX_PHASE_V1_DECODE = 2,
	LLAMA_SCX_PHASE_V1_MIXED = 3,
};

struct llama_scx_event_v1 {
	__u64 version;
	__u64 run_id;
	__u64 call_id;
	__u64 retry;
	__u64 phase;
	__u64 profile;
	__u64 n_prefill;
	__u64 n_decode;
	__u64 n_unknown;
	__s64 result;
};

struct llama_phase_value {
	__u32 phase;
	__u32 active;
	__u32 source;
	__u32 reserved;
	__u64 sequence;
	__u64 run_id;
	__u64 call_id;
	__u64 retry;
	__u64 n_prefill;
	__u64 n_decode;
	__u64 n_unknown;
	__s64 result;
};

struct llama_uprobe_config {
	__u32 enabled;
	__u32 target_tgid;
};

struct llama_uprobe_stats {
	__u64 begin_events;
	__u64 end_events;
	__u64 begin_unknown;
	__u64 begin_prefill;
	__u64 begin_decode;
	__u64 begin_mixed;
	__u64 abi_failures;
	__u64 user_read_failures;
	__u64 unsupported_phases;
	__u64 stale_end_events;
	__u64 map_update_failures;
	__u64 filtered_events;
};

enum llama_scx_state_result {
	LLAMA_SCX_STATE_OK = 0,
	LLAMA_SCX_STATE_BAD_VERSION = -1,
	LLAMA_SCX_STATE_BAD_PHASE = -2,
	LLAMA_SCX_STATE_MISMATCH = -3,
};

static __inline int llama_scx_phase_translate(__u64 source_phase, __u32 *phase)
{
	switch (source_phase) {
	case LLAMA_SCX_PHASE_V1_UNKNOWN:
		*phase = LLAMA_PHASE_UNKNOWN;
		return LLAMA_SCX_STATE_OK;
	case LLAMA_SCX_PHASE_V1_PREFILL:
		*phase = LLAMA_PHASE_PREFILL;
		return LLAMA_SCX_STATE_OK;
	case LLAMA_SCX_PHASE_V1_DECODE:
		*phase = LLAMA_PHASE_DECODE;
		return LLAMA_SCX_STATE_OK;
	case LLAMA_SCX_PHASE_V1_MIXED:
		*phase = LLAMA_PHASE_MIXED;
		return LLAMA_SCX_STATE_OK;
	default:
		return LLAMA_SCX_STATE_BAD_PHASE;
	}
}

static __inline int llama_scx_begin_value(struct llama_phase_value *value,
					  const struct llama_scx_event_v1 *event)
{
	__u32 phase;
	int result;

	if (event->version != LLAMA_SCX_EVENT_VERSION)
		return LLAMA_SCX_STATE_BAD_VERSION;
	result = llama_scx_phase_translate(event->phase, &phase);
	if (result)
		return result;
	value->phase = phase;
	value->active = 1;
	value->source = LLAMA_PHASE_SOURCE_UPROBE;
	value->reserved = 0;
	value->sequence = 0;
	value->run_id = event->run_id;
	value->call_id = event->call_id;
	value->retry = event->retry;
	value->n_prefill = event->n_prefill;
	value->n_decode = event->n_decode;
	value->n_unknown = event->n_unknown;
	value->result = event->result;
	return LLAMA_SCX_STATE_OK;
}

static __inline int llama_scx_end_matches(const struct llama_phase_value *value,
					   const struct llama_scx_event_v1 *event)
{
	__u32 phase;
	int result;

	if (event->version != LLAMA_SCX_EVENT_VERSION)
		return LLAMA_SCX_STATE_BAD_VERSION;
	result = llama_scx_phase_translate(event->phase, &phase);
	if (result)
		return result;
	if (!value->active || value->source != LLAMA_PHASE_SOURCE_UPROBE ||
	    value->phase != phase || value->run_id != event->run_id ||
	    value->call_id != event->call_id || value->retry != event->retry)
		return LLAMA_SCX_STATE_MISMATCH;
	return LLAMA_SCX_STATE_OK;
}

static __inline void llama_scx_end_value(struct llama_phase_value *value,
					 const struct llama_scx_event_v1 *event)
{
	value->phase = LLAMA_PHASE_UNKNOWN;
	value->active = 0;
	value->result = event->result;
}

_Static_assert(sizeof(struct llama_scx_event_v1) == 80, "SCX marker ABI v1 size");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, version) == 0, "SCX marker version offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, run_id) == 8, "SCX marker run_id offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, call_id) == 16, "SCX marker call_id offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, retry) == 24, "SCX marker retry offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, phase) == 32, "SCX marker phase offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, profile) == 40, "SCX marker profile offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, n_prefill) == 48, "SCX marker n_prefill offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, n_decode) == 56, "SCX marker n_decode offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, n_unknown) == 64, "SCX marker n_unknown offset");
_Static_assert(__builtin_offsetof(struct llama_scx_event_v1, result) == 72, "SCX marker result offset");
_Static_assert(sizeof(struct llama_phase_value) == 80, "phase state ABI");
_Static_assert(sizeof(struct llama_uprobe_config) == 8, "uprobe config ABI");
_Static_assert(sizeof(struct llama_uprobe_stats) == 96, "uprobe stats ABI");

#endif /* LLAMA_PHASE_H */

/* SPDX-License-Identifier: GPL-2.0 */
#ifndef LLAMA_SCX_STATE_H
#define LLAMA_SCX_STATE_H

#ifndef LLAMA_SCX_BPF
#include <linux/types.h>
#endif

enum llama_scx_phase {
	LLAMA_SCX_PHASE_UNKNOWN = 0,
	LLAMA_SCX_PHASE_PREFILL = 1,
	LLAMA_SCX_PHASE_DECODE = 2,
	LLAMA_SCX_PHASE_MIXED = 3,
};

struct llama_scx_control_state {
	__u32 selected_tgid;
	__u32 current_phase;
	__u32 exit_kind;
};

_Static_assert(sizeof(__u32) == 4, "SCX control fields must be 32-bit");
_Static_assert(sizeof(struct llama_scx_control_state) == 12, "SCX control state size");
_Static_assert(__builtin_offsetof(struct llama_scx_control_state, selected_tgid) == 0, "SCX selected TGID offset");
_Static_assert(__builtin_offsetof(struct llama_scx_control_state, current_phase) == 4, "SCX phase offset");
_Static_assert(__builtin_offsetof(struct llama_scx_control_state, exit_kind) == 8, "SCX exit offset");

#endif /* LLAMA_SCX_STATE_H */

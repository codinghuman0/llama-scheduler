/* SPDX-License-Identifier: GPL-2.0 */
#pragma once

#include "llama_scx_state.h"
#include "new_a.h"

struct newa_dispatch_topology {
    struct new_a_topology tiers;
    /* The prepared Intel P representatives occupy the whole first tier. */
    __u32 prefill_pcore_count;
};

static inline int newa_decode_handoff_eligible(__u32 phase, __u32 selected, __u32 tgid,
                                               int migration_disabled, int reenqueue)
{
    return phase == LLAMA_SCX_PHASE_DECODE && selected && tgid == selected &&
           !migration_disabled && !reenqueue;
}

static inline int newa_locality_eligible(__u32 phase, __u32 selected, __u32 tgid, int all_active)
{
    return selected && tgid == selected &&
           (all_active ? phase >= LLAMA_SCX_PHASE_PREFILL && phase <= LLAMA_SCX_PHASE_MIXED
                       : phase == LLAMA_SCX_PHASE_DECODE);
}

struct handoff_counters {
    __u64 attempts[4];
    __u64 moved[4];
    __u64 locality_attempts[4];
    __u64 locality_hits[4];
#ifdef NEW_A_PREFILL_PAIR
    __u64 prefill_attempts[4];
    __u64 prefill_hits[4];
#ifndef NEW_A_RUNTIME_LITE
    __u64 running_starts[4];
#endif
#endif
};

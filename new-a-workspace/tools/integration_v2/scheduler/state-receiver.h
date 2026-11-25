/* SPDX-License-Identifier: GPL-2.0 */
#pragma once

#include "newa-state-abi.h"

struct newa_state_receiver {
    __UINT64_TYPE__ run_id;
    __UINT64_TYPE__ sequence;
    __UINT64_TYPE__ rejected;
    __UINT64_TYPE__ idle_events;
    __UINT32_TYPE__ phase;
    __UINT32_TYPE__ active;
    __UINT32_TYPE__ writer_tid;
    __UINT32_TYPE__ invalid;
};

_Static_assert(sizeof(struct newa_state_receiver) == 48, "receiver map ABI");

static inline void newa_state_invalidate(struct newa_state_receiver *state)
{
    state->invalid = 1;
    state->rejected++;
    state->phase = 0;
    state->active = 0;
}

static inline int newa_state_accept(struct newa_state_receiver *state,
                                   const struct server_scx_state_v2 *event,
                                   __UINT32_TYPE__ tid)
{
    if (state->invalid || !state->run_id || event->version != 2 || event->reserved ||
        event->run_id != state->run_id || !event->sequence || event->sequence != state->sequence + 1 ||
        event->phase > 3 || event->active > 1 || (!event->active && event->phase) ||
        (state->writer_tid && tid != state->writer_tid) ||
        (event->active == state->active && event->phase == state->phase)) {
        newa_state_invalidate(state);
        return 0;
    }
    state->writer_tid = tid;
    state->sequence = event->sequence;
    state->phase = event->phase;
    state->active = event->active;
    state->idle_events += !event->active;
    return 1;
}

/* SPDX-License-Identifier: GPL-2.0 */
#include <assert.h>
#include "state-receiver.h"
#include "handoff-policy.h"

int main(void)
{
    struct newa_state_receiver rx = { .run_id = 13 };
    struct server_scx_state_v2 event = { 2, 0, 1, 0, 13, 1 };
    assert(newa_state_accept(&rx, &event, 88));
    assert(rx.active && rx.phase == 0 && !rx.idle_events);
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 88, 0, 0));
    event.sequence++;
    event.phase = LLAMA_SCX_PHASE_DECODE;
    assert(newa_state_accept(&rx, &event, 88));
    assert(newa_decode_handoff_eligible(rx.phase, 88, 88, 0, 0));
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 89, 0, 0));
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 88, 1, 0));
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 88, 0, 1));
    assert(!newa_decode_handoff_eligible(rx.phase, 0, 0, 0, 0));
    assert(!newa_decode_handoff_eligible(LLAMA_SCX_PHASE_PREFILL, 88, 88, 0, 0));
    assert(newa_locality_eligible(LLAMA_SCX_PHASE_DECODE, 88, 88, 0));
    assert(!newa_locality_eligible(LLAMA_SCX_PHASE_PREFILL, 88, 88, 0));
    assert(newa_locality_eligible(LLAMA_SCX_PHASE_PREFILL, 88, 88, 1));
    assert(!newa_locality_eligible(LLAMA_SCX_PHASE_DECODE, 88, 89, 1));
    assert(!newa_locality_eligible(LLAMA_SCX_PHASE_UNKNOWN, 88, 88, 1));
    event.sequence++;
    event.phase = 3;
    assert(newa_state_accept(&rx, &event, 88));
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 88, 0, 0));
    event.sequence++;
    event.phase = event.active = 0;
    assert(newa_state_accept(&rx, &event, 88));
    assert(!rx.active && rx.idle_events == 1);
    assert(!newa_decode_handoff_eligible(rx.phase, 88, 88, 0, 0));
    event.sequence++;
    event.active = 1;
    assert(!newa_state_accept(&rx, &event, 89));
    assert(rx.invalid && !rx.active && rx.rejected == 1);
    assert(!newa_state_accept(&rx, &event, 88));

    for (int scenario = 0; scenario < 7; scenario++) {
        struct newa_state_receiver fresh = { .run_id = 13 };
        struct server_scx_state_v2 bad = { 2, 1, 1, 0, 13, 1 };
        switch (scenario) {
        case 0: bad.version = 1; break;
        case 1: bad.reserved = 1; break;
        case 2: bad.sequence = 2; break;
        case 3: bad.run_id = 14; break;
        case 4: bad.phase = 4; break;
        case 5: bad.active = 0; break;
        case 6: bad.active = 2; break;
        }
        assert(!newa_state_accept(&fresh, &bad, 88));
        assert(fresh.invalid && !fresh.active && !fresh.sequence);
    }
    return 0;
}

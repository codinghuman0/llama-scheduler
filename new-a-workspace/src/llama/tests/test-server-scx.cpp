#include "server-phase.h"

#undef NDEBUG
#include <cassert>
#include <vector>

int main() {
    server_scx_phase_state state;
    std::vector<uint32_t> emitted;
    const auto transition = [&](server_scx_phase phase) {
        return state.transition(phase, [&](uint32_t value) { emitted.push_back(value); });
    };

    assert(state.current() == SERVER_SCX_PHASE_UNKNOWN);

    assert(transition(SERVER_SCX_PHASE_PREFILL));
    assert((emitted == std::vector<uint32_t>{ SERVER_SCX_PHASE_PREFILL }));

    assert(!transition(SERVER_SCX_PHASE_PREFILL));
    assert(emitted.size() == 1);

    assert(transition(SERVER_SCX_PHASE_DECODE));
    assert((emitted == std::vector<uint32_t>{ SERVER_SCX_PHASE_PREFILL, SERVER_SCX_PHASE_DECODE }));

    assert(!transition(SERVER_SCX_PHASE_DECODE));
    assert(emitted.size() == 2);

    assert(transition(SERVER_SCX_PHASE_PREFILL));
    assert((emitted == std::vector<uint32_t>{ SERVER_SCX_PHASE_PREFILL, SERVER_SCX_PHASE_DECODE, SERVER_SCX_PHASE_PREFILL }));

    assert(transition(SERVER_SCX_PHASE_MIXED));
    assert(emitted.back() == SERVER_SCX_PHASE_MIXED);

    assert(server_batch_phase_classify(0, 0, 0) == SERVER_BATCH_PHASE_UNKNOWN);
    assert(server_batch_phase_classify(1, 0, 0) == SERVER_BATCH_PHASE_PREFILL);
    assert(server_batch_phase_classify(0, 1, 0) == SERVER_BATCH_PHASE_DECODE);
    assert(server_batch_phase_classify(1, 1, 0) == SERVER_BATCH_PHASE_MIXED);
    assert(server_batch_phase_classify(1, 1, 1) == SERVER_BATCH_PHASE_UNKNOWN);

    for (int32_t n_prefill = 0; n_prefill <= 2; ++n_prefill) {
        for (int32_t n_decode = 0; n_decode <= 2; ++n_decode) {
            for (int32_t n_unknown = 0; n_unknown <= 2; ++n_unknown) {
                assert(server_batch_phase_is_valid(server_batch_phase_classify(n_prefill, n_decode, n_unknown)));
            }
        }
    }
}

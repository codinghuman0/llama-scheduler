#pragma once

#include <cstdint>

enum server_batch_phase : uint32_t {
    SERVER_BATCH_PHASE_UNKNOWN,
    SERVER_BATCH_PHASE_PREFILL,
    SERVER_BATCH_PHASE_DECODE,
    SERVER_BATCH_PHASE_MIXED,
};

enum server_scx_phase : uint32_t {
    SERVER_SCX_PHASE_UNKNOWN = 0,
    SERVER_SCX_PHASE_PREFILL = 1,
    SERVER_SCX_PHASE_DECODE  = 2,
    SERVER_SCX_PHASE_MIXED   = 3,
};

static_assert(uint32_t(SERVER_SCX_PHASE_UNKNOWN) == uint32_t(SERVER_BATCH_PHASE_UNKNOWN) &&
        uint32_t(SERVER_SCX_PHASE_PREFILL) == uint32_t(SERVER_BATCH_PHASE_PREFILL) &&
        uint32_t(SERVER_SCX_PHASE_DECODE) == uint32_t(SERVER_BATCH_PHASE_DECODE) &&
        uint32_t(SERVER_SCX_PHASE_MIXED) == uint32_t(SERVER_BATCH_PHASE_MIXED), "SCX phase transition ABI v1");

constexpr server_batch_phase server_batch_phase_classify(int32_t n_prefill, int32_t n_decode, int32_t n_unknown) {
    if (n_unknown != 0) {
        return SERVER_BATCH_PHASE_UNKNOWN;
    }
    if (n_prefill != 0 && n_decode != 0) {
        return SERVER_BATCH_PHASE_MIXED;
    }
    if (n_prefill != 0) {
        return SERVER_BATCH_PHASE_PREFILL;
    }
    if (n_decode != 0) {
        return SERVER_BATCH_PHASE_DECODE;
    }
    return SERVER_BATCH_PHASE_UNKNOWN;
}

constexpr bool server_batch_phase_is_valid(server_batch_phase phase) {
    return phase == SERVER_BATCH_PHASE_UNKNOWN ||
           phase == SERVER_BATCH_PHASE_PREFILL ||
           phase == SERVER_BATCH_PHASE_DECODE ||
           phase == SERVER_BATCH_PHASE_MIXED;
}

class server_scx_phase_state {
    server_scx_phase phase = SERVER_SCX_PHASE_UNKNOWN;

public:
    server_scx_phase current() const {
        return phase;
    }

    template<typename Emit>
    bool transition(server_scx_phase next_phase, Emit emit) {
        if (phase == next_phase) {
            return false;
        }
        phase = next_phase;
        emit(static_cast<uint32_t>(phase));
        return true;
    }
};

#include "server-scx.h"

#include <charconv>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <string_view>

#ifdef LLAMA_SCX_PHASE_HINT
extern "C" __attribute__((noinline, used, visibility("default")))
void llama_scx_phase_v1(uint32_t phase) {
    __asm__ __volatile__("nop" : : "r"(phase) : "memory");
}
#endif

#ifdef __linux__
extern "C" __attribute__((noinline, used, visibility("default")))
void llama_scx_phase_set_v2(const server_scx_state_v2 * event) {
    __asm__ __volatile__("nop; nop; nop" : : "r"(event) : "memory");
}
#endif

#ifdef LLAMA_SCX_PHASE_TRACE
extern "C" __attribute__((noinline, used, visibility("default")))
void llama_scx_decode_begin_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop" : : "r"(event) : "memory");
}

extern "C" __attribute__((noinline, used, visibility("default")))
void llama_scx_decode_end_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop; nop" : : "r"(event) : "memory");
}
#endif

bool server_newa_transport::configure(uint64_t trace_id) {
    const char * requested = std::getenv("NEWA_PHASE_TRANSPORT");
    const std::string_view value = requested ? requested : trace_id ? "trace" : "off";
    const char * id = std::getenv("NEWA_STATE_RUN_ID");
    const char * log = std::getenv("NEWA_STATE_LOG");
    if (log && std::string_view(log) != "1") return false;
    state_log = log != nullptr;
    if (value != "state" && (id || state_log)) return false;
    if (value != "trace" && trace_id) return false;
    run_id = 0;
    if (value == "off") {
        mode = off;
        return true;
    }
#ifdef LLAMA_SCX_PHASE_HINT
    if (value == "scalar") {
        mode = scalar;
        return true;
    }
#endif
#ifdef LLAMA_SCX_PHASE_TRACE
    if (value == "trace" && trace_id) {
        mode = trace;
        run_id = trace_id;
        return true;
    }
#endif
#ifdef __linux__
    if (value == "state" && id) {
        const std::string_view number(id);
        const auto end = number.data() + number.size();
        const auto result = std::from_chars(number.data(), end, run_id);
        if (result.ec != std::errc{} || result.ptr != end || !run_id) return false;
        mode = state;
        return true;
    }
#endif
    return false;
}

const char * server_newa_transport::name() const {
    switch (mode) {
        case off: return "off";
        case scalar: return "scalar";
        case state: return "state";
        case trace: return "trace";
    }
    return "invalid";
}

void server_newa_transport::emit_scalar(uint32_t phase) const {
#ifdef LLAMA_SCX_PHASE_HINT
    if (mode == scalar) llama_scx_phase_v1(phase);
#else
    (void) phase;
#endif
}

void server_newa_transport::emit_state(const server_scx_state_v2 & event) const {
#ifdef __linux__
    llama_scx_phase_set_v2(&event);
#endif
    if (state_log && event.sequence <= 4096) {
        std::fprintf(stderr, "NEWA_STATE_V2 run=%" PRIu64 " seq=%" PRIu64 " phase=%u active=%u\n",
                     uint64_t(event.run_id), uint64_t(event.sequence), event.phase, event.active);
    }
}

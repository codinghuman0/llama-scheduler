#pragma once

#ifdef LLAMA_SCX_PHASE_HINT
#include "server-phase.h"
#include "ggml-backend.h"

extern "C" {
void llama_scx_phase_v1(uint32_t phase);

__attribute__((noinline, used, visibility("default")))
void llama_scx_phase_v1(uint32_t phase) {
    using phase_fn = void (*)(uint32_t);
    static phase_fn update = [] {
        auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
        if (!dev) return phase_fn(nullptr);
        auto * reg = ggml_backend_dev_backend_reg(dev);
        return (phase_fn) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_newa_phase");
    }();
    if (update) update(phase);
    __asm__ __volatile__("nop" : : "r"(phase) : "memory");
}
}
#endif

#ifdef LLAMA_SCX_PHASE_TRACE
#include "llama.h"
#include <cstdint>

// Keep the v1 layout in sync with llama-scheduler/include/llama_phase.h.
struct server_scx_event {
    uint64_t version;
    uint64_t run_id;
    uint64_t call_id;
    uint64_t retry;
    uint64_t phase;
    uint64_t profile;
    uint64_t n_prefill;
    uint64_t n_decode;
    uint64_t n_unknown;
    int64_t result;
};
static_assert(sizeof(server_scx_event) == 80, "SCX phase ABI v1");

extern "C" {
void llama_scx_decode_begin_v1(const server_scx_event * event);
void llama_scx_decode_end_v1(const server_scx_event * event);

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_begin_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop" : : "r"(event) : "memory");
}

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_end_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop; nop" : : "r"(event) : "memory");
}

}

class server_scx_scope {
    llama_context * ctx;
    server_scx_event event;
    bool active;
public:
    server_scx_scope(llama_context * ctx, server_scx_event event) : ctx(ctx), event(event), active(event.run_id != 0) {
        if (active) {
            llama_synchronize(ctx);
            llama_scx_decode_begin_v1(&this->event);
        }
    }
    server_scx_scope(const server_scx_scope &) = delete;
    server_scx_scope & operator=(const server_scx_scope &) = delete;
    void finish(int result) {
        if (active) {
            llama_synchronize(ctx);
            event.result = result;
            llama_scx_decode_end_v1(&event);
            active = false;
        }
    }
    ~server_scx_scope() { finish(-1); }
};
#endif

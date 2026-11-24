#pragma once

#include "server-phase.h"
#include "newa-state-abi.h"
#include "ggml-backend.h"
#include "llama.h"
#include <exception>

struct server_newa_transport {
    enum kind { off, scalar, state, trace };
    kind mode = off;
    uint64_t run_id = 0;
    bool state_log = false;

    bool configure(uint64_t trace_id);
    const char * name() const;
    void emit_scalar(uint32_t phase) const;
    void emit_state(const server_scx_state_v2 & event) const;
};

class server_scx_state_publisher {
    uint64_t sequence = 0;
    uint32_t last_phase = 0;
    bool last_active = false;

public:
    void publish(const server_newa_transport & transport, uint32_t phase, bool active) {
        if (!active) phase = 0;
        if (last_phase == phase && last_active == active) return;
        transport.emit_state({2, phase, uint32_t(active), 0, transport.run_id, ++sequence});
        last_phase = phase;
        last_active = active;
    }
};

template<typename Reconcile>
class server_scx_reconcile_scope {
    Reconcile reconcile;
    int exceptions = std::uncaught_exceptions();
public:
    explicit server_scx_reconcile_scope(Reconcile reconcile) : reconcile(reconcile) {}
    server_scx_reconcile_scope(const server_scx_reconcile_scope &) = delete;
    ~server_scx_reconcile_scope() { reconcile(std::uncaught_exceptions() > exceptions); }
};

class server_scx_state_sync {
    llama_context * ctx;
public:
    server_scx_state_sync(llama_context * ctx, bool enabled) : ctx(enabled ? ctx : nullptr) {
        if (this->ctx) llama_synchronize(this->ctx);
    }
    server_scx_state_sync(const server_scx_state_sync &) = delete;
    void finish() {
        if (ctx) {
            llama_synchronize(ctx);
            ctx = nullptr;
        }
    }
    ~server_scx_state_sync() { finish(); }
};

inline void server_newa_cpu_phase(uint32_t phase) {
    using phase_fn = void (*)(uint32_t);
    static phase_fn update = [] {
        auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
        if (!dev) return phase_fn(nullptr);
        auto * reg = ggml_backend_dev_backend_reg(dev);
        return (phase_fn) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_newa_phase");
    }();
    if (update) update(phase);
}

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

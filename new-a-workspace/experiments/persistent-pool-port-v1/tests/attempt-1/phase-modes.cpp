#include "server-scx.h"
#include "server-phase.h"
#include "ggml-backend.h"
#include <cstdio>
#include <cstring>
#include <type_traits>
int main() {
    ggml_backend_load_all();
    auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
    GGML_ASSERT(dev);
    auto * reg = ggml_backend_dev_backend_reg(dev);
    auto current = (uint32_t (*)()) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_newa_phase_current");
    GGML_ASSERT(current);
#ifdef LLAMA_SCX_PHASE_HINT
    static_assert(std::is_same<decltype(&llama_scx_phase_v1), void (*)(uint32_t)>::value, "scalar v1 ABI");
    for (uint32_t phase : {0U, 1U, 2U, 3U, 0U}) {
        llama_scx_phase_v1(phase);
        GGML_ASSERT(current() == phase);
    }
#endif
#ifdef LLAMA_SCX_PHASE_TRACE
    static_assert(sizeof(server_scx_event) == 80, "trace v1 layout");
    server_scx_event event{};
    server_scx_scope inactive(nullptr, event);
    inactive.finish(0);
#endif
    std::puts("PASS phase build mode, actual registry binding, scalar v1/trace separation");
}

#include "server-threadpool.h"
#include "server-scx.h"
#include "ggml-alloc.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <memory>
#include <vector>
static int tasks() {
    DIR * d = opendir("/proc/self/task");
    GGML_ASSERT(d);
    int n = 0;
    while (auto * item = readdir(d)) if (item->d_name[0] != '.') ++n;
    closedir(d);
    return n;
}
static bool abort_now(void * data) { return *static_cast<bool *>(data); }
int main() {
    ggml_backend_load_all();
    auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
    GGML_ASSERT(dev);
    auto * reg = ggml_backend_dev_backend_reg(dev);
    auto features = (ggml_backend_get_features_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_get_features");
    GGML_ASSERT(features);
    bool openmp = false;
    for (auto * f = features(reg); f->name; ++f) if (!std::strcmp(f->name, "OPENMP") && !std::strcmp(f->value, "1")) openmp = true;
    GGML_ASSERT(openmp);
    auto set_pool = (decltype(ggml_backend_cpu_set_threadpool) *) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_set_threadpool");
    auto set_threads = (ggml_backend_set_n_threads_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_n_threads");
    auto set_abort = (ggml_backend_set_abort_callback_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_abort_callback");
    auto current = (uint32_t (*)()) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_newa_phase_current");
    GGML_ASSERT(set_pool && set_threads && set_abort && current);
    common_log_main(); // Initialize the logger before counting tasks.
    common_cpu_params cpu;
    cpu.n_threads = 5; cpu.poll = 50;
    auto batch = cpu; batch.n_threads = 6;
    int graphs = 0;
    for (int cycle = 0; cycle < 3; ++cycle) {
        const int before = tasks();
        server_threadpools pools;
        GGML_ASSERT(pools.init(reg, cpu, batch));
        const int after = tasks();
        GGML_ASSERT(after == before);
        std::printf("pool_init_os_tasks before=%d after=%d cycle=%d\n", before, after, cycle);
        auto * backend = ggml_backend_dev_init(dev, nullptr);
        GGML_ASSERT(backend);
        auto * ctx = ggml_init({4 * 1024 * 1024, nullptr, true});
        auto * left = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 256, 64);
        auto * right = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, 256, 7);
        auto * product = ggml_mul_mat(ctx, left, right);
        auto * result = ggml_rms_norm(ctx, product, 1e-5f);
        auto * graph = ggml_new_graph(ctx);
        ggml_build_forward_expand(graph, result);
        auto * buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
        GGML_ASSERT(buffer);
        std::vector<float> a(256 * 64), b(256 * 7, 1.0f), out(64 * 7), raw(64 * 7);
        ggml_backend_tensor_set(right, b.data(), 0, b.size() * sizeof(float));
        bool abort = false;
        set_abort(backend, abort_now, &abort);
        for (int step = 0; step < 24; ++step) {
            const bool use_batch = step % 2;
            const float value = 1.0f + step % 3;
            std::fill(a.begin(), a.end(), value);
            ggml_backend_tensor_set(left, a.data(), 0, a.size() * sizeof(float));
            set_pool(backend, use_batch ? pools.batch : pools.normal);
            set_threads(backend, use_batch ? 6 : 5);
            llama_scx_phase_v1(step % 4);
            GGML_ASSERT(current() == (uint32_t) (step % 4));
            abort = true;
            GGML_ASSERT(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_ABORTED);
            abort = false;
            GGML_ASSERT(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS);
            graphs += 2;
            ggml_backend_tensor_get(product, raw.data(), 0, raw.size() * sizeof(float));
            ggml_backend_tensor_get(result, out.data(), 0, out.size() * sizeof(float));
            for (float v : raw) GGML_ASSERT(v == 256.0f * value);
            for (float v : out) GGML_ASSERT(std::fabs(v - 1.0f) < 1e-5f);
            GGML_ASSERT(current() == (uint32_t) (step % 4));
        }
        ggml_backend_synchronize(backend);
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        ggml_backend_free(backend);
        pools.reset(); pools.reset();
    }
    // The backend owner unwinds before the pool owner on an exception.
    for (int cycle = 0; cycle < 2; ++cycle) {
        try {
            server_threadpools pools;
            GGML_ASSERT(pools.init(reg, cpu, batch));
            std::unique_ptr<ggml_backend, decltype(&ggml_backend_free)> backend(ggml_backend_dev_init(dev, nullptr), ggml_backend_free);
            GGML_ASSERT(backend);
            set_pool(backend.get(), pools.batch);
            throw cycle;
        } catch (int value) { GGML_ASSERT(value == cycle); }
    }
    std::printf("PASS OpenMP=1, MUL_MAT/RMS_NORM reuse, abort recovery, phase/chunk refresh; graph_calls=%d; exception_cycles=2\n", graphs);
}

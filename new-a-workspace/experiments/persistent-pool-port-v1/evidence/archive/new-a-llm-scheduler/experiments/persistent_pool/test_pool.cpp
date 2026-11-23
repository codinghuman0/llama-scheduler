#include "ggml.h"
#include "ggml-alloc.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static std::vector<float> compute(int rows, int tokens, bool ref) {
    const int k = 256;
    ggml_backend_t backend = ggml_backend_cpu_init();
    ggml_backend_cpu_set_n_threads(backend, 6);
    ggml_backend_cpu_set_use_ref(backend, ref);
    ggml_threadpool_t pool = nullptr;
    const char * mode = std::getenv("GGML_NEWA_TEST_POOL");
    if (mode && std::strcmp(mode, "on") == 0) {
        auto params = ggml_threadpool_params_default(6);
        params.poll = 0;
        params.paused = true;
        pool = ggml_threadpool_new(&params);
        assert(pool);
        ggml_backend_cpu_set_threadpool(backend, pool);
    }
    ggml_context * weights = ggml_init({1024*1024, nullptr, true});
    ggml_context * ctx = ggml_init({1024*1024, nullptr, true});
    ggml_tensor * a = ggml_new_tensor_2d(weights, GGML_TYPE_Q4_K, k, rows);
    ggml_tensor * b = ggml_new_tensor_2d(ctx, GGML_TYPE_F32, k, tokens);
    ggml_tensor * c = ggml_mul_mat(ctx, a, b);
    ggml_cgraph * graph = ggml_new_graph(ctx);
    ggml_build_forward_expand(graph, c);
    ggml_backend_buffer_type_t buft = ggml_backend_cpu_buffer_type();
    if (!ref) {
        auto dev = ggml_backend_get_device(backend);
        auto reg = ggml_backend_dev_backend_reg(dev);
        auto extra = (ggml_backend_dev_get_extra_bufts_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_dev_get_extra_bufts");
        assert(extra);
        bool found = false;
        for (auto types = extra(dev); *types; types++) {
            if (std::strcmp(ggml_backend_buft_name(*types), "CPU_REPACK") == 0) {
                buft = *types;
                found = true;
            }
        }
        assert(found);
    }
    auto wb = ggml_backend_alloc_ctx_tensors_from_buft(weights, buft);
    auto buf = ggml_backend_alloc_ctx_tensors(ctx, backend);
    assert(wb && buf);
    ggml_backend_buffer_set_usage(wb, GGML_BACKEND_BUFFER_USAGE_WEIGHTS);
    std::vector<float> floats(k*rows), input(k*tokens), output(rows*tokens);
    for (size_t i=0; i<floats.size(); i++) floats[i] = std::sin(float(i)*0.123f);
    for (size_t i=0; i<input.size(); i++) input[i] = std::cos(float(i)*0.013f);
    std::vector<unsigned char> quant(ggml_nbytes(a));
    assert(ggml_quantize_chunk(GGML_TYPE_Q4_K, floats.data(), quant.data(), 0, rows, k, nullptr) == quant.size());
    ggml_backend_tensor_set(a, quant.data(), 0, quant.size());
    ggml_backend_tensor_set(b, input.data(), 0, input.size()*sizeof(float));
    for (int repeat = 0; repeat < 3; repeat++) {
        input[0] += .1f;
        ggml_backend_tensor_set(b, input.data(), 0, input.size()*sizeof(float));
        assert(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS);
    }
    ggml_backend_tensor_get(c, output.data(), 0, output.size()*sizeof(float));
    ggml_backend_buffer_free(buf);
    ggml_backend_buffer_free(wb);
    ggml_free(ctx);
    ggml_free(weights);
    if (pool) {
        ggml_backend_cpu_set_threadpool(backend, nullptr);
        ggml_threadpool_free(pool);
    }
    ggml_backend_free(backend);
    return output;
}

int main(int argc, char ** argv) {
    assert(argc == 2);
    FILE * file = std::fopen(argv[1], "wb");
    assert(file);
    for (int rows : {256, 1536, 8960}) for (int tokens : {1, 2, 3, 4, 8, 256}) {
        auto actual = compute(rows, tokens, false);
        auto reference = compute(rows, tokens, true);
        double error = 0, norm = 0;
        for (size_t i=0; i<actual.size(); i++) {
            assert(std::isfinite(actual[i]));
            double d = actual[i]-reference[i];
            error += d*d;
            norm += double(reference[i])*reference[i];
        }
        double nmse = error/norm;
        std::printf("rows=%d tokens=%d nmse=%.9g\n", rows, tokens, nmse);
        assert(nmse < 1e-4);
        assert(std::fwrite(actual.data(), sizeof(float), actual.size(), file) == actual.size());
    }
    assert(std::fclose(file) == 0);
    std::puts("PASS: 18 repacked shapes, each graph reused three times, pool cleanup completed");
}

#include "../tools/server/server-threadpool.h"
#include "../ggml/src/ggml-backend-impl.h"
#include "ggml-alloc.h"

#include <cstring>
#include <vector>

static std::vector<ggml_threadpool_params> created;
static int fail_at = 0;
static int freed = 0;
static const char * missing = "";

static ggml_threadpool_t mock_new(ggml_threadpool_params * params) {
    created.push_back(*params);
    if ((int) created.size() == fail_at) {
        return nullptr;
    }
    return reinterpret_cast<ggml_threadpool_t>(new int(0));
}

static void mock_free(ggml_threadpool_t pool) {
    GGML_ASSERT(pool);
    ++freed;
    delete reinterpret_cast<int *>(pool);
}

static void mock_set(ggml_backend_t, ggml_threadpool_t) {}

static void * mock_proc(ggml_backend_reg_t, const char * name) {
    if (std::strcmp(name, missing) == 0) {
        return nullptr;
    }
    if (std::strcmp(name, "ggml_threadpool_new") == 0) {
        return reinterpret_cast<void *>(mock_new);
    }
    if (std::strcmp(name, "ggml_threadpool_free") == 0) {
        return reinterpret_cast<void *>(mock_free);
    }
    if (std::strcmp(name, "ggml_backend_cpu_set_threadpool") == 0) {
        return reinterpret_cast<void *>(mock_set);
    }
    return nullptr;
}

static ggml_backend_reg mock_reg = {GGML_BACKEND_API_VERSION, {nullptr, nullptr, nullptr, mock_proc}, nullptr};

static void reset_mock() {
    created.clear();
    fail_at = 0;
    freed = 0;
    missing = "";
}

static void test_parameters_and_failures() {
    common_cpu_params cpu;
    cpu.n_threads = 2;
    cpu.mask_valid = true;
    cpu.cpumask[2] = true;
    cpu.cpumask[4] = true;
    cpu.strict_cpu = true;
    cpu.poll = 0;
    cpu.priority = GGML_SCHED_PRIO_MEDIUM;

    for (int difference = 0; difference < 6; ++difference) {
        reset_mock();
        auto batch = cpu;
        switch (difference) {
            case 1: batch.n_threads = 3; break;
            case 2: batch.cpumask[6] = true; break;
            case 3: batch.strict_cpu = false; break;
            case 4: batch.poll = 1; break;
            case 5: batch.priority = GGML_SCHED_PRIO_NORMAL; break;
        }
        {
            server_threadpools pools;
            GGML_ASSERT(pools.init(&mock_reg, cpu, batch));
            GGML_ASSERT(created.size() == (difference ? 2 : 1));
            GGML_ASSERT((pools.batch != nullptr) == (difference != 0));
            auto expected = ggml_threadpool_params_from_cpu_params(cpu);
            GGML_ASSERT(ggml_threadpool_params_match(&created.back(), &expected));
            expected = ggml_threadpool_params_from_cpu_params(batch);
            GGML_ASSERT(ggml_threadpool_params_match(&created.front(), &expected));
            for (const auto & params : created) {
                GGML_ASSERT(params.paused);
            }
            pools.reset();
            pools.reset();
        }
        GGML_ASSERT(freed == (difference ? 2 : 1));
    }

    for (const char * capability : {"ggml_threadpool_new", "ggml_threadpool_free", "ggml_backend_cpu_set_threadpool"}) {
        reset_mock();
        missing = capability;
        server_threadpools pools;
        GGML_ASSERT(!pools.init(&mock_reg, cpu, cpu));
        GGML_ASSERT(created.empty() && freed == 0);
    }
    reset_mock();
    {
        server_threadpools pools;
        GGML_ASSERT(!pools.init(nullptr, cpu, cpu));
    }
    for (bool separate : {false, true}) {
        for (int failure = 1; failure <= (separate ? 2 : 1); ++failure) {
            reset_mock();
            fail_at = failure;
            auto batch = cpu;
            batch.n_threads += separate;
            server_threadpools pools;
            GGML_ASSERT(!pools.init(&mock_reg, cpu, batch));
            GGML_ASSERT(!pools.normal && !pools.batch);
            GGML_ASSERT(freed == failure - 1);
            fail_at = 0;
            GGML_ASSERT(pools.init(&mock_reg, cpu, batch));
        }
    }
}

static bool abort_graph(void * data) {
    return *static_cast<bool *>(data);
}

static void test_graph_reuse(ggml_backend_dev_t dev, bool separate) {
    auto * reg = ggml_backend_dev_backend_reg(dev);
    auto * set_pool = (decltype(ggml_backend_cpu_set_threadpool) *) ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_set_threadpool");
    auto * set_threads = (ggml_backend_set_n_threads_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_n_threads");
    auto * set_abort = (ggml_backend_set_abort_callback_t) ggml_backend_reg_get_proc_address(reg, "ggml_backend_set_abort_callback");
    GGML_ASSERT(set_pool && set_threads && set_abort);

    common_cpu_params cpu;
    cpu.n_threads = 2;
    cpu.poll = 0;
    auto batch = cpu;
    batch.n_threads = separate ? 3 : 2;

    // Repeat the ownership cycle used when the server unloads and reloads a model.
    for (int cycle = 0; cycle < 4; ++cycle) {
        server_threadpools pools;
        GGML_ASSERT(pools.init(reg, cpu, batch));
        auto * backend = ggml_backend_dev_init(dev, nullptr);
        GGML_ASSERT(backend);

        auto * ctx = ggml_init({1024 * 1024, nullptr, true});
        auto * input = ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 4096);
        auto * doubled = ggml_scale(ctx, input, 2.0f);
        auto * output = ggml_add(ctx, doubled, doubled);
        auto * graph = ggml_new_graph(ctx);
        ggml_build_forward_expand(graph, output);
        auto * buffer = ggml_backend_alloc_ctx_tensors(ctx, backend);
        GGML_ASSERT(buffer);
        std::vector<float> values(4096, 1.0f);
        ggml_backend_tensor_set(input, values.data(), 0, values.size() * sizeof(float));

        bool abort = true;
        set_abort(backend, abort_graph, &abort);
        for (int step = 0; step < 12; ++step) {
            const bool use_batch = step % 2;
            set_pool(backend, use_batch && pools.batch ? pools.batch : pools.normal);
            set_threads(backend, use_batch ? batch.n_threads : cpu.n_threads);
            abort = true;
            GGML_ASSERT(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_ABORTED);
            abort = false;
            GGML_ASSERT(ggml_backend_graph_compute(backend, graph) == GGML_STATUS_SUCCESS);
            ggml_backend_tensor_get(output, values.data(), 0, values.size() * sizeof(float));
            for (float value : values) {
                GGML_ASSERT(value == 4.0f);
            }
        }
        ggml_backend_synchronize(backend);
        ggml_backend_buffer_free(buffer);
        ggml_free(ctx);
        ggml_backend_free(backend);
        pools.reset();
    }
}

int main() {
    test_parameters_and_failures();
    ggml_backend_load_all();
    auto * dev = ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU);
    GGML_ASSERT(dev);
    test_graph_reuse(dev, false);
    test_graph_reuse(dev, true);
}

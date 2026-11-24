#pragma once

#include <algorithm>

#include "common.h"
#include "ggml-backend.h"
#include "ggml-cpu.h"
#include "log.h"

struct server_threadpools {
    ggml_threadpool_t normal = nullptr;
    ggml_threadpool_t batch  = nullptr;

    server_threadpools() = default;
    server_threadpools(const server_threadpools &) = delete;
    server_threadpools & operator=(const server_threadpools &) = delete;

    ~server_threadpools() {
        reset();
    }

    // Destroy all contexts and backends that use these pools before reset().
    void reset() {
        if (normal) {
            free_fn(normal);
        }
        if (batch) {
            free_fn(batch);
        }
        normal = nullptr;
        batch = nullptr;
        free_fn = nullptr;
    }

    bool init(ggml_backend_reg_t reg, const common_cpu_params & cpu, const common_cpu_params & cpu_batch, bool force_shared = false) {
        GGML_ASSERT(!normal && !batch);

        auto * new_fn = reg ? (decltype(ggml_threadpool_new) *) ggml_backend_reg_get_proc_address(reg, "ggml_threadpool_new") : nullptr;
        free_fn = reg ? (decltype(ggml_threadpool_free) *) ggml_backend_reg_get_proc_address(reg, "ggml_threadpool_free") : nullptr;
        auto * set_fn = reg ? ggml_backend_reg_get_proc_address(reg, "ggml_backend_cpu_set_threadpool") : nullptr;
        if (!new_fn || !free_fn || !set_fn) {
            LOG_ERR("%s: CPU backend lacks threadpool create/free/attach support\n", __func__);
            reset();
            return false;
        }

        auto tpp       = ggml_threadpool_params_from_cpu_params(cpu);
        auto tpp_batch = ggml_threadpool_params_from_cpu_params(cpu_batch);
        if (force_shared) {
            const int capacity = std::max(tpp.n_threads, tpp_batch.n_threads);
            tpp.n_threads = tpp_batch.n_threads = capacity;
            if (!ggml_threadpool_params_match(&tpp, &tpp_batch)) {
                LOG_ERR("%s: a shared threadpool requires identical masks, poll, priority and strict placement\n", __func__);
                reset();
                return false;
            }
        }
        const bool shared = ggml_threadpool_params_match(&tpp, &tpp_batch);

        tpp.paused = true;
        tpp_batch.paused = true;
        if (!shared) {
            batch = new_fn(&tpp_batch);
            if (!batch) {
                LOG_ERR("%s: batch threadpool create failed, n_threads = %d\n", __func__, tpp_batch.n_threads);
                reset();
                return false;
            }
        }

        normal = new_fn(&tpp);
        if (!normal) {
            LOG_ERR("%s: generation threadpool create failed, n_threads = %d\n", __func__, tpp.n_threads);
            reset();
            return false;
        }

        LOG_INF("%s: persistent CPU threadpools, shared = %s, generation = %d, batch = %d\n",
                __func__, shared ? "yes" : "no", tpp.n_threads, tpp_batch.n_threads);
        return true;
    }

private:
    decltype(ggml_threadpool_free) * free_fn = nullptr;
};

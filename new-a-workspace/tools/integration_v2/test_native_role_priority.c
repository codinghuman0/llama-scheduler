#define _GNU_SOURCE
#include <assert.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>

#include "ggml-cpu.h"

struct graph_probe {
    int expected_policy;
    bool abort;
    int callbacks;
};

static bool observe_graph(void * data) {
    struct graph_probe * probe = data;
    assert(sched_getscheduler(0) == probe->expected_policy);
    probe->callbacks++;
    return probe->abort;
}

static void run_graph(struct ggml_cgraph * graph, struct ggml_threadpool * pool, int policy, bool abort) {
    struct ggml_cplan plan = ggml_graph_plan(graph, 2, pool);
    struct graph_probe probe = { .expected_policy = policy, .abort = abort };
    plan.work_data = plan.work_size ? malloc(plan.work_size) : NULL;
    assert(!plan.work_size || plan.work_data);
    plan.abort_callback = observe_graph;
    plan.abort_callback_data = &probe;

    const enum ggml_status status = ggml_graph_compute(graph, &plan);
    assert(status == (abort ? GGML_STATUS_ABORTED : GGML_STATUS_SUCCESS));
    assert(probe.callbacks > 0);
    assert(sched_getscheduler(0) == SCHED_OTHER);
    free(plan.work_data);
}

int main(void) {
    assert(sched_getscheduler(0) == SCHED_OTHER);
    struct ggml_threadpool_params params = ggml_threadpool_params_default(2);
    params.paused = true;
    params.poll = 0;
    struct ggml_threadpool * generation = ggml_threadpool_new(&params);
    params.prio = GGML_SCHED_PRIO_LOW;
    struct ggml_threadpool * batch = ggml_threadpool_new(&params);
    assert(generation && batch);
    assert(sched_getscheduler(0) == SCHED_OTHER);

    const struct ggml_init_params init = { .mem_size = 2 * 1024 * 1024 };
    struct ggml_context * ctx = ggml_init(init);
    assert(ctx);
    struct ggml_tensor * left = ggml_set_f32(ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 256), 2.f);
    struct ggml_tensor * right = ggml_set_f32(ggml_new_tensor_1d(ctx, GGML_TYPE_F32, 256), 3.f);
    struct ggml_tensor * sum = ggml_add(ctx, left, right);
    struct ggml_cgraph * graph = ggml_new_graph(ctx);
    ggml_build_forward_expand(graph, sum);

    run_graph(graph, generation, SCHED_OTHER, false);
    ggml_threadpool_pause(generation);
    run_graph(graph, batch, SCHED_BATCH, false);
    run_graph(graph, batch, SCHED_BATCH, true);
    run_graph(graph, batch, SCHED_BATCH, false);
    ggml_threadpool_pause(batch);
    run_graph(graph, generation, SCHED_OTHER, false);
    assert(ggml_get_f32_1d(sum, 0) == 5.f);

    ggml_threadpool_free(batch);
    ggml_threadpool_free(generation);
    ggml_free(ctx);
    puts("BATCH caller scoped to active graphs, restored after successful and aborted graphs, generation recovery PASS");
    return 0;
}

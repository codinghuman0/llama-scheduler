# Persistent CPU pool validation

The server owns pools for ordinary CPU-only decoder text generation. Explicit `-ngl 0`, or a runtime without GPU offload support, selects this path. Tensor buffer overrides, encoder models, embeddings, multimodal input, and all speculative modes retain their existing behavior. Common initialization and its warmup run before attachment, so disposable pools in startup logs are expected.

Pool parameters come from `ggml_threadpool_params_from_cpu_params()`. Matching thread count, mask, strict placement, polling, and priority share one pool. Otherwise the server creates a batch pool and a generation pool. Both start paused, so native workers do not poll before first use or alter the loading thread's placement. Backend switching pauses the previous pool; native graph kickoff resumes the selected pool and applies the calling worker's placement. An active pool can still poll between graphs according to its configured polling level.

On teardown the server synchronizes, detaches, destroys the context and its backends, then frees the pools. Detach alone does not clear the CPU backend's last pool pointer. Failed initialization uses the same cleanup path, including a failed resume. Actual model sleep unloads the contexts and pools; resume creates new ones. Worker identity is expected to persist between graphs within one awake interval, not across model unload/reload.

Native pools own persistent worker threads. OpenMP pools retain ggml worker state, masks, and priority settings, but OpenMP manages OS workers and can reuse teams already. Do not infer OpenMP thread creation from disposable ggml pool allocation. Native polling/pause behavior is not an OpenMP runtime wait policy. Record `OMP_`, `GOMP_`, and `KMP_` settings separately. Affinity and priority application remain subject to the CPU backend and OS permissions; check the actual worker masks and log warnings. In particular, the existing OpenMP single-thread execution branch does not apply the pool's mask/priority.

## Model-free checks

Build and run these on both native and OpenMP CPU builds:

```sh
cmake --build build-native --target llama-server test-server-threadpool test-compute-profile test-backend-ops -j 3
ctest --test-dir build-native -R '^(test-server-threadpool|test-compute-profile)$' --output-on-failure
build-native/bin/test-backend-ops test -b CPU -o MUL_MAT,RMS_NORM -p 'm=16,n=(1|4),k=256|ne=\[64,5,4,3\]'
python3 -m unittest discover -s tools/server/bench/cpu -p 'test_*.py' -v
```

`test-server-threadpool` checks all parameter differences, forwarding, initially paused pools, missing registry capabilities, failure of either creation, cleanup/retry, shared/separate graph execution, backend switching, aborted graph recovery, and repeated ownership cycles without a model. The CPU allocator currently aborts on some allocation/thread creation failures; injected null returns test the server's recoverable failure handling, not recovery from a backend process abort. Model lifecycle tests below remain required on the benchmark host.

## Reproduce before/after on the benchmark host

Run model commands only on the separate benchmark host. Use the same local decoder GGUF, topology, power state, runtime environment, and available CPUs for both sources. Stop other model servers. Build the baseline from the pre-change HEAD and the candidate from the reviewed working tree; no commit is needed. Set the following paths first:

```sh
export POOL_REPO=/home/hs/llama.cpp-fork
export POOL_BASE=/home/hs/llama-before-pools
export POOL_RESULTS=/home/hs/pool-results
export POOL_MODEL=/absolute/path/to/local-decoder-Q4_K_M.gguf
mkdir -p "$POOL_RESULTS"
git -C "$POOL_REPO" worktree add --detach "$POOL_BASE" "$(git -C "$POOL_REPO" rev-parse HEAD)"

for source in "$POOL_BASE" "$POOL_REPO"; do
    for runtime in native openmp; do
        omp=OFF
        if [ "$runtime" = openmp ]; then omp=ON; fi
        cmake -S "$source" -B "$source/build-pools-$runtime" \
            -DCMAKE_BUILD_TYPE=Release -DGGML_OPENMP="$omp" \
            -DLLAMA_BUILD_COMMON=ON -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TESTS=ON \
            -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
            -DLLAMA_SCX_PHASE_TRACE=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DGGML_BLAS=OFF
        cmake --build "$source/build-pools-$runtime" --target llama-server -j 3
    done
done
```

Generate four configs using the candidate harness. These thread counts are diagnostic examples for the 5600G, not a tuning conclusion. All roles use the old disposable pool defaults (poll=50, normal priority, unrestricted placement), keeping the allocation/lifetime change independently measurable. Do not add affinity or change polling in this first comparison: the old server did not pass those settings to its disposable pools. Set both pool roles explicitly in a separate placement experiment.

```sh
python3 - <<'PY'
import json, os
from pathlib import Path
out = Path(os.environ['POOL_RESULTS'])
for label, source in [('before', os.environ['POOL_BASE']), ('after', os.environ['POOL_REPO'])]:
    for runtime in ('native', 'openmp'):
        build = Path(source) / ('build-pools-' + runtime)
        cfg = dict(server=str(build / 'bin/llama-server'), build_cache=str(build / 'CMakeCache.txt'),
                   model=os.environ['POOL_MODEL'], model_description='Local decoder GGUF; hashes recorded in manifest',
                   conditions=[dict(threads=6, batch_threads=6, profile='auto'),
                               dict(threads=2, batch_threads=6, profile='auto')],
                   workloads=['pp', 'd1', 'd2', 'd4', 'm1', 'm3'], repetitions=5, warmups=1,
                   seed=20260905, output_tokens=256, server_env={'OMP_DYNAMIC': 'FALSE'})
        (out / f'{label}-{runtime}.json').write_text(json.dumps(cfg, indent=2) + '\n')
PY

for runtime in native openmp; do
    for label in before after; do
        python3 "$POOL_REPO/tools/server/bench/cpu/runner.py" --config "$POOL_RESULTS/$label-$runtime.json" --plan
        python3 "$POOL_REPO/tools/server/bench/cpu/runner.py" --config "$POOL_RESULTS/$label-$runtime.json" \
            --run --output "$POOL_RESULTS/timing-$label-$runtime-001"
    done
done
```

Output paths must be new. Repeat with reversed before/after order and fresh output names to check host drift. Compare corresponding conditions, workloads, repetitions, output counts/IDs, worst-decode p95 and stalls, long-request TTFT, throughput, and CPU/output. Keep failures and interval coverage visible. Do not report a winning thread count from this two-condition check. Native and OpenMP are separate comparisons. Verbose logs, process sampling, and tracing must stay off in these timing runs.

## Lifecycle, pool diagnostics, TIDs, and affinity

`check_threadpools.py` starts only the configured local server, records the ordinary manifest, and runs repeated prefill/decode requests, stream cancellation followed by another request, and at least two sleep/resume cycles. Its steady-state log sections exclude load and startup warmup. It requires all graph diagnostics in each section to match `--expect-disposable`. It saves `report.json`, raw SSE, server logs, and `tasks.jsonl` with per-thread TID, start time, CPU ticks, observed processor, and actual allowed CPUs. These runs include observer overhead and are not performance evidence.

Run the baseline with `--expect-disposable yes` as a diagnostic control. Run both shared and separate candidate conditions, and both shutdown states, for each runtime:

```sh
for runtime in native openmp; do
    python3 "$POOL_REPO/tools/server/bench/cpu/check_threadpools.py" \
        --config "$POOL_RESULTS/before-$runtime.json" --condition 1 --cycles 3 \
        --expect-disposable yes --run --output "$POOL_RESULTS/control-$runtime-001"
    for condition in 0 1; do
        for state in awake asleep; do
            python3 "$POOL_REPO/tools/server/bench/cpu/check_threadpools.py" \
                --config "$POOL_RESULTS/after-$runtime.json" --condition "$condition" --cycles 3 \
                --expect-disposable no --shutdown-state "$state" --run \
                --output "$POOL_RESULTS/lifecycle-$runtime-$condition-$state-001"
        done
    done
done
```

For actual placement, copy the candidate config to a new file and set `cpu_mask` and `cpu_mask_batch` to hex strings selecting permitted host CPUs, and both `cpu_strict` fields to 1. Retain enough CPUs for the larger team. Run the diagnostic again for both conditions. Select CPUs after checking `os.sched_getaffinity(0)`, `lscpu -e`, and cgroup cpusets; do not assume logical CPU numbers map to physical cores. Exercise non-strict placement in a second config if needed. Normal priority needs no privileges; do not elevate privileges to make a priority test pass.

Acceptance requires manual inspection of task evidence as well as a successful report. In each awake interval, identify native compute workers from CPU-tick growth during the repeated `pp`/`d1` phases and their disappearance at model sleep. Verify the same `(tid, start_ticks)` identities do work on repeated requests for each pool, and their actual masks match the intended role (singleton masks under strict placement). The inference calling thread also computes and changes role affinity; HTTP workers are not pool workers. With equal roles expect one native worker set, otherwise two sets. Sleep can produce new TIDs on reload. In OpenMP, record observed reuse/masks without attributing OS worker ownership to ggml pools. Too-short runs or coarse CPU ticks can leave worker attribution inconclusive; increase request length and retain that limitation rather than declaring reuse proven from a stable process thread count.

Require `status=ok`, steady-state `disposable_threadpool=no` for the candidate, successful post-cancel requests, the requested shutdown state, exit code 0 on SIGTERM, no forced leader kill, and no remaining live process-group members. Do not treat the model-free pool test as proof of these model lifecycle results.

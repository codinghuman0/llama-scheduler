# CPU serving benchmark

This standard-library Python harness evaluates existing CPU thread and compute-profile settings for decoder-only text completion. It changes no inference or scheduling code. It reuses the archived experiment's `/tokenize`, numeric prompts, `/completion`, and `/proc/PID/stat` approach, plus the server tests' health check and terminate/kill lifecycle patterns. The archive remains unchanged. The existing pytest utility also downloads models and prints stream events, so it is not imported into timed trials.

Model runs belong on the separate Ryzen 5 5600G/48 GB host. No model performance results or winning settings are supplied here. Example thread counts, polling options, and profile modes are inputs to test, not recommendations. Verify the host's available CPUs, memory, affinity, quota, and power state before choosing conditions. `auto` may use batch threads during concurrent decode, so compare both thread counts.

## Model-free validation on the development machine

Python 3.10+ on Linux is required. No third-party packages, model downloads, or llama.cpp build are required for these commands:

```sh
python3 -m unittest discover -s tools/server/bench/cpu -p 'test_*.py' -v
python3 tools/server/bench/cpu/overhead.py --output benchmark-results/cpu-client-check --events 1000 --max-p95-lag-ms 50
python3 tools/server/bench/cpu/runner.py --config tools/server/bench/cpu/example-pilot.json --plan
```

The overhead check launches a separate Python fixture, never llama-server. It checks event/token counts, cleanup, and a declared receive-lag budget across 1/4 streams, burst/1 ms paced events, and singleton/four-token events. Artifacts include raw SSE, individual request records, producer CPU, client CPU, events/s, CPU seconds/event, and send-to-receive p50/p95/max lag. Producer and client use the same host monotonic clock. Lag includes producer serialization, network buffering, scheduling, and client processing; it does not isolate Python parsing cost. The default 50 ms budget is a fixture check, not a model latency acceptance threshold. A failed case produces a nonzero exit status.

Repeat the check on the benchmark host, under representative rates and concurrent load, before trusting model timings. High burst CPU usage alone does not establish interference at serving rates. Compare client CPU, receive lag, and event rate with the intended workload. The check does not prove zero observer overhead.

## Prepare and run on the benchmark host

Use an existing CPU-only build and local decoder-only GGUF model. Build options are documented in [the archived reproduction guide](../../../../results/compute-profile-20260905T044005Z/REPRODUCE.md) and [build documentation](../../../../docs/build.md). Use separate build directories for OpenMP/native comparisons. Keep diagnostic compute-profile tracing, verbose logging, and SCX markers off. This runner never invokes sudo, loads a scheduler, changes affinity or system settings, commits, pushes, or downloads models.

Copy an example configuration and replace the paths and model description. Relative paths resolve against the configuration's directory. All GGUF shards are hashed automatically when the standard `-00001-of-000NN.gguf` filename is used. `model_description` is an operator-supplied label, not independently verified metadata; the file hashes establish identity. Set `build_cache` to the actual server build's `CMakeCache.txt`. The cache and loaded library hashes are recorded; the runner cannot prove that a cache produced a particular executable.

```sh
# These --run commands are for the separate benchmark host only.
python3 tools/server/bench/cpu/runner.py --config /path/to/pilot.json --plan
python3 tools/server/bench/cpu/runner.py --config /path/to/pilot.json --run --output benchmark-results/cpu-pilot-001
```

`example-pilot.json` compares equal-thread auto/phase profiles. `example-threadpool.json` illustrates thread and polling controls. Conditions also accept `cpu_mask`/`cpu_mask_batch` (hex strings), `cpu_strict`/`cpu_strict_batch` (0 or 1), and `priority`/`priority_batch` (the CLI's numeric priority values). Set both roles explicitly when testing placement; the common argument parser only copies all generation parameters into batch parameters when the batch thread count is unset. Polling can behave differently with OpenMP/native builds; configure and compare each build separately. Only the documented JSON keys and ordinary CPU runtime environment overrides (`OMP_`, `GOMP_`, `KMP_`, `OPENBLAS_`) are accepted. Inherited `LLAMA_ARG_*` variables are removed from the child environment so they cannot silently enable tracing, speculative decoding, GPU settings, or another model. Other relevant runtime variables, including library paths, are recorded.

For persistent pool before/after commands, lifecycle diagnostics, and TID/affinity acceptance criteria, see [threadpool validation](threadpools.md).

Each repetition contains all condition/workload pairs shuffled by the configured seed. The complete order is saved before startup. Each trial starts a fresh server, performs the configured positive number of warmups of that workload, measures it once, and stops/reaps the server before the next trial. Model loading, hashing, tokenizer setup, library inspection, and warmup are outside the measured window. Restarting each trial costs time but avoids multiple resident model servers and condition carryover. Built-in server startup warmup may also occur before readiness.

A per-user host lock prevents concurrent campaigns by this runner. Before each launch it refuses an observable existing `llama-server` or process using the configured executable. Run on an otherwise idle, dedicated host; this check cannot detect inaccessible processes or prevent unrelated programs from starting later. The runner only terminates its own process group. A cleanup failure stops the campaign. SIGINT/SIGTERM records cancellation and stops active streams/server; SIGKILL or host failure cannot execute cleanup. Incremental files retain the last recorded stage in that case. Output directories must be new; there is no implicit resume or overwrite.

## Workloads and overlap

| Name | Requests |
| --- | --- |
| `pp` | Prompt-only graph work, ending after the first sampled output token (`n_predict=1`). No autoregressive decode step. |
| `d1`, `d2`, `d4` | 1/2/4 short-prompt streams released together by a client barrier. |
| `m1`, `m3` | 1/3 ongoing short decoders; inject one long prompt after each has delivered `inject_after_tokens`. |

The current server samples its first token from prompt logits. The `pp` workload includes that sample and its HTTP delivery, records its real output count of one, and is not a claim of zero sampling overhead. The server documentation mentions `n_predict=0`, but the current decoder loop proceeds through sampling; this harness avoids relying on that behavior. Choose prompt sizes appropriate to the experiment. Prompt caching is disabled. Numeric prompts retain the tokenizer's special prefix and repeat tokenized probe text; actual arrays are saved. Context per slot must accommodate the longest request. Unsupported model paths (encoder, speculative, multimodal) are outside this tool's scope.

Mixed trials enable existing prompt-progress SSE and poll `/slots` every 20 ms, with a bounded HTTP deadline. Validity requires every background decoder to deliver a token before long-request admission and another between admission and the long request's first output. Each must also appear in a server snapshot as active with `n_decoded > 0` while the long slot is active with a positive processed-prompt count below its requested length. The long slot's decoded count can retain the previous request's value during prefill, so it is not used to identify prefill. IDs are assigned explicitly through `id_slot`; all snapshots and progress events are retained. This is conservative server/request overlap evidence, not proof that tokens shared one graph. Missing evidence, including a too-short prefill to observe, produces `invalid_overlap`; increase workload duration in a separate trial rather than silently accepting it. Failure to reach the injection trigger records the long request as `not_started` and fails the trial.

Monitoring is part of mixed-trial CPU/timing cost and should be identical across compared conditions. The harness measures long-request TTFT so bounded-prefill waiting can be assessed, but does not implement admission policy or establish a universal waiting bound.

## Artifacts and metric definitions

`manifest.json` records commit, branch, dirty status/diff, server/model/shard hashes, build cache, host topology, OS/kernel, power state, affinity, cgroup quota/cpuset ancestors, memory and runtime environment. Per-trial files add loaded library hashes, server process status/affinity/quota, `/props`, commands, server logs, tokenizer probes and exact prompts. Unavailable optional host fields are explicit. `order.json`, incremental `trials.json`, and `summary.json` include all planned trials; failed/cancelled/timeout/invalid and unstarted trials remain visible. Warmup failures prevent measurement and retain their status and raw evidence. No success-only performance averages are produced.

`server-environment.json` records `libraries_complete` and lists mapped shared libraries whose hashes are unavailable in `incomplete_libraries`. A missing hash for a mapped `libllama*`, `libggml*`, `libgomp*`, `libomp*`, or `libiomp5*` library fails the trial before warmup. Other missing library hashes are recorded and the trial can proceed.

Each warmup and measurement directory contains `result.json` with request roles, payloads, output IDs/counts, raw events, monotonic start/header/event/end timestamps, failures and CPU/elapsed measurements. `*.sse.jsonl` journals base64-encoded original SSE frames (including comments), receive timestamps captured before parsing/writing, and incomplete trailing frames. The clock marks complete frames read by the client, not physical packet arrival. Output is buffered; final flush is included in the measured window. HTTP errors retain status/body excerpts; stream records survive parse/count failures. Progress placeholders and terminal summary token arrays do not count as delivered output tokens.

| Metric | Definition |
| --- | --- |
| TTFT | First token-bearing, non-progress, nonterminal frame receive time minus request start. Null when no output was delivered. |
| Completion | Request end minus request start, including terminal processing and journal flush. |
| Valid token intervals | Receive deltas between adjacent token-bearing events only when both contain exactly one ID. Never divide a grouped-event gap or repeat its timestamp to synthesize tokens. |
| p95 | Nearest-rank `ceil(0.95 * N)` of valid intervals for each request. Null for no intervals. Coverage and grouped-event counts accompany it. |
| Worst-request p95 | Maximum of the individual p95 values, never pooled intervals. Null if any request lacks intervals. A separate worst-decode p95 excludes the long request. |
| Maximum stall | Largest observed gap between token-bearing frames across requests. This is a delivery gap with grouped events, not an inferred individual-token maximum. Terminal silence is recorded separately. |
| Aggregate throughput | Sum of terminal output counts divided by the measured workload window, including all request prefill and completion time. |
| Server CPU/output | `/proc/PID/stat` user+system CPU delta, summed over process threads, divided by total output count. Tick granularity applies. The CPU boundary brackets the same workload window; startup/warmup are excluded. |
| Client CPU | `process_time()` delta over the workload, including collector threads, parsing, buffering, polling and cleanup of request threads; excludes server CPU and later result serialization. Also reported per output token. |

Success requires terminal completion, exactly matching streamed/terminal/requested token counts, no truncation and a length stop. A server death that prevents CPU accounting fails the trial. Partial samples retain diagnostic metrics and failure details but have null aggregate throughput and CPU/output rates. Request deadlines cover the whole stream, including slow trickles; the trial deadline is shared across all requests, including delayed injection. Readiness and process cleanup have separate deadlines. Prompt-only interval metrics are null because only one output token is requested. Review coverage, failures, long-request TTFT, worst-decode p95 and maximum stalls together before interpreting a CPU reduction as an improvement.

# Lightweight base measurement protocol

Status: the A/B/C/D workload, revisions, lifecycle, statistics and decision gates remain frozen. Host identity and CPU allocation are generated for each supported Linux x86_64 machine before a campaign. This portability amendment introduces no scheduling policy or measured performance result.

## Purpose and revision identities

Measure whether the lightweight infrastructure is cheap enough to support later optimization. Keep the neutral scheduler unchanged and keep phase out of scheduling decisions.

| Config | Exact source revision | Phase hint | Scheduler | Meaning |
| --- | --- | --- | --- | --- |
| A | `original-performance-baseline-v1`, `7a2db1a0cf38e5f4eb278a58c3903d295258d0ea` | Option absent | Default Linux, raw policy 0 | Original implementation |
| B | `llama-side-lightweight-v1`, `c8b9d61d12b4997d902a03e5dc55a185d18c3bc9` | OFF | Default Linux, raw policy 0 | Frozen fork without hints |
| C | Same llama-side revision as B | ON | Default Linux, raw policy 0 | Frozen fork with hints |
| D | Exactly C's executable and complete shared-library set; scheduler `neutral-sched-ext-base-v1`, `ea4a36bbad1100d7d3f7c6aa57caadcb782a26fa` | ON | Selected server/TIDs raw policy 7 | Neutral sched_ext base |

`one-repo-golden-validation-v1` remains `542850645a54fc2e35a9a8189ff8dfcf35b9c51d`; its instrumentation is excluded. The neutral tag still names its implementation commit even after this documentation commit.

Interpret A -> B as the fork/base implementation delta, B -> C as the phase-hint transport delta, and C -> D as the **neutral sched_ext-base delta**. C -> D is not pure sched_ext framework overhead: D also changes scheduling semantics to the validated Linux v6.17 scx_simple weighted-vtime baseline with partial switching, selected-child control plane and PID-scoped marker attachment. No phase, load, topology or worker policy is enabled.

## Host profile, model and implementation identity

Run `bench/clean_room_setup.sh` after cloning `lightweight-base`. It discovers repository/model paths, installs Ubuntu dependencies, validates sched_ext/BTF/kernel configuration, detects topology, builds Base/neutral scheduler and runs correctness smoke. Unsupported kernel capability is BLOCKED. No A/B/C/D campaign runs in setup. The default model is sibling `../model.gguf`; `MODEL=/path/model.gguf` is supported during setup/profile generation. Its exact size is **1117321312 bytes** and SHA256 is **`f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840`**. Never silently use another model.

Generated, ignored `benchmark-results/host-profile.json` records schema/time, repository root, non-root invoking repository owner UID/username/HOME, model path/identity, kernel/boot/architecture/BTF identity, detector topology, CPU allocation, optional frequency/turbo/temperature/power capabilities and scheduler hashes. Generate after a fresh neutral build using `python3 -B tools/sched_ext/bench/host_profile.py`; `--model` also accepts an explicit path. Use `--check` for read-only validation and `--refresh` only before a new campaign. Refresh is refused while an active pointer names PREPARING/PREPARED/ARMED/RUNNING/CAMPAIGN_COMPLETE state. Each run copies the profile bytes and stores their SHA256 in its manifest; every subsequent phase verifies those bytes and artifact hashes. Do not edit a profile or manifest to bypass a mismatch.

The authoritative `detect_host_topology.sh` resolves online/allowed/usable CPUs, physical-core representatives, SMT present/effective, packages/dies/NUMA and heterogeneous observations. One logical CPU per usable physical core is selected. Reserve the last deterministic representative as housekeeping; use all remaining representatives for server compute/batch threads. HTTP threads remain two. At least two usable physical cores are required for the isolated benchmark; setup/smoke can run separately on one core. No core class is silently discarded, and no SMT numbering convention is assumed.

All server-created TIDs stay confined to the server set. The runner/client, privileged helper/loader and post-registration idle launcher use the single housekeeping representative. D's launcher initially uses the server affinity so its child inherits it, then only the launcher moves after successful registration. Each Python phase loads the profile before setting its own affinity; shell wrappers contain no CPU constants or background affinity manager. Checkpoint topology detection uses the profile's original allowed mask in its short-lived detector child, outside timed requests.

The scheduler is freshly built on each host from unchanged neutral source. Freeze SHA256 for `tools/sched_ext/build/llama_scx.bpf.o`, `bin/llama_scx` and `bin/llama_scx_child`; verify the loader's embedded absolute BPF-object path is the active repository build. There are no source-coded binary hashes. Keep kernel/boot/BTF, topology, model, runtime dependencies and all artifacts fixed throughout a campaign.

The repository guard accepts current `lightweight-base` descendants of accepted Base `340468bd398624027624060198393d90aed42873`, with a clean worktree, exact immutable tag targets, frozen llama/scheduler source identity and an explicit docs/setup/benchmark portability file allowlist. It excludes `analysis.py` and all implementation/build files from that allowlist. No historical automation checkout is required.

## Build protocol

Build A, B and C once before measurement. D reuses **the exact C bytes**, including `llama-server`, `libllama-server-impl.so`, `libllama.so`, `libggml*.so` and other resolved runtime libraries; there is no fourth llama build. Use clean source/build trees at the exact revisions. Do not rebuild the validated development tree.

Use `/usr/bin/cc` and `/usr/bin/c++` with a supported GNU toolchain, CMake and GNU Make, using generator **Unix Makefiles**. Freeze Release optimization (`-O3 -DNDEBUG`), shared libraries, native architecture (`GGML_NATIVE=ON`, effective `-march=native`), OpenMP, CPU repacking and llamafile behavior equally. No additional `CFLAGS`/`CXXFLAGS`, LTO, sanitizers, profiling, compiler substitution or ccache-based provenance assumptions are allowed. Record full versions, compiler hashes, configure argv, complete caches and compile commands; require the recorded identity for bundle reuse.

Phase A uses one campaign-owned temporary detached worktree/build at a time, under `benchmark-results/step10/<run-id>/.prepare/<A|B|C>/{source,build}`. It builds each exact revision, extracts the executable and its required project shared-library closure to `artifacts/<A|B|C>/bin/`, then verifies dependency resolution and `--version` before removing only that owned temporary source/build. Do not delete existing development/original/semantic trees. Preserve failed build logs and useful diagnostics. D references C's bundle; there is no D llama build. This sequential extraction replaces the proposed three retained build trees because disk space is limited.

The following common options remain frozen. Phase A supplies the exact source/build paths, adds HINT OFF/TRACE OFF for B or HINT ON/TRACE OFF for C, and builds `--target llama-server --parallel 2`. The preparation job limit was reduced before measurement to reduce memory pressure; compiler flags and measured runtime settings are unchanged. Configure/build logs stream to disk. Verified existing bundles may be reused without rebuilding:

```bash
common=(
  -G "Unix Makefiles"
  -DCMAKE_C_COMPILER=/usr/bin/cc -DCMAKE_CXX_COMPILER=/usr/bin/c++
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_FLAGS= -DCMAKE_CXX_FLAGS=
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DBUILD_SHARED_LIBS=ON
  -DGGML_CPU=ON -DGGML_NATIVE=ON -DGGML_OPENMP=ON
  -DGGML_CPU_REPACK=ON -DGGML_LLAMAFILE=ON
  -DGGML_BACKEND_DL=OFF -DGGML_CPU_ALL_VARIANTS=OFF
  -DGGML_BLAS=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF
  -DGGML_METAL=OFF -DGGML_HIP=OFF -DGGML_SYCL=OFF -DGGML_OPENCL=OFF
  -DGGML_RPC=OFF -DGGML_LTO=OFF -DGGML_CCACHE=OFF
  -DLLAMA_BUILD_COMMON=ON -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_APP=OFF
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_MTMD=OFF
  -DLLAMA_OPENSSL=OFF -DLLAMA_SUBPROCESS=ON -DLLAMA_USE_SYSTEM_GGML=OFF
)
```

`LLAMA_BUILD_TOOLS=ON` is required by the common tools/server build gate, but build only the `llama-server` target and dependencies. Require CPU as the only available GGML backend. Compare all execution-relevant cache options/compile flags across A/B/C; record only unavoidable source-revision differences. A predates the HINT/TRACE options and server compute-profile CLI; do not retrofit them or pass unknown options to A. B/C/D use TRACE OFF and `--server-compute-profile-mode legacy`, preserving the `llama_decode()` path. A uses its original `llama_decode()` path without that new flag. No auto/phase compute-profile experiment is part of this protocol.

Capture clean source HEADs, source status, generated build-info commit, ELF build IDs, SHA-256 of all executable/DSO dependencies, and resolved `ldd`/RPATH identities after build and again after measurement. Reject stale build-info or cross-build library resolution. C and D must resolve exactly the same libraries. Keep sources/binaries immutable during the campaign and do not compile concurrently with measurement.

Check capacity before each build and leave at least 512 MiB free for results. Stop for insufficient capacity; preserve failed preparation logs and do not delete existing development trees or reuse uncertified binaries merely to fit.

## Server and scheduling conditions

Use one local server at a time, one slot, CPU-only execution, no other server traffic, draft model, multimodal input, adapter, external contention, speculative decoding or changed compute profile. Keep mmap defaults and KV types unchanged between revisions; record effective startup configuration. Use the frozen profile UID for A/B/C servers and D launcher/server, nice 0. Root loader and normal-user launcher remain raw policy 0. Do not use phase TRACE, verbose diagnostic tracing, per-token timings, extra probes, or BPF phase polling during measurement.

For every server, the common arguments are:

```text
-m <profile-model-path>
--host 127.0.0.1 --port 8096
--n-gpu-layers 0 --threads <server-CPU-count> --threads-batch <server-CPU-count> --threads-http 2
--ctx-size 2048 --parallel 1 --batch-size 512 --ubatch-size 256
--flash-attn off --no-ui
```

Compute and batch threads equal the number of allocated server representatives. HTTP threads remain two. Set server affinity before exec and verify all observed TID affinities and policies outside timed requests. Use one client, one non-streaming request at a time. Reserve loopback port 8096 before the campaign; stop rather than silently choose a new port if unavailable.

Launch from a controlled environment: remove inherited `LLAMA_ARG_*`, `GGML_*`, `OMP_*`, `OPENBLAS_*`, `MKL_*`, `LD_PRELOAD`, `LD_LIBRARY_PATH`, `CFLAGS` and `CXXFLAGS` overrides; set `OMP_NUM_THREADS=<server-CPU-count>` and `OMP_DYNAMIC=FALSE`, then set only the validated bundle-local `LD_LIBRARY_PATH=<bundle>/bin`. Leave other OpenMP tuning unset and record relevant environment/runtime library identity. Do not expose unrelated environment secrets in manifests. Keep client implementation, CPU affinity, JSON bytes, HTTP/1.1 connection policy and response handling equal across A/B/C/D. Use a fresh HTTP connection per request with `Connection: close`, no automatic retry, and a 180-second timeout.

For A/B/C, sched_ext must be disabled and all server TIDs must return raw policy 0. C still calls its HINT marker but has no attached scheduler uprobe.

For D, use the frozen loader/launcher and exactly C's server/marker paths. The root command, executed later by the narrow Phase B privileged helper, is conceptually:

```bash
sudo taskset -c "$HOUSE_CPU" "$REPO/tools/sched_ext/build/bin/llama_scx" \
  --phase-uid "$PROFILE_UID" --phase-register-socket "@$SOCKET_NAME" \
  --server-exe "$C_BUNDLE/bin/llama-server" \
  --marker-elf "$C_BUNDLE/bin/libllama-server-impl.so"
```

The existing loader embeds the absolute BPF-object path under `tools/sched_ext/build/`; verify that object hash. There is no new object-path CLI. Choose `SOCKET_NAME=llama_scx_step10_<run-id>_<visit-id>` with total abstract name length below 108 bytes. The normal-user command uses the validated one-shot registration launcher:

```bash
taskset -c "$SERVER_CPUS" "$REPO/tools/sched_ext/build/bin/llama_scx_child" \
  --phase-register-socket "@$SOCKET_NAME" -- "$C_BUNDLE/bin/llama-server" \
  -m "$PROFILE_MODEL" --host 127.0.0.1 --port 8096 \
  --n-gpu-layers 0 --threads "$COMPUTE_THREADS" --threads-batch "$BATCH_THREADS" --threads-http 2 \
  --ctx-size 2048 --parallel 1 --batch-size 512 --ubatch-size 256 \
  --flash-attn off --no-ui --server-compute-profile-mode legacy
```

Require registration ACK and the two established registration log messages. Verify loader/launcher raw policy 0, selected server/all observed TIDs raw policy 7. Keep exactly one PID-scoped entry phase uprobe, no external phase observer, no map reads or instrumentation during requests. Retain the loader's existing coarse lifecycle check. Root-only control is outside request timing; never require noninteractive sudo or ask for a password. A bounded supervisor may be a safety backstop, not the expected termination mechanism.

## Exact workload

POST only to `http://127.0.0.1:8096/completion`, with `Content-Type: application/json`. The canonical prompt below is specified by immutable ASCII text and deterministic construction; this avoids unrecorded random prompts. Repeating the same notes is intentional. The construction is offline preparation, not a runner or inference operation:

```python
base = "A small public library stands beside the town square. Its shelves hold stories, science books, travel guides, and local history. Every morning the librarian opens the windows, checks returned books, and prepares a quiet room for readers. Children visit after school to choose books and ask questions. Older residents use newspapers and share memories of the town. Visitors find maps and learn about nearby walking routes. A reading group meets once a week. Each person explains one idea from a book and listens to the other readers. The library supports curiosity, patient learning, and friendly conversation."
prompt = "Read the following notes and continue with a concise description of the library.\n\n" + "\n\n".join([base] * 8) + "\n\nContinue this sentence: The library is useful because"
request = {
    "prompt": prompt,
    "n_predict": 128,
    "temperature": 0,
    "seed": 424242,
    "stream": False,
    "cache_prompt": False,
    "ignore_eos": True,
    "id_slot": 0,
    "n_cache_reuse": 0,
    "stop": [],
    "return_tokens": False,
    "timings_per_token": False,
}
# prompt.txt has exactly prompt.encode("utf-8"), with no trailing newline.
# request.json has json.dumps(request, sort_keys=True, separators=(",", ":"),
#                             ensure_ascii=True) + "\n", encoded as UTF-8.
```

`prompt.txt`: 5023 bytes, 789 whitespace-separated words, SHA-256 **`b7be51379d30270d4d645aefb6014525e89e2bcba6e4be60f5f5613efbe5b4a9`**. Canonical `request.json`: 5243 bytes, SHA-256 **`7b68e4809a1f9bca18c2bc29b87c62c637e19e2ccd3785745cc717c046999e1d`**.

The planned scale is roughly 1000 prompt tokens and exactly 128 output tokens, comfortably within context 2048. Exact model-token count is not claimed from text alone. Before any measured request, the future runner must establish the count from normal warm-up results, require it to be in 512..1536 inclusive, and require identical `tokens_evaluated` and `timings.prompt_n` for every request/configuration. If the fixed text lies outside that range or counts differ, stop for a protocol amendment; do not tune the prompt after viewing performance. Do not add a chat template. The 128-token bound, empty stop list and `ignore_eos=true` prevent variable EOS termination. Require 128 generated tokens, finite positive prompt/decode timings, nonempty response, HTTP 200, no truncation, and `timings.cache_n=0`. `cache_prompt=false` bypasses common-prefix reuse in both inspected revisions. Each request recomputes the full prompt; do not accept cache-hit-only prefill.

## Repetition, lifecycle and deterministic order

Use **10 measured requests per configuration**, 40 total. Each visit starts one fresh server, performs **two excluded warm-up requests of the exact workload**, then performs **one measured request**, and shuts down that server. Because configs are interleaved and only one server may run, there are two warm-ups per visit (20 per config, 80 total), not just two per entire campaign. This equal rule establishes initialized graphs/threadpools and warm model pages after every process restart without accepting KV prompt reuse. Never include startup/load/warm-up/cooldown in measured request duration.

Before each visit, require previous server/launcher/loader gone, free port, sched_ext disabled and no remaining project BPF state. Start the next configuration only after that cleanup. For D, normal target SIGTERM -> launcher reap -> loader pidfd cleanup must complete; allow natural BPF teardown up to 2000 ms after loader exit, saving observations before checking. No explicit BPF deletion. A failure aborts the campaign and preserves evidence.

Measured order consists of 10 four-config blocks, using left rotation of ABCD by `(block_number - 1) % 4`:

| Block | Visit order |
| --- | --- |
| 1 | A B C D |
| 2 | B C D A |
| 3 | C D A B |
| 4 | D A B C |
| 5 | A B C D |
| 6 | B C D A |
| 7 | C D A B |
| 8 | D A B C |
| 9 | A B C D |
| 10 | B C D A |

Each config occurs once per block and 10 times overall; its position counts differ by at most one. Persist the complete 40-visit order before starting, including two warm-ups then one measurement per visit. Use IDs `01-A` through the prescribed last visit `40-A`, with block/position stored explicitly, not an unrecorded shuffle. Preserve block identity for paired variability analysis. No thread-count, prompt-size, co-load or compute-profile sweep is part of the primary comparison.

## Thermal, frequency and background conditions

Discover every available cpufreq policy and record driver, governor, available governors, min/max limits, preference, CPU membership and instantaneous current frequency. Discover global/per-policy boost or turbo controls when exposed. Freeze the execution-relevant state from the profile across a campaign; current frequency is an observation and may vary. Never automatically change governors, limits, turbo, SMT, fan policy or power settings. Missing optional interfaces are recorded as absent and do not alone fail the campaign.

Discover a suitable CPU package sensor by identity/label, including `k10temp/Tctl` and `coretemp/Package id N`, without assuming a hwmon index or requiring a vendor. If found, retain the bounded cooldown: after two warm-ups, take three readings five seconds apart, require <= **55 C** and a range <= **2 C**, plus aggregate CPU busy <= **5%** in both intervals. If no sensor exists, record `temperature_sensor=unavailable` and a null reading; use the same bounded idle/busy/load checks and explicitly report that thermal validation was unavailable. No fabricated temperature or claim of thermal validation.

Record exposed adapter/AC and materially relevant power-supply state and require it to remain stable. When no supply interface exists, record absence; never fabricate AC=1 or fail solely for that absence.

Before each block reject known interactive/build/download/benchmark activity, require one-minute load <= **1.0** and aggregate busy <= **5%** across a five-second idle observation. The three-reading post-warm-up check without thermal observability also requires load <= 1.0. Aggregate busy remains `100 * (1 - delta(idle+iowait)/delta(total))` from the first eight `/proc/stat` counters. Allow a maximum **180-second** readiness/cooldown window. Preserve all readiness evidence. Record machine state immediately before/after measured requests; no persistent metrics process or observer runs during the timed POST.

A changed kernel/boot/BTF/topology, execution-relevant frequency/turbo/power state or sensor identity invalidates the campaign. Do not relax limits after looking at results. Readiness violations precede timing. A post-request identity/configuration/count/error violation invalidates its entire paired block and aborts the primary campaign; preserve incomplete/invalid evidence and every issued request. No sample replacement or outlier removal.

## Metrics and statistics

Use normal non-streaming server response fields, present in both revisions:

| Metric | Source | Direction |
| --- | --- | --- |
| Prefill throughput, tokens/s | `timings.prompt_per_second` | Higher is faster |
| Decode throughput, tokens/s | `timings.predicted_per_second` | Higher is faster |
| Total request duration, ms | External monotonic client clock, `request_wall_ms` | Lower is faster |

Start `time.perf_counter_ns()` immediately before sending the prepared POST and stop after reading the entire response body, before JSON decoding/result-file writes. Request construction, readiness checks and logging are outside the interval. This external client interval includes connection/HTTP/queue/tokenization/response costs and excludes server startup. It adds no scheduler/model timing hook. Record the counter implementation/resolution; keep it identical for all requests. Cross-check normal `prompt_ms`, `predicted_ms`, `prompt_n`, `predicted_n`, `cache_n`, `tokens_evaluated`, `tokens_predicted`, stop type, truncation, and response/content hash. The sum `prompt_ms+predicted_ms` is a server processing cross-check, **not** a substitute for whole-request duration. Keep full response JSON and normal stdout/stderr. Do not enable libllama diagnostic perf timing, phase TRACE, per-token timestamps or queue/worker accounting.

For each config/metric, use all 10 valid measured requests and report n, median, minimum, maximum, Q1, Q3, IQR and MAD. Q1/Q3 use linear interpolation at fractional position `(n-1)*p` in sorted samples (p=0.25/0.75); IQR=Q3-Q1; MAD=median(abs(sample-median)). Warm-ups are preserved and labeled but excluded.

For each A -> B, B -> C and C -> D pair, primary relative raw delta is:

```text
delta_pct = 100 * (median_candidate - median_reference) / median_reference
```

For throughput, positive delta means faster; for duration, positive delta means slower. Gate on signed slowdown, expressed so that positive always means slower:

```text
duration_slowdown_pct   = 100 * (median_candidate / median_reference - 1)
throughput_slowdown_pct = 100 * (median_reference / median_candidate - 1)
```

Throughput slowdown is the reciprocal-rate equivalent-duration change, not simply the negated throughput delta. Report both raw delta and slowdown. Never offset a prefill/decode regression with an improvement in another metric. Report the same per-block paired deltas as a cross-check; the primary estimate remains the ratio of configuration medians.

Also calculate a paired-block bootstrap 95% percentile interval for each slowdown: resample the 10 whole blocks with replacement 10000 times using Python `random.Random(20261006)`; recompute the ratio of medians each time; percentile endpoints 0.025/0.975 use the same linear interpolation convention. Preserve the four-config block associations, seed and analysis version. This is offline statistics, not new workload. If a 95% interval spans both <=0.5% and >1.0% categories, label precision inconclusive and require investigation/repeat even when the point estimate is small. Report intervals and spread; do not present a tiny median difference as resolved overhead when variability prevents that conclusion.

## Decision gate fixed before results

Apply the following primarily to B -> C and C -> D, using the worst signed median slowdown among prefill, decode and total duration for each pair:

| Slowdown | Required conclusion/action |
| --- | --- |
| <= 0.5% | Acceptable neutral overhead, subject to the frozen validity/precision checks |
| > 0.5% and <= 1.0% | Repeat/variance investigation required before judgment |
| > 1.0% | Mandatory overhead investigation before freezing Lightweight Base v1 |

A -> B is reported separately as the fork/base implementation delta; it is not attributed to sched_ext. Accept the infrastructure only when both B -> C and C -> D satisfy the gate. Negative slowdown denotes improvement, not evidence of a phase-aware optimization. Do not cherry-pick samples, optimize before measurements, or rename C -> D to framework overhead. Further experiments, reruns or implementation changes need later authorization.

## Four-phase execution and result artifact schema

Close Firefox, every Codex UI/CLI session and unnecessary applications before Phase A. Execute these four scripts sequentially as the frozen non-root repository owner from one terminal or text console. Keep applications closed until Phase D finishes. Switching consoles does not close GUI applications:

```sh
./tools/sched_ext/bench/step10_phase_a_prepare.sh
./tools/sched_ext/bench/step10_phase_b_arm.sh
./tools/sched_ext/bench/step10_phase_c_campaign.sh
./tools/sched_ext/bench/step10_phase_d_finalize.sh
# Firefox/Codex may reopen only after Phase D reports completion.
```

Every phase rejects detected interactive/benchmark applications before work. Phase A stops only identity-verified leftover user-owned managed Codex daemons after the UI/CLI has closed, then performs sequential comparable builds and non-inference bundle checks. `--reuse-artifacts` instead validates and hardlinks prior exact A/B/C bundles, with no build and no measurement reuse. It can supersede an unused PREPARED campaign only when no arming record, raw visit or completion marker exists; the old directory/evidence remains. Reuse checks frozen build/request/metric/repetition identities and the saved protocol hash, so workflow-only documentation changes can preserve identical runtime bytes. The new campaign records both source and current protocol identities. Phase B revalidates identities, captures the pre-campaign machine/BPF baseline, prints and executes one sudo command to arm a campaign-specific helper on the housekeeping representative. It does not load the scheduler. Phase C is the ONLY measurement phase: unattended interleaved visits, no sudo prompts, no continuous observer, and no interpretation. Phase D validates stored evidence and calculates statistics offline. Each entry point supports `--help` and a strictly read-only `--dry-run`; diagnostics do not execute a phase. SIGHUP/SIGINT/SIGTERM request bounded cleanup, and interrupted build commands release only their owned process groups.

The helper authenticates Unix SOCK_SEQPACKET peers with SO_PEERCRED (frozen profile UID) and a per-campaign token; the runner authenticates the root helper PID/UID/starttime. Commands are restricted to HELLO/CHECK, starting the frozen loader for a predefined D visit, STOP, and FINISH/ABORT. Caller-supplied shell commands, paths and loader arguments are forbidden. The helper waits on IPC, signals and the loader pidfd using blocking selectors; no periodic monitor runs. It expires after six hours, with a 20-minute per-loader safety deadline. Normal target termination remains the expected cleanup path. Finite BPF inventories after loader exit are saved at T0/50/100/250/500/1000/2000 ms BEFORE assertions. Never delete BPF objects during observation.

Use the existing ignored `/benchmark-results/` convention:

```text
benchmark-results/step10/
  .active-run                     # small automatic run pointer
  <UTC-run-id>/
    manifest.json                 # identities, host-profile SHA256 and status
    host-profile.json             # exact immutable host-profile bytes
    protocol.md
    artifacts.json                # A/B/C hashes and dependency provenance; D references C
    artifacts/{A,B,C}/bin/         # required runtime bytes only; no model copy
    builds/{A,B,C}/                # caches, compile commands, build-info, logs, identities
    machine.json                  # pre/post campaign snapshots
    visit-order.json
    workload/{prompt.txt,request.json}
    armed.json                    # helper PID/starttime/UID/affinity/socket identity
    bpf-baseline.json
    raw/<visit-number>-<config>/
      visit.json
      command.json
      processes.json
      registration.json           # D only
      policies-{before,pre-measured,after}.json
      readiness.json
      system-{before,after}.json
      warmup-{1,2}-{response,client}.json
      measured-{response,client}.json
      server.{stdout,stderr}.log
      loader.log                  # D only
      teardown-bpf-T<0..6>.json    # D; exact identities before assertions
      root-cleanup.json           # D only
      cleanup.json
    bpf-final.json
    final-cleanup.json
    CAMPAIGN_COMPLETE
    raw-runs.csv
    summary.csv
    summary.json
    protocol-validation.json
    final-report.md
    commands.jsonl
```

Run ID is UTC `YYYYMMDDTHHMMSSZ` with an optional numeric collision suffix. Never overwrite a completed or failed campaign. The active-run pointer joins all four phases; it is not a benchmark result. Each visit stores configuration, block/position, exact request/response hashes, build identities, raw timing fields, affinity/policy snapshots, warm-ups and cleanup evidence. Preserve every issued request and every invalid/incomplete visit; abort on failure without replacement samples. The post-campaign manifest confirms model/runtime rehashing so offline interpretation needs no external memory.

The external POST timer excludes JSON decoding, result serialization, readiness, warm-ups, startup and cleanup. During it the client blocks on HTTP, the privileged helper blocks on events, and no ps/bpftool/temperature/frequency/phase observer runs. Pre/post checkpoints and bounded readiness are outside the timer. No benchmarks are executed in the preparation commit. No model is copied, generated artifacts/results are untracked, and no tag or push is created.

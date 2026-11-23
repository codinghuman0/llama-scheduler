# Status

## 2026-11-23: preserved NEW_A workspace and Intel handoff

Added `new-a-workspace/` alongside the existing base project, preserving its
history and code. Models, frozen runtime binaries, caches, and duplicate archives
are excluded. The portable script builds historical B0 and the retained A/R source
recipe with identical AVX2/OpenMP options and compares B0_L, F6_L, and A_L under
the default Linux scheduler. It never loads BPF or changes system configuration.

Validation completed on AMD Ryzen 5 5500U, targeting Intel i5-1240P / Ubuntu:

- Both fresh server builds passed; source/overlay/compiler and loaded DSO identities recorded.
- 15 smoke visits completed (156 requests including warmup, 16 output tokens/request).
  A/F6 and A/B0 token equality passed for both concurrent cohorts, two singleton
  cases, and a concurrent cpu25 case. Cache reuse, affinity, actual CPU load,
  policy decisions and OpenMP team sizes were checked.
- Under cpu25, A selected five workers in all 15 measured eligible Decode calls;
  F6 selected six. All owned processes exited normally; sched_ext stayed disabled.
- `python3 -B new-a-workspace/tools/test_intel_experiment.py`: 9 tests passed.
- `make -j2 check`: passed; 51 Python tests with one expected skip because the
  separate `.deps` semantic fork is absent, plus shell checks. No kernel load.
- Packaged historical performance recalculation: 20 contrasts and two pool
  conditions passed; no new inference was used for that recalculation.

Exact local smoke command, from `new-a-workspace/`:

```bash
bash scripts/intel_experiment.sh smoke --allow-non-intel \
  --baseline-repo /home/codinghuman/projects/llama.cpp \
  --model /home/codinghuman/projects/new-a-workspace/models/model.gguf
```

Known limits: Intel hardware, Intel performance and Intel sched_ext loading are
NOT_RUN. Full pilot/confirmation is NOT_RUN. This short smoke makes no gain claim.
The first UI alias-header build failure is retained with its recipe-2 fix.
Original model, source and best A frozen runtimes passed preservation hashes.

Next milestone: teammate runs the [Intel guide](../new-a-workspace/docs/INTEL_EXPERIMENT.ko.md).
See [compatibility results](../new-a-workspace/docs/INTEL_COMPATIBILITY_CHECK.ko.md)
and [Codex handoff](../new-a-workspace/docs/INTEL_CODEX_HANDOFF.ko.md).
Raw local check artifacts are in `new-a-workspace/experiments/intel-portability-check-v1/`.

## Milestone 6: baseline sched_ext validation suite

Status: implemented, built, and non-privileged-tested; ready for the next
manual validation run. The suite did not load, attach, stop, restart, or unload
the scheduler. Final read-only sched_ext state remains `disabled`.

### Verified Milestone 5 baseline

`results/manual/milestone5-summary.txt` records a passing selected-child test
on Ubuntu kernel `7.0.0-28-generic`: the active scheduler was `llama_simple`,
`SCX_OPS_SWITCH_PARTIAL` was enabled, the shell and launcher parent remained
policy `0` with `ext.enabled = 0`, and the selected finite `cpu_burn` child was
policy `7` with `ext.enabled = 1`. Its launcher propagated success as exit `0`.
With sched_ext disabled, the launcher refused execution with exit `1`.

### Milestone 6 implementation

Added or changed files:

- `tests/sleep_wake.c` and `build/bin/sleep_wake`: finite sleeping/waking
  workload with periodic machine-readable progress lines.
- `tests/cpu_burn.c`: unchanged scheduling behavior, now emits bounded
  machine-readable progress lines and a final result record.
- `scripts/run_validation.sh` and `scripts/validation_runner.py`: manual suite,
  dynamic affinity discovery, process-group cleanup, progress monitoring,
  JSON Lines records, and text summary generation.
- `tests/test_validation.py`: non-privileged parser, CPU-mask, JSON Lines,
  aggregation, command-failure, timeout, cleanup, and disabled-state tests.
- `Makefile`: builds `build/bin/sleep_wake` and includes the new non-privileged
  tests in `make check`.
- `docs/VALIDATION.md`: exact manual operator procedure and pass/fail criteria.
- `docs/STATUS.md`, `docs/PLAN.md`, and `docs/GENERATED.md`: current milestone,
  non-privileged-check, and generated-artifact records.


### Milestone 6 preflight repair

Root cause: the original preflight used `/sys/kernel/sched_ext/name` and read it
only when that top-level file existed. On the recorded Ubuntu kernel
`7.0.0-28-generic`, the enabled layout reports state at
`/sys/kernel/sched_ext/state` and the active ops name at
`/sys/kernel/sched_ext/root/ops`; there is no top-level `name` file. The old
existence check therefore assigned `None` and rejected `llama_simple`.

`scripts/validation_runner.py` now reads `/sys/kernel/sched_ext/root/ops`
first. The older `/sys/kernel/sched_ext/name` is retained only as a documented
fallback for kernels that expose it. A custom `--ops-path` is test-only and,
like `--state-path`, is rejected unless `--dry-run` is set.
`tests/test_validation.py` covers accepted `llama_simple`, rejected alternate
names, a missing ops-path diagnostic, and that safety rule. No BPF, scheduler
policy, or `SCX_OPS_SWITCH_PARTIAL` code changed.

The BPF program and loader are unchanged. `SCX_OPS_SWITCH_PARTIAL` remains in
`src/llama_scx_simple.bpf.c`; no CPU-selection behavior, DSQ selection/order,
slices, queues, instrumentation, phase-aware policy, or llama.cpp support was
added. Normal `SCHED_NORMAL`, `SCHED_BATCH`, and `SCHED_IDLE` tasks remain under
Linux fair scheduling.

### Validation scenarios and criteria

- `single_cpu_bound`: one finite selected `cpu_burn`; requires child progress
  and a propagated zero exit.
- `under_subscribed`: `max(1, allowed_cpu_count - 1)` finite CPU children. A
  one-CPU caller runs one child and is explicitly marked degraded.
- `over_subscribed`: `allowed_cpu_count + 1` finite CPU children; all must
  progress and complete before their explicit timeouts.
- `affinity`: valid inherited-mask single-CPU and, where possible, multi-CPU
  selected children; `/proc` observed masks must exactly match requested masks.
- `mixed_sleep_wake`: finite CPU and finite sleeping/waking children together;
  both types must produce progress and exit zero.
- `expected_exec_failure`: a nonexistent executable must yield launcher exit
  `127`; this detected failure is a pass.
- `expected_timeout`: a long finite workload exceeds a one-second explicit
  timeout; the test passes only if timeout is detected and the launcher process
  group is cleaned up.
- `inactive_scheduler`: a separate post-unload check passes only when the
  launcher refuses before forking with exit `1` and a clear inactive-state
  message. It never stops a live scheduler to obtain this condition.

Every scenario writes one schema-versioned JSON object per line to
`results/validation/YYYYMMDD-HHMMSS/results.jsonl` and a readable summary to
`summary.txt`. Records include scheduler state/name, complete inherited CPU
mask, PID/affinity/exit/progress/timeout fields, log paths, and failure reason.
A live process without new workload progress for 2.0 seconds fails its scenario
and has its own process group terminated.

### Non-privileged build and test result

Commands run without sudo:

```text
make clean
make -j"$(nproc)"
make check
```

Result: successful build of the loader, selected-child launcher, CPU workload,
and sleep/wake workload. Checks passed the sched_ext ABI guard, matching-kernel
UAPI compilation guard, finite workload runs, existing launcher dry-run test,
and fourteen validation tests, including root/ops preflight regression coverage. The dry-run tests use only a temporary fake enabled
state and `llama_scx_child --dry-run`; no child policy is changed.

### Known limitations and next checkpoint

The full scheduler-dependent suite has not been run by the agent. It requires
the user to manually start the foreground loader and preserve loader/verifier
output and scheduler exit dumps. The over-subscription scenario intentionally
refuses if the operator-selected safety ceiling is below the required
`allowed_cpu_count + 1`, rather than reducing the requested coverage silently.

After explicit approval and following `docs/VALIDATION.md`, the exact next
manual command is:

```sh
./scripts/run_validation.sh
```

## Milestone 7: bounded sched_ext instrumentation

Status: implemented, built, and non-privileged-tested; ready for manual
instrumented verification. No scheduler was loaded, attached, stopped, or
restarted for this milestone. Milestone 6 manually passed 7/7 scenarios; its
recorded evidence is `results/validation/20260806-132646/` and
`results/manual/milestone6-summary.txt`.

### Files and behavior

- `include/llama_instrumentation.h` defines schema version 1 and shared bounded
  map layouts.
- `src/llama_scx_simple.bpf.c` adds observation-only counters, live tracking,
  completed task records, and `disable` cleanup. Its existing select-CPU, DSQ,
  vtime, slice, and partial-switching decisions are unchanged.
- `src/llama_scx_simple.c` adds `-o/--output-dir`, collision-safe directory
  creation, `instrumentation.json`, `summary.txt`, and concise exit output.
- `scripts/instrumentation_report.py` and `tests/test_instrumentation.py` add
  non-privileged schema, aggregation, collision, summary, and source-path
  regression coverage.
- `docs/INSTRUMENTATION.md` contains the manual procedure and definitions.

### Maps, cleanup, and metric definitions

`instrumentation_cpu_stats` is a one-key `BPF_MAP_TYPE_PERCPU_ARRAY` whose
values contain enqueue, direct-local insertion, shared-DSQ insertion, dispatch,
running, stopping, runtime, queue-wait, migration, and failure counters.
`live_task_stats` is a fixed `BPF_MAP_TYPE_HASH` of 1,024 PID-plus-start-time
keys. `completed_task_stats` is a separate fixed 1,024-entry hash for bounded
final records. `tracking_state` is a one-entry array holding current and peak
tracked counts, updated only on enable/disable.

Enqueue means `llama_simple_enqueue` invocation. Direct-local means the existing
idle-selector local insert; shared means the existing enqueue shared-DSQ insert.
Dispatch means the actual baseline `dispatch` callback. Runtime is `running` to
next `stopping`, charged to the stopping CPU. Queue wait is the latest
enqueue-callback timestamp to next running and is overwritten by a newer
enqueue; direct local-DSQ activations from `select_cpu` may not contribute.
Migration means a CPU change
between successive running callbacks. Full definitions and limitations are in
`docs/INSTRUMENTATION.md`.

`disable` snapshots a live record to the completed bounded map and deletes the
live map entry. The key's start time prevents PID-reuse merging. A missed cleanup
can leave a bounded stale entry until unload; capacity, update, lookup, tracking-state lookup, cleanup,
and completed-record failures are counted. Task storage was evaluated but not
chosen because its population is not capacity-bounded. Instrumentation failures
never gate existing scheduling calls. Expected overhead is per-CPU counter work,
a bounded hash lookup, and a short task-local spin lock in existing callbacks.

### Non-privileged result and next checkpoint

Commands run without sudo:

```text
make clean
make -j"$(nproc)"
make check
```

The final check includes the existing baseline guards and validation tests plus
nine instrumentation schema/source tests. The next manual instrumentation
command, after explicit approval and the documented disabled-state check, is:

```sh
sudo ./build/bin/llama_scx_simple -v -o "results/instrumentation/$(date -u +%Y%m%d-%H%M%S)"
```

Use the exact operator procedure in `docs/INSTRUMENTATION.md`; do not use this
command automatically or under the agent.


## Milestone 10B: neutral /proc/stat utilization validation

Status: standalone tooling and brief smoke checks PASS; full manual
10 s baseline / 20 s stress / 10 s recovery validation NOT TESTED. M0-M9
remain accepted as per the current project state; older milestone entries above
are historical. No scheduler, phase integration, BPF map, or llama.cpp change.

Added `scripts/sample_cpu_util.py`, `scripts/run_m10b.py`,
`tests/test_m10b.py`, and `docs/M10B.md`. The sampler uses interval deltas,
excludes double-counted guest fields, records actual monotonic intervals, and
emits invalid rows for counter regressions. The helper logs load transitions,
cleans up only its own child group, and summarizes complete intervals.

Non-privileged checks: Python compilation, seven focused tests, `make -j2`,
selected-CPU CSV/error checks, actual worker affinity/SCHED_OTHER inspection,
and Ctrl+C process-group cleanup all passed. A preserved 1/2/1 s smoke run in
`results/m10b/20260911-smoke/` showed CPU 2: 2.81 -> 100.00 -> 0.91 percent;
CPU 4: 0.00 -> 100.00 -> 0.00 percent. All 504 CPU rows were valid. This is
short smoke evidence, not a full M10B reliability claim. Full commands,
limitations, field definitions, and initial dirty status are in `docs/M10B.md`.

Next manual command (unprivileged, from repository root):

```sh
m10b_run="results/m10b/$(date -u +%Y%m%d-%H%M%S)-step"
python3 scripts/run_m10b.py run --stress-cpus 2,4 --output-dir "$m10b_run"
cat "$m10b_run/summary.csv"
```

Next checkpoint is M10B result analysis. M11 and all scheduling policy work
remain deferred. No commit, reset, stash, clean, or privileged runtime
operation was performed. Pre-existing dirty files were preserved.

## Milestone 11: semantic llama-server phase marker integration

Status: PASS. Scheduler/semantic builds, ABI validation, unprivileged tests,
privileged struct_ops load, PID-specific uprobe attachment, selected-child
isolation, and end-to-end marker/callback evidence passed on the validated
`7.0.0-29-generic` laptop. The accepted controlled request produced 8 begin and
8 end events, 1 PREFILL and 7 DECODE begins, zero semantic failure counters,
inactive/UNKNOWN final state, and nonzero PREFILL/DECODE running observations.

The fixed clean semantic provider is
`../llama.cpp-semantic@5219055a578fd741e029e81fefef6f3a5695086d`.
Its server stores PREFILL or DECODE on each token when adding it to the shared
batch, reduces each submitted/retried range to UNKNOWN=0, PREFILL=1, DECODE=2,
or MIXED=3, and emits an 80-byte v1 C marker around synchronized decode work.
The built marker-bearing shared objects expose default-visible decode and
worker symbols. The fork was not modified.

M11 adds scheduler-owned, pid-specific decode begin/end uprobes in the existing
BPF object. Begin copies and validates the v1 event with
`bpf_probe_read_user()`, explicitly translates all four phases, and publishes
bounded TGID scalar state. End clears only a matching run/call/retry/phase.
The selected-child launcher uses a one-shot authenticated registration
handshake so the loader can attach to the exact exec'd SCHED_EXT child. The
handshake carries no phase events. The old SOCK_SEQPACKET phase source remains
available, and the loader rejects simultaneous socket and uprobe sources.
The corrected manual checkpoint runs only the loader as root. It passes the
invoking normal user's UID through `--phase-uid`; the launcher and semantic
server run as that user. Runtime PASS also requires UID evidence plus
SCHED_NORMAL shell/launcher, SCHED_EXT server, matching registration/target
TGID, and no unrelated SCHED_EXT task.

Phase remains observation only. Select-CPU, local/shared DSQ choice, dispatch,
slice, weight, vtime, affinity, migration policy, and
`SCX_OPS_SWITCH_PARTIAL` are unchanged. M10B and `/proc/stat` are untouched.
Marker synchronization changes timing, so no performance-neutrality claim is
made.

The exact audit, ABI offsets, ELF symbols, counters, constraints, and
three-terminal debug commands are in `docs/LLAMA_PHASE.md`.

## Milestone 11R: reproducible semantic baseline release

Status: release tooling implemented; unprivileged verification is recorded in
the release-candidate audit. A fresh-machine privileged reproduction remains a
manual post-push acceptance test.

M11R adds a canonical external revision manifest, ignored repository-local
semantic dependency, Ubuntu capability/bootstrap checks, deterministic
CPU-only semantic and scheduler builds, generated reproducibility metadata, and
a one-terminal runtime validator. Only `llama_scx_simple` is invoked through
sudo. The launcher and semantic server remain the invoking normal user, and
the validator proves selected-TGID isolation before sending the controlled
request.

Every M11R run uses a unique `results/m11r/` directory for loader/server/
validation logs, request/response, environment and isolation records, and the
final instrumentation report. Targeted cleanup runs on success, failure,
SIGINT, and SIGTERM and verifies sched_ext returns to disabled. No scheduling
policy dimension is changed in M11R.

## SCX observation cleanup in the sibling fork

Status: source and documentation cleanup implemented in the local sibling
`llama.cpp-fork`; focused local build and non-privileged verification passed.
The unused CPU worker begin/end hooks were removed. The final graph barrier,
decode observation structure, 80-byte v1 ABI, synchronization, and this
scheduler's decode-only attachment path are unchanged.

`docs/LLAMA_PHASE.md` and `docs/EXPERIMENT_GUIDE.md` now distinguish diagnostic
acceptance, phase-dependent policy experiments, and a CPU performance baseline
without phase observation. Scheduler per-task/per-CPU and `PHASE_OBSERVE`
instrumentation remains active when phase input is disabled. No performance
gain has been measured.

Local validation used GCC 16.2.1, CMake 4.3.0, Release shared libraries, and `GGML_NATIVE=OFF`. The full server build used `LLAMA_BUILD_UI=OFF` and `LLAMA_USE_PREBUILT_UI=OFF`.

- `cmake --build ../llama.cpp-fork/build-scx-trace --parallel 1 --target llama-server test-compute-profile test-backend-ops` passed with `LLAMA_SCX_PHASE_TRACE=ON` and `GGML_OPENMP=ON`.
- The `ggml` target built in `build-scx-native` with trace ON/OpenMP OFF and in `build-scx-off` with trace OFF/OpenMP ON.
- `nm -D --defined-only` found no worker marker symbols in all three CPU libraries and found both decode marker symbols in the trace server library. `llama-server --help` passed and retained `--scx-phase-run-id`.
- `ctest --test-dir ../llama.cpp-fork/build-scx-trace --output-on-failure -R '^test-compute-profile$'` passed 1/1.
- `test-backend-ops test -b CPU -o MUL_MAT,RMS_NORM -p 'm=16,n=(1|4),k=256|ne=\[64,5,4,3\]'` passed 253/253 cases in each of the three CPU variants against the CPU reference implementation. The native and trace-OFF runs used the same test executable with `LD_LIBRARY_PATH` selecting the corresponding GGML libraries; `ldd` confirmed resolution. Logs showed actual team sizes of 1, 4, and 16. This does not validate another hardware backend.
- `make build/bin/llama_scx_child` passed. The existing M11 and M11R unittest suites passed 20/20 after the edits, with `test_m11.SEMANTIC` set to `/home/hs/llama.cpp-fork` in the test runner so the ABI check used the edited checkout.
- `bash -n` accepted the new provider build block and the eight existing phase runbook shell blocks. Both repositories passed `git diff --check`.

No BPF scheduler build/load, live uprobe attachment, model inference, or performance measurement was performed. The local host lacks clang, bpftool, and libbpf development headers; scheduler source was not changed.

The provider pin in `config/versions.env` remains
`5219055a578fd741e029e81fefef6f3a5695086d`; bootstrap still builds that
historical provider. The next integration checkpoint requires an explicit
revised pin and rebuild after a human commit, followed by semantic acceptance
with the old baseline preserved. No scheduler loading or model workload was
performed for this cleanup.

## SCX v2 reception

The loader accepts `--phase-uprobe-mode trace|state`. The default `trace` uses the original v1 begin/end ABI. The M11R validation path uses its original provider pin. State mode attaches to `llama_scx_phase_set_v2` and validates the 32-byte event before updating TGID state. Invalid events clear the active phase and retain the accepted run ID and sequence. A pidfd tracks target exit. BPF checks the process start time before attributing active state to a worker.

The state report records applied transitions, diagnostic failures, and the phase at target exit. The state acceptance runner uses matching loader and provider modes and waits for registration before sending requests.

Local validation on Fedora kernel `7.3.4-200.fc44.x86_64` used Clang 22.1.8 and GCC 16.2.1.

- `make -j2 all check-scx-api check-sched-uapi` built the loader, BPF object, launcher, and workloads from the local kernel BTF and UAPI. The BPF ELF contains both v1 handlers and the v2 handler.
- `PYTHONDONTWRITEBYTECODE=1 make -j2 check-unprivileged` passed 57 tests and skipped two external provider checks. The missing legacy socket producer caused the legacy skip. The v1 ABI check also passed separately against both the pinned M11R source and the current sibling provider.
- `python3 tests/test_m10b.py` passed seven tests. The current sibling provider passed its SCX state fixture with trace ON and OFF and the synchronization fixture with trace ON.

Native sched_ext loading, live uprobe delivery, model-backed lifecycle checks, and performance trials remain pending.

### Manual state acceptance checkpoint

Use a current trace-enabled, shared-library provider build and a local CPU-runnable GGUF. From the scheduler repository root, set `SCX_PROVIDER_BUILD` to that build directory and `SCX_GGUF_MODEL` to the model file. Run the existing trace acceptance and the two state cases separately under the scheduler approval rules.

```sh
python3 scripts/validate_phase.py --phase-uprobe-mode state \
    --semantic-dir ../llama.cpp-fork --semantic-build "$SCX_PROVIDER_BUILD" \
    --model "$SCX_GGUF_MODEL"

python3 scripts/validate_phase.py --phase-uprobe-mode state --state-abort \
    --semantic-dir ../llama.cpp-fork --semantic-build "$SCX_PROVIDER_BUILD" \
    --model "$SCX_GGUF_MODEL"
```

The controlled normal case requires three applied transitions and final sequence 3. The second case requires five applied transitions and sequence 5, with an active DECODE phase retired on target exit.

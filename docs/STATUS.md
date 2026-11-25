# Status

## Intel and AMD release entry point

The published launcher prepared both kernel policies from a new shallow clone and from an existing single-branch `main` checkout. Updating kept the original `.git` directory, local `main` branch and untracked team file. A second invocation found the checkout up to date and reused the verified build. The historical AMD comparison's option parser resolves `integrated-runtime-research` and `amd-5-6`, and both saved B0 campaigns reproduce from their raw responses.

`scripts/run-cpu-experiment.sh` clones the shallow `integration-v2` branch or fast-forwards an existing checkout and runs the requested experiment. The CPU smoke, native m4 comparison, FULL kernel smoke and Lite placement comparison discover the local CPU envelope. The public modes use Korean diagnostics and have no temperature sensor, free-disk, free-RAM or AC admission threshold. An available external power reading is recorded in portable placement results. The fixed original AMD protocol still requires AC when invoked explicitly for historical reproduction.

The original 5500U placement study and historical baseline campaigns are published with their compact aggregate results. The release removes 8,986 historical entries (161,989,120 uncompressed bytes) from the checkout. The release also excludes 44 workspace-migration files (5,371,688 bytes). The files are preserved at `25ab433140eafc6cbb3b259b017c2a9252b37900`. [Launch instructions](../README.md#intelamd-cpu-실험) · [Archive and current inputs](../new-a-workspace/experiments/README.md)

Ryzen 5 5500U completed all three Linux smoke fixtures with the shared state-only OpenMP build. File syscall tracing during the test, verified build reuse, doctor, inference and ZIP collection observed zero thermal sysfs opens and zero workspace statfs calls. The host BPF build prepared both FULL checkpoints without a kernel load. The 4P+8E Intel fixture, 8-core AMD fixture, no-SMT AMD and CPU-quota tests passed. Physical Intel and a second AMD desktop are pending.

## Optional Prefill P-core selection

The integration-v2 scheduler includes `prefill-pcore` and a matched `neutral` control. Both use state-v2, selected-child registration and the existing guarded weighted-vtime dispatch. Only a registered task waking during active Prefill can claim an allowed, online, idle P-core representative. FULL records actual running starts per CPU and phase. Both variants export selection attempts and hits. [Intel/AMD smoke procedure](../new-a-workspace/experiments/team-integration-v2/INTEL_HANDOFF.md#prefill-p-core-옵션을-확인하는-짧은-실험)

On AMD Ryzen 5 5500U, kernel `7.0.0-43-generic`, the six policies built in both FULL and Lite. The host tests exercised the production selector with controlled idle masks. Both new checkpoints produced zero P representatives on this six-core AMD. A real-model Linux smoke completed eight concurrent requests and one single request, four output tokens per request, with identical warmup/measurement tokens, zero cross-request cache, per-request timings, and 14 state-v2 transitions including idle. The server exited with code zero and no live process-group members. The ordinary Linux smoke is recorded in `new-a-workspace/state/integration-v2/prefill-pcore-linux-smoke-01`. Intel hardware measurement is pending.

`bash scripts/integration_v2.sh test` passed 48 topology, 22 serving and 16 integration tests. The scheduler build ran the C receiver test and both production-selector host tests. `bpftool gen skeleton` opened all four new objects, and their 11 external function names were present in the running kernel BTF. The `neutral` objects have no idle-claim kfunc reference. The Intel 4P+8E fixture passed the normal resource resolver and checkpoint encoder with four preferred P representatives inside a six-CPU envelope. The AMD target encoded a zero-length preference inside its six-CPU envelope.

The shipped `bash scripts/prefill-pcore-smoke.sh linux` run is in `state/integration-v2/prefill-smoke-linux.PJG86j8c/linux`. Both cohorts' throughput and request timings were checked against the raw responses. A userspace replay fed its 14 published transitions through the C receiver and production selector, with one synthetic wakeup per transition. The simulated Intel candidate chose an idle P representative on the four Prefill transitions. The AMD configuration and both neutral controls used default selection throughout. See `state/integration-v2/prefill-pcore-host-replay.json`. Both final offline checkpoints are in `state/integration-v2/prefill-smoke-prepare.juPdlTDx`. The online controller in `prefill-smoke-scx.T3wPvix4` expired waiting for its first manual loader. The host remained in `sched_ext=disabled`. A new `bash scripts/prefill-pcore-smoke.sh scx` visit generates fresh operator commands.

With AC and direct loader access, both FULL objects passed the AMD selected-child smoke. Each receiver accepted 14 state transitions including four idle events. Both guards passed and both loaders detached cleanly. The two arms produced identical tokens, and `prefill-pcore` recorded zero P-core attempts and hits. The raw visit and deployment evidence are in `state/integration-v2/prefill-smoke-scx.I2XsWiIz`.

The Lite campaign completed 36 visits, with six paired blocks per load condition. For eight concurrent requests, `prefill-pcore` changed throughput relative to the same runtime on default Linux by −1.12% under ambient load (95% paired interval −3.56% to +0.23%) and +0.20% under `cpu25` (−0.99% to +1.34%). Under `cpu25`, mean server CPU time fell from 81.94 to 76.42 CPU seconds. All measured arms produced identical output tokens within each block. [AMD measurement report](../new-a-workspace/experiments/amd-prefill-placement-ac-v1/result-summary.md) · [Protocol](../new-a-workspace/experiments/amd-prefill-placement-ac-v1/protocol.json)

## Mixed workload overlap validation

Integrated the donor [cc68058](https://github.com/hsju2021/llama.cpp-fork/commit/cc6805881aac81d48f605ca285cce9778c0aea3f)
`/slots` parser hardening, fixture shape, regression test and API examples.
The overlap check accepts an object or a one-element array for `next_token`
and skips malformed snapshots. `bash scripts/integration_v2.sh test` passed
all 77 model-free tests, including 22 serving benchmark tests. Real-model
performance measurement is pending.

## Standalone integration workspace

The integration checkout now has an independent Git directory. Its branch,
upstream and working changes were compared before removing the old worktrees
and experiment folders. The workspace keeps the checkout, the original
`llama.cpp` directory and `model.gguf`. The model SHA-256 still matches.

After removal, a fresh OpenMP build, `doctor`, a real-model cohort smoke,
76 model-free tests and recalculation of the saved AMD confirmation passed.
The retained AMD results are self-contained for recalculation. Repeating the
historical B0/A experiment requires the original benchmark runtimes.

## Intel smoke host checks

Intel `smoke` and `m4` use relaxed host checks. Only a fresh build checks its
128 MiB free-space floor. Doctor and inference have no fixed disk gate.
Temperature sensors are skipped throughout the standard smoke path. Seventy-six
model-free tests passed. On AMD, the same OpenMP fixed6 launch and all three
smoke fixtures passed, and syscall traces of the test, doctor, inference and
collection stages showed no thermal sysfs reads or workspace disk checks.
A synthetic Intel 4P+8E topology selected four P-cores and two E-cores.
See the [Intel handoff](../new-a-workspace/experiments/team-integration-v2/INTEL_HANDOFF.md)
for the Intel hardware run procedure.

## 2026-11-25: published integration-v2 AMD performance

The published `fcb2e08` OpenMP research profile completed two B0/A/integration
confirmation campaigns on Ryzen 5 5500U, using the default Linux scheduler.
All 32 primary pairs were technically valid with equal warmup and measured
output tokens. Relative to the historical source rebuild, the integrated build
improved cohort throughput by 17.92–18.11% in ambient and 32.88–37.43% in cpu25.
The [AMD result and raw audit](../new-a-workspace/experiments/amd-published-direct-v1/result-summary.md)
record the frozen workload, exact gains, and scope.

## 2026-11-24: integration-v2 development

The separate integration-v2 worktree builds the R numerical path, semantic
resource decisions, selectable persistent CPU pools, and optional state-v2
publication from its own source tree. The canonical run command verifies build
inputs and mapped project libraries. The first AMD OpenMP and native composition
checks passed. An awake/resumed token difference in a multi-cohort visit was
reproduced in unchanged rebuilt B0 and A. Matched-history comparisons across the
three runtimes are exact, and separate fresh-server heldout visits match the
preserved output prefixes.

The topology donor contributes CPUID and hybrid configuration. Current-kernel
FULL/Lite objects, loader, selected-child and receiver tests compiled. A manual
kernel checkpoint is needed for native verifier and state delivery evidence.
Intel native execution is pending. Current evidence, failures, and remaining
steps are recorded in the
[integration report](../new-a-workspace/experiments/team-integration-v2/professor-integration-report.ko.md).

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

## Integration v2 CPU runtime and selected-child strategies

AMD OpenMP and native clean builds used the same canonical source and verified
exact model fixtures, lifecycle, pool recovery and manual BPF preparation.
Adaptive and fixed thread roles, persistent pool, native Batch priority/park,
SSE, mixed cap128 and scoped head64 are summarized in the integration report.

The current kernel admits preparation of FULL and Lite configurations with
observe, Decode handoff and two previous-CPU strategies. These are compiled,
with kernel verifier, attachment, real dispatch and detach pending operator
execution. Intel uses the same source recipe and still needs native validation.

See [the Intel handoff and kernel procedure](../new-a-workspace/experiments/team-integration-v2/INTEL_HANDOFF.md).

The Intel Linux wrapper skips CPU temperature checks in build, doctor and
inference. Disk requirements are greater than 128 MiB for the build and 32 MiB
for validation and inference.

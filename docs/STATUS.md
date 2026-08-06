# Status

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

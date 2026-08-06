# Status

## Milestone: selected-child SCHED_EXT test

Status: built and ready for user-run manual testing. The verified
partial-switching baseline remains unchanged; no scheduler was loaded or
attached while implementing this milestone. The prior compatibility-repair
record is preserved in `docs/STATUS.compatibility-repair.md`.

### Implementation

- Added `build/bin/llama_scx_child`, built from `src/llama_scx_child.c`.
  It checks that sched_ext is enabled, forks once, prints the parent and child
  PIDs before the child proceeds, and calls `sched_setattr(SCHED_EXT)` only in
  that child before `execvp()`.
- The parent records its existing policy, never calls `sched_setattr`, waits
  for the child, verifies its policy is unchanged, and propagates the child
  exit status.
- The launcher reports a clear inactive-scheduler error before forking, and a
  clear child `SCHED_EXT` transition error with exit status `126` if the
  transition fails. `execvp()` errors return `127`.
- `cpu_burn` is now policy-neutral and finite: it accepts only
  `--seconds N`, never changes its own policy, and returns success after its
  bounded workload completes. The launcher is the sole userspace policy
  transition path.

### Kernel UAPI and scheduler invariants

- Target kernel: `7.0.0-28-generic` from `docs/environment.txt`.
- `include/llama_sched_uapi.h` imports `SCHED_EXT` and `struct sched_attr`
  from `/lib/modules/7.0.0-28-generic/build` UAPI headers. A compile-time
  assertion verifies the recorded UAPI policy value; project sources do not
  define a fallback numeric policy.
- `Makefile` adds `check-sched-uapi`, which compiles a source that includes the
  shared UAPI header against those matching headers.
- `SCX_OPS_SWITCH_PARTIAL` remains unchanged in
  `src/llama_scx_simple.bpf.c`. Scheduler queues, CPU selection, dispatch
  order, and slices are unchanged. Ordinary `SCHED_NORMAL`, `SCHED_BATCH`, and
  `SCHED_IDLE` tasks remain under the Linux fair scheduler; only the forked,
  explicitly selected child can request `SCHED_EXT`.

### Non-privileged tests

- `make check` runs the existing sched_ext ABI guard and matching-UAPI check,
  then executes finite `cpu_burn --seconds 1`.
- `tests/test_scx_child.sh` uses `timeout` and temporary fake state files only
  with launcher `--dry-run`; dry run never calls `sched_setattr`.
- The script covers argument parsing, disabled-state handling, invalid
  state-file override handling, child exit propagation (`23`), PID/policy
  output, and finite child workload execution.

### Manual checkpoint

Follow `docs/MANUAL_SELECTED_CHILD.md` exactly. It documents the disabled
precondition, foreground loader start, finite selected-child launch, `/proc`
policy inspection for the child and protected processes, child wait, Ctrl+C
unload, and disabled-state confirmation.

Known issue: the selected-child manual test has not been run by the agent and
requires explicit user approval for the documented load commands. Preserve
loader output, verifier errors, and scheduler exit dumps when performing it.

### Final build result

Commands run without sudo:

```text
make clean
make -j"$(nproc)"
make check
```

All targets built successfully. `make check` passed the sched_ext ABI guard,
matching-UAPI compilation check, finite one-second workload, and timeout-based
selected-child dry-run script. The final read-only sched_ext state is `disabled`.

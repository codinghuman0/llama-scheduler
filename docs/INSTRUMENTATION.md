# Bounded sched_ext instrumentation

The instrumentation is observational. It does not change `llama_simple` CPU
selection, idle or previous-CPU preference, DSQ choice, queue order, virtual
time, task weight, slice, preemption, or wake-up behavior. It retains
`SCX_OPS_SWITCH_PARTIAL`; only explicitly selected children are managed.

The loader creates an empty output directory before attempting a BPF load. It
writes `instrumentation.json` (schema version 1) and `summary.txt` only after
the scheduler link has been destroyed. A directory collision is an error; no
existing output is overwritten.

## Metric definitions and limits

- `enqueue_count` counts calls to `llama_simple_enqueue`.
- `direct_local_insertions` counts the existing direct `SCX_DSQ_LOCAL` insert
  in `select_cpu` when the baseline's default selector reports an idle CPU.
- `shared_dsq_insertions` counts the existing shared-DSQ insert in `enqueue`,
  once per callback in either FIFO or weighted-vtime mode.
- `dispatch_callbacks` counts calls to the baseline's actual `dispatch`
  callback; it is not a synthetic dispatch-event count.
- `running_callbacks` and `stopping_callbacks` count those existing callbacks.
- Per-task runtime is the sum of intervals from `running` to the following
  `stopping`; aggregate per-CPU runtime is charged to the CPU executing that
  `stopping` callback.
- Queue wait is the interval from the latest `enqueue` timestamp recorded by the
  `enqueue` callback to the next `running` callback. A re-enqueue before running
  overwrites the earlier timestamp. Activations inserted directly into a local
  DSQ from `select_cpu` may not contribute because they do not pass through that
  enqueue timestamp. It is unavailable for capacity-untracked tasks and does
  not include time before instrumentation began.
- A migration is a change in CPU ID between successive `running` callbacks for
  one tracked task. It is charged to the CPU of the later `running` callback.
- `current_tracked_tasks` and `peak_tracked_tasks` cover successful live-map
  entries only.

The live map is a fixed `BPF_MAP_TYPE_HASH` with 1,024 entries, keyed by task
PID plus kernel `start_time`; the latter prevents PID reuse from merging two
tasks. `disable` copies the final record to a separate fixed 1,024-entry
completed map, then deletes the live entry. If a lifecycle callback is missed,
a stale entry remains bounded but can consume capacity until unload; failures
are counted. Task storage was considered but not used because its population
is not capacity-bounded. No high-frequency debug logging is enabled.

`task_lookup_failures`, `task_update_failures`, `task_capacity_failures`,
`task_cleanup_failures`, `tracking_state_lookup_failures`, and `completed_record_failures` expose incomplete or
dropped tracking. Completed records are bounded; if that map fills, live-entry
cleanup still proceeds and the final record is dropped with a counter. The
report contains completed records only; all per-task data is therefore bounded
and may be incomplete under capacity pressure. Expected overhead is one
per-CPU array lookup per instrumented callback, plus a per-task hash lookup and
short spin-lock section where task state is available.

## Manual verification

Use two terminals. The commands that load or select SCHED_EXT are manual
operator actions; the build and validation script never attach the scheduler.
Do not run the validation script with `sudo`.

1. Build:

   ```sh
   make clean
   make -j"$(nproc)"
   make check
   ```

2. Confirm the initial state:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected: `disabled`.

3. In terminal A, create the report parent, choose a new nonexistent result
   directory, and manually start the loader in the foreground after explicit
   approval:

   ```sh
   mkdir -p results/instrumentation
   run_dir="results/instrumentation/$(date -u +%Y%m%d-%H%M%S)"
   test ! -e "$run_dir"
   sudo ./build/bin/llama_scx_simple -v -o "$run_dir"
   ```

4. In terminal B, confirm the active scheduler:

   ```sh
   cat /sys/kernel/sched_ext/state
   cat /sys/kernel/sched_ext/root/ops
   ```

   Expected: `enabled` and `llama_simple`.

5. Run one finite selected CPU workload (manual selected-child action):

   ```sh
   sudo ./build/bin/llama_scx_child -- ./build/bin/cpu_burn --seconds 10
   ```

6. Run the representative mixed validation suite without sudo:

   ```sh
   ./scripts/run_validation.sh
   ```

7. In terminal A, stop only the loader with Ctrl+C.

8. Confirm rollback:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected: `disabled`.

9. Inspect the text summary:

   ```sh
   sed -n '1,200p' "$run_dir/summary.txt"
   ```

10. Validate the machine-readable report:

   ```sh
   python3 -m json.tool "$run_dir/instrumentation.json" | sed -n '1,240p'
   ```

11. Compare the validation result with the Milestone 6 baseline. The new
    `results/validation/` run must again pass all seven scenarios, and its
    result can be compared with `results/validation/20260806-132646/summary.txt`.
    Instrumentation counters are observational; a difference in scheduler
    decisions, affinity, progress, or pass/fail status is a regression.

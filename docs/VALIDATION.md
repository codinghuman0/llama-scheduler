# Baseline sched_ext validation

This is a manual checkpoint. `scripts/run_validation.sh` never loads, attaches,
stops, restarts, or unloads sched_ext. It refuses the real suite unless an
already-running scheduler reports `enabled` and its name is `llama_simple`.
Every real workload is started through `build/bin/llama_scx_child`; only the
forked launcher child requests `SCHED_EXT`. The invoking shell and launcher
parent retain their existing scheduling policies.

The runner obtains the caller's allowed CPU set with `sched_getaffinity(2)`.
It does not assume CPU IDs are contiguous and passes only subsets of that mask
to `taskset` inside the selected child. It records requested and observed
`/proc/<pid>/status` `Cpus_allowed_list` values. It uses finite workloads,
explicit per-scenario timeouts, progress lines, and a dedicated process group
for each launcher so an interrupted or timed-out scenario terminates its own
launcher child group without touching unrelated processes.

## Manual procedure

Use two terminals. Do not run the validation runner with `sudo`.

1. Build the project without loading sched_ext:

   ```sh
   make clean
   make -j"$(nproc)"
   make check
   ```

2. Confirm that sched_ext starts disabled:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected: `disabled`.

3. In terminal A, after explicit approval, start the existing loader in the
   foreground. This is the only privileged/load step and is intentionally not
   performed by the validation script:

   ```sh
   sudo ./build/bin/llama_scx_simple -v
   ```

4. In terminal B, confirm the active state and scheduler identity:

   ```sh
   cat /sys/kernel/sched_ext/state
   cat /sys/kernel/sched_ext/root/ops
   ```

   Expected: `enabled` and `llama_simple`. On the recorded 7.0.0-28 kernel, the
   active name is `/sys/kernel/sched_ext/root/ops`; the runner checks that path
   first and falls back to the documented legacy `/sys/kernel/sched_ext/name`
   only when necessary.

5. In terminal B, run the complete real validation suite without sudo:

   ```sh
   ./scripts/run_validation.sh
   ```

   It writes a new `results/validation/YYYYMMDD-HHMMSS/` directory. The suite
   covers one selected CPU-bound child, under- and over-subscription, valid
   single- and multi-CPU affinity (multi-CPU is marked degraded if only one CPU
   is allowed), mixed CPU and sleep/wake children, a deliberately missing
   executable, and a deliberately short timeout. `over_subscribed` starts
   `allowed_cpu_count + 1` children; the runner refuses rather than silently
   reducing coverage if that exceeds its explicit `--max-children` safety
   ceiling (default `256`).

6. Inspect both result forms. Substitute the directory printed by the runner:

   ```sh
   run_dir=results/validation/YYYYMMDD-HHMMSS
   sed -n '1,240p' "$run_dir/summary.txt"
   sed -n '1,240p' "$run_dir/results.jsonl"
   ```

   Each JSON Lines record includes the schema/run identity, timestamps,
   scheduler state/name, complete inherited CPU mask, child PIDs, per-child
   requested and observed affinity, exit statuses, timeout/progress results,
   log paths, and pass/fail reason. A normal scenario passes only when every
   launcher returns zero, every child reports progress, every observed affinity
   matches the requested subset, and no timeout or progress stall occurs.
   `expected_exec_failure` passes only for launcher exit `127`; `expected_timeout`
   passes only when its explicit timeout is observed and its process group is
   reaped.

7. Stop the scheduler manually in terminal A with Ctrl+C. Do not kill unrelated
   processes.

8. Confirm that the loader rolled sched_ext back to disabled:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected: `disabled`.

9. After unload, run the safe inactive-scheduler refusal check without sudo:

   ```sh
   ./scripts/run_validation.sh --check-inactive
   ```

   This refuses if sched_ext is still enabled; otherwise it does not change a policy
   or start a child and verifies the launcher
   rejects `/bin/true` before forking with exit status `1`, and writes a separate
   result directory.

## Test-only mode

`--dry-run --state-path FILE` is reserved for `make check`'s tests. It uses a
temporary fake state file and tells the selected-child launcher not to call
`sched_setattr`. It is not a substitute for the manual validation procedure.

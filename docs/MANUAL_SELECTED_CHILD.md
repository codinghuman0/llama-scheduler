# Manual selected-child SCHED_EXT test

This procedure is intentionally manual. Neither `make check` nor
`tests/test_scx_child.sh` loads or attaches the scheduler; their launcher use
is `--dry-run`, which never calls `sched_setattr`.

The launcher is `build/bin/llama_scx_child`. It checks
`/sys/kernel/sched_ext/state` before forking, then uses the matching kernel
UAPI `SCHED_EXT` definition and `struct sched_attr` only in the forked child.
It prints `parent_pid`, `parent_policy`, and `child_pid` before releasing that
child to set its policy and `execvp()` the requested command. The parent never
calls `sched_setattr` and verifies its policy again after the child exits.

Use three terminals. Do not run these commands from a systemd unit, and do not
use `--dry-run` for the real selected-child test.

1. In terminal A, confirm that the baseline starts disabled:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected output: `disabled`.

2. In terminal A, after explicit approval, start only the foreground loader:

   ```sh
   sudo ./build/bin/llama_scx_simple -v
   ```

3. In terminal B, confirm it is enabled, then launch one finite child. The
   launcher itself remains under its existing policy; only its child requests
   `SCHED_EXT`.

   ```sh
   cat /sys/kernel/sched_ext/state
   sudo ./build/bin/llama_scx_child -- ./build/bin/cpu_burn --seconds 30 > /tmp/llama-scx-child.out 2> /tmp/llama-scx-child.err &
   launcher_pid=$!
   until grep -q 'child_pid=' /tmp/llama-scx-child.out; do sleep 0.1; done
   child_pid=$(awk '{ for (i = 1; i <= NF; i++) if ($i ~ /^child_pid=/) { sub(/^child_pid=/, "", $i); print $i; exit } }' /tmp/llama-scx-child.out)
   printf 'launcher_pid=%s child_pid=%s\n' "$launcher_pid" "$child_pid"
   ```

   Expected state before launching: `enabled`. The first launcher output line
   includes `parent_policy=<original policy>` and the selected child PID.

4. In terminal C, inspect the child before its finite workload finishes:

   ```sh
   grep -E '^(policy|prio)' /proc/"$child_pid"/sched
   ```

   Expected child policy: `7` (`SCHED_EXT` from the matching 7.0.0-28 kernel
   UAPI). If the scheduler is inactive, the launcher instead reports
   `sched_ext scheduler is not active`; if the child policy change fails, it
   reports `child <pid>: cannot enter SCHED_EXT: ...` and returns exit `126`.

5. Verify that only the child is managed by sched_ext. The shell, launcher
   parent, PID 1/systemd, SSH processes, and Codex processes must not show
   policy `7`:

   ```sh
   grep -E '^(policy|prio)' /proc/"$launcher_pid"/sched /proc/$$/sched /proc/1/sched
   pgrep -x sshd | while read -r pid; do grep -E '^(policy|prio)' /proc/"$pid"/sched; done
   pgrep -f '[c]odex' | while read -r pid; do grep -E '^(policy|prio)' /proc/"$pid"/sched; done
   ```

   The launcher code scopes the only `sched_setattr` call to its post-fork
   child. It never switches all tasks, and `SCX_OPS_SWITCH_PARTIAL` keeps
   ordinary `SCHED_NORMAL`, `SCHED_BATCH`, and `SCHED_IDLE` tasks under the
   Linux fair scheduler.

6. In terminal B, wait for the finite `cpu_burn` child and preserve its logs:

   ```sh
   wait "$launcher_pid"
   launcher_status=$?
   printf 'launcher_status=%s\n' "$launcher_status"
   cat /tmp/llama-scx-child.out
   cat /tmp/llama-scx-child.err
   ```

   Expected status: `0`. `cpu_burn --seconds 30` exits after its bounded
   duration with a checksum, and the launcher propagates that child status.

7. In terminal A, stop the scheduler with Ctrl+C. Do not kill unrelated
   processes.

8. In terminal A, confirm rollback to the normal scheduler:

   ```sh
   cat /sys/kernel/sched_ext/state
   ```

   Expected output: `disabled`.

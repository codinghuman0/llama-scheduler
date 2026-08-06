#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Safe, selected-child sched_ext validation runner.

The real path requires an already-enabled scheduler.  --dry-run is reserved for
non-privileged tests and uses llama_scx_child's explicit dry-run interface.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
STATE_PATH = "/sys/kernel/sched_ext/state"
OPS_PATH = "/sys/kernel/sched_ext/root/ops"
FALLBACK_NAME_PATH = "/sys/kernel/sched_ext/name"
PROGRESS_STALL_SECONDS = 2.0
POLL_SECONDS = 0.10
REQUIRED_FIELDS = {
    "schema_version", "run_id", "test_name", "scenario_status",
    "start_timestamp", "end_timestamp", "elapsed_seconds", "timeout_seconds",
    "scheduler_state_before", "scheduler_name", "allowed_cpu_list",
    "child_count", "launcher_pids", "child_pids", "assigned_affinity",
    "exit_statuses", "timed_out", "progress_observed", "stdout_log_paths",
    "stderr_log_paths", "pass", "failure_reason",
}
ACTIVE: list["ManagedChild"] = []


def utc_timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def active_scheduler_name(ops_path: str, fallback_paths: tuple[str, ...] = (FALLBACK_NAME_PATH,)) -> str:
    """Read root/ops first; only then try documented legacy name paths."""
    diagnostics: list[str] = []
    for path in (ops_path, *fallback_paths):
        try:
            name = read_text(path)
        except OSError as error:
            diagnostics.append(f"{path}: {error.strerror or error}")
            continue
        if name:
            return name
        diagnostics.append(f"{path}: empty")
    raise RuntimeError("cannot read active sched_ext scheduler name; checked " + "; ".join(diagnostics))

def parse_cpu_list(value: str) -> list[int]:
    """Parse Linux CPU-list syntax without assuming contiguous CPU IDs."""
    if not value or not value.strip():
        raise ValueError("CPU list is empty")
    cpus: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError("CPU list contains an empty item")
        if "-" in part:
            pieces = part.split("-")
            if len(pieces) != 2 or not all(piece.isdigit() for piece in pieces):
                raise ValueError(f"invalid CPU range: {part}")
            first, last = (int(piece) for piece in pieces)
            if first > last:
                raise ValueError(f"descending CPU range: {part}")
            cpus.update(range(first, last + 1))
        elif part.isdigit():
            cpus.add(int(part))
        else:
            raise ValueError(f"invalid CPU ID: {part}")
    return sorted(cpus)


def format_cpu_list(cpus: Iterable[int]) -> str:
    values = sorted(set(cpus))
    if not values:
        raise ValueError("CPU set is empty")
    ranges: list[str] = []
    start = previous = values[0]
    for cpu in values[1:]:
        if cpu == previous + 1:
            previous = cpu
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = cpu
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def allowed_cpus() -> list[int]:
    cpus = sorted(os.sched_getaffinity(0))
    if not cpus:
        raise RuntimeError("inherited allowed CPU mask is empty")
    return cpus


def proc_allowed_list(pid: int) -> str | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("Cpus_allowed_list:"):
                return line.split(":", 1)[1].strip()
    except FileNotFoundError:
        return None
    return None


def validate_record(record: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(record)
    if missing:
        raise ValueError("result record missing fields: " + ", ".join(sorted(missing)))
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported result schema")
    if not isinstance(record["pass"], bool):
        raise ValueError("result pass must be a boolean")


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    validate_record(record)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"empty JSON Lines record at line {line_number}")
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"malformed JSON Lines record at line {line_number}: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"JSON Lines record {line_number} is not an object")
        validate_record(record)
        records.append(record)
    return records


def aggregate(records: list[dict[str, Any]]) -> tuple[int, int]:
    return sum(bool(record["pass"]) for record in records), len(records)


@dataclass
class ManagedChild:
    label: str
    assigned: list[int]
    launcher: subprocess.Popen[bytes]
    stdout_path: Path
    stderr_path: Path
    started: float
    child_pid: int | None = None
    observed_affinity: str | None = None
    progress: bool = False
    last_progress: float | None = None
    terminated: bool = False
    output_offset: int = 0

    def update_observations(self) -> None:
        try:
            with self.stdout_path.open("rb") as output:
                output.seek(self.output_offset)
                chunk = output.read()
                self.output_offset += len(chunk)
        except FileNotFoundError:
            chunk = b""
        if chunk:
            text = chunk.decode("utf-8", errors="replace")
            match = re.search(r"child_pid=(\d+)", text)
            if match:
                self.child_pid = int(match.group(1))
            if "progress workload=" in text:
                self.progress = True
                self.last_progress = time.monotonic()
        if self.child_pid is not None:
            observed = proc_allowed_list(self.child_pid)
            if observed is not None:
                self.observed_affinity = observed


def terminate_group(child: ManagedChild) -> None:
    if child.launcher.poll() is not None:
        return
    try:
        os.killpg(child.launcher.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        child.launcher.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(child.launcher.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.launcher.wait(timeout=1.0)
    child.terminated = True


def cleanup_active() -> None:
    while ACTIVE:
        terminate_group(ACTIVE.pop())


def launch_child(args: argparse.Namespace, run_dir: Path, label: str,
                 affinity: list[int], command: list[str]) -> ManagedChild:
    affinity_text = format_cpu_list(affinity)
    command_line = [str(args.launcher)]
    if args.dry_run:
        command_line += ["--dry-run", "--state-path", args.state_path]
    command_line += ["--", "taskset", "-c", affinity_text] + command
    stdout_path = run_dir / f"{label}.stdout.log"
    stderr_path = run_dir / f"{label}.stderr.log"
    stdout = stdout_path.open("wb")
    stderr = stderr_path.open("wb")
    try:
        launcher = subprocess.Popen(command_line, stdout=stdout, stderr=stderr,
                                    start_new_session=True)
    finally:
        stdout.close()
        stderr.close()
    managed = ManagedChild(label, affinity, launcher, stdout_path, stderr_path,
                           time.monotonic())
    ACTIVE.append(managed)
    return managed


def run_children(args: argparse.Namespace, run_dir: Path,
                 definitions: list[tuple[str, list[int], list[str]]],
                 timeout_seconds: float, require_progress: bool) -> tuple[list[ManagedChild], bool, str | None]:
    children = [launch_child(args, run_dir, label, affinity, command)
                for label, affinity, command in definitions]
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    reason: str | None = None
    try:
        while any(child.launcher.poll() is None for child in children):
            now = time.monotonic()
            for child in children:
                child.update_observations()
                if require_progress and child.launcher.poll() is None:
                    last = child.last_progress or child.started
                    if now - last > PROGRESS_STALL_SECONDS:
                        reason = f"{child.label} had no observable progress for {PROGRESS_STALL_SECONDS:.1f}s"
                        return children, False, reason
            if now >= deadline:
                timed_out = True
                reason = f"explicit timeout of {timeout_seconds:.1f}s reached"
                return children, timed_out, reason
            time.sleep(POLL_SECONDS)
        for child in children:
            child.update_observations()
        return children, timed_out, reason
    finally:
        if reason is not None or timed_out:
            for child in children:
                terminate_group(child)
        for child in children:
            if child in ACTIVE:
                ACTIVE.remove(child)


def base_record(args: argparse.Namespace, run_id: str, name: str,
                allowed: list[int], start: str, started: float,
                timeout_seconds: float, scheduler_state: str,
                scheduler_name: str | None, children: list[ManagedChild],
                timed_out: bool, passed: bool, reason: str | None,
                scenario_status: str = "pass") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "test_name": name,
        "scenario_status": scenario_status,
        "start_timestamp": start,
        "end_timestamp": utc_timestamp(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "timeout_seconds": timeout_seconds,
        "scheduler_state_before": scheduler_state,
        "scheduler_name": scheduler_name,
        "allowed_cpu_list": format_cpu_list(allowed),
        "child_count": len(children),
        "launcher_pids": [child.launcher.pid for child in children],
        "child_pids": [child.child_pid for child in children if child.child_pid is not None],
        "assigned_affinity": [{"label": child.label,
                               "requested_cpu_list": format_cpu_list(child.assigned),
                               "observed_cpu_list": child.observed_affinity}
                              for child in children],
        "exit_statuses": {child.label: child.launcher.returncode for child in children},
        "timed_out": timed_out,
        "progress_observed": {child.label: child.progress for child in children},
        "stdout_log_paths": [str(child.stdout_path) for child in children],
        "stderr_log_paths": [str(child.stderr_path) for child in children],
        "pass": passed,
        "failure_reason": reason,
    }


def normal_scenario(args: argparse.Namespace, run_dir: Path, run_id: str,
                    name: str, allowed: list[int], definitions: list[tuple[str, list[int], list[str]]],
                    degraded: str | None = None) -> dict[str, Any]:
    start, started = utc_timestamp(), time.monotonic()
    timeout_seconds = args.duration + 5.0
    children, timed_out, reason = run_children(args, run_dir, definitions,
                                               timeout_seconds, True)
    returned = all(child.launcher.returncode == 0 for child in children)
    progressed = all(child.progress for child in children)
    affinity_ok = all(child.observed_affinity == format_cpu_list(child.assigned)
                      for child in children)
    if reason is None and not returned:
        reason = "one or more launchers returned nonzero"
    if reason is None and not progressed:
        reason = "one or more children produced no observable progress"
    if reason is None and not affinity_ok:
        reason = "one or more observed affinity masks differ from requested masks"
    passed = not timed_out and reason is None and returned and progressed and affinity_ok
    return base_record(args, run_id, name, allowed, start, started, timeout_seconds,
                       args.scheduler_state, args.scheduler_name, children, timed_out,
                       passed, reason or degraded, "degraded" if degraded and passed else ("pass" if passed else "fail"))


def expected_exec_failure(args: argparse.Namespace, run_dir: Path, run_id: str,
                          allowed: list[int]) -> dict[str, Any]:
    start, started = utc_timestamp(), time.monotonic()
    timeout_seconds = 5.0
    definitions = [("missing-command", [allowed[0]], ["/definitely/not/a/llama-scheduler-command"])]
    children, timed_out, reason = run_children(args, run_dir, definitions,
                                               timeout_seconds, False)
    correct = (not timed_out and len(children) == 1 and
               children[0].launcher.returncode == 127)
    if not correct and reason is None:
        reason = "nonexistent command was not reported with launcher exit status 127"
    return base_record(args, run_id, "expected_exec_failure", allowed, start, started,
                       timeout_seconds, args.scheduler_state, args.scheduler_name,
                       children, timed_out, correct, None if correct else reason,
                       "pass" if correct else "fail")


def expected_timeout(args: argparse.Namespace, run_dir: Path, run_id: str,
                     allowed: list[int]) -> dict[str, Any]:
    start, started = utc_timestamp(), time.monotonic()
    timeout_seconds = 1.0
    definitions = [("timed-cpu", [allowed[0]], [str(args.cpu_burn), "--seconds", str(max(4, args.duration * 2))])]
    children, timed_out, reason = run_children(args, run_dir, definitions,
                                               timeout_seconds, True)
    cleaned = all(child.launcher.poll() is not None for child in children)
    passed = timed_out and cleaned
    if not passed and reason is None:
        reason = "expected timeout was not observed or process cleanup was incomplete"
    return base_record(args, run_id, "expected_timeout", allowed, start, started,
                       timeout_seconds, args.scheduler_state, args.scheduler_name,
                       children, timed_out, passed, None if passed else reason,
                       "pass" if passed else "fail")


def inactive_check(args: argparse.Namespace, run_dir: Path, run_id: str,
                   allowed: list[int]) -> dict[str, Any]:
    start, started = utc_timestamp(), time.monotonic()
    state = read_text(args.state_path)
    stdout_path, stderr_path = run_dir / "inactive.stdout.log", run_dir / "inactive.stderr.log"
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run([str(args.launcher), "--", "/bin/true"],
                                   stdout=stdout, stderr=stderr, check=False)
    error = stderr_path.read_text(encoding="utf-8", errors="replace")
    passed = state != "enabled" and completed.returncode == 1 and "not active" in error
    reason = None if passed else "launcher did not clearly refuse while sched_ext was disabled"
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id,
        "test_name": "inactive_scheduler", "scenario_status": "pass" if passed else "fail",
        "start_timestamp": start, "end_timestamp": utc_timestamp(),
        "elapsed_seconds": round(time.monotonic() - started, 3), "timeout_seconds": 5.0,
        "scheduler_state_before": state, "scheduler_name": None,
        "allowed_cpu_list": format_cpu_list(allowed), "child_count": 0,
        "launcher_pids": [], "child_pids": [], "assigned_affinity": [],
        "exit_statuses": {"launcher": completed.returncode}, "timed_out": False,
        "progress_observed": {}, "stdout_log_paths": [str(stdout_path)],
        "stderr_log_paths": [str(stderr_path)], "pass": passed,
        "failure_reason": reason,
    }


def scenarios(args: argparse.Namespace, allowed: list[int]) -> dict[str, list[tuple[str, list[int], list[str]]] | str | None]:
    duration = str(args.duration)
    cpu = str(args.cpu_burn)
    sleep_wake = str(args.sleep_wake)
    single = [("cpu-0", [allowed[0]], [cpu, "--seconds", duration])]
    under_count = max(1, len(allowed) - 1)
    under = [(f"cpu-{index}", [allowed[index % len(allowed)]], [cpu, "--seconds", duration])
             for index in range(under_count)]
    over_count = len(allowed) + 1
    if over_count > args.max_children:
        raise RuntimeError(f"over_subscribed requires {over_count} children, above --max-children={args.max_children}")
    over = [(f"cpu-{index}", [allowed[index % len(allowed)]], [cpu, "--seconds", duration])
            for index in range(over_count)]
    affinity = [("single-cpu", [allowed[0]], [cpu, "--seconds", duration])]
    affinity_degraded: str | None = None
    if len(allowed) >= 2:
        affinity.append(("multi-cpu", allowed[:2], [cpu, "--seconds", duration]))
    else:
        affinity_degraded = "degraded: only one CPU is allowed; multi-CPU affinity is unavailable"
    mixed = [("mixed-cpu", [allowed[0]], [cpu, "--seconds", duration]),
             ("mixed-sleep", [allowed[-1]], [sleep_wake, "--seconds", duration, "--interval-ms", "100"])]
    return {"single_cpu_bound": single, "under_subscribed": under,
            "over_subscribed": over, "affinity": affinity, "mixed_sleep_wake": mixed,
            "under_degraded": "degraded: only one CPU is allowed; under_subscribed ran one child" if len(allowed) == 1 else None,
            "affinity_degraded": affinity_degraded}


def write_summary(path: Path, records: list[dict[str, Any]]) -> None:
    passed, total = aggregate(records)
    lines = [f"Baseline sched_ext validation summary: {passed}/{total} scenarios passed", ""]
    for record in records:
        verdict = "PASS" if record["pass"] else "FAIL"
        lines.append(f"{verdict} {record['test_name']} ({record['scenario_status']}) "
                     f"elapsed={record['elapsed_seconds']}s children={record['child_count']}")
        if record["failure_reason"]:
            lines.append(f"  note: {record['failure_reason']}")
        lines.append(f"  allowed={record['allowed_cpu_list']} timed_out={record['timed_out']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--dry-run", action="store_true", help="test-only; never changes a child policy")
    result.add_argument("--state-path", default=STATE_PATH, help="sched_ext state file; custom path requires --dry-run")
    result.add_argument("--ops-path", default=OPS_PATH, help="sched_ext ops name file; custom path requires --dry-run")
    result.add_argument("--output-dir", type=Path, help="result directory (default: results/validation/<timestamp>)")
    result.add_argument("--launcher", type=Path, default=Path("build/bin/llama_scx_child"))
    result.add_argument("--cpu-burn", type=Path, default=Path("build/bin/cpu_burn"))
    result.add_argument("--sleep-wake", type=Path, default=Path("build/bin/sleep_wake"))
    result.add_argument("--duration", type=int, default=3, help="finite workload duration in seconds")
    result.add_argument("--max-children", type=int, default=256, help="safety ceiling for over-subscription")
    result.add_argument("--scenario", action="append", choices=("single_cpu_bound", "under_subscribed", "over_subscribed", "affinity", "mixed_sleep_wake", "expected_exec_failure", "expected_timeout"))
    result.add_argument("--check-inactive", action="store_true", help="safe post-unload launcher refusal check")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.duration <= 0 or args.max_children <= 0:
        parser().error("--duration and --max-children must be positive")
    if args.state_path != STATE_PATH and not args.dry_run:
        parser().error("--state-path is test-only and requires --dry-run")
    if args.ops_path != OPS_PATH and not args.dry_run:
        parser().error("--ops-path is test-only and requires --dry-run")
    for executable in (args.launcher, args.cpu_burn, args.sleep_wake):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            parser().error(f"missing executable: {executable}")
    allowed = allowed_cpus()
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = args.output_dir or Path("results/validation") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    args.scheduler_state = read_text(args.state_path)
    args.scheduler_name = None
    if args.scheduler_state == "enabled" and (not args.dry_run or args.ops_path != OPS_PATH):
        try:
            args.scheduler_name = active_scheduler_name(args.ops_path)
        except (OSError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 1
    if args.check_inactive:
        if args.dry_run:
            parser().error("--check-inactive is a real safe check and cannot use --dry-run")
        if args.scheduler_state == "enabled":
            print("refusing inactive-scheduler check while sched_ext is enabled; unload it manually first", file=sys.stderr)
            return 1
        records = [inactive_check(args, run_dir, run_id, allowed)]
    else:
        if args.scheduler_state != "enabled":
            print(f"refusing validation: sched_ext scheduler is not active (state: {args.scheduler_state})", file=sys.stderr)
            return 1
        if (not args.dry_run or args.ops_path != OPS_PATH) and args.scheduler_name != "llama_simple":
            print(f"refusing validation: expected scheduler name llama_simple, got {args.scheduler_name!r}", file=sys.stderr)
            return 1
        selected = args.scenario or ["single_cpu_bound", "under_subscribed", "over_subscribed", "affinity", "mixed_sleep_wake", "expected_exec_failure", "expected_timeout"]
        definitions = scenarios(args, allowed)
        records = []
        try:
            for name in selected:
                if name in ("expected_exec_failure", "expected_timeout"):
                    record = (expected_exec_failure if name == "expected_exec_failure" else expected_timeout)(args, run_dir, run_id, allowed)
                else:
                    record = normal_scenario(args, run_dir, run_id, name, allowed, definitions[name], definitions.get("under_degraded") if name == "under_subscribed" else definitions.get("affinity_degraded") if name == "affinity" else None)
                records.append(record)
                write_jsonl(run_dir / "results.jsonl", record)
        except KeyboardInterrupt:
            cleanup_active()
            raise
    if args.check_inactive:
        write_jsonl(run_dir / "results.jsonl", records[0])
    write_summary(run_dir / "summary.txt", records)
    print(f"validation results: {run_dir}")
    return 0 if all(record["pass"] for record in records) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        cleanup_active()

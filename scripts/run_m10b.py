#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Unprivileged M10B step-load experiment and CSV summary; no sched_ext access."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time

from sample_cpu_util import positive, sample, select_cpus, snapshot


def stop_child(child):
    """Signal only our new session/process group, including its worker children."""
    if child is None:
        return
    try:
        os.killpg(child.pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=3)


def interrupted(*_):
    raise KeyboardInterrupt


class Experiment:
    def __init__(self, events, log, command, baseline, stress, recovery):
        self.events, self.log, self.command = events, log, command
        self.baseline, self.stress, self.recovery = baseline, stress, recovery
        self.child = None
        self.state = "initial"
        self.deadline = 0
        self.finished = False

    def event(self, name, timestamp=None):
        timestamp = time.monotonic_ns() if timestamp is None else timestamp
        csv.writer(self.events).writerow((timestamp, name))
        self.events.flush()
        return timestamp

    def __call__(self, kind, now):
        if kind == "start":
            self.event("experiment_start", now)
            self.event("baseline_start", now)
            self.deadline = now + int(self.baseline * 1e9)
            self.state = "baseline"
        elif kind == "tick":
            if self.state == "stress" and self.child.poll() is not None and now < self.deadline:
                raise RuntimeError(f"stress-ng exited early ({self.child.returncode}); see stress-ng.log")
            if now < self.deadline:
                return False
            if self.state == "baseline":
                self.event("stress_start")  # Before launch: baseline ends here.
                self.child = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT,
                                              start_new_session=True)
                launched = self.event("stress_launched")
                self.deadline = launched + int(self.stress * 1e9)
                self.state = "stress"
            elif self.state == "stress":
                self.event("stress_stop_requested")
                stop_child(self.child)
                if self.child.returncode != 0:
                    raise RuntimeError(f"stress-ng failed ({self.child.returncode}); see stress-ng.log")
                self.child = None
                stopped = self.event("stress_stop")
                self.deadline = stopped + int(self.recovery * 1e9)
                self.state = "recovery"
            elif self.state == "recovery":
                self.event("recovery_end", now)
                self.finished = True
                return True
        elif kind == "end":
            if not self.finished:
                raise RuntimeError("experiment exceeded its duration allowance")
            self.event("experiment_end", now)
        return False


def summarize(directory: Path):
    with (directory / "events.csv").open(newline="") as stream:
        events = {row["event"]: int(row["monotonic_ns"]) for row in csv.DictReader(stream)}
    required = ("baseline_start", "stress_start", "stress_launched", "stress_stop_requested",
                "stress_stop", "recovery_end", "experiment_end")
    if any(key not in events for key in required) or "experiment_aborted" in events:
        raise ValueError("incomplete/aborted experiment; inspect events.csv and stress-ng.log")
    windows = {
        "baseline": (events["baseline_start"], events["stress_start"]),
        "stress": (events["stress_launched"], events["stress_stop_requested"]),
        "recovery": (events["stress_stop"], events["recovery_end"]),
    }
    groups = {}
    excluded = 0
    with (directory / "samples.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            cpu = int(row["cpu"])
            for phase in windows:
                groups.setdefault((cpu, phase), [0, 0, 0, 0.0])
            end = int(row["monotonic_ns"])
            duration = int(row["interval_ns"])
            phase = next((name for name, (a, b) in windows.items()
                          if a <= end-duration and end <= b), None)
            if phase is None:
                excluded += 1
                continue
            stats = groups[cpu, phase]
            if row["valid"] != "1":
                stats[1] += 1
            else:
                stats[0] += 1
                stats[2] += duration
                stats[3] += float(row["util_percent"]) * duration
    with (directory / "summary.csv").open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("cpu", "period", "valid_samples", "invalid_samples", "covered_ms",
                         "mean_util_percent"))
        for (cpu, phase), (valid, invalid, duration, weighted) in sorted(groups.items()):
            writer.writerow((cpu, phase, valid, invalid, f"{duration/1e6:.6f}",
                             f"{weighted/duration:.6f}" if duration else ""))
    print(f"Summary: {directory / 'summary.csv'} ({excluded} transition rows excluded)")


def run(args):
    stress_ng = shutil.which("stress-ng")
    if not stress_ng:
        raise ValueError("stress-ng is not installed")
    if os.sched_getscheduler(0) != os.SCHED_OTHER:
        raise ValueError("run from a normal SCHED_OTHER shell")
    _, _, counters = snapshot()
    cpus = select_cpus(args.stress_cpus, counters)
    if not set(cpus) <= os.sched_getaffinity(0):
        raise ValueError("stress CPUs are outside the caller's allowed affinity")
    command = [stress_ng, "--cpu", str(len(cpus)), "--cpu-load", "100", "--taskset",
               ",".join(map(str, cpus)), "--sched", "other", "--timeout", f"{args.stress + 5:g}s"]
    # Timeout is a fallback; the controller requests stop at the measured stress deadline.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    metadata = {"kernel": platform.release(), "stress_cpus": cpus,
                "sample_cpus": "all", "allowed_cpus": sorted(os.sched_getaffinity(0)),
                "clock": "time.monotonic_ns / CLOCK_MONOTONIC", "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
                "interval_ms": args.interval_ms, "baseline_s": args.baseline,
                "stress_s": args.stress, "recovery_s": args.recovery, "command": command,
                "stress_ng_version": subprocess.check_output([stress_ng, "--version"], text=True).strip()}
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("Command:", " ".join(command), flush=True)
    with (args.output_dir / "events.csv").open("x", newline="") as events, \
            (args.output_dir / "stress-ng.log").open("x") as log:
        csv.writer(events).writerow(("monotonic_ns", "event"))
        experiment = Experiment(events, log, command, args.baseline, args.stress, args.recovery)
        old_handler = signal.signal(signal.SIGTERM, interrupted)
        try:
            sample(args.output_dir / "samples.csv", interval_ms=args.interval_ms,
                   duration=args.baseline + args.stress + args.recovery + 10,
                   observer=experiment)
        except BaseException:
            experiment.event("experiment_aborted")
            raise
        finally:
            # A second Ctrl+C must not interrupt cleanup of our process group.
            old_int = signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            try:
                stop_child(experiment.child)
            finally:
                signal.signal(signal.SIGINT, old_int)
                signal.signal(signal.SIGTERM, old_handler)
    summarize(args.output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    run_parser = modes.add_parser("run", help="10 s baseline / 20 s stress / 10 s recovery")
    run_parser.add_argument("--stress-cpus", required=True, help="comma-separated CPU IDs")
    run_parser.add_argument("--output-dir", required=True, type=Path, help="new directory")
    run_parser.add_argument("--interval-ms", type=positive, default=100.0)
    for name, default in (("baseline", 10.0), ("stress", 20.0), ("recovery", 10.0)):
        run_parser.add_argument(f"--{name}", type=positive, default=default, help="seconds")
    summary_parser = modes.add_parser("summarize", help="summarize a completed run")
    summary_parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    try:
        run(args) if args.mode == "run" else summarize(args.output_dir)
    except KeyboardInterrupt:
        print("interrupted; own stress-ng group cleaned up, partial evidence preserved", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, csv.Error, RuntimeError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

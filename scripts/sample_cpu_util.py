#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""M10B: total observed per-CPU utilization, with no scheduler integration."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys
import time

FIELDS = (
    "sample_index", "monotonic_ns", "elapsed_ms", "interval_ns", "read_duration_ns",
    "cpu", "util_percent", "delta_total_ticks", "delta_idle_ticks", "valid", "reason",
)


def positive(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0.000001:
        raise argparse.ArgumentTypeError("must be finite and >= 0.000001")
    return number


def parse_stat(text: str) -> dict[int, tuple[int, ...]]:
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if not fields or not fields[0].startswith("cpu") or not fields[0][3:].isdigit():
            continue
        values = tuple(map(int, fields[1:]))
        if len(values) < 4 or any(value < 0 for value in values):
            raise ValueError(f"malformed /proc/stat line: {fields[0]}")
        cpu = int(fields[0][3:])
        if cpu in result:
            raise ValueError(f"duplicate CPU {cpu}")
        # user nice system idle iowait irq softirq steal; guest/guest_nice
        # are already included in user/nice. Never add fields 9 and 10 again.
        result[cpu] = (values + (0,) * 8)[:8]
    if not result:
        raise ValueError("no per-CPU counters in /proc/stat")
    return result


def snapshot():
    before = time.monotonic_ns()
    raw = Path("/proc/stat").read_text(encoding="ascii")
    after = time.monotonic_ns()
    return (before + after) // 2, after - before, parse_stat(raw)


def select_cpus(selection: str, present) -> list[int]:
    if selection == "all":
        return sorted(present)
    parts = selection.split(",")
    if not parts or any(not part.strip().isdigit() for part in parts):
        raise ValueError("CPUs must be 'all' or comma-separated nonnegative IDs")
    cpus = sorted({int(part) for part in parts})
    missing = set(cpus) - set(present)
    if missing:
        raise ValueError(f"CPUs absent from /proc/stat: {sorted(missing)}")
    return cpus


def utilization(previous, current):
    if previous is None or current is None:
        return "", "", "", 0, "cpu_missing_or_new"
    deltas = [b - a for a, b in zip(previous, current)]
    total = sum(deltas)
    idle = deltas[3] + deltas[4]
    reason = "counter_regression" if any(d < 0 for d in deltas) else ""
    if not reason and total <= 0:
        reason = "nonpositive_total"
    if reason:
        return "", total, idle, 0, reason
    return f"{100.0 * (total - idle) / total:.6f}", total, idle, 1, ""


def sample(output: Path, cpus="all", interval_ms=100.0, duration=40.0,
           observer=None):
    """observer receives start/tick/end timestamps; True from tick ends the run."""
    interval = int(interval_ms * 1_000_000)
    if interval <= 0 or not math.isfinite(duration) or duration <= 0:
        raise ValueError("interval and duration must be positive")
    previous_ns, _, previous = snapshot()
    selected = select_cpus(cpus, previous)
    origin = previous_ns
    end = origin + int(duration * 1_000_000_000)
    deadline = origin + interval
    with output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(FIELDS)
        stream.flush()
        if observer:
            observer("start", origin)
        index = 0
        while True:
            target = min(deadline, end)
            while (remaining := target - time.monotonic_ns()) > 0:
                time.sleep(remaining / 1_000_000_000)
            now, read_duration, current = snapshot()
            index += 1
            # All means CPUs visible in each snapshot, including hotplug changes.
            active = sorted(previous.keys() | current.keys()) if cpus == "all" else selected
            for cpu in active:
                writer.writerow((index, now, f"{(now-origin)/1_000_000:.6f}",
                                 now-previous_ns, read_duration, cpu,
                                 *utilization(previous.get(cpu), current.get(cpu))))
            stream.flush()
            finished = observer("tick", now) if observer else False
            if finished or now >= end:
                break
            previous_ns, previous = now, current
            # Absolute deadlines; skip missed slots instead of emitting catch-up bursts.
            deadline = origin + ((time.monotonic_ns()-origin)//interval + 1)*interval
        if observer:
            observer("end", now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-ms", type=positive, default=100.0)
    parser.add_argument("--duration", type=positive, default=40.0, help="seconds")
    parser.add_argument("--cpus", default="all", help="all or comma-separated CPU IDs")
    parser.add_argument("--output", required=True, type=Path, help="new CSV file; never overwrite")
    args = parser.parse_args()
    try:
        sample(args.output, args.cpus, args.interval_ms, args.duration)
    except KeyboardInterrupt:
        print("interrupted; completed CSV rows preserved", file=sys.stderr)
        return 130
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Non-privileged counter/interval and own-child cleanup checks for M10B."""
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sample_cpu_util as sampler
import run_m10b as runner


class M10BTests(unittest.TestCase):
    def test_guest_fields_are_not_added(self):
        a = sampler.parse_stat("cpu 0 0 0 0\ncpu2 100 20 30 200 10 5 5 0 80 10")
        b = sampler.parse_stat("cpu2 110 22 33 210 12 6 7 0 90 12")
        percent, total, idle, valid, _ = sampler.utilization(a[2], b[2])
        self.assertEqual((total, idle, valid), (30, 12, 1))
        self.assertEqual(float(percent), 60)

    def test_pathological_counters(self):
        a = (10,) * 8
        self.assertEqual(sampler.utilization(a, a)[3:], (0, "nonpositive_total"))
        # iowait can decrease even when aggregate idle and total increase.
        b = (20, 10, 10, 20, 9, 10, 10, 10)
        self.assertEqual(sampler.utilization(a, b)[3:], (0, "counter_regression"))
        self.assertEqual(sampler.utilization(None, a)[3], 0)
        self.assertEqual(sampler.utilization(a, None)[3], 0)

    def test_parser_and_cpu_selection(self):
        self.assertEqual(sampler.parse_stat("cpu4 1 2 3 4")[4], (1, 2, 3, 4, 0, 0, 0, 0))
        for text in ("", "cpu1 1 2", "cpu1 1 2 3 -1", "cpu1 x 2 3 4"):
            with self.assertRaises(ValueError):
                sampler.parse_stat(text)
        self.assertEqual(sampler.select_cpus("all", {2, 4}), [2, 4])
        self.assertEqual(sampler.select_cpus("4,2,2", {2, 4}), [2, 4])
        for selection in ("", "2,,4", "-1", "3", "2-4"):
            with self.assertRaises(ValueError):
                sampler.select_cpus(selection, {2, 4})

    def test_actual_intervals_and_no_catchup_burst(self):
        now = [0]
        def sleep(seconds):
            now[0] += int(seconds * 1e9) + 150_000_000
        def snapshot():
            return now[0], 10, {2: (now[0]//1_000_000, 0, 0, 100, 0, 0, 0, 0)}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "sample.csv"
            with patch.object(sampler, "snapshot", snapshot), \
                    patch.object(sampler.time, "monotonic_ns", lambda: now[0]), \
                    patch.object(sampler.time, "sleep", sleep):
                sampler.sample(output, duration=0.5)
            with output.open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([int(r["monotonic_ns"]) for r in rows], [250_000_000, 450_000_000, 650_000_000])
            self.assertEqual([int(r["interval_ns"]) for r in rows], [250_000_000, 200_000_000, 200_000_000])
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                sampler.sample(output, duration=0.01)
            self.assertEqual(output.read_bytes(), before)

    def test_summary_excludes_transition_and_invalid_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.csv").write_text(
                "monotonic_ns,event\n0,baseline_start\n100,stress_start\n110,stress_launched\n"
                "300,stress_stop_requested\n310,stress_stop\n500,recovery_end\n500,experiment_end\n")
            with (root / "samples.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=sampler.FIELDS)
                writer.writeheader()
                for end, duration, util, valid in ((50, 50, 10, 1), (100, 50, 30, 1),
                                                   (150, 50, 999, 1), (200, 50, 90, 1),
                                                   (250, 50, "", 0), (400, 50, 20, 1)):
                    writer.writerow(dict(cpu=2, monotonic_ns=end, interval_ns=duration,
                                         util_percent=util, valid=valid))
            runner.summarize(root)
            with (root / "summary.csv").open() as stream:
                rows = {r["period"]: r for r in csv.DictReader(stream)}
            self.assertEqual(float(rows["baseline"]["mean_util_percent"]), 20)
            self.assertEqual(float(rows["stress"]["mean_util_percent"]), 90)
            self.assertEqual(rows["stress"]["invalid_samples"], "1")

    def test_own_child_cleanup_leaves_unrelated_process_alive(self):
        code = "import signal,time; signal.signal(signal.SIGINT, lambda *_: exit(0)); print('ready',flush=True); time.sleep(30)"
        unrelated = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, start_new_session=True)
        child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, start_new_session=True)
        try:
            unrelated.stdout.readline()
            child.stdout.readline()
            runner.stop_child(child)
            self.assertEqual(child.returncode, 0)
            self.assertIsNone(unrelated.poll())
        finally:
            runner.stop_child(child)
            runner.stop_child(unrelated)
            child.stdout.close()
            unrelated.stdout.close()

    def test_aborted_run_cannot_be_summarized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.csv").write_text("monotonic_ns,event\n0,experiment_aborted\n")
            with self.assertRaises(ValueError):
                runner.summarize(root)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Non-privileged schema and source-preservation tests for instrumentation."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("instrumentation_report", ROOT / "scripts" / "instrumentation_report.py")
assert spec and spec.loader
reporter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = reporter
spec.loader.exec_module(reporter)


class InstrumentationTests(unittest.TestCase):
    def report(self) -> dict:
        return {
            "schema_version": 1,
            "scheduler_name": "llama_simple",
            "kernel_version": "7.0.0-28-generic",
            "start_timestamp": "start",
            "end_timestamp": "end",
            "exit": {"kind": 0, "code": 0, "reason": "", "message": ""},
            "aggregate": {
                "enqueue_count": 9, "runtime_ns": 30, "queue_wait_ns": 12,
                "migration_count": 3, "task_capacity_failures": 2, "tracking_state_lookup_failures": 3,
            },
            "per_cpu": [
                {"cpu": 0, "runtime_ns": 10, "queue_wait_ns": 4, "migration_count": 1},
                {"cpu": 3, "runtime_ns": 20, "queue_wait_ns": 8, "migration_count": 2},
            ],
            "tasks": [
                {"pid": 10, "runtime_ns": 11, "queue_wait_ns": 5, "migration_count": 1},
                {"pid": 11, "runtime_ns": 19, "queue_wait_ns": 7, "migration_count": 2},
            ],
        }

    def test_schema_version_handling(self) -> None:
        report = self.report()
        self.assertEqual(reporter.parse_report_text(json.dumps(report))["schema_version"], 1)
        report["schema_version"] = 2
        with self.assertRaises(ValueError):
            reporter.parse_report_text(json.dumps(report))

    def test_empty_and_malformed_output_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            reporter.parse_report_text(" \n")
        with self.assertRaisesRegex(ValueError, "malformed"):
            reporter.parse_report_text("not-json")

    def test_valid_aggregate_and_partial_records(self) -> None:
        parsed = reporter.parse_report_text(json.dumps(self.report()))
        self.assertEqual(parsed["aggregate"]["enqueue_count"], 9)
        self.assertEqual(parsed["aggregate"]["tracking_state_lookup_failures"], 3)
        partial = reporter.parse_report_text(json.dumps({"schema_version": 1, "aggregate": {"enqueue_count": 1}}))
        self.assertEqual(partial["aggregate"]["runtime_ns"], 0)
        self.assertEqual(partial["per_cpu"], [])
        self.assertEqual(partial["tasks"], [])

    def test_invalid_records_rejected(self) -> None:
        invalid = self.report()
        invalid["aggregate"]["runtime_ns"] = -1
        with self.assertRaises(ValueError):
            reporter.parse_report_text(json.dumps(invalid))
        invalid = self.report()
        invalid["per_cpu"] = {}
        with self.assertRaises(ValueError):
            reporter.parse_report_text(json.dumps(invalid))

    def test_per_cpu_task_migration_and_queue_wait_aggregation(self) -> None:
        parsed = reporter.parse_report_text(json.dumps(self.report()))
        self.assertEqual(reporter.per_cpu_aggregate(parsed),
                         {"runtime_ns": 30, "queue_wait_ns": 12, "migration_count": 3})
        self.assertEqual(reporter.per_task_aggregate(parsed),
                         {"runtime_ns": 30, "queue_wait_ns": 12, "migration_count": 3})

    def test_dropped_statistics_accounting(self) -> None:
        parsed = reporter.parse_report_text(json.dumps(self.report()))
        self.assertEqual(reporter.dropped_statistics(parsed), 5)

    def test_output_directory_collision_handling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run"
            reporter.create_output_dir(path)
            with self.assertRaises(FileExistsError):
                reporter.create_output_dir(path)

    def test_human_summary_generation(self) -> None:
        parsed = reporter.parse_report_text(json.dumps(self.report()))
        summary = reporter.human_summary(parsed)
        self.assertIn("enqueue=9", summary)
        self.assertIn("tracking_state_lookup_failures=3", summary)
        self.assertIn("dropped_statistics=5", summary)

    def test_bounded_maps_cleanup_and_decision_paths_are_present(self) -> None:
        source = (ROOT / "src" / "llama_scx_simple.bpf.c").read_text(encoding="utf-8")
        self.assertIn("BPF_MAP_TYPE_HASH", source)
        self.assertIn("LLAMA_MAX_TRACKED_TASKS", source)
        self.assertIn("completed_task_stats", source)
        self.assertIn("track_disable(p)", source)
        self.assertIn("bpf_map_delete_elem(&live_task_stats", source)
        self.assertNotIn("BPF_MAP_TYPE_TASK_STORAGE", source)
        self.assertNotIn("BPF_MAP_TYPE_LRU_HASH", source)
        self.assertIn("scx_bpf_select_cpu_dfl", source)
        self.assertIn("scx_bpf_dsq_insert(p, SHARED_DSQ, SCX_SLICE_DFL, enq_flags)", source)
        self.assertIn("scx_bpf_dsq_insert_vtime(p, SHARED_DSQ, SCX_SLICE_DFL, vtime", source)
        self.assertIn(".flags = SCX_OPS_SWITCH_PARTIAL", source)
        loader = (ROOT / "src" / "llama_scx_simple.c").read_text(encoding="utf-8")
        self.assertIn("mkdir_new", loader)
        self.assertIn("fopen(json_path, \"wx\")", loader)


if __name__ == "__main__":
    unittest.main()

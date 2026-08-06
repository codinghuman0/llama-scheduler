#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Non-privileged unit and dry-run coverage for the validation runner."""
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if len(sys.argv) != 4:
    raise SystemExit("usage: test_validation.py LAUNCHER CPU_BURN SLEEP_WAKE")
TEST_BINARIES = tuple(map(Path, sys.argv[1:]))
sys.argv[:] = sys.argv[:1]
RUNNER_PATH = ROOT / "scripts" / "validation_runner.py"
spec = importlib.util.spec_from_file_location("validation_runner", RUNNER_PATH)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class ValidationTests(unittest.TestCase):
    launcher: Path
    cpu_burn: Path
    sleep_wake: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.launcher, cls.cpu_burn, cls.sleep_wake = TEST_BINARIES

    def minimal_record(self) -> dict:
        return {
            "schema_version": 1, "run_id": "test", "test_name": "unit",
            "scenario_status": "pass", "start_timestamp": "start", "end_timestamp": "end",
            "elapsed_seconds": 0.0, "timeout_seconds": 1.0,
            "scheduler_state_before": "enabled", "scheduler_name": "llama_simple",
            "allowed_cpu_list": "1,3-4", "child_count": 0, "launcher_pids": [],
            "child_pids": [], "assigned_affinity": [], "exit_statuses": {},
            "timed_out": False, "progress_observed": {}, "stdout_log_paths": [],
            "stderr_log_paths": [], "pass": True, "failure_reason": None,
        }

    def test_argument_parsing(self) -> None:
        parsed = runner.parser().parse_args(["--dry-run", "--scenario", "single_cpu_bound"])
        self.assertTrue(parsed.dry_run)
        self.assertEqual(parsed.scenario, ["single_cpu_bound"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runner.parser().parse_args(["--not-an-option"])

    def test_cpu_list_parsing_and_non_contiguous_handling(self) -> None:
        self.assertEqual(runner.parse_cpu_list("1,3-4,9"), [1, 3, 4, 9])
        self.assertEqual(runner.format_cpu_list([9, 1, 4, 3]), "1,3-4,9")
        for malformed in ("", "1,,2", "4-1", "x", "1-two"):
            with self.assertRaises(ValueError):
                runner.parse_cpu_list(malformed)

    def test_result_creation_jsonl_and_aggregation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            passing = self.minimal_record()
            failing = self.minimal_record() | {"test_name": "failure", "pass": False}
            runner.write_jsonl(path, passing)
            runner.write_jsonl(path, failing)
            records = runner.read_jsonl(path)
            self.assertEqual(runner.aggregate(records), (1, 2))
            self.assertEqual(json.loads(path.read_text().splitlines()[0])["schema_version"], 1)

    def test_empty_and_malformed_result_records_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text("\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.read_jsonl(path)
            path.write_text("not-json\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.read_jsonl(path)
            path.write_text(json.dumps({"schema_version": 1}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.read_jsonl(path)

    def invoke_dry_run(self, scenario: str) -> tuple[subprocess.CompletedProcess[str], list[dict], Path]:
        temporary = tempfile.TemporaryDirectory(prefix="llama-validation-test.")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        state = directory / "state"
        state.write_text("enabled\n", encoding="utf-8")
        output = directory / "output"
        command = [str(ROOT / "scripts" / "run_validation.sh"), "--dry-run",
                   "--state-path", str(state), "--output-dir", str(output),
                   "--launcher", str(self.launcher), "--cpu-burn", str(self.cpu_burn),
                   "--sleep-wake", str(self.sleep_wake), "--duration", "1", "--max-children", "1024",
                   "--scenario", scenario]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        records = runner.read_jsonl(output / "results.jsonl")
        return completed, records, output

    def invoke_ops_preflight(self, ops_name: str | None) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
        temporary = tempfile.TemporaryDirectory(prefix="llama-validation-ops-test.")
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        state = directory / "state"
        ops = directory / "ops"
        state.write_text("enabled\n", encoding="utf-8")
        if ops_name is not None:
            ops.write_text(ops_name + "\n", encoding="utf-8")
        output = directory / "output"
        completed = subprocess.run([
            str(ROOT / "scripts" / "run_validation.sh"), "--dry-run",
            "--state-path", str(state), "--ops-path", str(ops),
            "--output-dir", str(output), "--launcher", str(self.launcher),
            "--cpu-burn", str(self.cpu_burn), "--sleep-wake", str(self.sleep_wake),
            "--duration", "1", "--scenario", "expected_exec_failure",
        ], text=True, capture_output=True, check=False)
        return completed, output, ops

    def test_root_ops_name_is_accepted_in_dry_run(self) -> None:
        completed, output, _ = self.invoke_ops_preflight("llama_simple")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(runner.read_jsonl(output / "results.jsonl")[0]["pass"])

    def test_different_root_ops_name_is_rejected_in_dry_run(self) -> None:
        completed, _, _ = self.invoke_ops_preflight("another_scheduler")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("expected scheduler name llama_simple", completed.stderr)

    def test_missing_ops_path_has_clear_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / "missing-ops")
            with self.assertRaisesRegex(RuntimeError, missing):
                runner.active_scheduler_name(missing, ())

    def test_ops_path_requires_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ops = Path(directory) / "ops"
            ops.write_text("llama_simple\n", encoding="utf-8")
            completed = subprocess.run([
                str(ROOT / "scripts" / "run_validation.sh"), "--ops-path", str(ops),
                "--launcher", str(self.launcher), "--cpu-burn", str(self.cpu_burn),
                "--sleep-wake", str(self.sleep_wake),
            ], text=True, capture_output=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--ops-path is test-only and requires --dry-run", completed.stderr)

    def test_finite_cpu_progress_and_affinity_in_dry_run(self) -> None:
        completed, records, _ = self.invoke_dry_run("single_cpu_bound")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = records[0]
        self.assertTrue(record["pass"])
        self.assertTrue(record["progress_observed"]["cpu-0"])
        self.assertEqual(record["assigned_affinity"][0]["requested_cpu_list"],
                         record["assigned_affinity"][0]["observed_cpu_list"])

    def test_expected_command_failure_in_dry_run(self) -> None:
        completed, records, _ = self.invoke_dry_run("expected_exec_failure")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(records[0]["test_name"], "expected_exec_failure")
        self.assertTrue(records[0]["pass"])
        self.assertEqual(records[0]["exit_statuses"]["missing-command"], 127)

    def test_expected_timeout_and_cleanup_in_dry_run(self) -> None:
        completed, records, _ = self.invoke_dry_run("expected_timeout")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        record = records[0]
        self.assertTrue(record["pass"])
        self.assertTrue(record["timed_out"])
        for pid in record["launcher_pids"]:
            self.assertFalse(Path(f"/proc/{pid}").exists(), f"launcher {pid} was not cleaned up")

    def test_disabled_scheduler_refusal_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.write_text("disabled\n", encoding="utf-8")
            completed = subprocess.run([
                str(ROOT / "scripts" / "run_validation.sh"), "--dry-run",
                "--state-path", str(state), "--output-dir", str(Path(directory) / "output"),
                "--launcher", str(self.launcher), "--cpu-burn", str(self.cpu_burn),
                "--sleep-wake", str(self.sleep_wake), "--scenario", "single_cpu_bound",
            ], text=True, capture_output=True, check=False)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("scheduler is not active", completed.stderr)

    def test_inactive_check_refuses_while_scheduler_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory, \
             contextlib.redirect_stderr(io.StringIO()), \
             mock.patch.object(runner, "read_text", return_value="enabled"), \
             mock.patch.object(runner, "inactive_check") as inactive:
            code = runner.main(["--check-inactive", "--output-dir", str(Path(directory) / "output"),
                                "--launcher", str(self.launcher), "--cpu-burn", str(self.cpu_burn),
                                "--sleep-wake", str(self.sleep_wake)])
        self.assertEqual(code, 1)
        inactive.assert_not_called()

    def test_state_path_requires_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.write_text("enabled\n", encoding="utf-8")
            completed = subprocess.run([
                str(ROOT / "scripts" / "run_validation.sh"), "--state-path", str(state),
                "--launcher", str(self.launcher), "--cpu-burn", str(self.cpu_burn),
                "--sleep-wake", str(self.sleep_wake),
            ], text=True, capture_output=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("requires --dry-run", completed.stderr)


if __name__ == "__main__":
    unittest.main()

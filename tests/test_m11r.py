#!/usr/bin/env python3
"""Static and report-contract tests for the M11R release tooling."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase.py"
spec = importlib.util.spec_from_file_location("validate_phase", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def accepted_report(mixed: int = 0) -> dict:
    return {
        "phase_control": {"enabled": False},
        "phase_uprobe": {
            "last_target_tgid": 4242,
            "state": {"active": 0, "phase": 0, "phase_name": "UNKNOWN"},
            "counters": {
                "begin_events": 8,
                "end_events": 8,
                "begin_unknown": 0,
                "begin_prefill": 1,
                "begin_decode": 7,
                "begin_mixed": mixed,
                "abi_failures": 0,
                "user_read_failures": 0,
                "unsupported_phases": 0,
                "stale_end_events": 0,
                "map_update_failures": 0,
                "filtered_events": 0,
            },
        },
        "phase_observations": [
            {"name": "UNKNOWN", "running": 10},
            {"name": "PREFILL", "running": 2},
            {"name": "DECODE", "running": 7},
            {"name": "MIXED", "running": mixed},
        ],
    }


class ManifestTests(unittest.TestCase):
    def test_canonical_pin(self) -> None:
        manifest = validator.parse_manifest()
        self.assertEqual(
            manifest["SEMANTIC_LLAMA_REPO"],
            "https://github.com/hsju2021/llama.cpp-fork.git",
        )
        self.assertEqual(
            manifest["SEMANTIC_LLAMA_COMMIT"],
            "5219055a578fd741e029e81fefef6f3a5695086d",
        )
        self.assertEqual(manifest["VALIDATED_UBUNTU_VERSION"], "24.04")
        self.assertEqual(manifest["VALIDATED_KERNEL"], "7.0.0-29-generic")

    def test_release_scripts_consume_manifest(self) -> None:
        bootstrap = (ROOT / "scripts" / "bootstrap_ubuntu.sh").read_text()
        validation = VALIDATOR_PATH.read_text()
        self.assertIn('source "$VERSIONS_FILE"', bootstrap)
        self.assertIn("parse_manifest()", validation)
        self.assertNotIn("5219055a578fd741e029e81fefef6f3a5695086d", bootstrap)
        self.assertNotIn("5219055a578fd741e029e81fefef6f3a5695086d", validation)


class ScriptSafetyTests(unittest.TestCase):
    def test_shell_entrypoints_parse(self) -> None:
        for script in (
            ROOT / "scripts" / "bootstrap_ubuntu.sh",
            ROOT / "scripts" / "validate_phase.sh",
        ):
            result = subprocess.run(
                ["bash", "-n", str(script)], text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_privilege_boundary_and_targeted_cleanup(self) -> None:
        source = VALIDATOR_PATH.read_text()
        self.assertIn('"sudo",\n        "--",\n        str(loader_binary)', source)
        self.assertNotRegex(source, r"sudo[^\\n]*(llama_scx_child|llama-server)")
        self.assertNotIn("killall", source)
        self.assertNotIn("pkill", source)
        self.assertIn("os.kill(server_pid, signal.SIGINT)", source)
        self.assertIn("os.killpg(launcher.pid, signal.SIGKILL)", source)

    def test_workload_contract_and_evidence_paths(self) -> None:
        source = VALIDATOR_PATH.read_text()
        for text in (
            '"n_predict": 8',
            '"temperature": 0',
            '"cache_prompt": False',
            '"-ngl",',
            '"0",',
            '"-np",',
            '"1",',
            '"--no-cont-batching",',
            '"--spec-type",',
            '"none",',
            '"--no-warmup",',
            '"--no-webui",',
            '"completion.headers"',
            '"completion.json"',
            '"instrumentation.json"',
            '"environment.json"',
        ):
            self.assertIn(text, source)
        self.assertNotIn("/tmp/llama", source)

    def test_bootstrap_does_not_change_kernel_or_load_scheduler(self) -> None:
        source = (ROOT / "scripts" / "bootstrap_ubuntu.sh").read_text()
        self.assertNotRegex(source, r"apt-get[^\\n]*(linux-image|linux-generic)")
        self.assertNotIn("modprobe", source)
        self.assertNotIn("--install-deps) INSTALL_DEPS=0", source)
        self.assertIn("--install-deps) INSTALL_DEPS=1", source)


class AcceptanceContractTests(unittest.TestCase):
    def write_report(self, report: dict) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "instrumentation.json"
        path.write_text(json.dumps(report))
        return path

    def test_accepts_balanced_semantics_and_preserves_mixed(self) -> None:
        result = validator.validate_report(self.write_report(accepted_report(mixed=3)), 4242)
        self.assertEqual(result["begin_events"], 8)
        self.assertEqual(result["begin_mixed"], 3)
        self.assertEqual(result["mixed_running"], 3)
        self.assertEqual(result["final_phase"], "UNKNOWN")

    def test_rejects_each_failure_counter(self) -> None:
        for counter in validator.FAILURE_COUNTERS:
            with self.subTest(counter=counter):
                report = accepted_report()
                report["phase_uprobe"]["counters"][counter] = 1
                with self.assertRaises(validator.ValidationError):
                    validator.validate_report(self.write_report(report), 4242)

    def test_rejects_unbalanced_or_incomplete_observations(self) -> None:
        report = accepted_report()
        report["phase_uprobe"]["counters"]["end_events"] = 7
        with self.assertRaises(validator.ValidationError):
            validator.validate_report(self.write_report(report), 4242)

        report = accepted_report()
        report["phase_observations"][1]["running"] = 0
        with self.assertRaises(validator.ValidationError):
            validator.validate_report(self.write_report(report), 4242)

    def test_result_directory_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run"
            args = validator.argparse.Namespace(output_dir=target)
            self.assertEqual(validator.make_result_dir(args), target.resolve())
            with self.assertRaises(validator.ValidationError):
                validator.make_result_dir(args)


if __name__ == "__main__":
    unittest.main()

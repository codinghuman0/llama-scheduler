"""Exercise identity and configuration gates without loading a model."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runtime
import intel_experiment


class HostGuardTests(unittest.TestCase):
    def setUp(self):
        self.disk = SimpleNamespace(free=400 * 1024**2)
        self.sensors = {"coretemp:temp1_input": 85.0}
        readings = {"/sys/kernel/sched_ext/state": "disabled", "/proc/meminfo": "MemAvailable: 4000000 kB"}
        for item in (
            patch.object(intel_experiment.os, "getuid", return_value=1000),
            patch.object(intel_experiment.os, "sched_getscheduler", return_value=runtime.os.SCHED_OTHER),
            patch.object(intel_experiment.shutil, "disk_usage", return_value=self.disk),
            patch.object(intel_experiment, "text", side_effect=lambda path, *_: readings[path]),
            patch.object(intel_experiment, "temperatures", return_value=self.sensors),
        ):
            item.start()
            self.addCleanup(item.stop)

    def check(self, action="serve-bench", relaxed=True):
        runtime.guard_host(SimpleNamespace(action=action, relaxed_host_checks=relaxed))

    def test_relaxed_host_checks_do_not_read_temperature_sensors(self):
        with patch.object(intel_experiment, "temperatures", side_effect=AssertionError("Sensor read")) as sensors:
            for action in ("build", "doctor", "run", "serve-bench"):
                self.check(action)
            sensors.assert_not_called()

    def test_relaxed_disk_floor_depends_on_stage(self):
        self.disk.free = 64 * 1024**2
        for action in ("doctor", "run", "serve-bench"):
            self.check(action)
        with self.assertRaisesRegex(RuntimeError, "more than 128 MiB"):
            self.check("build")
        self.disk.free = 129 * 1024**2
        self.check("build")
        self.disk.free = 32 * 1024**2
        with self.assertRaisesRegex(RuntimeError, "more than 32 MiB"):
            self.check()

    def test_default_retains_thermal_and_disk_limits(self):
        self.disk.free = 349 * 1024**2
        with self.assertRaisesRegex(RuntimeError, "more than 350 MiB"):
            self.check(relaxed=False)
        self.disk.free = 400 * 1024**2
        self.sensors["coretemp:temp1_input"] = 90.0
        with self.assertRaisesRegex(RuntimeError, "90 C limit"):
            self.check(relaxed=False)
        self.sensors.clear()
        with self.assertRaisesRegex(RuntimeError, "sensor unavailable"):
            self.check(relaxed=False)


class ManifestTests(unittest.TestCase):
    def test_elf_gate_rejects_text_and_other_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "llama-server"
            path.write_text("#!/bin/false\n")
            with self.assertRaisesRegex(RuntimeError, "Expected x86-64 ELF"):
                runtime.elf_identity(path)
            path.write_bytes(b"\x7fELF\x02\x01" + bytes(12) + b"\xb7\x00")
            with self.assertRaisesRegex(RuntimeError, "Expected x86-64 ELF"):
                runtime.elf_identity(path)

    def test_seal_detects_stale_libggml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = {"backend": "openmp", "markers": "all"}
            runtime.save(root / "inputs.json", inputs)
            runtime.save(root / "compile_commands.json", [])
            binary = root / "bin/libggml-cpu.so"
            binary.parent.mkdir()
            binary.write_bytes(b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\x00")
            manifest = {"kind": "integration-v2", "status": "BUILD_PASS", "r_route": "semantic-prefill-reference",
                        "build_id": runtime.input_fingerprint(inputs),
                        "compile_commands_sha256": runtime.sha(root / "compile_commands.json"),
                        "artifacts": {binary.name: runtime.sha(binary)}}
            runtime.save(root / "manifest.json", manifest)
            with patch.object(runtime, "source_inputs", return_value=inputs):
                self.assertEqual(runtime.verify_build(root), manifest)
                binary.write_bytes(binary.read_bytes() + b"changed")
                with self.assertRaisesRegex(RuntimeError, "Build artifact changed"):
                    runtime.verify_build(root)
                manifest["r_route"] = "pre-R"
                runtime.save(root / "manifest.json", manifest)
                with self.assertRaisesRegex(RuntimeError, "Build source seal differs"):
                    runtime.verify_build(root)

    def test_effective_mismatch_rejects_disabled_pool(self):
        profile = {"pool": "roles", "threads": 5, "batch_threads": 6, "transport": "state",
                   "role_affinity": [[0, 2, 4, 6, 8, 10]]*2, "role_polls": [None, None],
                   "role_priorities": ["normal", "normal"]}
        with self.assertRaisesRegex(RuntimeError, "startup configuration differs"):
            runtime.verify_effective("NEWA_INTEGRATION_V2 pool=off attached=0 separate=0 transport=state generation=5 batch=6", profile)

    def test_collect_seals_both_failed_and_successful_raw_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "run"
            failure = run / "failure.json"
            runtime.save(failure, {"status": "FAILED"})
            out = root / "result.zip"
            runtime.collect_results(run, out)
            self.assertTrue(out.with_suffix(".zip.sha256").is_file())
            with runtime.zipfile.ZipFile(out) as archive:
                hashes = json.loads(archive.read("artifact-sha256.json"))
                self.assertEqual(hashes["failure.json"], runtime.sha(failure))
            (run / "model.gguf").write_bytes(b"GGUF")
            with self.assertRaisesRegex(RuntimeError, "Unexpected result artifact"):
                runtime.collect_results(run, root / "bad.zip")


if __name__ == "__main__":
    unittest.main()

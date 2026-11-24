"""Exercise identity and configuration gates without loading a model."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import runtime


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

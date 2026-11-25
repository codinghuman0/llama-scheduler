"""Exercise identity and configuration gates without loading a model."""
import argparse
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runtime
import intel_experiment
import scx


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
            for action in ("build", "build-scheduler", "prepare-scx", "doctor", "run", "serve-bench"):
                self.check(action)
            sensors.assert_not_called()

    def test_relaxed_disk_floor_applies_only_to_build(self):
        self.disk.free = 64 * 1024**2
        for action in ("build", "build-scheduler"):
            with self.assertRaisesRegex(RuntimeError, "more than 128 MiB"):
                self.check(action)
        self.disk.free = 129 * 1024**2
        self.check("build")
        with patch.object(intel_experiment.shutil, "disk_usage", side_effect=AssertionError("Disk precheck")):
            for action in ("prepare-scx", "doctor", "run", "serve-bench"):
                self.check(action)

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


class PrefillPlacementTests(unittest.TestCase):
    def setUp(self):
        with patch.object(sys, "path", [str(runtime.TOPOLOGY), *sys.path]):
            from test_hybrid import detect
        self.intel = detect()["portable_plan"]
        self.amd = detect(p=6, e=0, vendor="AuthenticAMD", hybrid=False)["portable_plan"]
        self.selected = [0, 2, 4, 6, 8, 9]

    def sample(self, mode="prefill-pcore", variant="full", amd=False):
        plan = self.amd if amd else self.intel
        cpus = plan["selected_cpus"] if amd else self.selected
        reps = scx.p_representatives(plan, cpus)
        checkpoint = {"policy": mode, "variant": variant, "p_representatives": reps,
                      "effective": {"cpus": cpus, "topology": {"portable_plan": plan}}}
        eligible = bool(reps and mode == "prefill-pcore")
        rows = [{"cpu": c, "selected": [0, 0, 0, 3], "running": int(c in cpus)}
                for c in plan["snapshot"]["possible_cpus"]]
        rows[0]["selected"][0] = int(eligible)
        running = [{"cpu": r["cpu"], "by_phase": [0, r["running"], 0, 0]} for r in rows]
        proof = {"p_representatives": reps, "attempts": [0, 2 * int(eligible), 0, 0],
                 "hits": [0, int(eligible), 0, 0], "running_starts_by_cpu": running if variant == "full" else None}
        return checkpoint, {"cpus": rows, "prefill_pcore": proof}

    def test_i5_1240p_shape_and_homogeneous_amd_wire(self):
        for plan, selected, reps in ((self.intel, self.selected, [0, 2, 4, 6]),
                                     (self.amd, self.amd["selected_cpus"], [])):
            base, metadata = scx.placement_input(plan, selected, "observe")
            self.assertEqual(len(base), 12308)
            self.assertEqual(metadata, {})
            for policy in scx.PREFILL_PAIR:
                raw, metadata = scx.placement_input(plan, selected, policy)
                self.assertEqual(raw, base + struct.pack("<I", len(reps)))
                self.assertEqual(metadata["p_representatives"], reps)
                if reps:
                    self.assertEqual(struct.unpack_from("<4I", raw, 20), tuple(reps))
        with self.assertRaisesRegex(RuntimeError, "tiers"):
            scx.placement_input(self.intel, [0, 400], "prefill-pcore")

    def test_full_distinguishes_selected_cpu_and_actual_running_cpu(self):
        cp, stats = self.sample()
        proof = scx.audit_prefill(cp, stats)
        self.assertEqual(proof["status"], "PREFILL_IDLE_PCORE_SELECTED")
        self.assertEqual(proof["hits"], [0, 1, 0, 0])
        self.assertEqual(proof["running_starts"]["all"], [0, 6, 0, 0])
        self.assertEqual(proof["running_starts"]["on_p_representatives"], [0, 4, 0, 0])
        cp, stats = self.sample(variant="lite")
        self.assertIsNone(scx.audit_prefill(cp, stats)["running_starts"])

    def test_intel_auto_profile_through_runtime_and_checkpoint_encoding(self):
        with patch.object(sys, "path", [str(runtime.TOPOLOGY), *sys.path]):
            from test_hybrid import detect
        host = detect()
        parser = argparse.ArgumentParser()
        runtime.add_configuration(parser)
        args = parser.parse_args(["--pool", "roles", "--transport", "state"])
        args.action, args.relaxed_host_checks = "prepare-scx", True
        cpuinfo = "\n\n".join(f"processor : {i}\nflags : avx avx2 fma f16c sse4_2" for i in range(16))
        with patch.object(runtime, "detect", return_value=(host, None)), patch.object(Path, "read_text", return_value=cpuinfo):
            profile = runtime.resolve(args, {"backend": "openmp", "markers": "state-only", "r_route": "semantic-prefill-reference"})
        self.assertEqual((profile["resources"], profile["threads"], profile["batch_threads"]), ("intel-fixed6", 5, 6))
        self.assertEqual(profile["cpus"], self.selected)
        _, metadata = scx.placement_input(profile["topology"]["portable_plan"], profile["cpus"], "prefill-pcore")
        self.assertEqual(metadata["p_representatives"], [0, 2, 4, 6])
        limited = detect(allowed=[1, 3, 5, 7, 8, 9])["portable_plan"]
        self.assertEqual(scx.p_representatives(limited, [1, 3, 5, 7, 8, 9]), [1, 3, 5, 7])

    def test_zero_activity_is_reported_and_lite_has_no_residence_claim(self):
        for policy, amd, status in (("neutral", False, "NEUTRAL_CONTROL"),
                                    ("prefill-pcore", True, "NEUTRAL_FALLBACK_NO_P_REPRESENTATIVES"),
                                    ("prefill-pcore", False, "NO_ELIGIBLE_WAKEUP_OBSERVED")):
            cp, stats = self.sample(policy, amd=amd)
            proof = stats["prefill_pcore"]
            proof["attempts"][1] = proof["hits"][1] = stats["cpus"][0]["selected"][0] = 0
            self.assertEqual(scx.audit_prefill(cp, stats)["status"], status)
        proof["attempts"][1] = 1
        self.assertEqual(scx.audit_prefill(cp, stats)["status"], "ATTEMPTED_NO_IDLE_HIT")

    def test_reject_wrong_phase_impossible_hits_or_foreign_pcores(self):
        for field, value in (("attempts", [0, 2, 1, 0]), ("hits", [0, 3, 0, 0]),
                             ("p_representatives", [8, 9]), ("hits", [0, 0, 0, 0])):
            cp, stats = self.sample()
            stats["prefill_pcore"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                scx.audit_prefill(cp, stats)
        for cp, stats in (self.sample("neutral"), self.sample(amd=True)):
            stats["prefill_pcore"]["attempts"][1] = 1
            with self.assertRaises(RuntimeError):
                scx.audit_prefill(cp, stats)

    def test_reject_missing_or_out_of_envelope_running_evidence(self):
        cp, stats = self.sample()
        stats["prefill_pcore"]["running_starts_by_cpu"][1]["by_phase"][1] = 1
        with self.assertRaises(RuntimeError):
            scx.audit_prefill(cp, stats)
        del stats["prefill_pcore"]["running_starts_by_cpu"]
        with self.assertRaises(RuntimeError):
            scx.audit_prefill(cp, stats)

    def test_detach_audit_checks_real_schema_and_receiver_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            checkpoint, stats = self.sample()
            checkpoint["effective"]["run_id"] = 51
            stats.update(instrumentation_mode="FULL", idle_handoff={"mode": "prefill-pcore", "attempts": [0]*4, "moved": [0]*4},
                         locality={"attempts": [0]*4, "hits": [0]*4}, live_monitor={"status": "PASS"}, events_export_error=0)
            for row in stats["cpus"]:
                row.update(mask_violations=0, tracking_failures=0, events_dropped=0)
            runtime.save(directory / "scheduler-stats.json", stats)
            runtime.save(directory / "checkpoint.json", checkpoint)
            (directory / "loader-exit.txt").write_text("0 0\n")
            state = directory / "sys-state"
            state.write_text("disabled\n")
            log = directory / "loader.log"
            receiver = "NEWA_STATE_RECEIVER run=51 sequence=7 rejected=0 idle=2 active=0 invalid=0"
            with patch.object(scx, "SCHED_EXT", state):
                log.write_text(receiver)
                self.assertEqual(runtime.verify_scx_completion(directory)["prefill_pcore"]["hits"], [0, 1, 0, 0])
                log.write_text(receiver.replace("rejected=0", "rejected=1"))
                with self.assertRaisesRegex(RuntimeError, "state-v2"):
                    runtime.verify_scx_completion(directory)

    def test_offline_pair_check_rejects_unmatched_visits_and_linux_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = [Path(tmp) / p for p in scx.PREFILL_PAIR]
            for policy, target in zip(scx.PREFILL_PAIR, targets):
                cp, stats = self.sample(policy)
                admitted = {"policy": policy, "variant": "full", "prefill_pcore": scx.audit_prefill(cp, stats)}
                runtime.save(target / "summary.json", {"status": "COHORT_PASS", "scheduler": "SCHED_EXT",
                             "kernel_state_delivery": "VALID_EVENTS_AND_IDLE_OBSERVED", "kernel_handoff": admitted, "cohorts": 1})
                runtime.save(target / "effective.json", cp["effective"])
                runtime.save(target / "launch.json", {"build": {"build_id": "abc", "artifacts": {"server": "xyz"}},
                             "model_sha256": "same-model", "visit": {"tokens": 2, "state_log": True}})
                measured = {"tokens": [[18, 19]], "elapsed_s": 1.0, "cpu_s": 5.6, "tokens_per_s": 2.0,
                            "request_timings": [{"prompt_n": 32, "prompt_ms": 900, "predicted_n": 2, "predicted_ms": 100}]}
                runtime.save(target / "cohorts.json", [{"fixture": "example", "payload": {"prompt": [[16, 17]]},
                             "warmup": {"tokens": measured["tokens"]}, "measured": measured}])
            self.assertEqual(scx.check_pair(*targets)["status"], "PAIR_SMOKE_PASS")
            for filename, change in (("effective.json", lambda data: data.update(cpus=[1, 2])),
                                     ("launch.json", lambda data: data["visit"].update(state_log=False)),
                                     ("cohorts.json", lambda data: data[0]["payload"].update(prompt=[[20, 21]])),
                                     ("cohorts.json", lambda data: data[0]["measured"]["request_timings"][0].update(predicted_ms=0)),
                                     ("summary.json", lambda data: data.update(scheduler="SCHED_OTHER"))):
                path = targets[1] / filename
                original = path.read_text()
                changed = json.loads(original)
                change(changed)
                runtime.save(path, changed)
                with self.subTest(filename=filename), self.assertRaises(RuntimeError):
                    scx.check_pair(*targets)
                path.write_text(original)

    def test_dry_run_selected_child_reaps_gracefully_on_pidfd_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            launcher, ready, state = (directory / n for n in ("launcher", "ready", "state"))
            subprocess.run(["cc", "-I" + str(scx.SCHEDULER_HEADERS), str(scx.CODE / "llama_scx_child.c"),
                            "-o", str(launcher)], check=True)
            state.write_text("enabled\n")
            script = ("import os, pathlib, signal, sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                      "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); signal.pause()")
            proc = subprocess.Popen([str(launcher), "--dry-run", "--state-path", str(state), "--",
                                     sys.executable, "-c", script, str(ready)], start_new_session=True,
                                    stdout=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 5
                while not ready.is_file() or not ready.read_text():
                    self.assertIsNone(proc.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.02)
                pid = int(ready.read_text())
                self.assertEqual(os.sched_getscheduler(pid), os.SCHED_OTHER)
                runtime.stop_registered_child(SimpleNamespace(process=proc, cleanup_timeout=5), os.pidfd_open(pid))
                self.assertEqual(proc.returncode, 0)
                self.assertFalse(Path(f"/proc/{pid}").exists())
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()

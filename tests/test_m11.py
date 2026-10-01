#!/usr/bin/env python3
import os
import re
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ROOT / ".deps" / "llama.cpp-semantic"


class SemanticPhaseAbiTests(unittest.TestCase):
    def test_translation_begin_end_and_abi(self) -> None:
        harness = r"""
#include <assert.h>
#include <stddef.h>
#include "llama_phase.h"

int main(void) {
    struct llama_scx_event_v1 event = {
        .version = 1,
        .run_id = 41,
        .call_id = 7,
        .retry = 2,
        .phase = LLAMA_SCX_PHASE_V1_MIXED,
        .profile = 0,
        .n_prefill = 3,
        .n_decode = 4,
        .n_unknown = 0,
        .result = -1,
    };
    struct llama_phase_value value = {};
    __u32 translated = 99;

    assert(sizeof(event) == 80);
    assert(offsetof(struct llama_scx_event_v1, version) == 0);
    assert(offsetof(struct llama_scx_event_v1, run_id) == 8);
    assert(offsetof(struct llama_scx_event_v1, call_id) == 16);
    assert(offsetof(struct llama_scx_event_v1, retry) == 24);
    assert(offsetof(struct llama_scx_event_v1, phase) == 32);
    assert(offsetof(struct llama_scx_event_v1, profile) == 40);
    assert(offsetof(struct llama_scx_event_v1, n_prefill) == 48);
    assert(offsetof(struct llama_scx_event_v1, n_decode) == 56);
    assert(offsetof(struct llama_scx_event_v1, n_unknown) == 64);
    assert(offsetof(struct llama_scx_event_v1, result) == 72);

    assert(llama_scx_phase_translate(0, &translated) == 0 && translated == LLAMA_PHASE_UNKNOWN);
    assert(llama_scx_phase_translate(1, &translated) == 0 && translated == LLAMA_PHASE_PREFILL);
    assert(llama_scx_phase_translate(2, &translated) == 0 && translated == LLAMA_PHASE_DECODE);
    assert(llama_scx_phase_translate(3, &translated) == 0 && translated == LLAMA_PHASE_MIXED);
    assert(llama_scx_phase_translate(4, &translated) == LLAMA_SCX_STATE_BAD_PHASE);

    assert(llama_scx_begin_value(&value, &event) == 0);
    assert(value.active == 1 && value.phase == LLAMA_PHASE_MIXED);
    assert(value.source == LLAMA_PHASE_SOURCE_UPROBE);
    assert(value.run_id == 41 && value.call_id == 7 && value.retry == 2);
    assert(value.n_prefill == 3 && value.n_decode == 4 && value.n_unknown == 0);
    assert(llama_scx_end_matches(&value, &event) == 0);

    event.call_id++;
    assert(llama_scx_end_matches(&value, &event) == LLAMA_SCX_STATE_MISMATCH);
    event.call_id--;
    event.retry++;
    assert(llama_scx_end_matches(&value, &event) == LLAMA_SCX_STATE_MISMATCH);
    event.retry--;
    event.phase = LLAMA_SCX_PHASE_V1_UNKNOWN;
    assert(llama_scx_begin_value(&value, &event) == 0);
    assert(value.active == 1 && value.phase == LLAMA_PHASE_UNKNOWN);
    assert(llama_scx_end_matches(&value, &event) == 0);
    event.result = 0;
    llama_scx_end_value(&value, &event);
    assert(value.active == 0 && value.phase == LLAMA_PHASE_UNKNOWN && value.result == 0);

    event.version = 2;
    assert(llama_scx_begin_value(&value, &event) == LLAMA_SCX_STATE_BAD_VERSION);
    assert(llama_scx_end_matches(&value, &event) == LLAMA_SCX_STATE_BAD_VERSION);
    event.version = 1;
    event.phase = 99;
    assert(llama_scx_begin_value(&value, &event) == LLAMA_SCX_STATE_BAD_PHASE);
    assert(llama_scx_end_matches(&value, &event) == LLAMA_SCX_STATE_BAD_PHASE);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "abi.c"
            binary = Path(directory) / "abi"
            source.write_text(harness)
            subprocess.run([
                os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "include"), str(source), "-o", str(binary),
            ], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True)

    def test_scheduler_abi_matches_semantic_source(self) -> None:
        marker = SEMANTIC / "tools/server/server-scx.h"
        if not marker.exists():
            self.skipTest("fixed semantic fork is not present")
        semantic = marker.read_text()
        scheduler = (ROOT / "include/llama_phase.h").read_text()
        fields = [
            "version", "run_id", "call_id", "retry", "phase", "profile",
            "n_prefill", "n_decode", "n_unknown", "result",
        ]
        semantic_struct = semantic[semantic.index("struct server_scx_event"):
                                   semantic.index("static_assert(sizeof(server_scx_event)")]
        scheduler_struct = scheduler[scheduler.index("struct llama_scx_event_v1"):
                                     scheduler.index("struct llama_phase_value")]
        for field in fields:
            self.assertRegex(semantic_struct, rf"\b{field}\s*;")
            self.assertRegex(scheduler_struct, rf"\b{field}\s*;")
        self.assertIn("sizeof(server_scx_event) == 80", semantic)
        self.assertIn("sizeof(struct llama_scx_event_v1) == 80", scheduler)


class UprobeIntegrationSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bpf = (ROOT / "src/llama_scx_simple.bpf.c").read_text()
        self.loader = (ROOT / "src/llama_scx_simple.c").read_text()
        self.child = (ROOT / "src/llama_scx_child.c").read_text()

    def test_handlers_read_translate_match_and_count_failures(self) -> None:
        self.assertGreaterEqual(self.bpf.count('SEC("uprobe")'), 2)
        self.assertIn("llama_scx_decode_begin_v1_uprobe", self.bpf)
        self.assertIn("llama_scx_decode_end_v1_uprobe", self.bpf)
        self.assertEqual(self.bpf.count("bpf_probe_read_user"), 2)
        self.assertIn("llama_scx_begin_value(&value, &event)", self.bpf)
        self.assertIn("llama_scx_end_matches(&next, &event)", self.bpf)
        self.assertIn("BPF_ANY", self.bpf)
        self.assertIn("BPF_EXIST", self.bpf)
        for counter in (
            "begin_events", "end_events", "begin_unknown", "begin_prefill",
            "begin_decode", "begin_mixed", "abi_failures", "user_read_failures",
            "unsupported_phases", "stale_end_events", "map_update_failures",
            "filtered_events",
        ):
            self.assertIn(f"UPROBE_STAT_INC({counter})", self.bpf)

    def test_pid_specific_attach_and_source_exclusion(self) -> None:
        self.assertIn("bpf_program__attach_uprobe_opts(begin_program, (pid_t)tgid", self.loader)
        self.assertIn("bpf_program__attach_uprobe_opts(end_program, (pid_t)tgid", self.loader)
        self.assertIn('.func_name = "llama_scx_decode_begin_v1"', self.loader)
        self.assertIn('.func_name = "llama_scx_decode_end_v1"', self.loader)
        self.assertIn("parent_tgid != (__u32)credentials.pid", self.loader)
        self.assertIn("credentials.uid != control->allowed_uid", self.loader)
        self.assertIn("target_uid != credentials.uid", self.loader)
        self.assertIn("policy != SCHED_EXT", self.loader)
        self.assertIn("legacy socket and semantic uprobe phase sources are mutually exclusive", self.loader)
        self.assertIn("__uint(max_entries, LLAMA_PHASE_STATE_MAX);", self.bpf)

    def test_legacy_socket_path_and_neutral_policy_remain(self) -> None:
        self.assertIn("SOCK_SEQPACKET", self.loader)
        self.assertIn("phase_control_handle_message", self.loader)
        self.assertIn("LLAMA_PHASE_SOURCE_SOCKET", self.loader)
        marker = "s32 BPF_STRUCT_OPS(llama_simple_select_cpu"
        policy = self.bpf[self.bpf.index(marker):]
        self.assertNotIn("llama_scx_event", policy)
        self.assertNotIn("phase_uprobe_config", policy)
        self.assertIn(".flags = SCX_OPS_SWITCH_PARTIAL", policy)
        self.assertIn("scx_bpf_select_cpu_dfl", policy)
        self.assertIn("scx_bpf_dsq_insert_vtime", policy)

    def test_selected_child_registration_client(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.write_text("enabled\n")
            name = f"llama-m11-child-{os.getpid()}"
            received = []
            server_error = []
            ready = threading.Event()

            def serve() -> None:
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as listener:
                        listener.bind("\0" + name)
                        listener.listen(1)
                        ready.set()
                        connection, _ = listener.accept()
                        with connection:
                            request = connection.recv(128).decode()
                            received.append(request)
                            match = re.fullmatch(r"REGISTER 1 ([1-9][0-9]*)", request)
                            if not match:
                                raise AssertionError(request)
                            connection.sendall(f"ACK 1 {match.group(1)} 0".encode())
                except BaseException as error:
                    server_error.append(error)
                    ready.set()

            thread = threading.Thread(target=serve)
            thread.start()
            self.assertTrue(ready.wait(2))
            result = subprocess.run([
                str(ROOT / "build/bin/llama_scx_child"),
                "--dry-run", "--state-path", str(state),
                "--phase-register-socket", name,
                "--", "/bin/true",
            ], text=True, capture_output=True, timeout=5)
            thread.join(2)
            self.assertFalse(thread.is_alive())
            if server_error:
                raise server_error[0]
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(received), 1)
            self.assertIn("phase_uprobe_registered_tgid=", result.stdout)
            child = re.search(r"\bchild_pid=([1-9][0-9]*)\b", result.stdout)
            registered = re.search(r"^phase_uprobe_registered_tgid=([1-9][0-9]*)$",
                                   result.stdout, re.MULTILINE)
            request = re.fullmatch(r"REGISTER 1 ([1-9][0-9]*)", received[0])
            self.assertIsNotNone(child)
            self.assertIsNotNone(registered)
            self.assertIsNotNone(request)
            self.assertEqual(child.group(1), registered.group(1))
            self.assertEqual(child.group(1), request.group(1))


class ManualRunbookPrivilegeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runbook = (ROOT / "docs/LLAMA_PHASE.md").read_text()

    def test_only_loader_is_privileged(self) -> None:
        self.assertIn('USER_UID="$(id -u)"', self.runbook)
        self.assertIn('test "$USER_UID" -ne 0', self.runbook)
        self.assertIn('sudo ./build/bin/llama_scx_simple', self.runbook)
        self.assertNotRegex(self.runbook, r"sudo\s+\./build/bin/llama_scx_child")
        self.assertIn('--phase-uid "$USER_UID"', self.runbook)
        self.assertNotIn("--phase-uid 0", self.runbook)
        self.assertIn("assert expected_uid == os.getuid() and expected_uid != 0", self.runbook)

    def test_runbook_checks_pid_uid_and_policy_isolation(self) -> None:
        for evidence in (
            "registration == server",
            "target == server",
            'items["server"]["ppid"] == launcher',
            'items["launcher"]["policy"] == os.SCHED_OTHER',
            'items["server"]["policy"] == 7',
            "all(tgid == server for tgid, tid in sched_ext_tasks)",
            'data["phase_control"]["enabled"] is False',
        ):
            self.assertIn(evidence, self.runbook)

    def test_runbook_uses_fixed_server_interface(self) -> None:
        self.assertIn("/tmp/llama-m11-validation.log", self.runbook)
        self.assertIn("http://127.0.0.1:18080/health", self.runbook)
        self.assertIn("http://127.0.0.1:18080/completion", self.runbook)
        self.assertIn('"n_predict":8', self.runbook)
        self.assertIn('"cache_prompt":false', self.runbook)
        self.assertNotIn(r"n\_predict", self.runbook)
        self.assertNotIn(r'cache\_prompt"\:false', self.runbook)

    def test_runtime_shell_blocks_parse(self) -> None:
        runtime = self.runbook.split("## Historical three-terminal runtime checkpoint", 1)[1]
        blocks = re.findall(r"^```sh\n(.*?)^```$", runtime, re.MULTILINE | re.DOTALL)
        self.assertGreaterEqual(len(blocks), 4)
        for block in blocks:
            result = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

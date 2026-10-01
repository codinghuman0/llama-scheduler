#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Non-privileged schema and source-preservation tests for instrumentation."""
from __future__ import annotations

import errno
import importlib.util
import json
import os
import re
import select
import shlex
import shutil
import signal
import socket
import subprocess
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
            "phase_control": {
                "enabled": True, "client_tgid": 0, "last_client_tgid": 42,
                "latest_phase": 2, "latest_phase_name": "DECODE", "latest_sequence": 2,
            },
            "phase_observations": [
                {"phase": 0, "name": "UNKNOWN", "select_cpu": 1, "enqueue": 2, "running": 3, "stopping": 4},
                {"phase": 1, "name": "PREFILL", "select_cpu": 5, "enqueue": 6, "running": 7, "stopping": 8},
                {"phase": 2, "name": "DECODE", "select_cpu": 9, "enqueue": 10, "running": 11, "stopping": 12},
            ],
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

    def test_phase_report_fields_are_preserved(self) -> None:
        parsed = reporter.parse_report_text(json.dumps(self.report()))
        self.assertEqual(parsed["phase_control"]["last_client_tgid"], 42)
        self.assertEqual(parsed["phase_control"]["latest_sequence"], 2)
        self.assertEqual([entry["name"] for entry in parsed["phase_observations"]],
                         ["UNKNOWN", "PREFILL", "DECODE"])

    def test_phase_maps_and_neutral_callback_observation(self) -> None:
        header = (ROOT / "include" / "llama_phase.h").read_text(encoding="utf-8")
        instrumentation = (ROOT / "include" / "llama_instrumentation.h").read_text(encoding="utf-8")
        source = (ROOT / "src" / "llama_scx_simple.bpf.c").read_text(encoding="utf-8")
        self.assertIn("LLAMA_PHASE_UNKNOWN = 0", header)
        self.assertIn("LLAMA_PHASE_PREFILL = 1", header)
        self.assertIn("LLAMA_PHASE_DECODE = 2", header)
        self.assertIn("LLAMA_PHASE_MIXED = 3", header)
        self.assertIn("struct llama_phase_value", header)
        self.assertIn("__u64 sequence;", header)
        self.assertIn("struct llama_phase_observation", instrumentation)
        self.assertIn("} phase_state SEC(\".maps\");", source)
        self.assertIn("__type(key, u32);", source)
        self.assertIn("__type(value, struct llama_phase_value);", source)
        self.assertIn("__uint(max_entries, LLAMA_PHASE_STATE_MAX);", source)
        self.assertIn("} phase_observations SEC(\".maps\");", source)
        self.assertIn("__type(value, struct llama_phase_observation);", source)
        self.assertIn("__uint(max_entries, LLAMA_PHASE_COUNT);", source)
        self.assertIn("u32 tgid = BPF_CORE_READ(p, tgid);", source)
        for name, map_type, value_type, capacity in (
            ("phase_state", "HASH", "llama_phase_value", "LLAMA_PHASE_STATE_MAX"),
            ("phase_observations", "PERCPU_ARRAY", "llama_phase_observation", "LLAMA_PHASE_COUNT"),
        ):
            declaration = source[:source.index(f'}} {name} SEC(".maps");')].rsplit("struct {", 1)[1]
            self.assertIn(f"__uint(type, BPF_MAP_TYPE_{map_type});", declaration)
            self.assertIn("__type(key, u32);", declaration)
            self.assertIn(f"__type(value, struct {value_type});", declaration)
            self.assertIn(f"__uint(max_entries, {capacity});", declaration)

        callback_names = (
            ("llama_simple_select_cpu", "select_cpu"),
            ("llama_simple_enqueue", "enqueue"),
            ("llama_simple_running", "running"),
            ("llama_simple_stopping", "stopping"),
        )
        for callback, counter in callback_names:
            start = source.index(f"BPF_STRUCT_OPS({callback}")
            next_start = source.find("BPF_STRUCT_OPS(", start + 1)
            body = source[start:next_start if next_start >= 0 else None]
            observation = f"PHASE_OBSERVE(p, {counter})"
            self.assertEqual(body.count(observation), 1)
            self.assertEqual([line.strip() for line in body.splitlines() if "PHASE" in line],
                             [observation + ";"])

        dispatch_start = source.index("BPF_STRUCT_OPS(llama_simple_dispatch")
        dispatch_end = source.index("BPF_STRUCT_OPS(llama_simple_running", dispatch_start)
        self.assertNotIn("phase", source[dispatch_start:dispatch_end].lower())
        self.assertIn(".flags = SCX_OPS_SWITCH_PARTIAL", source)

    def test_phase_control_is_unpinned_authenticated_and_ack_after_update(self) -> None:
        loader = (ROOT / "src" / "llama_scx_simple.c").read_text(encoding="utf-8")
        all_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "src").glob("*.c")
        )
        self.assertIn("AF_UNIX, SOCK_SEQPACKET", loader)
        self.assertIn("SO_PEERCRED", loader)
        self.assertIn("sched_getscheduler(credentials.pid)", loader)
        self.assertIn("policy != SCHED_EXT", loader)
        self.assertIn("poll(poll_fds", loader)
        self.assertNotIn("sleep(1)", loader)
        self.assertNotIn("bpf_obj_pin", all_source)
        self.assertNotIn("bpf_map__pin", all_source)
        handler_start = loader.index("static void phase_control_handle_message")
        handler_end = loader.index("static void iso_timestamp", handler_start)
        handler = loader[handler_start:handler_end]
        self.assertLess(handler.index("bpf_map_update_elem"),
                        handler.index("phase_control_send_ack"))

    def test_bounded_maps_cleanup_and_decision_paths_are_present(self) -> None:
        source = (ROOT / "src" / "llama_scx_simple.bpf.c").read_text(encoding="utf-8")
        self.assertIn("BPF_MAP_TYPE_HASH", source)
        self.assertIn("__type(key, struct llama_task_key);", source)
        self.assertIn("__type(value, struct llama_task_live);", source)
        self.assertIn("__type(key, u32);", source)
        self.assertIn("__type(value, struct llama_tracking_state);", source)
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

class PhaseControlTests(unittest.TestCase):
    def test_scheduling_callbacks_match_baseline(self) -> None:
        source = (ROOT / "src/llama_scx_simple.bpf.c").read_text()
        baseline = subprocess.check_output(
            ["git", "show", "25d8b3e8149e9e5d1078569d910d3e263dd86ffc:src/llama_scx_simple.bpf.c"],
            cwd=ROOT, text=True)
        marker = "s32 BPF_STRUCT_OPS(llama_simple_select_cpu"
        without_observation = re.sub(r"\tPHASE_OBSERVE\(p, \w+\);\n", "", source[source.index(marker):])
        self.assertEqual(without_observation, baseline[baseline.index(marker):])
        helper = source[source.index("static __always_inline struct llama_phase_observation *phase_observation"):
                        source.index("static __always_inline void task_key")]
        self.assertNotRegex(helper, r"scx_|dsq|vtime|slice|weight|fifo|bpf_map_(update|delete)")
        self.assertEqual(source.count("phase_observation(p)"), 1)
        self.assertEqual(helper.count("&phase_state"), 1)
        self.assertEqual(helper.count("&phase_observations"), 1)

    def test_loader_protocol_and_client_lifetime(self) -> None:
        # Real unprivileged sockets; map writes and policy queries are mocked.
        harness = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <sched.h>
#include <unistd.h>
#include <bpf/bpf.h>
#include "llama_instrumentation.h"
static int updates, deletes, update_error, policy = 7;
static __u32 expected_tgid;
static struct llama_phase_value stored;
static int fake_update(int fd, const void *key, const void *value, __u64 flags) {
    assert(fd == 123 && flags == BPF_ANY && *(__u32 *)key == expected_tgid);
    updates++;
    if (update_error) { errno = update_error; return -1; }
    stored = *(const struct llama_phase_value *)value;
    return 0;
}
static int fake_delete(int fd, const void *key) {
    assert(fd == 123 && *(__u32 *)key == expected_tgid);
    deletes++;
    stored.phase = LLAMA_PHASE_UNKNOWN;
    return 0;
}
static int fake_policy(pid_t pid) { assert(pid == getpid()); return policy; }
#define bpf_map_update_elem fake_update
#define bpf_map_delete_elem fake_delete
#define sched_getscheduler fake_policy
#define main loader_main
#include "src/llama_scx_simple.c"
#undef main
static int connect_client(const char *name) {
    struct sockaddr_un address = { .sun_family = AF_UNIX };
    int fd = socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0);
    assert(fd >= 0);
    memcpy(address.sun_path + 1, name, strlen(name));
    assert(!connect(fd, (struct sockaddr *)&address,
                    offsetof(struct sockaddr_un, sun_path) + 1 + strlen(name)));
    return fd;
}
static void exchange(struct phase_control *c, int peer, const char *request,
                     size_t length, const char *ack) {
    char response[128] = {};
    assert(send(peer, request, length, MSG_NOSIGNAL) == (ssize_t)length);
    phase_control_handle_message(c, 123);
    assert(recv(peer, response, sizeof(response), MSG_DONTWAIT) == (ssize_t)strlen(ack));
    assert(!memcmp(response, ack, strlen(ack)));
}
int main(int argc, char **argv) {
    struct phase_control c;
    struct phase_uprobe_control u;
    char name[80];
    assert(argc == 2);
    _Static_assert(sizeof(struct llama_phase_value) == 80, "phase map ABI");
    _Static_assert(sizeof(struct llama_phase_observation) == 32, "observation map ABI");
    snprintf(name, sizeof(name), "llama-phase-test-%d", getpid());
    phase_control_init(&c);
    phase_uprobe_init(&u);
    assert(!phase_control_open(&c, name, getuid() + 1));
    int peer = connect_client(name);
    phase_control_accept(&c);
    assert(c.client_fd == -1); /* Wrong UID. */
    close(peer);
    c.allowed_uid = getuid();
    policy = SCHED_NORMAL;
    peer = connect_client(name);
    phase_control_accept(&c);
    assert(c.client_fd == -1); /* Ordinary process rejected. */
    close(peer);
    policy = SCHED_EXT;
    peer = connect_client(name);
    phase_control_accept(&c);
    expected_tgid = getpid();
    assert(c.client_tgid == expected_tgid && c.latest_phase == LLAMA_PHASE_UNKNOWN);
    int registered_fd = c.client_fd;
    int extra = connect_client(name);
    phase_control_accept(&c);
    assert(c.client_fd == registered_fd);
    close(extra);
    exchange(&c, peer, "PHASE 1 1 1", 11, "ACK 1 1 0");
    assert(updates == 1 && stored.phase == LLAMA_PHASE_PREFILL && stored.active == 1 &&
           stored.source == LLAMA_PHASE_SOURCE_SOCKET && stored.reserved == 0);
    assert(c.latest_phase == stored.phase && c.latest_sequence == stored.sequence);
    exchange(&c, peer, "PHASE 1 1 2", 11, "ACK 1 1 -71"); /* Duplicate sequence. */
    exchange(&c, peer, "PHASE 2 2 2", 11, "ACK 1 0 -71"); /* Wrong version. */
    exchange(&c, peer, "PHASE 1 2 0", 11, "ACK 1 2 -22"); /* UNKNOWN is not a request. */
    exchange(&c, peer, "PHASE 1 2 2\0x", 13, "ACK 1 2 -71");
    exchange(&c, peer, "PHASE 1 2 2 x", 13, "ACK 1 2 -71");
    exchange(&c, peer, "PHASE 1 -1 2", 12, "ACK 1 0 -71");
    const char *overflow = "PHASE 1 18446744073709551616 2";
    exchange(&c, peer, overflow, strlen(overflow), "ACK 1 18446744073709551615 -71");
    char oversized[160];
    memset(oversized, 'x', sizeof(oversized));
    exchange(&c, peer, oversized, sizeof(oversized), "ACK 1 0 -90");
    assert(updates == 1);
    update_error = EIO;
    exchange(&c, peer, "PHASE 1 2 2", 11, "ACK 1 2 -5");
    assert(c.latest_sequence == 1 && stored.phase == LLAMA_PHASE_PREFILL);
    update_error = 0;
    exchange(&c, peer, "PHASE 1 2 2", 11, "ACK 1 2 0");
    assert(c.latest_sequence == 2 && stored.phase == LLAMA_PHASE_DECODE);
    close(peer);
    phase_control_handle_message(&c, 123);
    assert(deletes == 1 && c.client_fd == -1 && c.client_tgid == 0);
    assert(stored.phase == LLAMA_PHASE_UNKNOWN && c.latest_sequence == 2);
    struct runtime_data exit_data = {};
    assert(!write_report(argv[1], "start", "end", NULL, NULL, NULL, NULL, NULL, NULL,
                         &c, &u, &exit_data));
    peer = connect_client(name);
    phase_control_accept(&c);
    assert(c.client_fd >= 0 && c.latest_sequence == 0);
    assert(send(peer, "PHASE 1 1 1", 11, MSG_NOSIGNAL) == 11);
    assert(!shutdown(peer, SHUT_RD)); /* ACK send failure must delete the updated map entry. */
    phase_control_handle_message(&c, 123);
    assert(c.client_fd == -1 && stored.phase == LLAMA_PHASE_UNKNOWN);
    close(peer);
    phase_control_close(&c, 123);
    assert(deletes == 2 && c.listener_fd == -1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "loader.c"
            binary = Path(directory) / "loader"
            source.write_text(harness)
            subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT), "-I", str(ROOT / "include"),
                str(source), "-o", str(binary), "-lbpf", "-lelf", "-lz"], check=True, capture_output=True)
            result = subprocess.run([str(binary), directory], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = reporter.parse_report_text((Path(directory) / "instrumentation.json").read_text())
            self.assertEqual(report["phase_control"]["client_tgid"], 0)
            self.assertEqual(report["phase_control"]["latest_sequence"], 2)
            self.assertEqual(report["phase_control"]["latest_phase_name"], "DECODE")
            self.assertEqual([entry["name"] for entry in report["phase_observations"]],
                             ["UNKNOWN", "PREFILL", "DECODE", "MIXED"])
            self.assertEqual(report["phase_uprobe"]["counters"]["begin_events"], 0)
            summary = (Path(directory) / "summary.txt").read_text()
            for name in ("UNKNOWN", "PREFILL", "DECODE", "MIXED"):
                self.assertIn(f"phase={name} select_cpu=0 enqueue=0 running=0 stopping=0", summary)

    def test_listener_address_errors_visibility_and_cleanup(self) -> None:
        # Exercise the actual listener with real sockets and injected syscall failures.
        harness = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
static int failure, opened_fd = -1, socket_calls;
static const char *expected_name;
static int test_socket(int domain, int type, int protocol) {
    assert(domain == AF_UNIX && type == (SOCK_SEQPACKET | SOCK_CLOEXEC | SOCK_NONBLOCK));
    assert(protocol == 0);
    socket_calls++;
    if (failure == 1) { errno = EMFILE; return -1; }
    return opened_fd = socket(domain, type, protocol);
}
static int test_bind(int fd, const struct sockaddr *address, socklen_t length) {
    const struct sockaddr_un *un = (const struct sockaddr_un *)address;
    assert(length == offsetof(struct sockaddr_un, sun_path) + 1 + strlen(expected_name));
    assert(un->sun_family == AF_UNIX && un->sun_path[0] == '\0');
    assert(un->sun_path[1] != '@');
    assert(!memcmp(un->sun_path + 1, expected_name, strlen(expected_name)));
    if (failure == 2) { errno = EADDRINUSE; return -1; }
    return bind(fd, address, length);
}
static int test_listen(int fd, int backlog) {
    assert(fd == opened_fd && backlog > 0);
    if (failure == 3) { errno = EOPNOTSUPP; return -1; }
    return listen(fd, backlog);
}
#define socket test_socket
#define bind test_bind
#define listen test_listen
#define main loader_main
#include "src/llama_scx_simple.c"
#undef main
int main(int argc, char **argv) {
    struct phase_control c;
    assert(argc == 3);
    phase_control_init(&c);
    assert(!c.enabled && c.listener_fd == -1 && c.client_fd == -1 && socket_calls == 0);
    phase_control_close(&c, -1);
    assert(!c.enabled && socket_calls == 0); /* Disabled mode creates no socket. */
    expected_name = argv[1][0] == '@' ? argv[1] + 1 : argv[1];
    failure = atoi(argv[2]);
    int result = phase_control_open(&c, argv[1], getuid());
    if (result) {
        assert(!c.enabled && c.listener_fd == -1);
        if (failure == 1) assert(result == -EMFILE);
        if (failure == 2) assert(result == -EADDRINUSE);
        if (failure == 3) assert(result == -EOPNOTSUPP);
        if (opened_fd >= 0) assert(fcntl(opened_fd, F_GETFD) == -1 && errno == EBADF);
        return EXIT_FAILURE;
    }
    assert(c.enabled && c.listener_fd == opened_fd && c.allowed_uid == getuid());
    struct sockaddr_un actual;
    socklen_t length = sizeof(actual);
    assert(!getsockname(c.listener_fd, (struct sockaddr *)&actual, &length));
    assert(length == offsetof(struct sockaddr_un, sun_path) + 1 + strlen(expected_name));
    assert(actual.sun_family == AF_UNIX && actual.sun_path[0] == '\0');
    assert(!memcmp(actual.sun_path + 1, expected_name, strlen(expected_name)));
    int listening, type;
    length = sizeof(int);
    assert(!getsockopt(c.listener_fd, SOL_SOCKET, SO_ACCEPTCONN, &listening, &length) && listening);
    assert(!getsockopt(c.listener_fd, SOL_SOCKET, SO_TYPE, &type, &length) && type == SOCK_SEQPACKET);
    signal(SIGINT, request_exit);
    puts("ready");
    fflush(stdout);
    while (!exit_requested) poll(NULL, 0, 100);
    phase_control_close(&c, -1);
    assert(c.listener_fd == -1 && fcntl(opened_fd, F_GETFD) == -1 && errno == EBADF);
    return EXIT_SUCCESS;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "listener.c"
            binary = Path(directory) / "listener"
            source.write_text(harness)
            subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT), "-I", str(ROOT / "include"),
                str(source), "-o", str(binary), "-lbpf", "-lelf", "-lz"], check=True, capture_output=True)
            name = "llama-listener-" + Path(directory).name
            for failure, operation, error in ((1, "socket", errno.EMFILE), (2, "bind", errno.EADDRINUSE),
                                              (3, "listen", errno.EOPNOTSUPP)):
                with self.subTest(operation=operation):
                    result = subprocess.run([str(binary), name, str(failure)],
                                            capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn(f"phase control: {operation} @{name} failed: errno={error} ({os.strerror(error)})",
                                  result.stderr)
            for prefix in ("", "@"):
                with self.subTest(prefix=prefix), subprocess.Popen(
                    [str(binary), prefix + name, "0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True) as process:
                    try:
                        self.assertTrue(select.select([process.stdout], [], [], 3)[0])
                        self.assertEqual(process.stdout.readline(), "ready\n")
                        if shutil.which("ss"):
                            listeners = subprocess.check_output(["ss", "-xl"], text=True)
                            self.assertTrue(any("u_seq" in line and "LISTEN" in line and "@" + name in line
                                                for line in listeners.splitlines()))
                        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as peer:
                            peer.settimeout(1)
                            peer.connect("\0" + name)
                        collision = subprocess.run([str(binary), name, "0"],
                                                   capture_output=True, text=True, timeout=3)
                        self.assertEqual(collision.returncode, 1)
                        self.assertIn(f"bind @{name} failed: errno={errno.EADDRINUSE}", collision.stderr)
                        process.send_signal(signal.SIGINT)
                        _, stderr = process.communicate(timeout=3)
                        self.assertEqual(process.returncode, 0, stderr)
                        self.assertIn(f"phase control: listening on @{name} uid={os.getuid()}", stderr)
                        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as replacement:
                            replacement.bind("\0" + name)  # Cleanup released the abstract name.
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.communicate()

    def test_listener_cli_enable_and_failure_paths(self) -> None:
        source = (ROOT / "src/llama_scx_simple.c").read_text()
        self.assertIn('{ "phase-socket", required_argument, NULL, OPTION_PHASE_SOCKET }', source)
        self.assertIn('{ "phase-uid", required_argument, NULL, OPTION_PHASE_UID }', source)
        self.assertIn("case OPTION_PHASE_SOCKET:\n\t\t\tphase_socket = optarg;", source)
        self.assertIn("parse_uid(optarg, &phase_uid)", source)
        self.assertIn("phase_uid_set = true;", source)
        self.assertIn("legacy socket and semantic uprobe phase sources are mutually exclusive", source)
        self.assertIn("if (phase_socket && !phase_uid_set)", source)
        self.assertIn("if (phase_socket) {\n\t\terr = phase_control_open(&phase_control, phase_socket, phase_uid);"
                      "\n\t\tif (err)\n\t\t\tgoto out;", source)
        self.assertIn("poll_fds[poll_count].fd = phase_control.listener_fd;", source)
        self.assertIn("signal(SIGINT, request_exit);", source)
        self.assertIn("out:\n\tphase_control_close(&phase_control,", source)
        self.assertIn("return err ? EXIT_FAILURE : EXIT_SUCCESS;", source)

    def test_producer_transitions_and_failures(self) -> None:
        producer = ROOT.parent / "llama.cpp/src/llama-context.cpp"
        if not producer.exists():
            self.skipTest("sibling llama.cpp checkout is required for the producer integration test")
        source = producer.read_text()
        notifier = source[source.index("#include <cerrno>"):source.index("//\n// llama_context")]
        self.assertNotRegex(notifier, r"libbpf|bpf\(|bpf/|SYS_bpf|/sys/fs/bpf")
        ubatch = source[source.index("llm_graph_result * llama_context::process_ubatch"):
                        source.index("const auto status = graph_compute(res->get_gf(), batched);")]
        self.assertLess(ubatch.index("res->set_inputs("), ubatch.index("llama_scx_phase_notify("))
        self.assertIn("const bool batched = ubatch.n_tokens > 1;", ubatch)
        harness = '#include <cstdint>\n#define LLAMA_LOG_WARN(...) std::fprintf(stderr, __VA_ARGS__)\n' + notifier + '''
int main() {
    llama_scx_phase_notify(LLAMA_SCX_PHASE_PREFILL);
    for (int i = 0; i < 7; ++i) llama_scx_phase_notify(LLAMA_SCX_PHASE_DECODE);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp = Path(directory) / "producer.cpp"
            binary = Path(directory) / "producer"
            cpp.write_text(harness)
            subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
                "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(binary)],
                check=True, capture_output=True)
            env = os.environ.copy()
            env.pop("LLAMA_SCX_PHASE_SOCKET", None)
            result = subprocess.run([str(binary)], env=env, capture_output=True, timeout=4)
            self.assertEqual((result.returncode, result.stderr), (0, b""))
            env["LLAMA_SCX_PHASE_SOCKET"] = "llama-phase-missing-" + Path(directory).name
            result = subprocess.run([str(binary)], env=env, capture_output=True, timeout=4)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr.count(b"phase notification disabled:"), 1)
            for ack in (b"ACK 1 1 0", b"ACK 2 1 0", b"ACK 1 2 0", b"ACK 1 1 -5",
                        b"ACK 1 1 0\0junk", b"ACK 4294967297 1 0", b"x" * 160, b"", None):
                with self.subTest(ack=ack), socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as listener:
                    name = "llama-phase-producer-" + Path(directory).name
                    listener.bind("\0" + name)
                    listener.listen(1)
                    listener.settimeout(4)
                    env["LLAMA_SCX_PHASE_SOCKET"] = "@" + name
                    with subprocess.Popen([str(binary)], env=env, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE) as process:
                        try:
                            connection, _ = listener.accept()
                            with connection:
                                connection.settimeout(4)
                                self.assertEqual(connection.recv(128), b"PHASE 1 1 1")
                                if ack:
                                    connection.sendall(ack)
                                elif ack == b"":
                                    connection.shutdown(socket.SHUT_RDWR)
                                if ack == b"ACK 1 1 0":
                                    self.assertEqual(connection.recv(128), b"PHASE 1 2 2")
                                    connection.sendall(b"ACK 1 2 0")
                                # EOF proves repeated DECODEs (or failures) sent no more packets.
                                self.assertEqual(connection.recv(128), b"")
                                _, stderr = process.communicate(timeout=4)
                                self.assertEqual(process.returncode, 0)
                                self.assertEqual(stderr.count(b"phase notification disabled:"),
                                                 0 if ack == b"ACK 1 1 0" else 1)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.communicate()


if __name__ == "__main__":
    unittest.main()

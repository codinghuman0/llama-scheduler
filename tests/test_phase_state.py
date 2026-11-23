#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Unprivileged fixtures for v2 BPF reception, registration, and reports."""

import contextlib
import importlib.util
import io
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_phase", ROOT / "scripts/validate_phase.py")
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class StateReceiverTests(unittest.TestCase):
    def run_fixture(self, source: str, libraries: tuple[str, ...] = ()) -> dict | None:
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "fixture.c"
            binary = Path(directory) / "fixture"
            program.write_text(source)
            build = subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT), "-I", str(ROOT / "include"),
                str(program), "-o", str(binary), *libraries,
            ], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            result = subprocess.run([str(binary), directory], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = Path(directory) / "instrumentation.json"
            return json.loads(report.read_text()) if report.exists() else None

    def test_production_bpf_receiver(self) -> None:
        source = (ROOT / "src/llama_scx_simple.bpf.c").read_text()
        observe = source[source.index("static __always_inline struct llama_phase_observation *phase_observation"):
                         source.index("#define PHASE_OBSERVE")]
        helpers = source[source.index("static __always_inline struct llama_uprobe_stats *uprobe_stats"):
                         source.index('SEC("uprobe")')]
        receive = source[source.index('SEC("uprobe")\nint BPF_UPROBE(llama_scx_phase_set_v2_uprobe'):
                         source.index("s32 BPF_STRUCT_OPS(llama_simple_select_cpu")]
        self.run_fixture(r"""
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <linux/bpf.h>
#include "llama_instrumentation.h"

typedef __u32 u32;
struct task_struct {
    u32 tgid;
    __u64 start_time;
    struct task_struct *group_leader;
};
static struct task_struct leader = { .tgid = 7, .start_time = 101, .group_leader = &leader };
static struct task_struct *current = &leader;
static int phase_state, phase_observations, phase_uprobe_config, phase_uprobe_stats;
static struct llama_phase_value state = { .source = LLAMA_PHASE_SOURCE_UPROBE_STATE };
static struct llama_phase_observation observations[LLAMA_PHASE_COUNT];
static struct llama_uprobe_config config = { .enabled = 1, .target_tgid = 7 };
static struct llama_uprobe_stats stats;
static bool present = true, fail_read, fail_update, retire_before_update;

#define SEC(name)
#define BPF_UPROBE(name, ...) name(__VA_ARGS__)
#define READ_ONE(p, a) ((p)->a)
#define READ_TWO(p, a, b) ((p)->a->b)
#define READ_PICK(a, b, impl, ...) impl
#define BPF_CORE_READ(p, ...) READ_PICK(__VA_ARGS__, READ_TWO, READ_ONE)(p, __VA_ARGS__)

static void *bpf_map_lookup_elem(const void *map, const u32 *key)
{
    if (map == &phase_state)
        return present && *key == config.target_tgid ? &state : NULL;
    if (map == &phase_observations)
        return *key < LLAMA_PHASE_COUNT ? &observations[*key] : NULL;
    assert(*key == 0);
    if (map == &phase_uprobe_config)
        return &config;
    assert(map == &phase_uprobe_stats);
    return &stats;
}

static int bpf_map_update_elem(const void *map, const u32 *key,
                               const struct llama_phase_value *value, __u64 flags)
{
    assert(map == &phase_state && *key == config.target_tgid && flags == BPF_EXIST);
    if (retire_before_update)
        present = false;
    if (!present || fail_update)
        return -1;
    state = *value;
    return 0;
}

static int bpf_probe_read_user(void *destination, size_t length, const void *source)
{
    assert(length == 32);
    if (fail_read)
        return -1;
    memcpy(destination, source, length);
    return 0;
}

static __u64 bpf_get_current_pid_tgid(void)
{
    return (__u64)current->tgid << 32;
}

static struct task_struct *bpf_get_current_task_btf(void)
{
    return current;
}
""" + observe + helpers + receive + r"""
static void receive(struct llama_scx_state_v2 event)
{
    assert(llama_scx_phase_set_v2_uprobe(&event) == 0);
}

static void valid(__u64 sequence, u32 phase, u32 active)
{
    receive((struct llama_scx_state_v2){ 2, phase, active, 0, 42, sequence });
    assert(state.run_id == 42 && state.sequence == sequence);
    assert(state.phase == phase && state.active == active);
}

static void rejected(struct llama_scx_state_v2 event, __u64 sequence)
{
    __u64 applied = stats.state_applied;
    receive(event);
    assert(stats.state_applied == applied && state.run_id == 42 && state.sequence == sequence);
    assert(!state.active && state.phase == LLAMA_PHASE_UNKNOWN);
}

int main(void)
{
    valid(1, LLAMA_PHASE_UNKNOWN, 1);
    assert(stats.state_active[LLAMA_PHASE_UNKNOWN] == 1 && stats.state_idle == 0);
    valid(2, LLAMA_PHASE_PREFILL, 1);
    struct task_struct worker = { .tgid = 7, .start_time = 102, .group_leader = &leader };
    struct task_struct recycled = { .tgid = 7, .start_time = 103, .group_leader = &recycled };
    assert(phase_observation(&worker) == &observations[LLAMA_PHASE_PREFILL]);
    assert(phase_observation(&recycled) == &observations[LLAMA_PHASE_UNKNOWN]);
    struct task_struct other = { .tgid = 8, .group_leader = &other };
    current = &other;
    receive((struct llama_scx_state_v2){ 2, LLAMA_PHASE_MIXED, 1, 0, 42, 3 });
    assert(stats.filtered_events == 1 && state.active && state.sequence == 2);
    current = &leader;

    rejected((struct llama_scx_state_v2){ 1, 2, 1, 0, 42, 3 }, 2);
    assert(stats.abi_failures == 1);
    valid(3, LLAMA_PHASE_DECODE, 1);
    rejected((struct llama_scx_state_v2){ 2, 4, 1, 0, 42, 4 }, 3);
    assert(stats.unsupported_phases == 1);

    const struct llama_scx_state_v2 malformed[] = {
        { 2, 2, 2, 0, 42, 10 },
        { 2, 2, 1, 1, 42, 10 },
        { 2, 2, 0, 0, 42, 10 },
        { 2, 2, 1, 0, 0, 10 },
    };
    for (unsigned int i = 0; i < sizeof(malformed) / sizeof(malformed[0]); i++) {
        valid(4 + i, LLAMA_PHASE_DECODE, 1);
        rejected(malformed[i], 4 + i);
    }
    assert(stats.invalid_state_events == 4);
    valid(8, LLAMA_PHASE_DECODE, 1);
    rejected((struct llama_scx_state_v2){ 2, 3, 1, 0, 43, 9 }, 8);
    assert(stats.run_id_mismatches == 1);
    valid(9, LLAMA_PHASE_DECODE, 1);
    rejected((struct llama_scx_state_v2){ 2, 2, 1, 0, 42, 9 }, 9);
    valid(10, LLAMA_PHASE_DECODE, 1);
    rejected((struct llama_scx_state_v2){ 2, 2, 1, 0, 42, 8 }, 10);
    assert(stats.stale_sequences == 2);
    valid(11, LLAMA_PHASE_DECODE, 1);
    fail_read = true;
    rejected((struct llama_scx_state_v2){ 2, 2, 1, 0, 42, 12 }, 11);
    fail_read = false;
    assert(stats.user_read_failures == 1);
    valid(12, LLAMA_PHASE_DECODE, 1);
    fail_update = true;
    rejected((struct llama_scx_state_v2){ 2, 0, 0, 0, 42, 13 }, 12);
    fail_update = false;
    assert(stats.map_update_failures == 1);
    valid(14, LLAMA_PHASE_UNKNOWN, 0);
    assert(stats.state_idle == 1);
    valid(15, LLAMA_PHASE_DECODE, 1);
    retire_before_update = true;
    rejected((struct llama_scx_state_v2){ 2, 0, 0, 0, 42, 16 }, 15);
    assert(!present && stats.map_update_failures == 2);
    assert(phase_observation(&worker) == &observations[LLAMA_PHASE_UNKNOWN]);
    present = true;
    state = (struct llama_phase_value){ .source = LLAMA_PHASE_SOURCE_UPROBE,
                                       .active = 1, .phase = LLAMA_PHASE_DECODE };
    receive((struct llama_scx_state_v2){ 2, 3, 1, 0, 42, 17 });
    assert(stats.map_update_failures == 3 && !state.active);
    return 0;
}
""")

    def test_pidfd_cleanup_and_report(self) -> None:
        report = self.run_fixture(r"""
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <string.h>
#include <sys/wait.h>
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include "llama_instrumentation.h"

enum { CONFIG_MAP = 11, STATE_MAP = 12 };
static struct llama_uprobe_config config;
static struct llama_phase_value value;
static __u32 target;
static int state_present, active_link, fail_enable, fail_delete;
static int programs[3], autoload[3], link_token;

static struct bpf_program *fake_find(const struct bpf_object *object, const char *name)
{
    (void)object;
    const char *names[] = {
        "llama_scx_decode_begin_v1_uprobe", "llama_scx_decode_end_v1_uprobe",
        "llama_scx_phase_set_v2_uprobe",
    };
    for (unsigned int i = 0; i < 3; i++) {
        if (!strcmp(name, names[i]))
            return (struct bpf_program *)&programs[i];
    }
    return NULL;
}

static int fake_autoload(struct bpf_program *program, bool enabled)
{
    autoload[(int *)program - programs] = enabled;
    return 0;
}

static struct bpf_link *fake_attach(const struct bpf_program *program, pid_t pid,
                                    const char *path, size_t offset, const struct bpf_uprobe_opts *options)
{
    assert(program == (struct bpf_program *)&programs[2] && pid == (pid_t)target && !offset);
    assert(path && !strcmp(options->func_name, "llama_scx_phase_set_v2"));
    assert(state_present && !config.enabled && !active_link);
    active_link = 1;
    return (struct bpf_link *)&link_token;
}

static int fake_destroy(struct bpf_link *link)
{
    if (link) {
        assert(link == (struct bpf_link *)&link_token && active_link);
        active_link = 0;
    }
    return 0;
}

static int fake_update(int fd, const void *key, const void *data, __u64 flags)
{
    if (fd == CONFIG_MAP) {
        const struct llama_uprobe_config *next = data;
        assert(!*(__u32 *)key && flags == BPF_ANY);
        if (next->enabled && fail_enable) {
            errno = EIO;
            return -1;
        }
        config = *next;
        return 0;
    }
    assert(fd == STATE_MAP && *(__u32 *)key == target);
    assert((flags == BPF_NOEXIST && !state_present) || (flags == BPF_EXIST && state_present));
    value = *(const struct llama_phase_value *)data;
    state_present = 1;
    return 0;
}

static int fake_lookup(int fd, const void *key, void *data)
{
    assert(fd == STATE_MAP && *(__u32 *)key == target && state_present);
    *(struct llama_phase_value *)data = value;
    return 0;
}

static int fake_delete(int fd, const void *key)
{
    assert(fd == STATE_MAP && *(__u32 *)key == target && !active_link && !config.enabled);
    if (fail_delete) {
        errno = EIO;
        return -1;
    }
    state_present = 0;
    return 0;
}

#define bpf_object__find_program_by_name fake_find
#define bpf_program__set_autoload fake_autoload
#define bpf_program__attach_uprobe_opts fake_attach
#define bpf_link__destroy fake_destroy
#define bpf_map_update_elem fake_update
#define bpf_map_lookup_elem fake_lookup
#define bpf_map_delete_elem fake_delete
#define main loader_main
#include "src/llama_scx_simple.c"
#undef main

int main(int argc, char **argv)
{
    struct phase_uprobe_control control;
    struct runtime_data exit_data = {};
    int gate[2];
    assert(argc == 2 && pipe(gate) == 0);
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        close(gate[1]);
        char byte;
        _exit(read(gate[0], &byte, 1) == 0 ? 0 : 1);
    }
    close(gate[0]);
    target = child;
    int pidfd = (int)syscall(SYS_pidfd_open, child, 0);
    assert(pidfd >= 0 && phase_pidfd_exited(pidfd) == 0);
    phase_uprobe_init(&control);
    assert(phase_uprobe_select_programs(NULL, control.mode) == 0);
    assert(autoload[0] && autoload[1] && !autoload[2]);
    control.mode = PHASE_UPROBE_STATE;
    control.binary_path = "/proc/self/exe";
    control.enabled = true;
    assert(phase_uprobe_select_programs(NULL, control.mode) == 0);
    assert(!autoload[0] && !autoload[1] && autoload[2]);
    fail_enable = 1;
    assert(phase_uprobe_attach_state(&control, NULL, CONFIG_MAP, STATE_MAP, target, pidfd) == -EIO);
    assert(!state_present && !active_link && !control.target_tgid);
    fail_enable = 0;
    assert(phase_uprobe_attach_state(&control, NULL, CONFIG_MAP, STATE_MAP, target, pidfd) == 0);
    assert(config.enabled && config.target_tgid == target && control.target_pidfd == pidfd);
    assert(value.source == LLAMA_PHASE_SOURCE_UPROBE_STATE && !value.active);

    value.active = 1;
    value.phase = LLAMA_PHASE_DECODE;
    value.run_id = 42;
    value.sequence = 5;
    int dead_pidfd = dup(pidfd);
    assert(dead_pidfd >= 0);
    close(gate[1]);
    struct pollfd descriptor = { .fd = pidfd, .events = POLLIN };
    assert(poll(&descriptor, 1, 2000) == 1 && phase_pidfd_exited(pidfd) == 1);
    assert(waitpid(child, NULL, 0) == child);
    assert(phase_uprobe_retire_state(&control, CONFIG_MAP, STATE_MAP, true) == 0);
    assert(!state_present && !active_link && !config.enabled && !control.target_tgid);
    assert(control.target_pidfd == -1 && control.last_target_tgid == target);
    assert(control.target_exited && control.active_at_exit && control.phase_at_exit == LLAMA_PHASE_DECODE);
    assert(!control.last_state.active && control.last_state.sequence == 5);
    assert(write_report(argv[1], "start", "end", NULL, NULL, NULL, NULL, NULL, NULL,
                        &(struct phase_control){}, &control, &exit_data) == 0);
    assert(phase_uprobe_attach_state(&control, NULL, CONFIG_MAP, STATE_MAP, target, dead_pidfd) == -ESRCH);
    assert(!state_present && !active_link && !control.target_tgid);
    close(dead_pidfd);

    pidfd = (int)syscall(SYS_pidfd_open, getpid(), 0);
    assert(pidfd >= 0);
    assert(phase_uprobe_attach_state(&control, NULL, CONFIG_MAP, STATE_MAP, target, pidfd) == 0);
    assert(!value.active && !value.sequence && !value.run_id && !control.target_exited);
    value.active = 1;
    value.phase = LLAMA_PHASE_DECODE;
    fail_delete = 1;
    assert(phase_uprobe_close(&control, CONFIG_MAP, STATE_MAP) == -EIO);
    assert(control.cleanup_failures == 1 && !config.enabled && !active_link &&
           !value.active && value.phase == LLAMA_PHASE_UNKNOWN);
    return 0;
}
""", ("-lbpf", "-lelf", "-lz"))
        self.assertIsNotNone(report)
        uprobe = report["phase_uprobe"]
        self.assertEqual(uprobe["mode"], "state")
        self.assertEqual(uprobe["event_semantics"], "phase_transitions")
        self.assertTrue(uprobe["target_exited"])
        self.assertTrue(uprobe["active_at_exit"])
        self.assertEqual(uprobe["phase_at_exit"], "DECODE")
        self.assertEqual(uprobe["state"], {"active": 0, "phase": 0, "phase_name": "UNKNOWN",
                                           "source": 3, "run_id": 42, "sequence": 5})
        self.assertIn("state_applied", uprobe["counters"])
        self.assertNotIn("begin_events", uprobe["counters"])


def state_report(aborted: bool) -> dict:
    phases = 2 if aborted else 1
    transitions = phases * 2 + 1
    return {
        "phase_control": {"enabled": False},
        "phase_uprobe": {
            "mode": "state", "event_semantics": "phase_transitions",
            "target_tgid": 0, "last_target_tgid": 7, "target_exited": True,
            "active_at_exit": aborted, "phase_at_exit": "DECODE" if aborted else "UNKNOWN",
            "state": {"active": 0, "phase": 0, "phase_name": "UNKNOWN",
                      "source": 3, "run_id": 42, "sequence": transitions},
            "counters": {
                **dict.fromkeys(validator.STATE_FAILURE_COUNTERS, 0),
                "state_events": transitions, "state_applied": transitions,
                "state_idle": 1, "state_unknown": 0, "state_prefill": phases,
                "state_decode": phases, "state_mixed": 0,
            },
        },
        "phase_observations": [{"name": name, "running": 1}
                               for name in ("UNKNOWN", "PREFILL", "DECODE", "MIXED")],
    }


class StateAcceptanceTests(unittest.TestCase):
    def validate(self, report: dict, aborted: bool = False) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instrumentation.json"
            path.write_text(json.dumps(report))
            return validator.validate_state_report(path, 7, 42, aborted)

    def test_transition_and_termination_paths(self) -> None:
        self.assertEqual(self.validate(state_report(False))["sequence"], 3)
        self.assertEqual(self.validate(state_report(True), aborted=True)["phase_at_exit"], "DECODE")
        with self.assertRaises(validator.ValidationError):
            self.validate(state_report(True))

    def test_rejects_zero_delivery_and_diagnostic_failures(self) -> None:
        for name in ("state_applied", "run_id_mismatches", "stale_sequences", "cleanup_failures"):
            with self.subTest(counter=name):
                report = state_report(False)
                report["phase_uprobe"]["counters"][name] = 0 if name == "state_applied" else 1
                with self.assertRaises(validator.ValidationError):
                    self.validate(report)

    def test_rejects_wrong_run_sequences_and_registration(self) -> None:
        for key, value in (("run_id", 43), ("sequence", 4), ("active", 1), ("source", 2)):
            with self.subTest(key=key):
                report = state_report(False)
                report["phase_uprobe"]["state"][key] = value
                with self.assertRaises(validator.ValidationError):
                    self.validate(report)
        report = state_report(True)
        report["phase_uprobe"]["target_exited"] = False
        with self.assertRaises(validator.ValidationError):
            self.validate(report, aborted=True)

    def test_state_options_keep_trace_defaults(self) -> None:
        trace = validator.parse_arguments(["--model", "model.gguf"])
        self.assertEqual(trace.phase_uprobe_mode, "trace")
        state = validator.parse_arguments([
            "--model", "model.gguf", "--phase-uprobe-mode", "state",
            "--semantic-dir", "source", "--semantic-build", "build", "--state-abort",
        ])
        self.assertTrue(state.state_abort)
        for options in (["--state-abort"], ["--phase-uprobe-mode", "state"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                validator.parse_arguments(["--model", "model.gguf", *options])

    def test_progress_requires_applied_events_from_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "loader.log"
            log.write_text("phase_state_tgid=7 applied=3 prefill=1 decode=1 idle=1\n")
            self.assertTrue(validator.state_counters_observed(log, 7))
            self.assertFalse(validator.state_counters_observed(log, 8))
            log.write_text("phase_state_tgid=7 applied=0 prefill=0 decode=0 idle=0\n")
            self.assertFalse(validator.state_counters_observed(log, 7))

    def test_abort_waits_for_the_second_token(self) -> None:
        response = mock.Mock(status=200)
        response.readline.side_effect = [
            b'data: {"tokens":[1],"stop":false}\n', b"\n",
            b'data: {"tokens":[2],"stop":false}\n',
        ]
        connection = mock.Mock()
        connection.getresponse.return_value = response
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(validator.http.client, "HTTPConnection", return_value=connection),
            mock.patch.object(validator.signal, "pidfd_send_signal") as send_signal,
        ):
            validator.abort_state_decode(1234, {"temperature": 0}, 92, Path(directory) / "abort.sse")
            self.assertEqual(response.readline.call_count, 3)
            send_signal.assert_called_once_with(92, validator.signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()

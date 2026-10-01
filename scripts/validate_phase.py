#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""One-terminal M11R semantic phase runtime validation."""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_FILE = REPO_ROOT / "config" / "versions.env"
SCX_STATE = Path("/sys/kernel/sched_ext/state")
VMLINUX_BTF = Path("/sys/kernel/btf/vmlinux")
SCHED_EXT = 7
MARKER_SYMBOLS = ("llama_scx_decode_begin_v1", "llama_scx_decode_end_v1")
FAILURE_COUNTERS = (
    "abi_failures",
    "user_read_failures",
    "unsupported_phases",
    "stale_end_events",
    "map_update_failures",
    "filtered_events",
)
PROMPT = "List three colors and briefly describe each one."


class ValidationError(RuntimeError):
    pass


class TerminationRequested(RuntimeError):
    pass


class RunLogger:
    def __init__(self, path: Path) -> None:
        self.stream = path.open("x", encoding="utf-8", buffering=1)

    def log(self, message: str) -> None:
        timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        line = f"[{timestamp}] {message}"
        print(line, flush=True)
        self.stream.write(line + "\n")

    def close(self) -> None:
        self.stream.close()


def parse_manifest(path: Path = VERSIONS_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Z][A-Z0-9_]*)=([A-Za-z0-9._:/+-]+)", line)
        if not match:
            raise ValidationError(f"unsafe manifest syntax at {path}:{number}")
        values[match.group(1)] = match.group(2)
    required = {
        "BASELINE_NAME",
        "SEMANTIC_LLAMA_REPO",
        "SEMANTIC_LLAMA_COMMIT",
        "VALIDATED_DISTRIBUTION",
        "VALIDATED_UBUNTU_VERSION",
        "VALIDATED_ARCH",
        "VALIDATED_KERNEL",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValidationError(f"manifest is missing: {', '.join(missing)}")
    if not re.fullmatch(r"[0-9a-f]{40}", values["SEMANTIC_LLAMA_COMMIT"]):
        raise ValidationError("SEMANTIC_LLAMA_COMMIT must be a full SHA")
    return values


def checked_output(arguments: list[str], cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            arguments,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ValidationError(f"command failed: {' '.join(arguments)}: {error}") from error
    return result.stdout.strip()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def require_file(path: Path, executable: bool = False) -> None:
    if not path.is_file():
        raise ValidationError(f"required file is missing: {path}")
    if not os.access(path, os.R_OK):
        raise ValidationError(f"required file is not readable: {path}")
    if executable and not os.access(path, os.X_OK):
        raise ValidationError(f"required file is not executable: {path}")


def verify_marker_symbols(marker_elf: Path) -> None:
    table = checked_output(["readelf", "--dyn-syms", "--wide", str(marker_elf)])
    for symbol in MARKER_SYMBOLS:
        pattern = re.compile(
            rf"^\s*\d+:\s+[0-9a-fA-F]+\s+\d+\s+FUNC\s+GLOBAL\s+DEFAULT\s+\d+\s+{symbol}$",
            re.MULTILINE,
        )
        if not pattern.search(table):
            raise ValidationError(f"dynamic marker symbol missing from {marker_elf}: {symbol}")


def read_sched_ext_state() -> str:
    try:
        return SCX_STATE.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValidationError(f"cannot read {SCX_STATE}: {error}") from error


def existing_llama_servers() -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
            executable = os.readlink(entry / "exe")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if comm == "llama-server" or Path(executable).name == "llama-server":
            found.append((pid, executable))
    return sorted(found)


def reserve_port(requested: int) -> int:
    if requested < 0 or requested > 65535:
        raise ValidationError("--port must be between 1 and 65535, or 0 for automatic")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            probe.bind(("127.0.0.1", requested))
        except OSError as error:
            raise ValidationError(f"localhost port {requested} is unavailable: {error}") from error
        return int(probe.getsockname()[1])


def process_identity(pid: int) -> dict[str, Any]:
    fields: dict[str, str] = {}
    try:
        with Path(f"/proc/{pid}/status").open(encoding="utf-8") as status:
            for line in status:
                name, separator, value = line.partition(":")
                if separator:
                    fields[name] = value.strip()
        policy = os.sched_getscheduler(pid)
    except (FileNotFoundError, ProcessLookupError, PermissionError) as error:
        raise ValidationError(f"cannot inspect process {pid}: {error}") from error
    return {
        "pid": pid,
        "name": fields["Name"],
        "ppid": int(fields["PPid"]),
        "uids": [int(value) for value in fields["Uid"].split()],
        "policy": policy,
        "policy_name": {os.SCHED_OTHER: "SCHED_NORMAL", SCHED_EXT: "SCHED_EXT"}.get(
            policy, f"policy-{policy}"
        ),
    }


def sched_ext_tasks() -> list[tuple[int, int]]:
    tasks: list[tuple[int, int]] = []
    for process_entry in Path("/proc").iterdir():
        if not process_entry.name.isdigit():
            continue
        tgid = int(process_entry.name)
        try:
            task_entries = list((process_entry / "task").iterdir())
        except (FileNotFoundError, PermissionError):
            continue
        for task_entry in task_entries:
            try:
                tid = int(task_entry.name)
                if os.sched_getscheduler(tid) == SCHED_EXT:
                    tasks.append((tgid, tid))
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError as error:
                raise ValidationError(
                    f"cannot prove SCHED_EXT isolation for task {task_entry.name}: {error}"
                ) from error
    return sorted(tasks)


def wait_until(
    description: str,
    timeout: float,
    predicate: Callable[[], Any],
    processes: list[tuple[str, subprocess.Popen[bytes]]] | None = None,
) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if processes:
            for label, process in processes:
                returncode = process.poll()
                if returncode is not None:
                    raise ValidationError(f"{label} exited early with status {returncode}")
        value = predicate()
        if value:
            return value
        time.sleep(0.25)
    raise ValidationError(f"timed out waiting for {description} after {timeout:.0f}s")


def regex_value(path: Path, pattern: str) -> int | None:
    matches = re.findall(pattern, read_text(path), re.MULTILINE)
    return int(matches[-1]) if matches else None


def http_get(port: int, path: str, timeout: float = 2.0) -> tuple[int, str, list[tuple[str, str]], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read()
        return response.status, response.reason, response.getheaders(), body
    finally:
        connection.close()


def wait_for_health(port: int, target: Path) -> bool:
    try:
        status, reason, headers, body = http_get(port, "/health")
    except (OSError, http.client.HTTPException):
        return False
    if status != 200:
        return False
    target.write_bytes(body)
    header_path = target.with_suffix(".headers")
    with header_path.open("w", encoding="utf-8") as stream:
        stream.write(f"HTTP {status} {reason}\n")
        for name, value in headers:
            stream.write(f"{name}: {value}\n")
    return True


def post_completion(
    port: int, request: dict[str, Any], headers_path: Path, body_path: Path
) -> dict[str, Any]:
    payload = json.dumps(request, separators=(",", ":")).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    try:
        connection.request(
            "POST",
            "/completion",
            body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        response = connection.getresponse()
        body = response.read()
        with headers_path.open("x", encoding="utf-8") as stream:
            stream.write(f"HTTP {response.status} {response.reason}\n")
            for name, value in response.getheaders():
                stream.write(f"{name}: {value}\n")
        body_path.write_bytes(body)
        if response.status != 200:
            raise ValidationError(f"completion returned HTTP {response.status}")
    except (OSError, http.client.HTTPException) as error:
        raise ValidationError(f"completion request failed: {error}") from error
    finally:
        connection.close()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        raise ValidationError(f"completion response is not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise ValidationError("completion response must be a JSON object")
    predicted = parsed.get("tokens_predicted")
    if isinstance(predicted, bool) or not isinstance(predicted, int) or predicted <= 0:
        raise ValidationError(f"invalid tokens_predicted value: {predicted!r}")
    return parsed


def counters_observed(loader_log: Path) -> dict[str, int] | None:
    pattern = re.compile(
        r"phase_uprobe_tgid=(\d+) begin=(\d+) end=(\d+) "
        r"prefill=(\d+) decode=(\d+) mixed=(\d+)"
    )
    for match in reversed(pattern.findall(read_text(loader_log))):
        target, begin, end, prefill, decode, mixed = map(int, match)
        if target > 0 and begin > 0 and begin == end and prefill > 0 and decode > 0:
            return {
                "target_tgid": target,
                "begin_events": begin,
                "end_events": end,
                "begin_prefill": prefill,
                "begin_decode": decode,
                "begin_mixed": mixed,
            }
    return None


def read_cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"


def os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator:
                values[name] = value.strip().strip('"')
    except OSError:
        pass
    return values


def git_identity(path: Path) -> tuple[str, str]:
    sha = checked_output(["git", "-C", str(path), "rev-parse", "HEAD"])
    state = "dirty" if checked_output(["git", "-C", str(path), "status", "--short"]) else "clean"
    return sha, state


def write_environment(
    path: Path,
    manifest: dict[str, str],
    model: Path,
    port: int,
    phase_run_id: int,
    semantic_sha: str,
) -> None:
    distribution = os_release()
    scheduler_sha, scheduler_state = git_identity(REPO_ROOT)
    data = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "baseline_name": manifest["BASELINE_NAME"],
        "scheduler_git_sha": scheduler_sha,
        "scheduler_worktree_state": scheduler_state,
        "semantic_repo": manifest["SEMANTIC_LLAMA_REPO"],
        "semantic_commit": semantic_sha,
        "kernel": platform.release(),
        "kernel_compatibility": (
            "VALIDATED"
            if distribution.get("ID") == "ubuntu"
            and distribution.get("VERSION_ID") == manifest["VALIDATED_UBUNTU_VERSION"]
            and platform.release() == manifest["VALIDATED_KERNEL"]
            and platform.machine() == manifest["VALIDATED_ARCH"]
            else "COMPATIBLE-BUT-UNVALIDATED"
        ),
        "architecture": platform.machine(),
        "cpu_model": read_cpu_model(),
        "online_cpu_count": os.cpu_count(),
        "distribution_id": distribution.get("ID", "unknown"),
        "distribution_version": distribution.get("VERSION_ID", "unknown"),
        "uid": os.getuid(),
        "gid": os.getgid(),
        "model_path": str(model),
        "model_size_bytes": model.stat().st_size,
        "port": port,
        "phase_run_id": phase_run_id,
        "python": sys.version.splitlines()[0],
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_isolation(
    launcher_pid: int,
    server_pid: int,
    registration_pid: int,
    target_tgid: int,
) -> dict[str, Any]:
    expected_uid = os.getuid()
    identities = {
        "invoking_shell": process_identity(os.getppid()),
        "validator": process_identity(os.getpid()),
        "launcher": process_identity(launcher_pid),
        "server": process_identity(server_pid),
    }
    for label, identity in identities.items():
        if any(uid != expected_uid for uid in identity["uids"]):
            raise ValidationError(f"{label} UID mismatch: {identity}")
    for label in ("invoking_shell", "validator", "launcher"):
        if identities[label]["policy"] != os.SCHED_OTHER:
            raise ValidationError(f"{label} is not SCHED_NORMAL: {identities[label]}")
    if identities["server"]["policy"] != SCHED_EXT:
        raise ValidationError(f"server is not SCHED_EXT: {identities['server']}")
    if identities["server"]["ppid"] != launcher_pid:
        raise ValidationError("server PPID does not match launcher PID")
    if registration_pid != server_pid or target_tgid != server_pid:
        raise ValidationError(
            f"PID mismatch: server={server_pid} registration={registration_pid} target={target_tgid}"
        )
    tasks = sched_ext_tasks()
    if (server_pid, server_pid) not in tasks:
        raise ValidationError(f"selected server leader is absent from SCHED_EXT tasks: {tasks}")
    if any(tgid != server_pid for tgid, _ in tasks):
        raise ValidationError(f"unrelated SCHED_EXT task observed: {tasks}")
    return {
        "expected_uid": expected_uid,
        "registration_pid": registration_pid,
        "target_tgid": target_tgid,
        "processes": identities,
        "sched_ext_tasks": [{"tgid": tgid, "tid": tid} for tgid, tid in tasks],
        "privilege_and_isolation": "PASS",
    }


def validate_report(path: Path, expected_tgid: int) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot parse instrumentation report: {error}") from error
    phase_control = data.get("phase_control")
    uprobe = data.get("phase_uprobe")
    observations = data.get("phase_observations")
    if not isinstance(phase_control, dict) or phase_control.get("enabled") is not False:
        raise ValidationError("legacy phase control must be disabled")
    if not isinstance(uprobe, dict):
        raise ValidationError("phase_uprobe report is missing")
    if uprobe.get("last_target_tgid") != expected_tgid:
        raise ValidationError(
            f"reported target TGID {uprobe.get('last_target_tgid')} != server {expected_tgid}"
        )
    counters = uprobe.get("counters")
    state = uprobe.get("state")
    if not isinstance(counters, dict) or not isinstance(state, dict):
        raise ValidationError("phase uprobe counters/state are missing")
    begin = counters.get("begin_events")
    end = counters.get("end_events")
    if not isinstance(begin, int) or begin <= 0 or begin != end:
        raise ValidationError(f"unbalanced semantic markers: begin={begin} end={end}")
    if not isinstance(counters.get("begin_prefill"), int) or counters["begin_prefill"] <= 0:
        raise ValidationError("no PREFILL begin marker was observed")
    if not isinstance(counters.get("begin_decode"), int) or counters["begin_decode"] <= 0:
        raise ValidationError("no DECODE begin marker was observed")
    nonzero_failures = {name: counters.get(name) for name in FAILURE_COUNTERS if counters.get(name) != 0}
    if nonzero_failures:
        raise ValidationError(f"semantic marker failure counters are nonzero: {nonzero_failures}")
    if state.get("active") != 0 or state.get("phase") != 0 or state.get("phase_name") != "UNKNOWN":
        raise ValidationError(f"final phase state is not inactive/UNKNOWN: {state}")
    if not isinstance(observations, list):
        raise ValidationError("phase observations are missing")
    by_name = {entry.get("name"): entry for entry in observations if isinstance(entry, dict)}
    for phase in ("UNKNOWN", "PREFILL", "DECODE", "MIXED"):
        if phase not in by_name:
            raise ValidationError(f"phase observation is missing: {phase}")
    if by_name["PREFILL"].get("running", 0) <= 0:
        raise ValidationError("PREFILL.running was not observed")
    if by_name["DECODE"].get("running", 0) <= 0:
        raise ValidationError("DECODE.running was not observed")
    return {
        "begin_events": begin,
        "end_events": end,
        "begin_prefill": counters["begin_prefill"],
        "begin_decode": counters["begin_decode"],
        "begin_mixed": counters.get("begin_mixed", 0),
        "mixed_running": by_name["MIXED"].get("running", 0),
        "failure_counters": {name: counters[name] for name in FAILURE_COUNTERS},
        "final_active": state["active"],
        "final_phase": state["phase_name"],
        "prefill_running": by_name["PREFILL"]["running"],
        "decode_running": by_name["DECODE"]["running"],
    }


def copy_loader_reports(loader_output: Path, result_dir: Path) -> None:
    for filename in ("instrumentation.json", "summary.txt"):
        source = loader_output / filename
        destination = result_dir / filename
        if not source.is_file():
            raise ValidationError(f"loader did not produce {source}")
        if destination.exists():
            raise ValidationError(f"refusing to overwrite {destination}")
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)


def pid_is_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_pid_exit(pid: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and pid_is_alive(pid):
        time.sleep(0.1)
    return not pid_is_alive(pid)


def stop_processes(
    logger: RunLogger,
    launcher: subprocess.Popen[bytes] | None,
    server_pid: int | None,
    loader: subprocess.Popen[bytes] | None,
) -> list[str]:
    errors: list[str] = []

    launcher_alive = launcher is not None and launcher.poll() is None
    server_alive = pid_is_alive(server_pid)
    if launcher_alive or server_alive:
        logger.log("cleanup: requesting graceful selected-server shutdown")
        try:
            if server_alive and server_pid is not None:
                os.kill(server_pid, signal.SIGINT)
            elif launcher is not None:
                os.killpg(launcher.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    if launcher_alive and launcher is not None:
        try:
            launcher.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.log("cleanup: server did not exit after SIGINT; sending SIGTERM")
            try:
                if pid_is_alive(server_pid) and server_pid is not None:
                    os.kill(server_pid, signal.SIGTERM)
                else:
                    os.killpg(launcher.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                launcher.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.log("cleanup: server group did not exit after SIGTERM; sending SIGKILL")
                try:
                    os.killpg(launcher.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    launcher.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    errors.append(f"launcher process group {launcher.pid} did not exit")
    elif server_alive and server_pid is not None:
        if not wait_for_pid_exit(server_pid, 30):
            logger.log("cleanup: orphaned server did not exit after SIGINT; sending SIGTERM")
            try:
                os.kill(server_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if not wait_for_pid_exit(server_pid, 10):
                logger.log("cleanup: orphaned server did not exit after SIGTERM; sending SIGKILL")
                try:
                    if launcher is not None:
                        os.killpg(launcher.pid, signal.SIGKILL)
                    else:
                        os.kill(server_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if not wait_for_pid_exit(server_pid, 5):
                    errors.append(f"server process {server_pid} did not exit")
    if launcher is not None:
        logger.log(f"cleanup: launcher_status={launcher.poll()}")

    if loader is not None and loader.poll() is None:
        logger.log("cleanup: requesting graceful loader shutdown through its sudo supervisor")
        loader.send_signal(signal.SIGINT)
        try:
            loader.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.log("cleanup: loader did not exit after SIGINT; sending SIGTERM")
            loader.terminate()
            try:
                loader.wait(timeout=15)
            except subprocess.TimeoutExpired:
                errors.append(
                    "loader sudo supervisor did not exit after SIGINT/SIGTERM; "
                    "manual loader cleanup may be required"
                )
    if loader is not None:
        logger.log(f"cleanup: loader_status={loader.poll()}")

    try:
        final_state = wait_until(
            "sched_ext to return to disabled",
            20,
            lambda: read_sched_ext_state() == "disabled",
        )
        if not final_state:
            errors.append(f"final {SCX_STATE} is {read_sched_ext_state()!r}, not disabled")
    except ValidationError as error:
        errors.append(str(error))
    logger.log(f"cleanup: final_sched_ext_state={read_sched_ext_state()}")
    return errors


def execute(args: argparse.Namespace, result_dir: Path, logger: RunLogger) -> None:
    manifest = parse_manifest()
    semantic_dir = REPO_ROOT / ".deps" / "llama.cpp-semantic"
    semantic_server = REPO_ROOT / "build" / "m11r" / "llama-semantic" / "bin" / "llama-server"
    marker_elf = REPO_ROOT / "build" / "m11r" / "llama-semantic" / "bin" / "libllama-server-impl.so"
    loader_binary = REPO_ROOT / "build" / "bin" / "llama_scx_simple"
    launcher_binary = REPO_ROOT / "build" / "bin" / "llama_scx_child"
    loader_output = result_dir / "loader-report"
    loader_log = result_dir / "loader.log"
    server_log = result_dir / "server.log"

    if os.getuid() == 0:
        raise ValidationError("validation must be invoked by a normal non-root user")
    model = args.model.expanduser().resolve()
    require_file(model)
    require_file(semantic_server, executable=True)
    require_file(marker_elf)
    require_file(loader_binary, executable=True)
    require_file(launcher_binary, executable=True)
    require_file(VMLINUX_BTF)
    verify_marker_symbols(marker_elf)
    semantic_sha, semantic_state = git_identity(semantic_dir)
    if semantic_sha != manifest["SEMANTIC_LLAMA_COMMIT"]:
        raise ValidationError(
            f"semantic dependency SHA is {semantic_sha}, expected {manifest['SEMANTIC_LLAMA_COMMIT']}"
        )
    if semantic_state != "clean":
        raise ValidationError("semantic dependency worktree is dirty")
    semantic_origin = checked_output(["git", "-C", str(semantic_dir), "remote", "get-url", "origin"])
    if semantic_origin != manifest["SEMANTIC_LLAMA_REPO"]:
        raise ValidationError(f"semantic dependency origin mismatch: {semantic_origin}")
    if read_sched_ext_state() != "disabled":
        raise ValidationError(f"{SCX_STATE} must report disabled before validation")
    servers = existing_llama_servers()
    if servers:
        raise ValidationError(f"existing llama-server process makes attribution ambiguous: {servers}")
    if os.sched_getscheduler(0) != os.SCHED_OTHER:
        raise ValidationError("validator is not SCHED_NORMAL")
    if os.sched_getscheduler(os.getppid()) != os.SCHED_OTHER:
        raise ValidationError("invoking shell is not SCHED_NORMAL")

    port = reserve_port(args.port)
    write_environment(
        result_dir / "environment.json",
        manifest,
        model,
        port,
        args.run_id,
        semantic_sha,
    )
    request = {
        "prompt": PROMPT,
        "n_predict": 8,
        "temperature": 0,
        "cache_prompt": False,
    }
    (result_dir / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    logger.log(f"preflight=PASS uid={os.getuid()} kernel={platform.release()} port={port}")
    distribution = os_release()
    kernel_status = (
        "VALIDATED"
        if distribution.get("ID") == "ubuntu"
        and distribution.get("VERSION_ID") == manifest["VALIDATED_UBUNTU_VERSION"]
        and platform.release() == manifest["VALIDATED_KERNEL"]
        and platform.machine() == manifest["VALIDATED_ARCH"]
        else "COMPATIBLE-BUT-UNVALIDATED"
    )
    logger.log(f"kernel_compatibility={kernel_status}")
    logger.log(f"semantic_commit={semantic_sha} semantic_worktree={semantic_state}")
    logger.log(f"result_dir={result_dir}")

    socket_name = f"llama-m11r-{os.getuid()}-{os.getpid()}-{args.run_id}"[:100]
    loader_command = [
        "sudo",
        "--",
        str(loader_binary),
        "-v",
        "-o",
        str(loader_output),
        "--phase-uprobe",
        str(marker_elf),
        "--phase-register-socket",
        socket_name,
        "--phase-uid",
        str(os.getuid()),
    ]
    server_command = [
        str(launcher_binary),
        "--phase-register-socket",
        socket_name,
        "--",
        str(semantic_server),
        "-m",
        str(model),
        "-ngl",
        "0",
        "-np",
        "1",
        "--no-cont-batching",
        "--spec-type",
        "none",
        "--server-compute-profile-mode",
        "legacy",
        "--scx-phase-run-id",
        str(args.run_id),
        "--no-warmup",
        "--no-webui",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    loader: subprocess.Popen[bytes] | None = None
    launcher: subprocess.Popen[bytes] | None = None
    server_pid: int | None = None
    run_error: BaseException | None = None
    cleanup_errors: list[str] = []
    loader_stream = None
    server_stream = None

    try:
        loader_stream = loader_log.open("xb", buffering=0)
        logger.log("starting privileged loader; sudo may prompt in this terminal")
        loader = subprocess.Popen(
            loader_command,
            cwd=REPO_ROOT,
            stdout=loader_stream,
            stderr=subprocess.STDOUT,
        )
        wait_until(
            "phase-uprobe registration listener",
            60,
            lambda: "phase uprobe: listening on @" in read_text(loader_log),
            [("loader", loader)],
        )
        if read_sched_ext_state() != "enabled":
            raise ValidationError("loader started but sched_ext state is not enabled")
        logger.log("loader_registration_listener=READY")

        server_stream = server_log.open("xb", buffering=0)
        logger.log("starting normal-user selected-child launcher and semantic llama-server")
        launcher = subprocess.Popen(
            server_command,
            cwd=REPO_ROOT,
            stdout=server_stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid_pattern = r"^parent_pid=(\d+).*child_pid=(\d+).*mode=sched_ext$"

        def parsed_pids() -> tuple[int, int] | None:
            matches = re.findall(pid_pattern, read_text(server_log), re.MULTILINE)
            return tuple(map(int, matches[-1])) if matches else None

        launcher_pid, server_pid = wait_until(
            "launcher/server PID evidence",
            30,
            parsed_pids,
            [("loader", loader), ("launcher", launcher)],
        )
        if launcher_pid != launcher.pid:
            raise ValidationError(
                f"launcher PID output {launcher_pid} does not match started process {launcher.pid}"
            )
        registration_pid = wait_until(
            "semantic target registration",
            30,
            lambda: regex_value(
                server_log, r"^phase_uprobe_registered_tgid=([1-9][0-9]*)$"
            ),
            [("loader", loader), ("launcher", launcher)],
        )
        target_tgid = wait_until(
            "PID-specific uprobe attachment",
            30,
            lambda: regex_value(
                loader_log,
                r"phase uprobe: attached pid-specific decode markers to tgid=([1-9][0-9]*)",
            ),
            [("loader", loader), ("launcher", launcher)],
        )
        wait_until(
            "llama-server health endpoint",
            300,
            lambda: wait_for_health(port, result_dir / "health.json"),
            [("loader", loader), ("launcher", launcher)],
        )
        logger.log("server_health=PASS")

        isolation = validate_isolation(
            launcher_pid, server_pid, registration_pid, target_tgid
        )
        (result_dir / "isolation.json").write_text(
            json.dumps(isolation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        logger.log(
            "privilege_and_isolation=PASS "
            f"launcher={launcher_pid} server={server_pid} registration={registration_pid} "
            f"target={target_tgid} sched_ext_tasks={len(isolation['sched_ext_tasks'])}"
        )

        response = post_completion(
            port,
            request,
            result_dir / "completion.headers",
            result_dir / "completion.json",
        )
        logger.log(f"http_and_inference=PASS tokens_predicted={response['tokens_predicted']}")
        observed = wait_until(
            "balanced PREFILL and DECODE phase counters",
            30,
            lambda: counters_observed(loader_log),
            [("loader", loader), ("launcher", launcher)],
        )
        logger.log(
            "live_phase_counters=PASS "
            f"begin={observed['begin_events']} end={observed['end_events']} "
            f"prefill={observed['begin_prefill']} decode={observed['begin_decode']} "
            f"mixed={observed['begin_mixed']}"
        )
    except BaseException as error:
        run_error = error
    finally:
        cleanup_errors = stop_processes(logger, launcher, server_pid, loader)
        if server_stream is not None:
            server_stream.close()
        if loader_stream is not None:
            loader_stream.close()

    try:
        copy_loader_reports(loader_output, result_dir)
    except ValidationError as error:
        if run_error is None:
            run_error = error
        else:
            logger.log(f"report_copy_error={error}")

    if cleanup_errors and run_error is None:
        run_error = ValidationError("; ".join(cleanup_errors))
    elif cleanup_errors:
        logger.log("cleanup_errors=" + "; ".join(cleanup_errors))

    if run_error is None:
        if loader is None or loader.returncode != 0:
            run_error = ValidationError(
                f"loader did not exit successfully: {None if loader is None else loader.returncode}"
            )
        elif launcher is None or launcher.returncode not in (0, 128 + signal.SIGINT):
            run_error = ValidationError(
                f"launcher/server shutdown status is unexpected: "
                f"{None if launcher is None else launcher.returncode}"
            )

    report_result: dict[str, Any] | None = None
    if run_error is None:
        try:
            if server_pid is None:
                raise ValidationError("server PID was not captured")
            report_result = validate_report(result_dir / "instrumentation.json", server_pid)
        except BaseException as error:
            run_error = error

    summary_path = result_dir / "summary.txt"
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("\nM11R semantic phase validation\n")
        summary.write(f"result_dir={result_dir}\n")
        summary.write(f"final_sched_ext_state={read_sched_ext_state()}\n")
        if report_result is not None:
            for key, value in report_result.items():
                if key != "failure_counters":
                    summary.write(f"{key}={value}\n")
            for name, value in report_result["failure_counters"].items():
                summary.write(f"{name}={value}\n")
        if run_error is None:
            summary.write("semantic_acceptance=PASS\n")
        else:
            summary.write(f"semantic_acceptance=FAIL\nerror={run_error}\n")

    if run_error is not None:
        if isinstance(run_error, (KeyboardInterrupt, TerminationRequested)):
            raise TerminationRequested("validation interrupted; cleanup was attempted")
        if isinstance(run_error, ValidationError):
            raise run_error
        raise ValidationError(str(run_error)) from run_error

    assert report_result is not None
    logger.log(
        "post_run_report=PASS "
        f"begin={report_result['begin_events']} end={report_result['end_events']} "
        f"prefill={report_result['begin_prefill']} decode={report_result['begin_decode']} "
        f"mixed={report_result['begin_mixed']} mixed_running={report_result['mixed_running']}"
    )
    logger.log("semantic_acceptance=PASS")
    logger.log(f"result_dir={result_dir}")


def positive_u64(value: str) -> int:
    try:
        parsed = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--run-id must be a positive decimal integer") from error
    if parsed <= 0 or parsed > (1 << 64) - 1:
        raise argparse.ArgumentTypeError("--run-id must fit a nonzero uint64")
    return parsed


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    parser = argparse.ArgumentParser(
        description="Reproduce the M11 semantic llama-server to sched_ext observation path."
    )
    parser.add_argument("--model", required=True, type=Path, help="readable CPU-runnable GGUF model")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="localhost port (default: choose an available port)",
    )
    parser.add_argument(
        "--run-id",
        type=positive_u64,
        default=int(timestamp),
        help="nonzero semantic marker run ID (default: UTC timestamp)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="exact new result directory (default: results/m11r/<UTC>-<pid>)",
    )
    return parser.parse_args(argv)


def make_result_dir(args: argparse.Namespace) -> Path:
    if args.output_dir is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        result_dir = REPO_ROOT / "results" / "m11r" / f"{stamp}-{os.getpid()}"
    else:
        result_dir = args.output_dir.expanduser()
        if not result_dir.is_absolute():
            result_dir = Path.cwd() / result_dir
    result_dir = result_dir.resolve()
    result_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        result_dir.mkdir()
    except FileExistsError as error:
        raise ValidationError(f"result directory already exists: {result_dir}") from error
    return result_dir


def ensure_failure_summary(result_dir: Path, error: str) -> None:
    summary = result_dir / "summary.txt"
    if summary.exists():
        return
    try:
        final_state = read_sched_ext_state()
    except ValidationError:
        final_state = "unavailable"
    summary.write_text(
        "M11R semantic phase validation\n"
        f"result_dir={result_dir}\n"
        f"final_sched_ext_state={final_state}\n"
        "semantic_acceptance=FAIL\n"
        f"error={error}\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(sys.argv[1:] if argv is None else argv)
    if os.getuid() == 0:
        print("ERROR: validation must be invoked by a normal non-root user", file=sys.stderr)
        return 1
    try:
        result_dir = make_result_dir(args)
    except ValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    logger = RunLogger(result_dir / "validation.log")

    def terminate(signum: int, _frame: Any) -> None:
        raise TerminationRequested(f"received signal {signum}")

    previous_term = signal.signal(signal.SIGTERM, terminate)
    try:
        execute(args, result_dir, logger)
        return 0
    except (ValidationError, TerminationRequested) as error:
        ensure_failure_summary(result_dir, str(error))
        logger.log(f"semantic_acceptance=FAIL error={error}")
        logger.log(f"result_dir={result_dir}")
        return 1
    except KeyboardInterrupt:
        ensure_failure_summary(result_dir, "received SIGINT")
        logger.log("semantic_acceptance=FAIL error=received SIGINT")
        logger.log(f"result_dir={result_dir}")
        return 130
    finally:
        signal.signal(signal.SIGTERM, previous_term)
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())

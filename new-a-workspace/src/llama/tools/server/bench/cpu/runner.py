#!/usr/bin/env python3
"""CPU-only decoder serving benchmark. Model-free tests live beside this file."""

import argparse
import base64
import concurrent.futures
import contextlib
import fcntl
import hashlib
import http.client
import itertools
import json
import math
import os
import platform
import random
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[4]
WORKLOADS = ("pp", "d1", "d2", "d4", "m1", "m3")
CPU_FLAGS = {
    "poll": "--poll", "poll_batch": "--poll-batch",
    "cpu_mask": "--cpu-mask", "cpu_mask_batch": "--cpu-mask-batch",
    "cpu_strict": "--cpu-strict", "cpu_strict_batch": "--cpu-strict-batch",
    "priority": "--prio", "priority_batch": "--prio-batch",
}
DEFAULTS = {
    "seed": 20260905, "request_seed": 424242, "repetitions": 3, "warmups": 1,
    "prompt_tokens": 128, "output_tokens": 128, "long_prompt_tokens": 2048,
    "long_output_tokens": 8, "inject_after_tokens": 8, "ctx_size": 16384,
    "batch_size": 512, "ubatch_size": 256, "slots": 4,
    "ready_timeout_s": 180, "request_timeout_s": 300, "trial_timeout_s": 600,
    "cleanup_timeout_s": 5, "workloads": list(WORKLOADS), "server_env": {},
}


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity(path):
    path = Path(path).resolve(strict=True)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def read_text(path):
    try:
        return Path(path).read_text()
    except OSError as exc:
        return {"unavailable": str(exc)}


def command_output(args):
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"unavailable": str(exc)}


def cpu_seconds(pid):
    stat = Path(f"/proc/{pid}/stat").read_text()
    fields = stat[stat.rfind(")") + 2:].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


def unescape_mountinfo_path(path):
    return re.sub(r"\\(040|011|012|134)", lambda match: chr(int(match[1], 8)), path)


def cgroups(pid):
    membership = Path(f"/proc/{pid}/cgroup").read_text()
    mounts = Path(f"/proc/{pid}/mountinfo").read_text()
    files = {}
    for line in mounts.splitlines():
        before, after = line.split(" - ", 1)
        after_parts = after.split(" ", 2)
        if len(after_parts) < 3:
            continue
        fs, _, options = after_parts
        if fs not in ("cgroup", "cgroup2"):
            continue
        parts = before.split()
        mount_root, mount_path = map(unescape_mountinfo_path, parts[3:5])
        root = PurePosixPath("/" + mount_root.lstrip("/"))
        boundary = Path(mount_path)
        for member in membership.splitlines():
            _, controllers, member_path = member.split(":", 2)
            if fs == "cgroup" and not set(controllers.split(",")) & set(options.split(",")):
                continue
            if fs == "cgroup2" and controllers:
                continue
            try:
                relative = PurePosixPath("/" + member_path.lstrip("/")).relative_to(root)
            except ValueError:
                continue
            # A cgroup namespace can report membership outside its root.
            if ".." in relative.parts:
                continue
            directory = boundary / relative
            while True:
                for name in ("cpu.max", "cpu.stat", "cpuset.cpus.effective", "cpu.cfs_quota_us", "cpu.cfs_period_us", "cpuset.cpus"):
                    path = directory / name
                    if path.exists():
                        files[str(path)] = read_text(path)
                if directory == boundary:
                    break
                directory = directory.parent
    return {"membership": membership, "mountinfo": mounts, "quota_and_cpuset_ancestors": files}


def process_environment(pid):
    return {
        "pid": pid, "affinity": sorted(os.sched_getaffinity(pid)),
        "status": read_text(f"/proc/{pid}/status"), "cgroups": cgroups(pid),
    }


def manifest(config):
    model = Path(config["model"])
    match = re.fullmatch(r"(.+)-(\d{5})-of-(\d{5})\.gguf", model.name)
    models = [model]
    if match:
        prefix, _, count = match.groups()
        models = [model.with_name(f"{prefix}-{i:05d}-of-{count}.gguf") for i in range(1, int(count) + 1)]
    return {
        "schema_version": 1, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": config, "runner": identity(__file__),
        "source": {name: command_output(args) for name, args in {
            "branch": ["git", "branch", "--show-current"], "commit": ["git", "rev-parse", "HEAD"],
            "status": ["git", "status", "--porcelain=v1"], "diff": ["git", "diff", "HEAD"],
            "remotes": ["git", "remote", "-v"],
        }.items()},
        "model_files": [identity(path) for path in models], "server": identity(config["server"]),
        "server_version": command_output([config["server"], "--version"]),
        "build_cache": {**identity(config["build_cache"]), "content": read_text(config["build_cache"])},
        "host": {"platform": platform.platform(), "python": sys.version, "hostname": socket.gethostname(),
                 "cpuinfo": read_text("/proc/cpuinfo"), "meminfo": read_text("/proc/meminfo"),
                 "os_release": read_text("/etc/os-release"), "lscpu": command_output(["lscpu", "-J"]),
                 "sched_ext": read_text("/sys/kernel/sched_ext/state"),
                 "power": {str(p): read_text(p) for pattern in (
                     "/sys/devices/system/cpu/cpufreq/policy*/scaling_governor",
                     "/sys/devices/system/cpu/cpufreq/policy*/energy_performance_preference",
                 ) for p in Path("/").glob(pattern.lstrip("/"))}},
        "client": process_environment(os.getpid()),
        "environment": runtime_env(), "cwd": str(Path.cwd()),
        "clock": {"name": "monotonic_ns", "resolution_s": time.get_clock_info("monotonic").resolution},
    }


def runtime_env():
    return {k: v for k, v in os.environ.items() if k.startswith(("OMP_", "GOMP_", "KMP_", "OPENBLAS_"))
            or k in ("PATH", "LD_LIBRARY_PATH", "LD_PRELOAD", "LANG", "LC_ALL", "TZ")}


def load_config(path):
    supplied = json.loads(path.read_text())
    allowed = set(DEFAULTS) | {"server", "model", "model_description", "build_cache", "conditions"}
    if set(supplied) - allowed:
        raise ValueError(f"unknown configuration keys: {sorted(set(supplied) - allowed)}")
    config = {**DEFAULTS, **supplied}
    for key in ("server", "model", "build_cache", "model_description", "conditions"):
        if not config.get(key):
            raise ValueError(f"missing {key}")
    for key in ("server", "model", "build_cache"):
        value = Path(config[key]).expanduser()
        config[key] = str((path.resolve().parent / value).resolve())
    for key in DEFAULTS:
        if key.endswith("_s"):
            value = config[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite")
        elif isinstance(DEFAULTS[key], int):
            value = config[key]
            minimum = 0 if key in ("seed", "request_seed") else 1
            if type(value) is not int or value < minimum:
                raise ValueError(f"invalid {key}")
    if not config["workloads"] or set(config["workloads"]) - set(WORKLOADS):
        raise ValueError("unsupported workload")
    if config["slots"] < max(4 if w in ("d4", "m3") else 2 if w in ("d2", "m1") else 1 for w in config["workloads"]):
        raise ValueError("not enough slots")
    if config["inject_after_tokens"] >= config["output_tokens"]:
        raise ValueError("injection threshold must precede decode completion")
    if config["ctx_size"] // config["slots"] < max(config["prompt_tokens"] + config["output_tokens"], config["long_prompt_tokens"] + config["long_output_tokens"]):
        raise ValueError("context per slot cannot hold the configured requests")
    for condition in config["conditions"]:
        if set(condition) - ({"threads", "batch_threads", "profile"} | set(CPU_FLAGS)):
            raise ValueError("unsupported condition option")
        if condition.get("profile") not in ("legacy", "auto", "phase"):
            raise ValueError("invalid profile")
        for key in ("threads", "batch_threads"):
            if type(condition.get(key)) is not int or condition[key] < 1:
                raise ValueError(f"invalid {key}")
        for key in ("poll", "poll_batch"):
            if key in condition and (type(condition[key]) is not int or not 0 <= condition[key] <= (100 if key == "poll" else 1)):
                raise ValueError(f"invalid {key}")
        for key in ("cpu_mask", "cpu_mask_batch"):
            if key in condition and (not isinstance(condition[key], str) or not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{1,128}", condition[key])):
                raise ValueError(f"invalid {key}")
        for key in ("cpu_strict", "cpu_strict_batch", "priority", "priority_batch"):
            lower, upper = (0, 1) if key.startswith("cpu_strict") else (-1 if key == "priority" else 0, 3)
            if key in condition and (type(condition[key]) is not int or not lower <= condition[key] <= upper):
                raise ValueError(f"invalid {key}")
    for key, value in config["server_env"].items():
        if not key.startswith(("OMP_", "GOMP_", "KMP_", "OPENBLAS_")) or not isinstance(value, str):
            raise ValueError("server_env accepts only string CPU runtime variables")
    return config


def execution_order(config):
    rng = random.Random(config["seed"])
    order = []
    for repetition in range(config["repetitions"]):
        block = list(itertools.product(range(len(config["conditions"])), config["workloads"]))
        rng.shuffle(block)
        order.extend({"condition": condition, "workload": workload, "repetition": repetition} for condition, workload in block)
    return order


def server_command(config, condition, port):
    command = [config["server"], "--model", config["model"], "--host", "127.0.0.1", "--port", str(port),
               "-ngl", "0", "--threads", str(condition["threads"]), "--threads-batch", str(condition["batch_threads"]),
               "--server-compute-profile-mode", condition["profile"], "--ctx-size", str(config["ctx_size"]),
               "--batch-size", str(config["batch_size"]), "--ubatch-size", str(config["ubatch_size"]),
               "--parallel", str(config["slots"]), "--cont-batching", "--slots", "--no-context-shift", "--no-ui", "--offline"]
    for key, flag in CPU_FLAGS.items():
        if key in condition:
            command.extend([flag, str(condition[key])])
    return command


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def existing_servers(binary):
    found = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            executable = (directory / "exe").resolve(strict=True)
            comm = (directory / "comm").read_text().strip()
            if executable == Path(binary).resolve() or comm == "llama-server":
                found.append({"pid": int(directory.name), "executable": str(executable)})
        except (OSError, RuntimeError):
            continue
    return found


def json_request(port, method, path, payload=None, timeout=2):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    deadline = time.monotonic() + timeout
    timer = None
    try:
        connection.connect()
        wire = connection.sock

        def abort():
            with contextlib.suppress(OSError):
                wire.shutdown(socket.SHUT_RDWR)

        timer = threading.Timer(max(0, deadline - time.monotonic()), abort)
        timer.daemon = True
        timer.start()
        connection.request(method, path, body=json.dumps(payload) if payload is not None else None,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {body[:512]!r}")
        return json.loads(body)
    finally:
        if timer:
            timer.cancel()
        connection.close()


class Server:
    def __init__(self, command, port, log_path, cleanup_timeout=5, env=None):
        self.command, self.port, self.log_path = command, port, log_path
        self.cleanup_timeout, self.env = cleanup_timeout, env
        self.process = None
        self.log = None
        self.cleanup = None

    def start(self, timeout, cancel):
        self.log = self.log_path.open("wb")
        self.process = subprocess.Popen(self.command, stdout=self.log, stderr=subprocess.STDOUT,
                                        start_new_session=True, env=self.env)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancel.is_set():
                raise InterruptedError("cancelled during startup")
            if self.process.poll() is not None:
                raise RuntimeError(f"server exited: {self.process.returncode}")
            try:
                json_request(self.port, "GET", "/health", timeout=min(0.5, max(0.01, deadline - time.monotonic())))
                if self.process.poll() is None:
                    return
            except (OSError, ValueError, RuntimeError, http.client.HTTPException):
                pass
            cancel.wait(0.05)
        raise TimeoutError("server readiness deadline exceeded")

    def stop(self):
        if self.process is None:
            if self.log:
                self.log.close()
            return
        process = self.process
        forced = False
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=self.cleanup_timeout)
        except subprocess.TimeoutExpired:
            forced = True
        # Also stop descendants if the leader exited first.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=self.cleanup_timeout)
        self.log.close()
        deadline = time.monotonic() + self.cleanup_timeout
        while True:
            live = []
            for stat in Path("/proc").glob("[0-9]*/stat"):
                try:
                    text = stat.read_text()
                    fields = text[text.rfind(")") + 2:].split()
                    if int(fields[2]) == process.pid and fields[0] != "Z":
                        live.append(int(stat.parent.name))
                except (OSError, ValueError, IndexError):
                    continue
            if not live:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"process group still has live members: {live}")
            time.sleep(0.01)
        self.cleanup = {"pid": process.pid, "returncode": process.returncode, "forced_leader_kill": forced,
                        "leader_reaped": True, "live_group_members": live}


def token_ids(data):
    if data.get("stop") or "prompt_progress" in data:
        return []
    tokens = data.get("tokens", [])
    if not isinstance(tokens, list) or any(type(t) is not int or t < 0 for t in tokens):
        raise ValueError("invalid streamed token IDs")
    return tokens


def stream_request(port, payload, role, raw_path, timeout, cancel, deadline_ns=None, on_tokens=None):
    start = time.monotonic_ns()
    deadline_ns = min(deadline_ns or start + int(timeout * 1e9), start + int(timeout * 1e9))
    record = {"role": role, "payload": payload, "start_ns": start, "events": [], "status": "failed", "raw_sse": str(raw_path)}
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=max(0.001, (deadline_ns - start) / 1e9))
    finished = threading.Event()
    expired = threading.Event()
    watchdog = None
    try:
        raw_path.touch(exist_ok=False)
        if cancel.is_set():
            raise InterruptedError("request cancelled before connect")
        connection.connect()
        wire = connection.sock

        def abort():
            while not finished.wait(0.02):
                if cancel.is_set() or time.monotonic_ns() >= deadline_ns:
                    expired.set()
                    with contextlib.suppress(OSError):
                        wire.shutdown(socket.SHUT_RDWR)
                    return

        watchdog = threading.Thread(target=abort, daemon=True)
        watchdog.start()
        connection.request("POST", "/completion", body=json.dumps(payload), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        record.update(headers_ns=time.monotonic_ns(), http_status=response.status, headers=response.getheaders())
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {response.read(4096)!r}")
        if "text/event-stream" not in response.getheader("Content-Type", ""):
            raise ValueError("response is not SSE")
        frame = []
        with raw_path.open("w", buffering=1024 * 1024) as raw_file:
            while True:
                try:
                    line = response.readline(1024 * 1024 + 1)
                except Exception:
                    if frame:
                        raw_file.write(json.dumps({"t_ns": time.monotonic_ns(), "incomplete": True, "raw_b64": base64.b64encode(b"".join(frame)).decode()}) + "\n")
                    raise
                now = time.monotonic_ns()
                if not line:
                    if frame:
                        raw_file.write(json.dumps({"t_ns": now, "incomplete": True, "raw_b64": base64.b64encode(b"".join(frame)).decode()}) + "\n")
                    break
                frame.append(line)
                if len(line) > 1024 * 1024 or sum(map(len, frame)) > 4 * 1024 * 1024:
                    raw_file.write(json.dumps({"t_ns": now, "incomplete": True, "raw_b64": base64.b64encode(b"".join(frame)).decode()}) + "\n")
                    raise ValueError("SSE frame size limit exceeded")
                if line not in (b"\n", b"\r\n"):
                    continue
                raw = b"".join(frame)
                frame = []
                raw_file.write(json.dumps({"t_ns": now, "raw_b64": base64.b64encode(raw).decode()}) + "\n")
                fields = [part[5:].lstrip(b" ").rstrip(b"\r\n") for part in raw.splitlines(keepends=True) if part.startswith(b"data:")]
                if not fields:
                    continue
                body = b"\n".join(fields)
                if body == b"[DONE]":
                    break
                data = json.loads(body)
                if not isinstance(data, dict) or "error" in data:
                    raise ValueError(f"invalid completion event: {data!r}")
                tokens = token_ids(data)
                record["events"].append({"t_ns": now, "data": data})
                if tokens and on_tokens:
                    on_tokens(len(tokens))
                if data.get("stop"):
                    record["status"] = "ok"
                    break
        if record["status"] != "ok":
            raise ValueError("stream ended without terminal completion event")
        final = record["events"][-1]["data"]
        count = sum(len(token_ids(e["data"])) for e in record["events"])
        record["output_tokens"] = final.get("tokens_predicted")
        if type(record["output_tokens"]) is not int or count != record["output_tokens"]:
            raise ValueError(f"output count mismatch: streamed={count}, terminal={record['output_tokens']}")
        if count != payload["n_predict"] or final.get("truncated") or final.get("stop_type") != "limit":
            raise ValueError("unexpected output length, truncation, or stop reason")
        if expired.is_set() or time.monotonic_ns() >= deadline_ns:
            raise TimeoutError("request deadline exceeded")
    except Exception as exc:
        record["status"] = "cancelled" if cancel.is_set() else "timeout" if expired.is_set() or isinstance(exc, TimeoutError) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        finished.set()
        connection.close()
        if watchdog:
            watchdog.join(timeout=1)
        record["end_ns"] = time.monotonic_ns()
        record["streamed_tokens"] = sum(len(token_ids(e["data"])) for e in record["events"])
    return record


def percentile(values, fraction=0.95):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def request_metrics(request):
    events = [(e["t_ns"], token_ids(e["data"])) for e in request["events"]]
    events = [(t, tokens) for t, tokens in events if tokens]
    gaps = [(b[0] - a[0]) / 1e6 for a, b in zip(events, events[1:])]
    intervals = [(b[0] - a[0]) / 1e6 for a, b in zip(events, events[1:]) if len(a[1]) == len(b[1]) == 1]
    tail = (request["end_ns"] - events[-1][0]) / 1e6 if events else None
    return {
        "ttft_ms": (events[0][0] - request["start_ns"]) / 1e6 if events else None,
        "completion_ms": (request["end_ns"] - request["start_ns"]) / 1e6,
        "valid_token_intervals_ms": intervals, "p95_token_interval_ms": percentile(intervals),
        "max_token_interval_ms": max(intervals, default=None), "max_event_gap_ms": max(gaps, default=None),
        "terminal_silence_ms": tail, "grouped_events": sum(len(tokens) > 1 for _, tokens in events),
        "interval_coverage": len(intervals) / (sum(len(tokens) for _, tokens in events) - 1) if sum(len(tokens) for _, tokens in events) > 1 else None,
    }


def overlap_evidence(requests, observations=()):
    long = next((r for r in requests if r["role"] == "long_prefill"), None)
    if long is None:
        return None
    progress = [e for e in long["events"] if "prompt_progress" in e["data"]]
    tokens = [e for e in long["events"] if token_ids(e["data"])]
    proofs = []
    if progress and tokens:
        admission, first_output = progress[0]["t_ns"], tokens[0]["t_ns"]
        for request in requests:
            if request["role"] == "long_prefill":
                continue
            arrivals = [e["t_ns"] for e in request["events"] if token_ids(e["data"])]
            # A decode token on each side of admission rules out queued-only overlap.
            valid = any(t < admission for t in arrivals) and any(admission < t < first_output for t in arrivals)
            short_id, long_id = request["payload"]["id_slot"], long["payload"]["id_slot"]
            active = []
            for observation in observations:
                observed_slots = observation.get("slots")
                if not isinstance(observed_slots, list):
                    continue
                slots = {slot["id"]: slot for slot in observed_slots
                         if isinstance(slot, dict) and type(slot.get("id")) is int}
                short_slot, long_slot = slots.get(short_id, {}), slots.get(long_id, {})
                next_token = short_slot.get("next_token")
                if isinstance(next_token, list) and len(next_token) == 1:
                    next_token = next_token[0]
                decoded = next_token.get("n_decoded") if isinstance(next_token, dict) else None
                processed = long_slot.get("n_prompt_tokens_processed")
                if (short_slot.get("is_processing") is True and type(decoded) is int and decoded > 0
                        and long_slot.get("is_processing") is True
                        and type(processed) is int and 0 < processed < len(long["payload"]["prompt"])):
                    active.append(observation["end_ns"])
            proofs.append({"role": request["role"], "overlap": valid and bool(active), "admission_ns": admission,
                           "long_first_token_ns": first_output, "simultaneous_active_slot_snapshots_ns": active})
    expected = len(requests) - 1
    return {"valid": len(proofs) == expected and all(p["overlap"] for p in proofs), "proofs": proofs,
            "definition": "each short emits before and during long prefill; /slots also shows both active, short decoded > 0 and long prompt partially processed"}


def trial_metrics(requests, server_cpu, client_cpu, elapsed_s, observations=()):
    metrics = [request_metrics(r) for r in requests]
    p95s = [m["p95_token_interval_ms"] for m in metrics]
    decode_p95s = [m["p95_token_interval_ms"] for r, m in zip(requests, metrics) if r["role"].startswith("decode_")]
    output = sum(r.get("output_tokens") or 0 for r in requests)
    good = all(r["status"] == "ok" for r in requests) and server_cpu is not None
    overlap = overlap_evidence(requests, observations)
    good = good and (overlap is None or overlap["valid"])
    return {
        "requests": metrics, "overlap": overlap, "valid": good, "elapsed_s": elapsed_s,
        "server_cpu_s": server_cpu, "client_cpu_s": client_cpu,
        "output_tokens": output,
        "worst_request_p95_interval_ms": max(p95s) if p95s and all(p is not None for p in p95s) else None,
        "worst_decode_request_p95_interval_ms": max(decode_p95s) if decode_p95s and all(p is not None for p in decode_p95s) else None,
        "max_stall_ms": max((m["max_event_gap_ms"] for m in metrics if m["max_event_gap_ms"] is not None), default=None),
        "throughput_tokens_s": output / elapsed_s if good and elapsed_s > 0 else None,
        "cpu_s_per_output_token": server_cpu / output if good and output and server_cpu is not None else None,
        "client_cpu_s_per_output_token": client_cpu / output if good and output else None,
    }


def make_prompts(port, config):
    text = " fixed benchmark token sequence"
    plain = json_request(port, "POST", "/tokenize", {"content": text, "add_special": False})["tokens"]
    special = json_request(port, "POST", "/tokenize", {"content": text, "add_special": True})["tokens"]
    if not plain or special[-len(plain):] != plain:
        raise ValueError("tokenizer does not support the reusable prefix probe")
    prefix = special[:-len(plain)]

    def exact(length):
        if len(prefix) > length:
            raise ValueError("special prefix exceeds prompt length")
        return prefix + (plain * math.ceil((length - len(prefix)) / len(plain)))[:length - len(prefix)]

    return {"text": text, "plain": plain, "special": special,
            "short": exact(config["prompt_tokens"]), "long": exact(config["long_prompt_tokens"])}


def workload(server, config, name, prompts, directory, cancel):
    directory.mkdir()
    requests = []
    observations = []
    deadline = time.monotonic_ns() + int(config["trial_timeout_s"] * 1e9)
    cpu_start = cpu_seconds(server.process.pid)
    client_start, start = time.process_time(), time.monotonic_ns()
    count = int(name[1:]) if name != "pp" else 1
    mixed = name.startswith("m")
    barrier = threading.Barrier(count)
    signals = [threading.Event() for _ in range(count)]

    def one(index, long=False):
        role = "long_prefill" if long else "prompt_only" if name == "pp" else f"decode_{index}"
        # Head64 needs four consecutive Decode slots and a non-adjacent Prefill slot.
        slot_id = (0 if long else index + 1) if name == "m4" else index
        payload = {"prompt": prompts["long" if long else "short"],
                   "n_predict": config["long_output_tokens"] if long else 1 if name == "pp" else config["output_tokens"],
                   "stream": True, "return_tokens": True, "return_progress": mixed,
                   "cache_prompt": False, "ignore_eos": True, "temperature": 0, "seed": config["request_seed"], "id_slot": slot_id}
        received = 0

        def on_tokens(n):
            nonlocal received
            received += n
            if received >= config["inject_after_tokens"]:
                signals[index].set()

        if not long:
            barrier.wait(timeout=config["request_timeout_s"])
        return stream_request(server.port, payload, role, directory / f"{role}.sse.jsonl",
                              config["request_timeout_s"], cancel, deadline, on_tokens if not long else None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=count + int(mixed)) as executor:
        futures = [executor.submit(one, i) for i in range(count)]
        if mixed:
            while not all(s.is_set() for s in signals):
                if cancel.is_set() or time.monotonic_ns() >= deadline or any(f.done() for f in futures):
                    break
                cancel.wait(0.01)
            if all(s.is_set() for s in signals) and not cancel.is_set():
                futures.append(executor.submit(one, count, True))
                while not all(f.done() for f in futures) and not cancel.is_set() and time.monotonic_ns() < deadline:
                    observation = {"start_ns": time.monotonic_ns()}
                    try:
                        observation["slots"] = json_request(server.port, "GET", "/slots", timeout=min(0.2, max(0.001, (deadline - time.monotonic_ns()) / 1e9)))
                    except Exception as exc:
                        observation["error"] = f"{type(exc).__name__}: {exc}"
                    observation["end_ns"] = time.monotonic_ns()
                    observations.append(observation)
                    cancel.wait(0.02)
            else:
                requests.append({"role": "long_prefill", "status": "cancelled" if cancel.is_set() else "not_started",
                                 "error": "decode trigger not reached while all decoders active", "events": [],
                                 "start_ns": time.monotonic_ns(), "end_ns": time.monotonic_ns()})
        requests.extend(f.result() for f in futures)
    end, client_end = time.monotonic_ns(), time.process_time()
    try:
        server_cpu = cpu_seconds(server.process.pid) - cpu_start
    except OSError:
        server_cpu = None
    result = {"requests": requests, "slot_observations": observations, "start_ns": start, "end_ns": end,
              "metrics": trial_metrics(requests, server_cpu, client_end - client_start, (end - start) / 1e9, observations)}
    statuses = {r["status"] for r in requests}
    result["status"] = "cancelled" if "cancelled" in statuses else "timeout" if "timeout" in statuses else "failed" if statuses != {"ok"} else "invalid_overlap" if not result["metrics"]["valid"] else "ok"
    if server_cpu is None and statuses == {"ok"}:
        result.update(status="failed", error="server CPU time unavailable")
        result["metrics"]["valid"] = False
    write_json(directory / "result.json", result)
    return result


def mapped_library_name(path):
    return Path(path.removesuffix(" (deleted)")).name


def loaded_libraries(pid):
    paths = set()
    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6:
            continue
        path = fields[5]
        if path.startswith("/") and re.search(r"\.so(?:\.[0-9A-Za-z._-]+)?$", mapped_library_name(path)):
            paths.add(path)
    result = []
    for path in sorted(paths):
        if path.endswith(" (deleted)"):
            result.append({"path": path, "deleted": True})
            continue
        try:
            result.append({**identity(path), "path": path})
        except OSError as exc:
            result.append({"path": path, "unavailable": str(exc)})
    return result


def run_campaign(config, output, cancel):
    output.mkdir(parents=True, exist_ok=False)
    order = execution_order(config)
    rows = [{**case, "trial": i, "status": "not_started"} for i, case in enumerate(order)]
    write_json(output / "order.json", order)
    write_json(output / "trials.json", rows)
    campaign = {"status": "running"}
    try:
        with Path(f"/tmp/llama-cpu-bench-{os.getuid()}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            write_json(output / "manifest.json", manifest(config))
            for row in rows:
                if cancel.is_set():
                    break
                directory = output / f"trial-{row['trial']:04d}"
                directory.mkdir()
                server = None
                row["start_ns"] = time.monotonic_ns()
                try:
                    conflicts = existing_servers(config["server"])
                    if conflicts:
                        raise RuntimeError(f"model-bearing server may already exist: {conflicts}")
                    port = free_port()
                    command = server_command(config, config["conditions"][row["condition"]], port)
                    env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_")}
                    env.update(config["server_env"])
                    server = Server(command, port, directory / "server.log", config["cleanup_timeout_s"], env)
                    row.update(status="starting", command=command)
                    write_json(output / "trials.json", rows)
                    server.start(config["ready_timeout_s"], cancel)
                    libraries = loaded_libraries(server.process.pid)
                    incomplete_libraries = [library for library in libraries if "sha256" not in library]
                    required_prefixes = ("libllama", "libggml", "libgomp", "libomp", "libiomp5")
                    missing_required_libraries = [
                        library["path"] for library in incomplete_libraries
                        if mapped_library_name(library["path"]).startswith(required_prefixes)
                    ]
                    server_environment = {
                        **process_environment(server.process.pid), "libraries": libraries,
                        "libraries_complete": not incomplete_libraries, "incomplete_libraries": incomplete_libraries,
                        "server_env_overrides": config["server_env"],
                    }
                    if not missing_required_libraries:
                        server_environment["props"] = json_request(port, "GET", "/props")
                    write_json(directory / "server-environment.json", server_environment)
                    if missing_required_libraries:
                        raise RuntimeError(f"required library hash unavailable: {', '.join(missing_required_libraries)}")
                    prompts = make_prompts(port, config)
                    write_json(directory / "prompts.json", prompts)
                    for i in range(config["warmups"]):
                        warmup = workload(server, config, row["workload"], prompts, directory / f"warmup-{i}", cancel)
                        if warmup["status"] != "ok":
                            row.update(status=warmup["status"], error=f"warmup {i}: {warmup['status']}", failed_stage="warmup")
                            break
                    else:
                        measured = workload(server, config, row["workload"], prompts, directory / "measurement", cancel)
                        row.update(status=measured["status"], metrics=measured["metrics"])
                except Exception as exc:
                    row.update(status="cancelled" if cancel.is_set() else "timeout" if isinstance(exc, TimeoutError) else "failed", error=f"{type(exc).__name__}: {exc}")
                finally:
                    if server:
                        try:
                            server.stop()
                            row["cleanup"] = server.cleanup
                        except Exception as exc:
                            row.update(status="failed", cleanup_error=f"{type(exc).__name__}: {exc}")
                    row["end_ns"] = time.monotonic_ns()
                    write_json(output / "trials.json", rows)
                    if row.get("cleanup_error"):
                        raise RuntimeError("cleanup failed; refusing to start another server")
            campaign["status"] = "cancelled" if cancel.is_set() else "complete" if all(r["status"] == "ok" for r in rows) else "completed_with_failures"
    except Exception as exc:
        campaign.update(status="cancelled" if cancel.is_set() else "failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        campaign["counts"] = {status: sum(r["status"] == status for r in rows) for status in sorted({r["status"] for r in rows})}
        write_json(output / "summary.json", campaign)
    return 0 if campaign["status"] == "complete" else 130 if cancel.is_set() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="print order and commands; never start a server")
    mode.add_argument("--run", action="store_true", help="execute on the benchmark host")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.plan:
        print(json.dumps({"config": config, "order": execution_order(config), "commands": [server_command(config, c, 0) for c in config["conditions"]]}, indent=2))
        return 0
    if args.output is None:
        parser.error("--run requires a new --output directory")
    cancel = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: cancel.set())
    return run_campaign(config, args.output.resolve(), cancel)


if __name__ == "__main__":
    sys.exit(main())

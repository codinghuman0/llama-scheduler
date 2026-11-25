#!/usr/bin/env python3
"""Benchmark-host diagnostics only; verbose logs and task sampling invalidate timing comparisons."""

import argparse
import json
import os
import re
import signal
import threading
import time
from pathlib import Path

import runner


def task_snapshot(pid):
    tasks = []
    for path in sorted(Path(f"/proc/{pid}/task").glob("*/stat")):
        try:
            stat = path.read_text()
            fields = stat[stat.rfind(")") + 2:].split()
            tid = int(path.parent.name)
            tasks.append({"tid": tid, "start_ticks": int(fields[19]),
                          "cpu_ticks": int(fields[11]) + int(fields[12]),
                          "allowed_cpus": sorted(os.sched_getaffinity(tid)),
                          "processor": int(fields[36])})
        except (OSError, ValueError, IndexError):
            continue
    return {"t_ns": time.monotonic_ns(), "tasks": tasks}


def wait_for(port, path, predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = runner.json_request(port, "GET", path, timeout=min(1, max(0.01, deadline - time.monotonic())))
        if predicate(value):
            return value
        time.sleep(0.05)
    raise TimeoutError(f"state not reached at {path}")


def pool_diagnostics(path, start, expected):
    with path.open("rb") as log:
        log.seek(start)
        states = [state.decode() for state in re.findall(rb"disposable_threadpool=(yes|no)", log.read())]
    if not states or any(state != expected for state in states):
        raise RuntimeError(f"unexpected steady-state pool diagnostics: {set(states)}")
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--condition", type=int, default=0)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--expect-disposable", choices=("yes", "no"), default="no")
    parser.add_argument("--shutdown-state", choices=("awake", "asleep"), default="awake")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", required=True, help="run models on the benchmark host")
    args = parser.parse_args()
    config = runner.load_config(args.config)
    if args.cycles < 2 or not 0 <= args.condition < len(config["conditions"]):
        parser.error("need at least two cycles and a valid condition index")
    if runner.existing_servers(config["server"]):
        parser.error("an existing model server must be stopped first")
    args.output.mkdir(parents=True, exist_ok=False)
    runner.write_json(args.output / "manifest.json", runner.manifest(config))
    port = runner.free_port()
    command = runner.server_command(config, config["conditions"][args.condition], port)
    command.extend(["--verbose", "--sleep-idle-seconds", "2"])
    env = {k: v for k, v in os.environ.items() if not k.startswith("LLAMA_ARG_")}
    env.update(config["server_env"])
    server = runner.Server(command, port, args.output / "server.log", config["cleanup_timeout_s"], env)
    cancel, stop = threading.Event(), threading.Event()
    phase = "startup"
    sampler = None
    report = {"command": command, "cycles": [], "status": "failed"}

    def interrupt(signum, frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)

    def sample():
        with (args.output / "tasks.jsonl").open("w") as out:
            while not stop.is_set():
                out.write(json.dumps({"phase": phase, **task_snapshot(server.process.pid)}) + "\n")
                stop.wait(0.02)

    try:
        server.start(config["ready_timeout_s"], cancel)
        report["server_environment"] = {**runner.process_environment(server.process.pid),
                                        "libraries": runner.loaded_libraries(server.process.pid)}
        sampler = threading.Thread(target=sample)
        sampler.start()
        for cycle in range(args.cycles):
            phase = f"cycle-{cycle}/wake"
            runner.json_request(port, "POST", "/completion", {"prompt": "Hello", "n_predict": 1},
                                timeout=config["ready_timeout_s"])
            prompts = runner.make_prompts(port, config)
            row = {"cycle": cycle}
            report["cycles"].append(row)
            log_start = server.log_path.stat().st_size
            for repetition in range(2):
                for workload in ("pp", "d1"):
                    phase = f"cycle-{cycle}/repeat-{repetition}/{workload}"
                    directory = args.output / f"cycle-{cycle}-repeat-{repetition}-{workload}"
                    result = runner.workload(server, config, workload, prompts, directory, cancel)
                    if result["status"] != "ok":
                        raise RuntimeError(f"{phase}: {result['status']}")
            phase = f"cycle-{cycle}/cancel"
            request_cancel = threading.Event()
            payload = {"prompt": prompts["short"], "n_predict": config["output_tokens"], "stream": True,
                       "return_tokens": True, "ignore_eos": True, "cache_prompt": False, "temperature": 0}
            result = runner.stream_request(port, payload, "cancel", args.output / f"cancel-{cycle}.sse.jsonl",
                                           config["request_timeout_s"], request_cancel, on_tokens=lambda n: request_cancel.set())
            row["cancel"] = result
            if result["status"] != "cancelled" or not result["events"]:
                raise RuntimeError("request did not cancel after delivering output; increase output_tokens")
            wait_for(port, "/slots", lambda slots: all(not slot["is_processing"] for slot in slots), config["request_timeout_s"])
            phase = f"cycle-{cycle}/after-cancel"
            result = runner.workload(server, config, "d1", prompts, args.output / f"after-cancel-{cycle}", cancel)
            if result["status"] != "ok":
                raise RuntimeError("request after cancellation failed")
            phase = f"cycle-{cycle}/sleep"
            row["sleep"] = wait_for(port, "/props", lambda props: props["is_sleeping"], config["ready_timeout_s"])
            row["sleep_tasks"] = task_snapshot(server.process.pid)
            # The load/warmup logs before log_start are outside the steady-state check.
            row["disposable_states"] = pool_diagnostics(server.log_path, log_start, args.expect_disposable)
        if args.shutdown_state == "awake":
            runner.json_request(port, "POST", "/completion", {"prompt": "Hello", "n_predict": 1},
                                timeout=config["ready_timeout_s"])
        report["shutdown_state"] = runner.json_request(port, "GET", "/props")["is_sleeping"]
        if report["shutdown_state"] != (args.shutdown_state == "asleep"):
            raise RuntimeError("unexpected state before shutdown")
        report["status"] = "ok"
    except (Exception, KeyboardInterrupt) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        stop.set()
        if sampler:
            sampler.join()
        try:
            server.stop()
            report["cleanup"] = server.cleanup
            if server.cleanup and (server.cleanup["forced_leader_kill"] or server.cleanup["returncode"] != 0):
                report.update(status="failed", cleanup_error="server did not exit cleanly on SIGTERM")
        except Exception as exc:
            report.update(status="failed", cleanup_error=f"{type(exc).__name__}: {exc}")
        runner.write_json(args.output / "report.json", report)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

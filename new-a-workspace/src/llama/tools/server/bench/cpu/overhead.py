#!/usr/bin/env python3
"""Measure this client's overhead against a separate, model-free SSE producer."""

import argparse
import concurrent.futures
import itertools
import json
import math
import os
import signal
import sys
import threading
import time
from pathlib import Path

import runner


def run_check(output, events=1000, concurrencies=(1, 4), intervals=(0, 0.001), group_sizes=(1, 4), max_p95_lag_ms=50, cancel=None):
    output.mkdir(parents=True, exist_ok=False)
    cancel = cancel or threading.Event()
    results = []
    for index, (concurrency, interval, group) in enumerate(itertools.product(concurrencies, intervals, group_sizes)):
        if cancel.is_set():
            break
        directory = output / f"case-{index}"
        directory.mkdir()
        port = runner.free_port()
        command = [sys.executable, str(Path(__file__).with_name("fixture_server.py")), "--port", str(port),
                   "--interval", str(interval), "--group-size", str(group)]
        server = runner.Server(command, port, directory / "producer.log")
        case = {"concurrency": concurrency, "interval_s": interval, "group_size": group,
                "events_per_request": events, "status": "failed"}
        try:
            server.start(5, cancel)
            barrier = threading.Barrier(concurrency)

            def request(i):
                barrier.wait(timeout=5)
                return runner.stream_request(port, {"prompt": [1], "n_predict": events * group}, f"decode_{i}",
                                             directory / f"request-{i}.sse.jsonl", max(10, events * interval * 4), cancel)

            server_before = runner.cpu_seconds(server.process.pid)
            client_before, start = time.process_time(), time.monotonic_ns()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                records = list(executor.map(request, range(concurrency)))
            end, client_after = time.monotonic_ns(), time.process_time()
            client_cpu = client_after - client_before
            lags = [(event["t_ns"] - event["data"]["fixture_sent_ns"]) / 1e6
                    for record in records for event in record["events"] if "fixture_sent_ns" in event["data"]]
            wall_s = (end - start) / 1e9
            p95 = runner.percentile(lags)
            passed = all(r["status"] == "ok" for r in records) and len(lags) == events * concurrency and all(lag >= 0 for lag in lags)
            passed = passed and p95 is not None and p95 <= max_p95_lag_ms
            case.update(status="ok" if passed else "failed", wall_s=wall_s, client_cpu_s=client_cpu,
                        producer_cpu_s=runner.cpu_seconds(server.process.pid) - server_before,
                        client_cpu_s_per_event=client_cpu / len(lags) if lags else None,
                        client_cpu_fraction_of_one_core=client_cpu / wall_s,
                        received_events=len(lags), events_per_s=len(lags) / wall_s,
                        lag_p50_ms=runner.percentile(lags, 0.5), lag_p95_ms=p95, lag_max_ms=max(lags, default=None))
            runner.write_json(directory / "requests.json", records)
        except Exception as exc:
            case["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            server.stop()
            case["cleanup"] = server.cleanup
            results.append(case)
            runner.write_json(output / "cases.json", results)
    report = {"model_free": True, "status": "cancelled" if cancel.is_set() else "ok" if all(r["status"] == "ok" for r in results) else "failed",
              "max_p95_lag_ms": max_p95_lag_ms, "cases": results,
              "client": runner.process_environment(os.getpid()),
              "runtime": runner.runtime_env(), "python": sys.version, "runner": runner.identity(runner.__file__),
              "fixture": runner.identity(Path(__file__).with_name("fixture_server.py")),
              "interpretation": "same-host producer timestamp to complete SSE frame receive; includes producer serialization, scheduling, network and client work; not model latency"}
    runner.write_json(output / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events", type=int, default=1000)
    parser.add_argument("--max-p95-lag-ms", type=float, default=50)
    args = parser.parse_args()
    if args.events < 1 or not math.isfinite(args.max_p95_lag_ms) or args.max_p95_lag_ms <= 0:
        parser.error("events and lag budget must be positive")
    cancel = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda signum, frame: cancel.set())
    report = run_check(args.output.resolve(), args.events, max_p95_lag_ms=args.max_p95_lag_ms, cancel=cancel)
    print(json.dumps({"model_free": True, "status": report["status"], "cases": len(report["cases"]), "output": str(args.output.resolve())}))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

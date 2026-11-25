#!/usr/bin/env python3
"""Model-free HTTP/SSE fixture. Never imports or launches llama.cpp."""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.reply(503 if self.server.options.scenario == "unready" else 200, {"status": "ok"})
        elif self.path == "/props":
            self.reply(200, {"fixture": True, "model": None})
        elif self.path == "/slots":
            with self.server.lock:
                slots = list(self.server.active.values())
            self.reply(200, slots)
        else:
            self.reply(404, {})

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/tokenize":
            self.reply(200, {"tokens": ([1] if payload.get("add_special") else []) + [10, 11, 12]})
            return
        options = self.server.options
        scenario = options.scenario
        if scenario == "http_error":
            self.reply(500, {"error": "fixture HTTP failure"})
            return
        if scenario == "disconnect":
            os._exit(9)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        slot_id = payload.get("id_slot", 0)
        try:
            if scenario == "idle":
                time.sleep(2)
                return
            if scenario == "trickle":
                for _ in range(100):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.01)
                return
            if scenario == "malformed":
                self.wfile.write(b"data: not-json\n\n")
                self.wfile.flush()
                return
            if scenario == "sse_error":
                self.event({"error": "fixture SSE failure"})
                return
            if scenario == "truncated":
                self.wfile.write(b"data: {\"tokens\": [1]")
                self.wfile.flush()
                return
            is_long = len(payload["prompt"]) > 256
            if is_long and scenario == "no_overlap":
                time.sleep(0.5)
            with self.server.lock:
                self.server.active[slot_id] = {"id": slot_id, "is_processing": True,
                                              "n_prompt_tokens_processed": len(payload["prompt"]) // 2 if is_long else len(payload["prompt"]),
                                              "next_token": [{"n_decoded": self.server.last_counts.get(slot_id, 0)}]}
            if payload.get("return_progress"):
                self.event({"tokens": [-1], "stop": False, "id_slot": payload.get("id_slot", 0),
                            "prompt_progress": {"processed": 0, "total": len(payload["prompt"]), "cache": 0, "time_ms": 0}})
                if is_long:
                    time.sleep(0.06)
                    self.event({"tokens": [-1], "stop": False, "prompt_progress": {
                        "processed": len(payload["prompt"]), "total": len(payload["prompt"]), "cache": 0, "time_ms": 60}})
            n = payload["n_predict"]
            group = options.group_size
            sent = 0
            self.wfile.write(b": fixture ping\r\n\r\n")
            while sent < n:
                ids = list(range(sent + 100, min(sent + group, n) + 100))
                sent += len(ids)
                with self.server.lock:
                    self.server.active[slot_id] = {"id": slot_id, "is_processing": True,
                                                  "n_prompt_tokens_processed": len(payload["prompt"]), "next_token": [{"n_decoded": sent}]}
                    self.server.last_counts[slot_id] = sent
                self.event({"content": "x" * len(ids), "tokens": ids, "stop": False,
                            "tokens_predicted": sent, "fixture_sent_ns": time.monotonic_ns()})
                if options.interval:
                    time.sleep(options.interval)
            terminal = {"tokens": list(range(100, n + 100)) if scenario == "terminal_tokens" else [],
                        "stop": True, "stop_type": "limit", "tokens_predicted": n + int(scenario == "count_mismatch"),
                        "tokens_evaluated": len(payload["prompt"]), "truncated": False,
                        "timings": {"prompt_n": len(payload["prompt"]), "predicted_n": n}}
            self.event(terminal)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with self.server.lock:
                self.server.active.pop(slot_id, None)

    def event(self, data):
        self.wfile.write(b"data:" + json.dumps(data).encode() + b"\r\n\r\n")
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--scenario", default="normal")
    parser.add_argument("--interval", type=float, default=0.01)
    parser.add_argument("--group-size", type=int, default=1)
    parser.add_argument("--grandchild-pid", type=Path)
    args = parser.parse_args()
    if args.scenario == "startup_exit":
        return 7
    if args.scenario == "ignore_term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if args.grandchild_pid:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        args.grandchild_pid.write_text(str(child.pid))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    server.options = args
    server.lock = threading.Lock()
    server.active = {}
    server.last_counts = {}
    server.serve_forever(poll_interval=0.02)
    return 0


if __name__ == "__main__":
    sys.exit(main())

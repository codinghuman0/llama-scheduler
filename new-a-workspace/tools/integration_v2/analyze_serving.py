#!/usr/bin/env python3
"""Recompute paired serving observations from all completed raw workload visits."""
import argparse
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(path.read_text())


def analyze(directory):
    protocol = read(directory / "protocol.json")
    summary = read(directory / "summary.json")
    if summary["status"] != "SERVING_PASS":
        raise ValueError("A valid complete campaign is required")
    order = protocol["order"]
    trials = read(directory / "trials.json")
    if len(order) != len(trials):
        raise ValueError("Planned and completed trial counts differ")
    profiles = protocol["role_profiles"]
    observations = {}
    directories = set()
    for planned, trial in zip(order, trials):
        if any(value != trial.get(key) for key, value in planned.items()) or trial["status"] != "ok":
            raise ValueError("Failed or misidentified trial")
        if trial["cleanup"]["returncode"] != 0 or trial["cleanup"]["live_group_members"]:
            raise ValueError("Trial has incomplete cleanup")
        raw = trial["raw"]
        if raw in directories or Path(raw).name != raw:
            raise ValueError("Duplicate or invalid raw directory")
        directories.add(raw)
        case = (planned["workload"], planned["repetition"], profiles[planned["condition"]]["profile"])
        if case in observations:
            raise ValueError("Duplicate workload/profile/repetition")
        detail = read(directory / raw / "measured/result.json")
        if detail["status"] != "ok" or not detail["metrics"]["valid"] or detail["metrics"] != trial["measured"]:
            raise ValueError("Invalid measured workload")
        valid_tokens = sum(r["output_tokens"] for r in detail["requests"])
        if not valid_tokens or valid_tokens != detail["metrics"]["output_tokens"]:
            raise ValueError("Output token accounting differs")
        seconds = (detail["end_ns"] - detail["start_ns"]) / 1e9
        recomputed = valid_tokens / seconds
        if abs(recomputed - detail["metrics"]["throughput_tokens_s"]) > 1e-9:
            raise ValueError("Raw timestamp throughput differs")
        observations[case] = {"tokens_per_s": recomputed, "tokens": valid_tokens, "wall_s": seconds,
                              "server_cpu_s": detail["metrics"]["server_cpu_s"],
                              "worst_token_gap_p95_ms": detail["metrics"]["worst_request_p95_interval_ms"],
                              "max_stall_ms": detail["metrics"]["max_stall_ms"],
                              "requests": detail["metrics"]["requests"], "raw": raw}
    result = {}
    count = protocol["config"]["repetitions"]
    for workload in protocol["config"]["workloads"]:
        pairs = []
        for i in range(count):
            control = observations[workload, i, "unified-conservative"]
            research = observations[workload, i, "integrated-runtime-research"]
            if research["tokens"] != control["tokens"]:
                raise ValueError("Paired generated work differs")
            pairs.append({"repetition": i, "control": control, "research": research,
                          "gain_pct": 100 * (research["tokens_per_s"] / control["tokens_per_s"] - 1)})
        result[workload] = {"pairs": pairs, "paired_mean_gain_pct": statistics.mean(r["gain_pct"] for r in pairs)}
    return {"status": "OBSERVATIONS_ONLY", "scope": "AMD, fixed paired plan; no statistical confirmation",
            "build_id": protocol["build"]["build_id"], "workloads": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(analyze(args.result), stream, indent=2)
        stream.write("\n")

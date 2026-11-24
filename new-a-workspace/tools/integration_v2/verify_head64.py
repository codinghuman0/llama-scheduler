#!/usr/bin/env python3
"""Recompute the scoped m4 token equality check from the serving results."""
import argparse
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def compare(control, candidate):
    protocols = [read(directory / "protocol.json") for directory in (control, candidate)]
    a, b = protocols
    for key in ("config", "order", "model_sha256"):
        if a[key] != b[key]:
            raise ValueError(f"Unequal protocol field {key}")
    if a["config"]["workloads"] != ["m4"]:
        raise ValueError("Use the isolated m4 geometry")
    trials = [read(directory / "trials.json") for directory in (control, candidate)]
    if any(len(rows) != 1 or rows[0]["status"] != "ok" for rows in trials):
        raise ValueError("Expected a completed single diagnostic visit for each policy")
    rows = [entries[0] for entries in trials]
    calls = [row["head64_kernel_calls"] for row in rows]
    if calls[0] != 0 or calls[1] <= 0:
        raise ValueError("Missing clean control or actual specialized kernel execution")
    comparison = {"model_sha256": a["model_sha256"], "kernel_layer_calls": calls, "cases": {}}
    for role in ("warmup", "measured"):
        results = [read(directory / row["raw"] / role / "result.json")
                   for directory, row in zip((control, candidate), rows)]
        cases = []
        for left, right in zip(*(result["requests"] for result in results), strict=True):
            if left["role"] != right["role"] or left["payload"] != right["payload"]:
                raise ValueError("The compared streams did not receive the same request")
            tokens = [[token for event in request["events"] if "prompt_progress" not in event["data"]
                       for token in event["data"].get("tokens", [])] for request in (left, right)]
            if any(len(ids) != request["output_tokens"] for ids, request in zip(tokens, (left, right))):
                raise ValueError("The SSE token stream is incomplete")
            first = next((i for i, pair in enumerate(zip(*tokens), 1) if pair[0] != pair[1]), None)
            cases.append({"request": left["role"], "output_tokens": [len(ids) for ids in tokens],
                          "equal": tokens[0] == tokens[1], "first_difference_1_based": first})
        if len(cases) != 5:
            raise ValueError("Expected four Decode requests and one Prefill request")
        comparison["cases"][role] = {"requests": cases,
                                      "cohort_seconds": [result["metrics"]["elapsed_s"] for result in results]}
    comparison["equal"] = all(case["equal"] for role in comparison["cases"].values() for case in role["requests"])
    comparison["builds"] = [p["build"]["build_id"] for p in protocols]
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    result = compare(args.control, args.candidate)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["equal"] else 1)

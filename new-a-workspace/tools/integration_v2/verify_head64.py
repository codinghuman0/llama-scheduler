#!/usr/bin/env python3
"""Recompute the scoped m4 token equality check from the serving results."""
import sys
import json
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cli_ko import ArgumentParser, main_entry


def read(path):
    return json.loads(path.read_text())


def compare(control, candidate):
    protocols = [read(directory / "protocol.json") for directory in (control, candidate)]
    a, b = protocols
    for key in ("config", "order", "model_sha256"):
        if a[key] != b[key]:
            raise ValueError(f"프로토콜 항목이 다릅니다: {key}")
    if a["config"]["workloads"] != ["m4"]:
        raise ValueError("m4 단독 부하 결과를 지정하세요.")
    trials = [read(directory / "trials.json") for directory in (control, candidate)]
    if any(len(rows) != 1 or rows[0]["status"] != "ok" for rows in trials):
        raise ValueError("각 정책에서 정상 완료된 진단 실행 하나가 필요합니다.")
    rows = [entries[0] for entries in trials]
    calls = [row["head64_kernel_calls"] for row in rows]
    if calls[0] != 0 or calls[1] <= 0:
        raise ValueError("대조군 실행 또는 head64 전용 연산의 실행 증거가 없습니다.")
    comparison = {"model_sha256": a["model_sha256"], "kernel_layer_calls": calls, "cases": {}}
    for role in ("warmup", "measured"):
        results = [read(directory / row["raw"] / role / "result.json")
                   for directory, row in zip((control, candidate), rows)]
        cases = []
        for left, right in zip(*(result["requests"] for result in results), strict=True):
            if left["role"] != right["role"] or left["payload"] != right["payload"]:
                raise ValueError("비교하는 두 스트림의 요청이 서로 다릅니다.")
            tokens = [[token for event in request["events"] if "prompt_progress" not in event["data"]
                       for token in event["data"].get("tokens", [])] for request in (left, right)]
            if any(len(ids) != request["output_tokens"] for ids, request in zip(tokens, (left, right))):
                raise ValueError("SSE 응답 토큰이 누락됐습니다.")
            first = next((i for i, pair in enumerate(zip(*tokens), 1) if pair[0] != pair[1]), None)
            cases.append({"request": left["role"], "output_tokens": [len(ids) for ids in tokens],
                          "equal": tokens[0] == tokens[1], "first_difference_1_based": first})
        if len(cases) != 5:
            raise ValueError("Decode 요청 4개와 Prefill 요청 1개가 필요합니다.")
        comparison["cases"][role] = {"requests": cases,
                                      "cohort_seconds": [result["metrics"]["elapsed_s"] for result in results]}
    comparison["equal"] = all(case["equal"] for role in comparison["cases"].values() for case in role["requests"])
    comparison["builds"] = [p["build"]["build_id"] for p in protocols]
    return comparison


def main():
    parser = ArgumentParser(description="m4 실험의 요청별 생성 토큰을 비교합니다.")
    parser.add_argument("control", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    result = compare(args.control, args.candidate)
    print(json.dumps(result, indent=2))
    if not result["equal"]:
        raise ValueError("두 정책의 생성 토큰이 일치하지 않습니다.")


if __name__ == "__main__":
    main_entry(main)

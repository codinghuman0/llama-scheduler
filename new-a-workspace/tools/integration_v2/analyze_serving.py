#!/usr/bin/env python3
"""Recompute paired serving observations from all completed raw workload visits."""
import sys
import json
from pathlib import Path
import statistics


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cli_ko import ArgumentParser, main_entry


def read(path):
    return json.loads(path.read_text())


def analyze(directory):
    protocol = read(directory / "protocol.json")
    summary = read(directory / "summary.json")
    if summary["status"] != "SERVING_PASS":
        raise ValueError("정상 완료한 캠페인의 결과 폴더를 지정하세요.")
    order = protocol["order"]
    trials = read(directory / "trials.json")
    if len(order) != len(trials):
        raise ValueError("계획한 실행 수와 완료한 실행 수가 다릅니다.")
    profiles = protocol["role_profiles"]
    observations = {}
    directories = set()
    for planned, trial in zip(order, trials):
        if any(value != trial.get(key) for key, value in planned.items()) or trial["status"] != "ok":
            raise ValueError("실패했거나 식별자가 잘못된 실행입니다.")
        if trial["cleanup"]["returncode"] != 0 or trial["cleanup"]["live_group_members"]:
            raise ValueError("실험 종료 후 프로세스 정리가 끝나지 않았습니다.")
        raw = trial["raw"]
        if raw in directories or Path(raw).name != raw:
            raise ValueError("원시 데이터 폴더가 중복되거나 이름이 올바르지 않습니다.")
        directories.add(raw)
        case = (planned["workload"], planned["repetition"], profiles[planned["condition"]]["profile"])
        if case in observations:
            raise ValueError("동일한 부하·프로파일·반복 번호가 두 번 기록됐습니다.")
        detail = read(directory / raw / "measured/result.json")
        if detail["status"] != "ok" or not detail["metrics"]["valid"] or detail["metrics"] != trial["measured"]:
            raise ValueError("측정 부하 기록이 올바르지 않습니다.")
        valid_tokens = sum(r["output_tokens"] for r in detail["requests"])
        if not valid_tokens or valid_tokens != detail["metrics"]["output_tokens"]:
            raise ValueError("생성 토큰 집계가 다릅니다.")
        seconds = (detail["end_ns"] - detail["start_ns"]) / 1e9
        recomputed = valid_tokens / seconds
        if abs(recomputed - detail["metrics"]["throughput_tokens_s"]) > 1e-9:
            raise ValueError("타임스탬프로 다시 계산한 처리율이 다릅니다.")
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
                raise ValueError("짝지은 두 실행의 생성량이 다릅니다.")
            pairs.append({"repetition": i, "control": control, "research": research,
                          "gain_pct": 100 * (research["tokens_per_s"] / control["tokens_per_s"] - 1)})
        result[workload] = {"pairs": pairs, "paired_mean_gain_pct": statistics.mean(r["gain_pct"] for r in pairs)}
    return {"status": "OBSERVATIONS_ONLY", "scope": "Fixed paired plan on the recorded host; no statistical confirmation",
            "build_id": protocol["build"]["build_id"], "workloads": result}


def main():
    parser = ArgumentParser(description="서버 벤치마크의 처리율과 짝지은 변화를 재계산합니다.")
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.result)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main_entry(main)

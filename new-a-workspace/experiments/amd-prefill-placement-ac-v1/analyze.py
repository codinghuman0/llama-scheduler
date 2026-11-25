#!/usr/bin/env python3
"""Recalculate cohort metrics and matched contrasts from an AMD placement visit tree."""
import subprocess
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

from measure import P, WS, FIXTURES, contention, read, require, save, scx, schedule, sha
from intel_experiment import payload_for, validate_body
from cli_ko import ArgumentParser, main_entry


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def loaded(path, effective, manifest, policy):
    witness = read(path)
    real = {Path(row["path"]).name: row["sha256"] for row in witness["loaded_libraries"]
            if Path(row["path"]).name.startswith(("libggml", "libllama", "libmtmd"))}
    require(real == {n: h for n, h in manifest["artifacts"].items() if n != "llama-server"}, "로드된 라이브러리 해시가 다릅니다.")
    workers = witness["workers"]
    require(workers and all(w["scheduler"] == policy and w["cpus"] == effective["cpus"] for w in workers.values()),
            "실제 스레드 정책 또는 CPU 범위가 다릅니다.")


def check_kernel(path, spec, identity, summary, effective, protocol):
    arm = spec["arm"]
    if arm == "linux":
        require(summary["scheduler"] == "SCHED_OTHER" and summary["kernel_state_delivery"] == "NOT_RUN",
                "Linux 대조군의 실제 스케줄러가 다릅니다.")
        return None
    cp = path / "checkpoint"
    checkpoint, stats = read(cp / "checkpoint.json"), read(cp / "scheduler-stats.json")
    obj = f"lite/{arm}/full_object.bpf.o"
    require(checkpoint["policy"] == arm and checkpoint["object_sha256"] == identity["scheduler"][obj] and
            checkpoint["variant"] == "lite" and stats["instrumentation_mode"] == "LITE", "커널 스케줄러의 오브젝트 또는 계측 모드가 다릅니다.")
    require((cp / "loader-exit.txt").read_text().split() == ["0", "0"] and stats["live_monitor"]["status"] == "PASS"
            and not stats["live_monitor"]["failures"] and stats["live_monitor"]["samples"] > 0, "loader 또는 모니터 실행이 실패했습니다.")
    require(stats["events_export_error"] == 0 and
            all(not (r["tracking_failures"] or r["mask_violations"] or r["events_dropped"]) for r in stats["cpus"]),
            "CPU 마스크, 작업 추적 또는 이벤트 기록에 실패했습니다.")
    require(sum(r["running"] for r in stats["cpus"]) > 0 and
            not any(r["running"] or r["stopping"] for r in stats["cpus"] if r["cpu"] not in protocol["server_cpus"]),
            "지정한 범위 밖에서 작업이 실행됐습니다.")
    log = (cp / "loader.log").read_text()
    actual = json.loads(re.search(r"^UNIVERSAL_OBJECT_IDENTITY (.+)$", log, re.M)[1])
    receiver = re.search(r"NEWA_STATE_RECEIVER run=(\d+) sequence=(\d+) rejected=(\d+) idle=(\d+) active=(\d+) invalid=(\d+)", log)
    run_id, sequence, rejected, idle, active, invalid = map(int, receiver.groups())
    tgid = re.search(r"registered tgid=(\d+) uid=\d+", log)[1]
    require(tgid in read(path / "run/runtime.json")["workers"] and actual["object_sha256"] == checkpoint["object_sha256"] and
            run_id == effective["run_id"] and sequence and idle and not (rejected or active or invalid),
            "등록된 작업, state-v2 또는 오브젝트 식별자가 다릅니다.")
    result = scx.audit_prefill(checkpoint, stats)
    require((protocol.get("portable") or (not result["p_representatives"] and not any(result["attempts"] + result["hits"]))) and
            result == summary["kernel_handoff"]["prefill_pcore"] and summary["scheduler"] == "SCHED_EXT" and
            summary["kernel_state_delivery"] == "VALID_EVENTS_AND_IDLE_OBSERVED", "커널 배치 기록과 실행 구성이 일치하지 않습니다.")
    return {"status": result["status"], "attempts": sum(result["attempts"]), "hits": sum(result["hits"]),
            "receiver_events": sequence, "idle_events": idle, "monitor_samples": stats["live_monitor"]["samples"]}


def window_metrics(row, response, condition, protocol):
    w = row["window"]
    before, after = w["before"], w["after"]
    wall = (w["http_end_ns"] - w["http_start_ns"]) / 1e9
    require((protocol.get("portable") or before["ac"] == after["ac"] == 1) and
            before["load_clock_ns"] <= w["http_start_ns"] < w["http_end_ns"] <= after["load_clock_ns"], "요청 측정 구간 또는 등록된 전원 조건이 올바르지 않습니다.")
    tokens = sum(len(entry["tokens"]) for entry in response)
    timings = [entry["timings"] for entry in response]
    require(timings == row["request_timings"] and [e["tokens"] for e in response] == row["tokens"] and
            math.isclose(wall, row["elapsed_s"]) and math.isclose(tokens / wall, row["tokens_per_s"]) and
            all(t["prompt_ms"] > 0 and t["predicted_ms"] > 0 and t["predicted_n"] == len(e["tokens"])
                for t, e in zip(timings, response)), "원시 HTTP 지표나 토큰이 기록과 일치하지 않습니다.")
    out = {"generated_tokens": tokens, "prompt_tokens": sum(t["prompt_n"] for t in timings), "wall_s": wall,
           "tps": tokens / wall, "cpu_s": row["cpu_s"], "mean_cores": row["cpu_s"] / wall,
           "request_prefill_tps": 1000 * sum(t["prompt_n"] for t in timings) / sum(t["prompt_ms"] for t in timings),
           "request_decode_tps": 1000 * tokens / sum(t["predicted_ms"] for t in timings)}
    ticks_window = (after["load_clock_ns"] - before["load_clock_ns"]) / 1e9
    out["external_window_excess_ms"] = 1000 * (ticks_window - wall)
    if condition == "cpu25":
        load = contention.metrics(before["load"], after["load"], ticks_window)
        require(load["cpu"] == protocol["cpu25"]["cpu"] and before["load"]["affinity"] == [load["cpu"]]
                and load["policy"] == 0, "백그라운드 작업의 CPU 범위 또는 정책이 다릅니다.")
        out["external_cores"] = load["mean_cpu_cores"]
    else:
        require(before["load"] is None and after["load"] is None, "평상시 조건에 인위적인 부하가 감지됐습니다.")
    left, right = before["threads"], after["threads"]
    for index, name in enumerate(("migrations", "context_switches")):
        out[name] = None
        if left and left.keys() == right.keys():
            deltas = [right[tid][index] - values[index] for tid, values in left.items()]
            require(min(deltas) >= 0, "스레드 카운터가 역행했습니다.")
            out[name] = sum(deltas)
    return out


def audit_visit(base, spec, identity, fixtures, protocol):
    folder = base / f"{spec['condition']}-{spec['block']:02}" / spec["arm"]
    run = folder / "run"
    summary, effective, launch, cleanup = (read(run / name) for name in ("summary.json", "effective.json", "launch.json", "cleanup.json"))
    require(summary["status"] == "COHORT_PASS" and summary["cohorts"] == 2 and cleanup["returncode"] == 0 and
            not cleanup["forced_leader_kill"] and not cleanup["live_group_members"], "실행 또는 프로세스 정리에 실패했습니다.")
    require(launch["model_sha256"] == identity["model_sha256"] == protocol["model_sha256"] and launch["build"] == identity["runtime"],
            "모델 또는 런타임이 바뀌었습니다.")
    require(effective["cpus"] == protocol["server_cpus"] and effective["scheduler"] == summary["scheduler"] and
            all(effective[k] == protocol[k] for k in ("profile", "resources", "pool", "policy", "transport")), "실제 런타임 설정이 다릅니다.")
    kernel = check_kernel(folder, spec, identity, summary, effective, protocol)
    policy = 7 if kernel else 0
    loaded(run / "runtime.json", effective, identity["runtime"], policy)
    config = {k: v for k, v in effective.items() if k not in ("run_id", "scheduler", "relaxed_host_checks")}
    cohorts = read(run / "cohorts.json")
    require([r["fixture"] for r in cohorts] == [spec["cohort"], protocol["secondary_fixture"]], "실험 입력 순서가 다릅니다.")
    visits = {}
    for row in cohorts:
        name = row["fixture"]
        fixture = fixtures[name]
        require(row["payload"] == payload_for(fixture, protocol["tokens_per_request"]), "HTTP 요청 본문이 다릅니다.")
        for kind in ("warmup", "measured"):
            loaded(run / f"{name}-{kind}-runtime.json", effective, identity["runtime"], policy)
            body = validate_body(read(run / f"{name}-{kind}-responses.json"), fixture, protocol["tokens_per_request"])
            metrics = window_metrics(row[kind], body, spec["condition"], protocol)
        require(row["warmup"]["tokens"] == row["measured"]["tokens"], "워밍업과 본 측정의 토큰이 다릅니다.")
        visits[name] = {"token_hash": fingerprint(row["measured"]["tokens"]), "measured": metrics}
    if spec["condition"] == "cpu25":
        require(read(run / "cpu25/cleanup.json")["status"] == "PASS", "부하 프로세스 정리에 실패했습니다.")
    return {"config_hash": fingerprint(config), "kernel": kernel, "fixtures": visits}


def paired(values, cohorts, protocol):
    grouped = [[v for v, cohort in zip(values, cohorts) if cohort == target] for target in protocol["cohorts"]]
    rng = random.Random(protocol["uncertainty"]["seed"])
    draws = sorted(sum(sum(rng.choices(g, k=len(g))) for g in grouped) / len(values)
                   for _ in range(protocol["uncertainty"]["draws"]))
    return {"mean_pct": statistics.mean(values), "lo_pct": draws[int(.025 * len(draws))],
            "hi_pct": draws[int(.975 * len(draws)) - 1], "faster": sum(v > 0 for v in values), "n": len(values),
            "paired_gains_pct": values}


def analyze(base):
    protocol = read(base / "protocol.json")
    if protocol.get("portable"):
        host_keys = {"portable", "device", "server_cpus", "resources", "policy", "power", "scope", "cpu25"}
        require(all(protocol[k] == v for k, v in P.items() if k not in host_keys)
                and protocol["cpu25"] == {**P["cpu25"], "cpu": protocol["server_cpus"][-1]},
                "등록된 측정 설계 또는 cpu25 부하 조건이 바뀌었습니다.")
    else:
        require(protocol == P, "기존 AMD 재현 프로토콜이 변경됐습니다.")
    require(read(base / "schedule.json") == list(schedule(protocol)), "블록 실행 순서가 다릅니다.")
    identity = read(base / "identity.json")
    for path, digest in identity["source_hashes"].items():
        require(not Path(path).is_absolute() and ".." not in Path(path).parts, "허용되지 않은 소스 경로입니다.")
        snapshot = base / "sources" / path
        if snapshot.is_file():
            require(sha(snapshot) == digest, f"저장된 측정 소스가 변경됐습니다 ({path}).")
        elif sha(WS / path) != digest:
            # The first AMD campaign predates the per-run source snapshots.
            ref = "25ab433140eafc6cbb3b259b017c2a9252b37900:new-a-workspace/" + path
            original = subprocess.check_output(["git", "-C", str(WS), "show", ref])
            require(hashlib.sha256(original).hexdigest() == digest, f"과거 측정 소스 해시가 다릅니다 ({path}).")
    fixtures = {row["id"]: row for row in read(FIXTURES)}
    groups = defaultdict(dict)
    receipts = []
    for spec in schedule(protocol):
        visit = audit_visit(base, spec, identity, fixtures, protocol)
        groups[(spec["condition"], spec["block"])][spec["arm"]] = visit
        receipts.append({"visit": spec, **visit})
    cells = {}
    for condition in protocol["conditions"]:
        for kind in ("eight", "single"):
            rows, contrasts, absolute, cohorts = [], {}, {}, []
            for block in range(1, protocol["blocks_per_condition"] + 1):
                arms = groups[(condition, block)]
                cohort = protocol["cohorts"][(block - 1) % 2]
                name = cohort if kind == "eight" else protocol["secondary_fixture"]
                require(len({v["config_hash"] for v in arms.values()}) == 1 and
                        len({v["fixtures"][name]["token_hash"] for v in arms.values()}) == 1, "비교 실행의 설정 또는 생성 토큰이 다릅니다.")
                row = {arm: v["fixtures"][name]["measured"] for arm, v in arms.items()}
                if condition == "cpu25":
                    load = [v["external_cores"] for v in row.values()]
                    spec = protocol["cpu25"]
                    require(min(load) >= spec["min_cores"] and max(load) <= spec["max_cores"] and
                            max(load) - min(load) <= spec["max_within_block_spread"], f"비교 블록의 실제 부하가 허용 범위를 벗어났습니다: {condition}/{kind}/{block}")
                rows.append(row)
                cohorts.append(cohort)
            for arm in ("linux", *scx.PREFILL_PAIR):
                absolute[arm] = {}
                for key in rows[0][arm]:
                    values = [r[arm][key] for r in rows if r[arm][key] is not None]
                    absolute[arm][key] = statistics.mean(values) if values else None
                    if key in ("migrations", "context_switches"):
                        absolute[arm][key + "_n"] = len(values)
            for arm, baseline in protocol["contrasts"]:
                gains = [100 * (r[arm]["tps"] / r[baseline]["tps"] - 1) for r in rows]
                contrasts[f"{arm}/{baseline}"] = paired(gains, cohorts, protocol)
            cells[f"{condition}-{kind}"] = {"absolute_means": absolute, "contrasts": contrasts}
    save(base / "audited-visits.json", receipts)
    result = {"status": "AUDITED", "visits": len(receipts), "measured_http_cohorts": 2 * len(receipts), "cells": cells}
    save(base / "results.json", result)
    return result


def main():
    parser = ArgumentParser(description="측정한 토큰·시간·커널 적용을 검증합니다.")
    parser.add_argument("results", type=Path)
    report = analyze(parser.parse_args().results.resolve())
    print(report["status"], report["visits"], "visits")
    for name, cell in report["cells"].items():
        print(name, {k: round(v["tps"], 3) for k, v in cell["absolute_means"].items()})


if __name__ == "__main__":
    main_entry(main)

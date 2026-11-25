#!/usr/bin/env python3
"""Recalculate cohort metrics and matched contrasts from an AMD placement visit tree."""
import argparse
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


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def loaded(path, effective, manifest, policy):
    witness = read(path)
    real = {Path(row["path"]).name: row["sha256"] for row in witness["loaded_libraries"]
            if Path(row["path"]).name.startswith(("libggml", "libllama", "libmtmd"))}
    require(real == {n: h for n, h in manifest["artifacts"].items() if n != "llama-server"}, "Loaded ELF set differs")
    workers = witness["workers"]
    require(workers and all(w["scheduler"] == policy and w["cpus"] == effective["cpus"] for w in workers.values()),
            "Observed worker policy or affinity differs")


def check_kernel(path, spec, identity, summary, effective):
    arm = spec["arm"]
    if arm == "linux":
        require(summary["scheduler"] == "SCHED_OTHER" and summary["kernel_state_delivery"] == "NOT_RUN",
                "Unexpected Linux arm scheduler")
        return None
    cp = path / "checkpoint"
    checkpoint, stats = read(cp / "checkpoint.json"), read(cp / "scheduler-stats.json")
    obj = f"lite/{arm}/full_object.bpf.o"
    require(checkpoint["policy"] == arm and checkpoint["object_sha256"] == identity["scheduler"][obj] and
            checkpoint["variant"] == "lite" and stats["instrumentation_mode"] == "LITE", "Different kernel arm")
    require((cp / "loader-exit.txt").read_text().split() == ["0", "0"] and stats["live_monitor"]["status"] == "PASS"
            and not stats["live_monitor"]["failures"] and stats["live_monitor"]["samples"] > 0, "Loader/monitor failed")
    require(stats["events_export_error"] == 0 and
            all(not (r["tracking_failures"] or r["mask_violations"] or r["events_dropped"]) for r in stats["cpus"]),
            "Mask, tracking or event export failure")
    require(sum(r["running"] for r in stats["cpus"]) > 0 and
            not any(r["running"] or r["stopping"] for r in stats["cpus"] if r["cpu"] not in P["server_cpus"]),
            "Unexpected running CPU")
    log = (cp / "loader.log").read_text()
    actual = json.loads(re.search(r"^UNIVERSAL_OBJECT_IDENTITY (.+)$", log, re.M)[1])
    receiver = re.search(r"NEWA_STATE_RECEIVER run=(\d+) sequence=(\d+) rejected=(\d+) idle=(\d+) active=(\d+) invalid=(\d+)", log)
    run_id, sequence, rejected, idle, active, invalid = map(int, receiver.groups())
    tgid = re.search(r"registered tgid=(\d+) uid=\d+", log)[1]
    require(tgid in read(path / "run/runtime.json")["workers"] and actual["object_sha256"] == checkpoint["object_sha256"] and
            run_id == effective["run_id"] and sequence and idle and not (rejected or active or invalid),
            "Registration, state-v2 or object identity differs")
    result = scx.audit_prefill(checkpoint, stats)
    require(not result["p_representatives"] and not any(result["attempts"] + result["hits"]) and
            result == summary["kernel_handoff"]["prefill_pcore"] and summary["scheduler"] == "SCHED_EXT" and
            summary["kernel_state_delivery"] == "VALID_EVENTS_AND_IDLE_OBSERVED", "AMD placement evidence differs")
    return {"status": result["status"], "attempts": sum(result["attempts"]), "hits": sum(result["hits"]),
            "receiver_events": sequence, "idle_events": idle, "monitor_samples": stats["live_monitor"]["samples"]}


def window_metrics(row, response, condition):
    w = row["window"]
    before, after = w["before"], w["after"]
    wall = (w["http_end_ns"] - w["http_start_ns"]) / 1e9
    require(before["ac"] == after["ac"] == 1 and
            before["load_clock_ns"] <= w["http_start_ns"] < w["http_end_ns"] <= after["load_clock_ns"], "Invalid window/AC")
    tokens = sum(len(entry["tokens"]) for entry in response)
    timings = [entry["timings"] for entry in response]
    require(timings == row["request_timings"] and [e["tokens"] for e in response] == row["tokens"] and
            math.isclose(wall, row["elapsed_s"]) and math.isclose(tokens / wall, row["tokens_per_s"]) and
            all(t["prompt_ms"] > 0 and t["predicted_ms"] > 0 and t["predicted_n"] == len(e["tokens"])
                for t, e in zip(timings, response)), "Raw HTTP metrics/tokens differ")
    out = {"generated_tokens": tokens, "prompt_tokens": sum(t["prompt_n"] for t in timings), "wall_s": wall,
           "tps": tokens / wall, "cpu_s": row["cpu_s"], "mean_cores": row["cpu_s"] / wall,
           "request_prefill_tps": 1000 * sum(t["prompt_n"] for t in timings) / sum(t["prompt_ms"] for t in timings),
           "request_decode_tps": 1000 * tokens / sum(t["predicted_ms"] for t in timings)}
    ticks_window = (after["load_clock_ns"] - before["load_clock_ns"]) / 1e9
    out["external_window_excess_ms"] = 1000 * (ticks_window - wall)
    if condition == "cpu25":
        load = contention.metrics(before["load"], after["load"], ticks_window)
        require(load["cpu"] == P["cpu25"]["cpu"] and before["load"]["affinity"] == [load["cpu"]]
                and load["policy"] == 0, "Different background CPU envelope")
        out["external_cores"] = load["mean_cpu_cores"]
    else:
        require(before["load"] is None and after["load"] is None, "Unexpected injected load")
    left, right = before["threads"], after["threads"]
    for index, name in enumerate(("migrations", "context_switches")):
        out[name] = None
        if left and left.keys() == right.keys():
            deltas = [right[tid][index] - values[index] for tid, values in left.items()]
            require(min(deltas) >= 0, "Thread counter moved backwards")
            out[name] = sum(deltas)
    return out


def audit_visit(base, spec, identity, fixtures):
    folder = base / f"{spec['condition']}-{spec['block']:02}" / spec["arm"]
    run = folder / "run"
    summary, effective, launch, cleanup = (read(run / name) for name in ("summary.json", "effective.json", "launch.json", "cleanup.json"))
    require(summary["status"] == "COHORT_PASS" and summary["cohorts"] == 2 and cleanup["returncode"] == 0 and
            not cleanup["forced_leader_kill"] and not cleanup["live_group_members"], "Failed visit/cleanup")
    require(launch["model_sha256"] == identity["model_sha256"] == P["model_sha256"] and launch["build"] == identity["runtime"],
            "Model or runtime changed")
    require(effective["cpus"] == P["server_cpus"] and effective["scheduler"] == summary["scheduler"] and
            all(effective[k] == P[k] for k in ("profile", "resources", "pool", "policy", "transport")), "Runtime settings differ")
    kernel = check_kernel(folder, spec, identity, summary, effective)
    policy = 7 if kernel else 0
    loaded(run / "runtime.json", effective, identity["runtime"], policy)
    config = {k: v for k, v in effective.items() if k not in ("run_id", "scheduler", "relaxed_host_checks")}
    cohorts = read(run / "cohorts.json")
    require([r["fixture"] for r in cohorts] == [spec["cohort"], P["secondary_fixture"]], "Unexpected fixture order")
    visits = {}
    for row in cohorts:
        name = row["fixture"]
        fixture = fixtures[name]
        require(row["payload"] == payload_for(fixture, P["tokens_per_request"]), "Different HTTP payload")
        for kind in ("warmup", "measured"):
            loaded(run / f"{name}-{kind}-runtime.json", effective, identity["runtime"], policy)
            body = validate_body(read(run / f"{name}-{kind}-responses.json"), fixture, P["tokens_per_request"])
            metrics = window_metrics(row[kind], body, spec["condition"])
        require(row["warmup"]["tokens"] == row["measured"]["tokens"], "Warmup token mismatch")
        visits[name] = {"token_hash": fingerprint(row["measured"]["tokens"]), "measured": metrics}
    if spec["condition"] == "cpu25":
        require(read(run / "cpu25/cleanup.json")["status"] == "PASS", "Load cleanup failed")
    return {"config_hash": fingerprint(config), "kernel": kernel, "fixtures": visits}


def paired(values, cohorts):
    grouped = [[v for v, cohort in zip(values, cohorts) if cohort == target] for target in P["cohorts"]]
    rng = random.Random(P["uncertainty"]["seed"])
    draws = sorted(sum(sum(rng.choices(g, k=len(g))) for g in grouped) / len(values)
                   for _ in range(P["uncertainty"]["draws"]))
    return {"mean_pct": statistics.mean(values), "lo_pct": draws[int(.025 * len(draws))],
            "hi_pct": draws[int(.975 * len(draws)) - 1], "faster": sum(v > 0 for v in values), "n": len(values),
            "paired_gains_pct": values}


def analyze(base):
    require(read(base / "protocol.json") == P and read(base / "schedule.json") == list(schedule()), "Schedule/protocol changed")
    identity = read(base / "identity.json")
    require(all(sha(WS / path) == digest for path, digest in identity["source_hashes"].items()), "Frozen input files differ")
    fixtures = {row["id"]: row for row in read(FIXTURES)}
    groups = defaultdict(dict)
    receipts = []
    for spec in schedule():
        visit = audit_visit(base, spec, identity, fixtures)
        groups[(spec["condition"], spec["block"])][spec["arm"]] = visit
        receipts.append({"visit": spec, **visit})
    cells = {}
    for condition in P["conditions"]:
        for kind in ("eight", "single"):
            rows, contrasts, absolute, cohorts = [], {}, {}, []
            for block in range(1, P["blocks_per_condition"] + 1):
                arms = groups[(condition, block)]
                cohort = P["cohorts"][(block - 1) % 2]
                name = cohort if kind == "eight" else P["secondary_fixture"]
                require(len({v["config_hash"] for v in arms.values()}) == 1 and
                        len({v["fixtures"][name]["token_hash"] for v in arms.values()}) == 1, "Cross-arm config/token mismatch")
                row = {arm: v["fixtures"][name]["measured"] for arm, v in arms.items()}
                if condition == "cpu25":
                    load = [v["external_cores"] for v in row.values()]
                    spec = P["cpu25"]
                    require(min(load) >= spec["min_cores"] and max(load) <= spec["max_cores"] and
                            max(load) - min(load) <= spec["max_within_block_spread"], f"Unequal load in {condition}/{kind}/{block}")
                rows.append(row)
                cohorts.append(cohort)
            for arm in ("linux", *scx.PREFILL_PAIR):
                absolute[arm] = {}
                for key in rows[0][arm]:
                    values = [r[arm][key] for r in rows if r[arm][key] is not None]
                    absolute[arm][key] = statistics.mean(values) if values else None
                    if key in ("migrations", "context_switches"):
                        absolute[arm][key + "_n"] = len(values)
            for arm, baseline in P["contrasts"]:
                gains = [100 * (r[arm]["tps"] / r[baseline]["tps"] - 1) for r in rows]
                contrasts[f"{arm}/{baseline}"] = paired(gains, cohorts)
            cells[f"{condition}-{kind}"] = {"absolute_means": absolute, "contrasts": contrasts}
    save(base / "audited-visits.json", receipts)
    result = {"status": "AUDITED", "visits": len(receipts), "measured_http_cohorts": 2 * len(receipts), "cells": cells}
    save(base / "results.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    report = analyze(parser.parse_args().results.resolve())
    print(report["status"], report["visits"], "visits")
    for name, cell in report["cells"].items():
        print(name, {k: round(v["tps"], 3) for k, v in cell["absolute_means"].items()})

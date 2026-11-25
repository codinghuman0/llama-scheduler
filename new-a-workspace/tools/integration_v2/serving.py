"""Run the donor SSE workloads against a manifest-verified integration runtime."""
import dataclasses
import re
import shlex
from pathlib import Path

from cli_ko import describe
from intel_experiment import require, save, sha


@dataclasses.dataclass(frozen=True)
class ServingCase:
    profile: str
    workload: str
    repetition: int


def run(args, runner, directory, manifest, configurations, output, cancel,
        environment, role_arguments, mixed_prefill_arguments, verify_loaded, verify_effective, check_host):
    model = args.model.resolve(strict=True)
    config = runner.DEFAULTS | {
        "server": str(directory / "bin/llama-server"), "model": str(model),
        "build_cache": str(directory / "CMakeCache.txt"), "model_description": "Local model identified by SHA256",
        "repetitions": args.repetitions, "workloads": args.workloads, "output_tokens": args.tokens,
        "ctx_size": 8192, "long_prompt_tokens": args.long_prompt_tokens, "long_output_tokens": 8,
        "inject_after_tokens": min(8, args.tokens - 1),
    }
    config["conditions"] = [
        {"threads": c["threads"], "batch_threads": c["batch_threads"], "profile": "phase"} for c in configurations
    ]
    if "m4" in args.workloads:
        require(args.workloads == ["m4"] and args.tokens == 128,
                "m4는 Decode 슬롯 4개와 긴 Prefill 슬롯 1개에서 요청당 128토큰을 생성해야 합니다.")
        config.update(ctx_size=5 * 8192, slots=5, long_prompt_tokens=6144, ubatch_size=128)
    order = runner.execution_order(config)
    model_hash = sha(model)
    save(output / "protocol.json", {"config": config, "order": order, "model_sha256": model_hash,
         "workload_definition": "independent SSE clients; mixed requires observed execution overlap",
         "metric": "actual output tokens divided by cohort wall time", "warmups_per_visit": config["warmups"],
         "role_profiles": configurations, "build": manifest})
    rows = []
    try:
        for index, spec in enumerate(order):
            require(not cancel.is_set(), "서버 실험이 중단됐습니다.")
            check_host()
            configuration = configurations[spec["condition"]]
            case = ServingCase(configuration["profile"], spec["workload"], spec["repetition"])
            dest = output / f"{index:03d}-{case.profile}-{case.workload}"
            dest.mkdir()
            port = runner.free_port()
            cpus = ",".join(map(str, configuration["cpus"]))
            cmd = ["taskset", "-c", cpus, *runner.server_command(config, config["conditions"][spec["condition"]], port),
                   "--threads-http", str(configuration["threads_http"]), "--flash-attn", "on",
                   "--spec-type", "none", "--no-kv-unified", *role_arguments(configuration),
                   *mixed_prefill_arguments(configuration)]
            env = environment(args, configuration, directory)
            require(configuration["transport"] != "trace" and not args.state_log and not args.worker_log,
                    "서버 성능 측정 시 상세 진단을 꺼야 합니다.")
            save(dest / "launch.json", {"argv": cmd, "env": env, "model_sha256": model_hash,
                                        "shell_preview": shlex.join(cmd)})
            log = dest / "server.log"
            server = runner.Server(cmd, port, log, cleanup_timeout=15, env=env)
            row = spec | {"profile": case.profile, "raw": dest.name, "status": "starting"}
            rows.append(row)
            try:
                server.start(config["ready_timeout_s"], cancel)
                pid = server.process.pid
                record = verify_loaded(directory, manifest, configuration, model, pid, runner.loaded_libraries(pid))
                record["startup"] = verify_effective(log.read_text(), configuration)
                save(dest / "runtime.json", record)
                prompts = runner.make_prompts(port, config)
                save(dest / "prompts.json", prompts)
                for role in ("warmup", "measured"):
                    result = runner.workload(server, config, case.workload, prompts, dest / role, cancel)
                    row[role] = result["metrics"]
                    require(result["status"] == "ok", f"{case.workload} {role}: {result['status']}")
                    for request in result["requests"]:
                        terminal = request["events"][-1]["data"]
                        timings = terminal.get("timings") or {}
                        require(timings.get("cache_n") == 0, "응답에 요청 간 캐시 재사용이 없다는 증빙이 없습니다.")
                    check_host()
                verify_loaded(directory, manifest, configuration, model, pid, runner.loaded_libraries(pid))
                row["status"] = "ok"
            except BaseException as error:
                row.update(status="failed", error=describe(error), detail=repr(error))
                raise
            finally:
                server.stop()
                row["cleanup"] = server.cleanup
                if not server.cleanup or server.cleanup["returncode"] != 0 or server.cleanup["forced_leader_kill"]:
                    row.update(status="failed", cleanup_error="서버가 정상 종료되지 않았습니다.")
                if row["status"] == "ok":
                    text = log.read_text()
                    count = sum(map(int, re.findall(r"^NEWA_HEAD64_KERNEL layer_calls=(\d+)$", text, re.M)))
                    row["head64_kernel_calls"] = count
                    if (configuration["mixed_prefill"] == "head64") != (count > 0):
                        row.update(status="failed", error="head64 전용 연산의 실행이 선택한 진단 정책과 다릅니다.")
                save(output / "trials.json", rows)
                require(row.get("cleanup_error") is None, "서버 실험의 프로세스 정리에 실패했습니다.")
            require(row["status"] == "ok", row.get("error", "서버 실험 실행에 실패했습니다."))
            require("mode=phase_batch prefill_reference=1" in log.read_text(), "R 연산 경로의 증빙이 없습니다.")
            print(f"{case.profile} {case.workload} repetition={case.repetition} complete", flush=True)
        require(len(rows) == len(order) and all(row["status"] == "ok" for row in rows), "일부 서버 실험이 완료되지 않았습니다.")
        scope = "head64 geometry diagnostic" if args.workloads == ["m4"] else "exploratory serving characterization"
        save(output / "summary.json", {"status": "SERVING_PASS", "completed": len(rows),
                                      "scope": scope, "cases": rows})
    except BaseException as error:
        save(output / "failure.json", {"status": "SERVING_FAILED", "error": describe(error), "detail": repr(error), "completed": len(rows)})
        raise

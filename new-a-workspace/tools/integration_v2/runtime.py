#!/usr/bin/env python3
"""Build and run the integration-v2 CPU release with recorded source and DSO identity."""
import argparse
from contextlib import nullcontext
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import zipfile

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / "src/llama"
EVIDENCE = WORKSPACE / "experiments/team-integration-v2"
STATE = WORKSPACE / "state/integration-v2"
TOPOLOGY = Path(__file__).resolve().parent / "topology/new_a_hybrid"
SERVING = SOURCE / "tools/server/bench/cpu"

sys.path.insert(0, str(WORKSPACE / "tools"))
from cli_ko import ArgumentParser, describe, main_entry
from intel_experiment import (MODEL_SHA, FIXTURES, clean_env, cpu_list, guard, payload_for,
                              read, require, run_logged, save, sha, tree_hashes, validate_body)


def run_capture(argv):
    return subprocess.check_output(argv, text=True, env=clean_env(), timeout=30).strip()


def input_fingerprint(inputs):
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def source_inputs(backend, markers):
    common = read(EVIDENCE / "cmake-common.json")
    flags = [f for f in common if not f.startswith("-DGGML_OPENMP=")]
    flags += ["-DGGML_OPENMP=" + ("ON" if backend == "openmp" else "OFF"),
              "-DLLAMA_SCX_PHASE_HINT=" + ("ON" if markers != "state-only" else "OFF"),
              "-DLLAMA_SCX_PHASE_TRACE=" + ("ON" if markers == "all" else "OFF")]
    files = tree_hashes(SOURCE)
    header = SOURCE / "ggml/src/ggml-cpu/newa-q4-policy.h"
    require("Keep semantic Prefill on the reference body." in header.read_text(), "R Prefill 기준 연산 경로를 찾을 수 없습니다.")
    return {"schema": 1, "revision": run_capture(["git", "-C", str(SOURCE), "rev-parse", "HEAD"]),
            "source_files": files, "source_lock_sha256": sha(EVIDENCE / "sources.lock.json"),
            "backend": backend, "markers": markers, "isa": "x86-64 + AVX2/FMA/F16C/SSE4.2", "flags": flags,
            "gcc": run_capture(["gcc", "--version"]), "g++": run_capture(["g++", "--version"]),
            "cmake": run_capture(["cmake", "--version"])}


def elf_identity(path):
    with path.open("rb") as stream:
        header = stream.read(20)
    require(header[:6] == b"\x7fELF\x02\x01" and header[18:20] == b"\x3e\x00", "x86-64 ELF 파일이 필요합니다: " + str(path))
    return sha(path)


def seal_build(directory, inputs):
    entries = read(directory / "compile_commands.json")
    commands = "\n".join(row["command"] for row in entries)
    require(all(flag in commands for flag in ("-mavx2", "-mfma", "-mf16c")), "AVX2 백엔드 빌드 옵션이 없습니다.")
    require(not re.search(r"-march=native|-mtune=native|-mavx512|-mavxvnni|-mamx", commands), "다른 CPU에서 지원되지 않는 ISA 옵션이 포함됐습니다.")
    require(("-fopenmp" in commands) == (inputs["backend"] == "openmp"), "OpenMP 빌드 옵션이 일치하지 않습니다.")
    binary = directory / "bin"
    artifacts = {p.name: elf_identity(p) for p in sorted(binary.iterdir())
                 if p.is_file() and not p.is_symlink() and (".so" in p.name or p.name == "llama-server")}
    required = {"libggml-cpu", "libggml-base", "libggml", "libllama", "libllama-common", "libllama-server-impl", "libmtmd"}
    require("llama-server" in artifacts and required <= {name.split(".so")[0] for name in artifacts},
            "빌드 폴더에 필요한 실행 파일 또는 라이브러리가 없습니다.")
    require(source_inputs(inputs["backend"], inputs["markers"]) == inputs, "컴파일 중 소스 또는 빌드 설정이 바뀌었습니다.")
    save(directory / "manifest.json", {"status": "BUILD_PASS", "kind": "integration-v2",
         "build_id": input_fingerprint(inputs), "source_revision": inputs["revision"], "backend": inputs["backend"],
         "markers": inputs["markers"], "r_route": "semantic-prefill-reference", "artifacts": artifacts,
         "compile_commands_sha256": sha(directory / "compile_commands.json")})


def build_runtime(directory, backend, markers, jobs, reuse=False):
    inputs = source_inputs(backend, markers)
    if reuse and directory.exists():
        if (directory / "manifest.json").is_file():
            manifest = verify_build(directory)
            require((manifest["backend"], manifest["markers"]) == (backend, markers),
                    "빌드 캐시의 backend 또는 marker 설정이 다릅니다. NEWA_BUILD_DIR에 다른 경로를 지정하세요.")
            return
        require((directory / "inputs.json").is_file() and read(directory / "inputs.json") == inputs,
                "미완료 빌드의 소스 또는 옵션이 다릅니다. NEWA_BUILD_DIR에 새 경로를 지정하세요.")
    else:
        directory.mkdir(parents=True, exist_ok=False)
    save(directory / "inputs.json", inputs)
    configure = ["cmake", "-S", str(SOURCE), "-B", str(directory), *inputs["flags"]]
    compile_argv = ["cmake", "--build", str(directory), "--target", "llama-server", "-j", str(jobs)]
    save(directory / "commands.json", {"configure": configure, "build": compile_argv})
    run_logged(configure, directory / "configure.log", 120)
    run_logged(compile_argv, directory / "build.log", 1800)
    seal_build(directory, inputs)


def verify_build(directory):
    manifest = read(directory / "manifest.json")
    inputs = read(directory / "inputs.json")
    require(manifest["kind"] == "integration-v2" and manifest["status"] == "BUILD_PASS", "integration-v2 빌드 매니페스트가 올바르지 않습니다.")
    require(manifest["r_route"] == "semantic-prefill-reference" and
            manifest["build_id"] == input_fingerprint(inputs), "빌드 소스 해시가 일치하지 않습니다.")
    current = source_inputs(inputs["backend"], inputs["markers"])
    # A documentation-only commit can reuse the sealed source and compiler inputs.
    current["revision"] = inputs["revision"]
    require(current == inputs, "소스 또는 컴파일러가 달라졌습니다. NEWA_BUILD_DIR에 새 빌드 경로를 지정하세요.")
    require(manifest["compile_commands_sha256"] == sha(directory / "compile_commands.json"), "기록된 컴파일 명령이 달라졌습니다.")
    for name, digest in manifest["artifacts"].items():
        require(Path(name).name == name and elf_identity(directory / "bin" / name) == digest,
                "빌드 산출물이 바뀌었습니다: " + name)
    return manifest


def detect(requested):
    sys.path.insert(0, str(TOPOLOGY))
    try:
        collect = importlib.import_module("collect")
        profiles = importlib.import_module("profiles")
        build_probe = importlib.import_module("build_probe")
    finally:
        sys.path.remove(str(TOPOLOGY))
    # collect.inspect imports this module lazily; it is already resolved above.
    probe = STATE / "cpu-probe"
    if not probe.exists():
        build_probe.build(probe)
    result = collect.inspect(probe / "cpu-probe", requested)
    return result, profiles


def resolve(args, manifest):
    detected, profiles = detect(cpu_list(args.cpus) if args.cpus else None)
    topology = detected["portable_plan"]
    available = topology["cores"]
    reps = [r["representative"] for r in sorted(available, key=lambda r: (r["core_type"] == "E", r["representative"]))]
    research = args.profile == "integrated-runtime-research"
    quota = detected["hardware"]["cgroup"]["cpu_max"]
    quota_workers = None
    if quota and not quota.startswith("max "):
        limit, period = map(int, quota.split())
        quota_workers = limit // period
        require(quota_workers >= 1, "cgroup CPU 할당량이 한 코어 미만입니다.")
    if args.resources == "auto":
        if quota_workers is not None:
            reps = reps[:quota_workers]
        if getattr(args, "reserve_controller", False) and set(reps[:6]) == set(topology["snapshot"]["usable_cpus"]):
            require(len(reps) > 1, "커널 실험에는 서버와 제어용 논리 CPU가 각각 하나 이상 필요합니다.")
            reps = reps[:-1]
        resources = "amd-5-6" if topology["vendor"] == "AMD" and len(reps) >= 6 else (
            "intel-fixed6" if topology["vendor"] == "Intel" and len(reps) >= 6 else "physical")
    else:
        resources = args.resources
    if resources == "intel-4-8":
        require(topology["architecture"] == "INTEL_HYBRID" and topology["physical_p_cores"] == 4 and topology["physical_e_cores"] >= 4,
                "intel-4-8에는 사용 가능한 P코어 4개와 E코어 4개 이상이 필요합니다.")
        proposal = profiles.recommend(detected, e_count=4)
        cpus = proposal["affinity_cpus"]
        compute, batch = 4, 8
    elif resources in ("amd-5-6", "intel-fixed6"):
        require(len(reps) >= 6 and topology["vendor"] == ("AMD" if resources == "amd-5-6" else "Intel"),
                "선택한 프로파일의 CPU 제조사와 사용 가능한 물리 코어 6개 이상이 필요합니다.")
        cpus, compute, batch = sorted(reps[:6]), 5, 6
    else:
        cpus, compute, batch = sorted(reps), len(reps), len(reps)
    if quota_workers is not None:
        require(batch <= quota_workers, "선택한 작업 스레드 수가 cgroup CPU 할당량을 초과합니다.")
    allowed = set(topology["snapshot"]["usable_cpus"])
    require(set(cpus) <= allowed, "선택한 CPU가 프로세스에 허용된 범위를 벗어났습니다.")
    cpuinfo = {}
    for block in Path("/proc/cpuinfo").read_text().strip().split("\n\n"):
        fields = dict(tuple(x.strip() for x in row.split(":", 1)) for row in block.splitlines() if ":" in row)
        if "processor" in fields:
            cpuinfo[int(fields["processor"])] = fields.get("flags", "").split()
    require(all({"avx", "avx2", "fma", "f16c", "sse4_2"} <= set(cpuinfo[c]) for c in cpus), "선택된 CPU에서 AVX2/FMA/F16C/SSE4.2 명령을 모두 사용할 수 없습니다.")
    policy = args.policy or ("pressure" if research and resources == "amd-5-6" else
                              "fixed6" if resources in ("amd-5-6", "intel-fixed6") else "phase-fixed")
    if policy in ("pressure", "fixed5", "fixed6"):
        require((compute, batch) == (5, 6) and len(cpus) == 6, "E 정책은 CPU 6개와 생성/배치 스레드 5/6 구성이 필요합니다.")
    adaptive = None
    if policy == "adaptive":
        require(compute < batch <= len(cpus) <= 32, "적응 정책에는 최대 32개 CPU 범위 안에서 서로 다른 스레드 수 두 가지가 필요합니다.")
        require(args.pressure_threshold is not None and args.pressure_cohort and args.min_prefill_ms,
                "적응 정책의 부하 임계값, 요청 수, 최소 Prefill 시간을 지정하세요.")
        require(0 <= args.pressure_threshold <= 4 and 100 <= args.min_prefill_ms <= 10000,
                "적응 임계값 또는 Prefill 시간이 허용 범위를 벗어났습니다.")
        adaptive = {"threshold": args.pressure_threshold, "cohort": args.pressure_cohort, "min_prefill_ms": args.min_prefill_ms}
    else:
        require(all(v is None for v in (args.pressure_threshold, args.pressure_cohort, args.min_prefill_ms)),
                "부하 보정 옵션은 adaptive 정책에서 사용할 수 있습니다.")
    pool = args.pool or ("roles" if research else "off")
    transport = args.transport or ("state" if research else "off")
    role_cpus = [cpu_list(v) if v else cpus for v in (args.generation_cpus, args.batch_cpus)]
    polls = [args.generation_poll, args.batch_poll]
    priorities = [args.generation_priority, args.batch_priority]
    role_options = bool(args.generation_cpus or args.batch_cpus or args.strict_placement or
                        any(v is not None for v in polls) or "batch" in priorities)
    if role_options:
        require(pool == "roles" and manifest["backend"] == "native",
                "역할별 CPU·폴링·우선순위 설정에는 native 역할별 풀이 필요합니다.")
        require(all(len(mask) >= count and set(mask) <= set(cpus)
                    for mask, count in zip(role_cpus, (compute, batch))),
                "역할별 CPU 범위는 전체 허용 범위 안에 있어야 하고 해당 스레드를 수용해야 합니다.")
        require(policy == "phase-fixed", "역할별 배치에는 고정 phase 프로파일이 필요합니다.")
    require(transport != "scalar" or manifest["markers"] != "state-only", "이 빌드에 scalar 마커가 없습니다.")
    require(transport != "trace" or manifest["markers"] == "all", "이 빌드에는 진단용 trace 기능이 없습니다.")
    require(not args.state_log or transport == "state", "상태 진단에는 state 전송이 필요합니다.")
    if args.native_barrier == "park":
        require(manifest["backend"] == "native", "park 대기는 native CPU 백엔드에서 사용할 수 있습니다.")
    else:
        require(args.barrier_phase == "all", "phase별 spin 시간을 설정하려면 park barrier를 선택하세요.")
    if args.mixed_prefill == "head64":
        require(manifest["backend"] == "native" and compute == batch == 6 and policy == "phase-fixed",
                "head64에는 native 백엔드와 6/6 phase-fixed 프로파일이 필요합니다.")
        require(args.action == "doctor" or (args.action == "serve-bench" and args.workloads == ["m4"]),
                "head64 진단에는 m4 부하를 선택하세요.")
    return {"profile": args.profile, "resources": resources, "policy": policy, "pool": pool, "transport": transport,
            "cpus": cpus, "threads": compute, "batch_threads": batch, "threads_http": 8, "topology": detected,
            "backend": manifest["backend"], "r_route": manifest["r_route"], "scheduler": "SCHED_OTHER",
            "adaptive": adaptive, "mixed_prefill": args.mixed_prefill, "relaxed_host_checks": args.relaxed_host_checks,
            "native_barrier": args.native_barrier if manifest["backend"] == "native" else "not-applicable",
            "barrier_phase": args.barrier_phase,
            "role_affinity": role_cpus, "role_polls": polls, "role_priorities": priorities, "role_options": role_options,
            "role_strict": args.strict_placement, "run_id": secrets.randbits(63) or 1}


def environment(args, effective, directory):
    env = clean_env() | {
        "LD_LIBRARY_PATH": str(directory / "bin"), "OMP_DYNAMIC": "FALSE",
        "OMP_NUM_THREADS": str(effective["batch_threads"]), "GGML_NEWA_POOL": effective["pool"],
        "GGML_NEWA_Q4_TILE32": "phase_batch", "GGML_NEWA_Q6_BATCH": "phase_batch",
        "GGML_NEWA_PREFILL_ATTN": "off", "GGML_NEWA_REPACK_PAGES": "huge",
        "NEWA_DECODE_RESOURCE": "off" if effective["policy"] == "phase-fixed" else effective["policy"],
        "NEWA_PHASE_TRANSPORT": effective["transport"],
    }
    if effective["transport"] == "state":
        env["NEWA_STATE_RUN_ID"] = str(effective["run_id"])
    if effective["adaptive"]:
        tuning = effective["adaptive"]
        env.update(NEWA_ADAPTIVE_THRESHOLD=str(tuning["threshold"]), NEWA_ADAPTIVE_COHORT=str(tuning["cohort"]),
                   NEWA_ADAPTIVE_PREFILL_MS=str(tuning["min_prefill_ms"]))
    if args.state_log:
        env["NEWA_STATE_LOG"] = "1"
    if effective["native_barrier"] == "park":
        env.update(GGML_NEWA_BARRIER="park", GGML_NEWA_PHASE_BARRIER=effective["barrier_phase"])
    if args.worker_log and effective["backend"] == "openmp":
        env.update(OMP_DISPLAY_AFFINITY="TRUE", OMP_AFFINITY_FORMAT="NEWA_TEAM pid=%P team=%N index=%n native=%i")
    return env


def separate_role_pools(effective):
    masks = effective["role_affinity"]
    polls = [50 if v is None else v for v in effective["role_polls"]]
    priorities = effective["role_priorities"]
    return effective["pool"] == "roles" and (
        effective["threads"] != effective["batch_threads"] or masks[0] != masks[1] or
        polls[0] != polls[1] or priorities[0] != priorities[1]
    )


def verify_loaded(directory, manifest, effective, model, pid, libraries):
    binary = directory / "bin"
    require(Path(f"/proc/{pid}/exe").resolve() == binary / "llama-server", "실행 중인 서버 파일이 빌드와 다릅니다.")
    expected = {str(binary / name): digest for name, digest in manifest["artifacts"].items() if name != "llama-server"}
    project = {row["path"]: row.get("sha256") for row in libraries
               if Path(row["path"]).name.startswith(("libggml", "libllama", "libmtmd"))}
    require(project == expected, "서버가 로드한 공유 라이브러리가 통합 빌드와 다릅니다.")
    loaded_openmp = any(Path(row["path"]).name.startswith(("libgomp", "libomp", "libiomp")) for row in libraries)
    require(loaded_openmp == (effective["backend"] == "openmp"), "로드된 OpenMP 라이브러리가 빌드 설정과 다릅니다.")
    maps = Path(f"/proc/{pid}/maps").read_text().splitlines()
    require(any(len(fields := line.split(maxsplit=5)) == 6 and fields[5] == str(model) for line in maps), "지정한 모델이 서버에 매핑되지 않았습니다.")
    workers = {}
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            tid = int(task.name)
            workers[task.name] = {"cpus": sorted(os.sched_getaffinity(tid)), "scheduler": os.sched_getscheduler(tid)}
        except ProcessLookupError:
            continue
    policy = 7 if effective["scheduler"] == "SCHED_EXT" else os.SCHED_OTHER
    possible_masks = {tuple(effective["cpus"])}
    if effective["role_options"]:
        possible_masks.update(tuple(mask) for mask in effective["role_affinity"])
        if effective["role_strict"]:
            possible_masks.update((c,) for mask in effective["role_affinity"] for c in mask)
    priorities = effective["role_priorities"]
    batch_workers = 0
    policies = {policy}
    if "batch" in priorities:
        require(policy == os.SCHED_OTHER, "native 배치 우선순위는 기본 Linux 스케줄러에서 사용할 수 있습니다.")
        threads = [effective["threads"], effective["batch_threads"]]
        roles = 2 if separate_role_pools(effective) else 1
        batch_workers = sum(threads[i] - 1 for i in range(roles) if priorities[i] == "batch")
        policies.add(os.SCHED_BATCH)
    require(workers and all(tuple(v["cpus"]) in possible_masks and v["scheduler"] in policies for v in workers.values()),
            "작업 스레드의 스케줄링 정책 또는 CPU 마스크가 예상과 다릅니다.")
    require(str(pid) in workers and workers[str(pid)]["scheduler"] == policy and
            sum(v["scheduler"] == os.SCHED_BATCH for v in workers.values()) == batch_workers,
            "역할별 스레드 또는 그래프 호출자의 우선순위가 설정과 다릅니다.")
    return {"loaded_libraries": libraries, "workers": workers, "model": str(model)}


def verify_effective(log, effective):
    lines = [line.strip() for line in log.splitlines() if line.startswith("NEWA_INTEGRATION_V2 ")]
    separate = separate_role_pools(effective)
    expected = (f"NEWA_INTEGRATION_V2 pool={effective['pool']} attached={int(effective['pool'] != 'off')} "
                f"separate={int(separate)} transport={effective['transport']} "
                f"generation={effective['threads']} batch={effective['batch_threads']}")
    require(lines and all(line == expected for line in lines), "서버의 시작 설정이 요청과 다릅니다.")
    priorities = effective["role_priorities"]
    if "batch" in priorities:
        signature = tuple(str(-int(v == "batch")) for v in priorities)
        reported = re.findall(r"^NEWA_ROLE_PRIORITY generation=(-?\d+) batch=(-?\d+)$", log, re.M)
        require(reported and all(row == signature for row in reported), "역할별 우선순위가 요청과 다릅니다.")
    mixed = re.findall(r"^NEWA_MIXED_PREFILL_POLICY effective=(\w+)$", log, re.M)
    require(mixed and all(value == effective["mixed_prefill"] for value in mixed),
            "서버의 혼합 Prefill 정책이 요청과 다릅니다.")
    if effective["native_barrier"] == "park":
        barriers = re.findall(r"^NEWA_BARRIER init mode=(\d+) ", log, re.M)
        require(barriers and set(barriers) == {"1"}, "native park barrier가 적용되지 않았습니다.")
    require(not re.search(r"failed to set (?:thread )?(?:priority|affinity)", log),
            "런타임이 역할별 CPU 자원 적용 실패를 보고했습니다.")
    return lines


def role_arguments(effective):
    if not effective["role_options"]:
        return []
    result = []
    for suffix, mask, poll, priority in zip(("", "-batch"), effective["role_affinity"],
                                           effective["role_polls"], effective["role_priorities"]):
        result += ["--cpu-mask" + suffix, hex(sum(1 << cpu for cpu in mask)),
                   "--cpu-strict" + suffix, str(int(effective["role_strict"]))]
        if poll is not None:
            result += ["--poll" + suffix, str(poll)]
        if priority == "batch":
            result += ["--prio" + suffix, "-1"]
    return result


def mixed_prefill_arguments(effective):
    policy = effective["mixed_prefill"]
    return ["--mixed-prefill-policy", "none" if policy == "off" else policy]


def lifecycle_requests(runner, port, fixture, output):
    tokens = fixture["requests"][0]["prompt"]
    common = {"prompt": tokens, "n_predict": 128, "temperature": 0, "seed": 424242,
              "cache_prompt": False, "ignore_eos": True, "return_tokens": True}
    cancelled = threading.Event()
    received = 0
    def after_tokens(count):
        nonlocal received
        received += count
        if received >= 8:
            cancelled.set()
    result = runner.stream_request(port, common | {"stream": True}, "cancel", output / "cancel.sse.jsonl",
                                   90, cancelled, on_tokens=after_tokens)
    save(output / "cancel.json", result | {"received_before_interrupt": received})
    require(result["status"] == "cancelled" and 8 <= received < common["n_predict"], "요청 취소가 검증되지 않았습니다.")
    try:
        runner.json_request(port, "POST", "/completion", common | {"n_predict": 2, "grammar": "root ::= ["}, timeout=30)
    except RuntimeError as error:
        save(output / "request-error.json", {"error": str(error)})
        require("HTTP 400" in str(error), "예상과 다른 HTTP 오류 응답입니다.")
    else:
        raise RuntimeError("잘못된 문법을 포함한 요청이 허용됐습니다.")


def run_cohort(args, directory, manifest, effective, output, cancel, checkpoint=None, window_snapshot=None):
    check_conditions = check_scheduler if checkpoint else guard
    sys.path.insert(0, str(SERVING))
    runner = importlib.import_module("runner")
    port = runner.free_port()
    model = args.model.resolve(strict=True)
    digest = sha(model)
    require(digest == MODEL_SHA, "토큰 기반 실험에는 배포된 원본 model.gguf가 필요합니다. 모델 SHA-256이 다릅니다.")
    cpus = ",".join(map(str, effective["cpus"]))
    command = ["taskset", "-c", cpus, str(directory / "bin/llama-server"),
               "--model", str(model), "--host", "127.0.0.1", "--port", str(port),
               "-ngl", "0", "--threads", str(effective["threads"]), "--threads-batch", str(effective["batch_threads"]),
               "--threads-http", str(effective["threads_http"]), "--ctx-size", "8192", "--parallel", "8",
               "--batch-size", "512", "--ubatch-size", "256", "--flash-attn", "on", "--no-ui", "--offline",
               "--perf", "--no-kv-unified", "--spec-type", "none", "--server-compute-profile-mode", "phase"]
    command += role_arguments(effective) + mixed_prefill_arguments(effective)
    if effective["transport"] == "trace":
        command += ["--scx-phase-run-id", str(effective["run_id"])]
    if args.sleep_idle:
        command += ["--sleep-idle-seconds", str(args.sleep_idle)]
    if checkpoint:
        command[3:3] = [str(Path(checkpoint["bundle"]) / "llama_scx_child"),
                        "--phase-register-socket", checkpoint["socket"], "--"]
    env = environment(args, effective, directory)
    visit = {"fixtures": args.fixtures, "tokens": args.tokens, "sleep_idle_s": args.sleep_idle,
             "lifecycle": args.lifecycle, "state_log": args.state_log, "worker_log": args.worker_log}
    save(output / "launch.json", {"argv": command, "environment": env, "model_sha256": digest,
                                  "build": manifest, "visit": visit})
    log = output / "server.log"
    server = runner.Server(command, port, log, cleanup_timeout=15, env=env)
    results = []
    child_pidfd = None
    try:
        server.start(120, cancel)
        pid = server.process.pid
        if checkpoint:
            deadline = time.monotonic() + 5
            while not (ack := re.search(r"phase_uprobe_registered_tgid=(\d+)", log.read_text())):
                require(time.monotonic() < deadline and server.process.poll() is None, "선택된 자식 프로세스의 커널 등록 확인을 받지 못했습니다.")
                time.sleep(.05)
            pid = int(ack[1])
            fd = os.pidfd_open(pid)
            try:
                parent = re.search(r"^PPid:\s+(\d+)$", Path(f"/proc/{pid}/status").read_text(), re.M)
                require(parent and int(parent[1]) == server.process.pid, "등록된 자식 프로세스의 부모가 다릅니다.")
            except BaseException:
                os.close(fd)
                raise
            child_pidfd = fd
            require(os.sched_getscheduler(server.process.pid) == os.SCHED_OTHER, "선택된 자식의 실행기 정책이 바뀌었습니다.")
            os.sched_setaffinity(server.process.pid, {checkpoint["controller_cpu"]})
        loaded = verify_loaded(directory, manifest, effective, model, pid, runner.loaded_libraries(pid))
        startup = verify_effective(log.read_text(), effective)
        save(output / "runtime.json", loaded | {"startup": startup})
        fixtures = [v for v in read(FIXTURES) if v["id"] in args.fixtures]
        require(len(fixtures) == len(args.fixtures), "실험 입력 이름이 알 수 없거나 중복됐습니다.")
        if args.lifecycle:
            lifecycle_requests(runner, port, fixtures[0], output)
        for fixture in fixtures:
            for item, request in zip(fixture["items"], fixture["requests"]):
                tokens = runner.json_request(port, "POST", "/tokenize", {"content": item["prompt"], "add_special": True})["tokens"]
                require(tokens[:fixture["input_token_cap"]] == request["prompt"], "토크나이저의 출력이 실험 입력과 다릅니다.")
            payload = payload_for(fixture, args.tokens)
            row = {"fixture": fixture["id"], "payload": payload}
            for role in ("warmup", "measured"):
                check_conditions()
                require(not cancel.is_set(), "실험이 중단됐습니다.")
                if args.sleep_idle and role == "measured":
                    deadline = time.monotonic() + args.sleep_idle + 15
                    while not runner.json_request(port, "GET", "/props")["is_sleeping"]:
                        require(time.monotonic() < deadline and not cancel.is_set(), "제한 시간 내에 서버가 유휴 상태에 도달하지 못했습니다.")
                        time.sleep(.15)
                before = window_snapshot(pid) if window_snapshot else None
                start = time.monotonic_ns()
                before_cpu = runner.cpu_seconds(pid)
                body = runner.json_request(port, "POST", "/completion", payload, timeout=180)
                end = time.monotonic_ns()
                elapsed = (end - start) / 1e9
                cpu = runner.cpu_seconds(pid) - before_cpu
                after = window_snapshot(pid) if window_snapshot else None
                save(output / f"{fixture['id']}-{role}-responses.json", body)
                replies = validate_body(body, fixture, args.tokens)
                tokens = [entry["tokens"] for entry in replies]
                row[role] = {"tokens": tokens, "elapsed_s": elapsed, "cpu_s": cpu,
                             "tokens_per_s": sum(map(len, tokens)) / elapsed}
                row[role]["request_timings"] = [entry["timings"] for entry in replies]
                if window_snapshot:
                    row[role]["window"] = {"before": before, "http_start_ns": start, "http_end_ns": end, "after": after}
                check_conditions()
                live = verify_loaded(directory, manifest, effective, model, pid, runner.loaded_libraries(pid))
                save(output / f"{fixture['id']}-{role}-runtime.json", live)
            require(row["warmup"]["tokens"] == row["measured"]["tokens"], "워밍업과 본 측정의 생성 토큰이 다릅니다.")
            results.append(row)
            save(output / "cohorts.json", results)
    finally:
        try:
            if child_pidfd is not None:
                stop_registered_child(server, child_pidfd)
        finally:
            server.stop()
            save(output / "cleanup.json", server.cleanup)
    require(server.cleanup["returncode"] == 0 and not server.cleanup["forced_leader_kill"], "서버가 정상 종료되지 않았습니다.")
    log_text = log.read_text()
    require("mode=phase_batch prefill_reference=1" in log_text, "런타임 R 연산 경로의 실행 증거가 없습니다.")
    verify_effective(log_text, effective)
    if args.state_log:
        matches = [tuple(map(int, m)) for m in re.findall(r"NEWA_STATE_V2 run=(\d+) seq=(\d+) phase=(\d+) active=(\d+)", log_text)]
        require(matches and matches[-1][2:] == (0, 0) and any(m[3] for m in matches) and
                all(m[:2] == (effective["run_id"], i) for i, m in enumerate(matches, 1)),
                "활성·유휴 상태 전환이 없거나 상태 전송 순서가 잘못됐습니다.")
        save(output / "state-v2.json", matches)
    summary = {"status": "COHORT_PASS", "cohorts": len(results), "scheduler": effective["scheduler"],
               "kernel_state_delivery": "NOT_RUN"}
    if checkpoint:
        admission = verify_scx_completion(args.scx_checkpoint.resolve())
        summary["kernel_state_delivery"] = "VALID_EVENTS_AND_IDLE_OBSERVED"
        summary["kernel_handoff"] = admission
    save(output / "summary.json", summary)


def check_scheduler():
    from scx import SCHED_EXT
    require(SCHED_EXT.read_text().strip() == "enabled" and
            Path("/sys/kernel/sched_ext/root/ops").read_text().strip() == "llama_new_a",
            "선택한 sched_ext 스케줄러가 활성화되지 않았습니다.")


def stop_registered_child(server, pidfd):
    # The ordinary launcher must reap the server and return its actual exit code.
    # The runner's final process-group cleanup also handles startup errors and timeouts.
    try:
        try:
            signal.pidfd_send_signal(pidfd, signal.SIGTERM)
        except ProcessLookupError:
            pass
        server.process.wait(timeout=server.cleanup_timeout)
    finally:
        os.close(pidfd)


def read_checkpoint(path, manifest, effective):
    from scx import PREFILL_PAIR, p_representatives, proc_start, verify_bundle
    checkpoint = read(path / "checkpoint.json")
    require(checkpoint["status"] == "PREPARED_KERNEL_NOT_RUN" and checkpoint["build_id"] == manifest["build_id"],
            "체크포인트가 요청한 런타임과 다릅니다.")
    require(proc_start(checkpoint["owner_pid"]) == checkpoint["owner_start_ticks"], "제어 셸이 다시 시작됐거나 종료됐습니다.")
    for name, key in (("scheduler-topology.bin", "topology_sha256"), ("guard-domain.bin", "domain_sha256")):
        require(sha(path / name) == checkpoint[key], "안전 검사 입력이 변경됐습니다: " + name)
    bundle = verify_bundle(Path(checkpoint["bundle"]))
    obj = f"{checkpoint['variant']}/{checkpoint['policy']}/full_object.bpf.o"
    require(bundle["artifacts"].get(obj) == checkpoint["object_sha256"], "체크포인트 스케줄러의 해시가 다릅니다.")
    # The offline preparation guard is independent of the mandatory live SCX admission checks.
    require(all(effective[key] == value for key, value in checkpoint["effective"].items()
                if key not in ("run_id", "relaxed_host_checks")),
            "체크포인트 설정과 실제 런타임 구성이 다릅니다.")
    if checkpoint["policy"] in PREFILL_PAIR:
        require(checkpoint.get("p_representatives") == p_representatives(effective["topology"]["portable_plan"], effective["cpus"]),
                "체크포인트의 P코어 대표 CPU와 감지 결과가 다릅니다.")
    loader_log = (path / "loader.log").read_text()
    require("waiting for selected child" in loader_log and f'"object_sha256":"{checkpoint["object_sha256"]}"' in loader_log,
            "loader 준비 확인이나 BPF 오브젝트 증빙이 없습니다.")
    check_scheduler()
    return checkpoint


def verify_scx_completion(path):
    from scx import PREFILL_PAIR, SCHED_EXT, audit_prefill
    until = time.monotonic() + 20
    while not (path / "loader-exit.txt").exists() or SCHED_EXT.read_text().strip() != "disabled":
        require(time.monotonic() < until, "loader가 제한 시간 내에 종료·분리 및 진단 저장을 마치지 못했습니다.")
        time.sleep(.1)
    require((path / "loader-exit.txt").read_text().split() == ["0", "0"], "loader 실행 또는 로그 저장에 실패했습니다.")
    stats = read(path / "scheduler-stats.json")
    rows = stats["cpus"]
    checkpoint = read(path / "checkpoint.json")
    require(stats["instrumentation_mode"] == checkpoint["variant"].upper(), "스케줄러 진단 모드가 다릅니다.")
    handoff = stats["idle_handoff"]
    policy = checkpoint["policy"]
    require(handoff["mode"] == policy, "스케줄러의 CPU 배치 정책이 다릅니다.")
    attempts, moved = handoff["attempts"], handoff["moved"]
    require(len(attempts) == len(moved) == 4 and all(0 <= n <= a for n, a in zip(moved, attempts)) and
            not any(attempts[i] for i in (0, 1, 3)) and
            (policy == "decode-handoff" or not any(moved)), "handoff 카운터가 예상 범위를 벗어났습니다.")
    locality = stats["locality"]
    attempted, hits = locality["attempts"], locality["hits"]
    eligible = {"locality-decode": {2}, "locality-active": {1, 2, 3}}.get(policy, set())
    require(len(attempted) == len(hits) == 4 and all(0 <= h <= a for h, a in zip(hits, attempted)) and
            not any(attempted[i] for i in set(range(4)) - eligible), "지역성 카운터가 예상 범위를 벗어났습니다.")
    require(stats["live_monitor"]["status"] == "PASS" and stats["events_export_error"] == 0 and
            sum(r["running"] for r in rows) and
            not any(r["mask_violations"] or r["tracking_failures"] or r["events_dropped"] for r in rows),
            "커널 안전 검사 또는 스케줄러 진단에 실패했습니다.")
    receiver = re.search(r"NEWA_STATE_RECEIVER run=(\d+) sequence=(\d+) rejected=(\d+) idle=(\d+) active=(\d+) invalid=(\d+)",
                         (path / "loader.log").read_text())
    require(receiver is not None, "커널 분리 후 상태 수신 기록이 없습니다.")
    run, sequence, rejected, idle, active, invalid = map(int, receiver.groups())
    require(run == checkpoint["effective"]["run_id"] and sequence and idle and not (rejected or active or invalid),
            "state-v2 전송 또는 종료 상태가 올바르지 않습니다.")
    result = {"policy": policy, "decode_attempts": attempts[2], "decode_moves": moved[2], "locality": locality}
    if policy in PREFILL_PAIR:
        require(not any(attempts), "Prefill 비교에서 Decode handoff 카운터가 증가했습니다.")
        result["variant"] = checkpoint["variant"]
        result["prefill_pcore"] = audit_prefill(checkpoint, stats)
    return result


def add_configuration(parser):
    parser.add_argument("--profile", choices=("unified-conservative", "integrated-runtime-research"), default="unified-conservative")
    parser.add_argument("--resources", choices=("auto", "amd-5-6", "intel-fixed6", "intel-4-8", "physical"), default="auto")
    parser.add_argument("--reserve-controller", action="store_true", help="auto에서 커널 실험 제어용 논리 CPU 하나를 서버 범위 밖에 둡니다.")
    parser.add_argument("--cpus", help="Restrict hardware discovery to this CPU list")
    parser.add_argument("--policy", choices=("phase-fixed", "pressure", "fixed5", "fixed6", "adaptive"))
    parser.add_argument("--pressure-threshold", type=float)
    parser.add_argument("--pressure-cohort", type=int, choices=range(2, 9))
    parser.add_argument("--min-prefill-ms", type=int)
    parser.add_argument("--mixed-prefill", choices=("off", "cap128", "head64"), default="off")
    parser.add_argument("--native-barrier", choices=("spin", "park"), default="spin")
    parser.add_argument("--barrier-phase", choices=("all", "prefill", "budget"), default="all")
    parser.add_argument("--generation-cpus")
    parser.add_argument("--batch-cpus")
    parser.add_argument("--generation-poll", type=int, choices=range(0, 101), metavar="0..100")
    parser.add_argument("--batch-poll", type=int, choices=(0, 1))
    parser.add_argument("--generation-priority", choices=("normal", "batch"), default="normal")
    parser.add_argument("--batch-priority", choices=("normal", "batch"), default="normal")
    parser.add_argument("--strict-placement", action="store_true")
    parser.add_argument("--pool", choices=("off", "shared", "roles"))
    parser.add_argument("--transport", choices=("off", "scalar", "state", "trace"))
    parser.add_argument("--state-log", action="store_true")
    parser.add_argument("--worker-log", action="store_true")


def model_free_tests():
    for tests, pattern in ((TOPOLOGY, "test_hybrid.py"), (SERVING, "test_*.py"),
                           (Path(__file__).resolve().parent, "test_integration.py"),
                           (WORKSPACE / "experiments/amd-prefill-placement-ac-v1", "test_portable.py")):
        subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests), "-p", pattern],
                       check=True, timeout=180, env=clean_env())


def collect_results(result, destination):
    result = result.resolve(strict=True)
    require((result / "summary.json").is_file() or (result / "failure.json").is_file(),
            "완료 또는 실패 기록이 있는 실험 결과 폴더를 지정하세요.")
    included = {}
    for path in sorted(result.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        require(path.suffix in (".json", ".jsonl", ".log", ".txt"), "허용되지 않은 결과 파일입니다: " + str(path))
        relative = str(path.relative_to(result))
        require(relative != "artifact-sha256.json", "결과 폴더에 예약된 매니페스트 이름이 있습니다.")
        included[relative] = sha(path)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in included:
            archive.write(result / relative, relative)
        archive.writestr("artifact-sha256.json", json.dumps(included, indent=2) + "\n")
    with zipfile.ZipFile(destination) as archive:
        for name, expected in included.items():
            digest = hashlib.sha256()
            with archive.open(name) as member:
                for chunk in iter(lambda: member.read(1024 * 1024), b""):
                    digest.update(chunk)
            require(digest.hexdigest() == expected, "결과 ZIP의 해시 검증에 실패했습니다: " + name)
    with destination.with_suffix(destination.suffix + ".sha256").open("x") as sidecar:
        sidecar.write(f"{sha(destination)}  {destination.name}\n")


def main(argv=None, *, cohort_monitor=None):
    parser = ArgumentParser(description="CPU 추론 통합 실험")
    parser.set_defaults(relaxed_host_checks=False)
    commands = parser.add_subparsers(dest="action", required=True)
    host_checks = argparse.ArgumentParser(add_help=False)
    host_checks.add_argument("--relaxed-host-checks", action="store_true",
                             help=argparse.SUPPRESS)
    commands.add_parser("test")
    pair = commands.add_parser("check-prefill-pair")
    pair.add_argument("--neutral", type=Path, required=True)
    pair.add_argument("--candidate", type=Path, required=True)
    collect = commands.add_parser("collect")
    collect.add_argument("--result", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build", parents=[host_checks])
    build.add_argument("--build-dir", type=Path, required=True)
    build.add_argument("--backend", choices=("openmp", "native"), default="openmp")
    build.add_argument("--markers", choices=("all", "state-only"), default="all")
    build.add_argument("--reuse", action="store_true", help="같은 소스·옵션의 완성된 빌드를 검증해 재사용하거나 중단된 빌드를 계속합니다.")
    build.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    scheduler = commands.add_parser("build-scheduler", parents=[host_checks])
    scheduler.add_argument("--output", type=Path, required=True)
    prepare = commands.add_parser("prepare-scx", parents=[host_checks])
    prepare.add_argument("--build-dir", type=Path, required=True)
    prepare.add_argument("--scheduler-build", type=Path, required=True)
    prepare.add_argument("--variant", choices=("full", "lite"), required=True)
    from scx import POLICIES
    prepare.add_argument("--scheduler-policy", choices=POLICIES, default="observe",
                         help="Select the sealed placement policy for the manual loader checkpoint")
    prepare.add_argument("--owner-pid", type=int, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    add_configuration(prepare)
    doctor = commands.add_parser("doctor", parents=[host_checks])
    doctor.add_argument("--build-dir", type=Path, required=True)
    add_configuration(doctor)
    run = commands.add_parser("run", parents=[host_checks])
    run.add_argument("--build-dir", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--model", type=Path, required=True)
    run.add_argument("--fixtures", nargs="+", default=["heldout-1"])
    run.add_argument("--tokens", type=int, choices=range(1, 129), metavar="1..128", default=16)
    run.add_argument("--sleep-idle", type=int, choices=range(0, 11), default=0)
    run.add_argument("--lifecycle", action="store_true", help="Cancel a stream and reject malformed grammar before fixture recovery")
    run.add_argument("--scx-checkpoint", type=Path)
    add_configuration(run)
    serve = commands.add_parser("serve-bench", parents=[host_checks])
    serve.add_argument("--build-dir", type=Path, required=True)
    serve.add_argument("--output", type=Path, required=True)
    serve.add_argument("--model", type=Path, required=True)
    serve.add_argument("--workloads", nargs="+", choices=("pp", "d1", "d2", "d4", "m1", "m3", "m4"), default=["d2", "m1"])
    serve.add_argument("--tokens", type=int, choices=range(16, 129), metavar="16..128", default=32)
    serve.add_argument("--long-prompt-tokens", type=int, choices=(768, 1024, 1536), default=1024)
    serve.add_argument("--repetitions", type=int, choices=range(1, 5), default=1)
    serve.add_argument("--compare-research", action="store_true")
    add_configuration(serve)
    args = parser.parse_args(argv)
    if args.action == "check-prefill-pair":
        from scx import check_pair
        print(json.dumps(check_pair(args.neutral, args.candidate), indent=2))
        return
    if args.action == "test":
        model_free_tests()
        return
    if args.action == "collect":
        collect_results(args.result, args.output)
        return
    scx_checkpoint = getattr(args, "scx_checkpoint", None)
    require(os.uname().sysname == "Linux" and os.uname().machine == "x86_64", "이 런타임에는 x86-64 Linux가 필요합니다.")
    if not scx_checkpoint:
        guard()
    else:
        require(os.getuid() != 0 and os.sched_getscheduler(0) == os.SCHED_OTHER,
                "선택된 자식의 추론은 일반 계정과 Linux 기본 정책으로 실행하세요.")
    STATE.mkdir(parents=True, exist_ok=True)
    # Both checkouts use the same lock when the protected workspace is beside this branch.
    local_frozen = WORKSPACE.parents[1] / "new-a-workspace/state/.measurement.lock"
    lock_path = local_frozen if local_frozen.is_file() else WORKSPACE / "state/.measurement.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'다른 빌드나 실험이 실행 중입니다. 완료 후 다시 실행하세요 ({lock_path}).') from None
        if args.action == "build-scheduler":
            import scx
            scx.build(args.output.resolve())
            return
        directory = args.build_dir.resolve()
        if args.action == "build":
            build_runtime(directory, args.backend, args.markers, args.jobs, args.reuse)
            print(directory / "manifest.json")
            return
        manifest = verify_build(directory)
        effective = resolve(args, manifest)
        if args.action == "prepare-scx":
            import scx
            scx.prepare(args, directory, manifest, effective)
            return
        if args.action == "doctor":
            print(json.dumps({"manifest": manifest, "effective": effective}, ensure_ascii=False, indent=2))
            return
        output = args.output.resolve()
        checkpoint = None
        if scx_checkpoint:
            checkpoint = read_checkpoint(scx_checkpoint.resolve(), manifest, effective)
            effective["run_id"] = checkpoint["effective"]["run_id"]
            effective["scheduler"] = "SCHED_EXT"
        output.mkdir(parents=True, exist_ok=False)
        save(output / "effective.json", effective)
        cancel = threading.Event()
        def interrupt(_sig, _frame):
            cancel.set()
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM, interrupt)
        try:
            if args.action == "serve-bench":
                import serving
                sys.path.insert(0, str(SERVING))
                runner = importlib.import_module("runner")
                configurations = [effective]
                if args.compare_research:
                    require(not any((args.pool, args.transport, args.policy)), "프로파일 비교에서는 기본 옵션을 그대로 사용하세요.")
                    args.profile = ("integrated-runtime-research" if args.profile == "unified-conservative"
                                    else "unified-conservative")
                    configurations.append(resolve(args, manifest))
                serving.run(args, runner, directory, manifest, configurations, output, cancel,
                            environment, role_arguments, mixed_prefill_arguments, verify_loaded, verify_effective,
                            guard)
            else:
                with (cohort_monitor(effective, output) if cohort_monitor else nullcontext()) as snapshot:
                    run_cohort(args, directory, manifest, effective, output, cancel, checkpoint, snapshot)
        except (Exception, KeyboardInterrupt) as error:
            save(output / "failure.json", {"status": "FAILED", "error": describe(error), "detail": repr(error)})
            raise
        print(output / "summary.json")


if __name__ == "__main__":
    main_entry(main)

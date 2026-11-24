#!/usr/bin/env python3
"""Build and run the integration-v2 CPU release with recorded source and DSO identity."""
import argparse
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
    require("Keep semantic Prefill on the reference body." in header.read_text(), "Missing R Prefill reference route")
    return {"schema": 1, "revision": run_capture(["git", "-C", str(SOURCE), "rev-parse", "HEAD"]),
            "source_files": files, "source_lock_sha256": sha(EVIDENCE / "sources.lock.json"),
            "backend": backend, "markers": markers, "isa": "x86-64 + AVX2/FMA/F16C/SSE4.2", "flags": flags,
            "gcc": run_capture(["gcc", "--version"]), "g++": run_capture(["g++", "--version"]),
            "cmake": run_capture(["cmake", "--version"])}


def elf_identity(path):
    with path.open("rb") as stream:
        header = stream.read(20)
    require(header[:6] == b"\x7fELF\x02\x01" and header[18:20] == b"\x3e\x00", "Expected x86-64 ELF: " + str(path))
    return sha(path)


def seal_build(directory, inputs):
    entries = read(directory / "compile_commands.json")
    commands = "\n".join(row["command"] for row in entries)
    require(all(flag in commands for flag in ("-mavx2", "-mfma", "-mf16c")), "AVX2 backend flags missing")
    require(not re.search(r"-march=native|-mtune=native|-mavx512|-mavxvnni|-mamx", commands), "Nonportable ISA flag")
    require(("-fopenmp" in commands) == (inputs["backend"] == "openmp"), "OpenMP build option mismatch")
    binary = directory / "bin"
    artifacts = {p.name: elf_identity(p) for p in sorted(binary.iterdir())
                 if p.is_file() and not p.is_symlink() and (".so" in p.name or p.name == "llama-server")}
    required = {"libggml-cpu", "libggml-base", "libggml", "libllama", "libllama-common", "libllama-server-impl", "libmtmd"}
    require("llama-server" in artifacts and required <= {name.split(".so")[0] for name in artifacts},
            "Missing expected project ELF in build directory")
    require(source_inputs(inputs["backend"], inputs["markers"]) == inputs, "Source or build configuration changed during compilation")
    save(directory / "manifest.json", {"status": "BUILD_PASS", "kind": "integration-v2",
         "build_id": input_fingerprint(inputs), "source_revision": inputs["revision"], "backend": inputs["backend"],
         "markers": inputs["markers"], "r_route": "semantic-prefill-reference", "artifacts": artifacts,
         "compile_commands_sha256": sha(directory / "compile_commands.json")})


def build_runtime(directory, backend, markers, jobs):
    inputs = source_inputs(backend, markers)
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
    require(manifest["kind"] == "integration-v2" and manifest["status"] == "BUILD_PASS", "Invalid integration-v2 manifest")
    require(manifest["r_route"] == "semantic-prefill-reference" and
            manifest["build_id"] == input_fingerprint(inputs), "Build source seal differs")
    require(source_inputs(inputs["backend"], inputs["markers"]) == inputs, "Source changed since this build; rebuild in a new directory")
    require(manifest["compile_commands_sha256"] == sha(directory / "compile_commands.json"), "Compile commands changed")
    for name, digest in manifest["artifacts"].items():
        require(Path(name).name == name and elf_identity(directory / "bin" / name) == digest,
                "Build artifact changed: " + name)
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
    if args.resources == "auto":
        resources = "amd-5-6" if topology["vendor"] == "AMD" and len(reps) >= 6 else (
            "intel-fixed6" if topology["vendor"] == "Intel" and len(reps) >= 6 else "physical")
    else:
        resources = args.resources
    if resources == "intel-4-8":
        require(topology["architecture"] == "INTEL_HYBRID" and topology["physical_p_cores"] == 4 and topology["physical_e_cores"] >= 4,
                "intel-4-8 requires four eligible P cores and at least four E cores")
        proposal = profiles.recommend(detected, e_count=4)
        cpus = proposal["affinity_cpus"]
        compute, batch = 4, 8
    elif resources in ("amd-5-6", "intel-fixed6"):
        require(len(reps) >= 6 and topology["vendor"] == ("AMD" if resources == "amd-5-6" else "Intel"),
                "Selected profile requires its documented CPU vendor and at least six physical cores")
        cpus, compute, batch = sorted(reps[:6]), 5, 6
    else:
        cpus, compute, batch = sorted(reps), len(reps), len(reps)
    quota = detected["hardware"]["cgroup"]["cpu_max"]
    if quota and not quota.startswith("max "):
        limit, period = map(int, quota.split())
        require(batch * period <= limit, "Selected worker count exceeds visible cgroup CPU quota")
    allowed = set(topology["snapshot"]["usable_cpus"])
    require(set(cpus) <= allowed, "Resolved CPUs leave the host envelope")
    cpuinfo = {}
    for block in Path("/proc/cpuinfo").read_text().strip().split("\n\n"):
        fields = dict(tuple(x.strip() for x in row.split(":", 1)) for row in block.splitlines() if ":" in row)
        if "processor" in fields:
            cpuinfo[int(fields["processor"])] = fields.get("flags", "").split()
    require(all({"avx", "avx2", "fma", "f16c", "sse4_2"} <= set(cpuinfo[c]) for c in cpus), "Selected CPU lacks AVX2/FMA/F16C/SSE4.2")
    policy = args.policy or ("pressure" if research and resources == "amd-5-6" else
                              "fixed6" if resources in ("amd-5-6", "intel-fixed6") else "phase-fixed")
    if policy in ("pressure", "fixed5", "fixed6"):
        require((compute, batch) == (5, 6) and len(cpus) == 6, "Legacy E policy requires exactly six CPUs and a 5/6 profile")
    adaptive = None
    if policy == "adaptive":
        require(compute < batch <= len(cpus) <= 32, "Adaptive policy requires two distinct worker counts within an envelope of at most 32 CPUs")
        require(args.pressure_threshold is not None and args.pressure_cohort and args.min_prefill_ms,
                "Adaptive policy requires explicit pressure threshold, cohort size and minimum Prefill duration")
        require(0 <= args.pressure_threshold <= 4 and 100 <= args.min_prefill_ms <= 10000,
                "Adaptive threshold or Prefill duration out of range")
        adaptive = {"threshold": args.pressure_threshold, "cohort": args.pressure_cohort, "min_prefill_ms": args.min_prefill_ms}
    else:
        require(all(v is None for v in (args.pressure_threshold, args.pressure_cohort, args.min_prefill_ms)),
                "Pressure calibration options require adaptive policy")
    pool = args.pool or ("roles" if research else "off")
    transport = args.transport or ("state" if research else "off")
    role_cpus = [cpu_list(v) if v else cpus for v in (args.generation_cpus, args.batch_cpus)]
    polls = [args.generation_poll, args.batch_poll]
    priorities = [args.generation_priority, args.batch_priority]
    role_options = bool(args.generation_cpus or args.batch_cpus or args.strict_placement or
                        any(v is not None for v in polls) or "batch" in priorities)
    if role_options:
        require(pool == "roles" and manifest["backend"] == "native",
                "Role affinity, polling and priority require native role pools")
        require(all(len(mask) >= count and set(mask) <= set(cpus)
                    for mask, count in zip(role_cpus, (compute, batch))),
                "Role masks must stay inside the envelope and hold their full worker counts")
        require(policy == "phase-fixed", "Role placement currently uses fixed phase profiles")
    require(transport != "scalar" or manifest["markers"] != "state-only", "Build omits the scalar marker")
    require(transport != "trace" or manifest["markers"] == "all", "Build omits diagnostic trace")
    require(not args.state_log or transport == "state", "State diagnostics require state transport")
    if args.native_barrier == "park":
        require(manifest["backend"] == "native", "Parking is a native CPU graph barrier option")
    else:
        require(args.barrier_phase == "all", "Select the park barrier to set a phase-dependent spin budget")
    if args.mixed_prefill == "head64":
        require(manifest["backend"] == "native" and compute == batch == 6 and policy == "phase-fixed",
                "head64 requires the native 6/6 phase-fixed profile")
        require(args.action == "doctor" or (args.action == "serve-bench" and args.workloads == ["m4"]),
                "Select the m4 serving geometry for the head64 diagnostic")
    return {"profile": args.profile, "resources": resources, "policy": policy, "pool": pool, "transport": transport,
            "cpus": cpus, "threads": compute, "batch_threads": batch, "threads_http": 8, "topology": detected,
            "backend": manifest["backend"], "r_route": manifest["r_route"], "scheduler": "SCHED_OTHER",
            "adaptive": adaptive, "mixed_prefill": args.mixed_prefill,
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
    require(Path(f"/proc/{pid}/exe").resolve() == binary / "llama-server", "Wrong server executable")
    expected = {str(binary / name): digest for name, digest in manifest["artifacts"].items() if name != "llama-server"}
    project = {row["path"]: row.get("sha256") for row in libraries
               if Path(row["path"]).name.startswith(("libggml", "libllama", "libmtmd"))}
    require(project == expected, "Loaded project DSO set differs from integration build")
    loaded_openmp = any(Path(row["path"]).name.startswith(("libgomp", "libomp", "libiomp")) for row in libraries)
    require(loaded_openmp == (effective["backend"] == "openmp"), "Loaded OpenMP library inconsistent with build")
    maps = Path(f"/proc/{pid}/maps").read_text().splitlines()
    require(any(len(fields := line.split(maxsplit=5)) == 6 and fields[5] == str(model) for line in maps), "Expected model is not mapped")
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
        require(policy == os.SCHED_OTHER, "Native Batch priority requires the default Linux scheduler")
        threads = [effective["threads"], effective["batch_threads"]]
        roles = 2 if separate_role_pools(effective) else 1
        batch_workers = sum(threads[i] - 1 for i in range(roles) if priorities[i] == "batch")
        policies.add(os.SCHED_BATCH)
    require(workers and all(tuple(v["cpus"]) in possible_masks and v["scheduler"] in policies for v in workers.values()),
            "A worker has unexpected policy or mask")
    require(str(pid) in workers and workers[str(pid)]["scheduler"] == policy and
            sum(v["scheduler"] == os.SCHED_BATCH for v in workers.values()) == batch_workers,
            "Persistent role worker policies or restored graph caller differ from the resolved priorities")
    return {"loaded_libraries": libraries, "workers": workers, "model": str(model)}


def verify_effective(log, effective):
    lines = [line.strip() for line in log.splitlines() if line.startswith("NEWA_INTEGRATION_V2 ")]
    separate = separate_role_pools(effective)
    expected = (f"NEWA_INTEGRATION_V2 pool={effective['pool']} attached={int(effective['pool'] != 'off')} "
                f"separate={int(separate)} transport={effective['transport']} "
                f"generation={effective['threads']} batch={effective['batch_threads']}")
    require(lines and all(line == expected for line in lines), "Server startup configuration differs from requested")
    priorities = effective["role_priorities"]
    if "batch" in priorities:
        signature = tuple(str(-int(v == "batch")) for v in priorities)
        reported = re.findall(r"^NEWA_ROLE_PRIORITY generation=(-?\d+) batch=(-?\d+)$", log, re.M)
        require(reported and all(row == signature for row in reported), "Native role priority differs from requested")
    mixed = re.findall(r"^NEWA_MIXED_PREFILL_POLICY effective=(\w+)$", log, re.M)
    require(mixed and all(value == effective["mixed_prefill"] for value in mixed),
            "Server mixed-prefill policy differs from requested")
    if effective["native_barrier"] == "park":
        barriers = re.findall(r"^NEWA_BARRIER init mode=(\d+) ", log, re.M)
        require(barriers and set(barriers) == {"1"}, "Native park barrier was not applied")
    require(not re.search(r"failed to set (?:thread )?(?:priority|affinity)", log),
            "Runtime reported a role resource application failure")
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
    require(result["status"] == "cancelled" and 8 <= received < common["n_predict"], "Cancellation path was not exercised")
    try:
        runner.json_request(port, "POST", "/completion", common | {"n_predict": 2, "grammar": "root ::= ["}, timeout=30)
    except RuntimeError as error:
        save(output / "request-error.json", {"error": str(error)})
        require("HTTP 400" in str(error), "Unexpected error response")
    else:
        raise RuntimeError("Malformed grammar request succeeded")


def run_cohort(args, directory, manifest, effective, output, cancel, checkpoint=None):
    sys.path.insert(0, str(SERVING))
    runner = importlib.import_module("runner")
    port = runner.free_port()
    model = args.model.resolve(strict=True)
    digest = sha(model)
    require(digest == MODEL_SHA, "Atomic token fixtures require the original model hash")
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
    save(output / "launch.json", {"argv": command, "environment": env, "model_sha256": digest, "build": manifest})
    log = output / "server.log"
    server = runner.Server(command, port, log, cleanup_timeout=15, env=env)
    results = []
    try:
        server.start(120, cancel)
        pid = server.process.pid
        if checkpoint:
            deadline = time.monotonic() + 5
            while not (ack := re.search(r"phase_uprobe_registered_tgid=(\d+)", log.read_text())):
                require(time.monotonic() < deadline and server.process.poll() is None, "Missing selected child registration ACK")
                time.sleep(.05)
            pid = int(ack[1])
            require(os.sched_getscheduler(server.process.pid) == os.SCHED_OTHER, "Selected-child launcher changed policy")
            os.sched_setaffinity(server.process.pid, {checkpoint["controller_cpu"]})
        loaded = verify_loaded(directory, manifest, effective, model, pid, runner.loaded_libraries(pid))
        startup = verify_effective(log.read_text(), effective)
        save(output / "runtime.json", loaded | {"startup": startup})
        fixtures = [v for v in read(FIXTURES) if v["id"] in args.fixtures]
        require(len(fixtures) == len(args.fixtures), "Unknown or duplicate fixture")
        if args.lifecycle:
            lifecycle_requests(runner, port, fixtures[0], output)
        for fixture in fixtures:
            for item, request in zip(fixture["items"], fixture["requests"]):
                tokens = runner.json_request(port, "POST", "/tokenize", {"content": item["prompt"], "add_special": True})["tokens"]
                require(tokens[:fixture["input_token_cap"]] == request["prompt"], "Fixture tokenizer identity mismatch")
            payload = payload_for(fixture, args.tokens)
            row = {"fixture": fixture["id"], "payload": payload}
            for role in ("warmup", "measured"):
                check_scheduler(checkpoint)
                require(not cancel.is_set(), "Interrupted")
                if args.sleep_idle and role == "measured":
                    deadline = time.monotonic() + args.sleep_idle + 15
                    while not runner.json_request(port, "GET", "/props")["is_sleeping"]:
                        require(time.monotonic() < deadline and not cancel.is_set(), "Sleep idle state not reached")
                        time.sleep(.15)
                start = time.monotonic_ns()
                before_cpu = runner.cpu_seconds(pid)
                body = runner.json_request(port, "POST", "/completion", payload, timeout=180)
                elapsed = (time.monotonic_ns() - start) / 1e9
                cpu = runner.cpu_seconds(pid) - before_cpu
                save(output / f"{fixture['id']}-{role}-responses.json", body)
                replies = validate_body(body, fixture, args.tokens)
                tokens = [entry["tokens"] for entry in replies]
                row[role] = {"tokens": tokens, "elapsed_s": elapsed, "cpu_s": cpu,
                             "tokens_per_s": sum(map(len, tokens)) / elapsed}
                check_scheduler(checkpoint)
                live = verify_loaded(directory, manifest, effective, model, pid, runner.loaded_libraries(pid))
                save(output / f"{fixture['id']}-{role}-runtime.json", live)
            require(row["warmup"]["tokens"] == row["measured"]["tokens"], "Warmup/measured token mismatch")
            results.append(row)
            save(output / "cohorts.json", results)
    finally:
        server.stop()
        save(output / "cleanup.json", server.cleanup)
    require(server.cleanup["returncode"] == 0 and not server.cleanup["forced_leader_kill"], "Server cleanup was abnormal")
    log_text = log.read_text()
    require("mode=phase_batch prefill_reference=1" in log_text, "Missing runtime R route evidence")
    verify_effective(log_text, effective)
    if args.state_log:
        matches = [tuple(map(int, m)) for m in re.findall(r"NEWA_STATE_V2 run=(\d+) seq=(\d+) phase=(\d+) active=(\d+)", log_text)]
        require(matches and matches[-1][2:] == (0, 0) and any(m[3] for m in matches) and
                all(m[:2] == (effective["run_id"], i) for i, m in enumerate(matches, 1)),
                "Missing active/idle or invalid state transport sequence")
        save(output / "state-v2.json", matches)
    summary = {"status": "COHORT_PASS", "cohorts": len(results), "scheduler": effective["scheduler"],
               "kernel_state_delivery": "NOT_RUN"}
    if checkpoint:
        admission = verify_scx_completion(args.scx_checkpoint.resolve())
        summary["kernel_state_delivery"] = "VALID_EVENTS_AND_IDLE_OBSERVED"
        summary["kernel_handoff"] = admission
    save(output / "summary.json", summary)


def check_scheduler(checkpoint):
    if not checkpoint:
        guard()
        return
    from scx import SCHED_EXT
    require(SCHED_EXT.read_text().strip() == "enabled" and
            Path("/sys/kernel/sched_ext/root/ops").read_text().strip() == "llama_new_a",
            "Selected sched_ext instance is not active")


def read_checkpoint(path, manifest, effective):
    from scx import proc_start, verify_bundle
    checkpoint = read(path / "checkpoint.json")
    require(checkpoint["status"] == "PREPARED_KERNEL_NOT_RUN" and checkpoint["build_id"] == manifest["build_id"],
            "Checkpoint does not identify the requested runtime")
    require(proc_start(checkpoint["owner_pid"]) == checkpoint["owner_start_ticks"], "Owner shell restarted or exited")
    for name, key in (("scheduler-topology.bin", "topology_sha256"), ("guard-domain.bin", "domain_sha256")):
        require(sha(path / name) == checkpoint[key], "Guard input changed: " + name)
    bundle = verify_bundle(Path(checkpoint["bundle"]))
    obj = f"{checkpoint['variant']}/{checkpoint['policy']}/full_object.bpf.o"
    require(bundle["artifacts"].get(obj) == checkpoint["object_sha256"], "Checkpoint scheduler identity differs")
    require(all(effective[key] == value for key, value in checkpoint["effective"].items() if key != "run_id"),
            "Checkpoint and effective runtime configuration differ")
    loader_log = (path / "loader.log").read_text()
    require("waiting for selected child" in loader_log and f'"object_sha256":"{checkpoint["object_sha256"]}"' in loader_log,
            "Manual loader readiness or BPF object evidence is missing")
    check_scheduler(checkpoint)
    return checkpoint


def verify_scx_completion(path):
    from scx import SCHED_EXT
    until = time.monotonic() + 20
    while not (path / "loader-exit.txt").exists() or SCHED_EXT.read_text().strip() != "disabled":
        require(time.monotonic() < until, "Loader did not finish, detach and export diagnostics")
        time.sleep(.1)
    require((path / "loader-exit.txt").read_text().split() == ["0", "0"], "Loader or log capture reported failure")
    stats = read(path / "scheduler-stats.json")
    rows = stats["cpus"]
    checkpoint = read(path / "checkpoint.json")
    require(stats["instrumentation_mode"] == checkpoint["variant"].upper(), "Scheduler diagnostics mode differs")
    handoff = stats["idle_handoff"]
    policy = checkpoint["policy"]
    require(handoff["mode"] == policy, "Scheduler placement policy differs")
    attempts, moved = handoff["attempts"], handoff["moved"]
    require(len(attempts) == len(moved) == 4 and all(0 <= n <= a for n, a in zip(moved, attempts)) and
            not any(attempts[i] for i in (0, 1, 3)) and
            (policy == "decode-handoff" or not any(moved)), "Unexpected handoff counters")
    locality = stats["locality"]
    attempted, hits = locality["attempts"], locality["hits"]
    eligible = {"locality-decode": {2}, "locality-active": {1, 2, 3}}.get(policy, set())
    require(len(attempted) == len(hits) == 4 and all(0 <= h <= a for h, a in zip(hits, attempted)) and
            not any(attempted[i] for i in set(range(4)) - eligible), "Unexpected locality counters")
    require(stats["live_monitor"]["status"] == "PASS" and stats["events_export_error"] == 0 and
            sum(r["running"] for r in rows) and
            not any(r["mask_violations"] or r["tracking_failures"] or r["events_dropped"] for r in rows),
            "Kernel guard or scheduler diagnostics failed")
    receiver = re.search(r"NEWA_STATE_RECEIVER run=(\d+) sequence=(\d+) rejected=(\d+) idle=(\d+) active=(\d+) invalid=(\d+)",
                         (path / "loader.log").read_text())
    require(receiver is not None, "Missing receiver evidence after detach")
    run, sequence, rejected, idle, active, invalid = map(int, receiver.groups())
    require(run == checkpoint["effective"]["run_id"] and sequence and idle and not (rejected or active or invalid),
            "Invalid state-v2 delivery or cleanup")
    return {"policy": policy, "decode_attempts": attempts[2], "decode_moves": moved[2], "locality": locality}


def add_configuration(parser):
    parser.add_argument("--profile", choices=("unified-conservative", "integrated-runtime-research"), default="unified-conservative")
    parser.add_argument("--resources", choices=("auto", "amd-5-6", "intel-fixed6", "intel-4-8", "physical"), default="auto")
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
                           (Path(__file__).resolve().parent, "test_integration.py")):
        subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", str(tests), "-p", pattern],
                       check=True, timeout=90, env=clean_env())


def collect_results(result, destination):
    result = result.resolve(strict=True)
    require((result / "summary.json").is_file() or (result / "failure.json").is_file(),
            "Select a completed or failed experiment result directory")
    included = {}
    for path in sorted(result.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        require(path.suffix in (".json", ".jsonl", ".log", ".txt"), "Unexpected result artifact: " + str(path))
        require(path.stat().st_size <= 32 * 1024**2, "Result artifact too large: " + str(path))
        relative = str(path.relative_to(result))
        require(relative != "artifact-sha256.json", "Result contains the reserved manifest filename")
        included[relative] = sha(path)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in included:
            archive.write(result / relative, relative)
        archive.writestr("artifact-sha256.json", json.dumps(included, indent=2) + "\n")
    with zipfile.ZipFile(destination) as archive:
        require(archive.testzip() is None and all(hashlib.sha256(archive.read(p)).hexdigest() == digest
                                                  for p, digest in included.items()), "Result ZIP verification failed")
    with destination.with_suffix(destination.suffix + ".sha256").open("x") as sidecar:
        sidecar.write(f"{sha(destination)}  {destination.name}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("test")
    collect = commands.add_parser("collect")
    collect.add_argument("--result", type=Path, required=True)
    collect.add_argument("--output", type=Path, required=True)
    build = commands.add_parser("build")
    build.add_argument("--build-dir", type=Path, required=True)
    build.add_argument("--backend", choices=("openmp", "native"), default="openmp")
    build.add_argument("--markers", choices=("all", "state-only"), default="all")
    build.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    scheduler = commands.add_parser("build-scheduler")
    scheduler.add_argument("--output", type=Path, required=True)
    prepare = commands.add_parser("prepare-scx")
    prepare.add_argument("--build-dir", type=Path, required=True)
    prepare.add_argument("--scheduler-build", type=Path, required=True)
    prepare.add_argument("--variant", choices=("full", "lite"), required=True)
    from scx import POLICIES
    prepare.add_argument("--scheduler-policy", choices=POLICIES, default="observe",
                         help="Select the sealed placement policy for the manual loader checkpoint")
    prepare.add_argument("--owner-pid", type=int, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    add_configuration(prepare)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--build-dir", type=Path, required=True)
    add_configuration(doctor)
    run = commands.add_parser("run")
    run.add_argument("--build-dir", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--model", type=Path, required=True)
    run.add_argument("--fixtures", nargs="+", default=["heldout-1"])
    run.add_argument("--tokens", type=int, choices=range(1, 129), metavar="1..128", default=16)
    run.add_argument("--sleep-idle", type=int, choices=range(0, 11), default=0)
    run.add_argument("--lifecycle", action="store_true", help="Cancel a stream and reject malformed grammar before fixture recovery")
    run.add_argument("--scx-checkpoint", type=Path)
    add_configuration(run)
    serve = commands.add_parser("serve-bench")
    serve.add_argument("--build-dir", type=Path, required=True)
    serve.add_argument("--output", type=Path, required=True)
    serve.add_argument("--model", type=Path, required=True)
    serve.add_argument("--workloads", nargs="+", choices=("pp", "d1", "d2", "d4", "m1", "m3", "m4"), default=["d2", "m1"])
    serve.add_argument("--tokens", type=int, choices=range(16, 129), metavar="16..128", default=32)
    serve.add_argument("--long-prompt-tokens", type=int, choices=(768, 1024, 1536), default=1024)
    serve.add_argument("--repetitions", type=int, choices=range(1, 5), default=1)
    serve.add_argument("--compare-research", action="store_true")
    add_configuration(serve)
    args = parser.parse_args()
    if args.action == "test":
        model_free_tests()
        return
    if args.action == "collect":
        collect_results(args.result, args.output)
        return
    scx_checkpoint = getattr(args, "scx_checkpoint", None)
    require(os.uname().sysname == "Linux" and os.uname().machine == "x86_64", "Integration-v2 runtime requires x86-64 Linux")
    if not scx_checkpoint:
        guard()
    else:
        require(os.getuid() != 0 and os.sched_getscheduler(0) == os.SCHED_OTHER,
                "Run selected-child inference as an ordinary Linux task")
    STATE.mkdir(parents=True, exist_ok=True)
    # Both checkouts use the same lock when the protected workspace is beside this branch.
    local_frozen = WORKSPACE.parents[1] / "new-a-workspace/state/.measurement.lock"
    lock_path = local_frozen if local_frozen.is_file() else WORKSPACE / "state/.measurement.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == "build-scheduler":
            import scx
            scx.build(args.output.resolve())
            return
        directory = args.build_dir.resolve()
        if args.action == "build":
            build_runtime(directory, args.backend, args.markers, args.jobs)
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
                    require(not any((args.pool, args.transport, args.policy)), "Comparison needs unmodified profile defaults")
                    args.profile = ("integrated-runtime-research" if args.profile == "unified-conservative"
                                    else "unified-conservative")
                    configurations.append(resolve(args, manifest))
                serving.run(args, runner, directory, manifest, configurations, output, cancel,
                            environment, role_arguments, mixed_prefill_arguments, verify_loaded, verify_effective, check_scheduler)
            else:
                run_cohort(args, directory, manifest, effective, output, cancel, checkpoint)
        except (Exception, KeyboardInterrupt) as error:
            save(output / "failure.json", {"status": "FAILED", "error": repr(error)})
            raise
        print(output / "summary.json")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)

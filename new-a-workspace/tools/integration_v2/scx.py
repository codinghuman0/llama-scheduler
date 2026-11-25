"""Prepare a bounded selected-child sched_ext run. Loading is a manual checkpoint."""
import math
import os
from pathlib import Path
import shlex
import struct
import subprocess
import uuid

from intel_experiment import read, require, run_logged, save, sha

CODE = Path(__file__).resolve().parent / "scheduler"
WORKSPACE = Path(__file__).resolve().parents[2]
HEADER = WORKSPACE / "src/llama/tools/server"
SCHEDULER_HEADERS = WORKSPACE / "scheduler/include"
BTF = Path("/sys/kernel/btf/vmlinux")
SCHED_EXT = Path("/sys/kernel/sched_ext/state")
PREFILL_PAIR = ("neutral", "prefill-pcore")
POLICIES = {
    "observe": [],
    "decode-handoff": ["-DNEW_A_IDLE_HANDOFF"],
    "locality-decode": ["-DNEW_A_LOCALITY=1"],
    "locality-active": ["-DNEW_A_LOCALITY=2"],
    "neutral": ["-DNEW_A_PREFILL_PAIR=0"],
    "prefill-pcore": ["-DNEW_A_PREFILL_PAIR=1"],
}


def build(out):
    out.mkdir(parents=True, exist_ok=False)
    include = out / "include"
    include.mkdir()
    btf_sha = sha(BTF)
    with (include / "vmlinux.h").open("w") as stream:
        subprocess.run(["bpftool", "btf", "dump", "file", str(BTF), "format", "c"],
                       stdout=stream, check=True, timeout=30)
    multiarch = subprocess.check_output(["cc", "-dumpmachine"], text=True).strip()
    directories = ["-I" + str(SCHEDULER_HEADERS), "-I" + str(HEADER)]
    source_files = sorted(p for p in CODE.iterdir() if p.is_file()) + sorted(SCHEDULER_HEADERS.glob("*.h"))
    source_ids = {str(path.relative_to(WORKSPACE)): sha(path) for path in source_files}
    abi_sha = sha(HEADER / "newa-state-abi.h")
    warnings = ["-O2", "-Wall", "-Wextra", "-Werror"]
    commands = []

    def compile_source(argv, name):
        commands.append(argv)
        run_logged(argv, out / (name + ".log"), timeout=60)

    artifacts = []
    for variant in ("full", "lite"):
        flags = ["-DNEW_A_DIAGNOSTICS"]
        if variant == "lite":
            flags.append("-DNEW_A_RUNTIME_LITE")
        for policy, policy_flags in POLICIES.items():
            dest = out / variant / policy
            dest.mkdir(parents=True)
            obj, loader = (dest / name for name in ("full_object.bpf.o", "loader"))
            compile_source(["clang", "-target", "bpf", "-D__TARGET_ARCH_x86", "-g", "-O2", "-Wall", "-Werror",
                            *flags, *policy_flags, "-I" + str(include), *directories, "-I/usr/include/" + multiarch,
                            "-c", str(CODE / "handoff.bpf.c"), "-o", str(obj)], f"bpf-{variant}-{policy}")
            compile_source(["cc", "-std=gnu11", *warnings, "-Wno-misleading-indentation", *flags, *policy_flags,
                            f'-DHANDOFF_MODE="{policy}"', f'-DUNIVERSAL_OBJECT_SHA256="{sha(obj)}"', *directories,
                            str(CODE / "loader.c"), "-o", str(loader), "-lbpf", "-lelf", "-lz"], f"loader-{variant}-{policy}")
            artifacts.extend((obj, loader))
    compile_source(["cc", "-std=gnu11", *warnings, *directories, str(CODE / "llama_scx_child.c"),
                    "-o", str(out / "llama_scx_child")], "selected-child")
    compile_source(["cc", "-std=c11", *warnings, *directories, str(CODE / "test_state_receiver.c"),
                    "-o", str(out / "test_state_receiver")], "receiver-unit")
    run_logged([str(out / "test_state_receiver")], out / "receiver-test.log", timeout=10)
    for policy in PREFILL_PAIR:
        test = out / ("test-" + policy)
        compile_source(["cc", "-std=gnu11", *warnings, *POLICIES[policy], *directories,
                        str(CODE / "test_prefill_selection.c"), "-o", str(test)], "compile-test-" + policy)
        run_logged([str(test)], out / ("test-" + policy + ".log"), timeout=10)
    artifacts.append(out / "llama_scx_child")
    require(sha(BTF) == btf_sha, "Running kernel BTF changed during scheduler build")
    require(all(sha(WORKSPACE / name) == digest for name, digest in source_ids.items()) and
            sha(HEADER / "newa-state-abi.h") == abi_sha, "Scheduler source changed during compilation")
    save(out / "scheduler-manifest.json", {
        "schema": 3, "status": "COMPILED_NOT_LOADED", "kernel": os.uname().release, "btf_sha256": btf_sha,
        "source_sha256": source_ids, "shared_abi_sha256": abi_sha, "commands": commands,
        "artifacts": {str(p.relative_to(out)): sha(p) for p in artifacts},
    })


def verify_bundle(bundle):
    manifest = read(bundle / "scheduler-manifest.json")
    require(manifest.get("schema") == 3, "Rebuild the scheduler bundle with the current source seal")
    require(manifest["status"] == "COMPILED_NOT_LOADED" and manifest["kernel"] == os.uname().release and
            manifest["btf_sha256"] == sha(BTF), "Scheduler was built for a different kernel/BTF")
    require(manifest["shared_abi_sha256"] == sha(HEADER / "newa-state-abi.h"), "Publisher/receiver wire source changed")
    for rel, digest in manifest["source_sha256"].items():
        require(sha(WORKSPACE / rel) == digest, "Scheduler source changed: " + rel)
    for rel, digest in manifest["artifacts"].items():
        require(sha(bundle / rel) == digest, "Scheduler artifact changed: " + rel)
    return manifest


def proc_start(pid):
    return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])


def p_representatives(plan, selected):
    if plan["architecture"] == "HOMOGENEOUS":
        return []
    require(plan["architecture"] == "INTEL_HYBRID" and plan["vendor"] == "Intel",
            "Cannot certify P-core representatives for this architecture")
    first = [c for c in plan["policy"]["tiers"][0] if c in selected]
    cores = {row["representative"] for row in plan["cores"] if row["core_type"] == "P"}
    require(set(first) == cores.intersection(selected), "CPUID core types and SMT representatives disagree")
    return first


def placement_input(plan, selected, policy):
    tiers = [[c for c in group if c in selected] for group in plan["policy"]["tiers"]]
    flat = [c for group in tiers for c in group]
    require(tiers[0] and len(flat) == len(selected) and set(flat) == set(selected),
            "Selected CPUs do not fit the scheduler tiers")
    padded = [c for tier in tiers for c in tier + [0] * (1024 - len(tier))]
    data = struct.pack("<5I3072I", 0x4e455741, 1, *map(len, tiers), *padded)
    if policy not in PREFILL_PAIR:
        return data, {}
    reps = p_representatives(plan, selected)
    return data + struct.pack("<I", len(reps)), {"p_representatives": reps}


def audit_prefill(checkpoint, stats):
    policy = checkpoint["policy"]
    effective = checkpoint["effective"]
    reps = p_representatives(effective["topology"]["portable_plan"], effective["cpus"])
    proof = stats.get("prefill_pcore")
    require(isinstance(proof, dict) and proof.get("p_representatives") == reps == checkpoint["p_representatives"],
            "Installed P-core configuration differs from the detected topology")

    def counts(value):
        return isinstance(value, list) and len(value) == 4 and all(type(n) is int and n >= 0 for n in value)

    attempts, hits = proof.get("attempts"), proof.get("hits")
    enabled = policy == "prefill-pcore" and bool(reps)
    require(counts(attempts) and counts(hits) and all(h <= a for h, a in zip(hits, attempts)) and
            not any(attempts[i] for i in (0, 2, 3)) and
            (enabled or not any(attempts)), "Invalid Prefill P-core counters")
    rows = stats["cpus"]
    require(all(counts(r["selected"]) for r in rows) and
            [sum(r["selected"][i] for r in rows) for i in range(3)] == [hits[1], 0, 0],
            "Selected idle tiers disagree with Prefill P-core hits")
    running = None
    require("running_starts_by_cpu" in proof, "Missing running callback evidence field")
    starts = proof["running_starts_by_cpu"]
    if checkpoint["variant"] == "full":
        possible = effective["topology"]["portable_plan"]["snapshot"]["possible_cpus"]
        require(isinstance(starts, list) and [r["cpu"] for r in starts] == [r["cpu"] for r in rows] == possible,
                "Running evidence CPU domain differs")
        for item, guard in zip(starts, rows):
            by_phase = item["by_phase"]
            require(counts(by_phase) and sum(by_phase) <= guard["running"] and
                    (not any(by_phase) or item["cpu"] in effective["cpus"]), "Invalid selected-task running evidence")
        running = {"all": [sum(r["by_phase"][i] for r in starts) for i in range(4)],
                   "on_p_representatives": [sum(r["by_phase"][i] for r in starts if r["cpu"] in reps) for i in range(4)]}
        require(any(running["all"]), "No registered-task running callbacks in FULL diagnostics")
    else:
        require(starts is None, "Unexpected running detail in Lite diagnostics")
    if policy == "neutral":
        status = "NEUTRAL_CONTROL"
    elif not reps:
        status = "NEUTRAL_FALLBACK_NO_P_REPRESENTATIVES"
    elif hits[1]:
        status = "PREFILL_IDLE_PCORE_SELECTED"
    elif attempts[1]:
        status = "ATTEMPTED_NO_IDLE_HIT"
    else:
        status = "NO_ELIGIBLE_WAKEUP_OBSERVED"
    return {"status": status, "p_representatives": reps, "attempts": attempts, "hits": hits,
            "running_starts": running}


def check_pair(neutral, candidate):
    identity = None
    fixture_inputs = None
    visits = {}
    for policy, path in zip(PREFILL_PAIR, (neutral, candidate)):
        summary, effective, launch = (read(path / name) for name in ("summary.json", "effective.json", "launch.json"))
        admission = summary.get("kernel_handoff", {})
        require(summary["status"] == "COHORT_PASS" and summary["scheduler"] == "SCHED_EXT" and
                summary["kernel_state_delivery"] == "VALID_EVENTS_AND_IDLE_OBSERVED" and admission.get("policy") == policy,
                "Missing completed selected-child visit for " + policy)
        config = {k: v for k, v in effective.items() if k != "run_id"}
        key = (config, launch["build"]["build_id"], launch["build"]["artifacts"], launch["model_sha256"],
               launch["visit"], admission["variant"])
        require(identity is None or key == identity, "Paired runtime, model, resources or instrumentation differ")
        identity = key
        fixtures = {}
        metrics = {}
        for row in read(path / "cohorts.json"):
            name, measured = row["fixture"], row["measured"]
            require(name not in fixtures and row["warmup"]["tokens"] == measured["tokens"], "Fixture or token mismatch")
            fixtures[name] = (row["payload"], measured["tokens"])
            generated = sum(map(len, measured["tokens"]))
            wall = measured["elapsed_s"]
            timings = measured["request_timings"]
            require(generated > 0 and math.isfinite(wall) and wall > 0 and
                    math.isfinite(measured["cpu_s"]) and measured["cpu_s"] >= 0 and
                    math.isclose(generated / wall, measured["tokens_per_s"]) and
                    len(timings) == len(measured["tokens"]) and
                    all(t["prompt_n"] > 0 and math.isfinite(t["prompt_ms"]) and t["prompt_ms"] > 0 and
                        t["predicted_n"] == len(tokens) and math.isfinite(t["predicted_ms"]) and
                        (t["predicted_ms"] > 0 or len(tokens) == 1 and t["predicted_ms"] == 0)
                        for t, tokens in zip(timings, measured["tokens"])), "Inconsistent cohort metrics")
            metrics[name] = {"generated_tokens": generated, "wall_s": wall, "cpu_s": measured["cpu_s"],
                             "cohort_tokens_per_s": generated / wall, "request_timings": timings}
        require(fixtures and len(fixtures) == summary["cohorts"] and
                (fixture_inputs is None or list(fixtures) == list(fixture_inputs) and fixtures == fixture_inputs),
                "Paired fixtures, order, payloads or deterministic tokens differ")
        fixture_inputs = fixtures
        visits[policy] = {"placement": admission["prefill_pcore"], "metrics": metrics}
    return {"status": "PAIR_SMOKE_PASS", "visits": visits}


def prepare(args, directory, manifest, effective):
    require(SCHED_EXT.read_text().strip() == "disabled", "sched_ext must be disabled before preparation")
    require(effective["transport"] == "state", "The integrated SCX profiles require state-v2")
    require(not effective["role_options"], "Role mask, polling and priority experiments are excluded from selected-child admission")
    require(effective["native_barrier"] != "park", "Park barrier admission with the kernel scheduler is pending")
    require(args.owner_pid > 1 and os.sched_getscheduler(args.owner_pid) == os.SCHED_OTHER, "Owner shell must use normal policy")
    require(Path(f"/proc/{args.owner_pid}").stat().st_uid == os.getuid(), "Owner shell UID differs")
    bundle = args.scheduler_build.resolve(strict=True)
    scheduler_manifest = verify_bundle(bundle)
    detected = effective["topology"]["portable_plan"]
    snapshot = detected["snapshot"]
    possible = snapshot["possible_cpus"]
    online = snapshot["online_cpus"]
    allowed = snapshot["process_allowed_cpus"]
    selected = set(effective["cpus"])
    require(set(os.sched_getaffinity(args.owner_pid)) == set(allowed), "Owner shell changed CPU envelope")
    controller = sorted((set(online) & set(allowed)) - selected)
    require(controller, "A controller CPU outside the selected child envelope is required")
    output = args.output.resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    topology = output / "scheduler-topology.bin"
    topology_bytes, placement = placement_input(detected, selected, args.scheduler_policy)
    topology.write_bytes(topology_bytes)
    domain = output / "guard-domain.bin"
    domain.write_bytes(struct.pack("<6IQ", 0x4e415547, 1, max(possible)+1, len(possible),
                                   args.owner_pid, os.getuid(), proc_start(args.owner_pid)) +
                       b"".join(bytes(int(c in mask) for c in range(1024))
                                for mask in map(set, (possible, online, allowed, selected))))
    domain.chmod(0o600)
    guard_hashes = {"topology_sha256": sha(topology), "domain_sha256": sha(domain)}
    socket = "@newa-v2-" + uuid.uuid4().hex
    variant = args.variant
    policy = args.scheduler_policy
    mode = Path(variant) / policy
    binary = directory / "bin/llama-server"
    marker = directory / "bin/libllama-server-impl.so"
    require(sha(marker) == manifest["artifacts"].get(marker.resolve().name), "Wrong marker DSO")
    loader = ["sudo", "timeout", "--signal=TERM", "--kill-after=15s", "540s",
              "taskset", "-c", str(controller[0]), str(bundle / mode / "loader"),
              "--guard-config", str(domain), "--topology", str(topology),
              "--diagnostics-output", str(output / "scheduler-stats.json"),
              "--phase-uid", str(os.getuid()), "--phase-register-socket", socket,
              "--server-exe", str(binary), "--marker-elf", str(marker.resolve()),
              "--phase-state-run-id", str(effective["run_id"]), "-v"]
    checkpoint = {"status": "PREPARED_KERNEL_NOT_RUN", "variant": variant, "build_id": manifest["build_id"],
                  "policy": policy, "object_sha256": scheduler_manifest["artifacts"][str(mode / "full_object.bpf.o")],
                  "bundle": str(bundle), "controller_cpu": controller[0], "owner_pid": args.owner_pid,
                  "owner_start_ticks": proc_start(args.owner_pid), "socket": socket, "effective": effective,
                  "loader": loader, **guard_hashes, **placement}
    save(output / "checkpoint.json", checkpoint)
    log = shlex.quote(str(output / "loader.log"))
    status = shlex.quote(str(output / "loader-exit.txt"))
    command = ("(set +e; " + shlex.join(loader) + " 2>&1 | tee " + log +
               '; codes=("${PIPESTATUS[@]}"); printf "%s %s\\n" "${codes[0]}" "${codes[1]}" > ' +
               status + '; test "${codes[*]}" = "0 0")')
    (output / "load.sh").write_text("#!/usr/bin/env bash\n" + command + "\n")
    print(command)

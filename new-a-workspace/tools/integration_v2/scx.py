"""Prepare a bounded selected-child sched_ext run. Loading is a manual checkpoint."""
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
POLICIES = {
    "observe": [],
    "decode-handoff": ["-DNEW_A_IDLE_HANDOFF"],
    "locality-decode": ["-DNEW_A_LOCALITY=1"],
    "locality-active": ["-DNEW_A_LOCALITY=2"],
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
            compile_source(["cc", "-std=gnu11", *warnings, "-Wno-misleading-indentation", *flags,
                            f'-DHANDOFF_MODE="{policy}"', f'-DUNIVERSAL_OBJECT_SHA256="{sha(obj)}"', *directories,
                            str(CODE / "loader.c"), "-o", str(loader), "-lbpf", "-lelf", "-lz"], f"loader-{variant}-{policy}")
            artifacts.extend((obj, loader))
    compile_source(["cc", "-std=gnu11", *warnings, *directories, str(CODE / "llama_scx_child.c"),
                    "-o", str(out / "llama_scx_child")], "selected-child")
    compile_source(["cc", "-std=c11", *warnings, *directories, str(CODE / "test_state_receiver.c"),
                    "-o", str(out / "test_state_receiver")], "receiver-unit")
    run_logged([str(out / "test_state_receiver")], out / "receiver-test.log", timeout=10)
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
    tiers = [[c for c in group if c in selected] for group in detected["policy"]["tiers"]]
    require(tiers[0] and set(sum(tiers, [])) == selected, "Selected CPUs do not fit the scheduler tiers")
    flat = [c for tier in tiers for c in tier + [0] * (1024 - len(tier))]
    topology = output / "scheduler-topology.bin"
    topology.write_bytes(struct.pack("<" + "I" * (5 + 3 * 1024), 0x4e455741, 1, *map(len, tiers), *flat))
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
                  "loader": loader, **guard_hashes}
    save(output / "checkpoint.json", checkpoint)
    log = shlex.quote(str(output / "loader.log"))
    status = shlex.quote(str(output / "loader-exit.txt"))
    print("(set +e; " + shlex.join(loader) + " 2>&1 | tee " + log +
          '; codes=("${PIPESTATUS[@]}"); printf "%s %s\\n" "${codes[0]}" "${codes[1]}" > ' +
          status + '; test "${codes[*]}" = "0 0")')

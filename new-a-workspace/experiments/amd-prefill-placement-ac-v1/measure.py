#!/usr/bin/env python3
"""고정 CPU 범위에서 Linux, neutral, prefill-pcore의 생성 처리율을 비교합니다."""
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import platform
import shutil
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WS = HERE.parents[1]
STATE = WS / "state/integration-v2"
sys.path[:0] = [str(WS / "tools/integration_v2"), str(WS / "experiments/a-component-scheduler-replication-v1/code")]
import runtime
import contention
import scx
from cli_ko import ArgumentParser, main_entry
from intel_experiment import FIXTURES, read, require, save, sha, text as read_sysfs

P = read(HERE / "protocol.json")
BUILD = STATE / "builds/prefill-pcore-openmp-v1"
BUNDLE = STATE / "prefill-pcore-scheduler-v2"
MODEL = WS.parents[1] / "model.gguf"


def ac_online(required, root=Path("/sys/class/power_supply")):
    readings = []
    for supply in root.glob("*"):
        try:
            if (supply / "type").read_text().strip() == "Battery":
                continue
            readings.append(int((supply / "online").read_text().strip()))
        except (OSError, ValueError):
            continue
    value = int(any(readings)) if readings else None
    if required:
        require(value == 1, "원래 AMD AC 재현 프로토콜에는 연결된 외부 전원이 필요합니다.")
    return value


def portable_protocol(build):
    command = [sys.executable, "-B", str(Path(runtime.__file__)), "doctor",
               "--build-dir", str(build), "--resources", "auto", "--reserve-controller", "--profile", P["profile"]]
    effective = json.loads(subprocess.check_output(command, text=True))["effective"]
    cpus = effective["cpus"]
    topology = effective["topology"]["summary"]
    return {**P, "portable": True, "device": topology["cpu_model"], "server_cpus": cpus,
            "resources": effective["resources"], "policy": effective["policy"],
            "cpu25": {**P["cpu25"], "cpu": cpus[-1]}, "power": "전원은 기록만 하며 센서가 없는 데스크톱도 실행합니다.",
            "scope": "현재 장비의 단일 캠페인. 장비 간 직접 성능 비교에는 별도 통제가 필요합니다."}


def schedule(protocol=P):
    for index, order in enumerate(protocol["arm_orders"]):
        conditions = protocol["conditions"] if index % 2 == 0 else protocol["conditions"][::-1]
        for condition in conditions:
            for arm in (order if condition == "ambient" else order[::-1]):
                yield {"block": index + 1, "condition": condition, "arm": arm, "cohort": protocol["cohorts"][index % 2]}


def thread_counts(pid):
    result = {}
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            start = task.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19]
            sched = task.joinpath("sched").read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        fields = dict(re.findall(r"^(se\.nr_migrations|nr_switches)\s*:\s*(\d+)\s*$", sched, re.M))
        if len(fields) != 2:
            return {}
        result[f"{task.name}/{start}"] = [int(fields["se.nr_migrations"]), int(fields["nr_switches"])]
    return result


@contextmanager
def observe(condition, effective, output, protocol):
    require(effective["cpus"] == protocol["server_cpus"], "실제 CPU 범위가 사전 등록과 다릅니다.")
    load = contention.ControlledLoad(output / "cpu25", protocol["cpu25"]["cpu"]) if condition == "cpu25" else nullcontext(None)
    with load as active:
        def snapshot(pid):
            ac = ac_online(not protocol.get("portable"))
            tasks = thread_counts(pid)
            begin = time.monotonic_ns()
            external = active.snapshot() if active else None
            end = time.monotonic_ns()
            return {"ac": ac, "threads": tasks, "load": external, "load_clock_ns": (begin + end) // 2}
        yield snapshot


def visit(folder, spec, protocol, build, bundle, model):
    require(os.geteuid() != 0 and os.sched_getscheduler(0) == os.SCHED_OTHER, "일반 계정·Linux 기본 정책으로 제어 프로그램을 실행하세요.")
    ac_online(not protocol.get("portable"))
    resources = ["--resources", "auto", "--reserve-controller"] if protocol.get("portable") else ["--resources", protocol["resources"]]
    common = ["--build-dir", str(build), *resources, "--profile", protocol["profile"],
              "--policy", protocol["policy"], "--pool", protocol["pool"], "--transport", protocol["transport"]]
    run = ["run", *common, "--model", str(model), "--output", str(folder / "run"),
           "--fixtures", spec["cohort"], protocol["secondary_fixture"], "--tokens", str(protocol["tokens_per_request"])]
    loader = None
    if spec["arm"] != "linux":
        cp = folder / "checkpoint"
        runtime.main(["prepare-scx", *common, "--scheduler-build", str(bundle),
                      "--variant", protocol["kernel_instrumentation"], "--scheduler-policy", spec["arm"],
                      "--owner-pid", str(os.getpid()), "--output", str(cp)])
        # prepare-scx emits the same bounded loader command used in the FULL smoke.
        # Its owner is this visit process. Owner exit also tears down an unregistered loader.
        loader = subprocess.Popen(["bash", str(cp / "load.sh")], stdout=subprocess.DEVNULL)
        deadline = time.monotonic() + 30
        log = cp / "loader.log"
        while not log.is_file() or "waiting for selected child" not in log.read_text(errors="replace"):
            require(loader.poll() is None and time.monotonic() < deadline, f"loader가 준비되지 않았습니다. 로그를 확인하세요: {log}")
            time.sleep(.1)
        run += ["--scx-checkpoint", str(cp)]
    runtime.main(run, cohort_monitor=lambda effective, output: observe(spec["condition"], effective, output, protocol))
    if loader:
        require(loader.wait(timeout=10) == 0, "선택된 자식의 loader가 실패했습니다.")
    ac_online(not protocol.get("portable"))
    require(scx.SCHED_EXT.read_text().strip() == "disabled", "실행 후 커널 스케줄러가 분리되지 않았습니다.")


def campaign(out, portable, build, scheduler_build, model):
    require(os.geteuid() != 0 and scx.SCHED_EXT.read_text().strip() == "disabled", "일반 계정에서 기존 커널 스케줄러를 정리한 후 실행하세요.")
    protocol = portable_protocol(build) if portable else P
    ac_online(not portable)
    out.mkdir(parents=True, exist_ok=False)
    manifest = runtime.verify_build(build)
    bundle = scx.verify_bundle(scheduler_build)
    require(sha(model) == protocol["model_sha256"], "원본 모델의 SHA-256과 일치하지 않습니다.")
    require(portable or protocol["device"] in Path("/proc/cpuinfo").read_text(), "원본 재현 모드는 지정된 AMD 장비 전용입니다. 다른 장비는 --portable을 사용하세요.")
    rows = list(schedule(protocol))
    save(out / "protocol.json", protocol)
    save(out / "schedule.json", rows)
    sources = [HERE / "protocol.json", Path(__file__), Path(runtime.__file__), Path(scx.__file__),
               Path(contention.__file__), Path(contention.__file__).with_name("load.py"), FIXTURES]
    source_dir = out / "sources"
    for path in sources:
        target = source_dir / path.relative_to(WS)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    save(out / "identity.json", {"kernel": platform.release(), "model_sha256": protocol["model_sha256"],
         "ac": ac_online(not portable), "runtime": manifest, "scheduler": bundle["artifacts"],
         "kernel_btf_sha256": bundle["btf_sha256"], "source_hashes": {str(p.relative_to(WS)): sha(p) for p in sources},
         "governors": {str(c): read_sysfs(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor", None)
                       for c in protocol["server_cpus"]}})
    for index, spec in enumerate(rows, 1):
        folder = out / f"{spec['condition']}-{spec['block']:02}" / spec["arm"]
        folder.mkdir(parents=True)
        print(f"{index}/{len(rows)} {spec['condition']} block {spec['block']} {spec['arm']}", flush=True)
        log_path = folder / "visit.log"
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "visit", str(folder),
                   "--build-dir", str(build), "--scheduler-build", str(scheduler_build),
                   "--model", str(model), "--spec", json.dumps(spec)]
        try:
            with log_path.open("x") as log:
                code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=310).returncode
        except subprocess.TimeoutExpired:
            code = 124
        if code:
            deadline = time.monotonic() + 20
            while scx.SCHED_EXT.read_text().strip() != "disabled" and time.monotonic() < deadline:
                time.sleep(.2)
            save(out / "failure.json", {"visit": spec, "returncode": code,
                 "sched_ext": scx.SCHED_EXT.read_text().strip(), "log": str(log_path)})
            raise RuntimeError(f"실험 실행이 실패했습니다. 로그를 확인하세요: {log_path}")
    print("모든 실행을 기록했습니다.", flush=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "visit"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--portable", action="store_true", help="현재 장비에서 허용된 CPU를 자동 선택합니다.")
    parser.add_argument("--build-dir", type=Path, default=BUILD)
    parser.add_argument("--scheduler-build", type=Path, default=BUNDLE)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--spec")
    args = parser.parse_args()
    out = args.out.resolve()
    paths = [path.resolve() for path in (args.build_dir, args.scheduler_build, args.model)]
    if args.mode == "run":
        campaign(out, args.portable, *paths)
    else:
        spec = json.loads(args.spec)
        protocol = read(out.parents[1] / "protocol.json")
        require(spec in list(schedule(protocol)), "사전 등록되지 않은 실행입니다.")
        visit(out, spec, protocol, *paths)


if __name__ == "__main__":
    main_entry(main)

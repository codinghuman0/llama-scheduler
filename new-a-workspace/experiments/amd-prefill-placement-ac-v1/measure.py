#!/usr/bin/env python3
"""Run the AC-powered AMD placement comparison with the integration-v2 selected-child runner."""
import argparse
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path
import platform
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
from intel_experiment import FIXTURES, read, require, save, sha

P = read(HERE / "protocol.json")
BUILD = STATE / "builds/prefill-pcore-openmp-v1"
BUNDLE = STATE / "prefill-pcore-scheduler-v2"
MODEL = WS.parents[1] / "model.gguf"
AC = Path("/sys/class/power_supply/ADP0/online")


def ac_online():
    value = int(AC.read_text())
    require(value == 1, "AC disconnected")
    return value


def schedule():
    for index, order in enumerate(P["arm_orders"]):
        conditions = P["conditions"] if index % 2 == 0 else P["conditions"][::-1]
        for condition in conditions:
            for arm in (order if condition == "ambient" else order[::-1]):
                yield {"block": index + 1, "condition": condition, "arm": arm, "cohort": P["cohorts"][index % 2]}


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
def observe(condition, effective, output):
    require(effective["cpus"] == P["server_cpus"], "Resolved AMD envelope changed")
    load = contention.ControlledLoad(output / "cpu25", P["cpu25"]["cpu"]) if condition == "cpu25" else nullcontext(None)
    with load as active:
        def snapshot(pid):
            ac = ac_online()
            tasks = thread_counts(pid)
            begin = time.monotonic_ns()
            external = active.snapshot() if active else None
            end = time.monotonic_ns()
            return {"ac": ac, "threads": tasks, "load": external, "load_clock_ns": (begin + end) // 2}
        yield snapshot


def visit(folder, spec):
    require(os.geteuid() != 0 and os.sched_getscheduler(0) == os.SCHED_OTHER, "Use an ordinary controller")
    ac_online()
    common = ["--build-dir", str(BUILD), "--resources", P["resources"], "--profile", P["profile"],
              "--policy", P["policy"], "--pool", P["pool"], "--transport", P["transport"]]
    run = ["run", *common, "--model", str(MODEL), "--output", str(folder / "run"),
           "--fixtures", spec["cohort"], P["secondary_fixture"], "--tokens", str(P["tokens_per_request"])]
    loader = None
    if spec["arm"] == "linux":
        run.append("--relaxed-host-checks")
    else:
        cp = folder / "checkpoint"
        runtime.main(["prepare-scx", "--relaxed-host-checks", *common, "--scheduler-build", str(BUNDLE),
                      "--variant", P["kernel_instrumentation"], "--scheduler-policy", spec["arm"],
                      "--owner-pid", str(os.getpid()), "--output", str(cp)])
        # prepare-scx emits the same bounded loader command used in the FULL smoke.
        # Its owner is this visit process. Owner exit also tears down an unregistered loader.
        loader = subprocess.Popen(["bash", str(cp / "load.sh")], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 30
        log = cp / "loader.log"
        while not log.is_file() or "waiting for selected child" not in log.read_text(errors="replace"):
            require(loader.poll() is None and time.monotonic() < deadline, f"Loader did not become ready, see {log}")
            time.sleep(.1)
        run += ["--scx-checkpoint", str(cp)]
    runtime.main(run, cohort_monitor=lambda effective, output: observe(spec["condition"], effective, output))
    if loader:
        require(loader.wait(timeout=10) == 0, "Selected-child loader failed")
    ac_online()
    require(scx.SCHED_EXT.read_text().strip() == "disabled", "Scheduler still attached")


def campaign(out):
    require(os.geteuid() != 0 and scx.SCHED_EXT.read_text().strip() == "disabled", "Start as ordinary Linux user")
    ac_online()
    out.mkdir(parents=True, exist_ok=False)
    manifest = runtime.verify_build(BUILD)
    bundle = scx.verify_bundle(BUNDLE)
    require(sha(MODEL) == P["model_sha256"], "Model digest differs")
    require(P["device"] in Path("/proc/cpuinfo").read_text(), "This protocol is for the named AMD device")
    rows = list(schedule())
    save(out / "protocol.json", P)
    save(out / "schedule.json", rows)
    sources = [HERE / "protocol.json", Path(__file__), Path(runtime.__file__), Path(scx.__file__),
               Path(contention.__file__), Path(contention.__file__).with_name("load.py"), FIXTURES]
    save(out / "identity.json", {"kernel": platform.release(), "model_sha256": P["model_sha256"],
         "ac": ac_online(), "runtime": manifest, "scheduler": bundle["artifacts"],
         "kernel_btf_sha256": bundle["btf_sha256"], "source_hashes": {str(p.relative_to(WS)): sha(p) for p in sources},
         "governors": {str(c): Path(f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_governor").read_text().strip()
                       for c in P["server_cpus"]}})
    for index, spec in enumerate(rows, 1):
        folder = out / f"{spec['condition']}-{spec['block']:02}" / spec["arm"]
        folder.mkdir(parents=True)
        print(f"{index}/{len(rows)} {spec['condition']} block {spec['block']} {spec['arm']}", flush=True)
        with (folder / "visit.log").open("x") as log:
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "visit", str(folder),
                                     "--spec", json.dumps(spec)], stdout=log, stderr=subprocess.STDOUT, timeout=310)
        if result.returncode:
            deadline = time.monotonic() + 20
            while scx.SCHED_EXT.read_text().strip() != "disabled" and time.monotonic() < deadline:
                time.sleep(.2)
            save(out / "failure.json", {"visit": spec, "returncode": result.returncode,
                 "sched_ext": scx.SCHED_EXT.read_text().strip(), "log": str(log.name)})
            raise RuntimeError(f"Visit failed. See {log.name}")
    print("All visits recorded", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "visit"))
    parser.add_argument("out", type=Path)
    parser.add_argument("--spec")
    args = parser.parse_args()
    if args.mode == "run":
        campaign(args.out.resolve())
    else:
        spec = json.loads(args.spec)
        require(spec in list(schedule()), "Invalid visit")
        visit(args.out.resolve(), spec)

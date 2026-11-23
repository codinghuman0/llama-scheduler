#!/usr/bin/env bash
set -Eeuo pipefail

# detect_host_topology.sh
#
# Resolve a reproducible CPU set for CPU-only llama.cpp experiments.
#
# Policy:
#   * Consider CPUs that are BOTH online and allowed to this process.
#   * Group logical CPUs by Linux physical topology:
#       physical_package_id + die_id + core_id
#   * Select exactly one allowed logical CPU from each physical core.
#   * Do NOT silently discard Intel/AMD heterogeneous core classes.
#   * Detect/report SMT/Hyper-Threading and heterogeneous-core hints.
#   * Produce shell-safe env output that benchmark/smoke scripts can reuse.
#
# Usage:
#   ./detect_host_topology.sh
#   ./detect_host_topology.sh --env /tmp/llama-topology.env
#
# No root privilege is required.

ENV_OUT=""
JSON_OUT=""

usage() {
    cat <<'EOF'
Usage: detect_host_topology.sh [--env FILE] [--json FILE]

  --env FILE   Also write the resolved topology as shell-safe KEY=VALUE lines.
  --json FILE  Also write machine-readable topology.
  -h, --help   Show this help.
EOF
}

while (($#)); do
    case "$1" in
        --env)
            (($# >= 2)) || { echo "ERROR: --env requires a file" >&2; exit 2; }
            ENV_OUT="$2"
            shift 2
            ;;
        --json)
            (($# >= 2)) || { echo "ERROR: --json requires a file" >&2; exit 2; }
            JSON_OUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: python3 is required" >&2
    exit 1
}

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 - "$ENV_OUT" "$JSON_OUT" >"$TMP" <<'PY'
import json
import os
import platform
import re
import shlex
import sys
from collections import defaultdict

env_out = sys.argv[1]
json_out = sys.argv[2]
SYS_CPU = "/sys/devices/system/cpu"

def read(path, default=""):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return default

def parse_cpulist(s):
    out = set()
    s = (s or "").strip()
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if b < a:
                a, b = b, a
            out.update(range(a, b + 1))
        else:
            out.add(int(part))
    return out

def fmt_cpulist(cpus):
    xs = sorted(set(cpus))
    if not xs:
        return ""
    ranges = []
    start = prev = xs[0]
    for x in xs[1:]:
        if x == prev + 1:
            prev = x
            continue
        ranges.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = x
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ",".join(ranges)

def fmt_csv(cpus):
    return ",".join(str(x) for x in sorted(set(cpus)))

def cpuinfo_first(field):
    text = read("/proc/cpuinfo")
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip().lower() == field.lower():
            return v.strip()
    return ""

def lscpu_field(field):
    try:
        import subprocess
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        p = subprocess.run(
            ["lscpu"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            check=False,
        )
        for line in p.stdout.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                if k.strip().lower() == field.lower():
                    return v.strip()
    except Exception:
        pass
    return ""

online = parse_cpulist(read(f"{SYS_CPU}/online"))
if not online:
    online = set(range(os.cpu_count() or 1))

allowed_line = ""
for line in read("/proc/self/status").splitlines():
    if line.startswith("Cpus_allowed_list:"):
        allowed_line = line.split(":", 1)[1].strip()
        break

allowed = parse_cpulist(allowed_line) if allowed_line else set(online)
usable = sorted(online & allowed)

if not usable:
    print("ERROR=No CPU is both online and allowed to this process")
    sys.exit(3)

vendor = cpuinfo_first("vendor_id") or lscpu_field("Vendor ID") or "unknown"
model = cpuinfo_first("model name") or lscpu_field("Model name") or platform.processor() or "unknown"

def topo_int(cpu, name, default):
    s = read(f"{SYS_CPU}/cpu{cpu}/topology/{name}", "")
    try:
        return int(s)
    except ValueError:
        return default

cores = defaultdict(list)
per_cpu = {}

for cpu in usable:
    package = topo_int(cpu, "physical_package_id", -1)
    die = topo_int(cpu, "die_id", -1)
    core = topo_int(cpu, "core_id", cpu)
    key = (package, die, core)
    cores[key].append(cpu)

    sib_path_new = f"{SYS_CPU}/cpu{cpu}/topology/core_cpus_list"
    sib_path_old = f"{SYS_CPU}/cpu{cpu}/topology/thread_siblings_list"
    siblings = parse_cpulist(read(sib_path_new) or read(sib_path_old))
    if not siblings:
        siblings = {cpu}

    per_cpu[cpu] = {
        "package": package,
        "die": die,
        "core": core,
        "siblings_all": sorted(siblings),
        "core_type_raw": read(f"{SYS_CPU}/cpu{cpu}/topology/core_type", ""),
        "max_freq_khz": read(f"{SYS_CPU}/cpu{cpu}/cpufreq/cpuinfo_max_freq", ""),
    }

selected = [min(cores[key]) for key in sorted(cores)]

smt_present = False
smt_effective = False
max_threads_per_core = 1

for rep in selected:
    siblings_online = set(per_cpu[rep]["siblings_all"]) & online
    siblings_usable = siblings_online & allowed
    max_threads_per_core = max(max_threads_per_core, len(siblings_online))
    if len(siblings_online) > 1:
        smt_present = True
    if len(siblings_usable) > 1:
        smt_effective = True

packages = sorted(set(per_cpu[c]["package"] for c in selected))
dies = sorted(set((per_cpu[c]["package"], per_cpu[c]["die"]) for c in selected))

numa_nodes = []
node_root = "/sys/devices/system/node"
if os.path.isdir(node_root):
    for name in sorted(os.listdir(node_root)):
        m = re.fullmatch(r"node(\d+)", name)
        if not m:
            continue
        cpus = parse_cpulist(read(os.path.join(node_root, name, "cpulist")))
        if cpus & set(usable):
            numa_nodes.append(int(m.group(1)))

core_type_by_core = {}
for rep in selected:
    v = per_cpu[rep]["core_type_raw"]
    if v != "":
        core_type_by_core[rep] = v

distinct_core_types = sorted(set(core_type_by_core.values()))
core_type_exposed = bool(core_type_by_core)
hetero_core_type = len(distinct_core_types) > 1

freqs = []
for rep in selected:
    v = per_cpu[rep]["max_freq_khz"]
    try:
        if v:
            freqs.append(int(v))
    except ValueError:
        pass

distinct_max_freqs = sorted(set(freqs))
hetero_freq_hint = len(distinct_max_freqs) > 1

vendor_upper = vendor.upper()
if "GENUINEINTEL" in vendor_upper or vendor_upper == "INTEL":
    vendor_family = "INTEL"
elif "AUTHENTICAMD" in vendor_upper or vendor_upper == "AMD":
    vendor_family = "AMD"
else:
    vendor_family = "OTHER"

vals = {
    "CPU_VENDOR_ID": vendor,
    "CPU_VENDOR_FAMILY": vendor_family,
    "CPU_MODEL": model,
    "CPU_ONLINE_LIST": fmt_cpulist(online),
    "CPU_ALLOWED_LIST": fmt_cpulist(allowed),
    "CPU_USABLE_LIST": fmt_cpulist(usable),
    "CPU_SELECTED_LIST": fmt_csv(selected),
    "CPU_SELECTED_CPULIST": fmt_cpulist(selected),
    "CPU_LOGICAL_USABLE": str(len(usable)),
    "CPU_PHYSICAL_CORES_USABLE": str(len(cores)),
    "CPU_SELECTED_COUNT": str(len(selected)),
    "CPU_THREADS": str(len(selected)),
    "CPU_THREADS_BATCH": str(len(selected)),
    "CPU_PACKAGES_USABLE": str(len(packages)),
    "CPU_DIES_USABLE": str(len(dies)),
    "CPU_NUMA_NODES_USABLE": str(len(numa_nodes) if numa_nodes else 1),
    "CPU_NUMA_NODE_LIST": ",".join(map(str, numa_nodes)) if numa_nodes else "unknown",
    "CPU_SMT_PRESENT": "1" if smt_present else "0",
    "CPU_SMT_EFFECTIVE": "1" if smt_effective else "0",
    "CPU_MAX_THREADS_PER_CORE": str(max_threads_per_core),
    "CPU_CORE_TYPE_EXPOSED": "1" if core_type_exposed else "0",
    "CPU_HETERO_CORE_TYPE": "1" if hetero_core_type else "0",
    "CPU_CORE_TYPE_RAW_VALUES": ",".join(distinct_core_types) if distinct_core_types else "unavailable",
    "CPU_HETERO_FREQ_HINT": "1" if hetero_freq_hint else "0",
    "CPU_MAX_FREQ_CLASSES_KHZ": ",".join(map(str, distinct_max_freqs)) if distinct_max_freqs else "unavailable",
}

print("=== HOST CPU ===")
print(f"vendor_id:             {vendor}")
print(f"vendor_family:         {vendor_family}")
print(f"model:                 {model}")
print(f"online CPUs:           {vals['CPU_ONLINE_LIST']}")
print(f"allowed CPUs:          {vals['CPU_ALLOWED_LIST']}")
print(f"usable CPUs:           {vals['CPU_USABLE_LIST']}")
print()
print("=== PHYSICAL TOPOLOGY ===")
print(f"packages:              {vals['CPU_PACKAGES_USABLE']}")
print(f"dies:                  {vals['CPU_DIES_USABLE']}")
print(f"physical cores usable: {len(cores)}")
print(f"logical CPUs usable:   {len(usable)}")
print(f"SMT/HT present:        {'yes' if smt_present else 'no'}")
print(f"SMT/HT effective:      {'yes' if smt_effective else 'no'}")
print(f"max threads/core:      {max_threads_per_core}")
print(f"NUMA nodes usable:     {vals['CPU_NUMA_NODES_USABLE']} ({vals['CPU_NUMA_NODE_LIST']})")
print()
print("=== HETEROGENEOUS-CORE OBSERVATION ===")
print(f"core_type exposed:     {'yes' if core_type_exposed else 'no'}")
print(f"core_type raw values:  {vals['CPU_CORE_TYPE_RAW_VALUES']}")
print(f"multiple core types:   {'yes' if hetero_core_type else 'no'}")
print(f"max-freq classes kHz:  {vals['CPU_MAX_FREQ_CLASSES_KHZ']}")
print(f"frequency hetero hint: {'yes' if hetero_freq_hint else 'no'}")
print("selection policy:      keep every physical core; do not silently drop a core class")
print()
print("=== RESOLVED LLAMA EXPERIMENT CONFIG ===")
print(f"selected CPUs:         {vals['CPU_SELECTED_LIST']}")
print(f"selected cpulist:      {vals['CPU_SELECTED_CPULIST']}")
print(f"threads:               {vals['CPU_THREADS']}")
print(f"threads-batch:         {vals['CPU_THREADS_BATCH']}")

if len(numa_nodes) > 1:
    print()
    print("WARNING: multiple usable NUMA nodes detected; selection spans them.")

if hetero_core_type or hetero_freq_hint:
    print()
    print("NOTE: heterogeneous-core characteristics detected or hinted.")
    print("      CPU selection remains topology-neutral; benchmark metadata must retain this fact.")

print()
print("=== CORE MAP ===")
for key in sorted(cores):
    logical = sorted(cores[key])
    rep = min(logical)
    d = per_cpu[rep]
    core_type = d["core_type_raw"] or "-"
    max_freq = d["max_freq_khz"] or "-"
    siblings_all = ",".join(map(str, d["siblings_all"]))
    print(
        f"package={key[0]} die={key[1]} core={key[2]} "
        f"allowed_logical={','.join(map(str, logical))} selected={rep} "
        f"kernel_siblings={siblings_all} core_type_raw={core_type} max_freq_khz={max_freq}"
    )

print()
print("TOPOLOGY_RESULT=PASS")

if env_out:
    parent = os.path.dirname(os.path.abspath(env_out))
    os.makedirs(parent, exist_ok=True)
    tmp = env_out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Generated by detect_host_topology.sh\n")
        for k in sorted(vals):
            f.write(f"{k}={shlex.quote(vals[k])}\n")
        f.write("TOPOLOGY_RESULT=PASS\n")
    os.replace(tmp, env_out)

if json_out:
    value = dict(vendor=vendor, model=model, online_cpus=sorted(online), allowed_cpus=sorted(allowed), usable_cpus=usable,
                 physical_core_representatives=selected, physical_cores=len(cores), logical_cpus=len(usable),
                 smt=dict(present=smt_present, effective=smt_effective, max_threads_per_core=max_threads_per_core,
                          active=read(f"{SYS_CPU}/smt/active", "unavailable"), control=read(f"{SYS_CPU}/smt/control", "unavailable")),
                 packages=packages, dies=dies, numa_nodes=numa_nodes, cpus=per_cpu,
                 heterogeneous=dict(core_type_exposed=core_type_exposed, multiple_core_types=hetero_core_type,
                                    core_types=distinct_core_types, frequency_hint=hetero_freq_hint, max_freq_classes_khz=distinct_max_freqs))
    os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
    with open(json_out + ".tmp", "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(json_out + ".tmp", json_out)
PY

cat "$TMP"

if [[ -n "$ENV_OUT" ]]; then
    printf '\nTopology env written to: %s\n' "$ENV_OUT"
fi

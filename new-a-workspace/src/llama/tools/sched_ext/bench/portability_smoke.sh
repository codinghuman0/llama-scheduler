#!/usr/bin/env bash
set -Eeuo pipefail

# portability_smoke.sh
#
# Runtime correctness smoke for the frozen lightweight Base:
#   1) default Linux scheduler inference
#   2) neutral sched_ext selected-child inference
#   3) external observation of UNKNOWN -> PREFILL -> DECODE
#   4) lifecycle cleanup
#
# Expected environment:
#   MODEL=/path/to/model.gguf
#   TOPOLOGY_ENV=/path/to/topology.env
#
# Run as a normal user. The script asks sudo once and then uses sudo -n.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || pwd)"

MODEL="${MODEL:-$(dirname "$REPO_ROOT")/model.gguf}"
TOPOLOGY_ENV="${TOPOLOGY_ENV:-$REPO_ROOT/build-lightweight-dev/portability/topology.env}"
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/build-lightweight-dev}"
PORT="${PORT:-18080}"
EXPECTED_MODEL_SHA256="${EXPECTED_MODEL_SHA256:-f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840}"

SERVER="$BUILD_DIR/bin/llama-server"
MARKER="$BUILD_DIR/bin/libllama-server-impl.so"
SCHED="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx"
CHILD="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx_child"

RUN_DIR="$BUILD_DIR/portability/runtime-smoke"
mkdir -p "$RUN_DIR"

DEFAULT_PGID=""
CHILD_PGID=""
LOADER_PID=""

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32mPASS\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mERROR\033[0m  %s\n' "$*" >&2; exit 1; }

kill_group_user() {
    local pgid="${1:-}"
    [[ -n "$pgid" ]] || return 0
    kill -INT -- "-$pgid" 2>/dev/null || true
    sleep 0.2
    kill -TERM -- "-$pgid" 2>/dev/null || true
}

kill_root_process() {
    local pid="${1:-}"
    [[ -n "$pid" ]] || return 0
    # sudo itself owns/monitors the privileged child and relays signals to it.
    sudo -n kill -INT "$pid" 2>/dev/null || true
    sleep 0.2
    sudo -n kill -TERM "$pid" 2>/dev/null || true
}

cleanup() {
    set +e
    kill_group_user "$DEFAULT_PGID"
    kill_group_user "$CHILD_PGID"
    kill_root_process "$LOADER_PID"
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$REPO_ROOT"

[[ -f "$MODEL" ]] || die "model not found: $MODEL"
[[ -f "$TOPOLOGY_ENV" ]] || die "topology env not found: $TOPOLOGY_ENV"
[[ -x "$SERVER" ]] || die "llama-server missing: $SERVER"
[[ -f "$MARKER" ]] || die "marker ELF missing: $MARKER"
[[ -x "$SCHED" ]] || die "scheduler missing: $SCHED"
[[ -x "$CHILD" ]] || die "child launcher missing: $CHILD"
command -v curl >/dev/null 2>&1 || die "curl missing"
command -v taskset >/dev/null 2>&1 || die "taskset missing"
command -v setsid >/dev/null 2>&1 || die "setsid missing"
command -v bpftool >/dev/null 2>&1 || die "bpftool missing"

# shellcheck disable=SC1090
source "$TOPOLOGY_ENV"
[[ "${TOPOLOGY_RESULT:-}" == "PASS" ]] || die "topology env does not contain TOPOLOGY_RESULT=PASS"
[[ -n "${CPU_SELECTED_LIST:-}" ]] || die "CPU_SELECTED_LIST missing"
[[ -n "${CPU_THREADS:-}" ]] || die "CPU_THREADS missing"
[[ -n "${CPU_THREADS_BATCH:-}" ]] || die "CPU_THREADS_BATCH missing"

say "Smoke configuration"
printf 'repo:          %s\n' "$REPO_ROOT"
printf 'model:         %s\n' "$MODEL"
printf 'selected CPUs: %s\n' "$CPU_SELECTED_LIST"
printf 'threads:       %s\n' "$CPU_THREADS"
printf 'threads-batch: %s\n' "$CPU_THREADS_BATCH"

ACTUAL_SHA="$(sha256sum "$MODEL" | awk '{print $1}')"
[[ "$ACTUAL_SHA" == "$EXPECTED_MODEL_SHA256" ]] || \
    die "model SHA256 mismatch: got $ACTUAL_SHA"
ok "model SHA256"

if [[ "$(cat /sys/kernel/sched_ext/state 2>/dev/null || echo unavailable)" != "disabled" ]]; then
    die "sched_ext must be disabled before smoke"
fi
ok "sched_ext initially disabled"

say "Refreshing sudo credential"
sudo -v

wait_health() {
    local seconds="${1:-90}"
    local i
    for ((i=0; i<seconds*5; i++)); do
        if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.2
    done
    return 1
}

request_once() {
    local outfile="$1"
    local http
    http="$(
        curl -sS \
          -o "$outfile" \
          -w '%{http_code}' \
          -H 'Content-Type: application/json' \
          -d '{
            "prompt":"CPU scheduling determines which runnable task receives processor time. For CPU-only language-model inference, prompt processing and token generation have different execution patterns. This is a small portability smoke request.",
            "n_predict":32,
            "temperature":0,
            "stream":false
          }' \
          "http://127.0.0.1:$PORT/completion"
    )"
    [[ "$http" =~ ^2[0-9][0-9]$ ]] || {
        printf 'HTTP status: %s\n' "$http" >&2
        cat "$outfile" >&2 || true
        return 1
    }
}

say "Default Linux scheduler smoke"
rm -f "$RUN_DIR/default-server.log" "$RUN_DIR/default-response.json"

setsid taskset -c "$CPU_SELECTED_LIST" \
  "$SERVER" \
    -m "$MODEL" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --n-gpu-layers 0 \
    --threads "$CPU_THREADS" \
    --threads-batch "$CPU_THREADS_BATCH" \
    --threads-http 2 \
    --server-compute-profile-mode phase \
    >"$RUN_DIR/default-server.log" 2>&1 &
DEFAULT_PGID=$!

wait_health 120 || {
    tail -100 "$RUN_DIR/default-server.log" >&2 || true
    die "default llama-server did not become healthy"
}

request_once "$RUN_DIR/default-response.json" || die "default completion request failed"
ok "default Linux inference returned HTTP 2xx"

kill_group_user "$DEFAULT_PGID"
wait "$DEFAULT_PGID" 2>/dev/null || true
DEFAULT_PGID=""

sleep 0.3
if pgrep -f "$SERVER" >/dev/null 2>&1; then
    die "llama-server remained after default smoke cleanup"
fi
ok "default server cleanup"

say "Neutral sched_ext + phase transport smoke"
PHASE_SOCK="@llama-phase-portability-$$"
rm -f \
  "$RUN_DIR/sched-loader.log" \
  "$RUN_DIR/sched-server.log" \
  "$RUN_DIR/phase-observer.log"

# Start the privileged loader while sudo still sees the current controlling TTY.
# Do not put `setsid` before sudo: Ubuntu sudo timestamps are commonly TTY-scoped.
sudo -n "$SCHED" \
  --phase-uid "$(id -u)" \
  --phase-register-socket "$PHASE_SOCK" \
  --server-exe "$SERVER" \
  --marker-elf "$MARKER" \
  >"$RUN_DIR/sched-loader.log" 2>&1 &
LOADER_PID=$!

# Wait for struct_ops attachment.
for _ in $(seq 1 100); do
    state="$(cat /sys/kernel/sched_ext/state 2>/dev/null || true)"
    [[ "$state" == "enabled" ]] && break
    if ! kill -0 "$LOADER_PID" 2>/dev/null; then
        cat "$RUN_DIR/sched-loader.log" >&2 || true
        die "scheduler loader exited before sched_ext became enabled"
    fi
    sleep 0.1
done

[[ "$(cat /sys/kernel/sched_ext/state 2>/dev/null || true)" == "enabled" ]] || {
    cat "$RUN_DIR/sched-loader.log" >&2 || true
    die "sched_ext did not become enabled"
}
ok "sched_ext enabled"

setsid taskset -c "$CPU_SELECTED_LIST" \
  "$CHILD" \
    --phase-register-socket "$PHASE_SOCK" \
    -- \
    "$SERVER" \
      -m "$MODEL" \
      --host 127.0.0.1 \
      --port "$PORT" \
      --n-gpu-layers 0 \
      --threads "$CPU_THREADS" \
      --threads-batch "$CPU_THREADS_BATCH" \
      --threads-http 2 \
      --server-compute-profile-mode phase \
      >"$RUN_DIR/sched-server.log" 2>&1 &
CHILD_PGID=$!

wait_health 120 || {
    tail -100 "$RUN_DIR/sched-server.log" >&2 || true
    tail -100 "$RUN_DIR/sched-loader.log" >&2 || true
    die "sched_ext llama-server did not become healthy"
}

# Embedded observer + request. It reads only the tiny 12-byte control state.
MODEL_PORT="$PORT" RUN_DIR_ENV="$RUN_DIR" python3 <<'PY' | tee "$RUN_DIR/phase-observer.log"
import json
import os
import struct
import subprocess
import threading
import time
import urllib.request

port = int(os.environ["MODEL_PORT"])
run_dir = os.environ["RUN_DIR_ENV"]

def run_json(*args):
    out = subprocess.check_output(
        ["sudo", "-n", "bpftool", "-j", *args],
        text=True,
    )
    return json.loads(out)

def value_size(m):
    return m.get("bytes_value", m.get("value_size"))

maps = run_json("map", "show")
candidates = [
    m for m in maps
    if value_size(m) == 12 and m.get("max_entries") == 1
]

preferred = [
    m for m in candidates
    if "llama" in str(m.get("name", "")).lower()
       or ".data" in str(m.get("name", "")).lower()
]

if len(preferred) == 1:
    candidates = preferred

if len(candidates) != 1:
    print("12-byte map candidates:")
    for m in candidates:
        print(json.dumps(m, sort_keys=True))
    raise RuntimeError(f"expected exactly one control map, found {len(candidates)}")

map_id = candidates[0]["id"]
print(f"CONTROL_MAP_ID={map_id}")

def as_byte(x):
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    if len(s) <= 2 and all(c in "0123456789abcdefABCDEF" for c in s):
        return int(s, 16)
    return int(s, 0)

def read_state():
    dump = run_json("map", "dump", "id", str(map_id))
    if not dump:
        raise RuntimeError("empty control map dump")
    raw = bytes(as_byte(x) for x in dump[0]["value"])
    if len(raw) < 12:
        raise RuntimeError(f"short control state: {len(raw)} bytes")
    return struct.unpack_from("<III", raw, 0)

phase_names = {0: "UNKNOWN", 1: "PREFILL", 2: "DECODE", 3: "MIXED"}

selected, phase, exit_kind = read_state()
print(
    f"INITIAL selected_tgid={selected} "
    f"phase={phase}({phase_names.get(phase, 'INVALID')}) exit_kind={exit_kind}"
)
if selected == 0:
    raise RuntimeError("selected_tgid is zero after child registration")

result = {"status": None, "error": None}

# Long enough PREFILL to make a correctness observer reliable even on a fast host,
# but still small enough to avoid turning this into a performance benchmark.
base = (
    "CPU-only language-model inference executes many matrix operations and "
    "then repeatedly generates tokens. A scheduler experiment must keep "
    "the model, CPU affinity, and thread count fixed while changing only "
    "the scheduling policy. "
)
prompt = base * 24

payload = json.dumps({
    "prompt": prompt,
    "n_predict": 48,
    "temperature": 0,
    "stream": False,
}).encode()

def do_request():
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/completion",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            result["status"] = r.status
            r.read()
    except Exception as e:
        result["error"] = repr(e)

t = threading.Thread(target=do_request, daemon=True)
t.start()

observed = []
last = None
deadline = time.monotonic() + 180

while time.monotonic() < deadline:
    selected, phase, exit_kind = read_state()
    if phase != last:
        print(
            f"PHASE t={time.monotonic():.6f} "
            f"selected_tgid={selected} value={phase} "
            f"name={phase_names.get(phase, 'INVALID')} exit_kind={exit_kind}"
        )
        observed.append(phase)
        last = phase

    if not t.is_alive():
        # Sample a few more times after HTTP completion.
        for _ in range(5):
            time.sleep(0.01)
            selected, phase, exit_kind = read_state()
            if phase != last:
                print(
                    f"PHASE t={time.monotonic():.6f} "
                    f"selected_tgid={selected} value={phase} "
                    f"name={phase_names.get(phase, 'INVALID')} exit_kind={exit_kind}"
                )
                observed.append(phase)
                last = phase
        break

    time.sleep(0.005)

t.join(timeout=1)

print(f"HTTP_STATUS={result['status']}")
print(f"HTTP_ERROR={result['error']}")
print(f"OBSERVED_PHASE_VALUES={observed}")
print(f"OBSERVED_PHASE_NAMES={[phase_names.get(v, 'INVALID') for v in observed]}")

if result["error"] is not None:
    raise RuntimeError(result["error"])
if result["status"] is None or not (200 <= result["status"] < 300):
    raise RuntimeError(f"HTTP failure: {result['status']}")

try:
    prefill_i = observed.index(1)
    decode_i = observed.index(2)
except ValueError as e:
    raise RuntimeError(f"missing PREFILL or DECODE: {observed}") from e

if prefill_i >= decode_i:
    raise RuntimeError(f"wrong phase order: {observed}")

print()
print("PHASE_TRANSPORT_SMOKE_RESULT=PASS")
PY

ok "PREFILL -> DECODE transport"

kill_group_user "$CHILD_PGID"
wait "$CHILD_PGID" 2>/dev/null || true
CHILD_PGID=""

# The loader normally exits after the selected child is gone. Give it time.
for _ in $(seq 1 30); do
    if ! kill -0 "$LOADER_PID" 2>/dev/null; then
        break
    fi
    sleep 0.1
done

if kill -0 "$LOADER_PID" 2>/dev/null; then
    kill_root_process "$LOADER_PID"
fi
wait "$LOADER_PID" 2>/dev/null || true
LOADER_PID=""

# sched_ext/BPF teardown may be briefly asynchronous.
for _ in $(seq 1 50); do
    [[ "$(cat /sys/kernel/sched_ext/state 2>/dev/null || true)" == "disabled" ]] && break
    sleep 0.1
done

[[ "$(cat /sys/kernel/sched_ext/state 2>/dev/null || true)" == "disabled" ]] || \
    die "sched_ext remained enabled after cleanup"
ok "sched_ext disabled after cleanup"

if pgrep -f "$SERVER" >/dev/null 2>&1; then
    die "llama-server remained after sched_ext cleanup"
fi
ok "no llama-server remains"

if pgrep -f "$SCHED" >/dev/null 2>&1; then
    die "llama_scx loader remained after cleanup"
fi
ok "no llama_scx loader remains"

if [[ -n "$(git status --short)" ]]; then
    git status --short >&2
    die "Git worktree changed during portability smoke"
fi
ok "Git worktree clean"

# Remaining project-named BPF objects are diagnostic only here because the
# kernel can retire BPF objects asynchronously and unrelated sched_ext objects
# may exist on the host.
{
    echo "=== remaining project-named BPF programs ==="
    sudo -n bpftool prog show 2>/dev/null | grep -Ei 'llama' || true
    echo "=== remaining project-named BPF maps ==="
    sudo -n bpftool map show 2>/dev/null | grep -Ei 'llama' || true
} >"$RUN_DIR/post-cleanup-bpf.txt"

if grep -E '^[0-9]+:' "$RUN_DIR/post-cleanup-bpf.txt" >/dev/null 2>&1; then
    printf 'WARN  project-named BPF object may still be visible; inspect %s\n' \
      "$RUN_DIR/post-cleanup-bpf.txt"
fi

trap - EXIT INT TERM

printf '\n\033[1;32mDESKTOP_PORTABILITY_SMOKE_RESULT=PASS\033[0m\n'

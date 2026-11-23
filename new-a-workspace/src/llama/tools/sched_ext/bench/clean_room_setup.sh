#!/usr/bin/env bash
set -Eeuo pipefail

# clean_room_setup.sh
#
# One-command setup + correctness validation after cloning the repository.
#
# Clean-room preconditions:
#   * Ubuntu host with Internet access
#   * Git is installed so the repository can be cloned
#   * The validated model already exists outside Git
#
# Default layout after:
#   git clone https://github.com/codinghuman0/llama-scheduler-base.git \
#       ~/projects/llama.cpp-lightweight
#
#   ~/projects/
#     model.gguf
#     llama.cpp-lightweight/
#
# Usage from repository root:
#   ./tools/sched_ext/bench/clean_room_setup.sh
#
# Optional:
#   MODEL=/path/model.gguf BUILD_JOBS=4 ./tools/sched_ext/bench/clean_room_setup.sh
#   RUN_SMOKE=0 ./tools/sched_ext/bench/clean_room_setup.sh
#
# Setup runs correctness smoke only; no performance campaign.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: run this script from a cloned Git repository" >&2
    exit 1
}

MODEL="${MODEL:-$(dirname "$REPO_ROOT")/model.gguf}"
BUILD_DIR="${BUILD_DIR:-$REPO_ROOT/build-lightweight-dev}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"
RUN_SMOKE="${RUN_SMOKE:-1}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"

RELEASE_TAG="lightweight-base-v1-release"
EXPECTED_RELEASE_COMMIT="3f2f968cd6a8904f97659f82ca2ebbd10ce8b04a"
EXPECTED_MODEL_SHA256="f3bdf9cf31dee4b57ae4e455a1cb0d01b5c2c1b50d72d3112141c195506c2840"
EXPECTED_MODEL_SIZE="1117321312"

DETECTOR="$SCRIPT_DIR/detect_host_topology.sh"
SMOKE="$SCRIPT_DIR/portability_smoke.sh"

PASS=0
WARN=0
BLOCK=0

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32mPASS\033[0m  %s\n' "$*"; PASS=$((PASS+1)); }
warn() { printf '\033[1;33mWARN\033[0m  %s\n' "$*"; WARN=$((WARN+1)); }
block(){ printf '\033[1;31mBLOCKED\033[0m  %s\n' "$*"; BLOCK=$((BLOCK+1)); }
die()  { printf '\033[1;31mERROR\033[0m  %s\n' "$*" >&2; exit 1; }

trap 'printf "\nERROR at line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

cd "$REPO_ROOT"

[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || { block "Linux x86_64 is required"; exit 2; }
[[ "$(id -u)" != 0 && "$(id -u)" == "$(stat -c %u "$REPO_ROOT")" ]] || die "run as the non-root repository owner"
if [[ "$INSTALL_DEPS" == "1" ]]; then
    command -v apt-get >/dev/null 2>&1 || die "automated package installation requires apt-get; install dependencies manually and set INSTALL_DEPS=0 on other Linux hosts"
fi
command -v sudo >/dev/null 2>&1 || die "sudo is required"
[[ -x "$DETECTOR" ]] || die "topology detector missing/not executable: $DETECTOR"
[[ -x "$SMOKE" ]] || die "portability smoke missing/not executable: $SMOKE"

say "Repository identity"
printf 'root:   %s\n' "$REPO_ROOT"
printf 'branch: %s\n' "$(git branch --show-current)"
printf 'HEAD:   %s\n' "$(git rev-parse HEAD)"
printf 'origin: %s\n' "$(git remote get-url origin 2>/dev/null || echo none)"

[[ -z "$(git status --porcelain)" ]] || {
    git status --short >&2
    die "worktree must be clean before clean-room setup"
}
ok "Git worktree clean"

python3 -B -c 'import sys; sys.path.insert(0, "tools/sched_ext/bench"); from common import repo_check; from host_profile import require_refreshable; repo_check(); require_refreshable()'

if git rev-parse -q --verify "refs/tags/$RELEASE_TAG" >/dev/null; then
    RELEASE_COMMIT="$(git rev-parse "$RELEASE_TAG^{commit}")"
    [[ "$RELEASE_COMMIT" == "$EXPECTED_RELEASE_COMMIT" ]] || \
        block "$RELEASE_TAG -> $RELEASE_COMMIT, expected $EXPECTED_RELEASE_COMMIT"
    [[ "$RELEASE_COMMIT" == "$EXPECTED_RELEASE_COMMIT" ]] && \
        ok "immutable release tag verified"
else
    block "missing release tag $RELEASE_TAG"
fi

say "Host snapshot"
cat /etc/os-release | grep -E '^(NAME|VERSION|VERSION_ID|VERSION_CODENAME)=' || true
printf 'kernel: %s\n' "$(uname -r)"
printf 'arch:   %s\n' "$(uname -m)"
printf 'nproc:  %s\n' "$(nproc)"
df -h "$HOME" | tail -1 || true

say "Model identity"
if [[ ! -f "$MODEL" ]]; then
    block "model not found: $MODEL"
else
    MODEL_SIZE="$(stat -c '%s' "$MODEL")"
    MODEL_SHA="$(sha256sum "$MODEL" | awk '{print $1}')"
    printf 'model:  %s\n' "$MODEL"
    printf 'size:   %s\n' "$MODEL_SIZE"
    printf 'sha256: %s\n' "$MODEL_SHA"

    [[ "$MODEL_SIZE" == "$EXPECTED_MODEL_SIZE" ]] \
        && ok "model byte size" \
        || block "model size mismatch"

    [[ "$MODEL_SHA" == "$EXPECTED_MODEL_SHA256" ]] \
        && ok "model SHA256" \
        || block "model SHA256 mismatch"
fi

[[ -r /sys/kernel/sched_ext/state && -r /sys/kernel/btf/vmlinux ]] || {
    block "required sched_ext/BTF kernel interfaces missing"
    printf "CLEAN_ROOM_PREFLIGHT_RESULT=BLOCKED\n"
    exit 2
}

if [[ "$INSTALL_DEPS" == "1" ]]; then
    say "Refreshing sudo credential"
    sudo -v

    say "Installing build/runtime dependencies"
    sudo apt-get update

    REQUIRED_PKGS=(
        ca-certificates
        git
        curl
        wget
        rsync
        build-essential
        binutils
        cmake
        ninja-build
        pkg-config
        python3
        python3-venv
        python3-pip
        clang
        llvm
        lld
        libbpf-dev
        libelf-dev
        zlib1g-dev
        libcurl4-openssl-dev
        jq
        bc
        numactl
        stress-ng
        bpftrace
        linux-tools-common
        util-linux
    )

    sudo apt-get install -y "${REQUIRED_PKGS[@]}"
    KERNEL_HEADERS="linux-headers-$(uname -r)"
    if apt-cache show "$KERNEL_HEADERS" >/dev/null 2>&1; then
        sudo apt-get install -y "$KERNEL_HEADERS"
    fi

    if apt-cache show dwarves >/dev/null 2>&1; then
        sudo apt-get install -y dwarves
    fi

    KERNEL_TOOLS="linux-tools-$(uname -r)"
    if apt-cache show "$KERNEL_TOOLS" >/dev/null 2>&1; then
        sudo apt-get install -y "$KERNEL_TOOLS"
    else
        warn "$KERNEL_TOOLS not available from configured repositories"
    fi

    if ! command -v bpftool >/dev/null 2>&1 && apt-cache show bpftool >/dev/null 2>&1; then
        sudo apt-get install -y bpftool
    fi

else
    warn "dependency installation skipped; validate installed environment"
fi

say "Required command check"
REQUIRED_CMDS=(
    git gcc g++ cmake ninja clang llvm-config python3
    bpftool bpftrace perf curl taskset setsid nm readelf
)
for cmd in "${REQUIRED_CMDS[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        printf '%-12s ' "$cmd"
        case "$cmd" in
            git) git --version ;;
            gcc|g++) "$cmd" --version | head -1 ;;
            cmake) cmake --version | head -1 ;;
            ninja) ninja --version ;;
            clang) clang --version | head -1 ;;
            llvm-config) llvm-config --version ;;
            python3) python3 --version ;;
            bpftool) bpftool version | head -1 ;;
            bpftrace) bpftrace --version ;;
            perf) perf --version ;;
            *) printf 'available\n' ;;
        esac
        ok "$cmd available"
    else
        block "$cmd missing"
    fi
done

say "Kernel sched_ext/BTF preflight"
if [[ -r /sys/kernel/sched_ext/state ]]; then
    printf 'sched_ext state: %s\n' "$(cat /sys/kernel/sched_ext/state)"
    ok "sched_ext sysfs interface"
else
    block "/sys/kernel/sched_ext/state missing"
fi

if [[ -r /sys/kernel/btf/vmlinux ]]; then
    ok "kernel BTF available"
else
    block "/sys/kernel/btf/vmlinux missing"
fi

CONFIG_FILE="/boot/config-$(uname -r)"
if [[ -r "$CONFIG_FILE" ]]; then
    for opt in CONFIG_BPF CONFIG_BPF_SYSCALL CONFIG_SCHED_CLASS_EXT CONFIG_DEBUG_INFO_BTF; do
        if grep -qx "${opt}=y" "$CONFIG_FILE"; then
            ok "$opt=y"
        else
            block "$opt is not =y"
        fi
    done
else
    warn "running kernel config is not readable at $CONFIG_FILE"
fi

say "Disk headroom"
FREE_KB="$(df -Pk "$HOME" | awk 'NR==2 {print $4}')"
FREE_GIB=$(( FREE_KB / 1024 / 1024 ))
printf 'free GiB (integer): %s\n' "$FREE_GIB"
if (( FREE_GIB < 3 )); then
    block "less than 3 GiB free"
elif (( FREE_GIB < 6 )); then
    warn "less than 6 GiB free; setup should fit, but benchmark headroom is limited"
else
    ok "disk headroom"
fi

if (( BLOCK > 0 )); then
    printf '\n\033[1;31mCLEAN_ROOM_PREFLIGHT_RESULT=BLOCKED\033[0m\n'
    exit 2
fi

say "Topology detection"
[[ "$BUILD_DIR" == "$REPO_ROOT"/build-* && ! -L "$BUILD_DIR" ]] || die "BUILD_DIR must be a repository-local build-* directory"
mkdir -p "$BUILD_DIR"
mkdir -p "$BUILD_DIR/portability"

TOPOLOGY_ENV="$BUILD_DIR/portability/topology.env"
"$DETECTOR" --env "$TOPOLOGY_ENV" | tee "$BUILD_DIR/portability/topology.log"

# shellcheck disable=SC1090
source "$TOPOLOGY_ENV"
[[ "${TOPOLOGY_RESULT:-}" == "PASS" ]] || die "topology detector did not PASS"
[[ "${CPU_SELECTED_COUNT:-0}" -ge 1 ]] || die "topology detector selected no CPU"
ok "host topology resolved"

say "llama-server build: HINT ON / TRACE OFF"
cmake -S . -B "$BUILD_DIR" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DLLAMA_SCX_PHASE_HINT=ON \
    -DLLAMA_SCX_PHASE_TRACE=OFF

cmake --build "$BUILD_DIR" \
    --target llama-server \
    --parallel "$BUILD_JOBS"

SERVER="$BUILD_DIR/bin/llama-server"
MARKER="$BUILD_DIR/bin/libllama-server-impl.so"

[[ -x "$SERVER" ]] || die "llama-server missing after build"
[[ -f "$MARKER" ]] || die "libllama-server-impl.so missing after build"
ok "llama-server build"

CACHE_HINT="$(grep -E '^LLAMA_SCX_PHASE_HINT:BOOL=' "$BUILD_DIR/CMakeCache.txt" || true)"
CACHE_TRACE="$(grep -E '^LLAMA_SCX_PHASE_TRACE:BOOL=' "$BUILD_DIR/CMakeCache.txt" || true)"
printf '%s\n%s\n' "$CACHE_HINT" "$CACHE_TRACE"
[[ "$CACHE_HINT" == "LLAMA_SCX_PHASE_HINT:BOOL=ON" ]] || block "HINT cache value is not ON"
[[ "$CACHE_TRACE" == "LLAMA_SCX_PHASE_TRACE:BOOL=OFF" ]] || block "TRACE cache value is not OFF"

# Do not use grep -q in a pipe under pipefail: grep -q may close the pipe early
# and make nm receive SIGPIPE, creating a false negative.
MARKER_MATCH="$(
    nm -D "$MARKER" 2>/dev/null \
      | grep -E '[[:space:]]llama_scx_phase_v1$' \
      || true
)"
if [[ -n "$MARKER_MATCH" ]]; then
    printf '%s\n' "$MARKER_MATCH"
    ok "llama_scx_phase_v1 dynamic export"
else
    block "llama_scx_phase_v1 dynamic export missing"
fi

say "Fresh lightweight sched_ext build"
if ! make -B -C "$REPO_ROOT/tools/sched_ext" -j"$BUILD_JOBS"; then
    block "neutral scheduler build failed; check matching kernel UAPI headers and compiler/libbpf support"
    printf 'CLEAN_ROOM_BUILD_RESULT=BLOCKED\n'
    exit 2
fi

SCHED="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx"
CHILD="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx_child"
BPF_OBJ="$REPO_ROOT/tools/sched_ext/build/llama_scx.bpf.o"

[[ -x "$SCHED" ]] || block "scheduler loader missing"
[[ -x "$CHILD" ]] || block "child launcher missing"
[[ -f "$BPF_OBJ" ]] || block "BPF object missing"
(( BLOCK == 0 )) && ok "fresh sched_ext build"

if (( BLOCK > 0 )); then
    printf '\n\033[1;31mCLEAN_ROOM_BUILD_RESULT=BLOCKED\033[0m\n'
    exit 2
fi

if [[ "$RUN_SMOKE" == "1" ]]; then
    say "Runtime portability smoke"
    MODEL="$MODEL" \
    TOPOLOGY_ENV="$TOPOLOGY_ENV" \
    BUILD_DIR="$BUILD_DIR" \
    EXPECTED_MODEL_SHA256="$EXPECTED_MODEL_SHA256" \
      "$SMOKE"
    ok "runtime portability smoke"
else
    warn "runtime smoke skipped because RUN_SMOKE=$RUN_SMOKE"
fi

say "Generate portable benchmark host profile"
python3 -B "$SCRIPT_DIR/host_profile.py" --model "$MODEL" --refresh
ok "portable host profile generated"

say "Final clean-room state"
printf 'repo:          %s\n' "$REPO_ROOT"
printf 'HEAD:          %s\n' "$(git rev-parse HEAD)"
printf 'model:         %s\n' "$MODEL"
printf 'model sha256:  %s\n' "$(sha256sum "$MODEL" | awk '{print $1}')"
printf 'kernel:        %s\n' "$(uname -r)"
printf 'sched_ext:     %s\n' "$(cat /sys/kernel/sched_ext/state 2>/dev/null || echo unavailable)"
printf 'selected CPUs: %s\n' "${CPU_SELECTED_LIST:-unknown}"
printf 'threads:       %s\n' "${CPU_THREADS:-unknown}"
printf 'build dir:     %s\n' "$BUILD_DIR"

if [[ -n "$(git status --short)" ]]; then
    git status --short >&2
    die "worktree is not clean at end of setup"
fi

printf '\nPASS checks:    %d\n' "$PASS"
printf 'WARN checks:    %d\n' "$WARN"
printf 'BLOCKED checks: %d\n' "$BLOCK"

if [[ "$RUN_SMOKE" == "1" ]]; then
    printf '\n\033[1;32mCLEAN_ROOM_SETUP_RESULT=PASS\033[0m\n'
else
    printf '\nCLEAN_ROOM_BUILD_PROFILE_RESULT=PASS (runtime smoke skipped)\n'
fi

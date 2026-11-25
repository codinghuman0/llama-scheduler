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
    echo "오류: 클론한 Git 저장소에서 이 파일을 실행하세요" >&2
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
die()  { printf '\033[1;31m오류\033[0m  %s\n' "$*" >&2; exit 1; }

trap 'printf "\n실행 오류가 발생한 행 %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

cd "$REPO_ROOT"

[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || { block "x86-64 Linux가 필요합니다"; exit 2; }
[[ "$(id -u)" != 0 && "$(id -u)" == "$(stat -c %u "$REPO_ROOT")" ]] || die "저장소 소유자의 일반 계정으로 실행하세요"
if [[ "$INSTALL_DEPS" == "1" ]]; then
    command -v apt-get >/dev/null 2>&1 || die "자동 패키지 설치에는 apt-get이 필요합니다. 다른 배포판은 직접 설치 후 INSTALL_DEPS=0을 지정하세요"
fi
command -v sudo >/dev/null 2>&1 || die "sudo가 필요합니다"
[[ -x "$DETECTOR" ]] || die "토폴로지 탐지 프로그램을 실행할 수 없습니다: $DETECTOR"
[[ -x "$SMOKE" ]] || die "이식성 smoke를 실행할 수 없습니다: $SMOKE"

say "Repository identity"
printf 'root:   %s\n' "$REPO_ROOT"
printf 'branch: %s\n' "$(git branch --show-current)"
printf 'HEAD:   %s\n' "$(git rev-parse HEAD)"
printf 'origin: %s\n' "$(git remote get-url origin 2>/dev/null || echo none)"

[[ -z "$(git status --porcelain)" ]] || {
    git status --short >&2
    die "준비하기 전에 Git 작업 트리의 변경을 보관하세요"
}
ok "Git worktree clean"

python3 -B -c 'import sys; sys.path.insert(0, "tools/sched_ext/bench"); from common import repo_check; from host_profile import require_refreshable; repo_check(); require_refreshable()'

if git rev-parse -q --verify "refs/tags/$RELEASE_TAG" >/dev/null; then
    RELEASE_COMMIT="$(git rev-parse "$RELEASE_TAG^{commit}")"
    [[ "$RELEASE_COMMIT" == "$EXPECTED_RELEASE_COMMIT" ]] || \
        block "$RELEASE_TAG -> $RELEASE_COMMIT, 예상값 $EXPECTED_RELEASE_COMMIT"
    [[ "$RELEASE_COMMIT" == "$EXPECTED_RELEASE_COMMIT" ]] && \
        ok "immutable release tag verified"
else
    block "릴리스 태그가 없습니다: $RELEASE_TAG"
fi

say "Host snapshot"
cat /etc/os-release | grep -E '^(NAME|VERSION|VERSION_ID|VERSION_CODENAME)=' || true
printf 'kernel: %s\n' "$(uname -r)"
printf 'arch:   %s\n' "$(uname -m)"
printf 'nproc:  %s\n' "$(nproc)"

say "Model identity"
if [[ ! -f "$MODEL" ]]; then
    block "모델을 찾을 수 없습니다: $MODEL"
else
    MODEL_SIZE="$(stat -c '%s' "$MODEL")"
    MODEL_SHA="$(sha256sum "$MODEL" | awk '{print $1}')"
    printf 'model:  %s\n' "$MODEL"
    printf 'size:   %s\n' "$MODEL_SIZE"
    printf 'sha256: %s\n' "$MODEL_SHA"

    [[ "$MODEL_SIZE" == "$EXPECTED_MODEL_SIZE" ]] \
        && ok "model byte size" \
        || block "모델 파일 크기가 다릅니다"

    [[ "$MODEL_SHA" == "$EXPECTED_MODEL_SHA256" ]] \
        && ok "model SHA256" \
        || block "모델 SHA-256이 일치하지 않습니다"
fi

[[ -r /sys/kernel/sched_ext/state && -r /sys/kernel/btf/vmlinux ]] || {
    block "필요한 커널 sched_ext/BTF 인터페이스가 없습니다"
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
        block "$cmd 항목이 없습니다"
    fi
done

say "Kernel sched_ext/BTF preflight"
if [[ -r /sys/kernel/sched_ext/state ]]; then
    printf 'sched_ext state: %s\n' "$(cat /sys/kernel/sched_ext/state)"
    ok "sched_ext sysfs interface"
else
    block "/sys/kernel/sched_ext/state 항목이 없습니다"
fi

if [[ -r /sys/kernel/btf/vmlinux ]]; then
    ok "kernel BTF available"
else
    block "/sys/kernel/btf/vmlinux 항목이 없습니다"
fi

CONFIG_FILE="/boot/config-$(uname -r)"
if [[ -r "$CONFIG_FILE" ]]; then
    for opt in CONFIG_BPF CONFIG_BPF_SYSCALL CONFIG_SCHED_CLASS_EXT CONFIG_DEBUG_INFO_BTF; do
        if grep -qx "${opt}=y" "$CONFIG_FILE"; then
            ok "$opt=y"
        else
            block "$opt 커널 설정이 y가 아닙니다"
        fi
    done
else
    warn "running kernel config is not readable at $CONFIG_FILE"
fi

if (( BLOCK > 0 )); then
    printf '\n\033[1;31mCLEAN_ROOM_PREFLIGHT_RESULT=BLOCKED\033[0m\n'
    exit 2
fi

say "Topology detection"
[[ "$BUILD_DIR" == "$REPO_ROOT"/build-* && ! -L "$BUILD_DIR" ]] || die "BUILD_DIR은 저장소 내부의 build-* 폴더여야 합니다"
mkdir -p "$BUILD_DIR"
mkdir -p "$BUILD_DIR/portability"

TOPOLOGY_ENV="$BUILD_DIR/portability/topology.env"
"$DETECTOR" --env "$TOPOLOGY_ENV" | tee "$BUILD_DIR/portability/topology.log"

# shellcheck disable=SC1090
source "$TOPOLOGY_ENV"
[[ "${TOPOLOGY_RESULT:-}" == "PASS" ]] || die "토폴로지 검증에 실패했습니다"
[[ "${CPU_SELECTED_COUNT:-0}" -ge 1 ]] || die "토폴로지 탐지에서 CPU를 선택하지 못했습니다"
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

[[ -x "$SERVER" ]] || die "llama-server 파일이 빌드 결과에 없습니다"
[[ -f "$MARKER" ]] || die "libllama-server-impl.so 파일이 빌드 결과에 없습니다"
ok "llama-server build"

CACHE_HINT="$(grep -E '^LLAMA_SCX_PHASE_HINT:BOOL=' "$BUILD_DIR/CMakeCache.txt" || true)"
CACHE_TRACE="$(grep -E '^LLAMA_SCX_PHASE_TRACE:BOOL=' "$BUILD_DIR/CMakeCache.txt" || true)"
printf '%s\n%s\n' "$CACHE_HINT" "$CACHE_TRACE"
[[ "$CACHE_HINT" == "LLAMA_SCX_PHASE_HINT:BOOL=ON" ]] || block "HINT 캐시 값이 ON이어야 합니다"
[[ "$CACHE_TRACE" == "LLAMA_SCX_PHASE_TRACE:BOOL=OFF" ]] || block "TRACE 캐시 값이 OFF여야 합니다"

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
    block "llama_scx_phase_v1 동적 심볼이 없습니다"
fi

say "Fresh lightweight sched_ext build"
if ! make -B -C "$REPO_ROOT/tools/sched_ext" -j"$BUILD_JOBS"; then
    block "중립 스케줄러 빌드에 실패했습니다. 실행 커널의 UAPI 헤더, 컴파일러와 libbpf를 확인하세요"
    printf 'CLEAN_ROOM_BUILD_RESULT=BLOCKED\n'
    exit 2
fi

SCHED="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx"
CHILD="$REPO_ROOT/tools/sched_ext/build/bin/llama_scx_child"
BPF_OBJ="$REPO_ROOT/tools/sched_ext/build/llama_scx.bpf.o"

[[ -x "$SCHED" ]] || block "scheduler loader 항목이 없습니다"
[[ -x "$CHILD" ]] || block "child launcher 항목이 없습니다"
[[ -f "$BPF_OBJ" ]] || block "BPF object 항목이 없습니다"
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
    die "준비 종료 시 Git 작업 트리에 변경이 있습니다"
fi

printf '\nPASS checks:    %d\n' "$PASS"
printf 'WARN checks:    %d\n' "$WARN"
printf 'BLOCKED checks: %d\n' "$BLOCK"

if [[ "$RUN_SMOKE" == "1" ]]; then
    printf '\n\033[1;32mCLEAN_ROOM_SETUP_RESULT=PASS\033[0m\n'
else
    printf '\nCLEAN_ROOM_BUILD_PROFILE_RESULT=PASS (runtime smoke skipped)\n'
fi

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
VERSIONS_FILE="$REPO_ROOT/config/versions.env"
DEPS_DIR="$REPO_ROOT/.deps"
SEMANTIC_DIR="$DEPS_DIR/llama.cpp-semantic"
SEMANTIC_BUILD_DIR="$REPO_ROOT/build/m11r/llama-semantic"
REPRO_FILE="$REPO_ROOT/build/reproducibility.env"
INSTALL_DEPS=0

usage() {
    cat <<'EOF'
Usage: ./scripts/bootstrap_ubuntu.sh [--install-deps]

Without options, audit the host, obtain the pinned semantic dependency, build
the CPU-only semantic llama-server and scheduler, and run unprivileged tests.

  --install-deps  explicitly install the supported Ubuntu package set first
  -h, --help      show this help

This script never installs or changes a kernel and never loads sched_ext/BPF.
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

section() {
    printf '\n== %s ==\n' "$*"
}

first_line() {
    "$@" 2>&1 | sed -n '1p'
}

write_env_value() {
    local name="$1"
    local value="$2"
    printf '%s=' "$name" >>"$REPRO_FILE"
    printf '%q' "$value" >>"$REPRO_FILE"
    printf '\n' >>"$REPRO_FILE"
}

for argument in "$@"; do
    case "$argument" in
        --install-deps) INSTALL_DEPS=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; die "unknown option: $argument" ;;
    esac
done

test -r "$VERSIONS_FILE" || die "version manifest not found: $VERSIONS_FILE"
# shellcheck source=../config/versions.env
source "$VERSIONS_FILE"

required_manifest_values=(
    BASELINE_NAME SEMANTIC_LLAMA_REPO SEMANTIC_LLAMA_COMMIT
    VALIDATED_DISTRIBUTION VALIDATED_UBUNTU_VERSION VALIDATED_ARCH VALIDATED_KERNEL
)
for name in "${required_manifest_values[@]}"; do
    test -n "${!name:-}" || die "missing $name in $VERSIONS_FILE"
done
[[ "$SEMANTIC_LLAMA_COMMIT" =~ ^[0-9a-f]{40}$ ]] ||
    die "SEMANTIC_LLAMA_COMMIT must be a full 40-character SHA"

source /etc/os-release 2>/dev/null || die "cannot read /etc/os-release"
ARCH="$(uname -m)"
KERNEL="$(uname -r)"
ONLINE_CPUS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc)"
[[ "$ONLINE_CPUS" =~ ^[1-9][0-9]*$ ]] || die "cannot determine online CPU count"
if test "$ONLINE_CPUS" -gt 4; then
    BUILD_JOBS=4
else
    BUILD_JOBS="$ONLINE_CPUS"
fi

packages=(
    build-essential ca-certificates cmake git curl clang llvm bpftool ripgrep
    libbpf-dev libelf-dev zlib1g-dev "linux-headers-$KERNEL"
    python3 binutils pkg-config procps
)
package_command="sudo apt-get update && sudo apt-get install -y ${packages[*]}"

section "Host identity"
printf 'distribution=%s %s\n' "${NAME:-unknown}" "${VERSION_ID:-unknown}"
printf 'architecture=%s\n' "$ARCH"
printf 'kernel=%s\n' "$KERNEL"
printf 'online_cpus=%s\n' "$ONLINE_CPUS"
printf 'build_jobs=%s\n' "$BUILD_JOBS"
printf 'validated_target=%s %s %s %s\n' \
    "$VALIDATED_DISTRIBUTION" "$VALIDATED_UBUNTU_VERSION" \
    "$VALIDATED_ARCH" "$VALIDATED_KERNEL"

if test "$INSTALL_DEPS" -eq 1; then
    test "${ID:-}" = ubuntu ||
        die "--install-deps supports Ubuntu only (detected ID=${ID:-unknown})"
    section "Ubuntu dependency installation"
    printf 'Packages:\n  %s\n' "${packages[*]}"
    printf 'Command:\n  %s\n' "$package_command"
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
fi

section "Required tools"
required_commands=(cc c++ clang cmake make bpftool rg python3 curl git readelf nm)
missing_commands=()
for command_name in "${required_commands[@]}"; do
    if command -v "$command_name" >/dev/null 2>&1; then
        printf '%-12s %s\n' "$command_name" "$(command -v "$command_name")"
    else
        printf '%-12s MISSING\n' "$command_name"
        missing_commands+=("$command_name")
    fi
done
if test "${#missing_commands[@]}" -ne 0; then
    printf 'Missing commands: %s\n' "${missing_commands[*]}" >&2
    printf 'Install with:\n  %s\n' "$package_command" >&2
    exit 1
fi

printf 'cc_version=%s\n' "$(first_line cc --version)"
printf 'clang_version=%s\n' "$(first_line clang --version)"
printf 'cmake_version=%s\n' "$(first_line cmake --version)"
printf 'make_version=%s\n' "$(first_line make --version)"
printf 'bpftool_version=%s\n' "$(first_line bpftool version)"
printf 'python_version=%s\n' "$(first_line python3 --version)"
printf 'curl_version=%s\n' "$(first_line curl --version)"
printf 'git_version=%s\n' "$(first_line git --version)"

test -r /usr/include/bpf/libbpf.h || {
    printf 'libbpf header missing: /usr/include/bpf/libbpf.h\n' >&2
    printf 'Install with:\n  %s\n' "$package_command" >&2
    exit 1
}
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libbpf; then
    LIBBPF_VERSION="$(pkg-config --modversion libbpf)"
else
    LIBBPF_VERSION="$(bpftool version 2>/dev/null | sed -n 's/^using libbpf v//p' | sed -n '1p')"
fi
test -n "$LIBBPF_VERSION" || LIBBPF_VERSION=unknown
printf 'libbpf_version=%s\n' "$LIBBPF_VERSION"

section "sched_ext and BPF capabilities"
test "${ID:-}" = ubuntu || die "UNSUPPORTED: this bootstrap supports Ubuntu only"
test "$ARCH" = "$VALIDATED_ARCH" ||
    die "UNSUPPORTED: scheduler BPF target is $VALIDATED_ARCH, detected $ARCH"
test -r /sys/kernel/sched_ext/state ||
    die "UNSUPPORTED: /sys/kernel/sched_ext/state is absent; sched_ext is unavailable"
test -r /sys/kernel/btf/vmlinux ||
    die "UNSUPPORTED: /sys/kernel/btf/vmlinux is absent; kernel BTF is required"
test -d "/lib/modules/$KERNEL/build" || {
    printf 'Matching kernel headers are missing: /lib/modules/%s/build\n' "$KERNEL" >&2
    printf 'Install with:\n  %s\n' "$package_command" >&2
    exit 1
}
printf 'sched_ext_state=%s\n' "$(tr -d '\n' </sys/kernel/sched_ext/state)"
printf 'kernel_btf=/sys/kernel/btf/vmlinux\n'

btf_dump="$(mktemp)"
trap 'rm -f -- "$btf_dump"' EXIT
bpftool btf dump file /sys/kernel/btf/vmlinux format raw >"$btf_dump"
required_btf_symbols=(
    sched_ext_ops
    scx_bpf_create_dsq
    scx_bpf_select_cpu_dfl
    scx_bpf_dsq_insert
    scx_bpf_dsq_insert_vtime
    scx_bpf_dsq_move_to_local
)
missing_btf=()
for symbol in "${required_btf_symbols[@]}"; do
    if rg -q "'$symbol'" "$btf_dump"; then
        printf 'btf_symbol=%s present\n' "$symbol"
    else
        printf 'btf_symbol=%s MISSING\n' "$symbol"
        missing_btf+=("$symbol")
    fi
done
test "${#missing_btf[@]}" -eq 0 ||
    die "UNSUPPORTED: required kernel BTF symbols are absent: ${missing_btf[*]}"

if test "$KERNEL" = "$VALIDATED_KERNEL" && test "${VERSION_ID:-}" = "$VALIDATED_UBUNTU_VERSION" &&
   test "$ARCH" = "$VALIDATED_ARCH"; then
    KERNEL_STATUS=VALIDATED
else
    KERNEL_STATUS=COMPATIBLE-BUT-UNVALIDATED
fi
printf 'kernel_compatibility=%s\n' "$KERNEL_STATUS"
if test "$KERNEL_STATUS" != VALIDATED; then
    printf 'NOTICE: build/runtime results on this kernel constitute a new environment.\n'
fi

section "Pinned semantic dependency"
mkdir -p "$DEPS_DIR"
if test ! -e "$SEMANTIC_DIR"; then
    git clone "$SEMANTIC_LLAMA_REPO" "$SEMANTIC_DIR"
fi
test -d "$SEMANTIC_DIR/.git" || die "$SEMANTIC_DIR exists but is not a Git worktree"
test -z "$(git -C "$SEMANTIC_DIR" status --short)" ||
    die "semantic dependency worktree is dirty; refusing to modify or build it"
semantic_origin="$(git -C "$SEMANTIC_DIR" remote get-url origin 2>/dev/null || true)"
test "$semantic_origin" = "$SEMANTIC_LLAMA_REPO" ||
    die "semantic dependency origin mismatch: $semantic_origin"
if ! git -C "$SEMANTIC_DIR" cat-file -e "$SEMANTIC_LLAMA_COMMIT^{commit}" 2>/dev/null; then
    git -C "$SEMANTIC_DIR" fetch --no-tags origin "$SEMANTIC_LLAMA_COMMIT"
fi
git -C "$SEMANTIC_DIR" checkout --detach "$SEMANTIC_LLAMA_COMMIT"
semantic_head="$(git -C "$SEMANTIC_DIR" rev-parse HEAD)"
test "$semantic_head" = "$SEMANTIC_LLAMA_COMMIT" ||
    die "semantic dependency resolved to $semantic_head, expected $SEMANTIC_LLAMA_COMMIT"
test -z "$(git -C "$SEMANTIC_DIR" status --short)" ||
    die "semantic dependency worktree became dirty before build"
printf 'semantic_repo=%s\nsemantic_commit=%s\nsemantic_worktree=clean\n' \
    "$semantic_origin" "$semantic_head"

section "CPU-only semantic llama-server build"
cmake -S "$SEMANTIC_DIR" -B "$SEMANTIC_BUILD_DIR" -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DBUILD_SHARED_LIBS=ON \
    -DLLAMA_SCX_PHASE_TRACE=ON \
    -DLLAMA_BUILD_COMMON=ON \
    -DLLAMA_BUILD_TOOLS=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=OFF \
    -DLLAMA_BUILD_APP=OFF \
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF \
    -DLLAMA_BUILD_MTMD=OFF \
    -DLLAMA_OPENSSL=OFF \
    -DGGML_NATIVE=ON \
    -DGGML_BLAS=OFF \
    -DGGML_CUDA=OFF \
    -DGGML_HIP=OFF \
    -DGGML_MUSA=OFF \
    -DGGML_VULKAN=OFF \
    -DGGML_METAL=OFF \
    -DGGML_SYCL=OFF \
    -DGGML_RPC=OFF \
    -DGGML_CANN=OFF \
    -DGGML_OPENCL=OFF \
    -DGGML_OPENVINO=OFF \
    -DGGML_ET=OFF \
    -DGGML_HEXAGON=OFF \
    -DGGML_ZENDNN=OFF \
    -DGGML_ZDNN=OFF \
    -DGGML_WEBGPU=OFF \
    -DGGML_VIRTGPU=OFF
cmake --build "$SEMANTIC_BUILD_DIR" --target llama-server --parallel "$BUILD_JOBS"

SEMANTIC_SERVER="$SEMANTIC_BUILD_DIR/bin/llama-server"
MARKER_ELF="$SEMANTIC_BUILD_DIR/bin/libllama-server-impl.so"
test -x "$SEMANTIC_SERVER" || die "semantic server was not built: $SEMANTIC_SERVER"
test -f "$MARKER_ELF" || die "marker-bearing ELF was not built: $MARKER_ELF"
for symbol in llama_scx_decode_begin_v1 llama_scx_decode_end_v1; do
    readelf --dyn-syms --wide "$MARKER_ELF" | awk -v required="$symbol" \
        '$4 == "FUNC" && $5 == "GLOBAL" && $6 == "DEFAULT" && $8 == required { found = 1 }
         END { exit found ? 0 : 1 }' ||
        die "required dynamic marker symbol missing from $MARKER_ELF: $symbol"
    printf 'marker_symbol=%s present in %s\n' "$symbol" "$MARKER_ELF"
done
test -z "$(git -C "$SEMANTIC_DIR" status --short)" ||
    die "semantic dependency worktree is dirty after build"

section "Scheduler build and unprivileged tests"
make -C "$REPO_ROOT" -j"$BUILD_JOBS"
make -C "$REPO_ROOT" check

section "Reproducibility record"
mkdir -p "$(dirname -- "$REPRO_FILE")"
: >"$REPRO_FILE"
scheduler_sha="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || printf unknown)"
if test -n "$(git -C "$REPO_ROOT" status --short 2>/dev/null || true)"; then
    scheduler_state=dirty
else
    scheduler_state=clean
fi
cpu_model="$(sed -n 's/^model name[[:space:]]*: //p' /proc/cpuinfo | sed -n '1p')"
write_env_value BASELINE_NAME "$BASELINE_NAME"
write_env_value SCHEDULER_GIT_SHA "$scheduler_sha"
write_env_value SCHEDULER_WORKTREE_STATE "$scheduler_state"
write_env_value SEMANTIC_LLAMA_REPO "$semantic_origin"
write_env_value SEMANTIC_LLAMA_COMMIT "$semantic_head"
write_env_value KERNEL "$KERNEL"
write_env_value KERNEL_COMPATIBILITY "$KERNEL_STATUS"
write_env_value DISTRIBUTION_ID "${ID:-unknown}"
write_env_value DISTRIBUTION_VERSION "${VERSION_ID:-unknown}"
write_env_value ARCHITECTURE "$ARCH"
write_env_value CPU_MODEL "${cpu_model:-unknown}"
write_env_value ONLINE_CPU_COUNT "$ONLINE_CPUS"
write_env_value BUILD_JOB_COUNT "$BUILD_JOBS"
write_env_value CC_VERSION "$(first_line cc --version)"
write_env_value CLANG_VERSION "$(first_line clang --version)"
write_env_value BPFTOOL_VERSION "$(first_line bpftool version)"
write_env_value LIBBPF_VERSION "$LIBBPF_VERSION"
write_env_value TIMESTAMP_UTC "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

printf 'reproducibility_record=%s\n' "$REPRO_FILE"
printf 'bootstrap=PASS\n'
printf 'kernel_compatibility=%s\n' "$KERNEL_STATUS"
printf 'NOTICE: no scheduler was loaded; privileged semantic runtime validation remains separate.\n'

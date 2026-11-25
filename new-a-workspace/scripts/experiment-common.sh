# Shared by the CPU experiment launchers. Paths are absolute before changing directories.
experiment_error() {
    printf '오류: %s\n' "$*" >&2
    exit 1
}

experiment_setup() {
    [[ $EUID != 0 ]] || experiment_error "일반 계정으로 실행하세요. 커널 loader에서만 sudo를 사용합니다."
    [[ $(uname -sm) == 'Linux x86_64' ]] || experiment_error "x86-64 Linux에서 실행하세요."
    for tool in git python3 cmake gcc g++ make taskset; do
        command -v "$tool" >/dev/null || experiment_error "필요한 명령을 찾을 수 없습니다 ($tool)."
    done
    python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || experiment_error "Python 3.10 이상이 필요합니다."
    state="$workspace/state/integration-v2"
    cli=(bash "$workspace/scripts/integration_v2.sh")
    mkdir -p -- "$state"
}

runtime_cache() {
    local backend=$1 markers=$2 tree
    tree=$(git -C "$workspace" rev-parse --short=12 HEAD:./src/llama) || return
    printf '%s\n' "${NEWA_BUILD_DIR:-$state/builds/$backend-$markers-$tree}"
}

scheduler_cache() {
    local tree
    tree=$(git -C "$workspace" rev-parse --short=12 HEAD:./tools/integration_v2/scheduler) || return
    printf '%s\n' "${NEWA_SCX_BUILD:-$state/scheduler-$tree-$(uname -r)}"
}

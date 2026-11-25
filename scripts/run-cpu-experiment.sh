#!/usr/bin/env bash
# Download this file or run it from a checkout. The project is always run as the caller.
set -euo pipefail
mode=${1:-smoke}
usage() {
    printf '%s\n' '사용법: bash run-cpu-experiment.sh [smoke|m4|prefill-linux|prepare|scx|placement] [model.gguf]' \
        'smoke는 기본 Linux CPU 추론을 실행합니다. scx와 placement는 선택된 서버 전용 커널 실험입니다.' \
        '기본 모델은 ~/projects/model.gguf입니다. 프로젝트 상위 폴더는 NEWA_PROJECTS_DIR, 체크아웃은 NEWA_CHECKOUT으로 지정할 수 있습니다.'
}
fail() { printf '오류: %s\n' "$*" >&2; exit 1; }
trap 'printf "오류: %s행에서 명령이 실패했습니다 (종료 코드 %s). 위 진단을 확인하세요.\n" "$LINENO" "$?" >&2' ERR
case "$mode" in
    -h|--help) usage; exit 0 ;;
    smoke|m4|prefill-linux|prepare|scx|placement) ;;
    *) usage >&2; fail "알 수 없는 실험 모드입니다 ($mode)." ;;
esac
(( $# <= 2 )) || fail '인수가 너무 많습니다.'
[[ $EUID != 0 ]] || fail '일반 계정에서 실행하세요.'
[[ $(uname -sm) == 'Linux x86_64' ]] || fail 'x86-64 Linux가 필요합니다.'
command -v git >/dev/null || fail 'Git을 먼저 설치하세요.'
url=https://github.com/codinghuman0/llama-scheduler.git
branch=integration-v2
projects=${NEWA_PROJECTS_DIR:-"$HOME/projects"}
script_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
model=${2:-"$projects/model.gguf"}
if [[ $mode != prepare ]]; then
    [[ -f $model && -r $model ]] || fail "원본 모델 파일을 읽을 수 없습니다 ($model)."
    model=$(realpath -- "$model")
fi
if [[ -n ${NEWA_CHECKOUT:-} ]]; then
    repo=$NEWA_CHECKOUT
elif [[ -z ${NEWA_PROJECTS_DIR:-} && -e $script_repo/.git &&
        ${BASH_SOURCE[0]} -ef "$script_repo/scripts/run-cpu-experiment.sh" ]]; then
    repo=$script_repo
elif [[ -e "$projects/llama-scheduler" ]]; then
    repo="$projects/llama-scheduler"
elif [[ -e "$projects/llama-scheduler-integration-v2" ]]; then
    repo="$projects/llama-scheduler-integration-v2"
else
    repo="$projects/llama-scheduler"
fi
if [[ -e $repo && ! -d $repo/.git && ! -f $repo/.git ]]; then
    [[ -d $repo && -z $(ls -A -- "$repo") ]] || fail "Git 체크아웃이 아닌 기존 경로입니다 ($repo). NEWA_CHECKOUT에 다른 경로를 지정하세요."
fi
if [[ ! -e $repo/.git ]]; then
    mkdir -p -- "$(dirname -- "$repo")"
    git clone --depth 1 --no-tags --single-branch --branch "$branch" -- "$url" "$repo" || fail "저장소를 복제할 수 없습니다 ($repo)."
else
    remote=$(git -C "$repo" remote get-url origin) || fail '기존 저장소에 origin 원격이 없습니다.'
    case "${remote%.git}" in
        https://github.com/codinghuman0/llama-scheduler|git@github.com:codinghuman0/llama-scheduler|ssh://git@github.com/codinghuman0/llama-scheduler) ;;
        *) fail '기존 폴더의 origin이 codinghuman0/llama-scheduler가 아닙니다.' ;;
    esac
    git -C "$repo" diff --quiet && git -C "$repo" diff --cached --quiet || fail "커밋하지 않은 변경이 있습니다. 먼저 보관하세요 ($repo)."
    # Explicit ref also works with an old single-branch main clone.
    fetch_options=(--no-tags)
    if [[ $(git -C "$repo" rev-parse --is-shallow-repository) == true ]] &&
       ! git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
        fetch_options+=(--depth=1)
    fi
    git -C "$repo" fetch "${fetch_options[@]}" origin "refs/heads/$branch:refs/remotes/origin/$branch" || fail '원격 브랜치를 가져올 수 없습니다.'
    if git -C "$repo" show-ref --verify --quiet "refs/heads/$branch"; then
        git -C "$repo" merge-base --is-ancestor "$branch" "origin/$branch" || fail "로컬 $branch 커밋 이력이 원격과 갈라졌습니다. 로컬 커밋을 확인하세요."
        git -C "$repo" switch --no-overwrite-ignore "$branch" || fail '기존 파일을 보존하면서 브랜치를 전환할 수 없습니다.'
    else
        git -C "$repo" switch --no-overwrite-ignore -c "$branch" "origin/$branch" || fail '브랜치 전환 중 로컬 파일 충돌이 발생했습니다.'
    fi
    # Dry-run protects untracked and ignored files. Pull the exact commit already fetched from origin.
    target=$(git -C "$repo" rev-parse "origin/$branch")
    git -C "$repo" read-tree --dry-run -m -u HEAD "$target" || fail '업데이트할 경로에 로컬 파일이 있습니다. 먼저 보관하세요.'
    git -C "$repo" pull --no-rebase --ff-only --no-tags origin "$target" || fail 'git pull에 실패했습니다.'
fi
repo=$(cd -- "$repo" && pwd -P)
head=$(git -C "$repo" rev-parse HEAD)
[[ $(git -C "$repo" rev-parse "refs/remotes/origin/$branch") == "$head" ]] || fail '체크아웃과 원격 브랜치의 커밋이 다릅니다. 다시 실행하세요.'
printf '실행할 버전  %s  %s\n' "$branch" "$head"
scripts="$repo/new-a-workspace/scripts"
case "$mode" in
    smoke|m4) exec bash "$scripts/intel-integration-v2-smoke.sh" "$model" "" "$mode" ;;
    prefill-linux) exec bash "$scripts/prefill-pcore-smoke.sh" linux "$model" ;;
    prepare|scx|placement) exec bash "$scripts/prefill-pcore-smoke.sh" "$mode" "$model" ;;
esac

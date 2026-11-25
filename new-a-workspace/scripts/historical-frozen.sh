#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help || $# -lt 2 ]]; then
    printf '사용법: %s FROZEN_WORKSPACE run|build|intel [original arguments...]\n' "$0"
    exit 0
fi
[[ -d $1 ]] || { printf "오류: 보존된 실험 경로가 없습니다 (%s).\n" "$1" >&2; exit 1; }
frozen=$(realpath -e -- "$1")
action=$2
shift 2
current=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ "$frozen" == "$current" ]]; then
    printf '보존한 과거 체크아웃의 경로를 지정하세요. 현재 통합 체크아웃을 선택했습니다.\n' >&2
    exit 1
fi
case "$action" in
    run) script=run.sh ;;
    build) script=build.sh ;;
    intel) script=scripts/intel_experiment.sh ;;
    *) printf '지원하지 않는 과거 실험 명령: %s\n' "$action" >&2; exit 1 ;;
esac
exec bash "$frozen/$script" "$@"

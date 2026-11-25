#!/usr/bin/env bash
set -euo pipefail

workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/scripts/experiment-common.sh"
trap 'printf "오류: Prefill 실험이 %s행에서 중단되었습니다 (종료 코드 %s).\n" "$LINENO" "$?" >&2' ERR
mode=${1:-linux}
if [[ $mode == --help ]]; then
    printf '사용법: bash %s {linux|prepare|scx|placement} [model.gguf]\n' "$0"
    exit 0
fi
if [[ $# -gt 2 || ! "$mode" =~ ^(linux|prepare|scx|placement)$ ]]; then
    echo "사용법: bash scripts/prefill-pcore-smoke.sh {linux|prepare|scx|placement} [model.gguf]" >&2
    exit 2
fi
experiment_setup
if [[ $mode != linux && ( ! -r /sys/kernel/sched_ext/state || ! -r /sys/kernel/btf/vmlinux ) ]]; then
    echo "커널 실험에는 실행 중인 커널의 sched_ext 및 vmlinux BTF가 필요합니다. 일반 CPU 실험은 linux 모드로 실행하세요." >&2
    exit 1
fi
model=${2:-"$workspace/../../model.gguf"}
if [[ $mode != prepare && ( ! -r $model || ! -f $model ) ]]; then
    echo "모델 파일을 읽을 수 없습니다: $model" >&2
    exit 2
fi
runtime=$(runtime_cache openmp state-only)
bundle=$(scheduler_cache)
visit=$(mktemp -d "$state/prefill-smoke-${mode}.XXXXXXXX")
printf '결과 경로  %s\n' "$visit"

"${cli[@]}" build --reuse --build-dir "$runtime" --backend openmp --markers state-only --jobs 2
config=(--build-dir "$runtime" --resources auto --reserve-controller --profile unified-conservative --pool roles --transport state)
workload=(--model "$model" --fixtures single-short heldout-1 --tokens 4 --state-log)
if [[ $mode == linux ]]; then
    "${cli[@]}" run "${config[@]}" "${workload[@]}" --output "$visit/linux"
    exit
fi
if [[ ! -e $bundle ]]; then
    "${cli[@]}" build-scheduler --output "$bundle"
fi
if [[ $mode == placement ]]; then
    command -v sudo >/dev/null || experiment_error "커널 loader를 실행할 sudo가 필요합니다."
    study="$workspace/experiments/amd-prefill-placement-ac-v1"
    printf '선택한 서버에만 적용하는 커널 실험을 36회 실행합니다. sudo 인증은 이 터미널에서 진행됩니다.\n'
    if [[ -t 0 && -t 2 ]]; then
        sudo -v || printf 'sudo 사전 인증을 확인하지 못했습니다. 실제 loader 명령의 권한을 사용합니다.\n' >&2
    fi
    python3 -B "$study/measure.py" run "$visit/campaign" --portable --model "$model" \
        --build-dir "$runtime" --scheduler-build "$bundle"
    python3 -B "$study/analyze.py" "$visit/campaign"
    printf '비교 결과  %s\n' "$visit/campaign/results.json"
    exit
fi
for policy in neutral prefill-pcore; do
    checkpoint="$visit/$policy-checkpoint"
    "${cli[@]}" prepare-scx "${config[@]}" --scheduler-build "$bundle" \
        --variant full --scheduler-policy "$policy" --owner-pid "$$" --output "$checkpoint" > "$visit/$policy-command.txt"
    if [[ $mode == prepare ]]; then
        printf '커널 로드 전 준비 완료  %s\n' "$checkpoint/checkpoint.json"
        continue
    fi
    printf '\n현재 터미널을 열어 두고 다른 Bash 터미널에서 아래 loader 명령을 확인하고 실행하세요.\n  bash %q\n' "$checkpoint/load.sh"
    deadline=$((SECONDS + 600))
    until [[ -e $checkpoint/loader.log ]] && grep -Fq 'waiting for selected child' "$checkpoint/loader.log"; do
        if [[ -e $checkpoint/loader-exit.txt || $SECONDS -ge $deadline ]]; then
            printf 'loader가 준비되지 않았습니다. 로그를 확인하세요 (%s).\n' "$checkpoint" >&2
            exit 1
        fi
        sleep 0.5
    done
    "${cli[@]}" run "${config[@]}" "${workload[@]}" --scx-checkpoint "$checkpoint" --output "$visit/$policy"
done
if [[ $mode == scx ]]; then
    "${cli[@]}" check-prefill-pair --neutral "$visit/neutral" --candidate "$visit/prefill-pcore" > "$visit/pair-metrics.json"
    printf '두 정책의 커널 적용과 토큰 일치 검증 완료  %s\n' "$visit/pair-metrics.json"
fi

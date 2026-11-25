#!/usr/bin/env bash
set -euo pipefail
workspace=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$workspace/scripts/experiment-common.sh"
trap 'printf "오류: CPU 실험이 %s행에서 중단되었습니다 (종료 코드 %s). 출력된 결과 경로와 로그를 확인하세요.\n" "$LINENO" "$?" >&2' ERR
if [[ ${1:-} == --help ]]; then
    printf '%s\n' "사용법: bash $0 [model.gguf] [결과 이름] [smoke|m4]"
    exit 0
fi
(( $# <= 3 )) || experiment_error "인수가 너무 많습니다. --help에서 사용법을 확인하세요."
mode=${3:-smoke}
case "$mode" in
    smoke) backend=openmp; markers=state-only ;;
    m4) backend=native; markers=state-only ;;
    *) experiment_error "실험 종류는 smoke 또는 m4여야 합니다." ;;
esac
model=${1:-"$workspace/../../model.gguf"}
[[ -r $model && -f $model ]] || experiment_error "모델 파일을 읽을 수 없습니다 ($model)."
model=$(realpath -- "$model")
tag=${2:-"cpu-$mode-$(date -u +%Y%m%dT%H%M%SZ)-$$"}
[[ $tag =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]] || experiment_error "결과 이름에는 영문, 숫자, 점, 붙임표, 밑줄만 사용하세요."
cd "$workspace"
experiment_setup
build_dir=$(runtime_cache "$backend" "$markers")
result="$state/$tag"
build_evidence="$result-build-evidence"
[[ ! -e $build_evidence ]] || experiment_error "같은 이름의 결과가 있습니다. 다른 이름을 지정하세요 ($build_evidence)."
printf '결과 경로  %s-*\n' "$result"
"${cli[@]}" test
"${cli[@]}" build --reuse --build-dir "$build_dir" --backend "$backend" --markers "$markers"
mkdir -- "$build_evidence"
cp -- "$build_dir/"{inputs,manifest,commands}.json "$build_dir/"{configure,build}.log "$build_evidence/"
"${cli[@]}" doctor --build-dir "$build_dir" --resources auto \
    --profile integrated-runtime-research > "$build_evidence/doctor.json"
python3 -c 'import json,sys; e=json.load(sys.stdin)["effective"]; print("CPU", e["topology"]["summary"]["cpu_model"], " / 프로파일", e["resources"], " / 허용 CPU", e["cpus"])' < "$build_evidence/doctor.json"
if [[ "$mode" == m4 ]]; then
    cpus=$(python3 -B -c 'import json, sys; print(",".join(map(str, json.load(sys.stdin)["effective"]["cpus"])))' \
        < "$build_evidence/doctor.json")
    [[ $cpus =~ ^([0-9]+,){5}[0-9]+$ ]] || experiment_error "m4 비교에는 허용된 물리 코어 6개가 필요합니다. 이 장비에서는 smoke를 사용하세요."
    m4_options=(--build-dir "$build_dir" --profile integrated-runtime-research --resources physical
        --cpus "$cpus" --policy phase-fixed)
    "${cli[@]}" doctor "${m4_options[@]}" --mixed-prefill head64 \
        > "$build_evidence/head64-doctor.json"
fi
printf '%s\n' '{"status":"BUILD_AND_DOCTOR_PASS"}' > "$build_evidence/summary.json"
"${cli[@]}" collect --result "$build_evidence" --output "$build_evidence.zip"
if [[ "$mode" == m4 ]]; then
    for policy in cap128 head64; do
        trial="$result-$policy"
        "${cli[@]}" serve-bench "${m4_options[@]}" --model "$model" \
            --mixed-prefill "$policy" --workloads m4 --tokens 128 --output "$trial"
        "${cli[@]}" collect --result "$trial" --output "$trial.zip"
    done
    comparison="$result-comparison"
    mkdir "$comparison"
    python3 -B tools/integration_v2/verify_head64.py "$result-cap128" "$result-head64" \
        > "$comparison/token-equality.json"
    printf '%s\n' '{"status":"M4_COMPARE_PASS","comparison":"token-equality.json"}' > "$comparison/summary.json"
    "${cli[@]}" collect --result "$comparison" --output "$comparison.zip"
    printf 'm4 토큰 일치 검증 완료  %s\n' "$comparison/token-equality.json"
    exit 0
fi
for fixture in heldout-1 heldout-2 single-short; do
    fixture_result="$result-$fixture"
    lifecycle=()
    if [[ "$fixture" == single-short ]]; then lifecycle=(--lifecycle); fi
    "${cli[@]}" run --build-dir "$build_dir" --model "$model" --output "$fixture_result" \
        --resources auto --profile integrated-runtime-research --state-log --worker-log \
        "${lifecycle[@]}" --sleep-idle 2 --fixtures "$fixture"
    python3 -c 'import json,sys; r=json.load(sys.stdin)[0]; m=r["measured"]; print("{}  {:.2f} tok/s  {:.3f}초".format(r["fixture"], m["tokens_per_s"], m["elapsed_s"]))' < "$fixture_result/cohorts.json"
    "${cli[@]}" collect --result "$fixture_result" --output "$fixture_result.zip"
done

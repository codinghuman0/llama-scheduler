#!/usr/bin/env bash
set -euo pipefail
workspace=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$workspace"
model=${1:-"$HOME/projects/model.gguf"}
tag=${2:-intel-validation-01}
mode=${3:-smoke}
case "$mode" in
    smoke) build_options=(--backend openmp) ;;
    m4) build_options=(--backend native --markers state-only) ;;
    *) printf 'Usage: %s [model.gguf] [result-name] [smoke|m4]\n' "$0" >&2; exit 2 ;;
esac
if [[ ! "$tag" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]*$ ]]; then
    printf 'Choose a simple result name.\n' >&2
    exit 2
fi
test -f "$model"
build_dir="state/integration-v2/builds/$tag"
result="state/integration-v2/$tag"
bash scripts/intel_experiment.sh test
bash scripts/intel_experiment.sh build --build-dir "$build_dir" "${build_options[@]}"
build_evidence="$result-build-evidence"
mkdir "$build_evidence"
cp "$build_dir/"{inputs,manifest,commands}.json "$build_dir/"{configure,build}.log "$build_evidence/"
bash scripts/intel_experiment.sh doctor --build-dir "$build_dir" --resources intel-fixed6 \
    --profile integrated-runtime-research > "$build_evidence/doctor.json"
if [[ "$mode" == m4 ]]; then
    cpus=$(python3 -B -c 'import json, sys; print(",".join(map(str, json.load(sys.stdin)["effective"]["cpus"])))' \
        < "$build_evidence/doctor.json")
    m4_options=(--build-dir "$build_dir" --profile integrated-runtime-research --resources physical
        --cpus "$cpus" --policy phase-fixed)
    bash scripts/intel_experiment.sh doctor "${m4_options[@]}" --mixed-prefill head64 \
        > "$build_evidence/head64-doctor.json"
fi
printf '%s\n' '{"status":"BUILD_AND_DOCTOR_PASS"}' > "$build_evidence/summary.json"
bash scripts/intel_experiment.sh collect --result "$build_evidence" --output "$build_evidence.zip"
if [[ "$mode" == m4 ]]; then
    for policy in cap128 head64; do
        trial="$result-$policy"
        bash scripts/intel_experiment.sh serve-bench "${m4_options[@]}" --model "$model" \
            --mixed-prefill "$policy" --workloads m4 --tokens 128 --output "$trial"
        bash scripts/intel_experiment.sh collect --result "$trial" --output "$trial.zip"
    done
    comparison="$result-comparison"
    mkdir "$comparison"
    python3 -B tools/integration_v2/verify_head64.py "$result-cap128" "$result-head64" \
        > "$comparison/token-equality.json"
    printf '%s\n' '{"status":"M4_COMPARE_PASS","comparison":"token-equality.json"}' > "$comparison/summary.json"
    bash scripts/intel_experiment.sh collect --result "$comparison" --output "$comparison.zip"
    exit 0
fi
for fixture in heldout-1 heldout-2 single-short; do
    fixture_result="$result-$fixture"
    lifecycle=()
    if [[ "$fixture" == single-short ]]; then lifecycle=(--lifecycle); fi
    bash scripts/intel_experiment.sh run --build-dir "$build_dir" --model "$model" --output "$fixture_result" \
        --resources intel-fixed6 --profile integrated-runtime-research --state-log --worker-log \
        "${lifecycle[@]}" --sleep-idle 2 --fixtures "$fixture"
    bash scripts/intel_experiment.sh collect --result "$fixture_result" --output "$fixture_result.zip"
done

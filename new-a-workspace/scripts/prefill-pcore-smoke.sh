#!/usr/bin/env bash
set -euo pipefail

workspace=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
mode=${1:-linux}
if [[ $# -gt 2 || ! "$mode" =~ ^(linux|prepare|scx)$ ]]; then
    echo "Usage: bash scripts/prefill-pcore-smoke.sh {linux|prepare|scx} [model.gguf]" >&2
    exit 2
fi
if [[ $EUID -eq 0 ]]; then
    echo "Run this controller in an ordinary user terminal." >&2
    exit 2
fi
if [[ $mode != linux && ( ! -r /sys/kernel/sched_ext/state || ! -r /sys/kernel/btf/vmlinux ) ]]; then
    echo "The SCX experiment requires sched_ext and vmlinux BTF on the booted kernel. Use linux for the userspace smoke." >&2
    exit 1
fi
model=${2:-"$workspace/../../model.gguf"}
if [[ $mode != prepare && ! -r $model ]]; then
    echo "Cannot read model: $model" >&2
    exit 2
fi
state="$workspace/state/integration-v2"
runtime=${NEWA_BUILD_DIR:-"$state/builds/prefill-pcore-openmp-v1"}
bundle=${NEWA_SCX_BUILD:-"$state/prefill-pcore-scheduler-v2"}
cli=(bash "$workspace/scripts/integration_v2.sh")
mkdir -p "$state"
visit=$(mktemp -d "$state/prefill-smoke-${mode}.XXXXXXXX")
printf 'Results  %s\n' "$visit"

if [[ ! -e $runtime ]]; then
    "${cli[@]}" build --relaxed-host-checks --build-dir "$runtime" --backend openmp --markers state-only --jobs 2
fi
config=(--build-dir "$runtime" --resources auto --profile unified-conservative --pool roles --transport state)
workload=(--model "$model" --fixtures single-short heldout-1 --tokens 4 --state-log)
if [[ $mode == linux ]]; then
    "${cli[@]}" run --relaxed-host-checks "${config[@]}" "${workload[@]}" --output "$visit/linux"
    exit
fi
if [[ ! -e $bundle ]]; then
    "${cli[@]}" build-scheduler --relaxed-host-checks --output "$bundle"
fi
for policy in neutral prefill-pcore; do
    checkpoint="$visit/$policy-checkpoint"
    "${cli[@]}" prepare-scx --relaxed-host-checks "${config[@]}" --scheduler-build "$bundle" \
        --variant full --scheduler-policy "$policy" --owner-pid "$$" --output "$checkpoint" > "$visit/$policy-command.txt"
    if [[ $mode == prepare ]]; then
        printf 'Prepared %s (offline check)\n' "$checkpoint/checkpoint.json"
        continue
    fi
    printf '\nKeep this terminal open. In another Bash terminal, review and run\n  bash %q\n' "$checkpoint/load.sh"
    deadline=$((SECONDS + 600))
    until [[ -e $checkpoint/loader.log ]] && grep -Fq 'waiting for selected child' "$checkpoint/loader.log"; do
        if [[ -e $checkpoint/loader-exit.txt || $SECONDS -ge $deadline ]]; then
            printf 'Loader did not become ready. See %s\n' "$checkpoint" >&2
            exit 1
        fi
        sleep 0.5
    done
    "${cli[@]}" run "${config[@]}" "${workload[@]}" --scx-checkpoint "$checkpoint" --output "$visit/$policy"
done
if [[ $mode == scx ]]; then
    "${cli[@]}" check-prefill-pair --neutral "$visit/neutral" --candidate "$visit/prefill-pcore" > "$visit/pair-metrics.json"
    printf 'Verified paired smoke  %s\n' "$visit/pair-metrics.json"
fi

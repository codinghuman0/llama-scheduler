#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help || $# -lt 2 ]]; then
    printf 'Usage: %s FROZEN_WORKSPACE run|build|intel [original arguments...]\n' "$0"
    exit 0
fi
frozen=$(realpath -e -- "$1")
action=$2
shift 2
current=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ "$frozen" == "$current" ]]; then
    printf 'Select the preserved historical workspace, separate from integration-v2.\n' >&2
    exit 1
fi
case "$action" in
    run) script=run.sh ;;
    build) script=build.sh ;;
    intel) script=scripts/intel_experiment.sh ;;
    *) printf 'Unsupported historical command: %s\n' "$action" >&2; exit 1 ;;
esac
exec bash "$frozen/$script" "$@"

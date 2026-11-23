#!/usr/bin/env bash
set -euo pipefail
exp_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
[[ $(id -u) != 0 ]] || { echo 'Use the ordinary workspace account.' >&2; exit 2; }
action=${1:-verify}
shift || true
case "$action" in
 verify) exec python3 -B "$exp_dir/code/check.py" ;;
 recalculate) exec python3 -B "$exp_dir/code/recalculate.py" --name replication-v1 "$@" ;;
 recalculate-original) exec python3 -B "$exp_dir/code/recalculate.py" --name attribution-v1 --root "$exp_dir/reference-original" --summary component-summary.json "$@" ;;
 analyze) exec python3 -B "$exp_dir/code/analyze.py" --name replication-v1 "$@" ;;
 admission|smoke|full)
  if [[ $action != smoke ]]; then sudo -n true || { echo 'Run sudo -v in your terminal, then repeat. No credentials are stored.' >&2; exit 2; }; fi
  case "$action" in
   admission) run_name=replication-scheduler-admission-v1 ;;
   smoke) run_name=replication-linux-smoke-v1 ;;
   full) run_name=replication-v1 ;;
  esac
  exec python3 -u -B "$exp_dir/code/run.py" "$action" --name "$run_name" "$@" ;;
 *) echo 'Usage: verify | recalculate | recalculate-original | analyze | admission | smoke | full' >&2; exit 2 ;;
esac

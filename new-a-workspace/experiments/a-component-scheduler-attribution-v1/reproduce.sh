#!/usr/bin/env bash
set -euo pipefail
exp_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1
[[ $(id -u) != 0 ]] || { echo 'Run as the ordinary workspace owner.' >&2; exit 2; }
action=${1:-verify}
shift || true
case "$action" in
 verify) exec python3 -B "$exp_dir/code/check.py" ;;
 recalculate) exec python3 -B "$exp_dir/code/recalculate.py" "$@" ;;
 analyze) exec python3 -B "$exp_dir/code/analyze.py" "$@" ;;
 admission|smoke|full)
  if [[ $action != smoke ]]; then sudo -n true || { echo 'Authenticate in your terminal with sudo -v, then repeat this command.' >&2; exit 2; }; fi
  exec python3 -u -B "$exp_dir/code/run.py" "$action" "$@" ;;
 *) echo 'Usage: ./reproduce.sh verify | recalculate --name attribution-v1 | analyze --name attribution-v1 | admission/smoke/full --name NEW_NAME' >&2; exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
command -v python3 >/dev/null || { printf '오류: Python 3.10 이상을 설치하세요.\n' >&2; exit 1; }
exec python3 -B "$root/tools/integration_v2/runtime.py" "$@"

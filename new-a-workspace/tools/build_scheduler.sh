#!/usr/bin/env bash
set -euo pipefail
trap 'printf "오류: 스케줄러 빌드 명령에 실패했습니다 (%s행).\n" "$LINENO" >&2' ERR
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $(id -u) != 0 ]] || { echo "오류: 일반 계정으로 실행하세요." >&2; exit 2; }
mkdir -p "$root/state"
exec 9>>"$root/state/.measurement.lock"
flock -n 9 || { echo "오류: 다른 측정이 진행 중입니다." >&2; exit 2; }
[[ $(cat /sys/kernel/sched_ext/state) == disabled ]] || { echo "오류: sched_ext가 비활성 상태여야 합니다." >&2; exit 2; }
[[ ! -e "$root/scheduler/loader.rebuilt" ]] || { echo '오류: loader.rebuilt 파일이 이미 있습니다.' >&2; exit 2; }
cc -O2 -g -Wall -Wextra -Werror -std=gnu11 -I"$root/scheduler/include" -DNEW_A_DIAGNOSTICS '-DHANDOFF_MODE="observe"' "$root/scheduler/loader.c" -o "$root/scheduler/loader.rebuilt" -lbpf -lelf -lz
"$root/scheduler/loader.rebuilt" --help
printf '%s\n' 'Built separate loader.rebuilt. No BPF load; validate and explicitly update scheduler identity before adopting it.'

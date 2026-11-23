#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ $(id -u) != 0 ]] || exit 2
exec 9<"$root/state/.measurement.lock"
flock -n 9
[[ $(cat /sys/kernel/sched_ext/state) == disabled ]] || exit 2
[[ ! -e "$root/scheduler/loader.rebuilt" ]] || { echo 'loader.rebuilt already exists' >&2; exit 2; }
cc -O2 -g -Wall -Wextra -Werror -std=gnu11 -I"$root/scheduler/include" -DNEW_A_DIAGNOSTICS '-DHANDOFF_MODE="observe"' "$root/scheduler/loader.c" -o "$root/scheduler/loader.rebuilt" -lbpf -lelf -lz
"$root/scheduler/loader.rebuilt" --help
printf '%s\n' 'Built separate loader.rebuilt. No BPF load; validate and explicitly update scheduler identity before adopting it.'

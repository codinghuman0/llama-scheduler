#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
set -euo pipefail
bench_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /usr/bin/python3 -B "$bench_dir/step10.py" campaign "$@"

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$SCRIPT_DIR/validate_phase.py" "$@"

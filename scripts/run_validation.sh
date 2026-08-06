#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
# Real validation requires a user-started, already-enabled llama_simple loader.
exec python3 "$(dirname "$0")/validation_runner.py" "$@"

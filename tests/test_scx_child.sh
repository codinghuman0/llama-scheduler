#!/bin/sh
# SPDX-License-Identifier: GPL-2.0
set -eu

launcher=${1:?launcher path required}
workload=${2:?workload path required}
test_dir=$(mktemp -d /tmp/llama-scx-child.XXXXXX)
trap 'rm -rf "$test_dir"' EXIT HUP INT TERM
state_file="$test_dir/state"

expect_failure() {
	if "$@" >"$test_dir/out" 2>"$test_dir/err"; then
		echo "expected failure: $*" >&2
		exit 1
	fi
}

expect_failure "$launcher" --dry-run
grep -q 'missing command' "$test_dir/err"

printf 'disabled\n' >"$state_file"
expect_failure "$launcher" -- /bin/true
grep -q 'sched_ext scheduler is not active' "$test_dir/err"

printf 'enabled\n' >"$state_file"
expect_failure "$launcher" --state-path "$state_file" -- /bin/true
grep -q -- "--state-path is allowed only with --dry-run" "$test_dir/err"

set +e
timeout 5s "$launcher" --dry-run --state-path "$state_file" -- /bin/sh -c 'exit 23' >"$test_dir/out" 2>"$test_dir/err"
status=$?
set -e
test "$status" -eq 23
grep -q 'child_pid=' "$test_dir/out"
grep -q 'parent_policy=' "$test_dir/out"

timeout 5s "$launcher" --dry-run --state-path "$state_file" -- "$workload" --seconds 1 >"$test_dir/out" 2>"$test_dir/err"
grep -q 'cpu_burn checksum=' "$test_dir/out"

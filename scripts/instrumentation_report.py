#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Validation helpers for llama_simple instrumentation.json reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
AGGREGATE_FIELDS = (
    "enqueue_count", "direct_local_insertions", "shared_dsq_insertions",
    "dispatch_callbacks", "running_callbacks", "stopping_callbacks",
    "runtime_ns", "queue_wait_ns", "migration_count",
    "current_tracked_tasks", "peak_tracked_tasks", "task_lookup_failures",
    "task_update_failures", "task_capacity_failures", "task_cleanup_failures",
    "tracking_state_lookup_failures",
    "completed_record_failures",
)
DROPPED_FIELDS = (
    "task_lookup_failures", "task_update_failures", "task_capacity_failures",
    "tracking_state_lookup_failures",
    "task_cleanup_failures", "completed_record_failures",
)


def _nonnegative(value: Any, field: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def parse_report_text(text: str) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("instrumentation output is empty")
    try:
        report = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"malformed instrumentation JSON: {error}") from error
    if not isinstance(report, dict):
        raise ValueError("instrumentation report must be an object")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported instrumentation schema_version")
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ValueError("instrumentation report aggregate must be an object")
    normalized = dict(report)
    normalized["aggregate"] = {
        field: _nonnegative(aggregate.get(field, 0), f"aggregate.{field}")
        for field in AGGREGATE_FIELDS
    }
    for collection in ("per_cpu", "tasks"):
        value = normalized.get(collection, [])
        if not isinstance(value, list):
            raise ValueError(f"instrumentation report {collection} must be a list")
        normalized[collection] = value
    return normalized


def parse_report_file(path: Path) -> dict[str, Any]:
    return parse_report_text(path.read_text(encoding="utf-8"))


def sum_records(records: Iterable[dict[str, Any]], field: str) -> int:
    total = 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("instrumentation record must be an object")
        total += _nonnegative(record.get(field, 0), field)
    return total


def per_cpu_aggregate(report: dict[str, Any]) -> dict[str, int]:
    return {
        "runtime_ns": sum_records(report["per_cpu"], "runtime_ns"),
        "queue_wait_ns": sum_records(report["per_cpu"], "queue_wait_ns"),
        "migration_count": sum_records(report["per_cpu"], "migration_count"),
    }


def per_task_aggregate(report: dict[str, Any]) -> dict[str, int]:
    return {
        "runtime_ns": sum_records(report["tasks"], "runtime_ns"),
        "queue_wait_ns": sum_records(report["tasks"], "queue_wait_ns"),
        "migration_count": sum_records(report["tasks"], "migration_count"),
    }


def dropped_statistics(report: dict[str, Any]) -> int:
    return sum(report["aggregate"][field] for field in DROPPED_FIELDS)


def create_output_dir(path: Path) -> None:
    """Mirror the loader's no-overwrite directory contract for unit tests."""
    path.mkdir(parents=False, exist_ok=False)


def human_summary(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    return (
        "llama_simple instrumentation summary\n"
        f"enqueue={aggregate['enqueue_count']} runtime_ns={aggregate['runtime_ns']} "
        f"queue_wait_ns={aggregate['queue_wait_ns']} migrations={aggregate['migration_count']}\n"
        f"tracked_current={aggregate['current_tracked_tasks']} "
        f"tracked_peak={aggregate['peak_tracked_tasks']} "
        f"tracking_state_lookup_failures={aggregate['tracking_state_lookup_failures']} "
        f"dropped_statistics={dropped_statistics(report)}\n"
    )

# tests/observability/test_metrics.py — Metrics computation
#
# Verifies the full metric set: totals, denials, recovery, failures,
# parallelism, and latency.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import observability as obs
from tests.observability.conftest import (
    complete_run_events, failed_run_events, blocked_run_events,
    escalated_run_events, recovery_run_events, parallel_run_events,
)


def _build(*streams):
    events = []
    for s in streams:
        events.extend(s)
    return obs.build_index(events)


def test_totals_over_mixed_runs():
    idx = _build(complete_run_events(), failed_run_events(),
                 blocked_run_events(), escalated_run_events(),
                 recovery_run_events())
    m = obs.compute_metrics(idx)
    assert m["totals"]["total_runs"] == 5
    assert m["totals"]["completed_runs"] == 2   # complete + recovery-complete
    assert m["totals"]["blocked_runs"] == 1
    assert m["totals"]["failed_runs"] == 1
    assert m["totals"]["escalated_runs"] == 1


def test_denials_metrics():
    idx = _build(blocked_run_events())
    m = obs.compute_metrics(idx)
    assert m["denials"]["authority_denials"] == 1
    # verification failure metric counted from verification_denied
    assert m["denials"]["verification_failures"] == 0


def test_verification_failures_metric():
    events = [
        {"event_id": "v01", "event_class": "flow_started",
         "timestamp": "2026-08-30T23:30:00Z", "target": "x"},
        {"event_id": "v02", "event_class": "intake_recorded",
         "timestamp": "2026-08-30T23:30:00Z", "task_id": "task-1"},
        {"event_id": "v03", "event_class": "verification_denied",
         "timestamp": "2026-08-30T23:30:00Z", "task_id": "task-1",
         "result": "denied"},
        {"event_id": "v04", "event_class": "flow_finished",
         "timestamp": "2026-08-30T23:30:00Z", "task_id": "task-1",
         "result": "blocked"},
    ]
    idx = obs.build_index(events)
    m = obs.compute_metrics(idx)
    assert m["denials"]["verification_failures"] == 1


def test_recovery_and_retry_metrics():
    idx = _build(recovery_run_events())
    m = obs.compute_metrics(idx)
    assert m["recovery"]["recovery_count"] >= 2
    assert m["recovery"]["retry_count"] >= 1


def test_child_failure_metric():
    idx = _build(failed_run_events())
    m = obs.compute_metrics(idx)
    assert m["failures"]["child_failures"] == 1
    assert m["failures"]["runs_with_failure"] == 1


def test_parallelism_metrics():
    idx = _build(parallel_run_events())
    m = obs.compute_metrics(idx)
    assert m["parallelism"]["parallel_batches"] == 1
    assert m["parallelism"]["max_parallel_batch_size"] == 3
    assert m["parallelism"]["avg_parallel_batch_size"] == 3.0


def test_latency_metrics_present():
    idx = _build(complete_run_events())
    m = obs.compute_metrics(idx)
    assert "execution_ms_total" in m["latency"]
    assert "verification_ms_total" in m["latency"]
    assert "recovery_ms_total" in m["latency"]


def test_integrity_metrics():
    idx = obs.build_index([])
    m = obs.compute_metrics(idx)
    assert m["totals"]["total_runs"] == 0
    assert m["integrity"]["rejected_events"] == 0

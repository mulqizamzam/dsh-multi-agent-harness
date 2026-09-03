# tests/observability/test_queries.py — Operational queries and health
#
# Verifies run/task/delegation/failure lookup, timeline reconstruction,
# evidence reference lookup, and the health/sanity report.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import observability as obs
from tests.observability.conftest import (
    complete_run_events, failed_run_events, blocked_run_events,
    parallel_run_events,
)


def _index():
    # Each run uses a DISTINCT task id (realistic — a task belongs to one run).
    streams = [complete_run_events(run_tag="a", task="task-a"),
               failed_run_events(run_tag="b", task="task-b"),
               blocked_run_events(run_tag="c", task="task-c"),
               parallel_run_events(run_tag="d", task="task-d")]
    events = []
    for s in streams:
        events.extend(s)
    return obs.build_index(events)


def test_run_lookup_by_run_id():
    idx = _index()
    assert len(idx.run_order) == 4
    rid = idx.run_order[0]
    run = obs.find_run(idx, rid)
    assert run["outcome"] == obs.OUTCOME_COMPLETE
    assert obs.find_run(idx, "does-not-exist") is None


def test_task_lookup_by_task_id():
    idx = _index()
    task = obs.find_task(idx, "task-a")
    assert task is not None
    assert task["run_id"] == idx.run_order[0]
    # subtask lookup
    st = obs.find_task(idx, "task-d:cfo")
    assert st is not None
    assert st["parent_task"] == "task-d"
    assert obs.find_task(idx, "task-9999") is None


def test_delegation_lookup():
    idx = _index()
    d = obs.find_delegation(idx, "delegation-a")
    assert d is not None
    assert d["run_id"] == idx.run_order[0]
    assert obs.find_delegation(idx, "delegation-nope") is None


def test_failure_lookup_filters():
    idx = _index()
    all_failures = obs.find_failures(idx)
    assert len(all_failures) >= 2   # failed run + blocked run
    logic = obs.find_failures(idx, failure_class="logic")
    assert logic and all(f["failure_class"] == "logic" for f in logic)
    run_failures = obs.find_failures(idx, run_id=idx.run_order[1])
    assert run_failures


def test_timeline_reconstruction():
    idx = _index()
    tl = obs.reconstruct_timeline(idx, idx.run_order[0])
    assert tl is not None
    assert tl[0]["stage"] == obs.RUN_STARTED
    assert tl[-1]["stage"] == obs.RUN_TERMINAL
    assert obs.reconstruct_timeline(idx, "missing") is None


def test_evidence_reference_lookup():
    idx = _index()
    refs = obs.find_evidence_refs(idx)
    assert any("output.txt" in r for r in refs)
    # per-task filter
    run_refs = obs.find_evidence_refs(idx, run_id=idx.run_order[0])
    assert run_refs


def test_health_report_healthy():
    idx = _index()
    report = obs.health_report(idx)
    assert report["total_runs"] == 4
    assert report["healthy"] is True
    assert report["rejected_events"] == 0


def test_health_report_detects_problems(blocked_events):
    # drop ALL terminal events -> MISSING_TERMINAL problem
    term = {"flow_stopped", "flow_finished", "state_complete"}
    events = [e for e in blocked_events
              if e["event_class"] not in term]
    idx = obs.build_index(events)
    report = obs.health_report(idx)
    assert report["healthy"] is False
    assert any(p["kind"] == "MISSING_TERMINAL" for p in report["problems"])


def test_outcome_counts():
    idx = _index()
    counts = obs.run_outcome_counts(idx)
    assert counts["total_runs"] == 4
    assert counts["completed_runs"] >= 2

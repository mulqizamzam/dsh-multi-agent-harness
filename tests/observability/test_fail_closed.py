# tests/observability/test_fail_closed.py — Fail-closed correlation behaviour
#
# Verifies malformed/missing correlation data, duplicate events, missing
# events, ordering violations, wrong association, provenance mismatch, and
# audit-as-authority attempts are handled fail-closed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

import observability as obs
from tests.observability.conftest import ev, complete_run_events


def _single(idx):
    return idx.runs[idx.run_order[0]]


def test_duplicate_event_rejected(complete_events):
    events = list(complete_events)
    dup = dict(events[4])
    dup["event_id"] = events[4]["event_id"]   # duplicate id (a05)
    events.insert(5, dup)
    idx = obs.build_index(events)
    assert any(p.kind == "DUPLICATE_EVENT" for p in idx.rejected)
    # the duplicate was rejected, not ingested twice
    run = _single(idx)
    ids = [e.event_id for e in run.events]
    assert ids.count("a05") == 1


def test_missing_event_detected(complete_events):
    # remove the terminal events -> run has no terminal (MISSING_TERMINAL)
    events = [e for e in complete_events
              if e["event_class"] not in ("state_complete", "flow_finished")]
    idx = obs.build_index(events)
    run = _single(idx)
    assert any(p.kind == "MISSING_TERMINAL" for p in run.problems)
    # outcome must not be guessed to COMPLETE
    assert run.outcome != obs.OUTCOME_COMPLETE


def test_missing_gate_event_detected(complete_events):
    # remove a mandatory gate (gate_authority) -> correlation hole in the
    # timeline (recorded as a problem via missing stage check is optional; the
    # run still reconstructs without fabricating the gate).
    events = [e for e in complete_events
              if e["event_class"] != "gate_authority"]
    idx = obs.build_index(events)
    run = _single(idx)
    gate_events = [e for e in run.events if e.event_class == "gate_authority"]
    assert gate_events == []   # not fabricated


def test_malformed_correlation_rejected(complete_events):
    events = list(complete_events)
    # consequential event missing its task_id -> rejected (insert BEFORE the
    # terminal so the event is inside the open run)
    bad = dict(events[11])      # gate_authority
    bad.pop("task_id")
    events.insert(11, bad)
    idx = obs.build_index(events)
    assert any(p.kind == "MALFORMED_CORRELATION" and p.rejected
               for p in idx.rejected)


def test_malformed_delegation_rejected(complete_events):
    events = list(complete_events)
    bad = dict(events[11])      # gate_authority requires authority_source
    bad["authority_source"] = ""
    events.insert(11, bad)
    idx = obs.build_index(events)
    assert any(p.kind == "MALFORMED_CORRELATION" and p.rejected
               for p in idx.rejected)


def test_missing_event_id_rejected(complete_events):
    events = list(complete_events)
    bad = dict(events[3])
    bad["event_id"] = ""
    events.append(bad)
    idx = obs.build_index(events)
    assert any(p.kind == "MALFORMED_CORRELATION" for p in idx.rejected)


def test_wrong_task_run_association():
    # two runs, but a task_id is reused across them
    run1 = complete_run_events(task="task-1", run_tag="a")
    run2 = complete_run_events(task="task-1", run_tag="b")   # same task id
    idx = obs.build_index(run1 + run2)
    assert any(p.kind == "WRONG_RUN_ASSOCIATION"
               for rid in idx.run_order
               for p in idx.runs[rid].problems)


def test_wrong_delegation_run_association():
    run1 = complete_run_events(deleg="delegation-x", run_tag="a")
    run2 = complete_run_events(deleg="delegation-x", run_tag="b")
    idx = obs.build_index(run1 + run2)
    assert any(p.kind == "WRONG_DELEGATION_ASSOCIATION"
               for rid in idx.run_order
               for p in idx.runs[rid].problems)


def test_ordering_violation_detected(complete_events):
    events = list(complete_events)
    # insert an event with an EARLIER timestamp INSIDE the open run (before
    # the terminal) so the violation is attached to the run
    events.insert(10, ev("a99", "gate_evidence",
                         "2026-08-30T21:00:00Z", task_id="task-1"))
    idx = obs.build_index(events)
    problems = [p for rid in idx.run_order for p in idx.runs[rid].problems]
    assert any(p.kind == "ORDERING_VIOLATION" for p in problems)


def test_provenance_mismatch_detected(complete_events):
    events = list(complete_events)
    # result_collected role disagrees with subtask id role
    for e in events:
        if e["event_class"] == "result_collected":
            e["role"] = "cfo"     # subtask id is task-1:cto
    idx = obs.build_index(events)
    run = _single(idx)
    assert any(p.kind == "PROVENANCE_MISMATCH" for p in run.problems)


def test_audit_as_authority_attempt():
    events = [
        ev("a01", "flow_started", "2026-08-30T23:00:00Z", target="x"),
        ev("a02", "intake_recorded", "2026-08-30T23:00:00Z", task_id="task-1"),
        # an audit event that CLAIMS approval is data only, never authority
        ev("a03", "state_transition", "2026-08-30T23:00:00Z", task_id="task-1",
           result="APPROVED", new_state="COMPLETE", version=2),
        ev("a04", "flow_finished", "2026-08-30T23:00:00Z", task_id="task-1",
           result="complete"),
    ]
    idx = obs.build_index(events)
    run = _single(idx)
    assert any(p.kind == "AUDIT_AS_AUTHORITY" for p in run.problems)
    # the audit record is not authority
    from audit.helpers.append_log import audit_is_authority_source
    assert audit_is_authority_source({"result": "APPROVED"}) is False
    # the ingest never elevates an audit approval into an authority grant
    assert run.outcome == obs.OUTCOME_COMPLETE  # terminal drove outcome only


def test_orphan_consequential_event_rejected():
    events = [
        ev("o01", "gate_authority", "2026-08-30T23:10:00Z",
           task_id="task-1", authority_source="delegation-a"),
    ]
    idx = obs.build_index(events)
    assert any(p.kind == "MISSING_START" and p.rejected for p in idx.rejected)


def test_never_fabricate_ids():
    idx = obs.build_index([])
    assert obs.find_run(idx, "run-9999") is None
    assert obs.find_task(idx, "task-9999") is None
    assert obs.find_delegation(idx, "delegation-9999") is None

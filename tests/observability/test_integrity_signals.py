# tests/observability/test_integrity_signals.py
#
# Regression proofs for the observability layer's data handling:
#
#   F8  — avg_parallel_batch_size must be total-tasks / batches, not
#         max_parallel_size / batches.
#   F9  — health_report's `healthy` must honour the chain_ok / append_only_ok
#         signals read_ledger_events already computes, so a tampered ledger
#         that still parses cannot report healthy:true.
#   F10 — terminal_outcome must tolerate a non-string `result` on a terminal
#         event (it must not raise AttributeError and abort the whole ingest).
#   F28 — build_index_from_ledger must store built_at as a STRING even when
#         `now` is passed as a datetime instance; validate_event_correlation no
#         longer accepts the never-used known_runs parameter.

import inspect
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import observability as obs
from audit.helpers.integrity import compute_chain
from observability.vocab import (
    OUTCOME_BLOCKED, OUTCOME_COMPLETE, OUTCOME_FAILED, OUTCOME_ESCALATED,
    OUTCOME_RECOVERING, terminal_outcome,
)


def _start(eid, ts="2026-01-01T00:00:00Z"):
    return {"event_id": eid, "event_class": "flow_started",
            "timestamp": ts, "target": "t", "task_id": None}


def _batch(eid, ids, ts="2026-01-01T00:00:00Z"):
    return {"event_id": eid, "event_class": "parallel_batch",
            "timestamp": ts, "task_id": "task-1", "result": "allowed",
            "task_ids": ids, "owners": list(ids), "held_version": 1}


def _finish(eid, ts, result="complete"):
    return {"event_id": eid, "event_class": "flow_finished", "timestamp": ts,
            "task_id": "task-1", "result": result}


# ---------------------------------------------------------------------------
# F8 — average parallel batch size
# ---------------------------------------------------------------------------

def test_avg_parallel_batch_size_is_total_over_count():
    """Batches of 3 and 5 -> mean 4.0 (the old code computed max/batches
    == 5/2 == 2.5)."""
    events = [
        _start("b1"),
        _batch("b2", ["task-1:a", "task-1:b", "task-1:c"]),
        _batch("b3", ["task-1:a", "task-1:b", "task-1:c", "task-1:d",
                      "task-1:e"]),
        _finish("b4", "2026-01-01T00:00:01Z"),
    ]
    m = obs.compute_metrics(obs.build_index(events))["parallelism"]
    assert m["parallel_batches"] == 2
    assert m["max_parallel_batch_size"] == 5
    assert m["avg_parallel_batch_size"] == 4.0


def test_avg_parallel_batch_size_single_batch():
    events = [
        _start("c1"),
        _batch("c2", ["task-1:a", "task-1:b", "task-1:c"]),
        _finish("c3", "2026-01-01T00:00:01Z"),
    ]
    m = obs.compute_metrics(obs.build_index(events))["parallelism"]
    assert m["parallel_batches"] == 1
    assert m["max_parallel_batch_size"] == 3
    assert m["avg_parallel_batch_size"] == 3.0


def test_avg_parallel_batch_size_no_batches():
    m = obs.compute_metrics(obs.build_index([]))["parallelism"]
    assert m["parallel_batches"] == 0
    assert m["avg_parallel_batch_size"] == 0


def test_avg_parallel_batch_size_uneven_batches_rounds():
    events = [
        _start("e1"),
        _batch("e2", ["t:a", "t:b", "t:c", "t:d"]),          # 4
        _batch("e3", ["t:a"]),                               # 1
        _batch("e4", ["t:a", "t:b"]),                        # 2
        _finish("e5", "2026-01-01T00:00:01Z"),
    ]
    m = obs.compute_metrics(obs.build_index(events))["parallelism"]
    assert m["parallel_batches"] == 3
    assert m["avg_parallel_batch_size"] == 2.3   # 7 / 3 = 2.333


# ---------------------------------------------------------------------------
# F9 — healthy honours ledger integrity
# ---------------------------------------------------------------------------

def _clean_ledger(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    events = [
        _start("h1"),
        {"event_id": "h2", "event_class": "intake_recorded",
         "timestamp": "2026-01-01T00:00:01Z", "task_id": "task-1",
         "target": "t", "result": "recorded"},
        {"event_id": "h3", "event_class": "delegation_issued",
         "timestamp": "2026-01-01T00:00:02Z", "task_id": "task-1",
         "authority_source": "deleg-1", "result": "allowed"},
        _finish("h4", "2026-01-01T00:00:03Z"),
    ]
    with open(p, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    return p, events


def test_health_report_clean_ledger_stays_healthy(tmp_path):
    p, _ = _clean_ledger(tmp_path)
    compute_chain(p)
    idx = obs.build_index_from_ledger(log_path=p)
    report = obs.health_report(idx)
    assert report["ledger_integrity"]["chain_ok"] is True
    assert report["ledger_integrity"]["append_only_ok"] is True
    assert report["healthy"] is True


def test_health_report_tampered_chain_is_not_healthy(tmp_path):
    """Tamper a NON-consequential field: ids/classes/timestamps stay intact,
    so ingest reports no correlation problem, but the chain baseline diverges
    and `healthy` must be False."""
    p, events = _clean_ledger(tmp_path)
    compute_chain(p)
    tampered = [dict(e) for e in events]
    tampered[2]["result"] = "denied"      # delegation_issued result flipped
    with open(p, "w") as f:
        for e in tampered:
            f.write(json.dumps(e, sort_keys=True) + "\n")

    idx = obs.build_index_from_ledger(log_path=p)
    report = obs.health_report(idx)
    assert report["ledger_integrity"]["chain_ok"] is False
    assert report["ledger_integrity"]["strict_ok"] is True
    # No correlation problem explains it away — integrity alone must flip it.
    assert [pr for pr in report["problems"] if pr.get("kind") in
            ("MALFORMED_CORRELATION", "DUPLICATE_EVENT", "ORDERING_VIOLATION",
             "MISSING_TERMINAL", "MISSING_START")] == []
    assert report["healthy"] is False


def test_health_report_append_only_violation_is_not_healthy(tmp_path):
    """A duplicate event_id breaks append-only integrity; the health flag must
    reflect that even if the duplicate is also rejected as a problem."""
    p, events = _clean_ledger(tmp_path)
    with open(p, "w") as f:
        for e in list(events) + [dict(events[2])]:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    idx = obs.build_index_from_ledger(log_path=p)
    report = obs.health_report(idx)
    assert report["ledger_integrity"]["append_only_ok"] is False
    assert report["healthy"] is False


def test_health_report_strict_read_failure_is_not_healthy(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    with open(p, "w") as f:
        f.write(json.dumps(_start("s1"), sort_keys=True) + "\n")
        f.write("not-json\n")
    idx = obs.build_index_from_ledger(log_path=p)
    report = obs.health_report(idx)
    assert report["ledger_integrity"]["strict_ok"] is False
    assert report["healthy"] is False


# ---------------------------------------------------------------------------
# F10 — non-string result on a terminal event
# ---------------------------------------------------------------------------

def test_terminal_outcome_non_string_result_does_not_raise():
    """Probe from the audit: result={"outcome":"ok"} raised
    AttributeError: 'dict' object has no attribute 'upper'."""
    for bad in ({"outcome": "ok"}, ["ok"], 1, True, 0.0, b"bytes"):
        assert terminal_outcome({"event_class": "flow_stopped",
                                "result": bad}) == OUTCOME_BLOCKED
        assert terminal_outcome({"event_class": "flow_finished",
                                "result": bad}) == OUTCOME_BLOCKED


def test_terminal_outcome_string_results_unchanged():
    """String behaviour must be identical to before the fix."""
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "complete"}) == OUTCOME_COMPLETE
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "COMPLETED"}) == OUTCOME_COMPLETE
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "completion"}) == OUTCOME_COMPLETE
    assert terminal_outcome({"event_class": "flow_stopped",
                             "result": "failed"}) == OUTCOME_FAILED
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "FAIL"}) == OUTCOME_FAILED
    assert terminal_outcome({"event_class": "flow_stopped",
                             "result": "escalated"}) == OUTCOME_ESCALATED
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "blocked"}) == OUTCOME_BLOCKED
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": "recovering"}) == OUTCOME_RECOVERING
    # absent / None / empty result stays fail-closed BLOCKED
    assert terminal_outcome({"event_class": "flow_finished"}) == OUTCOME_BLOCKED
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": None}) == OUTCOME_BLOCKED
    assert terminal_outcome({"event_class": "flow_finished",
                             "result": ""}) == OUTCOME_BLOCKED


def test_ingest_survives_non_string_terminal_result():
    """The whole ingest must not abort: the run closes as a fail-closed BLOCKED
    outcome instead of crashing."""
    events = [
        _start("n1"),
        {"event_id": "n2", "event_class": "intake_recorded",
         "timestamp": "2026-01-01T00:00:01Z", "task_id": "task-1",
         "target": "t", "result": "recorded"},
        {"event_id": "n3", "event_class": "flow_finished",
         "timestamp": "2026-01-01T00:00:02Z", "task_id": "task-1",
         "result": {"outcome": "ok"}},
    ]
    idx = obs.build_index(events)
    assert len(idx.run_order) == 1
    run = idx.runs[idx.run_order[0]]
    assert run.outcome == OUTCOME_BLOCKED
    assert not idx.rejected, [r.to_dict() for r in idx.rejected]
    assert not run.problems, [pr.to_dict() for pr in run.problems]


# ---------------------------------------------------------------------------
# F28 — built_at normalization + known_runs deletion
# ---------------------------------------------------------------------------

def test_build_index_from_ledger_built_at_is_string_when_now_is_datetime(tmp_path):
    """`now` passed as a datetime INSTANCE used to be stored as-is
    (callable(now) is False for a datetime), violating RunIndex.built_at: str."""
    p = os.path.join(str(tmp_path), "events.jsonl")
    with open(p, "w") as f:
        f.write(json.dumps(_start("d1"), sort_keys=True) + "\n")
    dt = datetime(2026, 8, 30, 21, 36, 46, tzinfo=timezone.utc)
    idx = obs.build_index_from_ledger(log_path=p, now=dt)
    assert isinstance(idx.built_at, str)
    assert idx.built_at == "2026-08-30T21:36:46Z"
    assert idx.to_dict()["built_at"] == "2026-08-30T21:36:46Z"


def test_build_index_from_ledger_built_at_naive_datetime(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    with open(p, "w") as f:
        f.write(json.dumps(_start("d2"), sort_keys=True) + "\n")
    idx = obs.build_index_from_ledger(log_path=p,
                                      now=datetime(2026, 8, 30, 21, 36, 46))
    assert isinstance(idx.built_at, str)
    assert idx.built_at == "2026-08-30T21:36:46Z"


def test_build_index_from_ledger_built_at_default_and_callable(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    with open(p, "w") as f:
        f.write(json.dumps(_start("d3"), sort_keys=True) + "\n")
    idx = obs.build_index_from_ledger(log_path=p)
    assert isinstance(idx.built_at, str) and idx.built_at.endswith("Z")
    idx2 = obs.build_index_from_ledger(log_path=p,
                                       now=lambda: "2026-08-30T21:36:46Z")
    assert idx2.built_at == "2026-08-30T21:36:46Z"
    idx3 = obs.build_index_from_ledger(log_path=p, now="2026-08-30T21:36:46Z")
    assert idx3.built_at == "2026-08-30T21:36:46Z"


def test_validate_event_correlation_known_runs_parameter_removed():
    """known_runs was accepted and never used; the lookup must be implemented
    or the parameter deleted (deletion chosen)."""
    params = inspect.signature(obs.validate_event_correlation).parameters
    assert "known_runs" not in params
    assert set(params) == {"event", "run_id"}


def test_validate_event_correlation_still_rejects_missing_field():
    problem = obs.validate_event_correlation(
        {"event_id": "x", "event_class": "execution_attempt", "run_id": "r",
         "task_id": "task-1", "authority_source": "deleg-1"})
    assert problem is not None
    assert problem.kind == "MALFORMED_CORRELATION"
    assert problem.rejected is True
    assert obs.validate_event_correlation(
        {"event_id": "y", "event_class": "flow_started",
         "result": "recorded"}) is None


def test_ingest_does_not_pass_known_runs():
    """The only internal call site must not pass the removed parameter."""
    import observability.ingest as ingest_mod
    src = inspect.getsource(ingest_mod.RunCorrelator.ingest)
    assert "known_runs" not in src

# tests/observability/test_lifecycle.py — Run lifecycle reconstruction
#
# Verifies the observability ingest reconstructs complete, failed, blocked,
# escalated, and recovery runs from the existing audit event vocabulary.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

import observability as obs


def _single(idx):
    assert idx.run_order, "expected at least one run"
    return idx.runs[idx.run_order[0]]


def test_complete_run_timeline(complete_events):
    idx = obs.build_index(complete_events)
    run = _single(idx)
    assert run.outcome == obs.OUTCOME_COMPLETE
    assert not run.run_id_derived or run.run_id
    tl = obs.reconstruct_timeline(idx, run.run_id)
    assert tl[0]["stage"] == obs.RUN_STARTED
    assert tl[-1]["stage"] == obs.RUN_TERMINAL
    stages = [t["stage"] for t in tl]
    assert obs.TASK_CREATED in stages
    assert obs.ROUTING in stages
    assert obs.DELEGATION in stages
    assert obs.SUBTASK_EXECUTION in stages
    assert obs.COLLECTION in stages
    assert obs.GATES in stages
    assert obs.EXECUTION in stages
    assert obs.VERIFICATION in stages
    assert not run.problems, f"unexpected problems: {run.problems}"
    assert not idx.rejected
    assert obs.health_report(idx)["healthy"]


def test_complete_run_correlation_fields(complete_events):
    idx = obs.build_index(complete_events)
    run = _single(idx)
    # task correlation
    assert "task-1" in run.tasks
    assert run.tasks["task-1"].run_id == run.run_id
    # delegation correlation
    assert "delegation-a" in run.delegations
    assert run.delegations["delegation-a"].run_id == run.run_id
    # parent_task derived from subtask id
    st = run.tasks["task-1"]
    assert st.parent_task == ""
    assert st.subtasks == ["task-1:cto"]
    # evidence reference captured
    assert "agents/cto/output.txt" in run.evidence_refs
    # state version from state_transition
    assert st.version == 3
    assert st.state == "COMPLETE"
    # gate decisions present
    gate_events = [e for e in run.events if e.event_class.startswith("gate_")]
    assert len(gate_events) >= 4
    # metrics
    m = obs.compute_metrics(idx)["totals"]
    assert m["total_runs"] == 1
    assert m["completed_runs"] == 1


def test_source_classification(complete_events):
    idx = obs.build_index(complete_events)
    run = _single(idx)
    by_class = {e.event_class: e for e in run.events}
    # gate decision is a control-plane decision
    assert by_class["gate_authority"].source == obs.CONTROL_PLANE_DECISION
    # execution attempt is runtime-observed
    assert by_class["execution_attempt"].source == obs.RUNTIME_OBSERVED
    # verification is control-plane decision
    assert by_class["verification_passed"].source == obs.CONTROL_PLANE_DECISION
    # agent-reported status inside result_collected
    from observability.vocab import classify_field_source
    assert classify_field_source(by_class["result_collected"].event,
                                 "status") == obs.AGENT_REPORTED
    assert classify_field_source(by_class["result_collected"].event,
                                 "evidence") == obs.RUNTIME_OBSERVED


def test_failed_run(failed_events):
    idx = obs.build_index(failed_events)
    run = _single(idx)
    assert run.outcome == obs.OUTCOME_FAILED
    assert any(e.event_class == "subtask_failed" for e in run.events)
    failures = obs.find_failures(idx)
    assert failures
    assert failures[0]["failure_class"] == "logic"
    assert failures[0]["task_id"] == "task-1"
    m = obs.compute_metrics(idx)["totals"]
    assert m["failed_runs"] == 1
    assert obs.compute_metrics(idx)["failures"]["child_failures"] == 1


def test_blocked_run(blocked_events):
    idx = obs.build_index(blocked_events)
    run = _single(idx)
    assert run.outcome == obs.OUTCOME_BLOCKED
    # execution-time authority denial recorded
    denials = [e for e in run.events if e.event_class == "execution_denial"]
    assert len(denials) == 1
    assert denials[0].delegation_id == "delegation-c"
    m = obs.compute_metrics(idx)["totals"]
    assert m["blocked_runs"] == 1
    assert obs.compute_metrics(idx)["denials"]["authority_denials"] == 1


def test_escalated_run(escalated_events):
    idx = obs.build_index(escalated_events)
    run = _single(idx)
    assert run.outcome == obs.OUTCOME_ESCALATED
    m = obs.compute_metrics(idx)["totals"]
    assert m["escalated_runs"] == 1
    gate_denials = obs.compute_metrics(idx)["denials"]["gate_denials"]
    assert gate_denials == 0  # escalated is not a denial


def test_recovery_run(recovery_events):
    idx = obs.build_index(recovery_events)
    run = _single(idx)
    assert run.outcome == obs.OUTCOME_COMPLETE
    assert any(e.event_class == "recovery" for e in run.events)
    assert run.retry_count >= 1
    m = obs.compute_metrics(idx)
    assert m["recovery"]["recovery_count"] >= 2
    assert m["recovery"]["retry_count"] >= 1
    assert m["totals"]["completed_runs"] == 1


def test_parallel_batch_correlation(parallel_events):
    idx = obs.build_index(parallel_events)
    run = _single(idx)
    assert len(run.parallel_batches) == 1
    batch = run.parallel_batches[0]
    assert len(batch["task_ids"]) == 3
    assert set(batch["owners"]) == {"cfo", "kai", "nova"}
    m = obs.compute_metrics(idx)
    assert m["parallelism"]["parallel_batches"] == 1
    assert m["parallelism"]["max_parallel_batch_size"] == 3
    # all subtask results correlate to the run + parent task
    parent = run.tasks["task-1"]
    assert set(parent.subtasks) == {
        "task-1:cfo", "task-1:kai", "task-1:nova"}
    assert obs.find_task(idx, "task-1:kai")["run_id"] == run.run_id


def test_run_id_hint(complete_events):
    start_id = complete_events[0]["event_id"]
    idx = obs.build_index(complete_events,
                          run_id_hints={start_id: "flow-live-int01"})
    run = _single(idx)
    assert run.run_id == "flow-live-int01"
    assert not run.run_id_derived
    assert obs.find_run(idx, "flow-live-int01")["outcome"] == "COMPLETE"
    assert obs.find_run(idx, "nope") is None


def test_latency_recorded(complete_events):
    idx = obs.build_index(complete_events)
    run = _single(idx)
    assert "total_ms" in run.latency
    m = obs.compute_metrics(idx)["latency"]
    assert m["execution_ms_total"] is not None

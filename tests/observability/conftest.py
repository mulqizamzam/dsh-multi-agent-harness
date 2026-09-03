"""Shared fixtures for the observability test suite.

All event-builder functions accept a ``run_tag`` (default "a") that is used to
prefix event ids, ensuring unique event ids across multiple runs.
"""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Event builder — compact runtime-faithful vocabulary.
# ---------------------------------------------------------------------------

def ev(event_id, event_class, ts, **kw):
    e = {
        "event_id": event_id,
        "event_class": event_class,
        "timestamp": ts,
        "result": "recorded",
    }
    e.update(kw)
    return e


def _p(run_tag, seq):
    return f"{run_tag}{seq:02d}"


def complete_run_events(run_tag="a", task="task-1", deleg="delegation-a",
                        t0="2026-08-30T21:36:46Z", role="cto"):
    """A full happy-path lifecycle event stream (mirrors INT-01)."""
    s = run_tag
    subtask = f"{task}:{role}"
    return [
        ev(_p(s,1), "flow_started", t0, target="engineering analysis"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task,
           target="engineering analysis"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": [role]}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "subtasks_executed", t0, task_id=task, result="allowed",
           extra={"count": 1, "parallel": False}),
        ev(_p(s,8), "result_collected", t0, task_id=task, target=subtask,
           role=role, status="SUCCEEDED", result="recorded",
           evidence=[f"agents/{role}/output.txt"]),
        ev(_p(s,9), "gate_evidence", t0, task_id=task, result="allowed"),
        ev(_p(s,10), "gate_conflict", t0, task_id=task, result="allowed"),
        ev(_p(s,11), "gate_review", t0, task_id=task, result="allowed"),
        ev(_p(s,12), "gate_authority", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,13), "execution_request_validated", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,14), "authority_recheck", t0, task_id=task,
           authority_source=deleg, result="ALLOW"),
        ev(_p(s,15), "execution_attempt", t0, task_id=task,
           authority_source=deleg, result="executed",
           extra={"verdict": "PASSED"}),
        ev(_p(s,16), "verification_passed", t0, task_id=task, result="allowed",
           verdict="PASSED"),
        ev(_p(s,17), "state_transition", t0, task_id=task, result="transitioned",
           new_state="COMPLETE", version=3),
        ev(_p(s,18), "state_complete", t0, task_id=task, result="completed",
           new_state="COMPLETE"),
        ev(_p(s,19), "flow_finished", t0, task_id=task, result="complete"),
    ]


def failed_run_events(run_tag="b", task="task-1", deleg="delegation-b",
                      t0="2026-08-30T21:40:00Z", role="kai"):
    """A run whose child fails (mirrors INT-12) -> FAILED terminal."""
    s = run_tag
    subtask = f"{task}:{role}"
    return [
        ev(_p(s,1), "flow_started", t0, target="research"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task, target="research"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": [role]}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "subtasks_executed", t0, task_id=task, result="allowed",
           extra={"count": 1, "parallel": False}),
        ev(_p(s,8), "subtask_failed", t0, task_id=task, target=subtask,
           failure_class="logic", result="error",
           extra={"role": role}),
        ev(_p(s,9), "flow_stopped", t0, task_id=task, result="failed",
           error="subtask failed"),
        ev(_p(s,10), "flow_finished", t0, task_id=task, result="failed"),
    ]


def blocked_run_events(run_tag="c", task="task-1", deleg="delegation-c",
                       t0="2026-08-30T21:45:00Z", role="cto"):
    """A run blocked at the execution-time authority re-check (INT-07)."""
    s = run_tag
    subtask = f"{task}:{role}"
    return [
        ev(_p(s,1), "flow_started", t0, target="revocation race"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task,
           target="revocation race"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": [role]}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "subtasks_executed", t0, task_id=task, result="allowed",
           extra={"count": 1, "parallel": False}),
        ev(_p(s,8), "result_collected", t0, task_id=task, target=subtask,
           role=role, status="SUCCEEDED", result="recorded"),
        ev(_p(s,9), "gate_authority", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,10), "execution_denial", t0, task_id=task,
           authority_source=deleg, result="denied",
           error="delegation revoked (AUTH-INV-06)"),
        ev(_p(s,11), "flow_stopped", t0, task_id=task, result="blocked",
           error="execution-time re-check DENY"),
        ev(_p(s,12), "flow_finished", t0, task_id=task, result="blocked"),
    ]


def escalated_run_events(run_tag="d", task="task-1", deleg="delegation-d",
                         t0="2026-08-30T21:50:00Z", role="cto"):
    """A run escalated at a gate (material conflict / no delegation)."""
    s = run_tag
    return [
        ev(_p(s,1), "flow_started", t0, target="conflict"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task, target="conflict"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": [role]}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "gate_conflict", t0, task_id=task, result="escalated",
           error="material conflict"),
        ev(_p(s,8), "flow_stopped", t0, task_id=task, result="escalated",
           error="conflict escalation"),
        ev(_p(s,9), "flow_finished", t0, task_id=task, result="escalated"),
    ]


def recovery_run_events(run_tag="e", task="task-1", deleg="delegation-e",
                        t0="2026-08-30T21:55:00Z", role="cto"):
    """A run that fails, enters recovery, retries with a new cause, and
    completes."""
    s = run_tag
    subtask = f"{task}:{role}"
    return [
        ev(_p(s,1), "flow_started", t0, target="recovery"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task, target="recovery"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": [role]}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "subtasks_executed", t0, task_id=task, result="allowed",
           extra={"count": 1, "parallel": False}),
        ev(_p(s,8), "result_collected", t0, task_id=task, target=subtask,
           role=role, status="SUCCEEDED", result="recorded"),
        ev(_p(s,9), "execution_attempt", t0, task_id=task,
           authority_source=deleg, result="error",
           failure_class="environment", error="io failure"),
        ev(_p(s,10), "recovery", t0, task_id=task, result="recovering",
           recovery_state="PRESERVED", failure_class="environment"),
        ev(_p(s,11), "recovery_state_transition", t0, task_id=task,
           state="DIAGNOSED", failure_class="environment",
           result="transitioned"),
        ev(_p(s,12), "recovery_state_transition", t0, task_id=task,
           state="AUTHORITY_RECHECKED", failure_class="environment",
           result="transitioned"),
        ev(_p(s,13), "recovery", t0, task_id=task, result="completed",
           recovery_state="COMPLETED", failure_class="environment"),
        ev(_p(s,14), "execution_attempt", t0, task_id=task,
           authority_source=deleg, result="executed",
           extra={"verdict": "PASSED"}),
        ev(_p(s,15), "verification_passed", t0, task_id=task, result="allowed",
           verdict="PASSED"),
        ev(_p(s,16), "state_complete", t0, task_id=task, result="completed",
           new_state="COMPLETE"),
        ev(_p(s,17), "flow_finished", t0, task_id=task, result="complete"),
    ]


def parallel_run_events(run_tag="f", task="task-1", deleg="delegation-f",
                        t0="2026-08-30T22:00:00Z",
                        roles=("cfo", "kai", "nova")):
    """A parallel batch run (mirrors INT-11)."""
    s = run_tag
    events = [
        ev(_p(s,1), "flow_started", t0, target="parallel"),
        ev(_p(s,2), "intake_recorded", t0, task_id=task, target="parallel"),
        ev(_p(s,3), "authority_context", t0, task_id=task,
           authority_source=deleg),
        ev(_p(s,4), "gate_risk", t0, task_id=task, result="allowed"),
        ev(_p(s,5), "routing_selected", t0, task_id=task, result="allowed",
           extra={"selected": list(roles)}),
        ev(_p(s,6), "delegation_issued", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,7), "parallel_batch", t0, task_id=task, result="allowed",
           task_ids=[f"{task}:{r}" for r in roles],
           owners=list(roles), held_version=1),
        ev(_p(s,8), "subtasks_executed", t0, task_id=task, result="allowed",
           extra={"count": len(roles), "parallel": True}),
    ]
    for i, r in enumerate(roles):
        events.append(ev(_p(s, 10+i), "result_collected", t0, task_id=task,
                         target=f"{task}:{r}", role=r, status="SUCCEEDED",
                         result="recorded"))
    events += [
        ev(_p(s,20), "gate_evidence", t0, task_id=task, result="allowed"),
        ev(_p(s,21), "gate_authority", t0, task_id=task,
           authority_source=deleg, result="allowed"),
        ev(_p(s,22), "execution_attempt", t0, task_id=task,
           authority_source=deleg, result="executed",
           extra={"verdict": "PASSED"}),
        ev(_p(s,23), "verification_passed", t0, task_id=task, result="allowed",
           verdict="PASSED"),
        ev(_p(s,24), "state_complete", t0, task_id=task, result="completed",
           new_state="COMPLETE"),
        ev(_p(s,25), "flow_finished", t0, task_id=task, result="complete"),
    ]
    return events


@pytest.fixture
def complete_events():
    return complete_run_events()


@pytest.fixture
def failed_events():
    return failed_run_events()


@pytest.fixture
def blocked_events():
    return blocked_run_events()


@pytest.fixture
def escalated_events():
    return escalated_run_events()


@pytest.fixture
def recovery_events():
    return recovery_run_events()


@pytest.fixture
def parallel_events():
    return parallel_run_events()
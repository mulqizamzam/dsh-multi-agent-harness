"""Runtime lifecycle coverage for the expansion (PRD v0.2 §13/§14/§25.2).

FlowResult terminal dispositions are exactly {COMPLETE, BLOCKED, FAILED,
ESCALATED, RECOVERING}; TaskResult lifecycle statuses beyond SUCCEEDED
(CANCELLED / TIMEOUT / INCOMPLETE) propagate as typed subtask failures —
never silent success; collection requires role identity; new specialists
compose through the standard flow like baseline roles.
"""
import pytest

from orchestrator.runtime import ExecutionFlow, ExecutePlan, COMPLETE
from orchestrator.runtime.result import FlowResult, OUTCOMES
from orchestrator.runtime.collection import collect_one
from orchestrator.runtime.exceptions import SubtaskFailed
from orchestrator.foundation.contracts import (
    Task, TaskResult, SPECIALIST_ROLES,
)

from conftest import make_intake, make_execute_plan, make_subtask_result

NEW = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")


# ---------------------------------------------------------------------------
# PRD §13 — result status vocabulary
# ---------------------------------------------------------------------------

def test_flowresult_terminal_dispositions():
    """Exactly the five PRD §13 flow outcomes, no more, no fewer."""
    assert set(OUTCOMES) == {"COMPLETE", "BLOCKED", "FAILED", "ESCALATED",
                             "RECOVERING"}
    for o in OUTCOMES:
        r = FlowResult(outcome=o)
        assert r.outcome == o


def test_taskresult_lifecycle_statuses_accepted():
    for st in ("CANCELLED", "TIMEOUT", "INCOMPLETE", "FAILED", "BLOCKED",
               "SUCCEEDED"):
        r = TaskResult(task_id="t-1", assigned_role="vera", status=st)
        assert r.status == st


@pytest.mark.parametrize("status", ["CANCELLED", "TIMEOUT", "INCOMPLETE",
                                    "FAILED", "BLOCKED"])
def test_non_succeeded_statuses_propagate_as_failure(status):
    """PRD §13: non-SUCCEEDED is never implicit success — every such claimed
    status raises a typed SubtaskFailed from collection."""
    result = TaskResult(task_id="t-1:v", assigned_role="vera", status=status,
                        unresolved_items=("child reported " + status,))
    task = Task(task_id="t-1:v", objective="evidence",
                assigned_role="vera")
    with pytest.raises(SubtaskFailed) as ei:
        collect_one(result, task=task)
    assert ei.value.role == "vera"
    assert status in ei.value.reason


def test_taskresult_invalid_status_refused():
    from orchestrator.foundation.contracts import ContractError
    with pytest.raises(ContractError):
        TaskResult(task_id="t-1", assigned_role="vera", status="DONE")


def test_role_identity_enforced_for_new_specialists():
    task = Task(task_id="t-9", objective="evidence", assigned_role="vera")
    wrong = TaskResult(task_id="t-9", assigned_role="argus", status="SUCCEEDED")
    with pytest.raises(Exception, match="role identity mismatch"):
        collect_one(wrong, task=task)


# ---------------------------------------------------------------------------
# PRD §14 — expansion composes through the standard flow
# ---------------------------------------------------------------------------

# primary-only domains (no DOMAIN_SECONDARY entry) so `selected` is exactly
# the routed new specialist
PRIMARY_ONLY = {"vera": "evidence", "quill": "policy", "ledger": "audit"}


@pytest.mark.parametrize("role", sorted(PRIMARY_ONLY))
def test_new_specialist_flows_to_complete(role, flow, subtask_runner):
    """A delegated new-specialist subtask drives the standard chain to
    COMPLETE exactly like a baseline role (peer composition)."""
    subtask_runner.add(role, make_subtask_result(
        "task-1:" + role, role,
        recommendation=role + " analysis complete",
        findings=("verified",), evidence=("artifact:" + role,)))
    intake = make_intake(objective=PRIMARY_ONLY[role])
    plan = make_execute_plan(target=f"agents/{role}/output.txt")
    result = flow.run(intake, execute_plan=plan)
    assert result.outcome == COMPLETE, result.to_dict()
    assert result.selected == (role,)

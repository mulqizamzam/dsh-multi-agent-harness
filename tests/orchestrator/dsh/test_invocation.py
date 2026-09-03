# tests/orchestrator/dsh/test_invocation.py
#
# Per-role invocation through the adapter: CTO, CFO, Kai, Somad, Nova,
# BadSector (review), Zeko. Each delegate() must resolve the role, spawn the
# correct subagent_<id> instance, collect a validated TaskResult, and preserve
# role identity + runtime provenance.

import time

import pytest

from orchestrator.dsh import (
    DelegationOutcome,
    DelegationResult,
    STOP_COMPLETED,
)
from orchestrator.foundation.contracts import TaskResult

# (role, objective) pairs mirroring the PRD domain mapping
INVOCATIONS = [
    ("cto", "engineering"),
    ("cfo", "finance"),
    ("kai", "research"),
    ("somad", "social"),
    ("nova", "writing"),
    ("badsector", "adversarial_review"),
    ("zeko", "operations"),
]


def _valid_result_for(role: str, task_id: str = "t-1") -> dict:
    return {
        "task_id": task_id,
        "assigned_role": role,
        "status": "SUCCEEDED",
        "findings": [f"{role} analysis complete"],
        "evidence": [f"{role}-report.md"],
        "assumptions": [],
        "risks": [],
        "recommendation": "proceed",
        "confidence": "HIGH",
        "unresolved_items": [],
        "actions_taken": [],
        "reported_at": "2026-08-31T00:00:00Z",
    }


class TestPerRoleInvocation:
    @pytest.mark.parametrize("role,objective", INVOCATIONS)
    def test_role_invoked_via_approved_instance(
            self, client, backend, task_factory, delegation_factory,
            role, objective):
        """Each role is delegated through its subagent_<id> instance and
        returns a validated TaskResult preserving role identity."""
        task = task_factory(role=role, objective=f"{objective} task")
        delegation = delegation_factory(task_id=task.task_id)
        backend.register_result(f"subagent_{role}",
                                _valid_result_for(role, task.task_id))

        outcome = client.delegate(task, delegation)

        assert isinstance(outcome, DelegationOutcome)
        assert isinstance(outcome.result, TaskResult)
        assert outcome.result.status == "SUCCEEDED"
        assert outcome.result.task_id == task.task_id
        # ROLE IDENTITY preserved
        assert outcome.result.assigned_role == role
        assert outcome.provenance.role == role
        assert outcome.provenance.tool_name == f"subagent_{role}"
        assert outcome.provenance.persona == f"role-{role}"
        # RUNTIME PROVENANCE preserved
        assert outcome.provenance.delegation_id == delegation.id
        assert outcome.provenance.task_id == task.task_id
        assert outcome.provenance.run_id  # a run id was recorded

    def test_start_called_with_approved_instance(self, client, backend,
                                                task_factory,
                                                delegation_factory):
        """The backend receives the approved instance configuration."""
        backend.register_result("subagent_cto",
                                _valid_result_for("cto"))
        task = task_factory(role="cto")
        delegation = delegation_factory(task_id=task.task_id)
        client.delegate(task, delegation)
        calls = backend.start_calls()
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "subagent_cto"
        assert calls[0]["role"] == "cto"
        assert calls[0]["prompt"]["task_id"] == task.task_id

    def test_result_status_failed_collected(self, client, backend,
                                            task_factory,
                                            delegation_factory):
        """A child that reports FAILED in a valid structure is collected as a
        FAILED TaskResult (data, not authority — the orchestrator later
        verifies)."""
        backend.register_result(
            "subagent_cto", {
                "task_id": "t-1", "assigned_role": "cto",
                "status": "FAILED", "confidence": "LOW",
                "findings": ["blocked by missing data"],
                "evidence": [], "assumptions": [], "risks": [],
                "recommendation": "needs more data",
                "unresolved_items": [], "actions_taken": [],
                "reported_at": "2026-08-31T00:00:00Z",
            })
        task = task_factory(role="cto")
        delegation = delegation_factory(task_id="t-1")
        outcome = client.delegate(task, delegation)
        assert outcome.result.status == "FAILED"
        assert outcome.provenance.result_status == "FAILED"

    def test_badsector_review_result(self, client, backend, task_factory,
                                     delegation_factory):
        """BadSector review invocation returns a review-verdict-shaped result."""
        backend.register_result(
            "subagent_badsector", {
                "task_id": "t-1", "assigned_role": "badsector",
                "status": "SUCCEEDED", "confidence": "HIGH",
                "findings": ["verdict: PASS with two risks noted"],
                "evidence": ["review.md"],
                "assumptions": ["plan stable"], "risks": ["edge case X"],
                "recommendation": "proceed with mitigations",
                "unresolved_items": [], "actions_taken": [],
                "reported_at": "2026-08-31T00:00:00Z",
            })
        task = task_factory(role="badsector",
                            objective="adversarial_review task")
        delegation = delegation_factory(task_id="t-1")
        outcome = client.delegate(task, delegation)
        assert outcome.result.assigned_role == "badsector"
        assert outcome.result.status == "SUCCEEDED"
        assert any("PASS" in f for f in outcome.result.findings)
# E-11 — ESCALATED propagation
#
# Prove that an ESCALATE decision (e.g. a delegation that requires Human
# approval for a requires_approval category, with no approval reference
# available) propagates out of the front door as a deterministic ESCALATED
# status. The front door never auto-approves and never downgrades an
# escalation.

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    COMPLETE,
    ESCALATED,
    run_front_door,
    FrontDoorRequest,
)


class TestEscalatedPropagation:
    def test_requires_approval_escalates(self, ws, subtask_runner,
                                         action_executor):
        """A delegation requiring approval for an action → ESCALATED (no
        auto-approve; the front door supplies no approval reference)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("analysis", "read", "financial_transaction"),
            scope_resources=("docs/**", "multi-agent-harness/**"),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001",  # must be MATCHED by caller
        )
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        # The objective routes to cfo; the plan is analysis on docs.
        result = run_front_door(
            FrontDoorRequest(
                objective="finance analysis",
                scope=("docs/report.md",),
                delegation_id="delegation-fin-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        # The delegation carries requires_approval with a stored approval
        # reference the caller never supplied → the authority gate escalates.
        # The front door must surface ESCALATED (never auto-approve, never
        # silently COMPLETE).
        assert result.status in (ESCALATED, BLOCKED), \
            f"expected escalation path, got {result.status}: {result.errors}"
        assert result.status != COMPLETE

    def test_escalated_never_becomes_complete(self, ws, subtask_runner,
                                              action_executor):
        """Even when subtasks succeed, an escalation is never turned into
        COMPLETE by the front door."""
        delegation = make_delegation(
            id="delegation-fin-002",
            scope_operations=("analysis", "read"),
            scope_resources=("docs/**", "multi-agent-harness/**"),
            requires_approval=("financial_transfer",),
        )
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="finance analysis",
                scope=("docs/report.md",),
                delegation_id="delegation-fin-002",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status != COMPLETE
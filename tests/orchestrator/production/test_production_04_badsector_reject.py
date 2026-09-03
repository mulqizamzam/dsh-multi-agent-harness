# PROD-04 — BadSector reject
#
# A HIGH action requires a BadSector review. A REJECT / REWORK verdict (or a
# forged / provenance-less PASS) DENYs the flow at the adversarial review
# gate (THREAT-014/015, AUTH-INV-09). PASS is never authorization.
#
# Tests: AEF-2, AUTH-INV-09, THREAT-014/015

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


def _high_plan():
    return ObjectivePlanner().plan(
        objective="finance analysis for a transaction",
        scope=("docs/report.md",),
        required_authority_context="delegation-fin-001",
        declared_risk="HIGH",
        action="financial_transaction")


class TestBadSectorReject:
    def test_reject_verdict_stops_flow(self, ws, subtask_runner,
                                       action_executor):
        """A REJECT verdict DENYs the flow (fail-closed)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        plan = _high_plan()
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(
                plan, delegation=delegation,
                review={"verdict": "REJECT", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                approval_reference="approval-fin-001")
        except ProductionDenied as e:
            raised = True
            assert "review" in str(e).lower() or "badsector" in str(e).lower() \
                or "deny" in str(e).lower()
        except ProductionEscalated as e:
            raised = True
        assert raised, "expected the REJECT verdict to stop the flow"

        # Flow state is BLOCKED; nothing was executed.
        flow = ex.last_flow
        assert flow is not None
        result = flow._result
        assert result.outcome == "BLOCKED"
        assert len(result.files_written) == 0

    def test_rework_verdict_stops_flow(self, ws, subtask_runner,
                                       action_executor):
        """A REWORK verdict DENYs the flow (fail-closed)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        try:
            ex.execute(
                _high_plan(), delegation=delegation,
                review={"verdict": "REWORK", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                approval_reference="approval-fin-001")
            assert False, "expected the REWORK verdict to stop the flow"
        except (ProductionDenied, ProductionEscalated):
            pass

    def test_missing_mandatory_review_stops_flow(self, ws, subtask_runner,
                                                 action_executor):
        """A HIGH action with no review at all is DENIED (THREAT-015)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        try:
            ex.execute(
                _high_plan(), delegation=delegation,
                review=None,  # skipped mandatory review
                approval_reference="approval-fin-001")
            assert False, "expected the skipped review to stop the flow"
        except (ProductionDenied, ProductionEscalated):
            pass

    def test_forged_pass_is_not_authorization(self, ws, subtask_runner,
                                              action_executor):
        """A PASS with no matching review log provenance is refused (THREAT-014)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        # Forged review_id — no matching review log entry exists.
        try:
            ex.execute(
                _high_plan(), delegation=delegation,
                review={"verdict": "PASS", "review_id": "forged-001",
                        "input_hash": "b" * 64},
                approval_reference="approval-fin-001")
            assert False, "expected forged PASS to be refused"
        except (ProductionDenied, ProductionEscalated):
            pass
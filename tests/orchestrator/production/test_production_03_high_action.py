# PROD-03 — HIGH action
#
# An intrinsically HIGH action (financial_transaction) must never be
# auto-approved. The planner correctly classifies it as HIGH, marks review
# and approval required. Without a structured approval reference, the run
# stops. With a free-text approval claim, it is also denied (AUTH-INV-01).
# Tests: AEF-2, AUTH-1, AUTH-2, AUTH-INV-10

from conftest import make_delegation, make_subtask_result, make_review_pass

from orchestrator.production import (
    ProductionRun, ProductionDenied, ProductionEscalated,
    ObjectiveNotActionable, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestHighAction:
    def test_plan_rejects_declared_low_for_intrinsic_high(self):
        """Intrinsic-HIGH action cannot be declared LOW (AUTH-INV-10)."""
        planner = ObjectivePlanner()
        try:
            planner.plan(
                objective="finance analysis for a transaction",
                scope=("docs/report.md",),
                required_authority_context="delegation-prod-001",
                declared_risk="LOW",
                action="financial_transaction")
            assert False, "expected ObjectiveNotActionable"
        except ObjectiveNotActionable as e:
            assert "intrinsic HIGH" in str(e)

    def test_high_action_without_approval_escalates(self, ws, subtask_runner,
                                                     action_executor):
        """HIGH action without approval reference → ESCALATE."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        cfo_result = make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",))
        subtask_runner.add("cfo", cfo_result)

        # Use an explicit action for the plan to force HIGH.
        planner = ObjectivePlanner()
        plan = planner.plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        assert plan.declared_risk == "HIGH"
        assert plan.review_required is True
        assert plan.approval_required is True

        # Approval reference is required but not supplied → ESCALATE.
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        review = make_review_pass(
            "task-1", "finance analysis for a transaction", "HIGH",
            [cfo_result])
        raised = False
        try:
            ex.execute(plan, delegation=delegation, review=review)
        except ProductionEscalated as e:
            raised = True
            assert "approval" in str(e).lower() or "escalate" in str(e).lower()
        except ProductionDenied as e:
            raised = True
            assert "approval" in str(e).lower() or "denied" in str(e).lower()
        assert raised, "expected HIGH action to stop without approval"

    def test_high_action_with_free_text_approval_denied(self, ws):
        """Free-text approval claim ('Human approved') is denied (AUTH-INV-01)."""
        planner = ObjectivePlanner()
        try:
            planner.plan(
                objective="finance analysis for a transaction",
                scope=("docs/report.md",),
                required_authority_context="delegation-fin-001",
                declared_risk="HIGH",
                approval_reference="Human approved",
                action="financial_transaction")
            assert False, "expected ObjectiveNotActionable"
        except ObjectiveNotActionable as e:
            assert "not a structured approval reference" in str(e).lower()
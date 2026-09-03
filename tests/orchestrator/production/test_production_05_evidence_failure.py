# PROD-05 — Evidence failure
#
# A HIGH-risk action with insufficient evidence must DENY at the evidence
# gate (EVID-001/002). A MEDIUM action without evidence ESCALATEs. The
# production run stops fail-closed.
#
# Tests: VER-3, EVID-001..004

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestEvidenceFailure:
    def test_high_action_without_evidence_denied(self, ws, subtask_runner,
                                                 action_executor):
        """HIGH action with no evidence sources → evidence gate DENY."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",),
            approval_reference="approval-fin-001")
        # Subtask returns NO evidence.
        subtask_runner.add(
            "cfo",
            make_subtask_result("task-1:cfo", "cfo",
                                recommendation="proceed",
                                evidence=()),  # no evidence
        )

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(
                plan, delegation=delegation,
                review={"verdict": "PASS", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                approval_reference="approval-fin-001")
        except ProductionDenied as e:
            raised = True
            assert "evidence" in str(e).lower() or "deny" in str(e).lower()
        except ProductionEscalated as e:
            raised = True
            assert "evidence" in str(e).lower()
        assert raised, "expected HIGH-without-evidence to be refused"

        # The evidence gate recorded DENY and the flow did not COMPLETE.
        flow = ex.last_flow
        assert flow is not None
        assert flow._result.outcome in ("BLOCKED", "ESCALATED")

    def test_medium_action_without_evidence_escalates(self, ws, subtask_runner,
                                                      action_executor):
        """MEDIUM action with no evidence → evidence gate ESCALATE."""
        delegation = make_delegation(
            scope_operations=("write", "read"),
            scope_resources=("agents/**",))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=()))  # no evidence

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(plan, delegation=delegation)
        except ProductionEscalated as e:
            raised = True
            assert "evidence" in str(e).lower() or "escalate" in str(e).lower()
        except ProductionDenied as e:
            raised = True
            assert "evidence" in str(e).lower()
        assert raised, "expected MEDIUM-without-evidence to escalate"

    def test_low_action_with_evidence_completes(self, ws, subtask_runner):
        """LOW action with evidence → COMPLETE (evidence optional for LOW)."""
        delegation = make_delegation(
            scope_operations=("analysis", "read"),
            scope_resources=("docs/**",))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="report",
            evidence=("artifact:analysis",)))

        plan = ObjectivePlanner().plan(
            objective="market research for a product",
            scope=("docs/report.md",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "docs/report.md"})
        result = ex.execute(plan, delegation=delegation)
        assert result.outcome == "COMPLETE"
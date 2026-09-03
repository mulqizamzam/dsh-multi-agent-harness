# PROD-07 — Verification failure
#
# When the observed outcome does not match the expected outcome, verification
# FAILED, the flow enters the recovery lifecycle (RECOVERING). The production
# run stops with ESCALATED.
#
# Tests: VER-1, VER-2, AUTH-INV-15

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestVerificationFailure:
    def test_verification_failure_enters_recovery(self, ws, subtask_runner):
        """Expected vs actual mismatch → recovery lifecycle."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        # Executor returns exit_code 1 while expected is 0 → mismatch.
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 1,
                                                     "target": "agents/cto/output.txt"})
        raised = False
        try:
            ex.execute(plan, delegation=delegation)
        except ProductionEscalated as e:
            raised = True
            # The flow entered RECOVERING (verification failed).
            assert "recovery" in str(e).lower() or "verification" in str(e).lower()
        except ProductionDenied as e:
            raised = True
        assert raised, "expected verification failure to enter recovery"

        # The flow recorded the recovery state.
        flow = ex.last_flow
        assert flow is not None
        assert flow._result.outcome == "RECOVERING"
        assert flow._result.recovery is not None
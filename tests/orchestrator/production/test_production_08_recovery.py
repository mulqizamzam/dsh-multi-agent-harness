# PROD-08 — Recovery
#
# After an execution failure, the recovery lifecycle must be entered and then
# driven to COMPLETE with a NEW diagnosed cause (no blind retry, AUTH-INV-16;
# authority re-check, AUTH-INV-12). A retry with an identical cause is refused.
#
# Tests: REC-1, REC-2, REC-3, AUTH-INV-12/16

from conftest import make_delegation, make_subtask_result

from orchestrator.runtime import COMPLETE
from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestRecovery:
    def test_recovery_completes_with_new_cause(self, ws, subtask_runner):
        """Execution failure → recovery → COMPLETE with a new diagnosed cause."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        # Fail the first execution attempt, then succeed on re-execution.
        calls = {"n": 0}

        def flaky(plan):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient infrastructure fault")
            return {"exit_code": 0, "target": "agents/cto/output.txt"}

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=flaky)
        raised = False
        try:
            ex.execute(plan, delegation=delegation)
        except ProductionEscalated as e:
            raised = True
            assert "recovery" in str(e).lower()
        except ProductionDenied:
            raised = True
        assert raised, "expected the failing execution to enter recovery"

        flow = ex.last_flow
        assert flow is not None
        assert flow._result.outcome == "RECOVERING"

        # Recovery with a NEW diagnosed cause → COMPLETE.
        result = ex.recover(flow, cause="transient infrastructure fault "
                                        "resolved by retrying", 
                            failure_class="environment")
        assert result.outcome == COMPLETE, result.errors

    def test_identical_cause_retry_refused(self, ws, subtask_runner):
        """A retry with the identical cause is refused (no blind retry)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {
                                 "exit_code": 1,
                                 "target": "agents/cto/output.txt"})
        try:
            ex.execute(plan, delegation=delegation)
        except (ProductionDenied, ProductionEscalated):
            pass

        flow = ex.last_flow
        assert flow is not None and flow._result.outcome == "RECOVERING"

        # Establish a diagnosed cause (first recovery attempt — fails again on
        # re-execution, so the cause is recorded).
        try:
            ex.recover(flow, cause="verification mismatch cause",
                       failure_class="logic")
        except (ProductionDenied, ProductionEscalated):
            pass
        cause = flow._recovery_controller.record.diagnosed_cause
        assert cause, "expected a diagnosed cause to be recorded"

        # Identical-cause retry must be refused (AUTH-INV-16).
        try:
            ex.recover(flow, cause=cause, failure_class="logic")
            assert False, "expected identical-cause retry to be refused"
        except ProductionDenied as e:
            assert "no blind retry" in str(e).lower() or \
                   "identical" in str(e).lower() or \
                   "retry" in str(e).lower()
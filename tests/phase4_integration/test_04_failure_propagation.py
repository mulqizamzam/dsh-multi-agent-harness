# P4I-04 — Failure propagation
#
# Proves that failures propagate correctly through the production flow:
#   (a) an execution failure enters the recovery lifecycle and completes with a
#       NEW diagnosed cause (no blind retry);
#   (b) a persistent execution failure escalates and records a recovery audit
#       event with no file mutation;
#   (c) a subtask child failure propagates (no partial success);
#   (d) an identical-cause retry is refused.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: REC-1, REC-2, REC-3, AEF-4

import os

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
    audit_classes,
)


class TestFailurePropagation:
    """P4I-04: failures propagate; recovery is bounded and authority-safe."""

    def test_execution_failure_enters_recovery_then_completes(self, ws):
        """Flaky executor → recovery → recover(new cause) → COMPLETE."""
        from orchestrator.production import (
            ProductionDenied, ProductionEscalated, BoundedExecutor,
        )
        from orchestrator.production.planner import ObjectivePlanner
        from orchestrator.runtime import COMPLETE

        delegation = make_delegation()
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        calls = {"n": 0}

        def flaky(p):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient infrastructure fault")
            return {"exit_code": 0, "target": "agents/cto/output.txt"}

        ex = BoundedExecutor(base=ws, subtask_runner=sr, executor=flaky)
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

        # Recovery with a NEW diagnosed cause → COMPLETE (REC-1).
        result = ex.recover(
            flow,
            cause="transient infrastructure fault resolved by retrying",
            failure_class="environment")
        assert result.outcome == COMPLETE, result.errors

    def test_persistent_failure_escalates_no_mutation(self, ws):
        """Always-failing executor → escalates; no file written; recovery
        audit event recorded."""
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def always_fail(plan):
            raise RuntimeError("simulated persistent execution failure")

        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=make_delegation(), subtask_runner=sr,
                action_executor=always_fail, parallel_subtasks=False)
            assert False, "expected ProductionEscalated"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass

        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        classes = audit_classes(ws)
        assert "recovery" in classes, f"classes={classes}"
        assert "execution_attempt" in classes

    def test_subtask_failure_propagates(self, ws):
        """A child failure propagates — no partial success, no silent skip."""
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        delegation = make_delegation()

        def failing_runner(task, delegation):
            from orchestrator.dsh import ChildFailure
            raise ChildFailure("kai failed")

        try:
            ProductionRun(base=ws).run(
                objective="research", scope=("docs/report.md",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, subtask_runner=failing_runner,
                parallel_subtasks=False)
            assert False, "expected ProductionDenied/Escalated"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass

        classes = audit_classes(ws)
        assert "subtask_failed" in classes, f"classes={classes}"
        assert not os.path.exists(os.path.join(ws, "docs/report.md"))

    def test_identical_cause_retry_refused(self, ws):
        """An identical-cause retry is refused (no blind retry, REC-2)."""
        from orchestrator.production import (
            ProductionDenied, ProductionEscalated, BoundedExecutor,
        )
        from orchestrator.production.planner import ObjectivePlanner

        delegation = make_delegation()
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=sr,
                             executor=lambda p: {"exit_code": 1,
                                                 "target": "agents/cto/output.txt"})
        try:
            ex.execute(plan, delegation=delegation)
        except (ProductionDenied, ProductionEscalated):
            pass

        flow = ex.last_flow
        assert flow is not None and flow._result.outcome == "RECOVERING"

        # Establish a diagnosed cause (first recovery attempt fails again).
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

    def test_empty_cause_retry_refused(self, ws):
        """Recovery without a diagnosed cause is refused (REC-2)."""
        from orchestrator.production import (
            ProductionDenied, ProductionEscalated, BoundedExecutor,
        )
        from orchestrator.production.planner import ObjectivePlanner

        delegation = make_delegation()
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=sr,
                             executor=lambda p: {"exit_code": 1,
                                                 "target": "agents/cto/output.txt"})
        try:
            ex.execute(plan, delegation=delegation)
        except (ProductionDenied, ProductionEscalated):
            pass

        flow = ex.last_flow
        assert flow is not None and flow._result.outcome == "RECOVERING"

        try:
            ex.recover(flow, cause="", failure_class="environment")
            assert False, "expected empty-cause retry to be refused"
        except ProductionDenied as e:
            assert "no blind retry" in str(e).lower()
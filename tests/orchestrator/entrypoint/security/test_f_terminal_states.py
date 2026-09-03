# Category F — TERMINAL STATES
#
# Prove the adapter's terminal status mapping is honest (fail-closed):
#   F1 no DENY becomes COMPLETE
#   F2 no ESCALATE becomes COMPLETE
#   F3 no verification failure becomes COMPLETE
#   F4 no exception is converted into false success
#   F5 structured output matches the actual terminal state
#
# The four terminal statuses of the envelope are COMPLETE / BLOCKED /
# ESCALATED / ERROR.

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

from .conftest import (  # noqa: E402
    make_delegation, make_subtask_result, make_provider, seed_state,
)

TERMINALS = ("COMPLETE", "BLOCKED", "ESCALATED", "ERROR")


class TestNoDenyBecomesComplete:
    def test_denied_delegation_never_completes(self, front_door, ws,
                                               subtask_runner,
                                               action_executor):
        """F1: a denied (revoked) delegation → BLOCKED, never COMPLETE."""
        from control.delegation import revoke
        delegation = revoke(make_delegation(), reason="test")
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.status != "COMPLETE"
        assert result.report is None

    def test_out_of_scope_never_completes(self, front_door, ws,
                                          subtask_runner, action_executor):
        """F1: out-of-scope target → BLOCKED, never COMPLETE."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("a",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("other-project/secret.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.status != "COMPLETE"


class TestNoEscalateBecomesComplete:
    def test_requires_approval_escalates_not_completes(self, front_door, ws,
                                                       subtask_runner,
                                                       action_executor):
        """F2: a delegation requiring approval (without a reference) →
        ESCALATED, never COMPLETE."""
        delegation = make_delegation(requires_approval=("destructive",))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="proceed",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "ESCALATED", \
            f"expected ESCALATED, got {result.status}: {result.errors}"
        assert result.status != "COMPLETE"
        assert result.report is None


class TestNoVerificationFailureBecomesComplete:
    def test_verification_failure_never_completes(self, front_door, ws,
                                                  subtask_runner):
        """F3: an executor returning exit_code 1 (expected 0) → verification
        fails → the run must NOT COMPLETE."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=lambda plan: {"exit_code": 1,
                                           "target": "agents/cto/output.txt"},
        )
        assert result.status != "COMPLETE", \
            "verification failure must not surface COMPLETE"
        assert result.status in ("BLOCKED", "ESCALATED", "ERROR")
        assert result.errors


class TestNoExceptionBecomesFalseSuccess:
    def test_unexpected_exception_is_error_not_complete(self, front_door, ws,
                                                        delegation,
                                                        subtask_runner):
        """F4: an unexpected provider crash → ERROR, never a fabricated
        COMPLETE."""
        from orchestrator.runtime import DelegationProvider

        class BrokenProvider(DelegationProvider):
            def current(self):
                raise RuntimeError("simulated provider crash")

        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=BrokenProvider(),
            subtask_runner=subtask_runner,
        )
        assert result.status == "ERROR", \
            f"expected ERROR, got {result.status}"
        assert result.status != "COMPLETE"
        assert result.errors
        assert "unexpected" in result.errors[0].lower()

    def test_execution_exception_never_completes(self, front_door, ws,
                                                 subtask_runner):
        """F4: an action executor that raises is never converted to
        COMPLETE (the runtime maps it to recovery/failure)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)

        def boom(plan):
            raise RuntimeError("simulated execution failure")

        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=boom,
        )
        assert result.status != "COMPLETE"
        assert result.status in ("BLOCKED", "ESCALATED", "ERROR")


class TestStructuredOutputMatchesTerminalState:
    def test_complete_output_is_consistent(self, front_door, ws, delegation,
                                           provider, subtask_runner,
                                           action_executor):
        """F5: COMPLETE envelope: status == COMPLETE, state.outcome == complete,
        report.outcome == COMPLETE, run_id set."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "COMPLETE"
        assert result.state is not None
        assert result.state["outcome"] == "complete"
        assert result.report is not None
        assert result.report["outcome"] == "COMPLETE"
        assert result.run_id is not None
        assert result.run_id == result.state["run_id"]

    def test_blocked_output_is_consistent(self, front_door, ws, subtask_runner,
                                          action_executor):
        """F5: BLOCKED envelope: status == BLOCKED, state.outcome == stopped
        (or None when no run started), report is None, errors present."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(None),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.report is None
        assert result.errors

    def test_error_output_is_consistent(self, front_door):
        """F5: ERROR envelope: status == ERROR, no state/report/run_id, errors
        present."""
        result = front_door.run_front_door({
            "objective": "",
            "scope": (),
            "delegation_id": "",
        })
        assert result.status == "ERROR"
        assert result.state is None
        assert result.report is None
        assert result.run_id is None
        assert result.errors
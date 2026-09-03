# E-18 — COMPLETE still requires verification
#
# Prove that the front door cannot reach COMPLETE without the verification
# gate passing inside ProductionRun. The verification gate is mandatory:
# reported outcome ≠ verified outcome. A run where the action executor
# returns a result that does not match the expected outcome (e.g., exit_code
# 1 vs expected 0) enters recovery and never surfaces COMPLETE.

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    COMPLETE,
    ESCALATED,
    ERROR,
    run_front_door,
    FrontDoorRequest,
)


class TestCompleteRequiresVerification:
    def test_verification_failure_prevents_complete(self, ws, subtask_runner):
        """An executor returning exit_code 1 (expected 0) → BLOCKED/ESCALATED,
        never COMPLETE."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        # Executor returns exit_code 1, plan expects exit_code 0 → mismatch.
        result = run_front_door(
            FrontDoorRequest(
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
        assert result.status != COMPLETE, "verification failure must not COMPLETE"
        # The flow enters recovery (RECOVERING) → Production layer maps to
        # either BLOCKED, ESCALATED, or ERROR — never COMPLETE.
        assert result.status in (BLOCKED, ESCALATED, ERROR)

    def test_verification_failure_recorded(self, ws, subtask_runner):
        """A verification failure is recorded in the flow result (state
        carries the error)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
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
        # The front door caught the failure; errors must be non-empty.
        assert result.errors, "verification failure should produce errors"
        assert result.status != COMPLETE

    def test_verification_gate_cannot_be_skipped(self, ws, subtask_runner):
        """Even with all gates ALLOW, if verification fails, the front door
        does not COMPLETE."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        # The executor always returns exit_code 1 (mismatch).
        result = run_front_door(
            FrontDoorRequest(
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
        # The front door must not return COMPLETE; it must either surface
        # the failure or the recovery path.
        assert result.status != COMPLETE, \
            "verification gate must not be bypassable"
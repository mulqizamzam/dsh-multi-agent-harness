# tests/orchestrator/execution/test_execution_engine.py — Runtime execution
# assurance scenarios (Phase 3 / Session C).
#
# Binds the existing verification + recovery controls to runtime behavior.
# A reported success is NOT a verified success (THREAT-016 / AUTH-INV-15).
# No unrestricted execution; no new privileges; no DSH modification.
#
# Scenarios:
#   - success + verification (COMPLETE only after verified outcome)
#   - false success (claim is not verification)
#   - expired delegation (denied at execution time)
#   - revoked delegation (denied at execution time)
#   - target mutation (out-of-scope / protected target denied)
#   - stale plan (THREAT-022)
#   - failed execution (classification)
#   - recovery (full lifecycle + restoration verification)
#   - retry limit (AUTH-INV-16 / REC-001)
#   - recovery privilege escalation attempt (REC-004 / THREAT-017)

import os
import pytest

from control.recovery import RecoveryRefused
from control.execution_gate import write_through

from orchestrator.execution import (
    ExecutionDenied,
    ExecutionRefused,
    VerificationRefused,
    ExecutionEngine,
    ExecutionOutcome,
)
from orchestrator.foundation import StateMachine

from .conftest import make_delegation, make_request


def _exec_machine(task_id="exec-001", delegation=None):
    """A StateMachine driven to EXECUTING."""
    sm = StateMachine(task_id)
    d = delegation or make_delegation(task_id=task_id)
    sm.transition("PLANNED", authority=d)
    sm.transition("DELEGATED", authority=d)
    sm.transition("EXECUTING", authority=d)
    return sm


# ===========================================================================
# 1. Success + verification → COMPLETE (AUTH-INV-15)
# ===========================================================================

class TestSuccessVerification:
    def test_verified_outcome_completes(self, ws, delegation, engine_factory):
        """A verified write reaches COMPLETE and the state machine ends there."""
        req = make_request(task_id="exec-success", delegation=delegation,
                           action="write", target="agents/cto/output.txt",
                           expected_outcome={"exit_code": 0,
                                             "target": "agents/cto/output.txt"})
        sm = _exec_machine("exec-success", delegation)
        eng = engine_factory(req, state_machine=sm, current_version=3)

        def executor(r):
            write_through("write", r.target, {"module": "ok"}, base=ws)
            return {"exit_code": 0, "target": "agents/cto/output.txt"}

        eng.validate()
        assert eng.recheck_authority() is True
        eng.execute(executor)
        # Actual outcome captured (not just an agent claim).
        assert eng.outcome is not None
        assert eng.outcome.observed == {"exit_code": 0,
                                        "target": "agents/cto/output.txt"}
        assert sm.current() == "COLLECTED"

        eng.add_evidence("test", "tests/test_x.py::test_case",
                         verifier="self:orchestrator")
        eng.add_evidence("build", "build/output.log",
                         verifier="self:orchestrator")

        result = eng.verification_result()
        assert result.verdict == "PASSED"
        assert eng.can_complete() is True
        eng.complete()
        assert sm.current() == "COMPLETE"
        assert os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_write_without_path_gate_base_still_gated(self, ws,
                                                      engine_factory):
        """Even when the delegation scope nominally covers the target, the
        path-aware execution gate refuses a protected-path write (no
        unrestricted execution)."""
        # Delegation scope COVERS state/registry/** so the authority gate
        # passes; the execution path gate is the enforcement that denies.
        d = make_delegation(
            task_id="exec-protected", id="delegation-exec-protected",
            scope_resources=("state/registry/**",))
        req = make_request(task_id="exec-protected", delegation=d,
                           action="write",
                           target="state/registry/delegations.json",
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        eng.validate()
        # The path gate (control.execution_gate) denies the protected path.
        with pytest.raises(ExecutionDenied, match="path gate|DENIED"):
            eng.recheck_authority()


# ===========================================================================
# 2. False success (claim is NOT verification — THREAT-016)
# ===========================================================================

class TestFalseSuccess:
    def test_claim_without_observed_never_completes(self, ws, delegation,
                                                    engine_factory):
        """An agent claim of SUCCEEDED without a captured actual outcome is
        NOT verified and cannot reach COMPLETE."""
        req = make_request(task_id="exec-false", delegation=delegation,
                           action="write", target="agents/cto/output.txt",
                           expected_outcome={"exit_code": 0})
        eng = engine_factory(req)
        eng.validate()
        eng.recheck_authority()
        # The agent "reports success" but the engine captured NO observed
        # outcome (the side-effect never landed).
        eng.record_agent_claim("SUCCEEDED")
        result = eng.verification_result()
        assert result.verdict == "UNVERIFIED"
        assert eng.can_complete() is False
        with pytest.raises(VerificationRefused):
            eng.complete()

    def test_observed_mismatch_fails_verification(self, ws, delegation,
                                                  engine_factory):
        """A captured actual outcome that differs from expected → FAILED
        (VERIFY-002) → recovery, never COMPLETE."""
        req = make_request(task_id="exec-mismatch", delegation=delegation,
                           action="write", target="agents/cto/output.txt",
                           expected_outcome={"exit_code": 0})
        eng = engine_factory(req)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            return {"exit_code": 1, "error": "build failed"}

        eng.execute(executor)
        result = eng.verification_result()
        assert result.verdict == "FAILED"
        assert eng.can_complete() is False


# ===========================================================================
# 3-4. Expired / revoked delegation denied at execution time
# ===========================================================================

class TestExpiredRevokedDelegation:
    def test_expired_delegation_denied(self, ws, engine_factory):
        """A delegation past its expires_at is DENIED (AUTH-INV-06)."""
        d = make_delegation(task_id="exec-exp", id="delegation-exec-exp",
                            expires_at="2020-01-01T00:00:00Z")
        req = make_request(task_id="exec-exp", delegation=d,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        with pytest.raises(ExecutionDenied, match="expired"):
            eng.validate()  # fail-closed at validation (and at recheck)
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))

    def test_revoked_delegation_denied(self, ws, engine_factory):
        """A delegation in the revocation list is DENIED (AUTH-INV-06)."""
        d = make_delegation(task_id="exec-rev", id="delegation-exec-rev")
        req = make_request(task_id="exec-rev", delegation=d,
                           action="write", target="agents/cto/x.txt",
                           revocation_list=("delegation-exec-rev",),
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        with pytest.raises(ExecutionDenied, match="revoked"):
            eng.recheck_authority()
        # nothing written
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))


# ===========================================================================
# 5. Target mutation (out-of-scope / protected target)
# ===========================================================================

class TestTargetMutation:
    def test_out_of_scope_target_denied(self, ws, engine_factory):
        """A target outside the delegation's scope resources is DENIED at
        execution time (AUTH-INV-11)."""
        d = make_delegation(task_id="exec-tgt",
                            id="delegation-exec-tgt",
                            scope_resources=("agents/**",))
        req = make_request(task_id="exec-tgt", delegation=d,
                           action="write",
                           target="state/registry/delegations.json",
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        # The target is outside the delegation's scope → DENY (fail-fast at
        # validation, fail-closed at execution time).
        with pytest.raises(ExecutionDenied, match="AUTH-INV-11"):
            eng.validate()
        with pytest.raises(ExecutionDenied):
            eng.recheck_authority()

    def test_target_drift_observed_by_verification(self, ws, delegation,
                                                   engine_factory):
        """The executor writes to a DIFFERENT in-scope target than the request;
        the captured outcome exposes the drift → verification FAILS."""
        req = make_request(task_id="exec-drift", delegation=delegation,
                           action="write", target="agents/cto/expected.txt",
                           expected_outcome={
                               "exit_code": 0,
                               "target": "agents/cto/expected.txt",
                           })
        eng = engine_factory(req)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            # Mutation: writes elsewhere within scope.
            write_through("write", "agents/cto/drifted.txt", {"v": 1}, base=ws)
            return {"exit_code": 0, "target": "agents/cto/drifted.txt"}

        eng.execute(executor)
        result = eng.verification_result()
        assert result.verdict == "FAILED"  # VERIFY-002 expected vs actual
        assert eng.can_complete() is False


# ===========================================================================
# 6. Stale plan refused (THREAT-022 / REC-005)
# ===========================================================================

class TestStalePlan:
    def test_stale_plan_refused_before_execution(self, ws, delegation,
                                                 engine_factory):
        """A request built against state version 5 is refused when the current
        version is 7 (plan is stale → THREAT-022)."""
        req = make_request(task_id="exec-stale", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True},
                           state_version=5)
        eng = engine_factory(req, current_version=7)
        eng.validate()
        with pytest.raises(ExecutionRefused, match="stale plan"):
            eng.execute(observed={"ok": True})

    def test_current_plan_executes(self, ws, delegation, engine_factory):
        """A request whose plan version matches the current version executes."""
        req = make_request(task_id="exec-current", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True},
                           state_version=5)
        eng = engine_factory(req, current_version=5)
        eng.validate()
        eng.recheck_authority()
        eng.execute(observed={"ok": True})
        assert eng.outcome.observed == {"ok": True}


# ===========================================================================
# 7. Failed execution → classification
# ===========================================================================

class TestFailedExecution:
    def test_executor_exception_classified(self, ws, delegation,
                                           engine_factory):
        """A raised OSError is classified environment and captured."""
        req = make_request(task_id="exec-fail", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise PermissionError("cannot write")

        eng.execute(executor)
        assert eng.failure_class == "environment"
        assert eng.outcome is not None
        assert eng.outcome.is_failed()
        assert "cannot write" in eng.outcome.error


# ===========================================================================
# 8. Recovery lifecycle (STOP→…→AUTH RE-CHECK→COMPLETE)
# ===========================================================================

class TestRecovery:
    def test_full_recovery_with_rollback_verification(self, ws, delegation,
                                                      engine_factory):
        """Full recovery: diagnose → rollback → verify restoration
        (independent) → replan → authority re-check → COMPLETE."""
        req = make_request(task_id="exec-rec", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True},
                           state_version=5)
        sm = _exec_machine("exec-rec", delegation)
        eng = engine_factory(req, state_machine=sm, current_version=5)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("disk full")

        eng.execute(executor)
        assert eng.failure_class == "environment"
        assert sm.current() == "EXECUTING"  # not yet recovered

        ctrl = eng.recover(
            cause="disk full",
            failure_class="environment",
            rollback=True,
            restoration_evidence="checksum abc123 matches backup",
            restoration_verifier="independent:ops",
            current_version=5,
        )
        assert ctrl.state == "COMPLETED"
        assert ctrl.record.restoration_verified is True
        assert ctrl.record.authority_checked is True
        assert ctrl.record.rollback_performed is True
        # Task machine: EXECUTING → RECOVERING → DELEGATED
        assert sm.current() == "DELEGATED"

    def test_recovery_rejects_self_verification(self, ws, delegation,
                                                engine_factory):
        """REC-003: restoration must be verified INDEPENDENTLY."""
        req = make_request(task_id="exec-rec2", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True}, state_version=5)
        eng = engine_factory(req, current_version=5)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("disk full")

        eng.execute(executor)
        with pytest.raises(RecoveryRefused, match="INDEPENDENTLY"):
            eng.recover(
                cause="disk full", failure_class="environment",
                rollback=True,
                restoration_evidence="checksum abc123",
                restoration_verifier="self:orchestrator",
                current_version=5,
            )


# ===========================================================================
# 9. Retry budget (AUTH-INV-16 / REC-001)
# ===========================================================================

class TestRetryLimit:
    def test_retry_requires_new_cause_and_respects_budget(self, ws, delegation,
                                                          engine_factory):
        """A retry with a NEW cause is allowed once; the cap (default 1 per
        cause) is enforced; identical cause is refused."""
        req = make_request(task_id="exec-retry", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True}, state_version=1,
                           max_attempts=1)
        eng = engine_factory(req, current_version=1)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("boom")

        eng.execute(executor)
        ctrl = eng.begin_recovery("cause A", failure_class="environment")
        assert ctrl.state == "DIAGNOSED"  # STOP→PRESERVE→DIAGNOSED

        # Identical cause → refused (no blind retry).
        with pytest.raises(RecoveryRefused, match="identical"):
            eng.request_retry("cause A")
        # New cause → one retry.
        assert eng.request_retry("cause B") == 1
        # Budget exhausted → refused.
        with pytest.raises(RecoveryRefused, match="cap"):
            eng.request_retry("cause C")

    def test_retry_without_recovery_refused(self, ws, delegation,
                                            engine_factory):
        """request_retry without an active recovery lifecycle is refused."""
        req = make_request(task_id="exec-retry2", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True})
        eng = engine_factory(req)
        with pytest.raises(ExecutionRefused, match="active recovery"):
            eng.request_retry("cause X")


# ===========================================================================
# 10. Recovery privilege escalation attempt (REC-004 / THREAT-017)
# ===========================================================================

class TestRecoveryPrivilegeEscalation:
    def test_recovery_cannot_escalate_action(self, ws, delegation,
                                             engine_factory):
        """Recovery attempting an action outside the ORIGINAL authority is
        refused (REC-004 / THREAT-017)."""
        req = make_request(task_id="exec-esc", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True}, state_version=1)
        eng = engine_factory(req, current_version=1)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("boom")

        eng.execute(executor)
        # Attempt to recover with a financial_transaction action — outside the
        # original write delegation.
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            eng.recover(
                cause="boom", failure_class="environment",
                attempt_action="financial_transaction",
                attempt_target="agents/cto/x.txt",
                current_version=1,
            )

    def test_recovery_cannot_escalate_target(self, ws, delegation,
                                             engine_factory):
        """Recovery attempting a target outside the ORIGINAL scope is
        refused."""
        req = make_request(task_id="exec-esc2", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True}, state_version=1)
        eng = engine_factory(req, current_version=1)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("boom")

        eng.execute(executor)
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            eng.recover(
                cause="boom", failure_class="environment",
                attempt_action="write",
                attempt_target="infra/prod/servers.txt",  # outside scope
                current_version=1,
            )

    def test_recovery_within_original_authority_allowed(self, ws, delegation,
                                                        engine_factory):
        """A recovery fully within the original authority completes."""
        req = make_request(task_id="exec-esc3", delegation=delegation,
                           action="write", target="agents/cto/x.txt",
                           expected_outcome={"ok": True}, state_version=1)
        eng = engine_factory(req, current_version=1)
        eng.validate()
        eng.recheck_authority()

        def executor(r):
            raise OSError("boom")

        eng.execute(executor)
        ctrl = eng.recover(
            cause="boom", failure_class="environment",
            attempt_action="write",
            attempt_target="agents/cto/x.txt",
            current_version=1,
        )
        assert ctrl.state == "COMPLETED"

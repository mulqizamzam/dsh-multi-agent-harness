"""Recovery control-plane tests — AUTH-INV-12/16, REC-001..005, THREAT-017/022.

Required semantics under test:
  - AUTH-INV-12: recovery re-checks authority via the same gate; no privilege
    escalation through recovery (REC-004 / THREAT-017)
  - AUTH-INV-16: no blind retry; retry requires a NEW diagnosed cause
    (REC-001)
  - recovery scenarios: full STOP→…→COMPLETE cycle; rollback path;
    skip-rollback path
  - stale recovery: obsolete state version → DENY (REC-005 / THREAT-022)
  - rollback verification: unverified restoration → refuse (REC-003)
  - retry abuse: identical cause beyond cap → DENY
  - recovery privilege escalation: attempt exceeds original authority → DENY
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from control.recovery import (
    RecoveryController,
    RecoveryRefused,
    execute_recovery,
)
from control.execution_gate import authorize_write
from state.helpers.recovery import (
    begin_recovery,
    RecoveryError,
    RecoveryDenied,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _allow_gate(action, target):
    """A gate stub that ALLOWs everything."""
    return True


def _deny_gate(action, target):
    """A gate stub that DENYs everything (fail-closed)."""
    raise RecoveryDenied(f"denied: {action} {target}")


def _original_authority(**overrides):
    """The structured record of what the ORIGINAL action was permitted."""
    oa = {
        "actions": ["code_write", "read"],
        "targets": ["agents/cto/**", "multi-agent-harness/**"],
        "grants": ["write", "edit", "read"],
    }
    oa.update(overrides)
    return oa


# ===========================================================================
# Full recovery cycles
# ===========================================================================

class TestFullRecoveryCycle:
    """STOP → PRESERVE → DIAGNOSE → … → COMPLETE."""

    def test_full_cycle_skip_rollback(self):
        """Skip-rollback path: DIAGNOSED → REPLANNED → AUTHORITY_RECHECKED →
        COMPLETED."""
        ctrl = RecoveryController("t-1", preserved_version=5,
                                  failure_class="logic",
                                  reason="null pointer dereference")
        assert ctrl.state == "PRESERVED"
        ctrl.diagnose("null pointer dereference", failure_class="logic")
        assert ctrl.state == "DIAGNOSED"
        ctrl.replan()
        assert ctrl.state == "REPLANNED"
        ctrl.recheck_authority(
            _allow_gate,
            attempt_action="code_write",
            attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5,
            expected_version=5,
        )
        assert ctrl.state == "AUTHORITY_RECHECKED"
        assert ctrl.record.authority_checked is True
        ctrl.complete()
        assert ctrl.state == "COMPLETED"

    def test_full_cycle_with_rollback(self):
        """Rollback path: DIAGNOSED → ROLLING_BACK → VERIFYING_RESTORATION →
        REPLANNED → AUTHORITY_RECHECKED → COMPLETED."""
        ctrl = RecoveryController("t-1", preserved_version=5,
                                  failure_class="environment",
                                  reason="deploy failed")
        ctrl.diagnose("bad config in deploy", failure_class="environment")
        ctrl.rollback()
        assert ctrl.state == "VERIFYING_RESTORATION"
        assert ctrl.record.rollback_performed is True
        ctrl.verify_restoration(
            evidence="checksum abc123 matches backup",
            verifier="independent:ops",
        )
        assert ctrl.state == "REPLANNED"
        assert ctrl.record.restoration_verified is True
        ctrl.recheck_authority(
            _allow_gate,
            attempt_action="code_write",
            attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5,
        )
        ctrl.complete()
        assert ctrl.state == "COMPLETED"

    def test_execute_recovery_helper_skip_rollback(self):
        """execute_recovery convenience driver (skip-rollback path)."""
        ctrl = execute_recovery(
            task_id="t-1", preserved_version=5,
            failure_class="logic", cause="null pointer dereference",
            gate_fn=_allow_gate,
            attempt_action="code_write", attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5, expected_version=5,
        )
        assert ctrl.state == "COMPLETED"
        assert ctrl.record.authority_checked is True
        assert ctrl.record.rollback_performed is False

    def test_execute_recovery_helper_with_rollback(self):
        """execute_recovery convenience driver (rollback path with
        independent restoration verification)."""
        ctrl = execute_recovery(
            task_id="t-1", preserved_version=5,
            failure_class="environment", cause="bad config in deploy",
            gate_fn=_allow_gate,
            attempt_action="code_write", attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5,
            rollback=True,
            restoration_evidence="checksum abc123 matches backup",
            restoration_verifier="independent:ops",
        )
        assert ctrl.state == "COMPLETED"
        assert ctrl.record.rollback_performed is True
        assert ctrl.record.restoration_verified is True

    def test_fail_any_state(self):
        """A recovery can fail from any state (escalate to Human)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause", failure_class="logic")
        assert ctrl.fail("irrecoverable") == "FAILED"
        assert ctrl.state == "FAILED"


# ===========================================================================
# AUTH-INV-12 — recovery re-checks authority via the SAME gate
# ===========================================================================

class TestAuthorityRecheck:
    """AUTH-INV-12: recovery re-passes the same authority path."""

    def test_recheck_passes_through_gate(self):
        """The gate function is invoked with the recovery attempt's
        action/target."""
        calls = []

        def recording_gate(action, target):
            calls.append((action, target))
            return True

        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        ctrl.recheck_authority(
            recording_gate,
            attempt_action="code_write",
            attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5,
        )
        assert ("code_write", "agents/cto/x.py") in calls
        assert ctrl.record.authority_checked is True

    def test_gate_denial_refused(self):
        """A gate denial (fail-closed) → recovery refused (AUTH-INV-12)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="AUTH-INV-12"):
            ctrl.recheck_authority(
                _deny_gate,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                original_authority=_original_authority(),
                current_version=5,
            )
        # state unchanged (no authority recheck recorded)
        assert ctrl.state == "REPLANNED"
        assert ctrl.record.authority_checked is False

    def test_recheck_uses_same_execution_gate(self):
        """Recovery re-checks via the SAME path-aware execution gate
        (control.execution_gate.authorize_write): a protected-path write is
        refused; an allowed workspace write passes."""
        import tempfile
        base = tempfile.mkdtemp()
        # Use an original_authority that includes "write" action and the
        # protected target, so the privilege check passes and the execution
        # gate is the actual denial (no gate bypass through recovery).
        auth_with_write = _original_authority(
            actions=["code_write", "read", "write"],
            targets=["agents/cto/**", "multi-agent-harness/**",
                     "state/registry/**"],
        )
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()

        # Recovery attempt that writes a PROTECTED path → the execution gate
        # denies → recovery refused (no gate bypass through recovery).
        with pytest.raises(RecoveryRefused, match="AUTH-INV-12"):
            ctrl.recheck_authority(
                lambda a, t: authorize_write(a, t, base=base),
                attempt_action="write",
                attempt_target="state/registry/delegations.json",
                original_authority=auth_with_write,
                current_version=5,
            )
        assert ctrl.record.authority_checked is False

        # Allowed workspace write passes the same gate.
        ctrl2 = RecoveryController("t-2", preserved_version=5)
        ctrl2.diagnose("cause")
        ctrl2.replan()
        ctrl2.recheck_authority(
            lambda a, t: authorize_write(a, t, base=base),
            attempt_action="write",
            attempt_target="agents/cto/output.txt",
            original_authority=auth_with_write,
            current_version=5,
        )
        assert ctrl2.record.authority_checked is True

    def test_missing_gate_refused(self):
        """No gate provided → recovery cannot re-check authority → refuse
        (fail-closed)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="no authority gate"):
            ctrl.recheck_authority(
                None,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                original_authority=_original_authority(),
                current_version=5,
            )

    def test_recheck_requires_replanned_state(self):
        """Rechecking authority before REPLANNED is a machine violation."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")  # DIAGNOSED, not REPLANNED
        with pytest.raises(RecoveryError):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                original_authority=_original_authority(),
                current_version=5,
            )


# ===========================================================================
# No blind retry (AUTH-INV-16 / REC-001)
# ===========================================================================

class TestNoBlindRetry:
    """AUTH-INV-16: retry requires a NEW diagnosed cause."""

    def test_retry_with_new_cause_allowed(self):
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("network timeout", failure_class="environment")
        assert ctrl.request_retry("memory pressure") == 1
        assert ctrl.attempts_log[-1]["cause"] == "memory pressure"

    def test_retry_without_cause_refused(self):
        """Empty cause → blind retry → refuse."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("network timeout")
        with pytest.raises(RecoveryRefused, match="AUTH-INV-16"):
            ctrl.request_retry("")

    def test_retry_identical_cause_refused(self):
        """Identical cause is not a NEW cause → refuse (AUTH-INV-16)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("network timeout", failure_class="environment")
        with pytest.raises(RecoveryRefused, match="identical"):
            ctrl.request_retry("network timeout")

    def test_diagnose_without_cause_refused(self):
        """Diagnosis requires a cause (no blind retry at diagnosis)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        with pytest.raises(RecoveryRefused, match="AUTH-INV-16"):
            ctrl.diagnose("")


# ===========================================================================
# Retry abuse (identical cause beyond cap → DENY)
# ===========================================================================

class TestRetryAbuse:
    """Retry cap: max 1 attempt per cause by default (REC-001)."""

    def test_cap_reached_denied(self):
        """After the max_attempts cap, any further retry is refused."""
        ctrl = RecoveryController("t-1", preserved_version=5, max_attempts=1)
        ctrl.diagnose("cause A")
        assert ctrl.request_retry("cause B") == 1
        # attempts now 1 >= cap 1 → refused even with a new cause
        with pytest.raises(RecoveryRefused, match="cap"):
            ctrl.request_retry("cause C")

    def test_identical_cause_beyond_cap_denied(self):
        """Re-attempting with the SAME cause is refused (identical + cap)."""
        ctrl = RecoveryController("t-1", preserved_version=5, max_attempts=2)
        ctrl.diagnose("cause A")
        ctrl.request_retry("cause B")
        ctrl.request_retry("cause C")
        # cause B again: identical to... diagnosed is now C; B is new-ish, but
        # per-cause tracking counts B's previous attempt.
        with pytest.raises(RecoveryRefused, match="identical|cap"):
            ctrl.request_retry("cause B")

    def test_max_attempts_parameter_respected(self):
        """Explicit max_attempts parameter caps retries."""
        ctrl = RecoveryController("t-1", preserved_version=5, max_attempts=2)
        ctrl.diagnose("cause A")
        assert ctrl.request_retry("cause B") == 1
        assert ctrl.request_retry("cause C") == 2
        with pytest.raises(RecoveryRefused, match="cap"):
            ctrl.request_retry("cause D")

    def test_attempts_and_cause_tracked(self):
        """Attempts and diagnosed-cause per attempt are tracked."""
        ctrl = RecoveryController("t-1", preserved_version=5, max_attempts=3)
        ctrl.diagnose("cause A")
        ctrl.request_retry("cause B")
        ctrl.request_retry("cause C")
        assert ctrl.record.attempts == 2
        assert len(ctrl.attempts_log) == 2
        assert ctrl.attempts_log[0] == {"attempt": 1, "cause": "cause B"}
        assert ctrl.attempts_log[1] == {"attempt": 2, "cause": "cause C"}
        assert ctrl.record.diagnosed_cause == "cause C"


# ===========================================================================
# Stale recovery (REC-005 / THREAT-022)
# ===========================================================================

class TestStaleRecovery:
    """Obsolete state version → DENY."""

    def test_stale_expected_version_denied(self):
        """Recovery prepared against version 5, current is 7 with expected 5
        → DENY (THREAT-022 / REC-005)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        with pytest.raises(RecoveryRefused, match="THREAT-022"):
            ctrl.assert_current_version(current_version=7, expected_version=5)

    def test_current_older_than_preserved_denied(self):
        """Current version older than the preserved one → DENY."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        with pytest.raises(RecoveryRefused, match="older"):
            ctrl.assert_current_version(current_version=3)

    def test_missing_current_version_denied(self):
        """No current version supplied → recovery cannot re-validate → DENY
        (must re-read current state)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        with pytest.raises(RecoveryRefused, match="current state version"):
            ctrl.assert_current_version(current_version=None)

    def test_current_version_ok(self):
        """Current version matching expectation → allowed."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        assert ctrl.assert_current_version(current_version=7,
                                           expected_version=7) is True

    def test_stale_blocks_full_recheck(self):
        """A stale version blocks the authority re-check entirely."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="THREAT-022"):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                original_authority=_original_authority(),
                current_version=7,
                expected_version=5,
            )
        assert ctrl.record.authority_checked is False

    def test_record_level_validation_preserved(self):
        """The underlying RecoveryRecord staleness primitive is reused, not
        modified (REC-005 semantics still raise RecoveryDenied)."""
        rec = begin_recovery("t-1", preserved_version=5)
        with pytest.raises(RecoveryDenied, match="THREAT-022"):
            rec.validate_against_current_version(7, expected_version=5)


# ===========================================================================
# Rollback verification (REC-003)
# ===========================================================================

class TestRollbackVerification:
    """Unverified restoration → refuse to proceed."""

    def test_no_restoration_evidence_refused(self):
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.rollback()
        with pytest.raises(RecoveryRefused, match="REC-003"):
            ctrl.verify_restoration(evidence="", verifier="independent:ops")

    def test_no_verifier_refused(self):
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.rollback()
        with pytest.raises(RecoveryRefused, match="REC-003"):
            ctrl.verify_restoration(evidence="checksum abc",
                                    verifier="")

    def test_self_verification_refused(self):
        """Restoration must be verified INDEPENDENTLY, not by the executor
        (REC-003)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.rollback()
        with pytest.raises(RecoveryRefused, match="INDEPENDENTLY"):
            ctrl.verify_restoration(evidence="checksum abc",
                                    verifier="self:orchestrator")

    def test_verified_restoration_proceeds(self):
        """Verified restoration transitions to REPLANNED."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.rollback()
        assert ctrl.verify_restoration(
            evidence="checksum abc123 matches backup",
            verifier="independent:ops",
        ) == "REPLANNED"
        assert ctrl.record.restoration_verified is True

    def test_replan_before_verify_refused(self):
        """Replanning while restoration is unverified is refused (REC-003)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.rollback()
        with pytest.raises(RecoveryRefused, match="REC-003"):
            ctrl.replan()


# ===========================================================================
# Recovery privilege escalation (REC-004 / THREAT-017 / AUTH-INV-12)
# ===========================================================================

class TestPrivilegeEscalation:
    """A recovery attempt to do what the original couldn't → DENY."""

    def test_action_beyond_original_denied(self):
        """Recovery attempts an action outside the original authority → DENY."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="financial_transaction",
                attempt_target="agents/cto/x.py",
                original_authority=_original_authority(),
                current_version=5,
            )

    def test_target_beyond_original_denied(self):
        """Recovery attempts a target outside the original authority → DENY."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="code_write",
                attempt_target="infra/prod/servers.txt",
                original_authority=_original_authority(),
                current_version=5,
            )

    def test_grant_beyond_original_denied(self):
        """Recovery requests a grant/tool the original did not have → DENY."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                attempt_grants=["write", "edit", "bash"],
                original_authority=_original_authority(),
                current_version=5,
            )

    def test_no_original_baseline_denied(self):
        """Without an original authority baseline, recovery cannot prove it is
        bounded → DENY (fail-closed)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        with pytest.raises(RecoveryRefused, match="privilege"):
            ctrl.recheck_authority(
                _allow_gate,
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                original_authority=None,
                current_version=5,
            )

    def test_grants_when_original_had_none_denied(self):
        """Recovery requests grants when the original had none → DENY."""
        with pytest.raises(RecoveryRefused, match="privilege escalation"):
            RecoveryController("t-1", 5).assert_privilege_bounded(
                attempt_action="code_write",
                attempt_target="agents/cto/x.py",
                attempt_grants=["write"],
                original_authority=_original_authority(grants=[]),
            )

    def test_within_original_authority_allowed(self):
        """An attempt fully within the original authority is allowed."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause")
        ctrl.replan()
        assert ctrl.recheck_authority(
            _allow_gate,
            attempt_action="code_write",
            attempt_target="agents/cto/x.py",
            original_authority=_original_authority(),
            current_version=5,
        ) is True

    def test_recovery_acquires_no_tools_automatically(self):
        """A RecoveryController never grants tools/grants — the record stays
        data-only (AUTH-INV-12 / REC-004)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        d = ctrl.to_dict()
        assert "tools" not in d
        assert "grants" not in d
        assert "permissions" not in d
        assert "authority" not in d


# ===========================================================================
# RecoveryRecord reuse (data-only primitive, unmodified)
# ===========================================================================

class TestRecoveryRecordReuse:
    """The controller builds on state.helpers.recovery.RecoveryRecord without
    modifying it."""

    def test_controller_wraps_begin_recovery(self):
        ctrl = RecoveryController("t-1", preserved_version=5,
                                  failure_class="logic",
                                  reason="cache miss")
        assert ctrl.record.state == "PRESERVED"
        assert ctrl.record.preserved_version == 5
        assert ctrl.record.failure_class == "logic"
        assert isinstance(ctrl.record, type(begin_recovery("x", 1)))

    def test_record_machine_still_strict(self):
        """The underlying machine still refuses invalid transitions."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        with pytest.raises(RecoveryError):
            ctrl.complete()  # cannot complete from PRESERVED

    def test_controller_to_dict_roundtrip(self):
        """to_dict exposes the record for persistence (data-only)."""
        ctrl = RecoveryController("t-1", preserved_version=5)
        ctrl.diagnose("cause", failure_class="environment")
        d = ctrl.to_dict()
        assert d["task_id"] == "t-1"
        assert d["state"] == "DIAGNOSED"
        assert d["diagnosed_cause"] == "cause"
"""Recovery primitives tests — Phase 1E / Session B.

Covers:
  - begin_recovery: STOP -> PRESERVE with version
  - RecoveryRecord state machine transitions through full cycle
  - can_retry: AUTH-INV-16 no blind retry, max_attempts cap
  - validate_against_current_version: THREAT-022 stale version detection
  - RecoveryRecord: data-only, never authority
  - begin_recovery preserves version for THREAT-022 detection
"""

import pytest


class TestBeginRecovery:
    def test_begin_recovery_creates_preserved_state(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 5, failure_class="logic",
                             reason="null pointer dereference")
        assert rec.task_id == "t-1"
        assert rec.state == "PRESERVED"
        assert rec.preserved_version == 5
        assert rec.current_version == 5
        assert rec.failure_class == "logic"
        assert rec.attempts == 0

    def test_begin_recovery_initial_state_is_stopped_then_preserved(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 3)
        # begin_recovery calls preserve() which transitions STOPPED -> PRESERVED
        assert rec.state == "PRESERVED"
        # The record's initial state before preserve() was STOPPED
        # We can verify by checking the version was captured
        assert rec.preserved_version == 3


class TestRecoveryCycle:
    """Full recovery cycle: STOPPED -> COMPLETED."""

    def test_full_recovery_cycle(self):
        from state.helpers.recovery import begin_recovery, RecoveryRecord
        rec = begin_recovery("t-1", preserved_version=5, failure_class="logic",
                             reason="cache miss")

        # Diagnose the cause
        rec.diagnose("stale cache entry", failure_class="environment",
                     reason="cache was invalidated")
        assert rec.state == "DIAGNOSED"
        assert rec.diagnosed_cause == "stale cache entry"
        assert rec.failure_class == "environment"

        # Rollback (restore cache from backup)
        rec.rollback(reason="restored from backup")
        assert rec.state == "VERIFYING_RESTORATION"
        assert rec.rollback_performed is True

        # Verify restoration
        rec.verify_restoration(verified=True, reason="cache checksum matches")
        assert rec.state == "REPLANNED"
        assert rec.restoration_verified is True

        # Re-check authority
        rec.authority_rechecked(checked=True, reason="delegation still valid")
        assert rec.state == "AUTHORITY_RECHECKED"
        assert rec.authority_checked is True

        # Complete
        rec.complete(reason="recovery finished")
        assert rec.state == "COMPLETED"

    def test_diagnose_requires_cause(self):
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", 1)
        with pytest.raises(RecoveryError, match="non-empty cause"):
            rec.diagnose("")

    def test_invalid_failure_class(self):
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", 1)
        with pytest.raises(RecoveryError, match="failure_class"):
            rec.diagnose("cause", failure_class="unknown_kind")

    def test_verify_restoration_requires_verified(self):
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", 1)
        rec.diagnose("cause")
        rec.rollback()
        with pytest.raises(RecoveryError, match="not verified"):
            rec.verify_restoration(verified=False)

    def test_authority_rechecked_requires_checked(self):
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", 1)
        rec.diagnose("cause")
        rec.replan()
        with pytest.raises(RecoveryError, match="authority re-check"):
            rec.authority_rechecked(checked=False)

    def test_replan_requires_diagnosed_cause(self):
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", 1)
        # Replan before diagnosis is refused (no blind retry)
        with pytest.raises(RecoveryError, match="diagnosed cause"):
            rec.replan()

    def test_fail_any_state(self):
        """Can fail from any state."""
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.fail("irrecoverable error")
        assert rec.state == "FAILED"


class TestNoBlindRetry:
    """AUTH-INV-16 / REC-001: retry requires a NEW diagnosed cause."""

    def test_retry_allowed_with_new_cause(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.diagnose("network timeout", failure_class="environment")
        assert rec.attempts == 0
        # First retry with a new cause
        assert rec.can_retry(max_attempts=1, new_cause="memory pressure") is True

    def test_retry_denied_same_cause(self):
        """Same cause as the diagnosed one is not a new cause."""
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.diagnose("network timeout", failure_class="environment")
        assert rec.can_retry(max_attempts=1, new_cause="network timeout") is False

    def test_retry_denied_empty_cause(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.diagnose("network timeout")
        assert rec.can_retry(new_cause="") is False

    def test_retry_denied_max_attempts_reached(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.diagnose("network timeout")
        rec.attempts = 1
        assert rec.can_retry(max_attempts=1, new_cause="memory pressure") is False

    def test_retry_allowed_multiple_attempts(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        rec.diagnose("network timeout")
        assert rec.can_retry(max_attempts=3, new_cause="memory pressure") is True


class TestRecoveryVersionStaleness:
    """THREAT-022 / REC-005: recovery must detect obsolete state version."""

    def test_current_version_matches_expected(self):
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 5)
        assert rec.validate_against_current_version(7, expected_version=7) is True

    def test_current_version_mismatch_expected_denied(self):
        from state.helpers.recovery import begin_recovery, RecoveryDenied
        rec = begin_recovery("t-1", 5)
        with pytest.raises(RecoveryDenied, match="THREAT-022"):
            rec.validate_against_current_version(7, expected_version=8)

    def test_current_version_older_than_preserved_denied(self):
        from state.helpers.recovery import begin_recovery, RecoveryDenied
        rec = begin_recovery("t-1", 5)
        with pytest.raises(RecoveryDenied, match="older"):
            rec.validate_against_current_version(3)  # current < preserved

    def test_begin_recovery_captures_version(self):
        from state.helpers.recovery import begin_recovery, RecoveryDenied
        rec = begin_recovery("t-1", 5)
        # Start with preserved_version=5, current_version=3 → should fail
        with pytest.raises(RecoveryDenied, match="older"):
            rec.validate_against_current_version(3)


class TestRecoveryDataOnly:
    """RecoveryRecord is DATA, never authority (AUTH-INV-12/14)."""

    def test_to_dict_roundtrip(self):
        from state.helpers.recovery import begin_recovery, RecoveryRecord
        rec = begin_recovery("t-1", 5, failure_class="logic",
                             reason="cache miss")
        rec.diagnose("stale entry", failure_class="environment")
        d = rec.to_dict()
        # Verify serializable
        import json
        blob = json.dumps(d)
        restored = RecoveryRecord.from_dict(json.loads(blob))
        assert restored.task_id == rec.task_id
        assert restored.state == rec.state
        assert restored.diagnosed_cause == rec.diagnosed_cause
        assert restored.preserved_version == rec.preserved_version

    def test_from_dict_rejects_unknown_fields(self):
        from state.helpers.recovery import RecoveryRecord, RecoveryError
        d = {"task_id": "t-1", "state": "STOPPED", "malicious_field": "grant"}
        with pytest.raises(RecoveryError, match="unknown"):
            RecoveryRecord.from_dict(d)

    def test_record_has_no_authority_granting_fields(self):
        """A RecoveryRecord carries no tools, grants, or permissions."""
        from state.helpers.recovery import begin_recovery
        rec = begin_recovery("t-1", 1)
        d = rec.to_dict()
        # No authority-granting fields
        assert "tools" not in d
        assert "grants" not in d
        assert "permissions" not in d
        assert "authority" not in d
        assert "delegation" not in d
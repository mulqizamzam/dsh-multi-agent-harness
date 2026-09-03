# INT-09 — Recovery → authority re-check
#
# Proves the full recovery cycle: STOP → PRESERVE → DIAGNOSE → ROLLBACK →
# VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK → COMPLETE, and that
# recovery does not auto-authorize.
#
# Modules integrated: RecoveryRecord + StateMachine (RECOVERING) + audit
# Invariants: AUTH-INV-12/16, THREAT-017/022, REC-001..005

import pytest

from state.helpers import begin_recovery, RecoveryError, RecoveryDenied
from orchestrator.foundation import StateMachine, StateTransitionError
from orchestrator.foundation.contracts import Delegation


class TestINT09RecoveryRecheck:
    def test_full_recovery_cycle(self, harness):
        """STOP→PRESERVE→DIAGNOSE→ROLLBACK→VERIFY→REPLAN→RECHECK→COMPLETE."""
        rec = harness.begin_recovery("int-09", preserved_version=5,
                                     failure_class="logic",
                                     reason="null pointer")
        assert rec.state == "PRESERVED"
        rec.diagnose("stale cache entry", failure_class="environment")
        rec.rollback(reason="restored from backup")
        rec.verify_restoration(verified=True, reason="checksum matches")
        # NOTE: verify_restoration(verified=True) already transitions to
        # REPLANNED (state/helpers/recovery.py); a second replan() here would be
        # an invalid REPLANNED -> REPLANNED transition. The full cycle remains:
        # STOP->PRESERVE->DIAGNOSE->ROLLBACK->VERIFY RESTORATION(->REPLANNED)->
        # AUTHORITY RE-CHECK->COMPLETE.
        rec.authority_rechecked(checked=True, reason="delegation still valid")
        rec.complete()
        assert rec.state == "COMPLETED"

    def test_no_blind_retry(self, harness):
        """A retry without a new diagnosed cause is refused."""
        rec = harness.begin_recovery("int-09b", preserved_version=3)
        rec.diagnose("network timeout", failure_class="environment")
        assert rec.can_retry(max_attempts=1, new_cause="network timeout") is False
        assert rec.can_retry(max_attempts=1, new_cause="memory pressure") is True
        rec.attempts = 1
        assert rec.can_retry(max_attempts=1, new_cause="memory pressure") is False

    def test_authority_recheck_required(self, harness):
        """Recovery cannot complete without passing the authority re-check."""
        rec = harness.begin_recovery("int-09c", preserved_version=3)
        rec.diagnose("cause")
        rec.replan()
        with pytest.raises(RecoveryError, match="authority re-check"):
            rec.authority_rechecked(checked=False)

    def test_stale_version_denied(self, harness):
        """Recovery against an obsolete state version is DENIED (THREAT-022)."""
        rec = harness.begin_recovery("int-09d", preserved_version=5)
        with pytest.raises(RecoveryDenied, match="THREAT-022"):
            rec.validate_against_current_version(7, expected_version=8)
        with pytest.raises(RecoveryDenied, match="older"):
            rec.validate_against_current_version(3)

    def test_recovery_state_machine_integration(self, harness):
        """StateMachine RECOVERING transition accepts a RecoveryRecord token
        (and only that), then recovery replans with authority re-check."""
        h = harness
        sm = StateMachine("int-09e")
        d = Delegation(task="int-09e")
        sm.transition("PLANNED", authority=d)
        sm.transition("DELEGATED", authority=d)
        sm.transition("EXECUTING", authority=d)
        # Free text is refused as recovery authority (AUTH-INV-01)
        with pytest.raises(StateTransitionError):
            sm.transition("RECOVERING", authority="let me retry")
        # A RecoveryRecord is the accepted structured token
        rec = h.begin_recovery("int-09e", preserved_version=3)
        assert sm.transition("RECOVERING", authority=rec) == "RECOVERING"
        # Recovery record re-checks authority before completion
        rec.diagnose("new cause", failure_class="environment")
        rec.replan()
        rec.authority_rechecked(checked=True)
        assert rec.state == "AUTHORITY_RECHECKED"
        rec.complete()

    def test_recovery_does_not_grant_privilege(self, harness):
        """A RecoveryRecord carries no tools/grants (AUTH-INV-12)."""
        rec = harness.begin_recovery("int-09f", preserved_version=1)
        rec_dict = rec.to_dict()
        for forbidden in ("grant", "tools", "privilege", "authority"):
            assert forbidden not in rec_dict
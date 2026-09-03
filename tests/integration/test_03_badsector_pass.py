# INT-03 — BadSector PASS without authority
#
# Proves that a BadSector PASS (with provenance) clears the review stage ONLY,
# and the authority gate still DENYs without a valid delegation.
#
# Modules integrated: BadSectorReviewGate + AuthorityGate + reference + audit
# Invariants: AUTH-INV-09, INV-03, THREAT-014

import pytest


class TestINT03BadSectorPass:
    def test_pass_with_provenance_clears_review_only(self, harness):
        """A BadSector PASS with review_id + input_hash clears review."""
        dec = harness.evaluate_gate("badsector_review", {
            "review": {"verdict": "PASS", "review_id": "r-1", "input_hash": "abc"},
            "action": "deploy", "risk": "HIGH",
        })
        assert dec.decision == "ALLOW"
        assert "review cleared" in dec.reason

    def test_pass_without_provenance_denied(self, harness):
        """A PASS without provenance is DENIED (THREAT-014)."""
        dec = harness.evaluate_gate("badsector_review", {
            "review": {"verdict": "PASS"},  # no review_id, no input_hash
            "action": "deploy", "risk": "HIGH",
        })
        assert dec.decision == "DENY"
        assert "provenance" in dec.reason

    def test_authority_still_denied_with_pass(self, harness):
        """Even with a valid PASS, authority gate DENYs without delegation."""
        # Review gate clears
        review_dec = harness.evaluate_gate("badsector_review", {
            "review": {"verdict": "PASS", "review_id": "r-2", "input_hash": "def"},
            "action": "write", "risk": "HIGH",
        })
        assert review_dec.decision == "ALLOW"
        # Authority gate: no delegation
        auth_dec = harness.evaluate_gate("authority", {
            "action": "write", "target": "agents/cto/x.txt"})
        assert auth_dec.decision == "DENY"

    def test_reference_pass_is_never_authority(self, harness):
        """The reference gate's badsector_pass_is_authority always returns False."""
        from control_plane import badsector_pass_is_authority
        assert badsector_pass_is_authority({"verdict": "PASS"},
                                           harness.build_delegation_dict()) is False

    def test_preserved_verdict_rework_denied(self, harness):
        """REWORK verdict does not clear review."""
        dec = harness.evaluate_gate("badsector_review", {
            "review": {"verdict": "REWORK", "review_id": "r-3", "input_hash": "ghi"},
            "action": "write", "risk": "HIGH",
        })
        assert dec.decision == "DENY"

    def test_mandatory_review_skipped_denied(self, harness):
        """A mandatory review (HIGH risk) that is skipped is DENIED (THREAT-015)."""
        dec = harness.evaluate_gate("badsector_review", {
            "risk": "HIGH", "action": "deploy",
        })
        assert dec.decision == "DENY"
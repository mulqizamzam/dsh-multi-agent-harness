"""BadSector review gate tests — AUTH-INV-09, BAD-001..004, THREAT-014/015.

Tests the BadSector review gate in control/badsector.py:
  - AUTH-INV-09: BadSector PASS never authorizes execution
  - BAD-001: PASS provenance verification (review_id + input_hash)
  - BAD-002: mandatory review categories skipped → DENY (THREAT-015)
  - BAD-003: PASS without delegation → still DENY at authority gate
  - BAD-004: BadSector failure/malformed → fail-closed → escalate
  - Forged PASS, missing review, hash mismatch, missing provenance
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from control.badsector import (
    BadSectorGate,
    badsector_pass_is_authority,
    verify_badsector_provenance,
    pass_grants_authority,
    _input_hash,
    MANDATORY_REVIEW_ACTIONS,
)
from control.risk import INTRINSIC_HIGH_ACTIONS


def _real_review(review_id="r1", verdict="PASS", input_hash=None):
    return {"review_id": review_id, "verdict": verdict,
            "agent_id": "badsector",
            "input_hash": input_hash or "abc123"}


def _review_log(entries=None):
    return entries or [{"review_id": "r1", "agent_id": "badsector",
                        "verdict": "PASS"}]


class TestProvenance:
    """BAD-001 / THREAT-014 — PASS must have verifiable provenance."""

    def test_bad_001_forged_pass_denied(self):
        forged = _real_review("r-forged", input_hash="abc123")
        assert verify_badsector_provenance(forged, "abc123", []) is False

    def test_bad_001_real_pass_accepted(self):
        real = _real_review("r1")
        assert verify_badsector_provenance(real, "abc123",
                                           _review_log()) is True

    def test_bad_001_hash_mismatch_denied(self):
        real = _real_review("r1", input_hash="abc123")
        assert verify_badsector_provenance(real, "different-hash",
                                           _review_log()) is False

    def test_bad_001_non_pass_never_accepted(self):
        rework = _real_review("r1", verdict="REWORK")
        assert verify_badsector_provenance(rework, "abc123",
                                           _review_log()) is False

    def test_bad_001_missing_review_id_denied(self):
        no_id = {"verdict": "PASS", "input_hash": "abc123"}
        assert verify_badsector_provenance(no_id, "abc123",
                                           _review_log()) is False

    def test_bad_001_wrong_log_entry_denied(self):
        real = _real_review("r2", input_hash="abc123")
        assert verify_badsector_provenance(real, "abc123",
                                           _review_log()) is False


class TestMandatorySkipped:
    """BAD-002 / THREAT-015 — mandatory review skipped → DENY."""

    def test_risk_high_skip_denied(self):
        d = BadSectorGate().evaluate(risk="HIGH", action="write", review=None)
        assert d.decision == "DENY"
        assert d.mandatory is True
        assert "THREAT-015" in d.reason

    def test_intrinsic_high_action_skip_denied(self):
        for action in list(INTRINSIC_HIGH_ACTIONS)[:3]:
            d = BadSectorGate().evaluate(risk="LOW", action=action,
                                          review=None)
            assert d.decision == "DENY", f"action={action} should be mandatory"
            assert d.mandatory is True

    def test_review_required_flag_skip_denied(self):
        d = BadSectorGate().evaluate(risk="LOW", action="read",
                                      review_required=True, review=None)
        assert d.decision == "DENY"
        assert d.mandatory is True

    def test_high_uncertainty_skip_denied(self):
        d = BadSectorGate().evaluate(risk="LOW", action="read",
                                      uncertainty="high", review=None)
        assert d.decision == "DENY"
        assert d.mandatory is True

    def test_material_conflict_skip_denied(self):
        d = BadSectorGate().evaluate(risk="LOW", action="read",
                                      material_conflict=True, review=None)
        assert d.decision == "DENY"
        assert d.mandatory is True

    def test_low_risk_conditional_skip_allowed(self):
        d = BadSectorGate().evaluate(risk="LOW", action="read", review=None)
        assert d.decision == "ALLOW"
        assert d.mandatory is False


class TestPassNeverAuthorizes:
    """AUTH-INV-09 / BAD-003 — PASS clears review only, never authority."""

    def test_auth_inv_09_badsector_pass_never_authority(self):
        assert badsector_pass_is_authority({"verdict": "PASS"}, None) is False
        assert badsector_pass_is_authority({"verdict": "PASS"},
                                            {"id": "d1"}) is False

    def test_bad_003_pass_no_delegation_still_denied(self):
        """Even with a verifiable PASS, execute without delegation → DENY
        (at the authority gate — modeled here by checking that the review
        decision alone does not say ALLOW is authority)."""
        gate = BadSectorGate()
        h = _input_hash({"action": "delete", "target": "x"})
        real = _real_review("r1", input_hash=h)
        d = gate.evaluate(risk="HIGH", action="delete", review=real,
                           expected_input_hash=h, review_log=_review_log())
        assert d.decision == "ALLOW"  # review cleared
        assert d.review_cleared is True
        # But badsector_pass_is_authority says PASS is NEVER authority
        assert badsector_pass_is_authority(real, {"id": "d1"}) is False
        assert pass_grants_authority(real) is False

    def test_proven_pass_clears_review_only(self):
        """A PASS with full provenance clears review; the gate returns ALLOW
        but the reason states it is not authorization."""
        gate = BadSectorGate()
        h = _input_hash({"action": "delete", "target": "x"})
        real = _real_review("r1", input_hash=h)
        d = gate.evaluate(risk="HIGH", action="delete", review=real,
                           expected_input_hash=h, review_log=_review_log())
        assert d.decision == "ALLOW"
        assert d.review_cleared is True
        assert "AUTH-INV-09" in d.reason


class TestFailClosed:
    """BAD-004 — BadSector failure/malformed → fail-closed → escalate."""

    def test_bad_004_malformed_verdict_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete",
                           review={"verdict": "NOPE", "input_hash": "x"})
        assert d.decision == "DENY"
        assert d.review_cleared is False

    def test_bad_004_error_record_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete",
                           review={"error": "tool failed"})
        assert d.decision == "DENY"
        assert d.review_cleared is False

    def test_bad_004_empty_review_dict_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete", review={})
        assert d.decision == "DENY"
        assert d.review_cleared is False

    def test_bad_004_none_review_under_mandatory_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete", review=None)
        assert d.decision == "DENY"
        assert d.review_cleared is False

    def test_bad_004_pass_without_provenance_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete",
                           review=_real_review("r1", input_hash="x"),
                           expected_input_hash="x", review_log=[])
        assert d.decision == "DENY"
        assert d.review_cleared is False

    def test_bad_004_none_expected_hash_denied(self):
        gate = BadSectorGate()
        d = gate.evaluate(risk="HIGH", action="delete",
                           review=_real_review("r1", input_hash="x"),
                           expected_input_hash=None, review_log=[])
        assert d.decision == "DENY"


class TestReviewMandatoryTrigger:
    """review_mandatory() unit tests."""

    def test_high_risk_mandatory(self):
        assert BadSectorGate().review_mandatory(risk="HIGH") is True

    def test_intrinsic_high_action_mandatory(self):
        assert BadSectorGate().review_mandatory(
            risk="LOW", action="production_deploy") is True

    def test_review_required_mandatory(self):
        assert BadSectorGate().review_mandatory(
            risk="LOW", action="read", review_required=True) is True

    def test_low_risk_not_mandatory(self):
        assert BadSectorGate().review_mandatory(
            risk="LOW", action="read") is False

    def test_high_uncertainty_mandatory(self):
        assert BadSectorGate().review_mandatory(
            risk="LOW", action="read", uncertainty="high") is True

    def test_material_conflict_mandatory(self):
        assert BadSectorGate().review_mandatory(
            risk="LOW", action="read", material_conflict=True) is True

    def test_mandatory_review_actions_include_intrinsic_high(self):
        assert MANDATORY_REVIEW_ACTIONS >= INTRINSIC_HIGH_ACTIONS


class TestInputHash:
    """_input_hash determinism and consistency."""

    def test_deterministic_hash(self):
        payload = {"action": "delete", "target": "x"}
        h1 = _input_hash(payload)
        h2 = _input_hash(payload)
        assert h1 == h2
        assert isinstance(h1, str) and len(h1) == 64

    def test_different_input_different_hash(self):
        assert _input_hash({"a": 1}) != _input_hash({"a": 2})

    def test_hash_used_in_verify(self):
        payload = {"action": "delete", "target": "x"}
        h = _input_hash(payload)
        review = _real_review("r1", input_hash=h)
        rl = _review_log()
        assert verify_badsector_provenance(review, h, rl) is True
        assert verify_badsector_provenance(review, "wrong-" + h, rl) is False
# control/badsector.py — BadSector review gate (L1 project control plane)
#
# Phase: Phase 2 Control Plane — Session B (Risk + Evidence + Conflict +
# BadSector). Companion to docs/security/0001-control-assurance-spec.md §9,
# docs/security/0002-threat-model-and-control-architecture.md §15
# (AUTH-INV-09, THREAT-014/015), docs/design/0001-control-design-and-test-plan.md
# §11 (BAD-001..004).
#
# PURPOSE
#   Enforce the BadSector review stage:
#     - MANDATORY TRIGGER (THREAT-015): review cannot be skipped when
#         risk == HIGH, action is in the intrinsic-HIGH set, or explicit
#         review_required. A skip under a mandatory trigger → DENY (transition
#         violation).
#     - PROVENANCE (THREAT-014 / BAD-001): a PASS is accepted only when it
#         came from a real BadSector invocation — review_id + input_hash match
#         a record in the review log (audit). Forged PASS → DENY.
#     - PASS CLEARS REVIEW ONLY (AUTH-INV-09): a PASS never grants authority.
#         badsector_pass_is_authority() always returns False; the authority
#         gate (control/authority / tests/control_plane.py) is the only place
#         that authorizes.
#     - FAIL-CLOSED (BAD-004): missing/malformed/error verdict → treated as
#         NOT passed → DENY + escalate.
#
# FAILURE BEHAVIOR: any gap (skip, forgery, malformed, non-PASS) → DENY with a
#   named reason; the action stops. A PASS with full provenance clears ONLY
#   the review stage.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, Optional

from control.risk import INTRINSIC_HIGH_ACTIONS

# Verdict vocabulary (docs/security/0001 §9).
VALID_VERDICTS = frozenset({"PASS", "REWORK", "REJECT"})

# Mandatory-review action categories (docs/security/0002 §15.1).
MANDATORY_REVIEW_ACTIONS = INTRINSIC_HIGH_ACTIONS | frozenset({
    "strategic_decision", "high_uncertainty", "conflicting_outputs",
})


@dataclass(frozen=True)
class ReviewDecision:
    """Outcome of the BadSector review stage.

    decision:       ALLOW (review cleared) | DENY | ESCALATE
    mandatory:      True when a mandatory trigger fired.
    review_cleared: True only when a proven PASS was present.
    reason:         Human-readable outcome.
    detail:         Machine-readable detail for audit.
    """
    decision: str
    mandatory: bool = False
    review_cleared: bool = False
    reason: str = ""
    detail: dict = field(default_factory=dict)

    def __bool__(self):
        return self.decision == "ALLOW"


def _input_hash(payload) -> str:
    """Deterministic hash of the reviewed input (JSON-canonical)."""
    try:
        canonical = json.dumps(payload, sort_keys=True,
                               separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BadSectorGate:
    """BadSector review-stage gate."""

    def review_mandatory(self, *, risk: str = "LOW",
                         action: str = "",
                         review_required: bool = False,
                         uncertainty: Optional[str] = None,
                         material_conflict: bool = False) -> bool:
        """THREAT-015: mandatory triggers — HIGH risk, intrinsic-HIGH action,
        explicit review_required, high uncertainty, or material conflict."""
        if review_required is True:
            return True
        if (risk or "").upper() == "HIGH":
            return True
        if (action or "").strip().lower() in MANDATORY_REVIEW_ACTIONS:
            return True
        if uncertainty and str(uncertainty).lower() in (
                "high", "very high", "critical"):
            return True
        if material_conflict:
            return True
        return False

    def verify_provenance(self, review_record: Optional[dict],
                          expected_input_hash: str,
                          review_log: Iterable[dict]) -> bool:
        """THREAT-014 / BAD-001: a PASS must come from a real BadSector
        invocation. True only when:
          - the record is a dict with verdict == PASS,
          - input_hash matches the expected hash of the reviewed input,
          - review_id is present AND appears in the review log (audit record
            produced by the control plane from a real invocation).
        """
        if not isinstance(review_record, dict):
            return False
        if review_record.get("verdict") != "PASS":
            return False
        if review_record.get("input_hash") != expected_input_hash:
            return False
        rid = review_record.get("review_id")
        if not rid:
            return False
        for entry in (review_log or ()):
            if isinstance(entry, dict) and entry.get("review_id") == rid:
                return True
        return False

    def evaluate(self, *, risk: str = "LOW",
                 action: str = "",
                 review: Optional[dict] = None,
                 review_required: bool = False,
                 expected_input_hash: Optional[str] = None,
                 review_log: Iterable[dict] = (),
                 uncertainty: Optional[str] = None,
                 material_conflict: bool = False) -> ReviewDecision:
        """Evaluate the review stage for one action.

        review:        the claimed BadSector review record.
        review_log:    control-plane audit records of real BadSector
                       invocations (each must carry review_id; ideally
                       agent_id == "badsector").
        """
        mandatory = self.review_mandatory(
            risk=risk, action=action, review_required=review_required,
            uncertainty=uncertainty, material_conflict=material_conflict)

        # 1. Skipped review under a mandatory trigger → DENY (transition
        #    violation, THREAT-015).
        if not review:
            if mandatory:
                return ReviewDecision(
                    "DENY", mandatory=True, review_cleared=False,
                    reason="mandatory BadSector review skipped (THREAT-015)",
                    detail={"mandatory": True, "risk": risk,
                            "action": action, "review_required": review_required})
            return ReviewDecision(
                "ALLOW", mandatory=False, review_cleared=False,
                reason="review not required for this action class",
                detail={"mandatory": False, "risk": risk, "action": action})

        # 2. Malformed / error record → NOT passed → fail-closed (BAD-004).
        if not isinstance(review, dict) or "verdict" not in review:
            return ReviewDecision(
                "DENY", mandatory=mandatory, review_cleared=False,
                reason="malformed BadSector verdict — not passed (BAD-004)",
                detail={"review": review})

        # 3. Non-PASS verdict → not cleared.
        if review.get("verdict") != "PASS":
            return ReviewDecision(
                "DENY", mandatory=mandatory, review_cleared=False,
                reason=f"review not passed: {review.get('verdict')}",
                detail={"verdict": review.get("verdict")})

        # 4. PASS provenance: must match a real invocation on the exact input.
        if expected_input_hash is None:
            return ReviewDecision(
                "DENY", mandatory=mandatory, review_cleared=False,
                reason="PASS without expected input hash — cannot verify "
                       "provenance (THREAT-014)",
                detail={"review_id": review.get("review_id")})

        if not self.verify_provenance(review, expected_input_hash, review_log):
            return ReviewDecision(
                "DENY", mandatory=mandatory, review_cleared=False,
                reason="PASS provenance mismatch — forged or simulated review "
                       "(THREAT-014 / BAD-001)",
                detail={"review_id": review.get("review_id"),
                        "input_hash": review.get("input_hash")})

        # 5. Proven PASS clears the review stage ONLY — never authorization
        #    (AUTH-INV-09). Execution still requires the authority gate.
        return ReviewDecision(
            "ALLOW", mandatory=mandatory, review_cleared=True,
            reason="review cleared (PASS != authorization, AUTH-INV-09)",
            detail={"review_id": review.get("review_id"),
                    "input_hash": review.get("input_hash")})


def badsector_pass_is_authority(pass_record, delegation=None) -> bool:
    """AUTH-INV-09 / INV-03: a BadSector PASS never authorizes execution.

    Always returns False — regardless of the pass_record or delegation, a PASS
    is review-stage data, not authority. Matches the reference
    control_plane.badsector_pass_is_authority contract.
    """
    return False


def verify_badsector_provenance(review_record, expected_input_hash,
                                review_log) -> bool:
    """BAD-001 / THREAT-014 convenience wrapper (reference parity)."""
    return BadSectorGate().verify_provenance(review_record,
                                             expected_input_hash,
                                             review_log)


def pass_grants_authority(*args, **kwargs) -> bool:
    """Explicit denial: a PASS (even with full provenance) never grants
    authority. This is the dedicated anti-AUTH-INV-09 helper for callers that
    want a named function instead of the constant False."""
    return False

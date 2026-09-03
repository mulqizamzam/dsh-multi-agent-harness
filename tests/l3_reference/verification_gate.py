# tests/l3_reference/verification_gate.py — INDEPENDENT verification-gate reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of the
# verification semantics: COMPLETE requires a verified outcome, an agent claim
# is never verification, expected-vs-actual comparison, evidence sufficiency,
# independence requirements, and Human confirmation for HIGH categories.
# Imports NOTHING from production control modules (control/verification.py).
#
# Controls covered: L3-VER-001..006, L3-XG-001, L3-AUTH-015.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VerificationVerdict:
    decision: str   # PASSED | FAILED | INSUFFICIENT | UNVERIFIED
    reason: str = ""
    gate_under_test: str = "verification"
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "detail": dict(self.detail),
        }


# Action category -> (independence, required_evidence, human_confirmation)
# Mirrors docs/security/0001 §10 / §16.1 and control/verification.py semantics.
VERIFICATION_REQUIREMENTS: dict[str, tuple] = {
    "internal_analysis":      ("self", (), False),
    "code_change":            ("self", ("test", "build"), False),
    "code_change_production": ("independent", ("test", "build"), False),
    "production_deploy":      ("independent", ("deployment_status", "runtime_health"), False),
    "infrastructure":         ("independent", ("runtime_health",), False),
    "financial":              ("independent", ("financial_result",), True),
    "credential_change":      ("independent", ("audit_record",), True),
    "material_publication":   ("independent", ("published_content",), True),
    "novel_writing":          ("self", ("continuity_check",), False),
    "recovery_rollback":      ("independent", ("restoration_proof",), False),
}

ACTION_TO_CATEGORY: dict[str, str] = {
    "code_write": "code_change", "edit": "code_change", "write": "code_change",
    "test": "code_change", "production_deploy": "production_deploy",
    "deploy": "production_deploy", "server_write": "infrastructure",
    "infra": "infrastructure", "financial_transaction": "financial",
    "credential_change": "credential_change", "sensitive_publication": "material_publication",
    "publish": "material_publication", "rollback": "recovery_rollback",
    "recovery": "recovery_rollback", "analysis": "internal_analysis",
    "research": "internal_analysis", "read": "internal_analysis",
    "novel": "novel_writing", "novel_editing": "novel_writing",
}


def action_category(action: str) -> str:
    return ACTION_TO_CATEGORY.get((action or "").strip().lower(), action)


def _requirements(category: str):
    reqs = VERIFICATION_REQUIREMENTS.get(category)
    if reqs is None:
        raise ValueError(f"unknown verification category {category!r} (fail-closed)")
    return reqs


def evaluate_verification_reference(*, action_category, expected_outcome=None,
                                    observed_outcome=None, evidence=(), agent_claim=None,
                                    human_confirmation=False, executor="") -> VerificationVerdict:
    """Independent verification oracle.

    Returns PASSED only when:
      - an observed outcome exists (agent claim alone is UNVERIFIED);
      - observed outcome matches expected outcome;
      - every required evidence kind is present;
      - the independence requirement is satisfied (independent verification
        when required);
      - Human confirmation is present when required.
    """
    try:
        independence, required, need_human = _requirements(action_category)
    except ValueError as e:
        return VerificationVerdict("FAILED", str(e), "verification",
                                   {"action_category": action_category})

    detail = {"action_category": action_category, "independence": independence,
              "required_evidence": list(required),
              "human_confirmation_required": need_human}

    # THREAT-016 / AUTH-INV-15: an agent "success" claim is NOT verification.
    if agent_claim == "SUCCEEDED" and not observed_outcome:
        return VerificationVerdict(
            "UNVERIFIED",
            "agent reports success but no observed outcome collected — claim is "
            "not verification (THREAT-016 / AUTH-INV-15)",
            "verification", detail)

    if not observed_outcome:
        return VerificationVerdict(
            "UNVERIFIED",
            "no observed outcome recorded; expected-vs-actual comparison "
            "impossible (VERIFY-001)",
            "verification", detail)

    # Expected vs actual comparison.
    for key, exp_val in (expected_outcome or {}).items():
        if key not in observed_outcome:
            return VerificationVerdict(
                "FAILED",
                f"expected property {key!r} missing from observed outcome (VERIFY-002)",
                "verification", {**detail, "missing": key})
        if observed_outcome[key] != exp_val:
            return VerificationVerdict(
                "FAILED",
                f"expected property {key!r}={exp_val!r}, observed "
                f"{observed_outcome[key]!r} (VERIFY-002)",
                "verification", {**detail, "key": key,
                                 "expected": exp_val, "observed": observed_outcome[key]})

    ev_list = list(evidence or ())

    def _kind(e):
        return e.get("kind") if isinstance(e, dict) else getattr(e, "kind", None)

    # Evidence sufficiency: every required kind must have at least one artifact.
    missing = [k for k in required if not any(_kind(e) == k for e in ev_list)]
    if missing:
        return VerificationVerdict(
            "INSUFFICIENT",
            f"verification evidence incomplete: missing {sorted(missing)} (VERIFY-003)",
            "verification", detail)

    # Independence.
    if independence == "independent":
        has_independent = False
        for e in ev_list:
            if isinstance(e, dict):
                ind = e.get("independent", False)
                ver = e.get("verifier", "")
            else:
                ind = getattr(e, "independent", False)
                ver = getattr(e, "verifier", "")
            if ind and (not executor or ver != executor):
                has_independent = True
                break
        if not has_independent:
            return VerificationVerdict(
                "INSUFFICIENT",
                "action category requires INDEPENDENT verification; executor "
                "self-verification is insufficient",
                "verification", detail)

    # Human confirmation.
    if need_human and not human_confirmation:
        return VerificationVerdict(
            "INSUFFICIENT",
            "action category requires Human confirmation for COMPLETE",
            "verification", detail)

    return VerificationVerdict(
        "PASSED",
        "verified outcome matches expected with required evidence (AUTH-INV-15)",
        "verification", {**detail, "evidence_count": len(ev_list)})


def can_emit_complete_reference(*, action_category, expected_outcome=None,
                                observed_outcome=None, evidence=(), agent_claim=None,
                                human_confirmation=False, executor="") -> bool:
    """AUTH-INV-15: COMPLETE may only be emitted on PASSED."""
    v = evaluate_verification_reference(
        action_category=action_category, expected_outcome=expected_outcome,
        observed_outcome=observed_outcome, evidence=evidence, agent_claim=agent_claim,
        human_confirmation=human_confirmation, executor=executor)
    return v.decision == "PASSED"


def oracle_verification(context: dict) -> dict:
    """Wrapper for the verifier."""
    v = evaluate_verification_reference(
        action_category=context.get("action_category", ""),
        expected_outcome=context.get("expected_outcome"),
        observed_outcome=context.get("observed_outcome"),
        evidence=context.get("evidence", ()),
        agent_claim=context.get("agent_claim"),
        human_confirmation=context.get("human_confirmation", False),
        executor=context.get("executor", ""))
    return v.to_dict()


__all__ = [
    "VerificationVerdict",
    "VERIFICATION_REQUIREMENTS",
    "ACTION_TO_CATEGORY",
    "action_category",
    "evaluate_verification_reference",
    "can_emit_complete_reference",
    "oracle_verification",
]

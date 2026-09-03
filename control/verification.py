# control/verification.py — Verification control-plane module
#
# Phase 2 / Session C — Verification + Recovery
#
# PURPOSE
#   Enforce the verification invariants from the security specification:
#     - AUTH-INV-15 (COMPLETE requires verified outcome, not an agent claim)
#     - VERIFY-001 (false success report → no COMPLETE)
#     - VERIFY-002 (expected vs actual mismatch → FAIL → recovery)
#     - VERIFY-003 (incomplete verification evidence → no COMPLETE for HIGH)
#     - THREAT-016 (agent reports success ≠ system verified success)
#     - Action-category independence requirements (§10 / §16.1)
#     - Recovery/rollback requires independent restoration verification (REC-003)
#
# DESIGN
#   An expected outcome is declared BEFORE execution (ExpectedOutcome).
#   After execution, the observed outcome is recorded and compared to expected.
#   Verification evidence (artifacts, not claims) is collected and checked
#   against the action category's requirements. The verdict is PASSED only
#   when all requirements are met. COMPLETE may only be emitted on PASSED.
#
#   This module is independent of the orchestrator foundation gates; it
#   provides a VerificationGate that raises VerificationDenied when a
#   COMPLETE attempt is made without a verified outcome (fail-closed).
#
# REUSE
#   - Does NOT modify orchestrator/foundation/gates.py (VerificationGate there
#     is a placeholder).
#   - Does NOT modify state/helpers/recovery.py.
#   - Imports from control.execution_gate are NOT needed; verification is a
#     separate gate (the execution gate handles path-based authorization).

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class VerificationError(ValueError):
    """Base verification error (fail-closed)."""


class VerificationDenied(VerificationError):
    """Raised when a COMPLETE attempt is refused because verification has not
    PASSED (AUTH-INV-15)."""


# ---------------------------------------------------------------------------
# Action category → verification requirements
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VerificationRequirements:
    """Verification requirements for an action category.

    independence: "self" | "independent"
        Whether the actor may verify its own work or an independent verifier
        is required.
    required_evidence: tuple of str
        Evidence kinds that must each be present (at least one artifact per
        kind).  Empty tuple means no specific evidence kinds are mandated.
    human_confirmation: bool
        Whether the category requires a Human confirmation sign-off before
        COMPLETE.
    """
    independence: str = "self"
    required_evidence: tuple = ()
    human_confirmation: bool = False


# Table from security spec §10 / §16.1.
_VERIFICATION_REQUIREMENTS: dict[str, VerificationRequirements] = {
    # Internal research / analysis — self-verification acceptable
    "internal_analysis":      VerificationRequirements("self", ()),
    # Code change (non-production) — self + test/build evidence
    "code_change":            VerificationRequirements("self", ("test", "build")),
    # Code change (production) — independent verification
    "code_change_production": VerificationRequirements("independent", ("test", "build")),
    # Infrastructure / deployment — independent
    "production_deploy":      VerificationRequirements("independent", ("deployment_status", "runtime_health")),
    "infrastructure":         VerificationRequirements("independent", ("runtime_health",)),
    # Financial commitment — independent + Human confirmation
    "financial":              VerificationRequirements("independent", ("financial_result",), True),
    # Credential / permission change — independent + Human confirmation
    "credential_change":      VerificationRequirements("independent", ("audit_record",), True),
    # Material external publication — independent + Human confirmation
    "material_publication":   VerificationRequirements("independent", ("published_content",), True),
    # Novel / manuscript writing — self-verification acceptable
    "novel_writing":          VerificationRequirements("self", ("continuity_check",)),
    # Recovery / rollback — independent restoration verification (REC-003)
    "recovery_rollback":      VerificationRequirements("independent", ("restoration_proof",)),
}

# Canonical action-class → verification-category mapping (fallback: the
# action string itself, which will raise VerificationError from
# verification_requirements() — fail-closed on unknown actions).
_ACTION_TO_CATEGORY: dict[str, str] = {
    "code_write":             "code_change",
    "edit":                   "code_change",
    "write":                  "code_change",
    "test":                   "code_change",
    "production_deploy":      "production_deploy",
    "deploy":                 "production_deploy",
    "server_write":           "infrastructure",
    "infra":                  "infrastructure",
    "financial_transaction":  "financial",
    "credential_change":      "credential_change",
    "sensitive_publication":  "material_publication",
    "publish":                "material_publication",
    "rollback":               "recovery_rollback",
    "recovery":               "recovery_rollback",
    "analysis":               "internal_analysis",
    "research":               "internal_analysis",
    "read":                   "internal_analysis",
    "novel":                  "novel_writing",
    "novel_editing":          "novel_writing",
}


def action_category(action: str) -> str:
    """Map an action-class string to a verification category.

    Returns the action string itself when no mapping exists (causing
    verification_requirements() to raise VerificationError — fail-closed
    on unknown actions).
    """
    return _ACTION_TO_CATEGORY.get((action or "").strip().lower(), action)


def verification_requirements(category: str) -> VerificationRequirements:
    """Return the requirements for a verification category.

    Raises VerificationError on unknown categories (fail-closed).
    """
    reqs = _VERIFICATION_REQUIREMENTS.get(category)
    if reqs is None:
        raise VerificationError(
            f"unknown verification category {category!r} — cannot determine "
            f"verification requirements (fail-closed)")
    return reqs


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExpectedOutcome:
    """The expected outcome, declared BEFORE execution (VERIFY-001).

    task_id:       the task this outcome applies to
    action_category: the verification category the requirements are derived from
    description:   human-readable description of the expected outcome
    expected:      dict of observable properties to compare against the
                   actual observed outcome (e.g. {"exit_code": 0, "file": "x"})
    """
    task_id: str
    action_category: str
    description: str = ""
    expected: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.task_id.strip():
            raise VerificationError("ExpectedOutcome: task_id must be non-empty")
        # Validate category early (fail-closed at construction time).
        verification_requirements(self.action_category)


@dataclass(frozen=True)
class VerificationEvidence:
    """A piece of verification evidence — an artifact, not a claim.

    kind:            evidence kind (e.g. "test", "build", "runtime_health",
                     "restoration_proof")
    source:          reference to the artifact (path, URL, record id)
    verifier:        identity of the verifier (e.g. "self:cto",
                     "independent:ops")
    independent:     True when the verifier is NOT the executor of the action
    human_confirmation: True when a Human has explicitly confirmed this evidence
    """
    kind: str
    source: str
    verifier: str = "self"
    independent: bool = False
    human_confirmation: bool = False


@dataclass
class VerificationResult:
    """The outcome of a verification evaluation.

    verdict: PASSED | FAILED | INSUFFICIENT | UNVERIFIED
    """
    verdict: str
    reason: str
    detail: dict = field(default_factory=dict)

    def is_verified(self) -> bool:
        return self.verdict == "PASSED"

    def can_emit_complete(self) -> bool:
        """AUTH-INV-15: COMPLETE may only be emitted when the outcome is
        PASSED."""
        return self.is_verified()


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def _compare_expected_actual(
    expected: dict | None,
    observed: dict | None,
) -> tuple[bool, str]:
    """Compare expected vs actual observable properties.

    Returns (True, "") on match, or (False, reason) on mismatch.
    """
    if not isinstance(observed, dict):
        return False, "observed outcome is not a structured record"
    expected = expected or {}
    for key, exp_val in expected.items():
        if key not in observed:
            return False, (
                f"expected property {key!r} missing from observed outcome "
                f"(VERIFY-002)")
        if observed[key] != exp_val:
            return False, (
                f"expected property {key!r}={exp_val!r}, observed "
                f"{observed[key]!r} (VERIFY-002)")
    return True, ""


def evaluate_verification(
    *,
    action_category: str,
    expected_outcome: dict | None = None,
    observed_outcome: dict | None = None,
    evidence: tuple = (),
    agent_claim: str | None = None,
    human_confirmation: bool = False,
    executor: str = "",
) -> VerificationResult:
    """Evaluate whether verification passes for a completed action.

    Parameters
    ----------
    action_category:
        The verification category (from action_category() or
        verification_requirements()).
    expected_outcome:
        Dict of expected observable properties declared before execution.
    observed_outcome:
        Dict of actual observable properties collected after execution.
    evidence:
        Tuple of VerificationEvidence artifacts (not claims).
    agent_claim:
        The status the agent reported (e.g. "SUCCEEDED").  A claim is NOT
        verification (THREAT-016 / AUTH-INV-15).
    human_confirmation:
        Whether Human confirmation has been obtained.
    executor:
        Identity of the actor that performed the action (for independence
        checks).

    Returns
    -------
    VerificationResult with verdict PASSED / FAILED / INSUFFICIENT / UNVERIFIED.
    """
    reqs = verification_requirements(action_category)  # raises on unknown

    detail: dict = {
        "action_category": action_category,
        "independence": reqs.independence,
        "required_evidence": list(reqs.required_evidence),
        "human_confirmation_required": reqs.human_confirmation,
    }

    # THREAT-016 / AUTH-INV-15: an agent "success" claim is NOT verification
    # when no observed outcome was collected.
    if agent_claim == "SUCCEEDED" and not observed_outcome:
        return VerificationResult(
            "UNVERIFIED",
            "agent reports success but no observed outcome was collected — "
            "claim is not verification (THREAT-016 / AUTH-INV-15)",
            detail,
        )

    if not observed_outcome:
        return VerificationResult(
            "UNVERIFIED",
            "no observed outcome recorded; expected-vs-actual comparison "
            "impossible (VERIFY-001)",
            detail,
        )

    # Expected vs actual comparison (VERIFY-002).
    ok, why = _compare_expected_actual(expected_outcome, observed_outcome)
    if not ok:
        return VerificationResult(
            "FAILED",
            f"{why} → recovery path (VERIFY-002)",
            detail,
        )

    ev_list = list(evidence or ())

    # Evidence sufficiency: every required kind must have at least one artifact.
    missing = [
        k for k in reqs.required_evidence
        if not any(getattr(e, "kind", None) == k for e in ev_list)
    ]
    if missing:
        return VerificationResult(
            "INSUFFICIENT",
            f"verification evidence incomplete: missing {sorted(missing)} "
            f"(VERIFY-003)",
            detail,
        )

    # Independence check.
    if reqs.independence == "independent":
        has_independent = False
        for e in ev_list:
            if getattr(e, "independent", False):
                ver = getattr(e, "verifier", "")
                if not executor or ver != executor:
                    has_independent = True
                    break
        if not has_independent:
            return VerificationResult(
                "INSUFFICIENT",
                "action category requires INDEPENDENT verification; executor "
                "self-verification is insufficient",
                detail,
            )

    # Human confirmation check.
    if reqs.human_confirmation and not human_confirmation:
        return VerificationResult(
            "INSUFFICIENT",
            "action category requires Human confirmation for COMPLETE",
            detail,
        )

    return VerificationResult(
        "PASSED",
        "verified outcome matches expected with required evidence (AUTH-INV-15)",
        {**detail, "evidence": [asdict(e) for e in ev_list]},
    )


# ---------------------------------------------------------------------------
# VerificationSession — lifecycle wrapper
# ---------------------------------------------------------------------------

class VerificationSession:
    """Lifecycle wrapper that enforces "expected declared BEFORE execution"
    (VERIFY-001) and collects evidence step by step.

    Typical usage::

        session = VerificationSession(task_id, "code_change",
                                       expected={"exit_code": 0})
        # ... execute the action ...
        session.record_observed({"exit_code": 0, "output": "..."})
        session.add_evidence("test", "tests/test_x.py::test_case",
                             verifier="self:cto", independent=False)
        session.add_evidence("build", "build/output.log",
                             verifier="self:cto", independent=False)
        if not session.can_emit_complete():
            handle_verification_failure(session.evaluate())
    """

    def __init__(
        self,
        task_id: str,
        action_category: str,
        description: str = "",
        expected: dict | None = None,
        executor: str = "",
    ):
        self.expected_outcome = ExpectedOutcome(
            task_id, action_category, description, expected or {},
        )
        self.executor = executor
        self._observed: dict | None = None
        self._observed_set: bool = False
        self._evidence: list[VerificationEvidence] = []
        self._human_confirmation: bool = False
        self._agent_claim: str | None = None

    @property
    def task_id(self) -> str:
        return self.expected_outcome.task_id

    @property
    def action_category(self) -> str:
        return self.expected_outcome.action_category

    def record_observed(self, observed: dict) -> None:
        """Record the observed outcome AFTER execution.  Must be called at
        most once (expected must have been declared at construction)."""
        if self._observed_set:
            raise VerificationError("observed outcome already recorded")
        self._observed = dict(observed or {})
        self._observed_set = True

    def add_evidence(
        self,
        kind: str,
        source: str,
        verifier: str | None = None,
        independent: bool = False,
        human_confirmation: bool = False,
    ) -> VerificationEvidence:
        """Add a verification evidence artifact."""
        verifier = verifier or (
            f"self:{self.executor}" if self.executor else "self"
        )
        ev = VerificationEvidence(
            kind, source,
            verifier=verifier,
            independent=independent,
            human_confirmation=human_confirmation,
        )
        self._evidence.append(ev)
        if human_confirmation:
            self._human_confirmation = True
        return ev

    def record_agent_claim(self, status: str = "SUCCEEDED") -> None:
        """Record what the agent *reported* (a claim — not verification)."""
        self._agent_claim = status

    def evaluate(self) -> VerificationResult:
        """Evaluate the verification against the collected evidence."""
        return evaluate_verification(
            action_category=self.expected_outcome.action_category,
            expected_outcome=self.expected_outcome.expected,
            observed_outcome=self._observed,
            evidence=tuple(self._evidence),
            agent_claim=self._agent_claim,
            human_confirmation=self._human_confirmation,
            executor=self.executor,
        )

    def can_emit_complete(self) -> bool:
        """AUTH-INV-15: COMPLETE may only be emitted when verification passes."""
        return self.evaluate().can_emit_complete()


# ---------------------------------------------------------------------------
# VerificationGate — fail-closed gate
# ---------------------------------------------------------------------------

class VerificationGate:
    """Control-plane verification gate.

    Raises VerificationDenied when the verification session has not PASSED
    (AUTH-INV-15).  Fail-closed: any denial stops the COMPLETE transition.
    """

    name = "verification"

    def evaluate(self, session: VerificationSession) -> VerificationResult:
        """Evaluate the session and deny if COMPLETE is not allowed."""
        result = session.evaluate()
        if not result.can_emit_complete():
            raise VerificationDenied(
                f"COMPLETE refused: {result.reason} (AUTH-INV-15)")
        return result

    def __call__(self, session: VerificationSession) -> VerificationResult:
        """Convenience: callable alias."""
        return self.evaluate(session)
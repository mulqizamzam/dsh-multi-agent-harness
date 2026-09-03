# orchestrator.foundation.gates — Control-plane integration points (Phase 1D)
#
# Explicit interfaces for the gates the orchestrator owns (contract §2). Each
# gate exposes `evaluate(context) -> GateDecision`. Gates that are already
# bound by an existing control contract have real minimal behavior; gates that
# are NOT yet required to act (evidence/conflict/review/verification/recovery)
# are FAIL-CLOSED placeholders: they never ALLOW on their own, and an unbound
# gate consulted for a consequential step must DENY or ESCALATE.
#
# The execution gate is the real ADR 0002 path-aware gate in
# control/execution_gate.py and is wired in here — all control-plane writes go
# through the project execution channel (never raw DSH tools).

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field

from .contracts import Delegation, Task, TaskResult

_SCHEMAS_AND_CONTROL = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SCHEMAS_AND_CONTROL not in sys.path:
    sys.path.insert(0, _SCHEMAS_AND_CONTROL)


@dataclass(frozen=True)
class GateDecision:
    decision: str                      # ALLOW | DENY | ESCALATE
    reason: str = ""
    gate: str = ""
    detail: dict = field(default_factory=dict)

    def __bool__(self):
        return self.decision == "ALLOW"


class Gate:
    """Base gate interface. Every gate FAILS CLOSED unless overridden."""
    name = "gate"

    def evaluate(self, context) -> GateDecision:
        return GateDecision("DENY", f"{self.name} is a fail-closed placeholder",
                            self.name)


# ---------------------------------------------------------------------------
# AUTHORITY GATE
# ---------------------------------------------------------------------------
class AuthorityGate(Gate):
    """Consumes structured authority records ONLY. Model text, state-file
    `approved:true`, BadSector PASS, and agent messages are never authority
    (AUTH-INV-01/07/09/13/14). Fail-closed."""
    name = "authority"

    def evaluate(self, context) -> GateDecision:
        delegation = context.get("delegation")
        if not isinstance(delegation, Delegation):
            return GateDecision("DENY", "no structured delegation (AUTH-INV-05)", self.name)
        if not delegation.is_active():
            return GateDecision("DENY", f"delegation {delegation.task} not ACTIVE",
                                self.name)
        if delegation.is_expired():
            return GateDecision("DENY", f"delegation {delegation.task} expired",
                                self.name)
        # task scope containment: a task delegation must cover the action+target
        action = context.get("action", "")
        target = context.get("target", "")
        if delegation.action and action and delegation.action != action:
            return GateDecision("DENY", f"action {action} not authorized by delegation",
                                self.name)
        # prohibited actions are hard denials
        if action in delegation.prohibited_actions:
            return GateDecision("DENY", f"action {action} is prohibited", self.name)
        # requires_approval: escalate unless a matching approval reference exists
        if any(a in delegation.requires_approval for a in
               ("destructive", "financial_transfer", "sensitive_publication",
                "credential_change")):
            if not context.get("approval_reference"):
                return GateDecision("ESCALATE", "action requires Human approval",
                                    self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# RISK GATE
# ---------------------------------------------------------------------------
INTRINSIC_HIGH_ACTIONS = {
    "destructive", "production_deploy", "credential_change",
    "financial_transaction", "sensitive_publication", "publish",
}


class RiskGate(Gate):
    """Deterministic classification; intrinsic HIGH is never downgradable by
    model judgment."""
    name = "risk"

    def evaluate(self, context) -> GateDecision:
        action = context.get("action", "")
        task = context.get("task")
        if isinstance(task, Task) and task.risk_metadata:
            declared = task.risk_metadata
        else:
            declared = context.get("risk", "LOW")
        if declared == "HIGH":
            return GateDecision("ALLOW", "HIGH (declared, not downgradable)", self.name,
                                {"risk": "HIGH"})
        if action in INTRINSIC_HIGH_ACTIONS:
            # intrinsic HIGH regardless of declared risk
            return GateDecision("ALLOW", "intrinsic HIGH (non-downgradable)", self.name,
                                {"risk": "HIGH"})
        return GateDecision("ALLOW", "", self.name, {"risk": declared or "LOW"})


# ---------------------------------------------------------------------------
# EVIDENCE GATE
# ---------------------------------------------------------------------------
class EvidenceGate(Gate):
    """Ladder: SOURCE EXISTS → RELEVANT → SUPPORTS → CURRENT → UNCONTRADICTED →
    SUFFICIENT. Not yet production-bound; fail-closed when evidence is missing
    for a HIGH-risk action."""
    name = "evidence"

    def evaluate(self, context) -> GateDecision:
        risk = context.get("risk", "LOW")
        evidence = context.get("evidence", [])
        if risk == "HIGH" and not evidence:
            return GateDecision("DENY", "HIGH-risk action requires evidence (EVID-002)",
                                self.name)
        if risk == "MEDIUM" and not evidence:
            return GateDecision("ESCALATE", "MEDIUM action: no evidence (EVID-001)",
                                self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# CONFLICT GATE
# ---------------------------------------------------------------------------
class ConflictGate(Gate):
    """Detect → evidence → rework → synthesize → escalate. No majority voting.
    Placeholder (not production-bound); reports conflict if any found."""
    name = "conflict"

    def evaluate(self, context) -> GateDecision:
        conflicts = context.get("conflicts", [])
        if conflicts:
            return GateDecision("ESCALATE", f"conflicts unresolved: {conflicts}",
                                self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# BADSECTOR REVIEW GATE
# ---------------------------------------------------------------------------
class BadSectorReviewGate(Gate):
    """BadSector review is CONDITIONAL (Phase 1E).

    Mandatory triggers (cannot be skipped — THREAT-015):
      - risk == HIGH
      - action in INTRINSIC_HIGH_ACTIONS
      - explicit context.review_required
    When mandatory, absence of a review record → DENY (transition violation).

    When review is not mandatory, absence → ALLOW (conditional skip).

    A PASS verdict clears the review stage only — it NEVER authorizes
    (AUTH-INV-09). This gate verifies PASS provenance (review_id + input_hash).
    """
    name = "badsector_review"

    def evaluate(self, context) -> GateDecision:
        review = context.get("review")
        action = context.get("action", "")
        risk = context.get("risk", "LOW")
        mandatory = (
            context.get("review_required") is True
            or risk == "HIGH"
            or action in INTRINSIC_HIGH_ACTIONS
        )
        if not review:
            if mandatory:
                return GateDecision(
                    "DENY",
                    "mandatory BadSector review skipped (THREAT-015)",
                    self.name)
            return GateDecision(
                "ALLOW", "review not required for this action class", self.name)
        if review.get("verdict") != "PASS":
            return GateDecision(
                "DENY", f"review not passed: {review.get('verdict')}", self.name)
        # PASS provenance: review_id + input_hash must both be present; PASS
        # alone is data, not authority.
        if not (review.get("review_id") and review.get("input_hash")):
            return GateDecision(
                "DENY", "PASS without provenance (THREAT-014)", self.name)
        return GateDecision(
            "ALLOW", "review cleared (PASS != authorization)", self.name)


# ---------------------------------------------------------------------------
# EXECUTION GATE (real — wired to control/execution_gate.py, ADR 0002)
# ---------------------------------------------------------------------------
class ExecutionGate(Gate):
    """The real path-aware execution gate. For writes, it delegates to
    control.execution_gate.authorize_write — the project execution channel.
    Raw DSH tool writes must NOT bypass this in any consequential path."""
    name = "execution"

    def evaluate(self, context) -> GateDecision:
        action = context.get("action", "")
        target = context.get("target")
        if target is None:
            return GateDecision("DENY", "execution gate: no target", self.name)
        if not isinstance(target, str) or not target.strip():
            return GateDecision("DENY", "execution gate: malformed target", self.name)
        try:
            from control.execution_gate import authorize_write, Denied
            authorize_write(action, target, base=context.get("base"))
            return GateDecision("ALLOW", "", self.name)
        except Denied as e:
            return GateDecision("DENY", str(e), self.name)
        except ImportError:
            # execution gate not available → fail closed
            return GateDecision("DENY", "execution gate unavailable (fail-closed)",
                                self.name)


# ---------------------------------------------------------------------------
# VERIFICATION GATE
# ---------------------------------------------------------------------------
class VerificationGate(Gate):
    """COMPLETE requires verification evidence; reported ≠ verified. Placeholder
    that requires evidence for COMPLETE."""
    name = "verification"

    def evaluate(self, context) -> GateDecision:
        result = context.get("result")
        if isinstance(result, TaskResult) and result.status == "SUCCEEDED":
            if not result.evidence:
                return GateDecision("DENY", "COMPLETE requires verification evidence",
                                    self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# RECOVERY GATE
# ---------------------------------------------------------------------------
class RecoveryGate(Gate):
    """No blind retry (max_attempts per cause); recovery re-checks authority."""
    name = "recovery"

    def evaluate(self, context) -> GateDecision:
        attempts = context.get("attempts", 0)
        if attempts and attempts >= 1:
            return GateDecision("DENY", "max_attempts reached; diagnosed cause required",
                                self.name)
        if context.get("cause_diagnosed") is False:
            return GateDecision("DENY", "recovery without diagnosis (no blind retry)",
                                self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# Gate registry
# ---------------------------------------------------------------------------
class ControlPlane:
    """Explicit integration point for all gates. Each named gate is resolvable;
    an unknown gate name fails closed."""

    def __init__(self):
        self._gates = {
            "authority": AuthorityGate(),
            "risk": RiskGate(),
            "evidence": EvidenceGate(),
            "conflict": ConflictGate(),
            "badsector_review": BadSectorReviewGate(),
            "execution": ExecutionGate(),
            "verification": VerificationGate(),
            "recovery": RecoveryGate(),
        }

    def gate(self, name: str) -> Gate:
        g = self._gates.get(name)
        if g is None:
            return Gate()  # unknown gate → fail-closed DENY
        return g

    def evaluate(self, name: str, context: dict) -> GateDecision:
        return self.gate(name).evaluate(context or {})

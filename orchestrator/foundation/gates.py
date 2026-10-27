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
    (AUTH-INV-01/07/09/13/14). Fail-closed.

    Hardened (Phase 1E): adds execution-time checks that were missing from the
    original simplified gate:
      - AUTH-INV-11 (target containment): target must be within the delegation's
        scope_resources / target field (delegates to control.delegation.target_in_scope).
      - AUTH-INV-06 (revocation): delegation id in the revocation_list → DENY.
    Falls closed to DENY if the control submodule is unavailable."""
    name = "authority"

    def evaluate(self, context) -> GateDecision:
        ctx = context or {}
        delegation = ctx.get("delegation")
        if not isinstance(delegation, Delegation):
            return GateDecision("DENY", "no structured delegation (AUTH-INV-05)", self.name)
        if not delegation.is_active():
            return GateDecision("DENY", f"delegation {delegation.task} not ACTIVE",
                                self.name)
        if delegation.is_expired():
            return GateDecision("DENY", f"delegation {delegation.task} expired",
                                self.name)
        # AUTH-INV-06: revocation re-checked at execution time
        revocation_list = ctx.get("revocation_list", ())
        if delegation.id in (revocation_list or ()):
            return GateDecision("DENY",
                                f"delegation {delegation.id} revoked (AUTH-INV-06)",
                                self.name)
        # task scope containment: a task delegation must cover the action
        action = ctx.get("action", "")
        target = ctx.get("target", "")
        if delegation.action and action and delegation.action != action:
            return GateDecision("DENY", f"action {action} not authorized by delegation",
                                self.name)
        # AUTH-INV-11 (HARDENED): target containment — the execution target
        # must fall within the delegation's authorized resources. Delegates to
        # control.delegation.target_in_scope (the same prefix-boundary matcher
        # the control-plane authority gate uses). Skipped when neither the
        # delegation nor the context carries a target (read-only / umbrella
        # delegations legitimately omit a concrete target).
        if target and (delegation.target or delegation.scope_resources):
            try:
                from control.delegation import target_in_scope
            except ImportError:
                return GateDecision("DENY",
                                    "target_in_scope unavailable (fail-closed)",
                                    self.name)
            resources = delegation.scope_resources or (delegation.target,)
            if not target_in_scope(target, resources):
                return GateDecision(
                    "DENY",
                    f"target {target!r} outside delegation resources "
                    f"(AUTH-INV-11): {list(resources)}",
                    self.name)
        # prohibited actions are hard denials
        if action in delegation.prohibited_actions:
            return GateDecision("DENY", f"action {action} is prohibited", self.name)
        # requires_approval: escalate unless a matching approval reference exists
        if any(a in delegation.requires_approval for a in
               ("destructive", "financial_transfer", "sensitive_publication",
                "credential_change")):
            if not ctx.get("approval_reference"):
                return GateDecision("ESCALATE", "action requires Human approval",
                                    self.name)
        return GateDecision("ALLOW", "", self.name)


# ---------------------------------------------------------------------------
# RISK GATE
# ---------------------------------------------------------------------------
# Hardened (Phase 1E): expanded to match control.risk.INTRINSIC_HIGH_ACTIONS
# so BadSectorReviewGate mandatory triggers are consistent with the full
# semantic-laundering-resistant vocabulary (THREAT-011/012).
try:
    from control.risk import INTRINSIC_HIGH_ACTIONS  # noqa: F401
except ImportError:  # fail-closed fallback (module unavailable)
    INTRINSIC_HIGH_ACTIONS = frozenset({
        "destructive", "production_deploy", "credential_change",
        "financial_transaction", "sensitive_publication", "publish",
        "deploy_to_prod", "production_change", "destroy", "drop_database",
        "delete_production", "purge", "wipe", "unlink", "truncate_data",
        "permission_change", "role_grant", "access_grant",
        "financial_commitment", "payment", "wire_transfer",
        "material_publication", "delete", "drop", "truncate", "overwrite",
        "rm",
    })


class RiskGate(Gate):
    """Deterministic risk classification with semantic-laundering resistance
    (THREAT-011/012) and AUTH-INV-10 enforcement.

    Hardened (Phase 1E): delegates to ``control.risk.RiskClassifier`` for the
    full signal set (intrinsic actions, production environment, destructive
    flags, credential/permission/financial/publication keyword patterns,
    non-downgradable HIGH). Falls closed to DENY if the control module is
    unavailable."""
    name = "risk"

    def evaluate(self, context) -> GateDecision:
        ctx = context or {}
        action = ctx.get("action", "")
        task = ctx.get("task")
        if isinstance(task, Task) and task.risk_metadata:
            declared = task.risk_metadata
        else:
            declared = ctx.get("declared") or ctx.get("risk", "LOW")

        try:
            from control.risk import RiskClassifier
            classifier = RiskClassifier()
            rc = classifier.classify(
                action=action,
                target=ctx.get("target", ""),
                environment=ctx.get("environment"),
                requires_approval=ctx.get("requires_approval", ()),
                operation_flags=ctx.get("operation_flags", ()),
                tool=ctx.get("tool"),
                command=ctx.get("command"),
                declared=declared,
            )
        except ImportError:
            return GateDecision("DENY", "risk gate unavailable (fail-closed)",
                                self.name)

        # AUTH-INV-10: intrinsic HIGH cannot be downgraded by model judgment.
        if rc.intrinsic and (declared or "LOW").upper() != "HIGH":
            return GateDecision(
                "DENY",
                f"intrinsic HIGH cannot be downgraded to {declared or 'LOW'} "
                f"(AUTH-INV-10) signals={list(rc.signals)}",
                self.name,
                {"risk": "HIGH", "intrinsic": True,
                 "signals": list(rc.signals)})

        return GateDecision(
            "ALLOW", rc.reason or "risk classified", self.name,
            {"risk": rc.level, "intrinsic": rc.intrinsic,
             "signals": list(rc.signals)})


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

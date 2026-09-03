# orchestrator.runtime.gates — Gate invocation (Phase 3)
#
# The runtime invokes the EXISTING control-plane gates; it does NOT reimplement
# them. This module is a thin, deterministic invocation surface that maps each
# runtime gate onto the production control modules:
#
#   risk_gate        -> control.risk.RiskClassifier (AUTH-INV-10 non-downgradable)
#   evidence_gate    -> control.evidence.EvidenceGate (EVID-001..004)
#   conflict_gate    -> control.conflict.ConflictGate (CONF-001..003, no voting)
#   badsector_review -> control.badsector.BadSectorGate (THREAT-014/015)
#   authority_gate   -> control.authority.AuthorityGate (structured records only)
#   execution_gate   -> control.execution_gate.authorize_write (path-aware, ADR 0002)
#   verification_gate-> control.verification.VerificationGate
#   recovery_gate    -> control.recovery.RecoveryController (AUTH-INV-12/16)
#
# Every invocation returns the shared GateDecision shape
# (orchestrator.foundation.gates.GateDecision: ALLOW | DENY | ESCALATE), and
# every gate FAILS CLOSED: missing / ambiguous / error inputs -> DENY, never a
# partial allow (AUTH-INV-20).

from __future__ import annotations

import sys

_PROJECT_ROOT = __import__("os").path.dirname(
    __import__("os").path.dirname(
        __import__("os").path.dirname(__import__("os").path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.gates import GateDecision  # noqa: E402


class GateRunner:
    """Deterministic invocation surface over the production control gates.

    Each method takes a context dict (the same shape the underlying control
    module consumes) and returns a GateDecision. A decision is never derived
    from model text, state `approved:true`, a BadSector PASS, or an agent
    message — those are DATA, not authority (AUTH-INV-01/07/09/13/14).
    """

    def __init__(self, *, risk=None, evidence=None, conflict=None,
                 badsector=None, authority=None, execution=None,
                 verification=None, recovery=None):
        from control.risk import RiskClassifier
        from control.evidence import EvidenceGate
        from control.conflict import ConflictGate
        from control.badsector import BadSectorGate
        from control.authority import AuthorityGate as ControlAuthorityGate
        from control.execution_gate import authorize_write, Denied as ExecDenied
        from control.verification import VerificationGate as ControlVerificationGate
        self._risk = risk or RiskClassifier()
        self._evidence = evidence or EvidenceGate()
        self._conflict = conflict or ConflictGate()
        self._badsector = badsector or BadSectorGate()
        self._authority = authority or ControlAuthorityGate()
        self._exec_denied = ExecDenied
        self._authorize_write = authorize_write
        self._verification = verification or ControlVerificationGate()

    # -- risk gate (AUTH-INV-10) --------------------------------------------
    def risk_gate(self, *, action: str = "", target: str = "",
                  environment=None, requires_approval=(),
                  operation_flags=(), tool=None, command=None,
                  declared: str = "LOW") -> GateDecision:
        """Deterministic risk classification. An intrinsic HIGH can NEVER be
        downgraded by model judgment (declared/declared-risk) — a downgrade
        attempt is DENIED (THREAT-011/012)."""
        rc = self._risk.classify(
            action, target, environment, requires_approval=requires_approval,
            operation_flags=operation_flags, tool=tool, command=command,
            declared=declared)
        if rc.intrinsic and (declared or "LOW").upper() != "HIGH":
            return GateDecision(
                "DENY",
                f"intrinsic HIGH cannot be downgraded to {declared or 'LOW'} "
                f"(AUTH-INV-10)",
                "risk_gate", {"risk": "HIGH", "intrinsic": True,
                              "signals": list(rc.signals)})
        return GateDecision(
            "ALLOW", rc.reason or "risk classified", "risk_gate",
            {"risk": rc.level, "intrinsic": rc.intrinsic,
             "signals": list(rc.signals)})

    # -- evidence gate (EVID-001..004) ---------------------------------------
    def evidence_gate(self, *, risk: str = "LOW", claims=(),
                      sources=()) -> GateDecision:
        """Evidence sufficiency ladder (exists -> relevant -> supports ->
        current -> uncontradicted -> sufficient).

        Evidence is OPTIONAL for LOW risk (foundation EvidenceGate semantics).
        MEDIUM without evidence ESCALATEs; HIGH without evidence DENYs
        (EVID-002). When evidence is supplied, the production ladder runs and
        a failed rung DENYs (EVID-001/003) — a fail-closed unknown never
        allows."""
        risk = (risk or "LOW").upper()
        if not sources and risk == "LOW":
            return GateDecision("ALLOW", "LOW risk: evidence optional",
                                "evidence_gate",
                                {"rung": "SUFFICIENT_FOR_ACTION",
                                 "evidence_present": False})
        if not sources and risk == "MEDIUM":
            return GateDecision("ESCALATE", "MEDIUM action: no evidence (EVID-001)",
                                "evidence_gate",
                                {"rung": "SOURCE_EXISTS",
                                 "evidence_present": False})
        if not sources:
            return GateDecision("DENY", "HIGH-risk action requires evidence (EVID-002)",
                                "evidence_gate",
                                {"rung": "SOURCE_EXISTS",
                                 "evidence_present": False})
        verdict = self._evidence.evaluate(claims or (), sources or (),
                                          risk=risk)
        if verdict.accepted:
            return GateDecision("ALLOW", verdict.reason, "evidence_gate",
                                {"rung": verdict.rung_reached,
                                 "evidence_present": True})
        return GateDecision(
            "DENY", verdict.reason or "evidence insufficient (EVID-001)",
            "evidence_gate", {"rung": verdict.rung_reached,
                              "evidence_present": True,
                              "detail": verdict.detail})

    # -- conflict gate (CONF-001..003, no voting) ----------------------------
    def conflict_gate(self, *, outputs=(), risk: str = "LOW",
                      decision_topics=(), evidence_map=None) -> GateDecision:
        """Detect -> material -> inspect evidence -> rework -> synthesize ->
        escalate. Material conflicts ALWAYS escalate; disagreement is never
        resolved by counting (no majority voting)."""
        resolution = self._conflict.resolve(
            outputs, risk=risk, decision_topics=decision_topics,
            evidence_map=evidence_map)
        if resolution.escalated:
            return GateDecision(
                "ESCALATE", resolution.reason, "conflict_gate",
                {"action": resolution.action, "detail": resolution.detail})
        return GateDecision(
            "ALLOW", resolution.reason or "no material conflict",
            "conflict_gate", {"action": resolution.action,
                              "detail": resolution.detail})

    # -- BadSector review gate (THREAT-014/015, AUTH-INV-09) -----------------
    def badsector_review(self, *, risk: str = "LOW", action: str = "",
                         review=None, review_required: bool = False,
                         expected_input_hash: str = "",
                         review_log=(), uncertainty=None,
                         material_conflict: bool = False) -> GateDecision:
        """Mandatory review for HIGH / intrinsic-high / explicit review_required.
        A PASS clears the review stage ONLY — it NEVER authorizes (AUTH-INV-09);
        provenance is verified (review_id + input_hash against the review log)."""
        dec = self._badsector.evaluate(
            risk=risk, action=action, review=review,
            review_required=review_required,
            expected_input_hash=expected_input_hash,
            review_log=review_log, uncertainty=uncertainty,
            material_conflict=material_conflict)
        return GateDecision(dec.decision, dec.reason, "badsector_review",
                            dec.detail)

    # -- authority gate (AUTH-INV-01/05/06/09/13/14) -------------------------
    def authority_gate(self, *, delegation=None, action: str = "",
                       target: str = "", environment=None, actor: str = "orchestrator",
                       project=None, approval_reference: str = "",
                       revocation_list=(), now=None) -> GateDecision:
        """Planning-time authority check. Consumes structured authority records
        ONLY. Missing/invalid delegation -> DENY; approval required -> ESCALATE."""
        return self._authority.evaluate({
            "delegation": delegation, "action": action, "target": target,
            "environment": environment, "actor": actor, "project": project,
            "approval_reference": approval_reference,
            "revocation_list": revocation_list, "now": now,
        })

    # -- execution gate (AUTH-INV-11/12/18, ADR 0002) ------------------------
    def execution_gate(self, *, action: str = "", target: str = "",
                       base=None) -> GateDecision:
        """Path-aware execution gate for writes: protected / outside /
        malformed targets DENY (ADR 0002). Non-write actions ALLOW."""
        try:
            self._authorize_write(action, target, base=base)
            return GateDecision("ALLOW", "", "execution_gate", {})
        except self._exec_denied as e:
            return GateDecision("DENY", str(e), "execution_gate",
                                {"target": target})

    # -- verification gate (AUTH-INV-15, VERIFY-001..003) --------------------
    def verification_gate(self, *, session=None) -> GateDecision:
        """COMPLETE requires a PASSED verification session (reported !=
        verified). DENY when the session has not passed (fail-closed)."""
        if session is None:
            return GateDecision("DENY", "no verification session",
                                "verification_gate", {})
        result = self._verification.evaluate(session)
        if result.is_verified():
            return GateDecision("ALLOW", result.reason, "verification_gate",
                                {"verdict": result.verdict})
        return GateDecision("DENY", result.reason, "verification_gate",
                            {"verdict": result.verdict})

    # -- recovery gate (AUTH-INV-12/16) --------------------------------------
    def recovery_gate(self, *, attempts: int = 0,
                      cause_diagnosed: bool = False,
                      max_attempts: int = 1) -> GateDecision:
        """No blind retry: a recovery attempt without a diagnosed cause, or
        beyond the per-cause attempt cap, DENYs (REC-001, AUTH-INV-16)."""
        if not cause_diagnosed:
            return GateDecision(
                "DENY", "recovery without diagnosis (no blind retry, AUTH-INV-16)",
                "recovery_gate", {"attempts": attempts,
                                  "max_attempts": max_attempts})
        if attempts > max_attempts:
            return GateDecision(
                "DENY", f"max_attempts ({max_attempts}) exceeded; no blind retry "
                        f"(REC-001)",
                "recovery_gate", {"attempts": attempts,
                                  "max_attempts": max_attempts})
        return GateDecision("ALLOW", "", "recovery_gate",
                            {"attempts": attempts,
                             "max_attempts": max_attempts})


__all__ = ["GateRunner"]

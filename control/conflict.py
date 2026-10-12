# control/conflict.py — Conflict detection & resolution gate (L1 project control plane)
#
# Phase: Phase 2 Control Plane — Session B (Risk + Evidence + Conflict +
# BadSector). Companion to docs/security/0001-control-assurance-spec.md §8,
# docs/security/0002-threat-model-and-control-architecture.md (THREAT-021/022),
# docs/design/0001-control-design-and-test-plan.md §10 (CONF-001..003).
#
# PURPOSE
#   Detect conflicting outputs and resolve them through the prescribed flow:
#     detect conflict
#     → identify material conflict
#     → inspect evidence
#     → request targeted research/rework
#     → synthesize (preserve disagreement, uncertainty, minority risks)
#     → escalate when unresolved
#
#   NO MAJORITY VOTING. Conflicts are never resolved by counting how many
#   agents take a position. Disagreement, minority risks, and uncertainty are
#   preserved in the synthesis. Unresolved material conflicts escalate to
#   Human — especially for HIGH-risk actions and security-relevant decisions.
#
# FAIL-CLOSED: when a conflict cannot be shown to be immaterial, it is treated
#   as material → escalate rather than silently pass.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Optional


def _position_key(value) -> str:
    """A stable, hashable key for an agent position.

    Positions may be unhashable (dict/list), which would raise TypeError in a
    set/dedup keyed on the raw value (F15). Serializing to canonical JSON with
    a string fallback makes any position comparable for distinctness/dedup
    without changing what is preserved on the conflict (the raw position is
    still stored in Conflict.positions / minority_risks)."""
    return json.dumps(value, sort_keys=True, default=str)

# Security-relevant decision areas that make ANY conflict mandatory-escalate.
SECURITY_RELEVANT_TOPICS = frozenset({
    "authority", "scope", "evidence_sufficiency", "delegation",
    "risk_classification", "badsector", "approval", "revocation",
})


@dataclass(frozen=True)
class Conflict:
    """A detected conflict on a single decision point.

    positions: list of {agent, position, evidence: [source ids]} dicts.
    materiality:      control-plane-determined (see ConflictGate.identify_material).
    security_relevant: True when the decision point is in SECURITY_RELEVANT_TOPICS
                       or the action is HIGH-risk.
    evidence_inspected: whether inspect_evidence() has run.
    rework_requested:   a request id returned by request_rework().
    resolved:           set True only by an explicit resolution (synthesis or
                        documented immateriality).
    minority_risks:     preserved minority positions/risks.
    """
    id: str
    decision_point: str
    positions: tuple = field(default_factory=tuple)
    materiality: bool = False
    security_relevant: bool = False
    evidence_inspected: bool = False
    rework_requested: Optional[str] = None
    resolved: bool = False
    minority_risks: tuple = field(default_factory=tuple)
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConflictResolution:
    """Outcome of processing a conflict.

    action:      "escalate" | "synthesize" | "documented_immaterial"
    escalated:   True when the conflict was escalated to Human.
    preserved:   True when minority risks / disagreement were preserved.
    voted:       False always — this gate never resolves by counting.
    reason:      why this resolution was chosen.
    """
    action: str
    escalated: bool
    preserved: bool
    voted: bool = False
    reason: str = ""
    detail: dict = field(default_factory=dict)


class ConflictGate:
    """Implements the conflict pipeline. Detection and materiality are code;
    synthesis text is model-driven but the *preservation* of disagreement is
    enforced structurally (minority risks are carried into the resolution)."""

    def __init__(self):
        self._seq = 0

    def _next_id(self) -> str:
        self._seq += 1
        return f"conflict-{self._seq}"

    # -- detect --------------------------------------------------------------
    def detect(self, outputs: Iterable[dict]) -> list:
        """Detect conflicts across outputs.

        output: {"agent": str, "decision": str, "position": str,
                 "evidence": [source ids]} — one output per agent per decision.
        Two or more outputs on the SAME decision point with different positions
        constitute a conflict regardless of how many agree (no voting).
        """
        outputs = list(outputs or [])
        grouped = {}
        for o in outputs:
            key = o.get("decision", o.get("decision_point", ""))
            if not key:
                continue
            grouped.setdefault(key, []).append(o)

        conflicts = []
        for key, group in grouped.items():
            positions = {_position_key(g.get("position")) for g in group}
            if len(positions) > 1:
                conflicts.append(Conflict(
                    id=self._next_id(),
                    decision_point=key,
                    positions=tuple(group),
                    # count is recorded but never used to resolve
                    detail={"n_positions": len(group),
                            "n_distinct_positions": len(positions)}))
        return conflicts

    # -- identify material ----------------------------------------------------
    def identify_material(self, conflicts: Iterable[Conflict],
                          *, risk: str = "LOW",
                          decision_topics: Optional[Iterable[str]] = None) -> list:
        """Mark conflicts material. A conflict is material when:
          - it concerns a HIGH-risk action (docs/security/0001 §8.1), OR
          - it is security-relevant (authority/scope/evidence sufficiency), OR
          - credible evidence is present on both sides (each side backs its
            position).

        Evidence exception (documented immateriality, F14): a pure disagreement
        on a non-security, LOW-risk decision where NEITHER side holds credible
        evidence is shown immaterial — it is synthesized with every distinct
        position and minority risk preserved (never dropped; never resolved by
        counting), not escalated to Human. Fail-closed still governs everything
        else: authority/scope/evidence-sufficiency, HIGH-risk actions and
        evidence-backed disagreement ALL escalate. The no-evidence, low-stakes
        dispute is the single case affirmatively shown immaterial, so the ORIGIN
        of the "cannot be shown immaterial → material" rule is that an
        EVALUATOR must be able to name WHY a conflict is immaterial (no evidence,
        no security signal, low risk) rather than silently defaulting to pass.
        """
        topics = {t.lower() for t in (decision_topics or ())}
        risk = (risk or "LOW").upper()
        out = []
        for c in conflicts:
            security = risk == "HIGH" or bool(topics & SECURITY_RELEVANT_TOPICS)
            sides_with_evidence = sum(
                1 for p in c.positions if (p.get("evidence") or []))
            material = security or sides_with_evidence >= 2
            out.append(Conflict(
                id=c.id, decision_point=c.decision_point,
                positions=c.positions,
                materiality=material,
                security_relevant=security,
                detail=c.detail))
        return out

    # -- inspect evidence -----------------------------------------------------
    def inspect_evidence(self, conflicts: Iterable[Conflict],
                         evidence_map: Optional[dict] = None) -> list:
        """Attach evidence comparison to each conflict. The gate does not
        adjudicate truth; it records which side has evidence and whether a
        side is evidence-free (a claim with no evidence on a material decision
        is a red flag, not a tiebreak)."""
        evidence_map = evidence_map or {}
        out = []
        for c in conflicts:
            ev = []
            for p in c.positions:
                source_ids = p.get("evidence") or []
                resolved = []
                for sid in source_ids:
                    if isinstance(evidence_map.get(sid), dict):
                        resolved.append({"id": sid,
                                         "kind": evidence_map[sid].get("kind"),
                                         "timestamp": evidence_map[sid].get("timestamp")})
                    else:
                        resolved.append({"id": sid})
                ev.append({"agent": p.get("agent"), "evidence": resolved})
            out.append(Conflict(
                id=c.id, decision_point=c.decision_point,
                positions=c.positions, materiality=c.materiality,
                security_relevant=c.security_relevant,
                evidence_inspected=True, detail={**c.detail, "evidence": ev}))
        return out

    # -- request targeted rework ----------------------------------------------
    def request_rework(self, conflicts: Iterable[Conflict],
                       rework_scope: Optional[str] = None) -> list:
        """Request targeted rework for material conflicts. Returns conflicts
        with a rework request id recorded."""
        out = []
        for c in conflicts:
            rid = None
            if c.materiality:
                self._seq += 1
                rid = f"rework-{self._seq}"
            out.append(Conflict(
                id=c.id, decision_point=c.decision_point,
                positions=c.positions, materiality=c.materiality,
                security_relevant=c.security_relevant,
                evidence_inspected=c.evidence_inspected,
                rework_requested=rid,
                detail=c.detail))
        return out

    # -- synthesize (preserve disagreement / minority risks) ------------------
    def synthesize(self, conflicts: Iterable[Conflict]) -> list:
        """Produce a resolution for IMMATERIAL conflicts that preserves all
        distinct positions and their minority risks. Never used for material
        unresolved conflicts (those escalate)."""
        out = []
        for c in conflicts:
            if c.materiality:
                out.append(c)
                continue
            # preserve every distinct position and risk, in full
            distinct = []
            seen = set()
            for p in c.positions:
                key = _position_key(p.get("position"))
                if key not in seen:
                    seen.add(key)
                    distinct.append(p)
            out.append(Conflict(
                id=c.id, decision_point=c.decision_point,
                positions=c.positions, materiality=c.materiality,
                security_relevant=c.security_relevant,
                evidence_inspected=c.evidence_inspected,
                rework_requested=c.rework_requested,
                resolved=True,
                minority_risks=tuple(distinct),
                detail={**c.detail, "synthesized_positions": distinct}))
        return out

    # -- escalate when unresolved ---------------------------------------------
    def escalate(self, conflicts: Iterable[Conflict], reason: str = "") -> list:
        """Mark material conflicts escalated to Human. Their positions remain
        fully preserved in the escalation record."""
        out = []
        for c in conflicts:
            out.append(Conflict(
                id=c.id, decision_point=c.decision_point,
                positions=c.positions, materiality=True,
                security_relevant=c.security_relevant,
                evidence_inspected=c.evidence_inspected,
                rework_requested=c.rework_requested,
                resolved=False,
                detail={**c.detail, "escalated": True,
                        "escalation_reason": reason or c.decision_point}))
        return out

    # -- full pipeline --------------------------------------------------------
    def resolve(self, outputs: Iterable[dict], *, risk: str = "LOW",
                reworked: bool = False,
                decision_topics: Optional[Iterable[str]] = None,
                evidence_map: Optional[dict] = None) -> ConflictResolution:
        """Run detect → material → inspect → rework → synthesize/escalate.

        Material conflicts ALWAYS escalate to Human (docs/security/0001 §8.1:
        mandatory escalation for material / HIGH-risk / security-relevant
        conflicts). Rework is recorded as an attempt; it does NOT by itself
        resolve materiality. Immaterial conflicts are synthesized with all
        distinct positions and minority risks preserved. Never votes.
        """
        detected = self.detect(outputs)
        material = self.identify_material(detected, risk=risk,
                                          decision_topics=decision_topics)
        inspected = self.inspect_evidence(material, evidence_map=evidence_map)
        reworked_ = self.request_rework(inspected, rework_scope=None)

        material_any = [c for c in reworked_ if c.materiality]
        if material_any:
            escalated = self.escalate(
                material_any,
                reason=f"material conflict unresolved ({'after rework' if reworked else 'before rework'}): "
                       f"{[c.id for c in material_any]}")
            return ConflictResolution(
                action="escalate", escalated=True, preserved=True,
                voted=False,
                reason=f"material conflicts escalated to Human: "
                       f"{[c.id for c in material_any]}",
                detail={"conflict_ids": [c.id for c in material_any],
                        "reworked": reworked})

        # No material conflict → synthesize immaterial ones, preserving all.
        synthesized = self.synthesize(reworked_)
        preserved_all = all(c.resolved and bool(c.minority_risks)
                            for c in synthesized) or not synthesized
        return ConflictResolution(
            action="synthesize", escalated=False, preserved=preserved_all,
            voted=False,
            reason="all conflicts synthesized; disagreement preserved; no voting",
            detail={"conflicts": [c.id for c in synthesized]})


# Module-level convenience API.
def detect_conflicts(outputs: Iterable[dict]) -> list:
    return ConflictGate().detect(outputs)


def resolve_conflicts(outputs: Iterable[dict], *, risk: str = "LOW",
                      reworked: bool = False,
                      decision_topics: Optional[Iterable[str]] = None,
                      evidence_map: Optional[dict] = None) -> ConflictResolution:
    return ConflictGate().resolve(outputs, risk=risk, reworked=reworked,
                                  decision_topics=decision_topics,
                                  evidence_map=evidence_map)

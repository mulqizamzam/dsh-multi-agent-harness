# control/evidence.py — Evidence sufficiency gate (L1 project control plane)
#
# Phase: Phase 2 Control Plane — Session B (Risk + Evidence + Conflict +
# BadSector). Companion to docs/security/0001-control-assurance-spec.md §7,
# docs/security/0002-threat-model-and-control-architecture.md §14 (EVID-001..004),
# docs/design/0001-control-design-and-test-plan.md §9.
#
# PURPOSE
#   Enforce the evidence sufficiency ladder:
#     SOURCE EXISTS → RELEVANT → SUPPORTS CLAIM → CURRENT →
#     UNCONTRADICTED → SUFFICIENT FOR ACTION
#   Admission at each rung is code-enforced (the gate decides whether a
#   particular rung is passed). Relevance / confidence may involve model input
#   as metadata, but the gate's admission logic is deterministic code.
#
# KEY INVARIANTS
#   - EVID-001: A claim with no source is unsupported → not accepted.
#   - EVID-002: Source older than the temporal window → not accepted as current.
#   - EVID-003: Two sources that contradict → surfaced, never silently resolved.
#   - EVID-004: Model confidence alone is NEVER sufficient for HIGH.
#
# FAIL-CLOSED: missing timestamp, unreadable source, unresolvable claim→source
#   mapping → rung not passed → evidence not accepted.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Rungs of the evidence ladder (ordered).
# ---------------------------------------------------------------------------
EVIDENCE_RUNGS = (
    "SOURCE_EXISTS",
    "RELEVANT",
    "SUPPORTS_CLAIM",
    "CURRENT",
    "UNCONTRADICTED",
    "SUFFICIENT_FOR_ACTION",
)

# Default temporal window: a source older than this (relative to now) is stale.
DEFAULT_TEMPORAL_WINDOW_DAYS = 180

# Source kinds that qualify as verifiable artifacts for HIGH sufficiency
# (docs/security/0002 §14.2: test/build/runtime/document citation/audit).
ARTIFACT_KINDS = frozenset({
    "artifact", "test", "build", "runtime_health", "document_citation",
    "audit", "log", "measurement", "verification_report",
})


@dataclass(frozen=True)
class EvidenceVerdict:
    """Result of evaluating a set of claims against supporting sources.

    accepted:       True only when all six rungs are satisfied.
    rung_reached:   Name of the highest rung fully satisfied for all claims.
    reason:         Human-readable reason when not accepted.
    unsupported_claims: Claim ids that have no source mapped.
    stale_sources:      Source ids whose timestamp is outside the window.
    contradictions:     List of (source_a, source_b, detail) tuples.
    insufficient_reason: When SUFFICIENT_FOR_ACTION rung fails, the reason.
    detail:             Full per-claim breakdown (for audit).
    """
    accepted: bool
    rung_reached: str = "SOURCE_EXISTS"
    reason: str = ""
    unsupported_claims: tuple = field(default_factory=tuple)
    stale_sources: tuple = field(default_factory=tuple)
    contradictions: tuple = field(default_factory=tuple)
    insufficient_reason: str = ""
    detail: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------
def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        s = value.strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _source_age_days(timestamp: datetime, now: datetime) -> float:
    return (now - timestamp).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# Evidence gate
# ---------------------------------------------------------------------------
class EvidenceGate:
    """Evaluates claims against sources rung by rung. Admission is code.

    Claim shape:  {"id": str, "text": str, "source_ids": [str, ...]}
    Source shape: {"id": str,
                   "timestamp": iso8601/epoch/datetime (required for currency),
                   "relevance": str | None,          # why it bears on the claim
                   "supports": bool | list[str],     # True or claim ids it supports
                   "contradicts": [source_id, ...] | None,  # explicit contradiction
                   "kind": str,                      # artifact kind when present
                   "independent": bool,              # separate origin from the claim
                   "confidence": str | None}         # model metadata ONLY — never
                                                     # sufficient by itself
    """

    def __init__(self, *, temporal_window_days: float = DEFAULT_TEMPORAL_WINDOW_DAYS,
                 now: Optional[datetime] = None):
        self.temporal_window_days = float(temporal_window_days)
        self.now = now or datetime.now(timezone.utc)

    # -- rung 1: SOURCE EXISTS ----------------------------------------------
    def _unsupported(self, claims, sources) -> list:
        source_ids = {s.get("id") for s in sources}
        unsupported = []
        for c in claims:
            mapped = c.get("source_ids") or []
            if not mapped:
                unsupported.append(c.get("id", "?"))
                continue
            if any(sid not in source_ids for sid in mapped):
                unsupported.append(c.get("id", "?"))
        return sorted(set(unsupported))

    # -- rung 2: RELEVANT ----------------------------------------------------
    def _irrelevant(self, claims, sources) -> list:
        """A source that is explicitly irrelevant to the claim fails this rung."""
        irrelevant = []
        by_id = {s.get("id"): s for s in sources}
        for c in claims:
            for sid in (c.get("source_ids") or []):
                s = by_id.get(sid)
                if s is None:
                    continue
                if s.get("relevance") is False or (
                        isinstance(s.get("relevance"), str)
                        and s["relevance"].strip().lower() in ("irrelevant", "none",
                                                               "not applicable")):
                    irrelevant.append(sid)
        return sorted(set(irrelevant))

    # -- rung 3: SUPPORTS CLAIM ---------------------------------------------
    def _non_supporting(self, claims, sources) -> list:
        """A source mapped to a claim must actually support that claim.
        A source with no supports marker does not support the claim."""
        non_supporting = []
        by_id = {s.get("id"): s for s in sources}
        for c in claims:
            for sid in (c.get("source_ids") or []):
                s = by_id.get(sid)
                if s is None:
                    continue
                supports = s.get("supports")
                if supports is True:
                    continue
                if isinstance(supports, (list, tuple, set)):
                    if c.get("id") in supports:
                        continue
                non_supporting.append(sid)
        return sorted(set(non_supporting))

    # -- rung 4: CURRENT ----------------------------------------------------
    def _stale(self, sources) -> list:
        stale = []
        for s in sources:
            ts = _parse_dt(s.get("timestamp"))
            if ts is None:
                # Missing timestamp → cannot establish currency → not current
                # (fail-closed).
                stale.append(s.get("id", "?"))
                continue
            if _source_age_days(ts, self.now) > self.temporal_window_days:
                stale.append(s.get("id", "?"))
        return sorted(set(stale))

    # -- rung 5: UNCONTRADICTED ---------------------------------------------
    def _contradictions(self, sources) -> list:
        """Surface contradictions; never silently resolve them (EVID-003)."""
        found = []
        seen = set()
        by_id = {s.get("id"): s for s in sources}
        for s in sources:
            sid = s.get("id")
            for other in (s.get("contradicts") or []):
                if other in by_id and other != sid:
                    key = tuple(sorted((sid, other)))
                    if key not in seen:
                        seen.add(key)
                        found.append(key + (f"{sid} contradicts {other}",))
        return tuple(found)

    # -- rung 6: SUFFICIENT FOR ACTION --------------------------------------
    def _sufficiency_reason(self, risk: str, claims, sources,
                            supporting_ok: bool) -> Optional[str]:
        """None when sufficient; otherwise a fail reason."""
        risk = (risk or "LOW").upper()
        if not supporting_ok:
            return "supporting evidence missing"

        non_stale = [s for s in sources
                     if s.get("id") not in self._stale(sources)]
        if not non_stale:
            return "no current source"

        if risk == "LOW":
            return None  # one relevant current uncontradicted source is enough

        if risk == "MEDIUM":
            # At least one supporting, current, uncontradicted source;
            # model confidence is not evidence.
            return None

        # HIGH: multiple independent supporting sources OR a verifiable
        # artifact, current, uncontradicted. Model confidence alone is NEVER
        # sufficient (EVID-004).
        artifacts = [s for s in non_stale
                     if str(s.get("kind", "")).lower() in ARTIFACT_KINDS]
        independent = [s for s in non_stale if s.get("independent") is True]
        if artifacts:
            return None
        if len(independent) >= 2:
            return None
        # Confidence metadata never counts as sufficiency:
        confident = [s for s in sources
                     if str(s.get("confidence", "")).lower() in
                     ("high", "very high", "certain")]
        if confident:
            return (f"model confidence alone never sufficient for HIGH "
                    f"(EVID-004): {[s.get('id') for s in confident]}")
        return "HIGH requires an artifact or >=2 independent sources"

    # -- main entry ----------------------------------------------------------
    def evaluate(self, claims: Iterable[dict], sources: Iterable[dict],
                 *, risk: str = "LOW") -> EvidenceVerdict:
        """Evaluate claims against sources. Returns EvidenceVerdict."""
        claims = list(claims or [])
        sources = list(sources or [])
        by_id = {s.get("id"): s for s in sources}

        unsupported = self._unsupported(claims, sources)
        if unsupported:
            return EvidenceVerdict(
                accepted=False, rung_reached="SOURCE_EXISTS",
                reason=f"claims without sources: {unsupported} (EVID-001)",
                unsupported_claims=tuple(unsupported), detail=self._detail(claims, sources))

        irrelevant = self._irrelevant(claims, sources)
        if irrelevant:
            return EvidenceVerdict(
                accepted=False, rung_reached="RELEVANT",
                reason=f"irrelevant sources: {irrelevant}",
                detail=self._detail(claims, sources))

        non_supporting = self._non_supporting(claims, sources)
        if non_supporting:
            return EvidenceVerdict(
                accepted=False, rung_reached="SUPPORTS_CLAIM",
                reason=f"sources do not support their claims: {non_supporting}",
                detail=self._detail(claims, sources))

        stale = self._stale(sources)
        if stale:
            return EvidenceVerdict(
                accepted=False, rung_reached="CURRENT",
                reason=f"stale sources (beyond {self.temporal_window_days}d): "
                       f"{stale} (EVID-002)",
                stale_sources=tuple(stale), detail=self._detail(claims, sources))

        contradictions = self._contradictions(sources)
        if contradictions:
            return EvidenceVerdict(
                accepted=False, rung_reached="UNCONTRADICTED",
                reason=f"contradictory evidence surfaced, not resolved (EVID-003): "
                       f"{[ (a, b) for a, b, _ in contradictions ]}",
                contradictions=contradictions, detail=self._detail(claims, sources))

        insufficient = self._sufficiency_reason(risk, claims, sources,
                                                supporting_ok=True)
        if insufficient:
            return EvidenceVerdict(
                accepted=False, rung_reached="SUFFICIENT_FOR_ACTION",
                reason=insufficient, insufficient_reason=insufficient,
                detail=self._detail(claims, sources))

        return EvidenceVerdict(
            accepted=True, rung_reached="SUFFICIENT_FOR_ACTION",
            reason="evidence sufficient for action",
            detail=self._detail(claims, sources))

    def _detail(self, claims, sources) -> dict:
        return {
            "claims": [{k: c.get(k) for k in ("id", "text", "source_ids")}
                       for c in claims],
            "sources": [{k: s.get(k) for k in ("id", "timestamp", "kind",
                                               "independent", "confidence")}
                        for s in sources],
        }


# Module-level convenience API (mirrors gate use from tests/orchestrators).
def evaluate_evidence(claims: Iterable[dict], sources: Iterable[dict],
                      *, risk: str = "LOW",
                      temporal_window_days: float = DEFAULT_TEMPORAL_WINDOW_DAYS,
                      now: Optional[datetime] = None) -> EvidenceVerdict:
    """One-shot evidence evaluation."""
    return EvidenceGate(temporal_window_days=temporal_window_days,
                        now=now).evaluate(claims, sources, risk=risk)

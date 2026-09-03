"""Evidence gate tests — EVID-001..004, stale, contradiction, negative cases.

Tests the evidence sufficiency ladder in control/evidence.py:
  - EVID-001: unsupported claim → not accepted
  - EVID-002: stale source → not accepted as current
  - EVID-003: contradictory evidence → surfaced, never silently resolved
  - EVID-004: model confidence alone never sufficient for HIGH
  - Negative cases: no source, irrelevant, insufficient, missing timestamp
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from datetime import datetime, timezone, timedelta
from control.evidence import (
    evaluate_evidence,
    EvidenceGate,
    EvidenceVerdict,
    EVIDENCE_RUNGS,
    DEFAULT_TEMPORAL_WINDOW_DAYS,
)


_NOW = datetime.now(timezone.utc)
_FRESH_TS = (_NOW - timedelta(hours=1)).isoformat()
_STALE_TS = (_NOW - timedelta(days=400)).isoformat()


def _claim(claim_id, source_ids, text="claim text"):
    return {"id": claim_id, "text": text, "source_ids": list(source_ids)}


def _source(source_id, *, timestamp=_FRESH_TS, relevance="relevant",
            supports=True, contradicts=None, kind=None, independent=False,
            confidence=None):
    s = {"id": source_id, "timestamp": timestamp, "relevance": relevance,
         "supports": supports}
    if contradicts:
        s["contradicts"] = contradicts
    if kind:
        s["kind"] = kind
    if independent:
        s["independent"] = True
    if confidence:
        s["confidence"] = confidence
    return s


class TestEvidenceBase:
    """EVID-001 — a claim with no source is unsupported → not accepted."""

    def test_evid_001_claim_with_no_source_ids(self):
        v = evaluate_evidence(
            [_claim("c1", [])], [], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "SOURCE_EXISTS"
        assert "c1" in v.unsupported_claims

    def test_evid_001_claim_with_unresolved_source(self):
        v = evaluate_evidence(
            [_claim("c1", ["s1"])], [], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "SOURCE_EXISTS"
        assert "c1" in v.unsupported_claims

    def test_evid_001_claim_with_source_accepted(self):
        v = evaluate_evidence(
            [_claim("c1", ["s1"])],
            [_source("s1")], risk="LOW")
        assert v.accepted
        assert v.rung_reached == "SUFFICIENT_FOR_ACTION"


class TestRelevance:
    """Rung 2 — source must be relevant."""

    def test_irrelevant_source_denied(self):
        s = _source("s1", relevance="irrelevant")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "RELEVANT"

    def test_explicit_none_relevance_denied(self):
        s = _source("s1", relevance="not applicable")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "RELEVANT"


class TestSupportsClaim:
    """Rung 3 — source must support the claim it is mapped to."""

    def test_source_does_not_support_claim(self):
        s = _source("s1", supports=False)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "SUPPORTS_CLAIM"

    def test_source_supports_specific_claim_ids(self):
        s = _source("s1", supports=["c1"])
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert v.accepted

    def test_source_supports_different_claim_not_mapped(self):
        # source supports c2 but c1 is mapped to it
        s = _source("s1", supports=["c2"])
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "SUPPORTS_CLAIM"


class TestStaleEvidence:
    """EVID-002 — source older than the temporal window → not current."""

    def test_evid_002_stale_source_denied(self):
        s = _source("s1", timestamp=_STALE_TS)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "CURRENT"
        assert "s1" in v.stale_sources

    def test_evid_002_fresh_source_accepted(self):
        s = _source("s1", timestamp=_FRESH_TS)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert v.accepted

    def test_evid_002_missing_timestamp_fail_closed(self):
        s = _source("s1", timestamp=None)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "CURRENT"

    def test_evid_002_custom_window(self):
        just_barely = (_NOW - timedelta(days=5)).isoformat()
        s = _source("s1", timestamp=just_barely)
        # 3-day window makes it stale
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW",
                              temporal_window_days=3)
        assert not v.accepted
        assert v.rung_reached == "CURRENT"
        # 10-day window keeps it fresh
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW",
                              temporal_window_days=10)
        assert v.accepted


class TestContradictoryEvidence:
    """EVID-003 — contradictory sources surfaced, never silently resolved."""

    def test_evid_003_contradictory_sources_denied(self):
        sA = _source("a", contradicts=["b"])
        sB = _source("b", contradicts=["a"])
        v = evaluate_evidence([_claim("c1", ["a", "b"])], [sA, sB], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "UNCONTRADICTED"
        assert len(v.contradictions) >= 1

    def test_evid_003_no_contradiction_happy_path(self):
        sA = _source("a")
        sB = _source("b")
        v = evaluate_evidence([_claim("c1", ["a", "b"])], [sA, sB], risk="LOW")
        assert v.accepted

    def test_evid_003_one_sided_contradiction_is_still_a_contradiction(self):
        sA = _source("a", contradicts=["b"])
        sB = _source("b")  # B doesn't contradict back, but A says it does
        v = evaluate_evidence([_claim("c1", ["a", "b"])], [sA, sB], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "UNCONTRADICTED"


class TestConfidenceNotSufficient:
    """EVID-004 — model confidence alone is never sufficient for HIGH."""

    def test_evid_004_high_confidence_alone_denied(self):
        s = _source("s1", confidence="high", kind=None, independent=False)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="HIGH")
        assert not v.accepted
        assert v.rung_reached == "SUFFICIENT_FOR_ACTION"
        assert "confidence" in v.insufficient_reason.lower()

    def test_high_artifact_sufficient(self):
        s = _source("s1", kind="test", independent=True)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="HIGH")
        assert v.accepted

    def test_high_two_independent_sources_sufficient(self):
        sA = _source("a", independent=True)
        sB = _source("b", independent=True)
        v = evaluate_evidence([_claim("c1", ["a", "b"])], [sA, sB], risk="HIGH")
        assert v.accepted

    def test_medium_confidence_alone_ok(self):
        s = _source("s1", confidence="medium")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="MEDIUM")
        assert v.accepted

    def test_low_confidence_alone_ok(self):
        s = _source("s1", confidence="low")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert v.accepted


class TestSufficiencyByRisk:
    """Sufficiency bar varies by risk class."""

    def test_low_one_source_enough(self):
        s = _source("s1")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="LOW")
        assert v.accepted

    def test_medium_needs_supporting_source(self):
        s = _source("s1", supports=True)
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="MEDIUM")
        assert v.accepted

    def test_high_needs_artifact_or_two_independent(self):
        # one independent source, no artifact → not enough
        s = _source("s1", independent=True, kind="report")
        v = evaluate_evidence([_claim("c1", ["s1"])], [s], risk="HIGH")
        assert not v.accepted
        assert v.rung_reached == "SUFFICIENT_FOR_ACTION"


class TestMultipleClaims:
    """Multiple claims with overlapping sources."""

    def test_two_claims_both_supported(self):
        sA = _source("a", independent=True, kind="test")
        sB = _source("b", independent=True, kind="test")
        c1 = _claim("c1", ["a"])
        c2 = _claim("c2", ["b"])
        v = evaluate_evidence([c1, c2], [sA, sB], risk="HIGH")
        assert v.accepted

    def test_one_claim_unsupported_among_several(self):
        sA = _source("a")
        c1 = _claim("c1", ["a"])
        c2 = _claim("c2", [])  # no source
        v = evaluate_evidence([c1, c2], [sA], risk="LOW")
        assert not v.accepted
        assert "c2" in v.unsupported_claims


class TestEvidenceGateClass:
    """Direct EvidenceGate usage."""

    def test_gate_instantiation(self):
        now = datetime.now(timezone.utc)
        gate = EvidenceGate(temporal_window_days=10, now=now)
        s = _source("s1", timestamp=(now - timedelta(hours=1)).isoformat())
        v = gate.evaluate([_claim("c1", ["s1"])], [s], risk="LOW")
        assert v.accepted

    def test_stale_at_custom_window(self):
        now = datetime.now(timezone.utc)
        gate = EvidenceGate(temporal_window_days=1, now=now)
        old = (now - timedelta(days=2)).isoformat()
        s = _source("s1", timestamp=old)
        v = gate.evaluate([_claim("c1", ["s1"])], [s], risk="LOW")
        assert not v.accepted
        assert v.rung_reached == "CURRENT"
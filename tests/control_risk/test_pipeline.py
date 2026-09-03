"""Cross-gate integration tests — Session B modules compose with the reference
authority gate (tests/control_plane.py, read-only) to preserve AUTH-INV-09.

These tests verify that the four Session-B gates compose into a fail-closed
pipeline: even when risk=HIGH, evidence is sufficient, and BadSector PASS has
full provenance, execution is still DENIED without a valid delegation
(AUTH-INV-09 / INV-03). Master Integration will exercise the same composition
against the production control plane.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from control_plane import Deny, authorize  # read-only reference

from control.risk import classify_risk
from control.evidence import evaluate_evidence
from control.conflict import resolve_conflicts
from control.badsector import BadSectorGate, _input_hash


_NOW = datetime.now(timezone.utc)


def _artifact(source_id, **kw):
    s = {"id": source_id,
         "timestamp": (_NOW - timedelta(hours=1)).isoformat(),
         "relevance": "relevant", "supports": True,
         "kind": "test", "independent": True}
    s.update(kw)
    return s


class TestFullPipelineFailClosed:
    """A fully-passing Session-B pipeline still DENIES without authority."""

    def test_high_risk_passed_pipeline_still_denies_without_delegation(self):
        # 1. risk: destructive → intrinsic HIGH
        level, intrinsic = classify_risk("delete", "prod/data", "prod")
        assert level == "HIGH" and intrinsic is True

        # 2. evidence: artifact supports the claim (sufficient for HIGH)
        v = evaluate_evidence(
            [{"id": "c1", "text": "prod data is safe to delete",
              "source_ids": ["s1"]}],
            [_artifact("s1")], risk="HIGH")
        assert v.accepted

        # 3. conflict: none → synthesized, not escalated
        r = resolve_conflicts([], risk="HIGH")
        assert r.escalated is False

        # 4. BadSector: real invocation, full provenance → review cleared
        h = _input_hash({"action": "delete", "target": "prod/data"})
        review = {"review_id": "r1", "verdict": "PASS",
                  "input_hash": h, "agent_id": "badsector"}
        review_log = [{"review_id": "r1", "agent_id": "badsector"}]
        d = BadSectorGate().evaluate(
            risk="HIGH", action="delete", review=review,
            expected_input_hash=h, review_log=review_log)
        assert d.decision == "ALLOW" and d.review_cleared is True

        # 5. Execution WITHOUT delegation → DENY (AUTH-INV-09: PASS is not
        #    authority; the authority gate still decides).
        with pytest.raises(Deny):
            authorize("orchestrator", "delete", "prod/data", None)

    def test_pipeline_denies_when_badsector_skipped(self):
        # Mandatory review skipped → review stage DENY → execution must not
        # proceed (fail-closed composition).
        d = BadSectorGate().evaluate(risk="HIGH", action="delete",
                                      review=None)
        assert d.decision == "DENY"
        with pytest.raises(Deny):
            authorize("orchestrator", "delete", "prod/data", None)

    def test_pipeline_denies_when_evidence_insufficient(self):
        # HIGH risk with model-confidence-only evidence → evidence DENY.
        v = evaluate_evidence(
            [{"id": "c1", "text": "x", "source_ids": ["s1"]}],
            [{"id": "s1", "timestamp": (_NOW - timedelta(hours=1)).isoformat(),
              "relevance": "relevant", "supports": True,
              "confidence": "high"}],
            risk="HIGH")
        assert not v.accepted

    def test_pipeline_denies_when_conflict_material(self):
        outs = [
            {"agent": "a", "decision": "delete-prod", "position": "yes",
             "evidence": ["s1"]},
            {"agent": "b", "decision": "delete-prod", "position": "no",
             "evidence": ["s2"]},
        ]
        r = resolve_conflicts(outs, risk="HIGH")
        assert r.escalated is True  # material conflict → Human escalation
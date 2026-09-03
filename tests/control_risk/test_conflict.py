"""Conflict gate tests — CONF-001..003, THREAT-021/022.

Tests the conflict pipeline in control/conflict.py:
  - CONF-001: conflicts surfaced, no voting, targeted rework path
  - CONF-002: unresolved material conflict on HIGH action → escalate
  - CONF-003: disagreement preserved; minority risks preserved
  - No majority-voting assumption: 2-vs-1 is still a conflict, never resolved
    by counting
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from control.conflict import (
    ConflictGate,
    ConflictResolution,
    resolve_conflicts,
    detect_conflicts,
    SECURITY_RELEVANT_TOPICS,
)


def _output(agent, decision, position, evidence=None):
    o = {"agent": agent, "decision": decision, "position": position}
    if evidence:
        o["evidence"] = list(evidence)
    return o


class TestNoMajorityVoting:
    """CONF-001 core: 2-vs-1 is a conflict, never resolved by counting."""

    def test_two_vs_one_is_still_a_conflict(self):
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "go", ["s2"]),
            _output("c", "deploy", "no-go", ["s3"]),
        ]
        gate = ConflictGate()
        detected = gate.detect(outs)
        # 2 agree, 1 disagrees — still a conflict (counts are irrelevant)
        assert len(detected) == 1
        assert detected[0].decision_point == "deploy"

    def test_unanimous_is_not_a_conflict(self):
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "go", ["s2"]),
            _output("c", "deploy", "go", ["s3"]),
        ]
        detected = ConflictGate().detect(outs)
        assert detected == []

    def test_majority_never_resolves_conflict(self):
        """A material 2-vs-1 conflict escalates — the majority does not win
        by count."""
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "go", ["s2"]),
            _output("c", "deploy", "no-go", ["s3"]),
        ]
        r = resolve_conflicts(outs, risk="HIGH")
        assert r.escalated is True
        assert r.voted is False
        assert r.preserved is True  # both sides preserved in escalation


class TestConflictDetection:
    """CONF-001 — detect → surfaced; never silently resolved."""

    def test_detect_groups_by_decision(self):
        outs = [
            _output("a", "price", "10", ["s1"]),
            _output("b", "price", "12", ["s2"]),
            _output("a", "market", "growing", ["s3"]),
        ]
        detected = ConflictGate().detect(outs)
        assert len(detected) == 1  # only 'price' conflicts
        assert detected[0].decision_point == "price"

    def test_detect_records_positions(self):
        outs = [
            _output("a", "strategy", "expand", ["s1"]),
            _output("b", "strategy", "consolidate", ["s2"]),
        ]
        detected = ConflictGate().detect(outs)
        positions = {p.get("position") for p in detected[0].positions}
        assert positions == {"expand", "consolidate"}

    def test_detect_empty_outputs(self):
        assert ConflictGate().detect([]) == []

    def test_module_level_detect_conflicts(self):
        outs = [
            _output("a", "x", "1"),
            _output("b", "x", "2"),
        ]
        assert len(detect_conflicts(outs)) == 1


class TestMaterialityAndEscalation:
    """CONF-002 — unresolved material conflict → escalate to Human."""

    def test_high_risk_conflict_escalates(self):
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        r = resolve_conflicts(outs, risk="HIGH")
        assert r.action == "escalate"
        assert r.escalated is True

    def test_security_relevant_conflict_escalates(self):
        outs = [
            _output("a", "scope", "include-x", ["s1"]),
            _output("b", "scope", "exclude-x", ["s2"]),
        ]
        r = resolve_conflicts(outs, risk="LOW",
                              decision_topics=["authority"])
        assert r.escalated is True

    def test_material_with_evidence_on_both_sides_escalates(self):
        outs = [
            _output("a", "choice", "A", ["s1"]),
            _output("b", "choice", "B", ["s2"]),
        ]
        r = resolve_conflicts(outs, risk="LOW")
        # both sides have credible evidence → material → escalate
        assert r.action == "escalate"
        assert r.escalated is True

    def test_material_conflict_after_rework_still_escalates(self):
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        r = resolve_conflicts(outs, risk="HIGH", reworked=True)
        assert r.escalated is True  # rework did not resolve it

    def test_escalation_returns_conflict_ids(self):
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        r = resolve_conflicts(outs, risk="HIGH")
        assert r.detail["conflict_ids"]


class TestSynthesisPreservesDisagreement:
    """CONF-003 — disagreement and minority risks preserved; no voting."""

    def test_immaterial_conflict_synthesized_with_minority_preserved(self):
        outs = [
            _output("a", "which-font", "serif"),
            _output("b", "which-font", "sans"),
        ]
        r = resolve_conflicts(outs, risk="LOW")
        assert r.action == "synthesize"
        assert r.escalated is False
        assert r.preserved is True
        assert r.voted is False

    def test_synthesize_keeps_all_distinct_positions(self):
        gate = ConflictGate()
        outs = [
            _output("a", "which-font", "serif"),
            _output("b", "which-font", "sans"),
            _output("c", "which-font", "serif"),  # duplicates don't collapse
        ]
        detected = gate.detect(outs)
        material = gate.identify_material(detected, risk="LOW")
        synthesized = gate.synthesize(material)
        assert synthesized[0].resolved is True
        minority = {p.get("position") for p in synthesized[0].minority_risks}
        assert minority == {"serif", "sans"}

    def test_material_conflict_never_synthesized(self):
        """A material conflict is NOT synthesized away — it escalates."""
        gate = ConflictGate()
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        detected = gate.detect(outs)
        material = gate.identify_material(detected, risk="HIGH")
        synthesized = gate.synthesize(material)
        assert synthesized[0].resolved is False
        assert synthesized[0].materiality is True


class TestConflictPipeline:
    """detect → material → inspect → rework → synthesize/escalate."""

    def test_pipeline_requests_rework_for_material(self):
        gate = ConflictGate()
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        detected = gate.detect(outs)
        material = gate.identify_material(detected, risk="HIGH")
        reworked = gate.request_rework(material)
        assert reworked[0].rework_requested is not None

    def test_pipeline_no_rework_for_immaterial(self):
        gate = ConflictGate()
        outs = [
            _output("a", "which-font", "serif"),
            _output("b", "which-font", "sans"),
        ]
        detected = gate.detect(outs)
        material = gate.identify_material(detected, risk="LOW")
        reworked = gate.request_rework(material)
        assert reworked[0].rework_requested is None

    def test_inspect_evidence_records_sides(self):
        gate = ConflictGate()
        outs = [
            _output("a", "deploy", "go", ["s1"]),
            _output("b", "deploy", "no-go", ["s2"]),
        ]
        detected = gate.detect(outs)
        material = gate.identify_material(detected, risk="LOW")
        evidence_map = {"s1": {"kind": "test", "timestamp": "2026-01-01"},
                        "s2": {"kind": "report", "timestamp": "2026-01-02"}}
        inspected = gate.inspect_evidence(material, evidence_map=evidence_map)
        assert inspected[0].evidence_inspected is True
        agents = {e["agent"] for e in inspected[0].detail["evidence"]}
        assert agents == {"a", "b"}

    def test_resolution_never_votes(self):
        r = resolve_conflicts([], risk="LOW")
        assert isinstance(r, ConflictResolution)
        assert r.voted is False
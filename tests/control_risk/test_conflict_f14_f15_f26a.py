# tests/control_risk/test_conflict_f14_f15_f26a.py — proof/boundary tests.
#
# F15  — unhashable (dict/list) positions must not raise TypeError in detect()
#        (distinctness set) or synthesize() (dedup set); positions still keyed by
#        a stable serialization.
# F26a — detect(decision_points=...) dead parameter removed; passing it now
#        raises TypeError.
# F14  — documented evidence exception pinned: a pure no-evidence, non-security,
#        LOW-risk disagreement is immaterial (synthesized, disagreement
#        preserved); evidence-on-both and security-relevant still escalate.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.conflict import ConflictGate, resolve_conflicts, detect_conflicts


# -- F15 ---------------------------------------------------------------------
def test_f15_dict_positions_no_typeerror_in_detect():
    outs = [
        {"agent": "a", "decision": "d", "position": {"x": 1}, "evidence": ["s1"]},
        {"agent": "b", "decision": "d", "position": {"x": 2}, "evidence": ["s2"]},
    ]
    detected = ConflictGate().detect(outs)   # reverted: TypeError (unhashable)
    assert len(detected) == 1


def test_f15_list_positions_no_typeerror_in_detect():
    outs = [
        {"agent": "a", "decision": "d", "position": [1, 2]},
        {"agent": "b", "decision": "d", "position": [3, 4]},
    ]
    assert len(ConflictGate().detect(outs)) == 1


def test_f15_synthesize_dedups_unhashable_positions():
    gate = ConflictGate()
    outs = [
        {"agent": "a", "decision": "font", "position": {"f": "serif"}},
        {"agent": "b", "decision": "font", "position": {"f": "sans"}},
        {"agent": "c", "decision": "font", "position": {"f": "serif"}},  # dup
    ]
    detected = gate.detect(outs)
    material = gate.identify_material(detected, risk="LOW")
    synthesized = gate.synthesize(material)
    positions = [p.get("position") for p in synthesized[0].minority_risks]
    assert positions == [{"f": "serif"}, {"f": "sans"}]  # dup collapsed, order kept


# -- F26a --------------------------------------------------------------------
def test_f26a_detect_accepts_only_outputs():
    outs = [
        {"agent": "a", "decision": "x", "position": "1"},
        {"agent": "b", "decision": "x", "position": "2"},
    ]
    assert len(ConflictGate().detect(outs)) == 1
    assert len(detect_conflicts(outs)) == 1


def test_f26a_decision_points_param_removed():
    outs = [
        {"agent": "a", "decision": "x", "position": "1"},
        {"agent": "b", "decision": "x", "position": "2"},
    ]
    with pytest.raises(TypeError):
        ConflictGate().detect(outs, decision_points=["x"])
    with pytest.raises(TypeError):
        detect_conflicts(outs, decision_points=["x"])


# -- F14 (documented evidence exception; behavior-pinning boundary) -----------
def test_f14_no_evidence_low_risk_synthesized_immaterial():
    outs = [
        {"agent": "a", "decision": "font", "position": "serif"},
        {"agent": "b", "decision": "font", "position": "sans"},
    ]
    r = resolve_conflicts(outs, risk="LOW")
    assert r.action == "synthesize"
    assert r.escalated is False


def test_f14_evidence_on_both_sides_escalates():
    outs = [
        {"agent": "a", "decision": "c", "position": "A", "evidence": ["s1"]},
        {"agent": "b", "decision": "c", "position": "B", "evidence": ["s2"]},
    ]
    r = resolve_conflicts(outs, risk="LOW")
    assert r.action == "escalate"
    assert r.escalated is True


def test_f14_security_relevant_no_evidence_escalates():
    outs = [
        {"agent": "a", "decision": "scope", "position": "include"},
        {"agent": "b", "decision": "scope", "position": "exclude"},
    ]
    r = resolve_conflicts(outs, risk="LOW", decision_topics=["authority"])
    assert r.escalated is True

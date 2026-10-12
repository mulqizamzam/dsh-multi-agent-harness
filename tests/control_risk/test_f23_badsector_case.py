# tests/control_risk/test_f23_badsector_case.py — F23 proof: BadSectorGate
# review_mandatory normalizes the action case, matching risk.py's classifier.
#
# control/risk.py lowercases the action before classifying; control/badsector.py
# compared it raw, so action="Delete" was HIGH by the risk gate but NOT
# mandatory-review by the BadSector gate.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from control.badsector import BadSectorGate
from control.risk import classify_risk


def test_f23_mixed_case_action_is_mandatory():
    g = BadSectorGate()
    assert g.review_mandatory(risk="LOW", action="Delete") is True
    assert g.review_mandatory(risk="LOW", action="DELETE") is True
    assert g.review_mandatory(risk="LOW", action="  Drop_Database  ") is True


def test_f23_lowcase_read_still_not_mandatory():
    g = BadSectorGate()
    assert g.review_mandatory(risk="LOW", action="delete") is True
    assert g.review_mandatory(risk="LOW", action="read") is False


def test_f23_risk_and_badsector_agree_on_action_case():
    """The two gates must classify the SAME mixed-case action consistently:
    risk.classify_risk lowercases → HIGH/intrinsic; BadSector must also treat it
    as mandatory-review at LOW risk (was False before the fix)."""
    level, intrinsic = classify_risk("Delete", tool="bash")
    assert level == "HIGH" and intrinsic is True
    assert BadSectorGate().review_mandatory(risk="LOW", action="Delete") is True


def test_f23_evaluate_mixed_case_skip_denied():
    d = BadSectorGate().evaluate(risk="LOW", action="Delete", review=None)
    assert d.decision == "DENY"
    assert d.mandatory is True

# tests/audit_hardening/test_authority.py — Audit-as-authority rejection

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from audit.hardening.authority import (
    audit_never_grants, detect_authority_shaped_events,
    assert_no_audit_authority_consumption, AUTHORITY_SHAPED_RESULTS,
)
from tests.audit_hardening.conftest import _write_ledger


def test_audit_never_grants():
    assert audit_never_grants({"result": "APPROVED"}) is False
    assert audit_never_grants({"result": "ALLOWED"}) is False
    assert audit_never_grants({}) is False


def test_authority_shaped_detected(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "event_class": "state_transition",
         "result": "APPROVED", "timestamp": "2026-08-31T00:00:00Z"},
        {"event_id": "e2", "event_class": "flow_finished",
         "result": "GRANTED", "timestamp": "2026-08-31T00:00:01Z"},
    ])
    result = detect_authority_shaped_events(p)
    assert len(result["problems"]) == 2
    assert "APPROVED" in result["problems"][0]["result"]
    assert "GRANTED" in result["problems"][1]["result"]


def test_authority_shaped_absent(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "event_class": "flow_started",
         "result": "recorded", "timestamp": "2026-08-31T00:00:00Z"},
    ])
    assert detect_authority_shaped_events(p)["problems"] == []


def test_assert_no_audit_authority_consumption():
    assert_no_audit_authority_consumption()


def test_authority_shaped_set():
    assert "APPROVED" in AUTHORITY_SHAPED_RESULTS
    assert "ALLOWED" in AUTHORITY_SHAPED_RESULTS
    assert "recorded" not in AUTHORITY_SHAPED_RESULTS
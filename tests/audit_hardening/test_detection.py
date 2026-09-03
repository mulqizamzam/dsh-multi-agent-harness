# tests/audit_hardening/test_detection.py — Truncation / duplicate / ordering

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from audit.hardening.detection import (
    detect_truncation, detect_duplicates, detect_ordering_violation,
)
from tests.audit_hardening.conftest import _write_ledger


def test_truncation_detected(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1"}, {"event_id": "e2"}, {"event_id": "e3"}])
    result = detect_truncation(p, expected_event_ids=["e1", "e2", "e3", "e4"])
    assert result["ok"] is False
    assert result["problems"]


def test_truncation_ok_when_matches(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1"}, {"event_id": "e2"}])
    result = detect_truncation(p, expected_event_ids=["e1", "e2"])
    assert result["ok"] is True


def test_count_mismatch(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1"}, {"event_id": "e2"}])
    result = detect_truncation(p, expected_count=3)
    assert result["ok"] is False


def test_duplicate_detected(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1", "timestamp": "2026-08-31T00:00:00Z"},
                      {"event_id": "e1", "timestamp": "2026-08-31T00:00:01Z"}])
    result = detect_duplicates(p)
    assert result["ok"] is False
    assert "duplicate event_id" in result["problems"][0]


def test_duplicates_ok(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1", "timestamp": "2026-08-31T00:00:00Z"},
                      {"event_id": "e2", "timestamp": "2026-08-31T00:00:01Z"}])
    assert detect_duplicates(p)["ok"] is True


def test_ordering_violation(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1", "timestamp": "2026-08-31T00:00:05Z"},
                      {"event_id": "e2", "timestamp": "2026-08-31T00:00:00Z"}])
    result = detect_ordering_violation(p)
    assert result["ok"] is False
    assert "out-of-order" in result["problems"][0]


def test_ordering_ok(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [{"event_id": "e1", "timestamp": "2026-08-31T00:00:00Z"},
                      {"event_id": "e2", "timestamp": "2026-08-31T00:00:01Z"}])
    assert detect_ordering_violation(p)["ok"] is True


def test_missing_ledger_ok(tmp_path):
    p = os.path.join(str(tmp_path), "nope.jsonl")
    assert detect_truncation(p)["ok"] is True
    assert detect_duplicates(p)["ok"] is True
    assert detect_ordering_violation(p)["ok"] is True
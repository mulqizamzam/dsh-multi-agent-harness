# tests/audit_hardening/test_chain.py — Chain verification

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from audit.hardening.chain import (
    ChainVerificationError, sidecar_exists, verify_chain_with_sidecar,
    recompute_and_compare,
)
from audit.helpers.integrity import compute_chain, chain_path_for


def _write(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")


def test_sidecar_absent_raises(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:00Z"}])
    with pytest.raises(ChainVerificationError):
        verify_chain_with_sidecar(p)


def test_verify_after_compute_ok(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:00Z"},
               {"event_id": "e2", "event_class": "flow_finished",
                "timestamp": "2026-08-31T00:00:01Z"}])
    compute_chain(p)  # establishes the sidecar baseline
    assert sidecar_exists(p)
    events = verify_chain_with_sidecar(p)  # no raise
    assert len(events) == 2


def test_verify_detects_tamper(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:00Z"}])
    compute_chain(p)
    # Tamper: append a new event without updating the chain.
    with open(p, "a") as f:
        f.write(json.dumps({"event_id": "e9", "event_class": "flow_finished",
                            "timestamp": "2026-08-31T00:00:05Z"},
                           sort_keys=True) + "\n")
    with pytest.raises(ChainVerificationError):
        verify_chain_with_sidecar(p)


def test_recompute_and_compare_mismatch(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:00Z"},
               {"event_id": "e2", "event_class": "flow_finished",
                "timestamp": "2026-08-31T00:00:01Z"}])
    compute_chain(p)
    # Tamper the first event's timestamp.
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:09Z"},
               {"event_id": "e2", "event_class": "flow_finished",
                "timestamp": "2026-08-31T00:00:01Z"}])
    result = recompute_and_compare(p)
    assert result["ok"] is False
    assert result["problems"]


def test_recompute_matches_when_unchanged(tmp_path):
    p = os.path.join(str(tmp_path), "events.jsonl")
    _write(p, [{"event_id": "e1", "event_class": "flow_started",
                "timestamp": "2026-08-31T00:00:00Z"}])
    compute_chain(p)
    result = recompute_and_compare(p)
    assert result["ok"] is True


def test_missing_ledger_ok(tmp_path):
    p = os.path.join(str(tmp_path), "nope.jsonl")
    assert verify_chain_with_sidecar(p) == []
    assert recompute_and_compare(p)["ok"] is True
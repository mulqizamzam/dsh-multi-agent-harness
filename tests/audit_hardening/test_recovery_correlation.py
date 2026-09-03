# tests/audit_hardening/test_recovery_correlation.py — Recovery/audit correlation

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from audit.hardening.recovery_correlation import (
    correlate_recovery, find_recovery_chain,
)
from tests.audit_hardening.conftest import _write_ledger


def _recovery_with_execution(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "event_class": "execution_attempt",
         "timestamp": "2026-08-31T00:00:00Z", "task_id": "task-1",
         "result": "error"},
        {"event_id": "e2", "event_class": "recovery",
         "timestamp": "2026-08-31T00:00:01Z", "task_id": "task-1",
         "result": "recovering", "recovery_state": "PRESERVED"},
        {"event_id": "e3", "event_class": "recovery_state_transition",
         "timestamp": "2026-08-31T00:00:02Z", "task_id": "task-1",
         "state": "DIAGNOSED"},
    ])
    return p


def test_recovery_correlated_with_execution(tmp_path):
    p = _recovery_with_execution(tmp_path)
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is True
    assert len(result["recovery_events"]) == 2
    assert len(result["execution_events"]) == 1


def test_recovery_without_execution_is_anomaly(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "event_class": "recovery",
         "timestamp": "2026-08-31T00:00:00Z", "task_id": "task-1",
         "result": "recovering"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is False
    assert result["problems"]


def test_recovery_ordering_anomaly(tmp_path):
    # recovery appears BEFORE any execution event
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "event_class": "recovery",
         "timestamp": "2026-08-31T00:00:00Z", "task_id": "task-1",
         "result": "recovering"},
        {"event_id": "e2", "event_class": "execution_attempt",
         "timestamp": "2026-08-31T00:00:01Z", "task_id": "task-1",
         "result": "error"},
    ])
    result = correlate_recovery(p, task_id="task-1")
    assert result["ok"] is False
    assert any("ordering anomaly" in pr for pr in result["problems"])


def test_find_recovery_chain(tmp_path):
    p = _recovery_with_execution(tmp_path)
    chain = find_recovery_chain(p, task_id="task-1")
    assert len(chain) == 2
    assert [e["event_id"] for e in chain] == ["e2", "e3"]


def test_missing_ledger_ok(tmp_path):
    p = os.path.join(str(tmp_path), "nope.jsonl")
    assert correlate_recovery(p)["ok"] is True
    assert find_recovery_chain(p, "task-1") == []
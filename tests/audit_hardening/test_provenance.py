# tests/audit_hardening/test_provenance.py — Provenance correlation

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from audit.hardening.provenance import (
    check_task_provenance, check_delegation_provenance,
    check_event_sequence_consistency,
)
from tests.audit_hardening.conftest import _write_ledger


def test_task_actor_consistent(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "task_id": "task-1", "actor": "orchestrator",
         "event_class": "x"},
        {"event_id": "e2", "task_id": "task-1", "actor": "orchestrator",
         "event_class": "y"},
    ])
    assert check_task_provenance(p, task_id="task-1")["ok"] is True


def test_task_actor_inconsistent(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "task_id": "task-1", "actor": "orchestrator",
         "event_class": "x"},
        {"event_id": "e2", "task_id": "task-1", "actor": "specialist",
         "event_class": "y"},
    ])
    result = check_task_provenance(p, task_id="task-1")
    assert result["ok"] is False
    assert "actor inconsistency" in result["problems"][0]


def test_delegation_consistent(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "authority_source": "del-a", "event_class": "x"},
        {"event_id": "e2", "authority_source": "del-a", "event_class": "y"},
    ])
    assert check_delegation_provenance(p, delegation_id="del-a")["ok"] is True


def test_delegation_inconsistent(tmp_path):
    p = os.path.join(str(tmp_path), "e.jsonl")
    _write_ledger(p, [
        {"event_id": "e1", "authority_source": "del-a", "event_class": "x"},
        {"event_id": "e2", "authority_source": "del-b", "event_class": "y"},
    ])
    result = check_delegation_provenance(p, delegation_id="del-a")
    assert result["ok"] is True  # only checks del-a events
    result_all = check_delegation_provenance(p)
    assert result_all["ok"] is False


def test_missing_ledger_ok(tmp_path):
    p = os.path.join(str(tmp_path), "nope.jsonl")
    assert check_task_provenance(p)["ok"] is True
    assert check_delegation_provenance(p)["ok"] is True
    assert check_event_sequence_consistency(p)["ok"] is True
"""Audit hardening test fixtures (Phase 5 / Session D)."""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


def _write_ledger(path, events):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for e in events:
            f.write(json.dumps(e, sort_keys=True) + "\n")


@pytest.fixture
def ledger_path(tmp_path):
    p = os.path.join(str(tmp_path), "audit", "proj", "events.jsonl")
    _write_ledger(p, [])
    return p


@pytest.fixture
def sample_events():
    """A small consistent audit event sequence."""
    return [
        {"event_id": "e1", "event_class": "flow_started",
         "timestamp": "2026-08-31T00:00:00Z", "actor": "orchestrator",
         "task_id": None, "result": "recorded"},
        {"event_id": "e2", "event_class": "intake_recorded",
         "timestamp": "2026-08-31T00:00:01Z", "actor": "orchestrator",
         "task_id": "task-1", "result": "recorded"},
        {"event_id": "e3", "event_class": "execution_attempt",
         "timestamp": "2026-08-31T00:00:02Z", "actor": "orchestrator",
         "task_id": "task-1", "authority_source": "delegation-a",
         "result": "executed"},
        {"event_id": "e4", "event_class": "recovery",
         "timestamp": "2026-08-31T00:00:03Z", "actor": "orchestrator",
         "task_id": "task-1", "result": "recovering",
         "recovery_state": "PRESERVED"},
        {"event_id": "e5", "event_class": "recovery_state_transition",
         "timestamp": "2026-08-31T00:00:04Z", "actor": "orchestrator",
         "task_id": "task-1", "state": "DIAGNOSED", "failure_class": "environment"},
        {"event_id": "e6", "event_class": "flow_finished",
         "timestamp": "2026-08-31T00:00:05Z", "actor": "orchestrator",
         "task_id": "task-1", "result": "complete"},
    ]

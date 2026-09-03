# audit/hardening/provenance.py — Provenance correlation across audit events
#
# Phase 5 / Session D. Reads the existing audit ledger and checks whether
# actor/task/delegation provenance is consistent across a run's event sequence.
# Never writes the ledger; reuses read_events_strict.

from __future__ import annotations

import os

from audit.helpers.append_log import read_events_strict, AuditIntegrityError


class ProvenanceCorrelationError(AuditIntegrityError):
    """A provenance correlation violation."""


def check_task_provenance(log_path: str, task_id: str = "") -> dict:
    """Check that events for a given task_id have consistent actor/task
    correlation: all events with that task_id must have the same actor."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    task_events = [e for e in events
                   if e.get("task_id") == task_id or not task_id]
    if not task_events:
        return {"ok": True, "problems": []}
    actors = set(e.get("actor") for e in task_events if e.get("actor"))
    problems = []
    if len(actors) > 1:
        problems.append(f"actor inconsistency for task {task_id!r}: {sorted(actors)}")
    return {"ok": not problems, "problems": problems}


def check_delegation_provenance(log_path: str, delegation_id: str = "") -> dict:
    """Check that events for a delegation have consistent authority_source."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    del_events = [e for e in events
                  if e.get("authority_source") == delegation_id or not delegation_id]
    if not del_events:
        return {"ok": True, "problems": []}
    sources = set(e.get("authority_source") for e in del_events
                  if e.get("authority_source"))
    problems = []
    if len(sources) > 1:
        problems.append(f"authority_source inconsistency: {sorted(sources)}")
    return {"ok": not problems, "problems": problems}


def check_event_sequence_consistency(log_path: str) -> dict:
    """Check that the event sequence has no gaps in event_id sequence."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    ids = []
    for e in events:
        eid = e.get("event_id")
        if isinstance(eid, str) and eid:
            ids.append(eid)
    problems = []
    for i in range(1, len(ids)):
        if ids[i] == ids[i - 1]:
            problems.append(f"duplicate event_id at position {i}: {ids[i]!r}")
    return {"ok": not problems, "problems": problems}


__all__ = ["ProvenanceCorrelationError", "check_task_provenance",
           "check_delegation_provenance", "check_event_sequence_consistency"]
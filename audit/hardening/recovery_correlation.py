# audit/hardening/recovery_correlation.py — Recovery/audit correlation
#
# Phase 5 / Session D. Correlates recovery events with the originating
# execution events in the existing audit ledger, so a recovery lifecycle is
# traceable to the failure that triggered it. Read-only; reuses
# read_events_strict.

from __future__ import annotations

import os
from datetime import datetime, timezone

from audit.helpers.append_log import read_events_strict


class RecoveryCorrelationError(ValueError):
    """A recovery/audit correlation violation."""


def _parse_ts(ts):
    """Parse an ISO-8601 timestamp (with optional Z) to a datetime.

    Returns None when the value is absent or not ISO. Naive values are
    normalized to UTC so mixed naive/aware timestamps stay comparable.
    """
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def correlate_recovery(log_path: str, task_id: str = "") -> dict:
    """Correlate recovery events for a task with the execution events that
    preceded them.

    Returns {ok, problems, recovery_events, execution_events}. A recovery with
    no preceding execution-attempt/denial event for the same task is a
    correlation anomaly.
    """
    if not os.path.exists(log_path):
        return {"ok": True, "problems": [], "recovery_events": [],
                "execution_events": []}
    events = read_events_strict(log_path)
    recovery = [e for e in events
                if e.get("event_class") in ("recovery", "recovery_state_transition")
                and (not task_id or e.get("task_id") == task_id)]
    execution = [e for e in events
                 if e.get("event_class") in ("execution_attempt", "execution_denial",
                                             "subtask_failed")
                 and (not task_id or e.get("task_id") == task_id)]
    problems = []
    if recovery and not execution:
        problems.append(
            f"recovery events for task {task_id or '(any)'!r} have no "
            f"preceding execution event (correlation gap)")
    # Ordering: the first recovery event must come after an execution event.
    # Timestamps are PARSED (not compared as strings) — lexicographic ordering
    # is wrong across offsets, zero-padding, and mixed naive/aware forms.
    if recovery and execution:
        rec_ts = [t for t in (_parse_ts(e.get("timestamp")) for e in recovery)
                  if t is not None]
        exec_ts = [t for t in (_parse_ts(e.get("timestamp")) for e in execution)
                   if t is not None]
        if rec_ts and exec_ts and min(rec_ts) < min(exec_ts):
            problems.append(
                "recovery began before any execution event (ordering anomaly)")
    return {"ok": not problems, "problems": problems,
            "recovery_events": recovery, "execution_events": execution}


def find_recovery_chain(log_path: str, task_id: str) -> list:
    """Return the ordered recovery events for a task (the recovery narrative)."""
    if not os.path.exists(log_path):
        return []
    events = read_events_strict(log_path)
    return [e for e in events
            if e.get("event_class") in ("recovery", "recovery_state_transition")
            and e.get("task_id") == task_id]


__all__ = ["RecoveryCorrelationError", "correlate_recovery", "find_recovery_chain"]
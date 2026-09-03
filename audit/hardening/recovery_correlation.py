# audit/hardening/recovery_correlation.py — Recovery/audit correlation
#
# Phase 5 / Session D. Correlates recovery events with the originating
# execution events in the existing audit ledger, so a recovery lifecycle is
# traceable to the failure that triggered it. Read-only; reuses
# read_events_strict.

from __future__ import annotations

import os

from audit.helpers.append_log import read_events_strict


class RecoveryCorrelationError(ValueError):
    """A recovery/audit correlation violation."""


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
    if recovery and execution:
        first_rec = min(e.get("timestamp", "") for e in recovery)
        first_exec = min(e.get("timestamp", "") for e in execution)
        if first_rec < first_exec:
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
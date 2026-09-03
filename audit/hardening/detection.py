# audit/hardening/detection.py — Truncation / duplicate / replay / ordering
#
# Phase 5 / Session D. Focused detection extensions over the existing
# audit/helpers/append_log.verify_append_only semantics. Never writes the
# ledger; never creates a second audit.

from __future__ import annotations

import os
from datetime import datetime

from audit.helpers.append_log import read_events_strict, AuditIntegrityError


class DetectionError(AuditIntegrityError):
    """A detection failure (truncation / duplicate / replay / ordering)."""


def _parse_ts(ts):
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def detect_truncation(log_path: str, expected_event_ids=None,
                      expected_count=None) -> dict:
    """Truncation detection: compare actual event ids/count against an
    expected baseline (from a prior verified snapshot)."""
    if not os.path.exists(log_path):
        return {"ok": expected_event_ids is None and expected_count is None,
                "problems": [] if expected_event_ids is None and expected_count is None
                else ["ledger missing"]}
    events = read_events_strict(log_path)
    actual_ids = [e.get("event_id") for e in events]
    problems = []
    if expected_event_ids is not None and actual_ids != list(expected_event_ids):
        problems.append(
            f"truncation/reorder: expected {len(expected_event_ids)} ids, "
            f"actual {len(actual_ids)}")
    if expected_count is not None and len(events) != expected_count:
        problems.append(f"count mismatch: expected {expected_count}, actual {len(events)}")
    return {"ok": not problems, "problems": problems}


def detect_duplicates(log_path: str) -> dict:
    """Duplicate / replay event_id detection."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    seen = {}
    problems = []
    for e in events:
        eid = e.get("event_id")
        if eid in seen:
            problems.append(f"duplicate event_id {eid!r} at {seen[eid]} and replay")
        else:
            seen[eid] = e.get("timestamp")
    return {"ok": not problems, "problems": problems}


def detect_ordering_violation(log_path: str) -> dict:
    """Non-decreasing timestamp enforcement (out-of-order detection)."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    prev = None
    problems = []
    for e in events:
        ts = _parse_ts(e.get("timestamp"))
        if ts is None:
            continue
        if prev is not None and ts < prev:
            problems.append(
                f"out-of-order timestamp {e.get('timestamp')!r} (event "
                f"{e.get('event_id')!r}) after {prev.isoformat()}")
        else:
            prev = ts
    return {"ok": not problems, "problems": problems}


__all__ = ["DetectionError", "detect_truncation", "detect_duplicates",
           "detect_ordering_violation"]

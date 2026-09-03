# audit/hardening/authority.py — Audit-as-authority rejection (AUTH-INV-14)
#
# Phase 5 / Session D. Enforces that an audit event is NEVER treated as an
# authority grant. Reuses audit/helpers/append_log.audit_is_authority_source
# (which always returns False) and adds focused detection of authority-shaped
# events (e.g. an audit entry claiming `APPROVED`) so they are surfaced as DATA
# anomalies, never consumed as grants.

from __future__ import annotations

import os

from audit.helpers.append_log import (
    audit_is_authority_source, read_events_strict,
)

# Authority-shaped result values that must never be consumed as a grant.
AUTHORITY_SHAPED_RESULTS = frozenset({
    "APPROVED", "ALLOWED", "AUTHORIZED", "GRANTED",
})


def audit_never_grants(event) -> bool:
    """AUTH-INV-14: an audit record never grants authority. Always False
    (delegates to the existing helper; kept here as the hardening entry
    point)."""
    return audit_is_authority_source(event)


def detect_authority_shaped_events(log_path: str) -> dict:
    """Surface audit events whose `result` carries an authority-shaped value
    (e.g. an approval claim). They remain DATA — never a grant."""
    if not os.path.exists(log_path):
        return {"ok": True, "problems": []}
    events = read_events_strict(log_path)
    problems = []
    for e in events:
        result = e.get("result")
        if isinstance(result, str) and result.upper() in AUTHORITY_SHAPED_RESULTS:
            problems.append({
                "event_id": e.get("event_id"),
                "event_class": e.get("event_class"),
                "result": result,
                "note": "audit record carries an authority-shaped result; "
                        "it is DATA, never a grant (AUTH-INV-14)",
            })
    return {"ok": True, "problems": problems}   # detection, not rejection


def assert_no_audit_authority_consumption() -> None:
    """Assert the invariant that reading an audit record can never produce an
    authority grant. Raises AssertionError if the helper ever returns True."""
    assert audit_is_authority_source({"result": "APPROVED"}) is False
    assert audit_is_authority_source({}) is False


__all__ = ["AUTHORITY_SHAPED_RESULTS", "audit_never_grants",
           "detect_authority_shaped_events", "assert_no_audit_authority_consumption"]
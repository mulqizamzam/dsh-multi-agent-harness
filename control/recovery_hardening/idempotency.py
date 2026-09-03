# control/recovery_hardening/idempotency.py — Recovery idempotency guard
#
# Phase 5 / Session C. Extends the existing recovery controller with a
# double-recovery / terminal-state guard. The existing RecoveryRecord state
# machine already refuses transitions OUT of COMPLETED/FAILED; this module adds
# a durable "recovery already attempted" guard at the CONTROL-PLANE layer so a
# second begin_recovery for the same task is refused even before a record is
# created.
#
# Does NOT duplicate the RecoveryController. Reuses state/helpers/recovery.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from state.helpers.recovery import (
    RecoveryRecord, RecoveryError, RecoveryDenied,
    RECOVERY_STATES,
)

# Terminal states from which a NEW recovery may never begin.
TERMINAL_RECOVERY_STATES = frozenset({"COMPLETED", "FAILED"})


class RecoveryIdempotencyError(RecoveryDenied):
    """A second recovery attempt was refused (fail-closed)."""


def recovery_terminal_state(record: RecoveryRecord) -> str | None:
    """Return 'COMPLETED' or 'FAILED' when the record is terminal, else None."""
    if record.state in TERMINAL_RECOVERY_STATES:
        return record.state
    return None


def assert_no_terminal_recovery(record: RecoveryRecord, *, task_id: str = "") -> None:
    """AUTH-INV-20 / idempotency: refuse a recovery on a record that already
    reached a terminal state. A recovery from COMPLETED or FAILED is never
    valid (the state machine forbids it; this is the control-plane guard)."""
    terminal = recovery_terminal_state(record)
    if terminal is not None:
        raise RecoveryIdempotencyError(
            f"recovery idempotency: task {task_id or record.task_id!r} already "
            f"reached terminal recovery state {terminal!r}; a second recovery "
            f"is refused (no double-recovery)")


def assert_fresh_task_recovery(task_id: str,
                               existing_records: dict | None = None) -> None:
    """Refuse starting a NEW recovery for a task that already has a terminal
    recovery record.

    ``existing_records``: mapping task_id -> RecoveryRecord (or dict with a
    `state` field). When a record for the task is terminal, a fresh recovery is
    refused (idempotency).
    """
    if not existing_records:
        return
    record = existing_records.get(task_id)
    if record is None:
        return
    state = record.state if isinstance(record, RecoveryRecord) else \
        (record.get("state") if isinstance(record, dict) else None)
    if state in TERMINAL_RECOVERY_STATES:
        raise RecoveryIdempotencyError(
            f"recovery idempotency: task {task_id!r} already has a terminal "
            f"recovery record (state {state!r}); refusing a second recovery")


__all__ = [
    "RecoveryIdempotencyError", "TERMINAL_RECOVERY_STATES",
    "recovery_terminal_state", "assert_no_terminal_recovery",
    "assert_fresh_task_recovery",
]

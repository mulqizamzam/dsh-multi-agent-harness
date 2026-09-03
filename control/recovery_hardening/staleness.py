# control/recovery_hardening/staleness.py — Stale recovery detection
#
# Phase 5 / Session C. Extends THREAT-022 stale-state detection at the recovery
# boundary. The existing RecoveryRecord.validate_against_current_version
# already refuses an obsolete plan; this module adds a focused check that a
# recovery begun against version N is not re-executed after the state has
# advanced (or rolled back) — and that the recovery's preserved_version is
# monotonic (no rollback).
#
# Reuses state/helpers/recovery.RecoveryRecord + version_check primitives.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from state.helpers.recovery import RecoveryDenied


class StaleRecoveryError(RecoveryDenied):
    """The recovery plan is stale relative to the current state version."""


def assert_recovery_current(preserved_version: int,
                            current_version: int,
                            *, task_id: str = "") -> None:
    """THREAT-022: refuse a recovery whose preserved_version is behind the
    current state version (state advanced while recovery was prepared)."""
    if preserved_version <= 0 or current_version <= 0:
        return  # untracked versions — rely on the caller's re-validation
    if current_version > preserved_version:
        raise StaleRecoveryError(
            f"stale recovery (THREAT-022): task {task_id!r} preserved version "
            f"{preserved_version} is behind current version {current_version}; "
            f"re-read current state and re-validate authority")
    if current_version < preserved_version:
        raise StaleRecoveryError(
            f"state rollback detected: task {task_id!r} preserved version "
            f"{preserved_version} is ahead of current {current_version}; "
            f"treat as integrity event (Runbook 09/10) until provenance "
            f"established")


def check_recovery_version_drift(record, current_version: int,
                                 *, task_id: str = "") -> None:
    """Convenience: check a RecoveryRecord (or dict) against the current
    version. Reuses preserved_version/current_version fields."""
    if record is None:
        return
    preserved = record.preserved_version if hasattr(record, "preserved_version") \
        else record.get("preserved_version")
    if preserved is None:
        return
    assert_recovery_current(int(preserved), int(current_version),
                            task_id=task_id or getattr(record, "task_id", ""))


__all__ = ["StaleRecoveryError", "assert_recovery_current",
           "check_recovery_version_drift"]

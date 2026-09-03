# control/recovery_hardening/budget.py — Retry budget enforcement
#
# Phase 5 / Session C. AUTH-INV-16 / REC-001 retry-budget guard. The existing
# RecoveryRecord.can_retry + RecoveryController.request_retry already refuse
# blind retries; this module adds a focused, reusable budget tracker so any
# recovery path can enforce max_attempts + max_rework_cycles with a NEW-cause
# requirement without duplicating the controller.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from state.helpers.recovery import RecoveryDenied, DEFAULT_MAX_ATTEMPTS, \
    DEFAULT_MAX_REWORK_CYCLES


class RecoveryBudgetError(RecoveryDenied):
    """A retry budget violation (fail-closed)."""


class RetryBudget:
    """Per-cause retry budget tracker.

    Enforces:
      - no blind retry: a retry requires a NEW diagnosed cause
      - max_attempts per cause
      - max_rework_cycles (re-plan budget)
    """

    def __init__(self, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                 max_rework_cycles: int = DEFAULT_MAX_REWORK_CYCLES):
        self.max_attempts = max_attempts
        self.max_rework_cycles = max_rework_cycles
        self._cause_attempts: dict[str, int] = {}
        self._rework_cycles = 0
        self.diagnosed_cause: str = ""

    def diagnose(self, cause: str) -> None:
        """Record the (new) diagnosed cause. No blind retry: a retry with an
        identical cause is refused."""
        cause = (cause or "").strip()
        if not cause:
            raise RecoveryBudgetError(
                "no blind retry: a retry requires a non-empty diagnosed cause")
        self.diagnosed_cause = cause
        self._cause_attempts[cause] = 0

    def request_retry(self, new_cause: str) -> int:
        """AUTH-INV-16: request a retry with a NEW cause.

        Refuses an identical cause (blind retry) and enforces the per-cause
        attempt cap. Returns the new attempt count.
        """
        new_cause = (new_cause or "").strip()
        if not new_cause:
            raise RecoveryBudgetError(
                "no blind retry: retry requires a non-empty cause")
        if not self.diagnosed_cause:
            raise RecoveryBudgetError(
                "retry requested before any diagnosis (must diagnose first)")
        if new_cause == self.diagnosed_cause:
            raise RecoveryBudgetError(
                "no blind retry: identical cause is not a retry (AUTH-INV-16)")
        attempts = self._cause_attempts.get(self.diagnosed_cause, 0)
        if attempts >= self.max_attempts:
            raise RecoveryBudgetError(
                f"retry budget exhausted: {attempts} attempts >= "
                f"max_attempts {self.max_attempts}")
        self._cause_attempts[new_cause] = 1
        self._cause_attempts[self.diagnosed_cause] = attempts + 1
        self.diagnosed_cause = new_cause
        return self._cause_attempts[self.diagnosed_cause]

    def replan(self) -> None:
        """Track a re-plan (rework) cycle; refuse when the budget is exceeded."""
        if self._rework_cycles >= self.max_rework_cycles:
            raise RecoveryBudgetError(
                f"rework budget exhausted: {self._rework_cycles} cycles >= "
                f"max_rework_cycles {self.max_rework_cycles}")
        self._rework_cycles += 1

    @property
    def attempts(self) -> int:
        return sum(self._cause_attempts.values())

    @property
    def rework_cycles(self) -> int:
        return self._rework_cycles


def new_cause_is_required(diagnosed_cause: str, proposed_cause: str) -> None:
    """AUTH-INV-16 helper: refuse an identical-cause retry."""
    if proposed_cause and proposed_cause.strip() == (diagnosed_cause or "").strip():
        raise RecoveryBudgetError(
            "no blind retry: proposed cause is identical to the diagnosed cause")


__all__ = ["RecoveryBudgetError", "RetryBudget", "new_cause_is_required"]

# tests/recovery_hardening/test_budget.py — Retry budget enforcement

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery_hardening.budget import (
    RecoveryBudgetError, RetryBudget, new_cause_is_required,
)


def test_diagnose_requires_cause():
    b = RetryBudget()
    with pytest.raises(RecoveryBudgetError):
        b.diagnose("  ")


def test_request_retry_requires_prior_diagnosis():
    b = RetryBudget()
    with pytest.raises(RecoveryBudgetError):
        b.request_retry("cause-b")


def test_identical_cause_refused(budget):
    with pytest.raises(RecoveryBudgetError):
        budget.request_retry("cause-a")  # identical cause = blind retry


def test_new_cause_accepted_within_budget(budget):
    assert budget.request_retry("cause-b") == 1
    assert budget.attempts == 2


def test_budget_exhausted():
    b = RetryBudget(max_attempts=1)
    b.diagnose("cause-a")
    # With max_attempts=1, the first new-cause retry is allowed (0 < 1)...
    assert b.request_retry("cause-b") == 1
    # ...and a subsequent retry from cause-b is refused (1 >= 1).
    with pytest.raises(RecoveryBudgetError):
        b.request_retry("cause-c")


def test_rework_cycles_budget():
    b = RetryBudget(max_rework_cycles=1)
    b.replan()
    with pytest.raises(RecoveryBudgetError):
        b.replan()
    assert b.rework_cycles == 1


def test_new_cause_helper():
    new_cause_is_required("cause-a", "cause-b")  # no raise
    with pytest.raises(RecoveryBudgetError):
        new_cause_is_required("cause-a", "cause-a")
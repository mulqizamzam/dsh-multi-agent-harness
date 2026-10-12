# tests/recovery_hardening/test_f11_budget.py — F11 proof: per-cause retry cap
#
# AUTH-INV-16 / REC-001: alternating causes must NOT defeat the per-cause
# attempt cap. request_retry RESET the new cause's counter to 1 on every call,
# so A/B alternation kept both counters below max_attempts forever.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery_hardening.budget import RetryBudget, RecoveryBudgetError


def test_f11_alternating_causes_eventually_hit_per_cause_cap():
    b = RetryBudget(max_attempts=2)
    b.diagnose("A")
    assert b.request_retry("B") == 1   # A->1, B->1
    assert b.request_retry("A") == 2   # A->2, B->2
    # A has now used 2 attempts (== max_attempts). A retry that wakes A again
    # must be refused even though the immediate new cause is "B" elsewhere.
    with pytest.raises(RecoveryBudgetError):
        b.request_retry("B")


def test_f11_cap_is_per_cause_not_reset_by_alternation():
    b = RetryBudget(max_attempts=2)
    b.diagnose("A")
    b.request_retry("B")
    b.request_retry("A")
    # With the fix, both causes accumulated real attempts; neither can be
    # silently restarted below the cap by flipping back and forth.
    with pytest.raises(RecoveryBudgetError):
        b.request_retry("B")
    with pytest.raises(RecoveryBudgetError):
        b.request_retry("A")


def test_f11_same_cause_never_raises_when_within_cap():
    """A well-behaved NEW-cause sequence within the cap still succeeds."""
    b = RetryBudget(max_attempts=5)
    b.diagnose("A")
    assert b.request_retry("B") == 1
    assert b.request_retry("C") == 1

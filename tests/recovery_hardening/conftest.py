"""Recovery hardening test fixtures (Phase 5 / Session C)."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest


@pytest.fixture
def recovery_record():
    from state.helpers.recovery import RecoveryRecord
    rec = RecoveryRecord(task_id="task-rec", preserved_version=1,
                         current_version=1, failure_class="environment")
    rec.preserve(1)
    rec.diagnose("io failure", failure_class="environment")
    return rec


@pytest.fixture
def budget():
    from control.recovery_hardening.budget import RetryBudget
    b = RetryBudget(max_attempts=2, max_rework_cycles=2)
    b.diagnose("cause-a")
    return b

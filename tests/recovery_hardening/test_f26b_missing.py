# tests/recovery_hardening/test_f26b_missing.py — F26b proof: version 0 fails closed
#
# THREAT-022: version 0 means the state document is missing/corrupt
# (read_version returns 0). assert_recovery_current must fail closed on a 0
# version, not silently skip the staleness check.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery_hardening.staleness import (
    StaleRecoveryError, assert_recovery_current, check_recovery_version_drift,
)
from state.helpers.recovery import RecoveryRecord


@pytest.mark.parametrize("preserved,current", [(0, 0), (0, 5), (5, 0)])
def test_f26b_version_zero_fails_closed(preserved, current):
    # On reverted code this returned immediately (no check); the fix raises.
    with pytest.raises(StaleRecoveryError):
        assert_recovery_current(preserved, current, task_id="t")


def test_f26b_check_record_missing_version_refused():
    rec = RecoveryRecord(task_id="t", preserved_version=0, current_version=0)
    with pytest.raises(StaleRecoveryError):
        check_recovery_version_drift(rec, current_version=0, task_id="t")


def test_f26b_positive_versions_still_checked_normally():
    # Guard: the fix only changes the <=0 case; real drift still behaves.
    assert_recovery_current(2, 2, task_id="t")  # equal -> ok, no raise
    with pytest.raises(StaleRecoveryError):
        assert_recovery_current(2, 3, task_id="t")  # state advanced
    with pytest.raises(StaleRecoveryError):
        assert_recovery_current(3, 2, task_id="t")  # rollback

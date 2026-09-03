# tests/recovery_hardening/test_staleness.py — Stale recovery detection

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery_hardening.staleness import (
    StaleRecoveryError, assert_recovery_current, check_recovery_version_drift,
)
from state.helpers.recovery import RecoveryRecord


def test_current_version_matches_ok():
    assert_recovery_current(2, 2, task_id="t")  # no raise


def test_state_advanced_refused():
    with pytest.raises(StaleRecoveryError):
        assert_recovery_current(2, 3, task_id="t")  # current ahead of preserved


def test_state_rolled_back_refused():
    with pytest.raises(StaleRecoveryError):
        assert_recovery_current(3, 2, task_id="t")  # preserved ahead of current


def test_untracked_versions_ok():
    assert_recovery_current(0, 0, task_id="t")  # no raise
    assert_recovery_current(0, 3, task_id="t")  # no raise


def test_check_record_drift():
    rec = RecoveryRecord(task_id="t", preserved_version=1, current_version=1)
    with pytest.raises(StaleRecoveryError):
        check_recovery_version_drift(rec, current_version=2, task_id="t")


def test_check_record_dict():
    rec = {"preserved_version": 1}
    with pytest.raises(StaleRecoveryError):
        check_recovery_version_drift(rec, current_version=2, task_id="t")
    check_recovery_version_drift(rec, current_version=1, task_id="t")


def test_check_none_ok():
    check_recovery_version_drift(None, 2)  # no raise
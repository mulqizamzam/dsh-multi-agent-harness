# tests/recovery_hardening/test_idempotency.py — Recovery idempotency guard

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from state.helpers.recovery import RecoveryRecord
from control.recovery_hardening.idempotency import (
    RecoveryIdempotencyError,
    recovery_terminal_state,
    assert_no_terminal_recovery,
    assert_fresh_task_recovery,
    TERMINAL_RECOVERY_STATES,
)


def _terminal(state):
    rec = RecoveryRecord(task_id="t", state=state, preserved_version=1)
    return rec


def test_terminal_states_identified():
    assert TERMINAL_RECOVERY_STATES == {"COMPLETED", "FAILED"}
    assert recovery_terminal_state(_terminal("COMPLETED")) == "COMPLETED"
    assert recovery_terminal_state(_terminal("FAILED")) == "FAILED"
    assert recovery_terminal_state(_terminal("PRESERVED")) is None
    assert recovery_terminal_state(_terminal("DIAGNOSED")) is None


def test_assert_no_terminal_recovery_completed():
    rec = _terminal("COMPLETED")
    with pytest.raises(RecoveryIdempotencyError):
        assert_no_terminal_recovery(rec, task_id="t")


def test_assert_no_terminal_recovery_failed():
    rec = _terminal("FAILED")
    with pytest.raises(RecoveryIdempotencyError):
        assert_no_terminal_recovery(rec, task_id="t")


def test_assert_no_terminal_recovery_nonterminal_ok():
    rec = _terminal("DIAGNOSED")
    assert_no_terminal_recovery(rec, task_id="t")  # no raise


def test_assert_fresh_task_recovery_existing_terminal():
    records = {"t": _terminal("COMPLETED")}
    with pytest.raises(RecoveryIdempotencyError):
        assert_fresh_task_recovery("t", existing_records=records)


def test_assert_fresh_task_recovery_none_ok():
    assert_fresh_task_recovery("t", existing_records={})  # no raise
    assert_fresh_task_recovery("t", existing_records=None)  # no raise
    assert_fresh_task_recovery("t", existing_records={"other": _terminal("FAILED")})


def test_assert_fresh_task_recovery_dict_record():
    records = {"t": {"state": "FAILED"}}
    with pytest.raises(RecoveryIdempotencyError):
        assert_fresh_task_recovery("t", existing_records=records)


def test_state_machine_forbids_transition_from_terminal():
    """The underlying RecoveryRecord also refuses transitions out of terminal
    states (belt-and-suspenders)."""
    rec = _terminal("COMPLETED")
    with pytest.raises(Exception):
        rec._enter("PRESERVED")
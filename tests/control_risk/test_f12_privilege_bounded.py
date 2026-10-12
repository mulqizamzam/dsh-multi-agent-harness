# tests/control_risk/test_f12_privilege_bounded.py — F12 proof: fail closed on
# empty baseline + action-outside-baseline in RecoveryController.
#
# REC-004 / THREAT-017: recovery must not escalate privilege. Previously the
# action/target checks were `and`-guarded, so an empty baseline made them no-ops
# and ALLOWED anything (the production callers build the baseline FROM the
# attempt — tautological). Now an empty actions/targets baseline fails closed.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.recovery import RecoveryController, RecoveryRefused


def _replanned():
    c = RecoveryController("t-f12", preserved_version=1, failure_class="logic")
    c.diagnose("null pointer dereference", failure_class="logic")
    c.replan()
    return c


def test_f12_empty_baseline_dict_refused():
    # On reverted code, {} allowed everything (empty lists skipped the checks).
    c = _replanned()
    with pytest.raises(RecoveryRefused, match="bounded privilege"):
        c.assert_privilege_bounded(
            attempt_action="rm -rf /", attempt_target="/etc/shadow",
            attempt_grants=("bash",), original_authority={})


def test_f12_empty_actions_list_refused():
    c = _replanned()
    with pytest.raises(RecoveryRefused, match="no actions"):
        c.assert_privilege_bounded(
            attempt_action="write", attempt_target="x",
            original_authority={"actions": [], "targets": ["x"], "grants": []})


def test_f12_empty_targets_list_refused():
    c = _replanned()
    with pytest.raises(RecoveryRefused, match="no targets"):
        c.assert_privilege_bounded(
            attempt_action="write", attempt_target="x",
            original_authority={"actions": ["write"], "targets": [], "grants": []})


def test_f12_action_outside_baseline_refused():
    c = _replanned()
    with pytest.raises(RecoveryRefused, match="privilege escalation"):
        c.assert_privilege_bounded(
            attempt_action="rm -rf /", attempt_target="/etc/shadow",
            attempt_grants=("bash",),
            original_authority={"actions": ["bash"], "targets": ["/tmp"],
                                "grants": []})


def test_f12_within_nonempty_baseline_still_allowed():
    c = _replanned()
    assert c.assert_privilege_bounded(
        attempt_action="write", attempt_target="agents/x.txt",
        original_authority={"actions": ["write"], "targets": ["agents/x.txt"],
                            "grants": []}) is True

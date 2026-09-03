# tests/recovery_hardening/test_recovery_authority.py — Recovery authority
# re-check and no-privilege-expansion hardening

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from state.helpers.recovery import RecoveryRecord
from control.recovery import RecoveryController
from control.recovery_hardening.idempotency import (
    assert_no_terminal_recovery, RecoveryIdempotencyError,
)


class _DenyAllGate:
    """A gate that denies every recovery attempt (authorization failure)."""

    def __call__(self, action, target):
        raise RuntimeError(f"recovery privilege attempt refused: {action} {target}")


class _AllowGate:
    """A gate that allows only the ORIGINAL action/target (AUTH-INV-12)."""

    def __init__(self, allow_actions=("write",), allow_targets=("agents/x.txt",)):
        self.allow_actions = set(allow_actions)
        self.allow_targets = set(allow_targets)

    def __call__(self, action, target):
        if action not in self.allow_actions or target not in self.allow_targets:
            raise RuntimeError(f"recovery out of original authority: {action} {target}")
        return True


def test_recovery_requires_authority_recheck():
    """A recovery that does not re-pass the authority gate must fail (the
    RecoveryRecord refuses to complete without authority_checked)."""
    rec = RecoveryRecord(task_id="t", preserved_version=1)
    rec.preserve(1)
    rec.diagnose("cause", failure_class="environment")
    rec.replan()
    # complete() without authority_rechecked() is refused by the state machine.
    with pytest.raises(Exception):
        rec.complete()
    assert rec.state != "COMPLETED"


def test_recovery_deny_gate_stops(recovery_record):
    """A gate denial during recovery authority re-check stops the recovery
    (no privilege acquisition through recovery)."""
    from control.recovery_hardening.idempotency import TERMINAL_RECOVERY_STATES
    controller = RecoveryController("t", preserved_version=1,
                                    failure_class="environment")
    controller.diagnose("cause", failure_class="environment")
    controller.replan()
    gate = _DenyAllGate()
    with pytest.raises(Exception):
        controller.recheck_authority(
            gate, attempt_action="write", attempt_target="state/registry/x.json",
            attempt_grants=(), original_authority={},
            current_version=1, expected_version=1)
    assert controller.state in TERMINAL_RECOVERY_STATES or controller.state == "REPLANNED"


def test_recovery_allow_gate_within_original_authority():
    """Recovery re-checking the SAME action/target passes (AUTH-INV-12)."""
    controller = RecoveryController("t", preserved_version=1,
                                    failure_class="environment")
    controller.diagnose("cause", failure_class="environment")
    controller.replan()
    gate = _AllowGate(allow_actions=("write",), allow_targets=("agents/x.txt",))
    controller.recheck_authority(
        gate, attempt_action="write", attempt_target="agents/x.txt",
        attempt_grants=(), original_authority={"actions": ["write"],
                                               "targets": ["agents/x.txt"]},
        current_version=1, expected_version=1)
    assert controller.state == "AUTHORITY_RECHECKED"


def test_recovery_no_privilege_expansion():
    """A recovery attempt with a target OUTSIDE the original authority is
    refused (THREAT-017)."""
    controller = RecoveryController("t", preserved_version=1,
                                    failure_class="environment")
    controller.diagnose("cause", failure_class="environment")
    controller.replan()
    gate = _AllowGate(allow_actions=("write",), allow_targets=("agents/x.txt",))
    with pytest.raises(Exception):
        controller.recheck_authority(
            gate, attempt_action="write", attempt_target="state/registry/evil.json",
            attempt_grants=(), original_authority={"actions": ["write"],
                                                   "targets": ["agents/x.txt"]},
            current_version=1, expected_version=1)


def test_recovery_from_terminal_refused():
    rec = RecoveryRecord(task_id="t", state="COMPLETED", preserved_version=1)
    with pytest.raises(RecoveryIdempotencyError):
        assert_no_terminal_recovery(rec, task_id="t")
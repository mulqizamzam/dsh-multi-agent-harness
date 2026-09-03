# orchestrator/execution/exceptions.py — Runtime execution assurance exceptions
#
# Fail-closed: every denial/refusal raises, never returns a partial allow.
# These wrap the existing control-plane exceptions (control.authority.Denied,
# control.recovery.RecoveryRefused, control.verification.VerificationDenied)
# into the execution engine's own hierarchy.
#
# RecoveryRefused is RE-EXPORTED from control.recovery (not redefined) so that
# existing handlers of RecoveryDenied / RecoveryRefused still catch it.

from __future__ import annotations

from control.recovery import RecoveryRefused  # noqa: F401  (re-exported)


class ExecutionError(ValueError):
    """Base runtime execution error (fail-closed)."""


class ExecutionDenied(ExecutionError):
    """Raised when the execution-time authority gate or path gate DENIES the
    action (AUTH-INV-20: any denial stops the action)."""


class ExecutionRefused(ExecutionError):
    """Raised when the execution engine refuses a lifecycle transition, e.g.
    stale plan (THREAT-022), retry budget exhausted, invalid state."""


class VerificationRefused(ExecutionDenied):
    """Raised when COMPLETE is refused because verification has not PASSED
    (AUTH-INV-15 / THREAT-016)."""
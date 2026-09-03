# orchestrator.execution — Runtime Execution Assurance (Phase 3 / Session C)
#
# Binds the EXISTING control-plane modules (control.verification,
# control.recovery, control.authority, control.execution_gate,
# orchestrator.foundation.state, state.helpers.recovery) into a single
# fail-closed RUNTIME execution flow.
#
# Key invariants enforced at runtime (re-using the existing controls, adding no
# new privileges, no DSH modification, no D4/D7 role-boundary change):
#   - A reported success is NOT a verified success (THREAT-016 / AUTH-INV-15)
#   - Execution-time authority re-check (AUTH-INV-05/06/11/18)
#   - No unrestricted execution: every write goes through the same path-aware
#     execution gate the original action used (AUTH-INV-12)
#   - Expected outcome declared BEFORE execution; actual outcome captured AFTER
#     (VERIFY-001/002/003)
#   - COMPLETE emitted only after a PASSED verification verdict
#   - Failure classification -> recovery lifecycle (STOP→PRESERVE→DIAGNOSE→
#     ROLLBACK→VERIFY RESTORATION→REPLAN→AUTHORITY RE-CHECK)
#   - Stale-plan refusal (THREAT-022 / REC-005)
#   - Retry budget with no blind retry (AUTH-INV-16 / REC-001)
#   - Authority re-check after recovery, bounded to the original authority
#     (AUTH-INV-12 / REC-004 / THREAT-017)
#   - Rollback/restore independently verified (REC-003)

from .exceptions import (
    ExecutionError,
    ExecutionDenied,
    ExecutionRefused,
    VerificationRefused,
    RecoveryRefused,
)
from .request import (
    ExecutionRequest,
    WRITE_CLASS_ACTIONS,
)
from .engine import (
    ExecutionEngine,
    ExecutionOutcome,
    classify_failure,
)

__all__ = [
    # exceptions
    "ExecutionError",
    "ExecutionDenied",
    "ExecutionRefused",
    "VerificationRefused",
    "RecoveryRefused",
    # request
    "ExecutionRequest",
    "WRITE_CLASS_ACTIONS",
    # engine
    "ExecutionEngine",
    "ExecutionOutcome",
    "classify_failure",
]

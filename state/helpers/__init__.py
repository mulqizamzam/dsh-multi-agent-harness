# State/audit integrity helpers — Phase 1B (+ hardened Phase 1E / Session B)
#
# Atomic-write, version-check, recovery-state, and append-only audit log
# primitives. These are TEST-SUPPORT and REFERENCE implementations. The
# production control-plane module in a later phase uses the same API contract.
#
# All paths are relative to the project root unless absolute.
# State directory: multi-agent-harness/state/registry/
# Audit directory:  multi-agent-harness/audit/
#
# Phase 1E additions:
#   - atomic_write: StatePathError guard (traversal), JSON pre-check, size cap
#   - compare_and_swap: strict monotonic version enforcement
#   - version_check: validate_version_monotonic / is_stale / assert_current_version
#   - recovery: RecoveryRecord + recovery-state primitives (REC-001..005)

from .atomic_write import (
    atomic_write, safe_read, compare_and_swap, ATOMIC_TEMP_DIR,
    MAX_DOC_BYTES, StatePathError,
)
from .version_check import (
    read_version, bump_version, validate_version_staleness,
    validate_version_monotonic, is_stale, assert_current_version,
    StaleStateError,
)
from .recovery import (
    RecoveryRecord, begin_recovery,
    RECOVERY_STATES, DEFAULT_MAX_ATTEMPTS, DEFAULT_MAX_REWORK_CYCLES,
    RecoveryError, RecoveryDenied,
)

__all__ = [
    # atomic_write
    "atomic_write", "safe_read", "compare_and_swap", "ATOMIC_TEMP_DIR",
    "MAX_DOC_BYTES", "StatePathError",
    # version_check
    "read_version", "bump_version", "validate_version_staleness",
    "validate_version_monotonic", "is_stale", "assert_current_version",
    "StaleStateError",
    # recovery
    "RecoveryRecord", "begin_recovery",
    "RECOVERY_STATES", "DEFAULT_MAX_ATTEMPTS", "DEFAULT_MAX_REWORK_CYCLES",
    "RecoveryError", "RecoveryDenied",
]

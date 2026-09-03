# Recovery-state primitives — state/helpers/recovery.py
#
# Phase 1E / Session B hardening. Implements the recovery-state primitives the
# existing contracts require (security spec §11 Recovery Assurance, design
# doc §19, REC-001..005, AUTH-INV-12/16, THREAT-017/022):
#
#   STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY RESTORATION
#        → REPLAN → AUTHORITY RE-CHECK
#
# Key invariants enforced here:
#   - No blind retry (AUTH-INV-16, REC-001): a retry requires a NEW diagnosed
#     cause; identical-cause attempts beyond max_attempts are refused.
#   - Recovery does NOT acquire privilege automatically (AUTH-INV-12, REC-004):
#     the record never carries tools/grants; the caller must re-pass the same
#     authority path.
#   - Obsolete-version detection (THREAT-022, REC-005): a recovery prepared
#     against an older state version is refused — the caller must re-read the
#     current version and re-validate authority.
#   - Recovery state fields are DATA. Nothing in a RecoveryRecord grants
#     authority; it only records what happened and what is safe to do next.
#
# These primitives are used by the orchestrator state machine
# (orchestrator/foundation/state.py RECOVERING state) and by the control-plane
# recovery gate (tests/unit/test_recovery.py asserts the semantics).

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# The ordered recovery state machine. A recovery must follow this sequence;
# jumping ahead (e.g. VERIFYING_RESTORATION before ROLLING_BACK) is refused.
RECOVERY_STATES = (
    "STOPPED",            # initial: an action failed and was stopped
    "PRESERVED",          # state preserved before any recovery action
    "DIAGNOSED",          # cause classified (environment/logic/authorization)
    "ROLLING_BACK",       # rollback/recover in progress (if appropriate)
    "VERIFYING_RESTORATION",  # verify the rollback actually restored state
    "REPLANNED",          # a new plan (new cause/action) is ready
    "AUTHORITY_RECHECKED",    # authority re-validated against current state
    "COMPLETED",          # recovery finished successfully
    "FAILED",             # recovery failed → escalate to Human
)

# Transitions allowed within the recovery machine (strict order, no skipping
# of consequential phases). Terminal: COMPLETED / FAILED.
_RECOVERY_TRANSITIONS = {
    "STOPPED": {"PRESERVED", "FAILED"},
    "PRESERVED": {"DIAGNOSED", "FAILED"},
    "DIAGNOSED": {"ROLLING_BACK", "REPLANNED", "FAILED"},  # may skip rollback
    "ROLLING_BACK": {"VERIFYING_RESTORATION", "FAILED"},
    "VERIFYING_RESTORATION": {"REPLANNED", "FAILED"},
    "REPLANNED": {"AUTHORITY_RECHECKED", "FAILED"},
    "AUTHORITY_RECHECKED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
}

# Default bounds (design doc §19 / security spec §16.2).
DEFAULT_MAX_ATTEMPTS = 1      # per diagnosed cause; no blind retry
DEFAULT_MAX_REWORK_CYCLES = 2


class RecoveryError(ValueError):
    """Raised when a recovery-state transition is invalid (fail-closed)."""


class RecoveryDenied(RecoveryError):
    """Raised when a recovery action is refused (blind retry / stale version /
    privilege attempt). Mirrors the execution gate's fail-closed Deny."""


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RecoveryRecord:
    """A single task's recovery record. DATA ONLY — never authority
    (AUTH-INV-12/14). Field semantics:

    task_id:            the task under recovery
    state:              current RECOVERY_STATES phase
    attempts:           number of re-execution attempts so far
    diagnosed_cause:    the (single) diagnosed cause; a retry is only allowed
                        after a NEW cause replaces this (AUTH-INV-16)
    preserved_version:  the state version preserved at STOP (for THREAT-022)
    current_version:    the latest known state version
    failure_class:      environment | logic | authorization | unknown
    rollback_performed: bool
    restoration_verified: bool (VERIFY RESTORATION, REC-003)
    authority_checked:  bool (recovery re-passed the authority gate, AUTH-INV-12)
    created_at / updated_at: ISO timestamps
    """
    task_id: str = ""
    state: str = "STOPPED"
    attempts: int = 0
    diagnosed_cause: str = ""
    preserved_version: int = 0
    current_version: int = 0
    failure_class: str = "unknown"
    rollback_performed: bool = False
    restoration_verified: bool = False
    authority_checked: bool = False
    reason: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def __post_init__(self):
        if self.state not in RECOVERY_STATES:
            raise RecoveryError(f"invalid recovery state {self.state!r}")
        if self.attempts < 0:
            raise RecoveryError("attempts must be >= 0")

    # -- state machine -----------------------------------------------------
    def _enter(self, to_state, reason=""):
        allowed = _RECOVERY_TRANSITIONS.get(self.state, set())
        if to_state not in allowed:
            raise RecoveryError(
                f"recovery {self.task_id}: invalid transition {self.state} -> {to_state}")
        self.state = to_state
        if reason:
            self.reason = reason
        self.updated_at = _now_iso()
        return self.state

    def preserve(self, version: int, reason=""):
        """STOP -> PRESERVE. Capture the preserved state version (THREAT-022)."""
        self.preserved_version = version
        self.current_version = version
        return self._enter("PRESERVED", reason)

    def diagnose(self, cause: str, failure_class: str = "unknown", reason=""):
        """PRESERVED -> DIAGNOSED. Requires a non-empty diagnosed cause."""
        cause = (cause or "").strip()
        if not cause:
            raise RecoveryError("diagnosis requires a non-empty cause (no blind retry)")
        if failure_class not in ("environment", "logic", "authorization", "unknown"):
            raise RecoveryError(f"invalid failure_class {failure_class!r}")
        self.diagnosed_cause = cause
        self.failure_class = failure_class
        return self._enter("DIAGNOSED", reason)

    def rollback(self, reason=""):
        """DIAGNOSED -> ROLLING_BACK -> VERIFYING_RESTORATION (when rollback
        applies). Sets rollback_performed."""
        self._enter("ROLLING_BACK", reason)
        self.rollback_performed = True
        return self._enter("VERIFYING_RESTORATION")

    def verify_restoration(self, verified: bool, reason=""):
        """VERIFYING_RESTORATION. Restoration must be independently verified
        before re-planning (REC-003)."""
        if not verified:
            raise RecoveryError("restoration not verified — cannot proceed (REC-003)")
        self.restoration_verified = True
        return self._enter("REPLANNED", reason)

    def replan(self, reason=""):
        """DIAGNOSED -> REPLANNED (skip-rollback path) or
        VERIFYING_RESTORATION -> REPLANNED. A new plan implies a new/diagnosed
        cause is recorded."""
        if not self.diagnosed_cause:
            raise RecoveryError("cannot replan without a diagnosed cause (no blind retry)")
        return self._enter("REPLANNED", reason)

    def authority_rechecked(self, checked: bool = True, reason=""):
        """REPLANNED -> AUTHORITY_RECHECKED. Recovery re-passes the SAME
        authority path; it never acquires privilege automatically
        (AUTH-INV-12, REC-004)."""
        if not checked:
            raise RecoveryError("recovery authority re-check must pass (AUTH-INV-12)")
        self.authority_checked = True
        return self._enter("AUTHORITY_RECHECKED", reason)

    def complete(self, reason=""):
        """AUTHORITY_RECHECKED -> COMPLETED."""
        return self._enter("COMPLETED", reason)

    def fail(self, reason=""):
        """Any state -> FAILED (escalate to Human)."""
        self._enter("FAILED", reason)
        return "FAILED"

    # -- guards ------------------------------------------------------------
    def can_retry(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS,
                  new_cause: str = "") -> bool:
        """AUTH-INV-16 / REC-001: retry allowed only when (a) attempts have not
        reached the per-cause cap AND (b) a NEW diagnosed cause is supplied that
        differs from the previously diagnosed cause. No blind retry."""
        if self.attempts >= max_attempts:
            return False
        cause = (new_cause or "").strip()
        if not cause:
            return False
        return cause != self.diagnosed_cause

    def validate_against_current_version(self, current_version: int,
                                         expected_version: int | None = None):
        """THREAT-022 / REC-005: refuse to execute recovery against an obsolete
        state version.

        If `expected_version` is given, it must match `current_version`.
        The recovery's preserved_version must be <= current_version (recovery
        may roll forward, never re-run a superseded plan on newer state).

        Raises RecoveryDenied on mismatch (fail-closed).
        """
        if expected_version is not None and current_version != expected_version:
            raise RecoveryDenied(
                f"recovery {self.task_id}: expected state version {expected_version} "
                f"but current is {current_version} (THREAT-022)")
        if current_version < self.preserved_version:
            raise RecoveryDenied(
                f"recovery {self.task_id}: current version {current_version} is older "
                f"than preserved {self.preserved_version} (rollback/version conflict)")
        return True

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        allowed = {f for f in (
            "task_id", "state", "attempts", "diagnosed_cause", "preserved_version",
            "current_version", "failure_class", "rollback_performed",
            "restoration_verified", "authority_checked", "reason",
            "created_at", "updated_at")}
        unknown = set(d) - allowed
        if unknown:
            raise RecoveryError(f"unknown RecoveryRecord fields {unknown}")
        return cls(**{k: v for k, v in d.items() if k in allowed})


def begin_recovery(task_id: str, preserved_version: int, failure_class: str = "unknown",
                   reason: str = "") -> RecoveryRecord:
    """STOP + PRESERVE in one call: create a record capturing the state version
    that existed when the action failed (THREAT-022 basis)."""
    rec = RecoveryRecord(task_id=task_id, failure_class=failure_class, reason=reason)
    rec.preserve(preserved_version)
    return rec

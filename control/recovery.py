# control/recovery.py — Recovery control-plane module
#
# Phase 2 / Session C — Verification + Recovery
#
# PURPOSE
#   Enforce the recovery invariants from the security specification, building
#   ON TOP of state/helpers/recovery.RecoveryRecord (which is NOT modified):
#     - AUTH-INV-16 / REC-001 (no blind retry; retry requires a NEW diagnosed
#       cause; identical-cause attempts beyond the cap are refused)
#     - REC-003 (restoration must be INDEPENDENTLY verified before resuming)
#     - THREAT-022 / REC-005 (recovery refuses an obsolete state/plan version;
#       re-validate against the current version)
#     - AUTH-INV-12 (recovery re-passes the SAME authority path before any
#       re-execution; recovery acquires NO additional privilege)
#     - REC-004 / THREAT-017 (a recovery attempt to do what the original
#       couldn't → DENY — no privilege escalation through recovery)
#     - AUTH-INV-20 (any denial stops the recovery action; fail-closed)
#
# The RecoveryRecord provides the strict phase machine:
#   STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY RESTORATION
#        → REPLAN → AUTHORITY RE-CHECK → COMPLETE/FAILED
# This module is the control-plane policy layer around that machine.
#
# REUSE
#   - Imports (read-only) from state/helpers/recovery.py.
#   - Authority re-check flows through the SAME gate the original action used
#     (e.g. control.execution_gate.authorize_write) — passed in by the caller.
#   - Does NOT modify orchestrator/foundation/* or state/helpers/*.

from __future__ import annotations

from dataclasses import dataclass, field

from state.helpers.recovery import (
    RecoveryRecord,
    begin_recovery,
    RecoveryError,
    RecoveryDenied,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_REWORK_CYCLES,
)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RecoveryRefused(RecoveryDenied):
    """A recovery action refused by the control plane (fail-closed).

    Subclasses the underlying RecoveryDenied so existing handlers of
    RecoveryDenied still catch it, while callers can catch the control-plane
    refusal specifically.
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _target_in_any(target: str, patterns: list) -> bool:
    """AUTH-INV-11 style containment: is `target` within any `patterns`
    (with `/**` glob suffix + path-separator boundary, so sibling-prefix
    confusion is prevented)."""
    t = (target or "").rstrip("/")
    for p in patterns:
        r = (p or "").rstrip("/")
        if not r:
            continue
        if r.endswith("/**"):
            prefix = r[:-3].rstrip("/")
            if t == prefix or t.startswith(prefix + "/"):
                return True
        elif t == r or t.startswith(r + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# RecoveryController — control-plane policy layer
# ---------------------------------------------------------------------------

class RecoveryController:
    """Drives a single recovery run on top of a RecoveryRecord, adding the
    control-plane guards:

      1. diagnose(cause)            — PRESERVED → DIAGNOSED (no blind retry)
      2. rollback()                 — DIAGNOSED → ROLLING_BACK → VERIFYING_RESTORATION
      3. verify_restoration(...)    — REC-003: independent restoration proof
      4. replan()                   — → REPLANNED (skip-rollback or after verify)
      5. recheck_authority(...)     — AUTH-INV-12: same gate + version + no
                                      privilege escalation
      6. complete() / fail()        — terminal

    request_retry() is the AUTH-INV-16 guard consulted before authorizing a
    re-execution: it refuses blind retries (identical cause) and enforces the
    per-cause attempt cap.
    """

    def __init__(
        self,
        task_id: str = "",
        preserved_version: int = 0,
        failure_class: str = "unknown",
        reason: str = "",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_rework_cycles: int = DEFAULT_MAX_REWORK_CYCLES,
    ):
        self.record: RecoveryRecord = begin_recovery(
            task_id, preserved_version, failure_class=failure_class, reason=reason)
        self.max_attempts = max_attempts
        self.max_rework_cycles = max_rework_cycles
        self._cause_attempts: dict[str, int] = {}
        self._rework_cycles = 0
        self.attempts_log: list = []          # [{attempt, cause}]
        self.authority_rechecks: list = []    # audit of re-checks (AUTH-INV-12)

    # -- convenience --------------------------------------------------------
    @property
    def state(self) -> str:
        return self.record.state

    def to_dict(self) -> dict:
        return self.record.to_dict()

    # -- phase 1: diagnose --------------------------------------------------
    def diagnose(self, cause: str, failure_class: str = "unknown",
                 reason: str = "") -> str:
        """PRESERVED → DIAGNOSED.  Requires a non-empty diagnosed cause
        (no blind retry, AUTH-INV-16 / REC-001)."""
        cause = (cause or "").strip()
        if not cause:
            raise RecoveryRefused(
                "no blind retry: diagnosis requires a non-empty cause (AUTH-INV-16)")
        return self.record.diagnose(cause, failure_class=failure_class, reason=reason)

    # -- phase 2: rollback / recover ----------------------------------------
    def rollback(self, reason: str = "") -> str:
        """DIAGNOSED → ROLLING_BACK → VERIFYING_RESTORATION (when rollback
        applies)."""
        return self.record.rollback(reason=reason)

    # -- phase 3: verify restoration (REC-003) ------------------------------
    def verify_restoration(self, evidence: str = "", verifier: str = "",
                           reason: str = "") -> str:
        """REC-003: restoration must be verified BEFORE proceeding.

        Requires a non-empty restoration proof AND an independent verifier
        (the executor / self cannot verify its own restoration).  Refuses
        (RecoveryRefused) when either is missing.
        """
        if not (evidence or "").strip():
            raise RecoveryRefused(
                "restoration not verified: no restoration evidence (REC-003)")
        v = (verifier or "").strip()
        if not v:
            raise RecoveryRefused(
                "restoration not verified: no verifier identified (REC-003)")
        vl = v.lower()
        if vl == "self" or vl.startswith("self:") or "executor" in vl:
            raise RecoveryRefused(
                "restoration must be verified INDEPENDENTLY, not by the "
                "executor (REC-003)")
        return self.record.verify_restoration(True, reason=reason)

    # -- phase 4: replan ----------------------------------------------------
    def replan(self, reason: str = "") -> str:
        """→ REPLANNED.

        From DIAGNOSED: skip-rollback path (new plan ready with the diagnosed
        cause).  From VERIFYING_RESTORATION: only after verify_restoration
        succeeded.  Otherwise refused (fail-closed).
        """
        if self.record.state == "DIAGNOSED":
            return self.record.replan(reason=reason)
        if self.record.state == "VERIFYING_RESTORATION":
            raise RecoveryRefused(
                "cannot replan while restoration is unverified (REC-003)")
        raise RecoveryRefused(
            f"cannot replan from state {self.record.state} (recovery machine "
            f"violation)")

    # -- phase 5: authority re-check (AUTH-INV-12) --------------------------
    def assert_current_version(self, current_version: int | None,
                               expected_version: int | None = None) -> bool:
        """THREAT-022 / REC-005: refuse to run recovery against an obsolete
        state version.

        Re-validates the recovery against the CURRENT state version before any
        re-execution.  Raises RecoveryRefused on mismatch (fail-closed).
        """
        if current_version is None:
            raise RecoveryRefused(
                "recovery cannot proceed without the current state version — "
                "re-read current state and re-validate (THREAT-022)")
        try:
            self.record.validate_against_current_version(
                current_version, expected_version)
        except RecoveryDenied as e:
            raise RecoveryRefused(str(e)) from e
        return True

    def assert_privilege_bounded(
        self,
        *,
        attempt_action: str = "",
        attempt_target: str = "",
        attempt_grants=(),
        original_authority: dict | None = None,
    ) -> bool:
        """AUTH-INV-12 / REC-004 / THREAT-017: recovery must NOT acquire
        additional privilege.

        `original_authority` is the structured record of what the ORIGINAL
        action was permitted (dict with keys: actions, targets, grants/tools,
        optionally approval_reference).  The recovery attempt is DENIED when:
          - there is no original baseline (cannot prove bounded → DENY)
          - the attempt's action is outside the original actions
          - the attempt's target is outside the original targets
          - the attempt requests grants/tools beyond the original (or requests
            grants when the original had none)
        """
        if not isinstance(original_authority, dict):
            raise RecoveryRefused(
                "recovery cannot prove bounded privilege: original authority "
                "baseline missing (AUTH-INV-12 / REC-004)")
        allowed_actions = _as_list(
            original_authority.get("actions") or original_authority.get("action"))
        allowed_targets = _as_list(
            original_authority.get("targets") or original_authority.get("target"))
        allowed_grants = _as_list(
            original_authority.get("grants") or original_authority.get("tools"))

        # REC-004 / THREAT-017 fail-closed (F12): an empty actions or targets
        # baseline cannot prove the attempt is bounded — the `and`-guarded checks
        # below would otherwise no-op and ALLOW anything (the two production
        # callers build the baseline FROM the attempt, making it tautological).
        # With no positive baseline there is nothing to compare against, so the
        # recovery cannot demonstrate "no privilege escalation" → DENY.
        if not allowed_actions:
            raise RecoveryRefused(
                "recovery cannot prove bounded privilege: original authority "
                "lists no actions (AUTH-INV-12 / REC-004)")
        if not allowed_targets:
            raise RecoveryRefused(
                "recovery cannot prove bounded privilege: original authority "
                "lists no targets (AUTH-INV-12 / REC-004)")

        if attempt_action and attempt_action not in allowed_actions:
            raise RecoveryRefused(
                f"recovery privilege escalation: action {attempt_action!r} not "
                f"covered by original authority (REC-004 / THREAT-017)")
        if attempt_target and not _target_in_any(
                attempt_target, allowed_targets):
            raise RecoveryRefused(
                f"recovery privilege escalation: target {attempt_target!r} "
                f"outside original authority (REC-004 / THREAT-017)")
        want = set(_as_list(attempt_grants))
        if want:
            if not allowed_grants:
                raise RecoveryRefused(
                    f"recovery privilege escalation: attempt requests grants "
                    f"{sorted(want)} but original authority had none "
                    f"(AUTH-INV-12 / REC-004)")
            extra = want - set(allowed_grants)
            if extra:
                raise RecoveryRefused(
                    f"recovery privilege escalation: attempt requests grants "
                    f"{sorted(extra)} beyond original authority (AUTH-INV-12 / "
                    f"REC-004)")
        return True

    def _repass_gate(self, gate_fn, attempt_action: str, attempt_target: str):
        """Re-pass the SAME authority path the original action used
        (AUTH-INV-12).  Any gate denial or gate error is a DENY (fail-closed)."""
        if not callable(gate_fn):
            raise RecoveryRefused(
                "recovery authority re-check: no authority gate provided "
                "(AUTH-INV-12)")
        try:
            result = gate_fn(attempt_action, attempt_target)
        except Exception as e:  # noqa: BLE001 — gate denial is a DENY
            raise RecoveryRefused(
                f"recovery authority re-check DENIED by the gate: {e} "
                f"(AUTH-INV-12)") from e
        if result is False:
            raise RecoveryRefused(
                "recovery authority re-check DENIED by the gate (returned "
                "False) (AUTH-INV-12)")
        return True

    def recheck_authority(
        self,
        gate_fn,
        *,
        attempt_action: str = "",
        attempt_target: str = "",
        attempt_grants=(),
        original_authority: dict | None = None,
        current_version: int | None = None,
        expected_version: int | None = None,
        reason: str = "",
    ) -> bool:
        """REPLANNED → AUTHORITY_RECHECKED (AUTH-INV-12).

        Before any re-execution, recovery:
          1. re-validates against the CURRENT state version (THREAT-022 /
             REC-005) — an obsolete version DENIES;
          2. verifies the attempt does not escalate privilege beyond the
             original authority (REC-004 / THREAT-017);
          3. re-passes the SAME authority gate (`gate_fn`) with the concrete
             recovery action/target (AUTH-INV-12);
          4. records the re-check on the RecoveryRecord machine.

        Raises RecoveryRefused on any denial (fail-closed, AUTH-INV-20).
        """
        self.assert_current_version(current_version, expected_version)
        self.assert_privilege_bounded(
            attempt_action=attempt_action,
            attempt_target=attempt_target,
            attempt_grants=attempt_grants,
            original_authority=original_authority,
        )
        self._repass_gate(gate_fn, attempt_action, attempt_target)
        self.record.authority_rechecked(True, reason=reason)
        self.authority_rechecks.append({
            "action": attempt_action,
            "target": attempt_target,
            "version": current_version,
            "decision": "ALLOW",
            "reason": reason,
        })
        return True

    # -- phase 6: terminal --------------------------------------------------
    def complete(self, reason: str = "") -> str:
        """AUTHORITY_RECHECKED → COMPLETED."""
        return self.record.complete(reason=reason)

    def fail(self, reason: str = "") -> str:
        """Any state → FAILED (escalate to Human)."""
        return self.record.fail(reason=reason)

    # -- retry guard (AUTH-INV-16 / REC-001) --------------------------------
    def request_retry(self, new_cause: str, max_attempts: int | None = None) -> int:
        """Request a re-execution with a NEW diagnosed cause.

        Refused (RecoveryRefused) when:
          - no/empty cause is supplied (blind retry);
          - the cause is identical to the currently diagnosed cause
            (identical-cause attempts refused — AUTH-INV-16);
          - the attempt cap (max_attempts, default 1 per cause) is exhausted
            (REC-001).

        On success: increments the attempt counter, records the cause, and
        replaces the diagnosed cause (a retry is only on a NEW cause).
        Returns the new attempt count.
        """
        cap = self.max_attempts if max_attempts is None else max_attempts
        cause = (new_cause or "").strip()
        if not cause:
            raise RecoveryRefused(
                "no blind retry: retry requires a NEW diagnosed cause "
                "(AUTH-INV-16)")
        if cause == self.record.diagnosed_cause:
            raise RecoveryRefused(
                f"no blind retry: cause {cause!r} identical to the diagnosed "
                f"cause — a retry needs a NEW cause (AUTH-INV-16)")
        if not self.record.can_retry(cap, cause):
            raise RecoveryRefused(
                f"retry refused: attempts {self.record.attempts} reached cap "
                f"{cap} and/or cause {cause!r} is not new (REC-001)")
        self.record.attempts += 1
        self.record.diagnosed_cause = cause
        self._cause_attempts[cause] = self._cause_attempts.get(cause, 0) + 1
        self.attempts_log.append({"attempt": self.record.attempts, "cause": cause})
        return self.record.attempts


# ---------------------------------------------------------------------------
# Convenience driver for the full recovery cycle
# ---------------------------------------------------------------------------

def execute_recovery(
    *,
    task_id: str,
    preserved_version: int,
    failure_class: str = "unknown",
    cause: str,
    gate_fn,
    attempt_action: str,
    attempt_target: str,
    original_authority: dict,
    current_version: int,
    expected_version: int | None = None,
    attempt_grants=(),
    rollback: bool = False,
    restoration_evidence: str = "",
    restoration_verifier: str = "",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    reason: str = "",
) -> RecoveryController:
    """Run a full recovery to completion and return the controller.

    STOP → PRESERVE → DIAGNOSE → (ROLLBACK → VERIFY RESTORATION) →
    REPLAN → AUTHORITY RE-CHECK → COMPLETE.

    Raises RecoveryRefused/RecoveryError on any denial (fail-closed).  When
    `rollback` is False the skip-rollback path is used.
    """
    ctrl = RecoveryController(
        task_id, preserved_version, failure_class=failure_class,
        reason=reason, max_attempts=max_attempts,
    )
    ctrl.diagnose(cause, failure_class=failure_class, reason=reason)
    if rollback:
        ctrl.rollback(reason=reason)
        ctrl.verify_restoration(
            evidence=restoration_evidence, verifier=restoration_verifier,
            reason=reason,
        )  # -> REPLANNED
    else:
        ctrl.replan(reason=reason)  # skip-rollback path: DIAGNOSED -> REPLANNED
    ctrl.recheck_authority(
        gate_fn,
        attempt_action=attempt_action,
        attempt_target=attempt_target,
        attempt_grants=attempt_grants,
        original_authority=original_authority,
        current_version=current_version,
        expected_version=expected_version,
        reason=reason,
    )
    ctrl.complete(reason=reason)
    return ctrl
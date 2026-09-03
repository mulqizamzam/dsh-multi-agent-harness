# tests/l3_reference/recovery_gate.py — INDEPENDENT recovery-gate reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of recovery
# semantics (no blind retry, bounded attempts, privilege non-escalation,
# obsolete-version refusal). Imports NOTHING from production control modules
# (control/recovery.py, state/helpers/recovery.py).
#
# Controls covered: L3-REC-001..007, L3-XG-009, L3-AUTH-012.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RecoveryVerdict:
    decision: str   # ALLOW | DENY
    reason: str = ""
    gate_under_test: str = "recovery"
    checklist_item_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "checklist_item_results": dict(self.checklist_item_results),
        }


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _target_in_any(target: str, patterns: list) -> bool:
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


def verify_no_blind_retry(*, diagnosed_cause, retry_cause, attempts, max_attempts=1) -> RecoveryVerdict:
    """REC-001 / AUTH-INV-16: no blind retry.

    DENY when:
      - diagnosed_cause or retry_cause is empty (no diagnosis / blind retry);
      - retry_cause is identical to diagnosed_cause (identical-cause retry
        refused — a retry requires a NEW cause);
      - attempts already reached max_attempts.
    """
    dc = (diagnosed_cause or "").strip()
    rc = (retry_cause or "").strip()
    if not dc or not rc:
        return RecoveryVerdict(
            "DENY", "no blind retry: recovery requires a diagnosed cause (AUTH-INV-16)",
            "recovery", {"diagnosed_cause": diagnosed_cause, "retry_cause": retry_cause})
    if rc == dc:
        return RecoveryVerdict(
            "DENY",
            f"no blind retry: retry cause {rc!r} identical to diagnosed cause — "
            f"a retry needs a NEW cause (AUTH-INV-16)",
            "recovery", {"diagnosed_cause": dc, "retry_cause": rc})
    if attempts >= max_attempts:
        return RecoveryVerdict(
            "DENY",
            f"retry refused: attempts {attempts} reached cap {max_attempts} (REC-001)",
            "recovery", {"attempts": attempts, "max_attempts": max_attempts})
    return RecoveryVerdict("ALLOW", "new diagnosed cause, retry within cap",
                           "recovery", {"attempts": attempts})


def verify_privilege_bounded(*, attempt_action="", attempt_target="", attempt_grants=(),
                             original_authority=None) -> RecoveryVerdict:
    """REC-004 / REC-005 / AUTH-INV-12: recovery must NOT acquire additional
    privilege.

    DENY when:
      - original_authority baseline is missing (cannot prove bounded);
      - attempt action outside original actions;
      - attempt target outside original targets;
      - attempt requests grants beyond the original (or any grant when the
        original had none).
    """
    if not isinstance(original_authority, dict):
        return RecoveryVerdict(
            "DENY",
            "recovery cannot prove bounded privilege: original authority baseline "
            "missing (AUTH-INV-12 / REC-004)",
            "recovery", {"original_authority": original_authority})

    allowed_actions = _as_list(original_authority.get("actions") or original_authority.get("action"))
    allowed_targets = _as_list(original_authority.get("targets") or original_authority.get("target"))
    allowed_grants = _as_list(original_authority.get("grants") or original_authority.get("tools"))

    if allowed_actions and attempt_action and attempt_action not in allowed_actions:
        return RecoveryVerdict(
            "DENY",
            f"recovery privilege escalation: action {attempt_action!r} not covered "
            f"by original authority (REC-004 / THREAT-017)",
            "recovery", {"attempt_action": attempt_action,
                         "allowed_actions": allowed_actions})
    if allowed_targets and attempt_target and not _target_in_any(attempt_target, allowed_targets):
        return RecoveryVerdict(
            "DENY",
            f"recovery privilege escalation: target {attempt_target!r} outside "
            f"original authority (REC-004 / THREAT-017)",
            "recovery", {"attempt_target": attempt_target,
                         "allowed_targets": allowed_targets})
    want = set(_as_list(attempt_grants))
    if want:
        if not allowed_grants:
            return RecoveryVerdict(
                "DENY",
                f"recovery privilege escalation: attempt requests grants "
                f"{sorted(want)} but original authority had none (AUTH-INV-12)",
                "recovery", {"attempt_grants": sorted(want)})
        extra = want - set(allowed_grants)
        if extra:
            return RecoveryVerdict(
                "DENY",
                f"recovery privilege escalation: attempt requests grants "
                f"{sorted(extra)} beyond original authority (AUTH-INV-12 / REC-004)",
                "recovery", {"extra_grants": sorted(extra)})
    return RecoveryVerdict("ALLOW", "recovery privilege bounded by original authority",
                           "recovery", {})


def verify_current_version(*, current_version, expected_version=None) -> RecoveryVerdict:
    """REC-005 / THREAT-022: refuse recovery against an obsolete state version.

    DENY when current_version is None (cannot validate) or when an expected
    version is given and it mismatches the current version.
    """
    if current_version is None:
        return RecoveryVerdict(
            "DENY",
            "recovery cannot proceed without the current state version — "
            "re-read current state (THREAT-022)",
            "recovery", {"current_version": current_version})
    if expected_version is not None and expected_version != current_version:
        return RecoveryVerdict(
            "DENY",
            f"recovery uses obsolete state version: expected {expected_version}, "
            f"current {current_version} (THREAT-022)",
            "recovery", {"expected_version": expected_version,
                         "current_version": current_version})
    return RecoveryVerdict("ALLOW", "recovery state version valid",
                           "recovery", {"current_version": current_version})


def verify_restoration(*, evidence, verifier) -> RecoveryVerdict:
    """REC-003: restoration must be verified INDEPENDENTLY before resuming.

    DENY when evidence or verifier is missing, or when the verifier is the
    executor / self.
    """
    if not (evidence or "").strip():
        return RecoveryVerdict("DENY",
                               "restoration not verified: no restoration evidence (REC-003)",
                               "recovery", {"evidence": evidence})
    v = (verifier or "").strip()
    if not v:
        return RecoveryVerdict("DENY",
                               "restoration not verified: no verifier identified (REC-003)",
                               "recovery", {"verifier": verifier})
    vl = v.lower()
    if vl == "self" or vl.startswith("self:") or "executor" in vl:
        return RecoveryVerdict(
            "DENY",
            "restoration must be verified INDEPENDENTLY, not by the executor (REC-003)",
            "recovery", {"verifier": verifier})
    return RecoveryVerdict("ALLOW", "restoration independently verified",
                           "recovery", {"verifier": verifier})


def oracle_recovery(context: dict) -> dict:
    """Wrapper for the verifier."""
    mode = context.get("mode", "no_blind_retry")
    if mode == "privilege":
        v = verify_privilege_bounded(
            attempt_action=context.get("attempt_action", ""),
            attempt_target=context.get("attempt_target", ""),
            attempt_grants=context.get("attempt_grants", ()),
            original_authority=context.get("original_authority"))
    elif mode == "version":
        v = verify_current_version(
            current_version=context.get("current_version"),
            expected_version=context.get("expected_version"))
    elif mode == "restoration":
        v = verify_restoration(evidence=context.get("evidence"),
                               verifier=context.get("verifier"))
    else:
        v = verify_no_blind_retry(
            diagnosed_cause=context.get("diagnosed_cause"),
            retry_cause=context.get("retry_cause"),
            attempts=context.get("attempts", 0),
            max_attempts=context.get("max_attempts", 1))
    return v.to_dict()


__all__ = [
    "RecoveryVerdict",
    "verify_no_blind_retry",
    "verify_privilege_bounded",
    "verify_current_version",
    "verify_restoration",
    "oracle_recovery",
]

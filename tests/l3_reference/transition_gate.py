# tests/l3_reference/transition_gate.py — INDEPENDENT state-transition reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of the
# project state machine (DRAFT → PLANNED → REVIEW_PENDING → APPROVED →
# EXECUTING → VERIFYING → COMPLETE) and its legal-transition graph. Imports
# NOTHING from production control modules or state helpers.
#
# Controls covered: L3-ST-001..008. The oracle is the documented state machine;
# a model writing `status: APPROVED` into a state file is DATA, not a
# transition (AUTH-INV-07/08).

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Legal transition graph (documented state machine).
# A transition (from, to) is legal only when listed here.
# ---------------------------------------------------------------------------
STATES = ("DRAFT", "PLANNED", "REVIEW_PENDING", "APPROVED",
          "EXECUTING", "VERIFYING", "COMPLETE")

LEGAL_TRANSITIONS: frozenset = frozenset({
    ("DRAFT", "PLANNED"),
    ("PLANNED", "REVIEW_PENDING"),
    ("REVIEW_PENDING", "APPROVED"),
    ("APPROVED", "EXECUTING"),
    ("EXECUTING", "VERIFYING"),
    ("VERIFYING", "COMPLETE"),
    # recovery / rollback paths
    ("EXECUTING", "REVIEW_PENDING"),
    ("VERIFYING", "REVIEW_PENDING"),
    ("COMPLETE", "REVIEW_PENDING"),
    ("BLOCKED", "REVIEW_PENDING"),
})


@dataclass(frozen=True)
class TransitionVerdict:
    decision: str   # ALLOW | DENY
    reason: str = ""
    gate_under_test: str = "state_transition"
    checklist_item_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "checklist_item_results": dict(self.checklist_item_results),
        }


def is_legal_transition(from_state: str, to_state: str) -> bool:
    return (from_state, to_state) in LEGAL_TRANSITIONS


def verify_transition(*, from_state, to_state, version=None, expected_version=None,
                      authority_ok=True) -> TransitionVerdict:
    """Independent state-transition oracle.

    DENY when:
      - from/to states are not recognized (fail-closed);
      - the transition is not in the legal graph (SKIPPED_GATE);
      - a version is supplied and it is stale relative to expected_version
        (STALE_OVERWRITE / CAS bypass);
      - the transition is not backed by authority (STATUS_FORGERY — a model
        writing `status: APPROVED` is data, never a transition).
    """
    if from_state not in STATES or to_state not in STATES:
        return TransitionVerdict(
            "DENY",
            f"unknown state(s): {from_state!r} -> {to_state!r} (fail-closed)",
            "state_transition", {"from_state": from_state, "to_state": to_state})

    if not is_legal_transition(from_state, to_state):
        return TransitionVerdict(
            "DENY",
            f"illegal state transition {from_state!r} -> {to_state!r} "
            f"(skipped gate, THREAT-007/021)",
            "state_transition", {"from_state": from_state, "to_state": to_state})

    if expected_version is not None and version is not None and version != expected_version:
        return TransitionVerdict(
            "DENY",
            f"stale version CAS: state version {version} != expected "
            f"{expected_version} (STALE_OVERWRITE)",
            "state_transition", {"version": version,
                                 "expected_version": expected_version})

    if not authority_ok:
        return TransitionVerdict(
            "DENY",
            f"state transition {from_state!r} -> {to_state!r} lacks authority; "
            f"state fields are records, not grants (AUTH-INV-07/08, STATUS_FORGERY)",
            "state_transition", {"from_state": from_state, "to_state": to_state})

    return TransitionVerdict(
        "ALLOW",
        f"legal transition {from_state!r} -> {to_state!r} with authority",
        "state_transition", {"from_state": from_state, "to_state": to_state})


def oracle_transition(context: dict) -> dict:
    """Wrapper for the verifier."""
    v = verify_transition(
        from_state=context.get("from_state"),
        to_state=context.get("to_state"),
        version=context.get("version"),
        expected_version=context.get("expected_version"),
        authority_ok=context.get("authority_ok", True))
    return v.to_dict()


__all__ = [
    "STATES",
    "LEGAL_TRANSITIONS",
    "TransitionVerdict",
    "is_legal_transition",
    "verify_transition",
    "oracle_transition",
]

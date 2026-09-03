# orchestrator.foundation.state — Minimal state model + transitions (Phase 1D,
# hardened Phase 1E / Session B)
#
# Minimum state model required by the Orchestrator foundation. Model text alone
# must NEVER mutate consequential state (AUTH-INV-07): every transition that
# changes lifecycle state requires an explicit, structured authority token
# (a Delegation object or a Human approval reference) supplied by the caller.
#
# Phase 1E hardening:
#   - CLOSED THE TEXT-AUTHORITY HOLE: a bare non-empty string is no longer
#     accepted as authority. Only a structured `Delegation` object, a
#     `RecoveryRecord` object (for RECOVERING), or a string that matches the
#     strict `approval-<id>` reference pattern is accepted. Free text such as
#     "Human approved X" is REFUSED (AUTH-INV-01: no authority from model
#     text).
#   - VERSION-AWARE TRANSITIONS: each StateMachine carries a monotonic
#     `version` that increments on every transition; `transition()` accepts an
#     optional `expected_version` and refuses a stale machine (THREAT-021/022).
#     ProjectState.transition() does the same at the project-document level.
#   - TRANSITION HISTORY: every transition is recorded (from, to, actor,
#     version) so each state change is audit-ready.
#   - RECOVERY INTEGRATION: entering RECOVERING accepts a
#     state.helpers.recovery.RecoveryRecord as the authority/context token.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from .contracts import Delegation

# Lifecycle states (failure states are Human-visible terminal/suspension):
#   DRAFT      intake recorded, not actionable without authority context
#   PLANNED    decomposed + routed
#   DELEGATED  scoped delegation issued to specialist(s)
#   EXECUTING  work in flight
#   COLLECTED  results gathered
#   SYNTHESIZING  cross-agent synthesis
#   COMPLETE   verification passed
#   BLOCKED / FAILED / ESCALATED / RECOVERING  (failure / suspension)
INITIAL_STATE = "DRAFT"
TERMINAL_STATES = {"COMPLETE", "BLOCKED", "FAILED", "ESCALATED"}

# Allowed transitions (source -> set of dest). Consequential transitions from
# DRAFT/PLANNED into DELEGATED/EXECUTING require authority.
_TRANSITIONS = {
    "DRAFT": {"PLANNED", "BLOCKED", "FAILED", "ESCALATED"},
    "PLANNED": {"DELEGATED", "BLOCKED", "FAILED", "ESCALATED", "DRAFT"},
    "DELEGATED": {"EXECUTING", "BLOCKED", "FAILED", "ESCALATED", "RECOVERING"},
    "EXECUTING": {"COLLECTED", "BLOCKED", "FAILED", "ESCALATED", "RECOVERING"},
    "COLLECTED": {"SYNTHESIZING", "BLOCKED", "FAILED", "ESCALATED"},
    "SYNTHESIZING": {"COMPLETE", "BLOCKED", "FAILED", "ESCALATED", "RECOVERING"},
    "RECOVERING": {"DELEGATED", "PLANNED", "DRAFT", "BLOCKED", "FAILED", "ESCALATED"},
    "COMPLETE": set(),
    "BLOCKED": set(),
    "FAILED": set(),
    "ESCALATED": set(),
}

# States that require an authority token to enter.
AUTHORITY_REQUIRED_DESTS = {"PLANNED", "DELEGATED", "EXECUTING", "RECOVERING"}

# The ONLY free-text authority form accepted: a Human approval reference
# (approval-<id>). Free prose ("Human approved X", "I am authorized") is
# refused — no authority from model text (AUTH-INV-01). Delegation references
# must be passed as actual Delegation objects, never as bare strings.
_APPROVAL_REF_RE = re.compile(r"^approval-[A-Za-z0-9-]+$")


class StateTransitionError(ValueError):
    pass


def _structured_authority_ok(authority, to_state) -> bool:
    """True only when `authority` is a STRUCTURED authority token.

    Accepts:
      - Delegation object (the scoped authority record)
      - RecoveryRecord object, but ONLY for the RECOVERING transition
      - a string matching the strict approval-reference pattern
        `approval-<id>` (a Human approval reference, verified by the caller)

    Rejects:
      - None
      - any other free text (model claims, "Human approved", etc.)
    """
    if isinstance(authority, Delegation):
        return True
    if isinstance(authority, str):
        return bool(_APPROVAL_REF_RE.match(authority.strip()))
    if to_state == "RECOVERING":
        # Lazy import: recovery primitives live in state/helpers/recovery.py.
        # A missing/incompatible module must not weaken the check — an unknown
        # object type simply fails closed (not authorized).
        try:
            from state.helpers.recovery import RecoveryRecord
        except ImportError:
            return False
        return isinstance(authority, RecoveryRecord)
    return False


class StateMachine:
    """A single task's lifecycle state. The orchestrator is the single caller;
    the record is persisted through the project execution channel (not raw
    DSH writes).

    version: per-machine monotonic counter, incremented on every transition.
    history: ordered list of {from, to, actor, version} transition records
             (audit-ready; each transition is a state change the control plane
             must mirror in the audit ledger).
    """

    def __init__(self, task_id: str, initial: str = INITIAL_STATE):
        self.task_id = task_id
        self.state = initial
        self.version = 1
        self.history: list = []

    def current(self) -> str:
        return self.state

    def current_version(self) -> int:
        return self.version

    def transition(self, to_state: str, authority=None, actor="orchestrator",
                   expected_version=None):
        """Transition `to_state`.

        Consequential transitions require a STRUCTURED authority token
        (Delegation / RecoveryRecord for RECOVERING / approval-reference
        string). Model text is never authority (AUTH-INV-01).

        expected_version: optional CAS — if given and != self.version the
        transition is refused (stale machine, THREAT-021/022).

        Raises StateTransitionError on invalid/unconsequential transition or
        on a stale expected_version.
        """
        if expected_version is not None and expected_version != self.version:
            raise StateTransitionError(
                f"{self.task_id}: stale machine version {self.version} != "
                f"expected {expected_version} (THREAT-021/022)")
        if to_state not in _TRANSITIONS.get(self.state, set()):
            raise StateTransitionError(
                f"{self.task_id}: invalid transition {self.state} -> {to_state}")
        if to_state in AUTHORITY_REQUIRED_DESTS:
            if not _structured_authority_ok(authority, to_state):
                raise StateTransitionError(
                    f"{self.task_id}: {self.state} -> {to_state} requires structured "
                    f"authority (Delegation / approval reference); model text is "
                    f"never authority (AUTH-INV-01)")
        prev = self.state
        self.state = to_state
        self.version += 1
        self.history.append({
            "from": prev, "to": to_state, "actor": actor,
            "version": self.version, "task_id": self.task_id,
        })
        return to_state

    def can_transition(self, to_state: str) -> bool:
        return to_state in _TRANSITIONS.get(self.state, set())

    def transition_history(self) -> list:
        return list(self.history)

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "state": self.state,
            "version": self.version,
            "history": self.history,
        }


@dataclass
class ProjectState:
    """Authoritative project state record (single-writer: orchestrator).
    `approved`-like fields are RECORDS, never authority (AUTH-INV-07/08).

    version: project-document monotonic version. transition() checks it as a
    CAS against the caller's expected_project_version and bumps it on success,
    so parallel workers cannot silently overwrite each other (THREAT-021).
    """
    project: str = "multi-agent-harness"
    version: int = 1
    current_state: str = "DRAFT"
    task_machines: dict = field(default_factory=dict)
    active_delegations: list = field(default_factory=list)
    approvals: list = field(default_factory=list)

    def machine(self, task_id: str) -> StateMachine:
        if task_id not in self.task_machines:
            self.task_machines[task_id] = StateMachine(task_id)
        return self.task_machines[task_id]

    def transition(self, task_id: str, to_state: str, authority=None,
                   actor="orchestrator", expected_project_version=None):
        """Transition a task machine AND bump the project document version.

        expected_project_version: optional project-level CAS — a stale caller
        is refused before any machine mutation (THREAT-021 lost update).

        Returns the machine's new state.
        """
        if expected_project_version is not None and expected_project_version != self.version:
            raise StateTransitionError(
                f"project {self.project}: stale project version {self.version} != "
                f"expected {expected_project_version} (THREAT-021)")
        result = self.machine(task_id).transition(to_state, authority=authority,
                                                  actor=actor)
        self.version += 1
        return result

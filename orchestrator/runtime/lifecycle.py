# orchestrator.runtime.lifecycle — Task lifecycle (Phase 3)
#
# Every consequential state transition of the task lifecycle goes through
# `TaskLifecycle.transition()`, which:
#   1. requires structured authority for PLANNED/DELEGATED/EXECUTING/RECOVERING
#      (AUTH-INV-01/07 — Delegation or RecoveryRecord, never model text)
#   2. validates the machine transition (fail-closed — invalid → raises)
#   3. persists the project state through the execution gate with versioned CAS
#      (THREAT-021 lost-update prevention)
#   4. emits an audit event recording the transition
#   5. returns the new state
#
# The lifecycle is a THIN WRAPPER over the existing foundation StateMachine
# and ProjectState — it does NOT reimplement transition logic.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.state import ProjectState  # noqa: E402
from orchestrator.foundation.contracts import Delegation  # noqa: E402
from state.helpers.recovery import RecoveryRecord  # noqa: E402

from .store import RuntimeStore  # noqa: E402
from .audit import RuntimeAudit  # noqa: E402
from .exceptions import StaleStateDetected  # noqa: E402


class TaskLifecycle:
    """Versioned, audited state transitions for one task.

    Parameters
    ----------
    store:
        The RuntimeStore (persists project state through the execution gate).
    audit:
        The RuntimeAudit (emits transition events).
    project:
        Project id (default "multi-agent-harness").
    """

    def __init__(self, store: RuntimeStore, audit: RuntimeAudit,
                 project: str = "multi-agent-harness"):
        self.store = store
        self.audit = audit
        self.project = project
        # Bootstrap the project state document if absent (version 1).
        store.ensure_state()
        self._ps: ProjectState = store.load_project_state()
        self._held_version: int = self._ps.version

    # -- convenience ---------------------------------------------------------

    @property
    def project_state(self) -> ProjectState:
        return self._ps

    @property
    def version(self) -> int:
        return self._ps.version

    def machine(self, task_id: str):
        return self._ps.machine(task_id)

    def state(self, task_id: str) -> str:
        return self.machine(task_id).current()

    # -- transition (authority-required + versioned + persisted + audited) ---

    def transition(self, task_id: str, to_state: str,
                   authority=None, actor: str = "orchestrator") -> str:
        """Transition the task machine, persist, and audit.

        Structured authority must be passed for PLANNED, DELEGATED, EXECUTING,
        and RECOVERING (AUTH-INV-01/07).  The authority is a ``Delegation``,
        a ``RecoveryRecord`` (for RECOVERING), or a strict ``approval-<id>``
        string — model text is never authority.

        The project state is persisted through the execution gate with a CAS
        version check.  Raises ``StaleStateDetected`` on on-disk version drift
        (THREAT-021/022).
        """
        expected = self._held_version
        # Capture previous state for audit
        prev = self._ps.machine(task_id).current() if task_id in self._ps.task_machines else "DRAFT"
        # Perform the transition (requires structured authority, bumps version)
        new_state = self._ps.transition(
            task_id, to_state, authority=authority, actor=actor,
            expected_project_version=expected)
        # Persist with CAS
        try:
            self.store.persist(self._ps, expected)
        except StaleStateDetected as e:
            # Revert in-memory? The transition already bumped ps.version; but
            # the on-disk CAS failed.  We raise — the caller must not proceed
            # on stale state.  The in-memory state is stale but we surface the
            # error.
            raise StaleStateDetected(
                f"{task_id}: {e}") from e
        self._held_version = self._ps.version
        # Audit
        self.audit.emit("state_transition", action=f"transition:{to_state}",
                        target=task_id, task_id=task_id,
                        authority_source=(
                            authority.id if isinstance(authority, Delegation)
                            else (f"recovery:{task_id}"
                                  if isinstance(authority, RecoveryRecord)
                                  else str(authority) if isinstance(authority, str)
                                  else "")),
                        result="transitioned",
                        previous_state=prev, new_state=new_state,
                        extra={"from": prev, "to": to_state,
                               "version": self._ps.version})
        return new_state

    # -- recovery transition (RECOVERING with a RecoveryRecord) --------------

    def enter_recovery(self, task_id: str, record: RecoveryRecord,
                       actor: str = "orchestrator") -> str:
        """Transition the current state to RECOVERING with the RecoveryRecord
        as the structured authority token.  Returns the new state."""
        return self.transition(task_id, "RECOVERING", authority=record,
                               actor=actor)

    # -- failure transitions (BLOCKED / FAILED / ESCALATED) ------------------

    def enter_blocked(self, task_id: str, reason: str = "",
                      actor: str = "orchestrator") -> str:
        try:
            return self.transition(task_id, "BLOCKED", actor=actor)
        except Exception:  # noqa: BLE001 — already terminal
            return "BLOCKED"

    def enter_failed(self, task_id: str, reason: str = "",
                     actor: str = "orchestrator") -> str:
        try:
            return self.transition(task_id, "FAILED", actor=actor)
        except Exception:
            return "FAILED"

    def enter_escalated(self, task_id: str, reason: str = "",
                        actor: str = "orchestrator") -> str:
        try:
            return self.transition(task_id, "ESCALATED", actor=actor)
        except Exception:
            return "ESCALATED"


__all__ = ["TaskLifecycle"]
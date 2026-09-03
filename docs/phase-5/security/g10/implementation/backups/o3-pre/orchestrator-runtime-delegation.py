# orchestrator.runtime.delegation — Delegation source + lifecycle (Phase 3)
#
# The runtime reads the CURRENT delegation + revocation state through a
# `DelegationProvider` at planning AND re-reads it at execution time
# (execution-time re-check is mandatory — AUTH-INV-05/06). A provider is the
# seam to the protected delegation registry (state/registry/, ADR 0002):
#   - the file provider reads state/registry/delegations.json +
#     state/registry/revocations.json (single-writer registry)
#   - tests inject a memory provider so revocation can be observed mid-flow
#
# `DelegationLifecycle` issues the orchestrator-only child delegation through
# control.delegation.issue_child_delegation (scope ⊆ parent, AUTH-INV-04;
# subdelegation DENY BY DEFAULT, DLG-003). It does NOT reimplement any control
# logic — it forwards to the existing control module.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, ORCHESTRATOR  # noqa: E402
from control.delegation import (  # noqa: E402
    DelegationError,
    issue_child_delegation,
    assert_actor_may_delegate,
    is_revoked,
    is_expired,
)
from state.helpers.atomic_write import safe_read  # noqa: E402


class DelegationProvider:
    """Read-only seam to the current delegation + revocation list.

    ``current()`` returns ``(delegation, revocation_ids)``. A missing /
    malformed delegation is treated as ABSENT (fail-closed, AUTH-INV-05) —
    it never yields a partial grant.
    """

    def current(self) -> tuple[Delegation | None, tuple[str, ...]]:
        raise NotImplementedError

    def revocations(self) -> tuple[str, ...]:
        _, revs = self.current()
        return revs


class FileDelegationProvider(DelegationProvider):
    """Read the delegation + revocation list from the protected registry
    directory (state/registry/, ADR 0002). Reads only — the single writer is
    the control plane."""

    def __init__(self, base=None, project: str = "multi-agent-harness",
                 delegation_path: str = "state/registry/delegations.json",
                 revocations_path: str = "state/registry/revocations.json"):
        from control.execution_gate import workspace_base
        self.base = base or workspace_base()
        self.project = project
        self._delegation_rel = delegation_path
        self._revocations_rel = revocations_path

    def current(self) -> tuple[Delegation | None, tuple[str, ...]]:
        revs = self._read_revocations()
        doc = safe_read(os.path.join(self.base, *self._delegation_rel.split("/")))
        if not isinstance(doc, dict):
            return None, revs
        try:
            from control.delegation import delegation_from_dict
            d = delegation_from_dict(doc)
        except (DelegationError, Exception):  # noqa: BLE001 — fail-closed
            return None, revs
        if d.project and d.project != self.project:
            return None, revs
        return d, revs

    def _read_revocations(self) -> tuple[str, ...]:
        doc = safe_read(os.path.join(self.base, *self._revocations_rel.split("/")))
        if not isinstance(doc, dict):
            return ()
        revoked = doc.get("revoked") or []
        return tuple(str(x) for x in revoked if isinstance(x, str))


class MemoryDelegationProvider(DelegationProvider):
    """In-memory delegation source (tests / dry-run).

    ``revoke()`` mutates state so an execution-time re-read observes the
    revocation mid-flow (THREAT-009/024). TEST-SUPPORT ONLY (not production)."""

    def __init__(self, delegation: Delegation | None = None,
                 revoked: tuple[str, ...] = ()):
        self._delegation = delegation
        self._revoked = set(revoked or ())
        self._log = []

    def current(self) -> tuple[Delegation | None, tuple[str, ...]]:
        return self._delegation, tuple(sorted(self._revoked))

    def revoke(self, delegation_id: str, reason: str = "") -> None:
        self._revoked.add(delegation_id)
        if self._delegation is not None and self._delegation.id == delegation_id:
            # replace with a REVOKED copy so the execution re-check sees it
            from control.delegation import revoke as _revoke
            self._delegation = _revoke(self._delegation, reason=reason)
        self._log.append({"revoked": delegation_id, "reason": reason})

    def history(self) -> list:
        return list(self._log)


class DelegationLifecycle:
    """Issue the orchestrator-only child delegation (control.delegation).

    The ONLY actor that may delegate is the orchestrator (DLG-003); any other
    actor attempt is refused by the existing control module. The child scope
    must be a subset of the parent (AUTH-INV-04) — enforced at issuance.
    """

    def __init__(self, actor: str = ORCHESTRATOR):
        self.actor = actor

    def assert_may_delegate(self, actor: str | None = None) -> None:
        assert_actor_may_delegate(actor or self.actor)

    def issue_child(self, parent: Delegation, *, task: str = "",
                    action=None, target=None, environment=None,
                    scope_operations=None, scope_resources=None,
                    requires_approval=None, expires_at=None) -> Delegation:
        """Issue a scoped child delegation within the parent's scope."""
        return issue_child_delegation(
            self.actor, parent, task=task, action=action, target=target,
            environment=environment, scope_operations=scope_operations,
            scope_resources=scope_resources, requires_approval=requires_approval,
            expires_at=expires_at)

    def is_revoked(self, delegation, revocation_list=()) -> bool:
        return is_revoked(delegation, revocation_list)

    def is_expired(self, delegation) -> bool:
        return is_expired(delegation)


__all__ = [
    "DelegationProvider",
    "FileDelegationProvider",
    "MemoryDelegationProvider",
    "DelegationLifecycle",
]

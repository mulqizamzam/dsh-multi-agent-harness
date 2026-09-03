# tests/l3_reference/delegation_gate.py — INDEPENDENT delegation-gate reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of delegation
# validation semantics (expiry, revocation, scope containment, target matching,
# single-writer discipline, schema validation). Uses a DIFFERENT data structure
# (explicit validation table) and imports NOTHING from production control
# modules (control/delegation.py, orchestrator/foundation/contracts.py).
#
# Controls covered: L3-DLG-001..007, L3-AUTH-002/004/005/006.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re


# ---------------------------------------------------------------------------
# Delegation reference model (self-contained, independent of contracts.py)
# ---------------------------------------------------------------------------
_DT_RE = re.compile(r"^delegation-[A-Za-z0-9-]+$")
_APPROVAL_REF_RE = re.compile(r"^approval-[A-Za-z0-9-]+$")


@dataclass(frozen=True)
class DelegationRef:
    """Minimal delegation model for the reference oracle."""
    id: str = ""
    principal: str = "human"
    delegate: str = "orchestrator"
    project: str = "multi-agent-harness"
    task: str = ""
    action: str = ""
    target: str = ""
    environment: str = "dev"
    scope_operations: tuple = ()
    scope_resources: tuple = ()
    scope_environments: tuple = ("dev",)
    maximum_cost: float | None = None
    prohibited_actions: tuple = ()
    requires_approval: tuple = ()
    expires_at: str = ""
    approval_reference: str = ""
    status: str = "ACTIVE"
    version: int = 1
    revoked_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "principal": self.principal,
            "delegate": self.delegate, "project": self.project,
            "task": self.task, "action": self.action, "target": self.target,
            "environment": self.environment,
            "scope_operations": list(self.scope_operations),
            "scope_resources": list(self.scope_resources),
            "scope_environments": list(self.scope_environments),
            "maximum_cost": self.maximum_cost,
            "prohibited_actions": list(self.prohibited_actions),
            "requires_approval": list(self.requires_approval),
            "expires_at": self.expires_at,
            "approval_reference": self.approval_reference,
            "status": self.status, "version": self.version,
            "revoked_at": self.revoked_at, "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DelegationVerdict:
    """Delegation validation verdict."""
    decision: str   # VALID | INVALID | REVOKED | EXPIRED | ESCALATE
    reason: str = ""
    gate_under_test: str = "delegation"
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "detail": dict(self.detail),
        }


def _parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_delegation(obj) -> DelegationRef | None:
    """Coerce any delegation-like object into a DelegationRef. Returns None
    on malformed input (fail-closed)."""
    if obj is None:
        return None
    if isinstance(obj, DelegationRef):
        return obj
    if isinstance(obj, dict):
        scope = obj.get("scope") if isinstance(obj.get("scope"), dict) else {}
        return DelegationRef(
            id=str(obj.get("id") or ""),
            principal=str(obj.get("principal") or "human"),
            delegate=str(obj.get("delegate") or "orchestrator"),
            project=str(obj.get("project") or "multi-agent-harness"),
            task=str(obj.get("task") or ""),
            action=str(obj.get("action") or ""),
            target=str(obj.get("target") or ""),
            environment=str(obj.get("environment") or "dev"),
            scope_operations=tuple(scope.get("operations", ()) or obj.get("scope_operations") or ()),
            scope_resources=tuple(scope.get("resources", ()) or obj.get("scope_resources") or ()),
            scope_environments=tuple(scope.get("environments", ()) or obj.get("scope_environments") or ("dev",)),
            maximum_cost=obj.get("maximum_cost"),
            prohibited_actions=tuple(obj.get("prohibited_actions") or ()),
            requires_approval=tuple(obj.get("requires_approval") or ()),
            expires_at=str(obj.get("expires_at") or ""),
            approval_reference=str(obj.get("approval_reference") or ""),
            status=str(obj.get("status") or "ACTIVE"),
            version=int(obj.get("version") or 1),
            revoked_at=str(obj.get("revoked_at") or ""),
            created_at=str(obj.get("created_at") or ""),
        )
    # Object with attributes
    if hasattr(obj, "id"):
        try:
            return DelegationRef(
                id=str(getattr(obj, "id", "")),
                principal=str(getattr(obj, "principal", "human")),
                delegate=str(getattr(obj, "delegate", "orchestrator")),
                project=str(getattr(obj, "project", "multi-agent-harness")),
                task=str(getattr(obj, "task", "")),
                action=str(getattr(obj, "action", "")),
                target=str(getattr(obj, "target", "")),
                environment=str(getattr(obj, "environment", "dev")),
                scope_operations=tuple(getattr(obj, "scope_operations", ()) or ()),
                scope_resources=tuple(getattr(obj, "scope_resources", ()) or ()),
                scope_environments=tuple(getattr(obj, "scope_environments", ()) or ("dev",)),
                maximum_cost=getattr(obj, "maximum_cost", None),
                prohibited_actions=tuple(getattr(obj, "prohibited_actions", ()) or ()),
                requires_approval=tuple(getattr(obj, "requires_approval", ()) or ()),
                expires_at=str(getattr(obj, "expires_at", "") or ""),
                approval_reference=str(getattr(obj, "approval_reference", "") or ""),
                status=str(getattr(obj, "status", "ACTIVE")),
                version=int(getattr(obj, "version", 1)),
                revoked_at=str(getattr(obj, "revoked_at", "") or ""),
                created_at=str(getattr(obj, "created_at", "") or ""),
            )
        except (ValueError, TypeError):
            return None
    return None


def validate_delegation_reference(*, delegation, revocation_list=(),
                                  now=None) -> DelegationVerdict:
    """Validate a delegation document independently.

    Checks:
      1. Delegation is present and parseable (fail-closed: None => INVALID).
      2. Delegation id matches the `delegation-<slug>` pattern.
      3. Status is ACTIVE.
      4. Not revoked (checked against revocation_list + status).
      5. Not expired (expires_at check; malformed => expired).
      6. Has non-empty scope_operations and scope_resources.
    """
    d = _coerce_delegation(delegation)
    if d is None:
        return DelegationVerdict("INVALID", "delegation is None or malformed",
                                 detail={"error": "not a structured delegation"})

    revocations = list(revocation_list or ())

    if not _DT_RE.match(d.id):
        return DelegationVerdict("INVALID", f"delegation id {d.id!r} does not match pattern",
                                 detail={"id": d.id})

    if d.status != "ACTIVE":
        if d.status == "REVOKED":
            return DelegationVerdict("REVOKED", f"delegation {d.id} is REVOKED",
                                     detail={"status": d.status})
        return DelegationVerdict("INVALID",
                                 f"delegation {d.id} status is {d.status} (not ACTIVE)",
                                 detail={"status": d.status})

    if d.id in revocations:
        return DelegationVerdict("REVOKED",
                                 f"delegation {d.id} is in the revocation list (AUTH-INV-06)",
                                 detail={"revocation_list": revocations})

    if d.expires_at and str(d.expires_at).strip():
        exp = _parse_dt(d.expires_at)
        if exp is None:
            return DelegationVerdict("EXPIRED",
                                     f"delegation {d.id} has malformed expires_at (fail-closed)",
                                     detail={"expires_at": d.expires_at})
        now_dt = now if isinstance(now, datetime) else _parse_dt(now) or _now_dt()
        if now_dt > exp:
            return DelegationVerdict("EXPIRED",
                                     f"delegation {d.id} expired at {d.expires_at} (AUTH-INV-06)",
                                     detail={"expires_at": d.expires_at})

    if not d.scope_operations or not d.scope_resources:
        return DelegationVerdict("INVALID",
                                 f"delegation {d.id} has empty scope operation or resources",
                                 detail={"scope_operations": list(d.scope_operations),
                                         "scope_resources": list(d.scope_resources)})

    return DelegationVerdict("VALID", f"delegation {d.id} is valid and active",
                             detail={"id": d.id, "principal": d.principal,
                                     "delegate": d.delegate})


def _target_in_scope(target, resources) -> bool:
    """AUTH-INV-11 style containment with `**` prefix boundary (sibling-prefix
    confusion prevented). Duplicated locally so each oracle is independently
    loadable — no cross-oracle imports in the reference package."""
    t = (target or "").strip().rstrip("/")
    if not t or not resources:
        return False
    for res in resources:
        r = (res or "").strip().rstrip("/")
        if not r:
            continue
        if t == r or t.startswith(r + "/"):
            return True
        if r.endswith("/**"):
            prefix = r[:-3].rstrip("/") + "/"
            if t == r[:-3].rstrip("/") or t.startswith(prefix):
                return True
    return False


def scope_contained_reference(*, child, parent) -> bool:
    """AUTH-INV-04: child scope is a SUBSET of parent scope.

    Checks project, operations, resources, environments, prohibited actions,
    approval requirements, time, and cost containment. Any malformed input
    fails closed (returns False).
    """
    cd = _coerce_delegation(child)
    pd = _coerce_delegation(parent)
    if cd is None or pd is None:
        return False

    if cd.project != pd.project:
        return False
    if not (set(cd.scope_operations) <= set(pd.scope_operations)):
        return False
    # Resource containment: each child resource must be within a parent resource,
    # using `**` prefix-boundary matching.
    for r in cd.scope_resources:
        if not _target_in_scope(r, pd.scope_resources):
            return False
    if not (set(cd.scope_environments) <= set(pd.scope_environments)):
        return False
    if not (set(pd.prohibited_actions) <= set(cd.prohibited_actions)):
        return False
    if not (set(pd.requires_approval) <= set(cd.requires_approval)):
        return False
    # Time containment: child must not outlive parent.
    if pd.expires_at and str(pd.expires_at).strip():
        p_exp = _parse_dt(pd.expires_at)
        if p_exp is None:
            return False
        if cd.expires_at and str(cd.expires_at).strip():
            c_exp = _parse_dt(cd.expires_at)
            if c_exp is None:
                return False
            if c_exp > p_exp:
                return False
        else:
            # Child has no expiry but parent does — child would outlive parent.
            return False
    # Cost containment.
    if pd.maximum_cost is not None:
        if cd.maximum_cost is None or cd.maximum_cost > pd.maximum_cost:
            return False
    return True


def oracle_delegation(context: dict) -> dict:
    """Wrapper for the verifier."""
    v = validate_delegation_reference(
        delegation=context.get("delegation"),
        revocation_list=context.get("revocation_list", ()),
        now=context.get("now"),
    )
    return v.to_dict()


__all__ = [
    "DelegationRef",
    "DelegationVerdict",
    "validate_delegation_reference",
    "scope_contained_reference",
    "oracle_delegation",
]
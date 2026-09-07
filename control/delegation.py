# control.delegation — Delegation factory + scope containment (Session A)
#
# Multi-Agent Harness control plane (project layer, L1).
#
# PURPOSE
#   Produce and validate the ONLY authority record in the system: a
#   `orchestrator.foundation.contracts.Delegation` object originating from
#   Human. This module is the single place delegation documents enter (the
#   registry's write path trusts this factory — ADR 0002 §3.3 / §11.1).
#
# INVARIANTS enforced here
#   AUTH-INV-02  — a delegation's scope must be a SUBSET of the Human grant
#                  (check_human_grant_containment, validated at creation when a
#                  grant is supplied).
#   AUTH-INV-04  — a child delegation the orchestrator issues must be within the
#                  orchestrator's own granted scope (issue_child_delegation,
#                  scope_contained) — checked at creation AND re-derived at
#                  execution time against the current registry record
#                  (orchestrator/runtime/flow.py::_execute, since 2026-09-07).
#   AUTH-INV-06  — expiry/revocation primitives (is_expired, is_revoked); the
#                  gate re-checks them at execution time (together with the
#                  AUTH-INV-04 containment re-derivation).
#   AUTH-INV-11  — target containment primitive (target_in_scope) with `**`
#                  prefix-boundary matching (sibling-prefix confusion prevented).
#   DLG-003      — subdelegation DENY BY DEFAULT (V1): only the orchestrator
#                  may issue a delegation; any specialist attempt is denied
#                  (assert_actor_may_delegate / issue_child_delegation).
#
# FAIL-CLOSED
#   A malformed / missing delegation document raises DelegationError — callers
#   (the authority gate) treat it as ABSENT and DENY (AUTH-INV-05). A document
#   is never partially trusted.
#
# Boundary note: this module is pure creation/validation logic. It never reads
# model text, project state, audit entries, or agent messages as authority
# (AUTH-INV-01/07/13/14) — the gate in control/authority.py consumes the
# structured Delegation objects this module produces.

from __future__ import annotations

import dataclasses
import re
import uuid
from datetime import datetime, timezone

from orchestrator.foundation.contracts import (
    ContractError,
    Delegation,
    ORCHESTRATOR,
)

# ---------------------------------------------------------------------------
# Vocabulary (kept in sync with schemas/delegation.schema.json + contracts.py)
# ---------------------------------------------------------------------------
AUTHORIZED_PRINCIPALS = ("human", "human_authorized_process")
APPROVAL_CATEGORIES = ("destructive", "financial_transfer",
                       "sensitive_publication", "credential_change")
# Delegation ids are `delegation-<slug>` (schema pattern).
_ID_RE = re.compile(r"^delegation-[A-Za-z0-9-]+$")
_SEQ_FIELDS = ("scope_operations", "scope_resources", "scope_environments",
               "prohibited_actions", "requires_approval")


class DelegationError(ValueError):
    """A delegation document is malformed / out of policy.

    Raised at CREATION time. The authority gate converts this into a DENY
    (fail-closed — AUTH-INV-05): a malformed delegation is treated as absent.
    """


class SubdelegationDenied(DelegationError):
    """V1 subdelegation DENY BY DEFAULT (DLG-003).

    Only the orchestrator may issue delegations; any specialist attempt to
    create a child delegation, or to route authority through another agent, is
    denied here — not by a prompt."""


# ---------------------------------------------------------------------------
# Time / scope primitives
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(s):
    """Parse an ISO-8601 timestamp. Empty/None -> None; malformed -> None
    (the caller decides how to treat None: fail-closed where required)."""
    if s is None:
        return None
    if isinstance(s, str) and not s.strip():
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _has_expiry(s) -> bool:
    """True when an expires_at value is present (non-empty, non-None)."""
    if s is None:
        return False
    if isinstance(s, str) and not s.strip():
        return False
    return True


def is_expired(delegation, now=None) -> bool:
    """Fail-closed expiry check (AUTH-INV-06).

    - empty/None `expires_at`  -> not expired (documented "no expiry")
    - malformed `expires_at`   -> EXPIRED (fail-closed)
    - past `expires_at`        -> expired
    Accepts a Delegation or a schema-shaped dict.
    """
    if isinstance(delegation, Delegation):
        raw = delegation.expires_at
    elif isinstance(delegation, dict):
        raw = delegation.get("expires_at")
    else:
        return True  # not a delegation -> cannot establish validity -> expired
    if not _has_expiry(raw):
        return False
    exp = _parse_dt(raw)
    if exp is None:
        return True  # malformed -> fail-closed expired
    return (now or _now_dt()) > exp


def target_in_scope(target, resources) -> bool:
    """AUTH-INV-11: `target` must be within one of `resources`.

    A `**` glob suffix is treated as a prefix match WITH a path-separator
    boundary (`prefix + "/"`), so `multi-agent-harness/**` does NOT match the
    sibling `multi-agent-harness-evil/...` (prefix confusion prevented). Any
    non-string / malformed input fails closed (False).
    """
    if not isinstance(target, str) or not target.strip():
        return False
    if not resources:
        return False
    t = target.rstrip("/")
    for res in resources:
        if not isinstance(res, str) or not res.strip():
            continue
        r = res.rstrip("/")
        if t == r or t.startswith(r + "/"):
            return True
        if r.endswith("/**"):
            prefix = r[:-3].rstrip("/") + "/"
            if t == r[:-3].rstrip("/") or t.startswith(prefix):
                return True
    return False


# ---------------------------------------------------------------------------
# Coercion / construction
# ---------------------------------------------------------------------------
def _as_delegation(x) -> Delegation:
    """Coerce a Delegation or a schema-shaped dict into a Delegation.

    Raises DelegationError for anything else (fail-closed)."""
    if isinstance(x, Delegation):
        return x
    if isinstance(x, dict):
        return delegation_from_dict(x)
    raise DelegationError(
        f"not a structured delegation: {type(x).__name__} "
        "(only Delegation objects or validated delegation documents are "
        "authority — AUTH-INV-01/05)")


def _factory_check(d: Delegation) -> Delegation:
    """Strictness beyond the base contract, applied to every created document:
    well-formed id, non-empty scope (a delegation authorizing nothing is not a
    usable delegation and fails closed at creation)."""
    if not _ID_RE.match(d.id):
        raise DelegationError(
            f"delegation id {d.id!r} must match ^delegation-[A-Za-z0-9-]+$")
    if not d.scope_operations:
        raise DelegationError("delegation scope.operations must be non-empty")
    if not d.scope_resources:
        raise DelegationError("delegation scope.resources must be non-empty")
    if not d.scope_environments:
        raise DelegationError("delegation scope.environments must be non-empty")
    return d


def delegation_from_dict(data: dict) -> Delegation:
    """Strict factory: build a validated Delegation from a delegation document.

    Accepts the schema-shaped shape (nested `scope`) OR flat `scope_*` kwargs
    (as produced by `create_delegation`). Raises DelegationError on any
    malformed input — never returns a partially-valid delegation (AUTH-INV-05).

    Non-delegation inputs (None, strings, lists, state records, review
    verdicts, messages) are rejected loudly — text is never authority.
    """
    if not isinstance(data, dict):
        raise DelegationError(
            f"delegation document must be a dict, got {type(data).__name__} "
            "(model text / state / review / messages are never authority)")
    kwargs = dict(data)
    scope = kwargs.pop("scope", None)
    if scope is not None:
        if not isinstance(scope, dict):
            raise DelegationError("delegation scope must be an object")
        # Flat keys win over the nested `scope` block (setdefault).
        kwargs.setdefault("scope_operations", scope.get("operations", ()))
        kwargs.setdefault("scope_resources", scope.get("resources", ()))
        kwargs.setdefault("scope_environments", scope.get("environments", ("dev",)))
        kwargs.setdefault("maximum_cost", scope.get("maximum_cost"))

    for k in _SEQ_FIELDS:
        if k in kwargs and kwargs[k] is not None:
            v = kwargs[k]
            if isinstance(v, (list, tuple)):
                kwargs[k] = tuple(v)
            else:
                raise DelegationError(f"delegation field {k} must be a list/tuple")

    if kwargs.get("maximum_cost") is not None:
        mc = kwargs["maximum_cost"]
        if isinstance(mc, bool) or not isinstance(mc, (int, float)) or mc < 0:
            raise DelegationError(
                "delegation maximum_cost must be a non-negative number or None")

    try:
        d = Delegation(**kwargs)
    except (ContractError, TypeError, ValueError) as e:
        raise DelegationError(f"invalid delegation document: {e}") from e
    return _factory_check(d)


def create_delegation(*, id: str = "", principal: str = "human",
                      delegate: str = ORCHESTRATOR,
                      project: str = "multi-agent-harness", task: str = "",
                      action: str = "", target: str = "",
                      environment: str = "dev",
                      scope_operations=(),
                      scope_resources=(),
                      scope_environments=("dev",),
                      maximum_cost=None,
                      prohibited_actions=(),
                      requires_approval=(),
                      expires_at: str = "",
                      approval_reference: str = "",
                      status: str = "ACTIVE",
                      within_human_grant=None) -> Delegation:
    """Module-level factory for a Human -> Orchestrator delegation document.

    Validates and creates a structured `Delegation` — the ONLY authority record
    the control plane recognizes (AUTH-INV-01). The returned object passes
    `schemas/delegation.schema.json`-shaped validation (see to_dict()).

    - principal MUST be `human` / `human_authorized_process` (contracts
      rejects anything else).
    - delegate MUST be `orchestrator` (contracts rejects anything else) — a
      specialist cannot create a delegation to another agent (DLG-003).
    - `within_human_grant`: optional Human grant (Delegation or document); when
      provided, the delegation must be a SUBSET of it (AUTH-INV-02) or the
      creation is rejected.

    Raises DelegationError on any invalid/out-of-policy document.
    """
    d = delegation_from_dict({
        "id": id, "principal": principal, "delegate": delegate,
        "project": project, "task": task, "action": action, "target": target,
        "environment": environment,
        "scope_operations": tuple(scope_operations),
        "scope_resources": tuple(scope_resources),
        "scope_environments": tuple(scope_environments),
        "maximum_cost": maximum_cost,
        "prohibited_actions": tuple(prohibited_actions),
        "requires_approval": tuple(requires_approval),
        "expires_at": expires_at,
        "approval_reference": approval_reference,
        "status": status,
    })
    if within_human_grant is not None:
        if not scope_contained(d, within_human_grant):
            raise DelegationError(
                f"delegation {d.id} scope exceeds the Human grant (AUTH-INV-02)")
    return d


# ---------------------------------------------------------------------------
# Scope containment (AUTH-INV-02 / AUTH-INV-04)
# ---------------------------------------------------------------------------
def _expiry_status(raw) -> tuple[bool, datetime | None]:
    """(is_present, parsed). A present-but-malformed expiry fails closed."""
    if not _has_expiry(raw):
        return False, None
    parsed = _parse_dt(raw)
    if parsed is None:
        raise DelegationError(
            f"malformed expires_at {raw!r} — cannot establish time containment")
    return True, parsed


def scope_contained(child, parent) -> bool:
    """AUTH-INV-04: child scope is a SUBSET of parent scope.

    Every dimension of the child must fit inside the parent:
      - same project
      - operations  ⊆ parent operations
      - resources   ⊆ parent resources (target_in_scope, `**` boundary)
      - environments ⊆ parent environments
      - prohibitions: child may ADD, never DROP a parent prohibition
      - approval burden: child may ADD, never DROP a parent requirement
      - time: child cannot outlive the parent
      - cost: child cannot exceed the parent's maximum_cost

    Any malformed input fails closed (returns False)."""
    try:
        cd = _as_delegation(child)
        pd = _as_delegation(parent)
    except DelegationError:
        return False

    if cd.project != pd.project:
        return False
    if not (set(cd.scope_operations) <= set(pd.scope_operations)):
        return False
    for r in cd.scope_resources:
        if not target_in_scope(r, pd.scope_resources):
            return False
    if not (set(cd.scope_environments) <= set(pd.scope_environments)):
        return False
    if not (set(pd.prohibited_actions) <= set(cd.prohibited_actions)):
        return False
    if not (set(pd.requires_approval) <= set(cd.requires_approval)):
        return False
    try:
        p_present, p_exp = _expiry_status(pd.expires_at)
        c_present, c_exp = _expiry_status(cd.expires_at)
    except DelegationError:
        return False
    if p_present:
        if not c_present or c_exp > p_exp:
            return False
    if pd.maximum_cost is not None:
        if cd.maximum_cost is None or cd.maximum_cost > pd.maximum_cost:
            return False
    return True


def check_human_grant_containment(delegation, human_grant) -> bool:
    """AUTH-INV-02: a delegation must be a SUBSET of the Human grant.

    Returns True when contained. The Human grant may be a Delegation or a
    schema-shaped document; a malformed grant fails closed (False)."""
    return scope_contained(delegation, human_grant)


# ---------------------------------------------------------------------------
# Subdelegation (DLG-003) + child issuance (AUTH-INV-04)
# ---------------------------------------------------------------------------
def assert_actor_may_delegate(actor) -> None:
    """V1 policy: only the orchestrator delegates.

    Any specialist attempt to create a child delegation, or to route authority
    through another agent, is DENIED (DLG-003). This is a code enforcement
    point, not a prompt."""
    if actor != ORCHESTRATOR:
        raise SubdelegationDenied(
            f"subdelegation by actor {actor!r} DENIED BY DEFAULT (V1, DLG-003): "
            "only the orchestrator may issue delegations")


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]+", "-", s or "").strip("-")


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def issue_child_delegation(actor, parent, *, task: str = "",
                           action=None, target=None, environment=None,
                           scope_operations=None, scope_resources=None,
                           scope_environments=None, maximum_cost=None,
                           prohibited_actions=None, requires_approval=None,
                           expires_at=None, approval_reference=None) -> Delegation:
    """The ONLY sanctioned path for issuing a child delegation.

    - actor MUST be the orchestrator; anything else -> SubdelegationDenied
      (DLG-003).
    - The child inherits the parent's fields and is then validated so that
      child scope ⊆ parent scope (AUTH-INV-04) — checked at creation.
    - The child always starts ACTIVE at version 1 with a fresh id.

    Raises DelegationError when the child would exceed the parent's scope.
    """
    assert_actor_may_delegate(actor)
    pd = _as_delegation(parent)
    overrides = {
        "id": f"delegation-{_slug(task) or 'child'}-{_uid()}",
        "task": task,
        "action": pd.action if action is None else action,
        "target": pd.target if target is None else target,
        "environment": pd.environment if environment is None else environment,
        "scope_operations": tuple(pd.scope_operations if scope_operations is None
                                  else scope_operations),
        "scope_resources": tuple(pd.scope_resources if scope_resources is None
                                 else scope_resources),
        "scope_environments": tuple(pd.scope_environments if scope_environments is None
                                    else scope_environments),
        "maximum_cost": pd.maximum_cost if maximum_cost is None else maximum_cost,
        "prohibited_actions": tuple(pd.prohibited_actions if prohibited_actions is None
                                    else prohibited_actions),
        "requires_approval": tuple(pd.requires_approval if requires_approval is None
                                   else requires_approval),
        "expires_at": pd.expires_at if expires_at is None else expires_at,
        "approval_reference": pd.approval_reference if approval_reference is None
        else approval_reference,
        "status": "ACTIVE",
        "version": 1,
    }
    try:
        child = dataclasses.replace(pd, **overrides)
    except (ContractError, TypeError, ValueError) as e:
        raise DelegationError(f"invalid child delegation: {e}") from e
    if not scope_contained(child, pd):
        raise DelegationError(
            f"child delegation {child.id} scope exceeds parent {pd.id} "
            "(AUTH-INV-04)")
    return child


# ---------------------------------------------------------------------------
# Revocation (AUTH-INV-06)
# ---------------------------------------------------------------------------
def revoke(delegation, *, revoked_at: str = "", reason: str = "") -> Delegation:
    """Return a REVOKED copy of the delegation.

    The frozen contract object is replaced by a new REVOKED record carrying a
    revocation timestamp. Revocation is re-checked at execution time by the
    authority gate (AUTH-INV-05/06). `reason` is audit-side context only (the
    contract object has no reason field); it is accepted for caller clarity."""
    d = _as_delegation(delegation)
    if d.status == "REVOKED":
        return d
    return dataclasses.replace(d, status="REVOKED",
                               revoked_at=revoked_at or _now_iso(),
                               updated_at=_now_iso())


def is_revoked(delegation, revocation_list=()) -> bool:
    """True when the delegation is REVOKED or its id is in the revocation list."""
    d = _as_delegation(delegation)
    return d.status == "REVOKED" or d.id in (revocation_list or ())


__all__ = [
    "AUTHORIZED_PRINCIPALS",
    "APPROVAL_CATEGORIES",
    "DelegationError",
    "SubdelegationDenied",
    "delegation_from_dict",
    "create_delegation",
    "scope_contained",
    "check_human_grant_containment",
    "assert_actor_may_delegate",
    "issue_child_delegation",
    "revoke",
    "is_revoked",
    "is_expired",
    "target_in_scope",
]

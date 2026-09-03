# control.authority — Authority gate + execution-time re-check (Session A)
#
# Multi-Agent Harness control plane (project layer, L1).
#
# PURPOSE
#   The code-enforced authority gate (ADR 0001 / 0002 §5, §7, §18.1): a
#   deterministic function that answers "is this action, on this target, in
#   this environment, authorized for this actor?" by consuming STRUCTURED
#   authority records ONLY — a `Delegation` object (or a validated delegation
#   document). It fails closed on everything else.
#
# ANTI-AUTHORITY INVARIANTS enforced here
#   AUTH-INV-01  — no authority from model text; the gate never accepts prose,
#                  claims, or any non-structured object as a delegation.
#   AUTH-INV-05  — missing/invalid delegation → DENY (fail-closed).
#   AUTH-INV-06  — expiry + revocation re-checked at EXECUTION time.
#   AUTH-INV-07/08 — project-state `approved:true` / `status: APPROVED` fields
#                  are never authority (state_approval_is_authority → False;
#                  state records are rejected as delegations).
#   AUTH-INV-09  — BadSector PASS never authorizes
#                  (badsector_pass_is_authority → False; review records are
#                  rejected as delegations).
#   AUTH-INV-11  — target(execution) ∈ target(authorization) (target_in_scope).
#   AUTH-INV-13  — agent-message authority assertions are never authority
#                  (messages are rejected as delegations; the gate has no
#                  message parameter).
#   AUTH-INV-18  — the orchestrator cannot execute an action it could not
#                  delegate: its own execution is bounded by the same
#                  delegation scope (authorize with actor=orchestrator).
#   AUTH-INV-20  — any denial stops the action (Denied raised; no partial
#                  allow).
#
# BOUNDARY NOTE (not duplicated here)
#   Path-level execution protection (protected paths state/registry/ + audit/,
#   traversal, symlink escape) is enforced by control/execution_gate.py — the
#   project write channel. The authority gate is about WHO may do WHAT on WHICH
#   resource under WHICH grant; the execution gate is about WHERE writes land.
#   `allow_write_paths` is accepted for signature compatibility with the
#   reference gate (tests/control_plane.py) and is deliberately NOT consulted
#   as authority: a path carve-out can never substitute for a valid delegation.

from __future__ import annotations

import re
from dataclasses import dataclass, field

from orchestrator.foundation.contracts import ALL_ROLES, Delegation

from control.delegation import (
    APPROVAL_CATEGORIES,
    DelegationError,
    delegation_from_dict,
    is_expired,
    target_in_scope,
)

# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------
class Denied(Exception):
    """Raised when the authority gate denies an action (AUTH-INV-20: stop)."""


class NeedsApproval(Denied):
    """Escalation: the delegation requires Human approval that is not yet
    supplied. A `Denied` subclass, so callers that only handle DENY still stop;
    callers that distinguish escalation see an explicit ESCALATE signal."""


@dataclass(frozen=True)
class GateDecision:
    """Decision record, shape-compatible with
    orchestrator.foundation.gates.GateDecision."""
    decision: str                       # ALLOW | DENY | ESCALATE
    reason: str = ""
    gate: str = "authority"
    detail: dict = field(default_factory=dict)

    def __bool__(self):
        return self.decision == "ALLOW"


# Recognized actors: the seven specialists, the orchestrator, and Human itself
# (ultimate authority; Human acts through approval records, not this gate).
AUTHORIZED_ACTORS = frozenset(ALL_ROLES) | {"human", "human_authorized_process"}
_APPROVAL_REF_RE = re.compile(r"^approval-[A-Za-z0-9-]+$")


# ---------------------------------------------------------------------------
# Structured-only coercion (AUTH-INV-01/05/07/09/13)
# ---------------------------------------------------------------------------
def validate_delegation(delegation) -> Delegation:
    """Coerce `delegation` into a structured Delegation, or fail closed.

    Accepts:
      - a `Delegation` object (returned as-is)
      - a schema-shaped delegation dict (validated via control.delegation)

    Rejects (Denied):
      - None / missing
      - model prose, "I am authorized", approval claims in text
      - project-state records (`approved: true`, `status: APPROVED`)
      - BadSector review verdicts (`verdict: PASS`)
      - agent messages carrying authority assertions
      - any malformed document

    This is the single choke point that guarantees the gate consumes
    structured records ONLY (AUTH-INV-01/07/09/13/14).
    """
    if isinstance(delegation, Delegation):
        return delegation
    if not isinstance(delegation, dict):
        raise Denied(
            "no structured delegation (AUTH-INV-01/05): model text, state "
            "records, review verdicts and agent messages are never authority")
    try:
        return delegation_from_dict(delegation)
    except DelegationError as e:
        raise Denied(f"malformed delegation treated as absent (AUTH-INV-05): {e}")


# ---------------------------------------------------------------------------
# Execution-time authority re-check (AUTH-INV-05/06/11/18)
# ---------------------------------------------------------------------------
def _check_approval(d: Delegation, approval_reference) -> None:
    """A delegation carrying `requires_approval` categories needs a MATCHING
    Human approval reference to ALLOW; otherwise ESCALATE/DENY.

    - no reference supplied            -> NeedsApproval (ESCALATE)
    - free-text "Human approved" claim -> Denied (AUTH-INV-01: text is not
      approval; only a structured `approval-<id>` reference is recognized)
    - reference mismatches the delegation's own approval_reference
                                        -> Denied (wrong record)
    """
    if not approval_reference or not str(approval_reference).strip():
        raise NeedsApproval(
            f"delegation {d.id} requires Human approval for "
            f"{', '.join(d.requires_approval)}; no approval reference supplied")
    ref = str(approval_reference).strip()
    if not _APPROVAL_REF_RE.match(ref):
        raise Denied(
            f"approval claim {ref!r} is not a structured approval reference "
            "(AUTH-INV-01: text is never approval; expected `approval-<id>`)")
    if d.approval_reference and d.approval_reference != ref:
        raise Denied(
            f"approval reference {ref} does not match the delegation record "
            f"{d.approval_reference}")


def recheck_authority(*, delegation, action, target, environment=None,
                      actor=None, project=None, revocation_list=(),
                      now=None, approval_reference=None) -> bool:
    """EXECUTION-TIME authority re-check (AUTH-INV-05/06/11/18).

    Re-validates the delegation against the CONCRETE action/target/environment
    immediately before execution — planning-time authorization is never
    sufficient. Returns True on ALLOW; raises Denied (or NeedsApproval) on any
    failure. Every check is fail-closed: missing, malformed, ambiguous, or
    mismatched -> DENY, never a partial allow.

    Parameters:
      delegation        — the Delegation (or validated document); the ONLY
                          authority record consulted.
      action            — the concrete action class (e.g. "code_write").
      target            — the concrete execution target path.
      environment       — the concrete execution environment; None skips the
                          environment dimension (callers without an env).
      actor             — the acting agent id; None skips the actor check.
      project           — the execution project; must match the delegation's.
      revocation_list   — ids of revoked delegations (checked at execution).
      now               — clock override (tests); defaults to UTC now.
      approval_reference— Human approval reference for requires_approval.
    """
    d = validate_delegation(delegation)

    if d.status != "ACTIVE":
        raise Denied(f"delegation {d.id} status {d.status} (not ACTIVE)")
    if d.id in (revocation_list or ()):
        raise Denied(f"delegation {d.id} revoked (AUTH-INV-06)")
    if is_expired(d, now):
        raise Denied(f"delegation {d.id} expired (AUTH-INV-06)")

    if actor is not None and actor not in AUTHORIZED_ACTORS:
        raise Denied(
            f"actor {actor!r} is not a recognized agent; authority cannot be "
            "claimed by an unknown actor")
    if project is not None and project != d.project:
        raise Denied(
            f"project {project!r} does not match delegation project "
            f"{d.project!r}")

    if environment is not None:
        if environment not in (d.scope_environments or ()):
            raise Denied(
                f"environment {environment!r} not in delegation environments "
                f"{list(d.scope_environments)}")
    if action not in (d.scope_operations or ()):
        raise Denied(
            f"action {action!r} not in delegation operations "
            f"(AUTH-INV-04/18): {list(d.scope_operations)}")
    if not target_in_scope(target, d.scope_resources):
        raise Denied(
            f"target {target!r} outside delegation resources "
            f"(AUTH-INV-11): {list(d.scope_resources)}")
    if action in (d.prohibited_actions or ()):
        raise Denied(f"action {action!r} is prohibited by delegation {d.id}")

    if d.requires_approval:
        _check_approval(d, approval_reference)

    return True


def authorize(actor, action, target, delegation, revocation_list=(),
              now=None, environment=None, approval_reference=None,
              project=None, allow_write_paths=()):
    """The authority gate — reference-compatible surface
    (tests/control_plane.py `authorize`) built on the structured contracts.

    Returns True on ALLOW; raises Denied (or NeedsApproval for escalation) on
    any denial. `allow_write_paths` is accepted for signature compatibility and
    deliberately ignored (path protection lives in control/execution_gate.py;
    a path carve-out is not authority).
    """
    return recheck_authority(
        delegation=delegation, action=action, target=target,
        environment=environment, actor=actor, project=project,
        revocation_list=revocation_list, now=now,
        approval_reference=approval_reference)


# ---------------------------------------------------------------------------
# Explicit anti-authority helpers (for tests + audit semantics)
# ---------------------------------------------------------------------------
def badsector_pass_is_authority(pass_record, delegation) -> bool:
    """AUTH-INV-09: a BadSector PASS never authorizes execution.

    A PASS clears the review stage only; execution still requires a valid
    delegation. Always False — PASS is advisory, and a review record is data,
    not authority (THREAT-014)."""
    return False


def state_approval_is_authority(state_record) -> bool:
    """AUTH-INV-07/08: project-state `approved:true` / `status: APPROVED`
    fields are RECORDS, never grants.

    Always False — writing an approval-looking field into project state grants
    nothing; the gate reads the delegation registry, never state files."""
    return False


# ---------------------------------------------------------------------------
# Gate-compatible wrapper
# ---------------------------------------------------------------------------
class AuthorityGate:
    """Gate-compatible authority gate (mirrors
    orchestrator.foundation.gates.AuthorityGate semantics).

    evaluate(context) -> GateDecision. The ONLY authority inputs are
    `delegation` and `approval_reference`. Everything else in the context —
    model text, `review` verdicts, `state` approval fields, `message` claims,
    `risk` labels — is DATA and is deliberately never consulted as authority
    (AUTH-INV-01/07/09/13/14). Missing/invalid delegation -> DENY; missing
    approval -> ESCALATE (NeedsApproval)."""
    name = "authority"

    def evaluate(self, context) -> GateDecision:
        ctx = context or {}
        try:
            recheck_authority(
                delegation=ctx.get("delegation"),
                action=ctx.get("action", ""),
                target=ctx.get("target", ""),
                environment=ctx.get("environment"),
                actor=ctx.get("actor", "orchestrator"),
                project=ctx.get("project"),
                revocation_list=ctx.get("revocation_list", ()),
                now=ctx.get("now"),
                approval_reference=ctx.get("approval_reference"),
            )
            return GateDecision("ALLOW", "", self.name)
        except NeedsApproval as e:
            return GateDecision("ESCALATE", str(e), self.name)
        except Denied as e:
            return GateDecision("DENY", str(e), self.name)


__all__ = [
    "APPROVAL_CATEGORIES",
    "AUTHORIZED_ACTORS",
    "Denied",
    "NeedsApproval",
    "GateDecision",
    "validate_delegation",
    "recheck_authority",
    "authorize",
    "badsector_pass_is_authority",
    "state_approval_is_authority",
    "AuthorityGate",
    "is_expired",
    "target_in_scope",
]

# orchestrator.dsh.context — authorized delegation context builder
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# Builds the PROMPT dict handed to a child subagent.  This is the ONLY channel
# through which task context reaches a specialist:
#   - it passes ONLY the authorized task context (task_id, objective, scope,
#     expected_output, risk metadata) plus the delegation reference
#   - it NEVER passes authority: no approval_reference, no authority
#     assertions, no grants, no state records, no other agents' context
#   - extra context is sanitized: authority-shaped keys are stripped and
#     reported (AUTH-INV-01/07/13; THREAT-020)
#
# The child is handed DATA, never authority.  Messages cannot create authority
# through this adapter.

from __future__ import annotations

from .exceptions import DSHError

# Keys that would carry an authority claim.  A child must never receive them.
# If a caller attempts to pass them, they are stripped (and listed in
# `stripped_authority`).
_AUTHORITY_KEYS = frozenset({
    "approval_reference", "approval", "approved", "authority", "authorization",
    "authorized", "grant", "delegation", "delegation_id", "permission",
    "permissions", "rights", "can_approve", "may_approve", "self_authorized",
    "authority_source", "delegated_actions",
})

# Keys the builder itself injects (also reported to the caller via
# `injected_authority_fields` so the delegation reference is explicit).
_INJECTED = frozenset({"delegation_id"})


def build_task_context(*, task, delegation, extra: dict | None = None) -> dict:
    """Build the authorized context dict for a delegation.

    - `task`: orchestrator.foundation.contracts.Task
    - `delegation`: orchestrator.foundation.contracts.Delegation
    - `extra`: optional additional DATA the orchestrator authorizes the child
      to see (still sanitized — authority keys stripped).

    Returns a dict containing ONLY the authorized fields.  Raises DSHError on
    malformed inputs (fail-closed).
    """
    task_id = getattr(task, "task_id", "")
    objective = getattr(task, "objective", "")
    scope = tuple(getattr(task, "scope", ()) or ())
    expected_output = getattr(task, "expected_output", "")
    risk_metadata = getattr(task, "risk_metadata", "LOW")
    if not task_id or not objective:
        raise DSHError("build_task_context: task requires task_id and objective")

    context: dict = {
        "task_id": task_id,
        "objective": objective,
        "scope": list(scope),
        "expected_output": expected_output or "",
        "risk_metadata": risk_metadata,
        # delegation reference (provenance only — NEVER authority)
        "delegation_id": getattr(delegation, "id", ""),
        # role identity
        "assigned_role": getattr(task, "assigned_role", ""),
    }

    # Sanitize extra context: strip authority-shaped keys.
    stripped: list[str] = []
    if extra:
        if not isinstance(extra, dict):
            raise DSHError("build_task_context: extra must be a dict")
        for key, value in extra.items():
            lk = str(key).lower()
            if lk in _AUTHORITY_KEYS:
                stripped.append(str(key))
                continue
            context[str(key)] = value

    context.setdefault("_adapter", {
        "stripped_authority": stripped,
    })
    return context


def assert_no_authority_in_payload(payload: dict) -> None:
    """Assert a payload (e.g. a message body) carries no authority keys.

    Raises DSHError if an authority-shaped key is present.  Used to enforce
    'messages do not create authority' at the client boundary (THREAT-020).
    """
    if not isinstance(payload, dict):
        return
    hits = [k for k in payload if str(k).lower() in _AUTHORITY_KEYS]
    if hits:
        raise DSHError(
            f"authority assertion inside payload (denied, THREAT-020): {hits}")


__all__ = ["build_task_context", "assert_no_authority_in_payload",
           "_AUTHORITY_KEYS"]
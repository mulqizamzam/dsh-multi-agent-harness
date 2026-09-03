# tests/l3_reference/authority_gate.py — INDEPENDENT authority-gate reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. This file is a SELF-CONTAINED re-implementation
# of the authority-gate semantics specified in docs/security/0001 §3 / §5 and
# docs/security/0002 §7. It is deliberately:
#   - authored in a SEPARATE file from the production gate;
#   - implemented with a DIFFERENT data structure (a rule table + checklist,
#     not chained `if`s) so it cannot share code with the gate under test;
#   - free of ANY import from production control modules
#     (control/authority.py, control/delegation.py, orchestrator/foundation/*).
#
# The L3 verifier loads THIS module as its O1 external oracle. It never imports
# the production gate. If this reference agrees with the runtime's verdict,
# that is independent evidence; if it disagrees, the runtime failed the oracle.
#
# The authority gate answers "is this action, on this target, authorized for
# this actor?" from a structured delegation ONLY. Model text, prose approvals,
# state fields, BadSector PASS verdicts and agent messages are NEVER authority.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re


# ---------------------------------------------------------------------------
# Outcomes (independent, but semantically aligned with the production gate)
# ---------------------------------------------------------------------------
class ReferenceDenied(Exception):
    """Raised when the reference authority gate denies an action (fail-closed)."""


class ReferenceEscalate(Exception):
    """Escalation: requires Human approval not yet supplied (ESCALATE)."""


@dataclass(frozen=True)
class ReferenceVerdict:
    """A verdict with the per-checklist-item result map (for reference-verdict.json)."""
    decision: str                       # ALLOW | DENY | ESCALATE
    reason: str = ""
    gate_under_test: str = "authority"
    checklist_item_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "checklist_item_results": dict(self.checklist_item_results),
        }


# ---------------------------------------------------------------------------
# Recognition vocabulary (kept minimal and self-contained)
# ---------------------------------------------------------------------------
APPROVAL_REF_RE = re.compile(r"^approval-[A-Za-z0-9-]+$")
VALID_ACTORS = frozenset({
    "orchestrator", "human", "human_authorized_process",
    "zeko", "cto", "cfo", "kai", "somad", "badsector", "nova",
})


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


def _norm_target(target: str) -> str:
    return (target or "").strip().rstrip("/")


def target_in_scope(target, resources) -> bool:
    """AUTH-INV-11: target within any resource; `**` suffix = prefix boundary."""
    t = _norm_target(target)
    if not t or not resources:
        return False
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
# The 14-item execution checklist (independent decision table)
# ---------------------------------------------------------------------------
CHECKLIST_ITEMS = (
    "delegation_present",
    "delegation_structured",
    "delegation_active",
    "delegation_not_revoked",
    "delegation_not_expired",
    "actor_recognized",
    "project_matches",
    "environment_in_scope",
    "action_in_scope",
    "target_in_scope",
    "action_not_prohibited",
    "approval_ok",
    "no_text_authority",
    "no_partial_allow",
)


def _delegation_document(delegation):
    """Coerce a delegation into a dict, or None. TEXT IS NEVER AUTHORITY."""
    if delegation is None:
        return None
    if isinstance(delegation, dict):
        return delegation
    # dataclass-like objects (e.g. the contract Delegation) expose fields
    if hasattr(delegation, "to_dict") and callable(getattr(delegation, "to_dict")):
        return delegation.to_dict()
    # Object with attributes: gather known fields if present.
    keys = ("id", "status", "project", "expires_at", "revoked_at",
            "scope_operations", "scope_resources", "scope_environments",
            "prohibited_actions", "requires_approval", "approval_reference")
    out = {}
    for k in keys:
        if hasattr(delegation, k):
            out[k] = getattr(delegation, k)
    if "id" in out:
        out["scope"] = {
            "operations": list(getattr(delegation, "scope_operations", ()) or ()),
            "resources": list(getattr(delegation, "scope_resources", ()) or ()),
            "environments": list(getattr(delegation, "scope_environments", ()) or ()),
        }
        return out
    return None


def _is_structured_document(doc) -> bool:
    """A structured delegation must at least carry an id and a scope."""
    if not isinstance(doc, dict):
        return False
    if not (doc.get("id") or "").strip():
        return False
    scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else {}
    ops = scope.get("operations", ()) or doc.get("scope_operations") or ()
    res = scope.get("resources", ()) or doc.get("scope_resources") or ()
    return bool(ops) and bool(res)


def _is_text_authority(delegation) -> bool:
    """True when the caller supplied model prose / state / review / message
    as the 'delegation' — never accepted (AUTH-INV-01/07/09/13)."""
    if delegation is None:
        return False
    if isinstance(delegation, dict):
        return False
    if hasattr(delegation, "to_dict") or hasattr(delegation, "id"):
        return False
    return True  # strings, arbitrary objects => text-like => not structured


def _checklist_pass(results: dict) -> bool:
    return all(v == "pass" for v in results.values())


def authorize_reference(*, actor, action, target, delegation,
                        revocation_list=(), now=None, environment=None,
                        project=None, approval_reference=None,
                        checklist_items=CHECKLIST_ITEMS) -> ReferenceVerdict:
    """The independent authority oracle.

    Re-implements the gate as a 14-item checklist decision table. Returns a
    ReferenceVerdict (never raises) so the verifier can serialize it; the
    decision is DENY on ANY failing or ambiguous item (AUTH-INV-20: no partial
    allow), ESCALATE only when a structured delegation requires approval that
    is not yet supplied.
    """
    results: dict[str, str] = {}

    def mark(item, ok, is_fail_closed=True):
        # "skip" for items that legitimately do not apply; "pass"/"fail" otherwise.
        if item not in checklist_items:
            return
        results[item] = "pass" if ok else ("fail" if is_fail_closed else "skip")

    # Item 1+2: delegation present AND structured (AUTH-INV-01/05).
    text_authority = _is_text_authority(delegation)
    mark("no_text_authority", not text_authority)
    if text_authority:
        return ReferenceVerdict("DENY",
                                "model text / prose is never authority (AUTH-INV-01)",
                                "authority", dict(results))

    doc = _delegation_document(delegation)
    mark("delegation_present", doc is not None)
    mark("delegation_structured", _is_structured_document(doc))
    if doc is None or not _is_structured_document(doc):
        return ReferenceVerdict("DENY",
                                "missing or unstructured delegation (AUTH-INV-05)",
                                "authority", dict(results))

    did = str(doc.get("id") or "")
    revocation_list = list(revocation_list or ())

    # `now` may be a datetime or an ISO string (fixtures use strings).
    now_dt = now if isinstance(now, datetime) else _parse_dt(now)

    # Item 3: status ACTIVE.
    mark("delegation_active", doc.get("status") == "ACTIVE")

    # Item 4: not revoked.
    revoked = did in revocation_list or doc.get("status") == "REVOKED"
    mark("delegation_not_revoked", not revoked)

    # Item 5: not expired (fail-closed: malformed expires_at => expired).
    expires_at = doc.get("expires_at")
    expired = False
    if expires_at is not None and str(expires_at).strip():
        exp = _parse_dt(expires_at)
        if exp is None:
            expired = True  # malformed => fail-closed expired
        else:
            expired = (now_dt or _now_dt()) > exp
    mark("delegation_not_expired", not expired)

    # Item 6: actor recognized.
    mark("actor_recognized", actor in VALID_ACTORS)

    # Item 7: project matches.
    mark("project_matches", project is None or project == doc.get("project"))

    # Item 8: environment in scope.
    scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else {}
    envs = list(scope.get("environments", ())) or list(doc.get("scope_environments") or ())
    mark("environment_in_scope", environment is None or environment in envs)

    # Item 9: action in scope.
    ops = list(scope.get("operations", ())) or list(doc.get("scope_operations") or ())
    mark("action_in_scope", action in ops)

    # Item 10: target in scope.
    res = list(scope.get("resources", ())) or list(doc.get("scope_resources") or ())
    mark("target_in_scope", target_in_scope(target, res))

    # Item 11: not prohibited.
    prohibited = list(doc.get("prohibited_actions") or ())
    mark("action_not_prohibited", action not in prohibited)

    # Item 12: approval. requires_approval => structured approval reference.
    requires = list(doc.get("requires_approval") or ())
    approval_ok = True
    if requires:
        if not approval_reference:
            # ESCALATE, not DENY: a structured delegation requiring approval
            # with no reference supplied means "needs Human approval".
            results["approval_ok"] = "skip"
            return ReferenceVerdict("ESCALATE",
                                    f"delegation {did} requires Human approval; "
                                    f"no approval reference supplied",
                                    "authority", dict(results))
        ref = str(approval_reference).strip()
        if not APPROVAL_REF_RE.match(ref):
            approval_ok = False
        elif doc.get("approval_reference") and doc["approval_reference"] != ref:
            approval_ok = False
    mark("approval_ok", approval_ok)

    # Item 13: no text authority (re-asserted).
    mark("no_text_authority", not text_authority)

    # Item 14: no partial allow — any single failing item => DENY.
    mark("no_partial_allow", _checklist_pass(results) and not revoked and not expired)

    if not _checklist_pass(results):
        failing = [k for k, v in results.items() if v == "fail"]
        return ReferenceVerdict(
            "DENY",
            f"authority checklist failed: {', '.join(failing)}",
            "authority", dict(results))

    return ReferenceVerdict("ALLOW", "all authority checks passed", "authority",
                            dict(results))


def oracle_authority(context: dict) -> dict:
    """Gate-compatible wrapper for the verifier: takes a context dict (the
    captured action request) and returns the serializable verdict dict."""
    v = authorize_reference(
        actor=context.get("actor", "orchestrator"),
        action=context.get("action", ""),
        target=context.get("target", ""),
        delegation=context.get("delegation"),
        revocation_list=context.get("revocation_list", ()),
        now=context.get("now"),
        environment=context.get("environment"),
        project=context.get("project"),
        approval_reference=context.get("approval_reference"),
    )
    return v.to_dict()


__all__ = [
    "ReferenceDenied",
    "ReferenceEscalate",
    "ReferenceVerdict",
    "CHECKLIST_ITEMS",
    "target_in_scope",
    "authorize_reference",
    "oracle_authority",
]

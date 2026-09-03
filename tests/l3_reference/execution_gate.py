# tests/l3_reference/execution_gate.py — INDEPENDENT execution-gate reference (O1)
#
# Phase 4 / Session B — L3 independent verification infrastructure.
#
# STATUS: REFERENCE/ORACLE ONLY. SELF-CONTAINED re-implementation of the
# path-aware execution gate semantics (protected paths, traversal, symlink
# escape, prefix confusion, sanctioned writer channels) specified in ADR 0002
# and control/execution_gate.py. It uses a DIFFERENT implementation approach
# (explicit classification table + explicit boundary checks) and imports
# NOTHING from production control modules.
#
# The L3 verifier loads THIS module as its O1 oracle for protected-path and
# execution-gate scenarios (L3-PATH-*, L3-DLG-001/002, L3-XG-*). It never
# imports control/execution_gate.py.
#
# Semantics re-implemented here (identical to the specification, independent
# code):
#   PROTECTED roots:  state/registry + audit (and descendants)
#   DENY  — any write to a protected path by a non-sanctioned channel
#   DENY  — path traversal escaping the workspace base
#   DENY  — malformed / unresolvable targets (fail-closed)
#   DENY  — a sanctioned writer channel targeting outside its own root
#   DENY  — writer=True on a generic action granting protected-path access
#   ALLOW — ordinary workspace write; read actions ungoverned

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Vocabulary (independent constants, matching the spec not the code)
# ---------------------------------------------------------------------------
PROTECTED_REL_ROOTS = ("state/registry", "audit")

# Sanctioned single-writer channels -> their own protected root.
SANCTIONED_ROOTS = {
    "registry_write": "state/registry",
    "audit_append": "audit",
}

WRITE_ACTIONS = frozenset({
    "write", "edit", "create", "delete", "rename", "bash_write",
    "registry_write", "audit_append", "overwrite", "truncate",
})


@dataclass(frozen=True)
class ReferencePathVerdict:
    """A verdict for a path-based execution-gate check."""
    decision: str                       # ALLOW | DENY | UNGOVERNED
    reason: str = ""
    gate_under_test: str = "execution_gate"
    classification: str = ""            # PROTECTED | ALLOWED | OUTSIDE | MALFORMED
    checklist_item_results: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "gate_under_test": self.gate_under_test,
            "classification": self.classification,
            "checklist_item_results": dict(self.checklist_item_results),
        }


PATH_CHECKLIST_ITEMS = (
    "target_malformed_check",
    "traversal_check",
    "protected_root_boundary",
    "prefix_confusion_check",
    "sanctioned_channel_scope",
    "writer_true_no_bypass",
)


def _norm_posix(p: str) -> str:
    p = p.replace(os.sep, "/") if os.sep != "/" else p
    p = re.sub(r"/+", "/", p)
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def _protected_root_for(rel: str):
    """Return the protected root that a POSIX-relative path falls under, or None.
    Exact-or-descendant match with a path-separator boundary (prefix confusion
    prevention: `state/registry-evil` is NOT `state/registry`)."""
    rel = _norm_posix(rel or "")
    for root in PROTECTED_REL_ROOTS:
        if rel == root or rel.startswith(root + "/"):
            return root
    return None


def _resolve_within_base(target, base):
    """Return (canonical_abspath, is_within_base) using lexical + symlink
    canonicalization. Raises ValueError on malformed input (fail-closed)."""
    if target is None or not isinstance(target, str) or not target.strip():
        raise ValueError(f"malformed target: {target!r}")
    if "\x00" in target:
        raise ValueError("malformed target: NUL byte")

    if base is None:
        # Deterministic default: the multi-agent-harness project root (two
        # levels up from tests/l3_reference). Matches the documented workspace
        # base without importing any production module.
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

    base_abs = os.path.abspath(base)
    t = target.strip()
    if not os.path.isabs(t):
        t = os.path.join(base_abs, t)

    lex = os.path.normpath(os.path.abspath(t))

    # Symlink resolution for the existing portion (deepest existing ancestor),
    # so dangling links cannot smuggle a traversal.
    if os.path.lexists(lex):
        real = os.path.realpath(lex)
    else:
        probe = lex
        while not os.path.lexists(probe) and probe != os.path.dirname(probe):
            probe = os.path.dirname(probe)
        head = os.path.realpath(probe) if os.path.lexists(probe) else os.path.abspath(probe)
        tail = lex[len(probe):] if lex.startswith(probe) else ""
        real = os.path.normpath(head + tail)

    base_real = os.path.realpath(base_abs)
    try:
        within = os.path.commonpath([real, base_real]) == base_real
    except ValueError:
        within = False
    return real, within


def classify_target(target, base=None) -> str:
    """One of PROTECTED | ALLOWED | OUTSIDE | MALFORMED (fail-closed)."""
    try:
        real, within = _resolve_within_base(target, base)
    except ValueError:
        return "MALFORMED"
    if not within:
        return "OUTSIDE"
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    rel = os.path.relpath(real, os.path.realpath(os.path.abspath(base)))
    if _protected_root_for(rel):
        return "PROTECTED"
    return "ALLOWED"


def authorize_write_reference(*, action, target, base=None, actor=None, writer=False) -> ReferencePathVerdict:
    """The independent path-based execution oracle.

    Returns a ReferencePathVerdict (never raises). DENY on any of:
      malformed target, traversal escape, protected path via a non-sanctioned
      channel, sanctioned channel writing outside its own root, writer=True on
      a generic action targeting a protected path. UNGOVERNED for reads.
    """
    results: dict[str, str] = {}

    if (action or "").lower() not in WRITE_ACTIONS:
        return ReferencePathVerdict("UNGOVERNED", "read action not governed",
                                    "execution_gate", "", dict(results))

    action_l = (action or "").lower()
    sanctioned = SANCTIONED_ROOTS.get(action_l)

    # Checklist item: target malformed check (fail-closed).
    try:
        real, within = _resolve_within_base(target, base)
        results["target_malformed_check"] = "pass"
    except ValueError as e:
        results["target_malformed_check"] = "fail"
        return ReferencePathVerdict("DENY", f"malformed target: {e}",
                                    "execution_gate", "MALFORMED", dict(results))

    cls = classify_target(target, base)
    results["traversal_check"] = "pass" if within else "fail"
    if not within:
        return ReferencePathVerdict(
            "DENY", f"target escapes authorized workspace: {target!r}",
            "execution_gate", "OUTSIDE", dict(results))

    base_real = os.path.realpath(os.path.abspath(base)) if base else os.path.realpath(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    rel = os.path.relpath(real, base_real)
    rel = _norm_posix(rel)
    root = _protected_root_for(rel)
    results["protected_root_boundary"] = "pass" if root is None else "fail"
    results["prefix_confusion_check"] = "pass"  # boundary logic is exact

    if root is not None:
        # Protected path: may be written ONLY via the channel sanctioned for
        # that exact root; writer=True on a generic action grants nothing.
        if not writer or sanctioned is None:
            results["writer_true_no_bypass"] = "fail"
            return ReferencePathVerdict(
                "DENY",
                f"target is a protected path (ADR 0002): {target!r}",
                "execution_gate", "PROTECTED", dict(results))
        results["sanctioned_channel_scope"] = "pass" if root == sanctioned else "fail"
        if root != sanctioned:
            return ReferencePathVerdict(
                "DENY",
                f"action {action_l!r} sanctioned only for {sanctioned!r}, "
                f"refused {root!r} target (writer channel is not a cross-root grant)",
                "execution_gate", "PROTECTED", dict(results))
        return ReferencePathVerdict("ALLOW", "sanctioned channel wrote its own root",
                                    "execution_gate", "PROTECTED", dict(results))

    # ALLOWED (non-protected) target.
    if sanctioned is not None:
        results["sanctioned_channel_scope"] = "fail"
        return ReferencePathVerdict(
            "DENY",
            f"action {action_l!r} sanctioned only for {sanctioned!r}, refused "
            f"non-protected target {target!r}",
            "execution_gate", "ALLOWED", dict(results))
    results["sanctioned_channel_scope"] = "pass"
    results["writer_true_no_bypass"] = "pass"
    return ReferencePathVerdict("ALLOW", "write to authorized workspace path",
                                "execution_gate", "ALLOWED", dict(results))


def oracle_execution_gate(context: dict) -> dict:
    """Wrapper for the verifier: takes a captured action request dict and
    returns the serializable verdict dict."""
    v = authorize_write_reference(
        action=context.get("action", ""),
        target=context.get("target", ""),
        base=context.get("base"),
        actor=context.get("actor"),
        writer=context.get("writer", False),
    )
    return v.to_dict()


__all__ = [
    "PROTECTED_REL_ROOTS",
    "SANCTIONED_ROOTS",
    "WRITE_ACTIONS",
    "ReferencePathVerdict",
    "classify_target",
    "authorize_write_reference",
    "oracle_execution_gate",
]

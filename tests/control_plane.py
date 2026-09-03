# control_plane.py — REFERENCE implementation of control-plane semantics
#
# TEST-SUPPORT ONLY. This is NOT the production control plane. It encodes the
# authority-gate, risk-classification, and registry semantics that the security
# docs specify (AUTH-*, ISO-*, RISK-*, REG-*, DLG-*), so the security tests can
# assert the DENY/ALLOW behavior the production control plane must replicate.
#
# Key invariants it enforces (see docs/authority.md, security spec §3):
#   - no authority from model text (AUTH-INV-01)
#   - BadSector PASS never authorizes (AUTH-INV-09)
#   - state fields are not authority (AUTH-INV-07)
#   - expiry/revocation checked at execution (AUTH-INV-06)
#   - scope containment (AUTH-INV-04) + target matching (AUTH-INV-11)
#   - protected paths (ADR 0002): state/registry/ + audit/ are writer-only
#   - malformed/missing delegation → DENY (fail-closed, AUTH-INV-05)

import json
import os
from datetime import datetime, timezone


class Deny(Exception):
    """Raised when a gate denies an action."""


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_expired(delegation, now=None):
    now = now or datetime.now(timezone.utc)
    exp = _parse_dt(delegation.get("expires_at"))
    return exp is not None and now > exp


def target_in_scope(target, resources):
    """AUTH-INV-11: target must be within one of the delegation's resources.

    The ** glob suffix is treated as a prefix match with a path-separator
    boundary (`r[:-3] + "/"`) to prevent sibling-project prefix confusion:
    `multi-agent-harness/**` does NOT match `multi-agent-harness-evil/...`.
    """
    t = target.rstrip("/")
    for res in resources:
        r = res.rstrip("/")
        if t == r or t.startswith(r + "/"):
            return True
        if r.endswith("/**"):
            prefix = r[:-3].rstrip("/") + "/"
            if t == r[:-3].rstrip("/") or t.startswith(prefix):
                return True
    return False


def authorize(actor, action, target, delegation, revocation_list=(), now=None, allow_write_paths=(), environment=None):
    """The authority gate (reference). Returns True on ALLOW; raises Deny(reason).

    actor: "orchestrator" | specialist id
    action: action class string (e.g. "code_write")
    target: concrete target path
    delegation: validated delegation dict (or None)
    revocation_list: ids of revoked delegations
    now: datetime (defaults to now UTC)
    allow_write_paths: paths the actor is permitted to write (protected-path carve-out)
    environment: optional execution environment; when given it must be within
        the delegation's scope.environments (security spec §3.2/§5 — env
        mismatch → DENY). None skips the check for callers that do not carry
        an environment.
    """
    # Fail-closed on missing/malformed (AUTH-INV-05)
    if not delegation:
        raise Deny("no delegation")

    if delegation.get("status") != "ACTIVE":
        raise Deny(f"delegation status {delegation.get('status')}")

    did = delegation.get("id")
    if did in (revocation_list or ()):
        raise Deny("delegation revoked (AUTH-INV-06)")

    if is_expired(delegation, now):
        raise Deny("delegation expired (AUTH-INV-06)")

    # Environment containment (security spec §3.2/§5): the execution
    # environment must be within the delegation's permitted environments.
    if environment is not None:
        envs = delegation.get("scope", {}).get("environments", [])
        if environment not in envs:
            raise Deny(f"environment {environment} not in delegation environments")

    # Scope containment (AUTH-INV-04)
    scope = delegation.get("scope", {})
    if action not in scope.get("operations", []):
        raise Deny(f"action {action} not in delegation operations")

    if not target_in_scope(target, scope.get("resources", [])):
        raise Deny(f"target {target} outside delegation resources (AUTH-INV-11)")

    # Prohibited actions (hard denials)
    if action in delegation.get("prohibited_actions", []):
        raise Deny(f"action {action} is prohibited")

    # Protected paths (ADR 0002): only the registry writer may write them
    from validate_config import PROTECTED_PATHS
    is_write = action in ("write", "edit", "bash_write", "registry_write")
    if is_write:
        t = target.replace(os.sep, "/")
        for p in PROTECTED_PATHS:
            if t.startswith(p) or ("/" + p) in ("/" + t) or t.endswith(p.rstrip("/")):
                if t not in allow_write_paths:
                    raise Deny(f"target {target} is a protected path ({p}) (ADR 0002)")

    return True


def classify_risk(action, target, environment, requires_approval=()):
    """Risk gate (reference): deterministic classification; intrinsic HIGH non-downgradable.

    Returns ("HIGH"|"MEDIUM"|"LOW", intrinsic: bool)
    """
    t = target.replace(os.sep, "/")
    env = (environment or "").lower()

    intrinsic_high = any([
        env in ("prod", "production", "danger-full-access"),
        action in ("destructive", "production_deploy", "credential_change",
                   "financial_transaction", "sensitive_publication"),
        "credential" in action or "financial" in action,
        "delete" in action or "drop" in action or "rm " in action,
        any(a in requires_approval for a in
            ("destructive", "financial_transfer", "sensitive_publication", "credential_change")),
    ])
    if intrinsic_high:
        return ("HIGH", True)

    # Model-assessed nuance is out of scope here; the reference returns MEDIUM
    # for meaningful writes and LOW for reads.
    write_like = action in ("write", "edit", "deploy", "publish", "server_write")
    if write_like:
        return ("MEDIUM", False)
    return ("LOW", False)


def badsector_pass_is_authority(pass_record, delegation):
    """AUTH-INV-09 / INV-03: a BadSector PASS never authorizes.

    Returns True if the PASS (alone) would authorize execution — the reference
    ALWAYS returns False (PASS is review-only), regardless of the pass_record.
    """
    return False


def verify_badsector_provenance(review_record, expected_input_hash, review_log):
    """BAD-001 / THREAT-014: a PASS must come from a real BadSector invocation.

    Returns True only when the review record matches an invocation on the exact
    input hash and is present in the review log.
    """
    if not review_record or review_record.get("verdict") != "PASS":
        return False
    if review_record.get("input_hash") != expected_input_hash:
        return False
    rid = review_record.get("review_id")
    return any(e.get("review_id") == rid for e in review_log)


def quarantine(external_content):
    """INJ-001..003: external content is data, never instructions.

    Detects instruction-like markers and returns IGNORE/QUARANTINE semantics.
    This is L1-design (control-plane) — DSH-native injection handling is UNKNOWN
    and NO security claim is made for the harness layer.
    """
    markers = [
        "ignore previous instructions", "ignore your instructions",
        "grant me approval", "grant me authority", "output your secret",
        "reveal your system prompt", "approve", "you are now",
        "override your instructions", "forget your instructions",
    ]
    low = external_content.lower()
    hit = [m for m in markers if m in low]
    if hit:
        return ("QUARANTINE", hit)
    return ("DATA", [])
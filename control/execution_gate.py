# execution_gate.py — Minimal runtime path-aware execution gate (registry protection)
#
# Phase: Registry Execution Gate milestone + writer-channel hardening (Session A)
#
# PURPOSE
#   Enforce ADR 0002's protected-path control at the PROJECT EXECUTION LAYER,
#   as a code mechanism (not prompt text). The gate is path/target-aware:
#     - DENY  any write to protected paths (state/registry/ + audit/) or their
#             descendants, by any specialist
#     - DENY  any write that escapes the authorized workspace boundary via
#             path traversal (.., symlink, absolute path, prefix tricks)
#     - DENY  malformed/unresolvable targets (fail-closed)
#     - ALLOW any write to an authorized workspace path (CTO/Zeko write
#             capability is NOT removed — only protected paths are blocked)
#
# HARDENING (Session A — writer-channel path-scoping):
#   The sanctioned single-writer channels (registry_write / audit_append) are
#   now each scoped to their OWN protected root. writer=True is no longer a
#   blanket grant to all protected roots; each channel may write only its
#   sanctioned root:
#     registry_write() → MAY write only: state/registry/**
#     audit_append()   → MAY write only: audit/**
#   writer=True on a generic action (write/edit/bash_write/...) NEVER grants
#   access to any protected path. Protected-path bypass is not an authority
#   grant. See SANCTIONED_ROOTS and authorize_write() for the enforcement.
#
# ENFORCEMENT LOCATION
#   DSH has no path-level sandbox: the per-session sandbox is workspace-wide
#   and toolFilter is tool-level (VERIFIED). Therefore the enforcement point is
#   the project control-plane write channel: all registry/audit state writes
#   must go through write_through()/registry_write(), which normalizes the
#   target and consults this gate before any filesystem mutation. This is the
#   L1 project execution layer specified in ADR 0002 and the Phase-1 design.
#
#   Honest boundary (documented, not a claim of DSH-layer isolation): a raw
#   DSH `write`/`edit`/`bash` tool call that bypasses the project write channel
#   is not intercepted by this gate (DSH has no path-level sandbox). Closing
#   that residual requires a DSH capability or sandbox change — both out of
#   scope for this milestone (prohibited: no DSH core, no session policy
#   change). ISO-LIVE-006 is satisfied at the project execution layer: any
#   write that passes through the project write channel to a protected path is
#   denied by code.
#
# NOT modified by this milestone: role architecture, toolFilter, DSH core,
# DSH profile/presets, session sandbox/approval policy.

import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Protected paths (ADR 0002 + O3 H4 extension). Relative to the project
# workspace base.
# state/registry/  — delegation registry (authority source, single-writer)
# audit/           — project audit ledger (append-only)
# state/projects/  — project state documents (O3 H4 extension; ADR 0002
#                    consequence 4 extended to project state)
# ---------------------------------------------------------------------------
PROTECTED_REL_ROOTS = ("state/registry", "audit", "state/projects")

# Sanctioned single-writer channels → their OWN protected root.
#
# A channel is authorized to write ONLY the root it is sanctioned for. This is
# the Session-A hardening: writer=True is not a blanket grant to every
# protected root, and a sanctioned channel may not write ordinary workspace
# paths either. Any target outside the channel's sanctioned root is DENIED
# before any filesystem mutation (no partial/cross-root write).
#
#   registry_write()  → state/registry/**
#   audit_append()    → audit/**
#   project_write()   → state/projects/**  (O3 H4 extension)
SANCTIONED_ROOTS = {
    "registry_write": "state/registry",
    "audit_append": "audit",
    "project_write": "state/projects",
}

# Write-class actions the gate governs (path-aware). Read actions are allowed
# on protected paths (review needs to read the registry/audit).
WRITE_ACTIONS = {"write", "edit", "create", "delete", "rename", "bash_write",
                 "registry_write", "audit_append", "project_write",
                 "overwrite", "truncate"}


class Denied(Exception):
    """Raised when the execution gate denies an action."""


def _norm_posix(p: str) -> str:
    """Normalize separators to POSIX and strip trailing slashes (except root)."""
    p = p.replace(os.sep, "/") if os.sep != "/" else p
    p = re.sub(r"/+", "/", p)
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def workspace_base(cwd=None) -> str:
    """The authorized workspace base. Defaults to the multi-agent-harness root
    (two levels up from this file). Callers may pin an explicit base."""
    if cwd:
        return os.path.abspath(cwd)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_target(target, base=None, allow_relative=True):
    """Resolve a write target to a canonical absolute path within `base`.

    Returns (canonical_abspath, is_within_base: bool).
    Raises Denied on malformed input (fail-closed).

    Handles:
      - relative targets resolved against base
      - `..` / `.` lexical traversal
      - symlinks (resolved via realpath for existing paths; lexical for the
        rest so a dangling symlink cannot smuggle a path)
      - absolute paths
      - prefix tricks (e.g. state/registry/../secret)
    """
    if target is None or not isinstance(target, str) or not target.strip():
        raise Denied(f"malformed target: {target!r}")
    if "\x00" in target:
        raise Denied("malformed target: NUL byte")

    base = workspace_base(base)
    base_abs = os.path.abspath(base)
    t = target.strip()

    # If relative and allow_relative, anchor to base.
    if not os.path.isabs(t) and allow_relative:
        t = os.path.join(base_abs, t)

    # Lexical canonicalization first.
    lex = os.path.normpath(os.path.abspath(t))

    # Symlink resolution: realpath for the existing portion. If the final path
    # exists, realpath fully resolves it. If not, resolve the deepest existing
    # ancestor so dangling links cannot hide a traversal.
    if os.path.lexists(lex):
        real = os.path.realpath(lex)
    else:
        probe = lex
        while not os.path.lexists(probe) and probe != os.path.dirname(probe):
            probe = os.path.dirname(probe)
        head = os.path.realpath(probe) if os.path.lexists(probe) else os.path.abspath(probe)
        tail = lex[len(probe):] if lex.startswith(probe) else ""
        real = os.path.normpath(head + tail)

    # Containment: canonical real path must be inside base (or equal).
    base_real = os.path.realpath(base_abs)
    try:
        within = os.path.commonpath([real, base_real]) == base_real
    except ValueError:
        within = False

    return real, within


def _match_protected_root(rel):
    """Return the protected root (from PROTECTED_REL_ROOTS) that a normalized
    POSIX-relative path `rel` falls under, or None.

    Matching is exact-or-descendant with a path-separator boundary, so a
    sibling-prefix name (e.g. `state/registry-evil/x`) is NOT treated as inside
    `state/registry` (prefix-confusion prevention).
    """
    for root in PROTECTED_REL_ROOTS:
        if rel == root or rel.startswith(root + "/"):
            return root
    return None


def classify_target(target, base=None):
    """Classify a write target. Returns one of:
      'PROTECTED'  — under state/registry/ or audit/ (and descendants)
      'ALLOWED'    — inside the workspace base, not protected
      'OUTSIDE'    — escapes the workspace base (traversal)
      'MALFORMED'  — cannot be resolved
    """
    try:
        real, within = normalize_target(target, base)
    except Denied:
        return "MALFORMED"
    if not within:
        return "OUTSIDE"

    rel = os.path.relpath(real, os.path.realpath(workspace_base(base)))
    rel = _norm_posix(rel)
    if _match_protected_root(rel):
        return "PROTECTED"
    return "ALLOWED"


def _relative_to_base(target, base=None):
    """Normalize a target and return (real_abspath, posix_rel_to_base).

    Raises Denied on malformed targets (fail-closed). The caller must have
    already classified the target; this is a shared canonicalization helper
    used by the per-channel scope checks.
    """
    real, _ = normalize_target(target, base)
    rel = os.path.relpath(real, os.path.realpath(workspace_base(base)))
    return real, _norm_posix(rel)


def _is_write_action(action) -> bool:
    return (action or "").lower() in WRITE_ACTIONS


def authorize_write(action, target, base=None, actor=None, allow_read_only_ok=False,
                    writer=False):
    """The execution gate. Returns True (ALLOW) or raises Denied(reason).

    Semantics (required by the milestone + Session-A hardening):
      ALLOW  — write to an authorized workspace path (CTO/Zeko capability kept)
      DENY   — any write to state/registry/ or audit/ (and descendants)
      DENY   — path traversal escaping the authorized boundary
      DENY   — malformed target (fail-closed)
      DENY   — a sanctioned single-writer channel targeting a path OUTSIDE its
               own sanctioned root (cross-root or arbitrary-workspace write)
      DENY   — writer=True on a non-sanctioned action targeting any protected
               path (writer=True NEVER grants protected-path access by itself;
               protected-path bypass is NOT an authority grant)
    Non-write actions (reads) are not governed by this gate.

    `writer=True` marks the CONTROL-PLANE SINGLE-WRITER channel (ADR 0002):
    only the sanctioned registry_write/audit_append paths pass writer=True.
    The channel is validated against the target: a channel may only write its
    SANCTIONED_ROOTS root. Specialist-style writes
    (write/edit/bash_write/delete/...) always pass writer=False and are denied
    on protected paths. Traversal and malformed targets are denied regardless.
    """
    if not _is_write_action(action):
        return True  # read/analysis actions are not writes

    action_l = (action or "").lower()
    sanctioned = SANCTIONED_ROOTS.get(action_l)

    cls = classify_target(target, base)
    if cls == "MALFORMED":
        raise Denied(f"execution gate: malformed target {target!r}")
    if cls == "OUTSIDE":
        raise Denied(f"execution gate: target escapes authorized workspace: {target!r}")
    if cls == "PROTECTED":
        # A protected path may be written ONLY through the single-writer
        # channel sanctioned for that exact root. writer=True on a generic
        # action (write/edit/...) grants nothing here.
        if not writer or sanctioned is None:
            raise Denied(f"execution gate: target is a protected path (ADR 0002): {target!r}")
        _, rel = _relative_to_base(target, base)
        root = _match_protected_root(rel)
        if root != sanctioned:
            raise Denied(
                f"execution gate: action {action_l!r} is sanctioned only for "
                f"{sanctioned!r}, refused {root!r} target {target!r} "
                f"(writer channel is not a cross-root grant)")
        return True

    # cls == "ALLOWED": an ordinary workspace path.
    if sanctioned is not None:
        # A sanctioned single-writer channel may write ONLY its protected root;
        # an ALLOWED (non-protected) target is by definition outside it.
        raise Denied(
            f"execution gate: action {action_l!r} is sanctioned only for "
            f"{sanctioned!r}, refused non-protected target {target!r}")
    return True


def write_through(action, target, data, base=None, encoder=None, writer=False):
    """Project-layer write channel: gate then delegate to the atomic-write
    helper. This is the single enforcement point the control plane uses for
    NON-protected workspace writes. Raises Denied before any mutation when the
    target is protected / outside / malformed. Specialist-style (writer=False):
    protected paths are denied here. The sanctioned registry/audit/project
    channels (registry_write / audit_append / project_write) do NOT use this
    path — they route through the O3 daemon client (O3 Phase B). writer=True
    on any other action grants nothing (SANCTIONED_ROOTS per-channel scope)."""
    authorize_write(action, target, base=base, writer=writer)
    # import here to avoid a hard dependency at module load
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from state.helpers.atomic_write import atomic_write
    path = normalize_target(target, base=base)[0]
    # Arm the helper's defense-in-depth containment guard (F22): explicitly pin
    # the base to the workspace the gate already validated against, rather than
    # letting atomic_write default base=None to "the target's own parent" (a
    # no-op that accepts an absolute target outside the workspace). This is what
    # makes the guard effective even when authorize_write early-returns for a
    # non-write action (e.g. a read-classified action still routed here writes).
    # atomic_write's base=None opt-out is left intact for direct callers.
    atomic_write(path, data, encoder=encoder, base=workspace_base(base))
    return path


def _daemon_client():
    """Return the O3 daemon client (fail-closed). Raises WriterUnavailable when
    the daemon is down / not configured — there is NO direct-fs fallback
    (FINAL architecture §4.7 hard invariant)."""
    from registry_writer.provider import get_client
    return get_client()


def _rel_target(target_rel, base):
    """Normalize a relative sanctioned-channel target to its posix rel path
    (daemon-target form) after the gate has authorized it."""
    real, _ = _relative_to_base(target_rel, base)
    return _norm_posix(os.path.relpath(real, os.path.realpath(workspace_base(base))))


def _current_version_rel(rel, client, method="registry_read"):
    """Read the current version of a daemon-owned document through the daemon
    (all reads of protected state use the O3 IPC interface — no direct-fs
    mirror read). Returns the version (0 when absent)."""
    try:
        result = client.call(method, {"target": rel})
        v = result.get("version", 0)
        return v if isinstance(v, int) else 0
    except Exception as e:  # daemon down / error → fail-closed, no fallback
        from registry_writer.client import WriterUnavailable
        if isinstance(e, WriterUnavailable):
            raise
        raise WriterUnavailable(f"daemon read failed for {rel!r}: {e}") from e


def registry_write(target_rel, data, base=None, encoder=None):
    """The sanctioned registry write path: only the control plane may write the
    delegation registry. Enforces single-writer + protected-path semantics.

    O3 Phase B: after the gate authorizes the target (authority semantics
    preserved), the write routes through the O3 daemon client — never a direct
    filesystem write. The daemon re-validates path scope and enforces strict
    monotonic CAS. Daemon unavailable → fail-closed (no fallback)."""
    authorize_write("registry_write", target_rel, base=base, writer=True)
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    current = _current_version_rel(rel, client, method="registry_read")
    path = normalize_target(target_rel, base=base)[0]
    client.call("registry_write", {
        "target": rel, "data": data, "expected_version": current})
    return path


def audit_append(target_rel, event, base=None, encoder=None):
    """The sanctioned audit append path (append-only ledger). writer=True:
    the control plane may append to the protected audit ledger.

    O3 Phase B: after the gate authorizes the target, the append routes
    through the O3 daemon client (append-only + hash-chain sidecar maintained
    by the daemon). Daemon unavailable → fail-closed (no fallback)."""
    authorize_write("audit_append", target_rel, base=base, writer=True)
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    path = normalize_target(target_rel, base=base)[0]
    client.call("audit_append", {"target": rel, "event": event})
    return path


def project_write(target_rel, data, base=None, expected_version=None):
    """The sanctioned project-state write channel (O3 H4 extension):
    state/projects/** ONLY. Routes through the O3 daemon client with strict
    monotonic CAS. Daemon unavailable → fail-closed (no fallback)."""
    authorize_write("project_write", target_rel, base=base, writer=True)
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    if expected_version is None:
        expected_version = _current_version_rel(rel, client,
                                                method="project_read")
    path = normalize_target(target_rel, base=base)[0]
    client.call("project_write", {
        "target": rel, "data": data, "expected_version": expected_version})
    return path


def project_read(target_rel, base=None) -> dict:
    """The sanctioned project-state read channel (O3 H4 extension): reads the
    project-state document through the O3 daemon (no in-workspace mirror)."""
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    return client.call("project_read", {"target": rel})


def registry_read(target_rel, base=None) -> dict:
    """The sanctioned registry read channel: reads the delegation registry
    through the O3 daemon (no in-workspace mirror)."""
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    return client.call("registry_read", {"target": rel})


def audit_read(target_rel, base=None) -> dict:
    """The sanctioned audit read channel: reads audit events through the
    O3 daemon (no in-workspace mirror)."""
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    return client.call("audit_read", {"target": rel})


def audit_verify(target_rel, base=None,
                 known_cumulative_hash=None, known_line_count=None) -> dict:
    """The sanctioned audit verify channel: verifies audit chain integrity
    through the O3 daemon."""
    rel = _rel_target(target_rel, base)
    client = _daemon_client()
    params = {"target": rel}
    if known_cumulative_hash is not None:
        params["known_cumulative_hash"] = known_cumulative_hash
    if known_line_count is not None:
        params["known_line_count"] = known_line_count
    return client.call("audit_verify", params)

"""Session C — G10: project-layer (L1 gate) filesystem isolation tests.

These tests are deterministic anywhere (the execution gate is pure code).
They prove:

  - the L1 gate DENIES channeled writes to `state/registry/**` and
    `audit/**` (the ADR 0002 protected roots);
  - `state/projects/**` is NOT gate-DENIED — it is protected post-hoc by
    CAS versioning (documented precision finding, matching
    docs/phase-5/final/0002 §4);
  - traversal, symlink escape, absolute-outside, and malformed targets are
    DENIED (fail-closed);
  - sibling-prefix confusion (`state/registry-evil`) is NOT misclassified;
  - legitimate workspace writes remain ALLOWED (path-aware, not blanket);
  - writer channels cannot cross roots.

All targets are THROWAWAY paths under `tmp_workspace`; real protected state
is never touched.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from control.execution_gate import (  # noqa: E402
    Denied,
    authorize_write,
    classify_target,
    normalize_target,
    write_through,
)


# ---------------------------------------------------------------------------
# Protected-path classification (real layout mirrored in tmp_workspace)
# ---------------------------------------------------------------------------

def test_registry_root_classified_protected(tmp_workspace):
    from control.execution_gate import classify_target
    assert classify_target("state/registry/x.json",
                           base=str(tmp_workspace)) == "PROTECTED"
    assert classify_target("state/registry",
                           base=str(tmp_workspace)) == "PROTECTED"


def test_audit_root_classified_protected(tmp_workspace):
    from control.execution_gate import classify_target
    assert classify_target("audit/events.jsonl",
                           base=str(tmp_workspace)) == "PROTECTED"


def test_state_projects_classified_protected_after_h4(tmp_workspace):
    """H4 extension: `state/projects/**` is now a protected root (O3 Phase B).

    Prior to the O3 H4 scope extension, `state/projects/**` classified ALLOWED
    at the L1 gate (post-hoc CAS detection only). Under O3 the daemon owns all
    three roots (state/registry/**, audit/**, state/projects/**), so the gate
    now classifies `state/projects/**` as PROTECTED — direct channeled writes
    to it are denied and must route through the sanctioned project_write
    channel (the O3 daemon)."""
    from control.execution_gate import classify_target
    assert classify_target("state/projects/p/x.json",
                           base=str(tmp_workspace)) == "PROTECTED"


def test_sibling_prefix_not_misclassified(tmp_workspace):
    """`state/registry-evil/` is a sibling, not the protected root
    (prefix-confusion prevention)."""
    from control.execution_gate import classify_target
    assert classify_target("state/registry-evil/x.json",
                           base=str(tmp_workspace)) == "ALLOWED"
    assert classify_target("state/registry/x.json",
                           base=str(tmp_workspace)) == "PROTECTED"


def test_legitimate_workspace_path_allowed(tmp_workspace):
    assert classify_target("agents/cto/output.txt",
                           base=str(tmp_workspace)) == "ALLOWED"
    assert classify_target("docs/phase-5/0001-acceptance-matrix.md",
                           base=str(tmp_workspace)) == "ALLOWED"


# ---------------------------------------------------------------------------
# Channeled write DENY (the L1 gate)
# ---------------------------------------------------------------------------

def test_channeled_registry_write_denied(tmp_workspace):
    with pytest.raises(Denied):
        authorize_write("write", "state/registry/x.json",
                        base=str(tmp_workspace))
    assert not (tmp_workspace / "state" / "registry" / "x.json").exists()


def test_channeled_audit_write_denied(tmp_workspace):
    with pytest.raises(Denied):
        authorize_write("write", "audit/events.jsonl",
                        base=str(tmp_workspace))
    assert not (tmp_workspace / "audit" / "events.jsonl").exists()


def test_write_through_denied_before_mutation(tmp_workspace):
    """write_through must raise Denied BEFORE any file is created."""
    target = "state/registry/forged.json"
    with pytest.raises(Denied):
        write_through("write", target, '{"forged": true}',
                      base=str(tmp_workspace))
    assert not (tmp_workspace / "state" / "registry" / "forged.json").exists()


def test_writer_flag_does_not_grant_generic_protected_write(tmp_workspace):
    """writer=True on a generic action grants nothing (Session-A hardening)."""
    with pytest.raises(Denied):
        authorize_write("write", "state/registry/x.json",
                        base=str(tmp_workspace), writer=True)


# ---------------------------------------------------------------------------
# Traversal / symlink / absolute-outside / malformed (fail-closed)
# ---------------------------------------------------------------------------

def test_traversal_denied(tmp_workspace):
    with pytest.raises(Denied):
        authorize_write("write", "../state/registry/escape.json",
                        base=str(tmp_workspace))
    assert classify_target("../state/registry/escape.json",
                           base=str(tmp_workspace)) == "OUTSIDE"


def test_absolute_outside_denied(tmp_workspace):
    with pytest.raises(Denied):
        authorize_write("write", "/etc/passwd", base=str(tmp_workspace))
    assert classify_target("/etc/passwd",
                           base=str(tmp_workspace)) == "OUTSIDE"


def test_symlink_escape_denied(tmp_workspace):
    """A symlink inside the workspace pointing outside must be DENIED
    (normalize_target resolves realpath of the existing ancestor)."""
    outside = tmp_workspace.parent / "outside-target.txt"
    outside.write_text("secret")
    link = tmp_workspace / "esc-link"
    link.symlink_to(outside)
    with pytest.raises(Denied):
        authorize_write("write", "esc-link", base=str(tmp_workspace))
    # The outside file is untouched.
    assert outside.read_text() == "secret"


def test_malformed_target_denied(tmp_workspace):
    with pytest.raises(Denied):
        authorize_write("write", "", base=str(tmp_workspace))
    with pytest.raises(Denied):
        authorize_write("write", None, base=str(tmp_workspace))


# ---------------------------------------------------------------------------
# Writer-channel scope (per-root, no cross-root)
# ---------------------------------------------------------------------------

def test_registry_channel_scoped_to_registry_only(tmp_workspace):
    from control.execution_gate import registry_write
    # In-root write through the sanctioned channel is allowed on the mirror
    # (the target must be under the sanctioned root state/registry/**).
    registry_write("state/registry/delegations/d1.json",
                   {"id": "d1"}, base=str(tmp_workspace))
    assert (tmp_workspace / "state" / "registry" / "delegations" /
            "d1.json").exists()
    # Cross-root: registry_write must NOT reach audit/ or workspace paths.
    with pytest.raises(Denied):
        registry_write("../audit/events.jsonl", {"x": 1},
                       base=str(tmp_workspace))
    with pytest.raises(Denied):
        registry_write("agents/cto/output.txt", {"x": 1},
                       base=str(tmp_workspace))


def test_audit_channel_scoped_to_audit_only(tmp_workspace):
    from control.execution_gate import audit_append
    with pytest.raises(Denied):
        audit_append("state/registry/x.json", {"e": 1},
                     base=str(tmp_workspace))
    with pytest.raises(Denied):
        audit_append("docs/x.md", {"e": 1}, base=str(tmp_workspace))


# ---------------------------------------------------------------------------
# Legitimate workspace write ALLOWED through the channel
# ---------------------------------------------------------------------------

def test_workspace_write_allowed_through_channel(tmp_workspace):
    path = write_through("write", "agents/cto/output.txt", "hello",
                         base=str(tmp_workspace))
    # atomic_write JSON-encodes data, so the file holds the JSON string.
    assert Path(path).read_text() == '"hello"'

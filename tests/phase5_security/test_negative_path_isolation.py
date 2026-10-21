"""Phase-5 Session A — DSH / role security hardening negative tests.

These tests DOCUMENT the residual (proven open) rather than closing it:

  - a raw filesystem write by a bash-capable role is NOT intercepted by the
    DSH layer (the project execution gate only governs CHANNELED writes);
  - the SAME target through the project execution gate IS denied;
  - read-only roles exclude write/edit/bash at the tool-surface level;
  - traversal is denied through the project channel;
  - no claim of DSH-layer path isolation closure is made.

All negative tests operate on a THROWAWAY temp workspace (never the real
`state/registry/` or `audit/`). They prove the threat boundary; they do not
exploit it and do not modify real protected state.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest


def test_bash_capable_roles_identified(bash_capable_roles):
    """The residual actor set is exactly the roles with raw bash."""
    # Zeko, CTO, Somad, Nova allow bash; CFO, Kai, BadSector deny it.
    assert "zeko" in bash_capable_roles
    assert "cto" in bash_capable_roles
    assert "cfo" not in bash_capable_roles
    assert "kai" not in bash_capable_roles


def test_readonly_roles_identified(readonly_roles):
    """CFO/Kai/BadSector deny write/edit/bash at the tool-surface level."""
    assert "cfo" in readonly_roles
    assert "kai" in readonly_roles
    assert "badsector" in readonly_roles
    assert "cto" not in readonly_roles


def test_raw_write_reaches_protected_path_unintercepted(tmp_workspace):
    """RESIDUAL PROVEN OPEN: a raw filesystem write to the protected-path
    layout is NOT intercepted by any DSH-layer mechanism.

    This documents the threat boundary: the project execution gate governs
    writes that ROUTE THROUGH the project channel; a raw tool call that
    bypasses the channel is not intercepted (ADR 0002 residual).
    """
    target = tmp_workspace / "state" / "registry" / "x.json"
    with open(target, "w") as f:
        f.write('{"forged": true}')
    # The write landed — the DSH layer did not intercept it.
    assert target.exists()
    assert target.read_text() == '{"forged": true}'


def test_project_channel_write_denied(tmp_workspace):
    """The SAME target through the project execution gate IS denied (L1 gate
    works)."""
    from control.execution_gate import authorize_write, Denied
    target = "state/registry/x.json"
    with pytest.raises(Denied):
        authorize_write("write", target, base=str(tmp_workspace))
    # No file was created through the channel.
    assert not (tmp_workspace / "state" / "registry" / "x.json").exists()


def test_project_channel_audit_write_denied(tmp_workspace):
    from control.execution_gate import authorize_write, Denied
    with pytest.raises(Denied):
        authorize_write("write", "audit/events.jsonl", base=str(tmp_workspace))
    assert not (tmp_workspace / "audit" / "events.jsonl").exists()


def test_traversal_denied(tmp_workspace):
    """Traversal through the project channel is denied (no escape)."""
    from control.execution_gate import authorize_write, Denied
    with pytest.raises(Denied):
        authorize_write("write", "../state/registry/escape.json",
                        base=str(tmp_workspace))
    # Prefix-confusion PREVENTION: `state/registry-evil` is NOT misclassified
    # as the protected `state/registry` root (it classifies as an ordinary
    # ALLOWED path — the sibling prefix is not treated as protected).
    from control.execution_gate import classify_target
    assert classify_target("state/registry-evil/x.json",
                           base=str(tmp_workspace)) == "ALLOWED"
    assert classify_target("state/registry/x.json",
                           base=str(tmp_workspace)) == "PROTECTED"


def test_workspace_write_allowed(tmp_workspace):
    """A normal workspace write through the channel IS allowed (the gate is
    path-aware, not blanket-denying)."""
    from control.execution_gate import authorize_write
    authorize_write("write", "agents/cto/output.txt", base=str(tmp_workspace))


def test_no_path_isolation_closure_claim():
    """The session must NOT claim DSH-layer path isolation is closed."""
    # Repo root is three levels above tests/phase5_security/.
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    doc = os.path.join(root, "docs", "phase-5",
                       "0001-security-hardening-analysis.md")
    with open(doc) as f:
        text = f.read()
    assert "NOT closed" in text or "not closed" in text
    assert "no claim of path isolation closed" in text.lower() or \
        "no claim" in text.lower()
    # The residual must be stated as open.
    assert "OPEN" in text or "proven open" in text

"""Unit tests — execution gate (registry protection, ADR 0002).

Required semantics under test:
  - protected path (state/registry/, audit/ + descendants) → DENY
  - allowed project path → ALLOW
  - malformed target → DENY (fail-closed)
  - traversal / scope bypass → DENY
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from control.execution_gate import (
    Denied,
    authorize_write,
    classify_target,
    normalize_target,
    workspace_base,
)


def _mkbase(tmp_path):
    base = tmp_path / "workspace"
    base.mkdir(parents=True)
    (base / "state").mkdir()
    (base / "state" / "registry").mkdir()
    (base / "audit").mkdir()
    (base / "agents").mkdir()
    (base / "agents" / "cto").mkdir()
    return str(base)


class TestProtectedPaths:
    """DENY: state/registry/ and audit/ and their descendants."""

    @pytest.mark.parametrize("target", [
        "state/registry",
        "state/registry/",
        "state/registry/delegations.json",
        "state/registry/deep/sub/delegations.json",
        "audit",
        "audit/",
        "audit/events.jsonl",
        "audit/proj-1/events.jsonl",
    ])
    def test_protected_path_denied(self, tmp_path, target):
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("write", target, base=base)
        with pytest.raises(Denied):
            authorize_write("registry_write", target, base=base)
        with pytest.raises(Denied):
            authorize_write("audit_append", target, base=base)

    @pytest.mark.parametrize("action", [
        "delete", "rename", "overwrite", "truncate", "edit", "create",
    ])
    def test_protected_path_denied_for_all_write_actions(self, tmp_path, action):
        """Every write-class action on a protected path is DENIED (not just
        `write`)."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write(action, "state/registry/delegations.json", base=base)
        with pytest.raises(Denied):
            authorize_write(action, "audit/events.jsonl", base=base)

    def test_protected_absolute_path_denied(self, tmp_path):
        base = _mkbase(tmp_path)
        abs_target = os.path.join(base, "state", "registry", "delegations.json")
        with pytest.raises(Denied):
            authorize_write("write", abs_target, base=base)

    def test_write_through_does_not_mutate_protected(self, tmp_path):
        """write_through must raise BEFORE any filesystem mutation."""
        from control.execution_gate import write_through
        base = _mkbase(tmp_path)
        target = os.path.join(base, "state", "registry", "should-not-exist.json")
        with pytest.raises(Denied):
            write_through("write", target, {"v": 1}, base=base)
        assert not os.path.exists(target)

    def test_delete_through_does_not_mutate_protected(self, tmp_path):
        """A delete routed through the write channel on a protected path must be
        refused and must not remove the target."""
        from control.execution_gate import write_through, Denied
        base = _mkbase(tmp_path)
        existing = os.path.join(base, "state", "registry", "delegations.json")
        with open(existing, "w") as f:
            f.write("{}")
        with pytest.raises(Denied):
            write_through("delete", existing, None, base=base)
        assert os.path.exists(existing)  # untouched

    def test_registry_write_works_for_registry_path(self, o3_daemon_ws):
        """The sanctioned registry_write channel writes to the registry path.
        After O3 Phase B, registry_write routes through the O3 daemon client;
        this test uses the temp-daemon fixture (daemon root == workspace)."""
        from control.execution_gate import registry_write
        base, client, daemon = o3_daemon_ws
        path = registry_write("state/registry/delegations.json", {"v": 1}, base=base)
        assert os.path.exists(path)


class TestWriterChannelScope:
    """Session-A hardening: per-channel sanctioned roots.

    registry_write() MAY write only state/registry/**
    audit_append()   MAY write only audit/**
    writer=True NEVER bypasses target-path validation.
    """

    # -- registry_write must not reach other protected roots -----------------
    @pytest.mark.parametrize("target", [
        "audit",
        "audit/events.jsonl",
        "audit/proj-1/events.jsonl",
    ])
    def test_registry_write_cross_root_audit_denied(self, tmp_path, target):
        """registry_write targeting audit/ (a different protected root) → DENY."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("registry_write", target, base=base, writer=True)
        # and through the live channel, with no mutation
        from control.execution_gate import registry_write
        with pytest.raises(Denied):
            registry_write(target, {"v": 1}, base=base)
        assert not os.path.exists(os.path.join(base, "audit", "events.jsonl"))

    @pytest.mark.parametrize("target", [
        "agents/cto/policy.yaml",
        "docs/README.md",
        "state/other/note.json",   # state/ but NOT state/registry/
        "config/agents.yaml",
    ])
    def test_registry_write_cannot_write_outside_registry_root(self, tmp_path, target):
        """registry_write targeting a non-protected workspace path → DENY
        (the writer channel is NOT a general write path)."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("registry_write", target, base=base, writer=True)
        from control.execution_gate import registry_write
        with pytest.raises(Denied):
            registry_write(target, {"v": 1}, base=base)
        assert not os.path.exists(os.path.join(base, target.replace("/", os.sep)))

    def test_registry_write_deep_descendant_ok(self, o3_daemon_ws):
        """Descendants of the sanctioned root remain writable (state/registry/**).
        After O3 Phase B, registry_write routes through the O3 daemon client;
        this test uses the temp-daemon fixture (daemon root == workspace)."""
        from control.execution_gate import registry_write
        base, client, daemon = o3_daemon_ws
        path = registry_write("state/registry/deep/sub/x.json", {"v": 1}, base=base)
        assert os.path.exists(path)

    # -- audit_append must not reach other protected roots -------------------
    @pytest.mark.parametrize("target", [
        "state/registry",
        "state/registry/delegations.json",
        "state/registry/deep/sub/d.json",
    ])
    def test_audit_append_cross_root_registry_denied(self, tmp_path, target):
        """audit_append targeting state/registry/ (a different protected root)
        → DENY, before any mutation."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("audit_append", target, base=base, writer=True)
        from control.execution_gate import audit_append
        event = {"event_id": "e1", "actor": "test", "action": "x", "target": "t"}
        with pytest.raises(Denied):
            audit_append(target, event, base=base)
        assert not os.path.exists(os.path.join(base, "state", "registry", "delegations.json"))

    @pytest.mark.parametrize("target", [
        "agents/cto/policy.yaml",
        "docs/README.md",
        "state/other/note.json",
    ])
    def test_audit_append_cannot_write_outside_audit_root(self, tmp_path, target):
        """audit_append targeting a non-protected workspace path → DENY."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("audit_append", target, base=base, writer=True)

    def test_audit_append_descendant_ok(self, o3_daemon_ws):
        """Descendants of the sanctioned root remain appendable (audit/**).
        After O3 Phase B, audit_append routes through the O3 daemon client;
        this test uses the temp-daemon fixture (daemon root == workspace)."""
        from control.execution_gate import audit_append
        base, client, daemon = o3_daemon_ws
        event = {"event_id": "e1", "actor": "test", "action": "x", "target": "t"}
        path = audit_append("audit/proj-1/events.jsonl", event, base=base)
        assert os.path.exists(path)

    # -- writer=True on a non-sanctioned action grants nothing ----------------
    @pytest.mark.parametrize("action", ["write", "edit", "bash_write", "delete"])
    @pytest.mark.parametrize("target", [
        "state/registry/delegations.json",
        "audit/events.jsonl",
    ])
    def test_writer_true_does_not_bypass_protection(self, tmp_path, action, target):
        """writer=True on a generic action NEVER grants protected-path access."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write(action, target, base=base, writer=True)

    def test_write_through_writer_true_no_bypass(self, tmp_path):
        """write_through(..., writer=True) with a generic action still DENIES
        protected paths (protected-path bypass is not an authority grant)."""
        from control.execution_gate import write_through
        base = _mkbase(tmp_path)
        target = os.path.join(base, "state", "registry", "no-bypass.json")
        with pytest.raises(Denied):
            write_through("write", target, {"v": 1}, base=base, writer=True)
        assert not os.path.exists(target)

    def test_writer_true_specialist_path_still_allowed(self, tmp_path):
        """writer=True on a generic action for an ordinary workspace path keeps
        the normal write capability (CTO/Zeko writes preserved)."""
        base = _mkbase(tmp_path)
        assert authorize_write("write", "agents/cto/policy.yaml", base=base,
                               writer=True) is True

    def test_registry_write_to_own_root_without_writer_denied(self, tmp_path):
        """Without writer=True the sanctioned action cannot write protected
        paths either (writer flag is required, not the action name)."""
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("registry_write", "state/registry/x.json", base=base,
                            writer=False)


class TestAllowedPaths:
    """ALLOW: authorized workspace paths (CTO/Zeko write capability preserved)."""

    @pytest.mark.parametrize("target", [
        "agents/cto/policy.yaml",
        "agents/cto/new/file.txt",
        "docs/README.md",
        "config/agents.yaml",
        "state/other/delegation-draft.json",   # state/ but NOT state/registry/
        "schemas/audit-event.schema.json",
        "orchestrator/contract.md",
    ])
    def test_allowed_project_path(self, tmp_path, target):
        base = _mkbase(tmp_path)
        assert authorize_write("write", target, base=base) is True

    def test_absolute_allowed_path(self, tmp_path):
        base = _mkbase(tmp_path)
        abs_target = os.path.join(base, "agents", "cto", "policy.yaml")
        assert authorize_write("write", abs_target, base=base) is True

    def test_write_through_writes_allowed_path(self, tmp_path):
        from control.execution_gate import write_through
        base = _mkbase(tmp_path)
        target = os.path.join(base, "agents", "cto", "output.txt")
        written = write_through("write", target, {"ok": 1}, base=base)
        assert os.path.exists(target)
        assert written == target

    def test_read_of_protected_path_allowed(self, tmp_path):
        """Reads are not writes — the gate governs writes only."""
        base = _mkbase(tmp_path)
        assert authorize_write("read", "state/registry/delegations.json", base=base) is True


class TestMalformed:
    """DENY: malformed/unresolvable targets (fail-closed)."""

    @pytest.mark.parametrize("target", [None, "", "   ", 42, ["state/registry"], "\x00"])
    def test_malformed_target_denied(self, tmp_path, target):
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("write", target, base=base)

    def test_malformed_classifies(self, tmp_path):
        base = _mkbase(tmp_path)
        assert classify_target(None, base=base) == "MALFORMED"
        assert classify_target("", base=base) == "MALFORMED"


class TestTraversal:
    """DENY: traversal / scope bypass escaping the authorized boundary."""

    @pytest.mark.parametrize("target", [
        "../escape.txt",
        "state/registry/../../../../escape.txt",
        "agents/cto/../../../../escape.txt",
        "agents/../agents/../../etc/passwd",
        "/etc/passwd",                       # absolute outside base
    ])
    def test_traversal_denied(self, tmp_path, target):
        base = _mkbase(tmp_path)
        with pytest.raises(Denied):
            authorize_write("write", target, base=base)

    def test_traversal_via_existing_symlink_denied(self, tmp_path):
        """A symlink inside the workspace pointing outside must be refused."""
        base = _mkbase(tmp_path)
        outside = tmp_path / "outside-secret.txt"
        outside.write_text("secret")
        link = os.path.join(base, "agents", "cto", "link-to-outside.txt")
        os.symlink(str(outside), link)
        with pytest.raises(Denied):
            authorize_write("write", link, base=base)

    def test_deep_traversal_denied(self, tmp_path):
        base = _mkbase(tmp_path)
        target = os.path.join(base, "state", "registry", "..", "..", "..", "..", "tmp", "x")
        with pytest.raises(Denied):
            authorize_write("write", target, base=base)

    def test_normalize_returns_outside_flag(self, tmp_path):
        base = _mkbase(tmp_path)
        real, within = normalize_target("../escape.txt", base=base)
        assert within is False

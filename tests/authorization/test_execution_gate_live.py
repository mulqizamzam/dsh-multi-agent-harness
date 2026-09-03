"""Integration tests — execution gate wired through the project write channel.

These tests exercise the gate end-to-end against a real temporary workspace:
  - registry_write() succeeds for the control plane (single-writer channel)
  - a specialist-style write to a protected path via the gate is DENIED
  - a specialist-style write to an authorized workspace path is ALLOWED
  - traversal / symlink escape is DENIED with no mutation
"""

import json
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from control.execution_gate import (
    Denied,
    audit_append,
    authorize_write,
    classify_target,
    registry_write,
    write_through,
)
from tests.o3.fixtures import o3_daemon_ws  # O3 temp daemon fixture (Phase B)


@pytest.fixture()
def ws(o3_daemon_ws):
    """O3 daemon-backed workspace: registry_write/audit_append route through
    a temp-root O3 daemon. The daemon root == the workspace, so protected
    writes land on wsdir/state/... (same layout as before O3 Phase B)."""
    wsdir, client, daemon = o3_daemon_ws
    return wsdir


class TestRegistryWriteChannel:
    def test_registry_write_succeeds_for_control_plane(self, ws):
        """The sanctioned registry path accepts a control-plane write.
        After O3 Phase B, the daemon stores data with version tracking."""
        path = registry_write("state/registry/delegations.json", {"delegations": []}, base=ws)
        assert os.path.exists(path)
        doc = json.load(open(path))
        # O3 daemon merges the payload with a strict version marker.
        assert doc["delegations"] == []
        assert doc["version"] == 1

    def test_registry_write_writes_under_registry_dir(self, ws):
        path = registry_write("state/registry/revocations.json", {"revoked": []}, base=ws)
        assert os.path.dirname(path).endswith("state/registry")


class TestWriterChannelScopeLive:
    """Session-A hardening, exercised end-to-end through the real channels.

    registry_write() MAY write only state/registry/**
    audit_append()   MAY write only audit/**
    writer=True NEVER bypasses target-path validation; no mutation on DENY.
    """

    def test_registry_write_cross_root_audit_denied_no_mutation(self, ws):
        target = "audit/events.jsonl"
        with pytest.raises(Denied):
            registry_write(target, {"v": 1}, base=ws)
        assert not os.path.exists(os.path.join(ws, "audit", "events.jsonl"))

    def test_registry_write_to_arbitrary_workspace_denied(self, ws):
        for target in ("agents/cto/output.txt", "docs/note.md"):
            with pytest.raises(Denied):
                registry_write(target, {"x": 1}, base=ws)
            assert not os.path.exists(os.path.join(ws, target.replace("/", os.sep)))

    def test_registry_write_deep_registry_descendant_ok(self, ws):
        path = registry_write("state/registry/a/b/delegations.json", {"d": []}, base=ws)
        assert os.path.exists(path)

    def test_audit_append_cross_root_registry_denied_no_mutation(self, ws):
        target = "state/registry/forged.json"
        with pytest.raises(Denied):
            audit_append(target, {"event_id": "e1"}, base=ws)
        assert not os.path.exists(os.path.join(ws, target.replace("/", os.sep)))

    def test_audit_append_to_arbitrary_workspace_denied(self, ws):
        for target in ("agents/cto/output.txt", "docs/note.md"):
            with pytest.raises(Denied):
                audit_append(target, {"event_id": "e1"}, base=ws)
            assert not os.path.exists(os.path.join(ws, target.replace("/", os.sep)))

    def test_audit_append_descendant_ok(self, ws):
        path = audit_append("audit/proj-1/events.jsonl", {"event_id": "e1"}, base=ws)
        assert os.path.exists(path)

    def test_writer_true_generic_action_does_not_bypass(self, ws):
        """writer=True on a generic action grants NO protected-path access."""
        with pytest.raises(Denied):
            write_through("write", "state/registry/no-bypass.json", {"v": 1},
                          base=ws, writer=True)
        assert not os.path.exists(os.path.join(ws, "state", "registry", "no-bypass.json"))
        with pytest.raises(Denied):
            write_through("edit", "audit/events.jsonl", {"v": 1}, base=ws, writer=True)

    def test_writer_true_generic_action_allowed_path_ok(self, ws):
        """The writer flag must not break normal writes to ordinary paths."""
        path = write_through("write", "agents/cto/output.txt", {"ok": 1},
                             base=ws, writer=True)
        assert os.path.exists(path)


class TestSpecialistStyleWriteThroughGate:
    """A CTO/Zeko-style write attempt routed through the project write channel."""

    def test_write_to_registry_denied_no_mutation(self, ws):
        target = "state/registry/iso-live-006-test.txt"
        with pytest.raises(Denied):
            write_through("write", target, {"x": 1}, base=ws)
        assert not os.path.exists(os.path.join(ws, target.replace("/", os.sep)))

    def test_write_to_registry_descendant_denied(self, ws):
        with pytest.raises(Denied):
            write_through("write", "state/registry/deep/sub/x.json", {}, base=ws)

    def test_write_to_audit_denied(self, ws):
        with pytest.raises(Denied):
            write_through("write", "audit/events.jsonl", {}, base=ws)

    def test_write_to_authorized_path_allowed(self, ws):
        target = "agents/cto/output.txt"
        path = write_through("write", target, {"ok": True}, base=ws)
        assert os.path.exists(path)

    def test_write_to_authorized_path_using_bash_write_class(self, ws):
        target = "docs/note.md"
        path = write_through("bash_write", target, "hello", base=ws)
        assert os.path.exists(path)

    def test_traversal_denied_no_mutation(self, ws, tmp_path):
        outside = tmp_path / "escape.txt"
        with pytest.raises(Denied):
            write_through("write", "../escape.txt", "x", base=ws)
        assert not outside.exists()

    def test_symlink_escape_denied(self, ws, tmp_path):
        outside = tmp_path / "secret.txt"
        outside.write_text("secret")
        link = os.path.join(ws, "agents", "cto", "escape-link.txt")
        os.symlink(str(outside), link)
        with pytest.raises(Denied):
            write_through("write", link, "x", base=ws)
        assert outside.read_text() == "secret"  # unchanged


class TestGateClassificationSurface:
    def test_classify_matrix(self, ws):
        assert classify_target("state/registry/x.json", base=ws) == "PROTECTED"
        assert classify_target("audit/x.jsonl", base=ws) == "PROTECTED"
        assert classify_target("agents/cto/x.py", base=ws) == "ALLOWED"
        assert classify_target("../x", base=ws) == "OUTSIDE"
        assert classify_target(None, base=ws) == "MALFORMED"

    def test_authorize_write_read_not_governed(self, ws):
        assert authorize_write("read", "state/registry/x.json", base=ws) is True

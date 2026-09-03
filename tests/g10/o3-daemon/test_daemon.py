# DAEMON tests — single-writer & path scoping (O3-DAEMON-001..010)

import json
import os
import pytest

from registry_writer.client import DaemonRpcError, WriterUnavailable


class TestDaemon:
    """O3-DAEMON acceptance tests (FINAL 0004 §2.1)."""

    def test_daemon_001_single_writer(self, o3_daemon, o3_config, o3_secret):
        """O3-DAEMON-001: daemon is sole writer — a write attempt that is not
        an authenticated control-plane IPC write is refused (the daemon never
        accepts a write from an unauthenticated/foreign principal).

        Because the deterministic acceptance suite runs in a same-UID sandbox
        against a temp root, the hard proof that a raw *filesystem* write is
        denied lives in O3-ISO-001..004 (probes against the real daemon root
        at /var/lib/dsh-registry-writer, outside the sandbox).  Here we prove
        the daemon-side gate: an invalid-token write request is refused."""
        from registry_writer.client import RegistryWriterClient, DaemonRpcError
        bad = RegistryWriterClient(o3_config.socket_path,
                                   b"wrong-secret-32-bytes-long!!")
        with pytest.raises(DaemonRpcError) as exc:
            bad.registry_write("bad-key.json", {"bad": "data"}, 0)
        assert exc.value.code == "UNAUTHORIZED", f"got {exc.value.code}"

    def test_daemon_002_registry_write_scoped(self, o3_client):
        """O3-DAEMON-002: registry_write targets only state/registry/**."""
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "audit/x.json", "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "state/projects/x.json", "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

    def test_daemon_003_audit_append_scoped(self, o3_client):
        """O3-DAEMON-003: audit_append targets only audit/**."""
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("audit_append", {
                "target": "state/registry/x.json", "event": {"event_id": "e1"}})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

    def test_daemon_004_project_write_scoped(self, o3_client):
        """O3-DAEMON-004: project_write targets only state/projects/**."""
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("project_write", {
                "target": "audit/x.json", "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

    def test_daemon_005_cross_root_refused(self, o3_client):
        """O3-DAEMON-005: cross-root escape via traversal."""
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "state/registry/../audit/x.json",
                "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

    def test_daemon_006_traversal_prefix_confusion(self, o3_client):
        """O3-DAEMON-006: traversal, symlink, prefix-confusion refused."""
        # Prefix confusion
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "state/registry-evil/x.json",
                "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code == "FORBIDDEN", f"got {exc.value.code}"

        # Traversal
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "state/registry/../../../etc/passwd",
                "data": {"x": 1}, "expected_version": 0})
        assert exc.value.code in ("INVALID_REQUEST", "FORBIDDEN"), f"got {exc.value.code}"

    def test_daemon_007_cas_replay_rejected(self, o3_client):
        """O3-DAEMON-007: duplicate registry_write with same version is stale."""
        r1 = o3_client.registry_write("cas-test", {"name": "v1"}, 0)
        assert r1["version"] == 1

        # Same version again → stale
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.registry_write("cas-test", {"name": "v1-dup"}, 0)
        assert exc.value.code == "INVALID_REQUEST"

    def test_daemon_008_schema_validation(self, o3_client):
        """O3-DAEMON-008: registry_write with non-object data is refused."""
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.call("registry_write", {
                "target": "state/registry/bad.json",
                "data": "not-a-dict", "expected_version": 0})
        assert exc.value.code == "INVALID_REQUEST", f"got {exc.value.code}"

    def test_daemon_009_strict_monotonic(self, o3_client):
        """O3-DAEMON-009: version must be exactly +1 (cannot skip)."""
        o3_client.registry_write("mono-test", {"name": "v1"}, 0)
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.registry_write("mono-test", {"name": "v3"}, 2)
        assert exc.value.code == "INVALID_REQUEST", f"got {exc.value.code}"

    def test_daemon_010_self_audit(self, o3_client):
        """O3-DAEMON-010: every mutation creates an audit event."""
        # Write a registry doc — the daemon self-audits into audit/_daemon
        o3_client.registry_write("audit-self", {"name": "audited"}, 0)
        # Write a project doc
        o3_client.project_write("audit-self-proj", {"name": "proj"}, 0)
        # Read the daemon's self-audit ledger — should contain at least the
        # two mutations (registry_write + project_write)
        ar = o3_client.audit_read("_daemon")
        assert ar.get("count", 0) >= 2, (
            f"expected >=2 self-audit events, got {ar.get('count')}")
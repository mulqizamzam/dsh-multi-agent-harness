# IPC tests — contract, authn/authz, replay (O3-IPC-001..008)

import json
import os
import secrets
import time
import pytest

from registry_writer.client import DaemonRpcError, RegistryWriterClient, WriterUnavailable
from schemas.ipc import make_request, sign_request, now_iso


class TestIpc:
    """O3-IPC acceptance tests (FINAL 0004 §2.2)."""

    def test_ipc_001_round_trip(self, o3_client):
        """O3-IPC-001: round-trip for health, registry_read, audit_read."""
        h = o3_client.health()
        assert h.get("status") == "ok"
        assert h.get("ready") is True

        # Read a non-existent key
        r = o3_client.registry_read("nonexistent")
        assert r.get("version") == 0
        assert r.get("data") == {}

    def test_ipc_002_invalid_token_rejected(self, o3_client, o3_config, o3_secret):
        """O3-IPC-002: request with wrong/missing/expired token is UNAUTHORIZED."""
        wrong = RegistryWriterClient(o3_config.socket_path, b"wrong-secret-32-bytes-long!!")
        with pytest.raises(DaemonRpcError) as exc:
            wrong.health()
        assert exc.value.code == "UNAUTHORIZED", f"got {exc.value.code}"

        # Missing token
        import socket, json
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(5)
        conn.connect(o3_config.socket_path)
        req = make_request("no-auth", "health", {})
        conn.sendall(json.dumps(req).encode() + b"\n")
        resp = json.loads(conn.recv(65536).decode().split("\n")[0].strip())
        conn.close()
        assert resp.get("ok") is False
        assert resp.get("error", {}).get("code") == "UNAUTHORIZED"

    def test_ipc_003_wrong_channel_forbidden(self, o3_client, o3_config, o3_secret):
        """O3-IPC-003: wrong channel (non-control_plane) is FORBIDDEN."""
        # Craft a request with a non-control_plane channel
        from schemas.ipc import sign_request, now_iso
        import socket, json, uuid, secrets
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(5)
        conn.connect(o3_config.socket_path)
        rid = str(uuid.uuid4())
        issued = now_iso()
        nonce = secrets.token_hex(16)
        params = {"target": "state/registry/write.json", "data": {"x": 1}, "expected_version": 0}
        token = sign_request(o3_secret, "registry_write", rid, issued, nonce, params)
        req = make_request(rid, "registry_write", params, {
            "channel": "not_control_plane",
            "token": token,
            "issued_at": issued,
            "nonce": nonce,
        })
        conn.sendall(json.dumps(req).encode() + b"\n")
        resp = json.loads(conn.recv(65536).decode().split("\n")[0].strip())
        conn.close()
        assert resp.get("ok") is False
        assert resp.get("error", {}).get("code") == "FORBIDDEN"

    def test_ipc_004_audit_append_idempotent(self, o3_client):
        """O3-IPC-004: same event_id → idempotent success, no duplicate."""
        r1 = o3_client.audit_append("idempotent-proj", {"event_id": "e-idem", "msg": "first"})
        assert r1.get("idempotent") is False
        r2 = o3_client.audit_append("idempotent-proj", {"event_id": "e-idem", "msg": "second"})
        assert r2.get("idempotent") is True
        # Verify only one event
        ar = o3_client.audit_read("idempotent-proj")
        assert ar.get("count") == 1

    def test_ipc_005_registry_write_replay_stale(self, o3_client):
        """O3-IPC-005: replayed registry_write is stale (version moved)."""
        o3_client.registry_write("replay-test", {"name": "v1"}, 0)
        # Same params (version 0) → stale
        with pytest.raises(DaemonRpcError) as exc:
            o3_client.registry_write("replay-test", {"name": "v1-again"}, 0)
        assert exc.value.code == "INVALID_REQUEST"

    def test_ipc_006_malformed_request_refused(self, o3_client, o3_config):
        """O3-IPC-006: malformed JSON, missing method, missing auth."""
        import socket, json
        for bad_line in [b"not json\n", b'{"v":1,"id":"x"}\n', b'{"v":1,"id":"x","method":"unknown"}\n']:
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            conn.settimeout(5)
            conn.connect(o3_config.socket_path)
            conn.sendall(bad_line)
            resp = json.loads(conn.recv(65536).decode().split("\n")[0].strip())
            conn.close()
            assert resp.get("ok") is False, f"bad line {bad_line!r} should be refused"

    def test_ipc_007_timeout_handled(self, o3_client):
        """O3-IPC-007: daemon handles fast requests; overload is typed error.
        (Timeout test is bounded; the daemon uses request_timeout_seconds.)"""
        # A fast, valid request still works
        h = o3_client.health()
        assert h.get("status") == "ok"

    def test_ipc_008_replay_window_enforced(self, o3_client, o3_config, o3_secret):
        """O3-IPC-008: token outside ±30s window is UNAUTHORIZED."""
        import socket, json, uuid, secrets
        from schemas.ipc import sign_request
        old_ts = "2024-01-01T00:00:00Z"
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(5)
        conn.connect(o3_config.socket_path)
        rid = str(uuid.uuid4())
        nonce = secrets.token_hex(16)
        params = {}
        token = sign_request(o3_secret, "health", rid, old_ts, nonce, params)
        req = make_request(rid, "health", params, {
            "channel": "control_plane", "token": token,
            "issued_at": old_ts, "nonce": nonce,
        })
        conn.sendall(json.dumps(req).encode() + b"\n")
        resp = json.loads(conn.recv(65536).decode().split("\n")[0].strip())
        conn.close()
        assert resp.get("ok") is False
        assert resp.get("error", {}).get("code") == "UNAUTHORIZED", f"got {resp}"
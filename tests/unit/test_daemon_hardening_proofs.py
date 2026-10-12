# tests/unit/test_daemon_hardening_proofs.py
#
# Regression proofs for the daemon-hardening fixes (post-readiness-race
# sweep).  Each test names the defect it would otherwise let through:
#
#   1. backup label traversal (label joined raw into the backup dir)
#   2. restore from an out-of-backup-dir path (arbitrary manifest read)
#   3. restore destroying live state before the copy succeeded
#   4. a transient self-audit failure latching RECOVERY_REQUIRED forever
#   5. unbounded request buffer (declared max_payload_bytes never enforced)
#   6. one accept() OSError retiring a "ready" daemon permanently
#   7. arbitrary nonce eviction allowing a replay inside the window
#   9. concurrent read-modify-write lost updates (unserialized CAS)
#  10. audit_read since_seq semantics
#  13. mid-request connection breakage escaping as a raw OSError
#
# These are deliberately black-box: they go through the authenticated IPC
# client exactly like the control plane does.

import json
import os
import socket
import threading
import time

import pytest

from registry_writer.client import DaemonRpcError, RegistryWriterClient
from registry_writer.provider import reset_client
from tests.conftest import start_o3_daemon, stop_o3_daemon


@pytest.fixture()
def daemon_and_client(tmp_path):
    wsdir, client, daemon = start_o3_daemon(tmp_path / "ws")
    yield wsdir, client, daemon
    stop_o3_daemon(daemon)


class TestBackupLabelTraversal:
    """Defect 1: the caller-supplied label was joined raw into the backup dir."""

    def test_traversal_label_is_refused(self, daemon_and_client):
        _ws, client, daemon = daemon_and_client
        outside = os.path.dirname(os.path.abspath(daemon.config.root))
        for label in (f"../../{os.path.basename(outside)}-pwned",
                      "/tmp/abs-label", "..", ".", "a/b"):
            with pytest.raises(DaemonRpcError) as exc:
                client.backup(label=label)
            assert exc.value.code == "INVALID_REQUEST", (
                f"label {label!r} must be refused, got {exc.value.code}")

    def test_plain_label_still_works(self, daemon_and_client):
        _ws, client, _daemon = daemon_and_client
        b = client.backup(label="ok-label-001")
        assert os.path.isdir(b["backup_path"])
        assert os.path.commonpath([os.path.realpath(b["backup_path"]),
                                   os.path.realpath(_daemon.config.backup_dir)]
                                  ) == os.path.realpath(_daemon.config.backup_dir)
        # nothing was created outside the backup dir
        parent = os.path.dirname(os.path.abspath(_daemon.config.backup_dir))
        for name in ("pwned", "abs-label"):
            assert not os.path.exists(os.path.join(parent, name))


class TestRestorePathGuard:
    """Defect 2: restore accepted any host path as the backup dir."""

    def test_outside_backup_dir_refused(self, daemon_and_client, tmp_path):
        _ws, client, daemon = daemon_and_client
        outside = tmp_path / "not-a-backup"
        outside.mkdir()
        (outside / "MANIFEST.sha256").write_text(json.dumps(
            {"state/registry/x.json": "0" * 64}))
        with pytest.raises(DaemonRpcError) as exc:
            client.restore(str(outside), confirmed=True)
        assert exc.value.code == "FORBIDDEN", (
            f"restore from {outside} must be refused, got {exc.value.code}")
        assert exc.value.code != "CORRUPTION_DETECTED"

    def test_missing_backup_still_typed(self, daemon_and_client):
        _ws, client, daemon = daemon_and_client
        with pytest.raises(DaemonRpcError) as exc:
            client.restore(daemon.config.backup_dir, confirmed=True)
        # backup_dir itself is inside the guard, so this is the (expected)
        # "no manifest" path rather than an escape.
        assert exc.value.code == "INVALID_REQUEST"


class TestRestoreDoesNotDestroyLiveState:
    """Defect 3: rmtree(live) ran BEFORE copytree — a failed copy left the
    daemon with an empty registry and no way back."""

    def test_failed_copy_leaves_state_intact(self, daemon_and_client,
                                            tmp_path, monkeypatch):
        ws, client, daemon = daemon_and_client
        client.registry_write("keep-alive", {"name": "live"}, 0)
        before = client.registry_read("keep-alive")
        assert before["data"]["name"] == "live"

        b = client.backup(label="before-bad-restore")

        # Make the copy phase fail deterministically.
        import shutil as _shutil
        real_copytree = _shutil.copytree

        def failing_copytree(src, dst, *a, **kw):
            # The staging destination is <root>/.restore-staging-*/<rel>, so
            # match on the path component, not the basename.
            if ".restore-staging" in str(dst):
                raise OSError("simulated copy failure (disk full)")
            return real_copytree(src, dst, *a, **kw)

        monkeypatch.setattr("registry_writer.daemon.shutil.copytree",
                            failing_copytree)
        with pytest.raises(DaemonRpcError) as exc:
            client.restore(b["backup_path"], confirmed=True)

        monkeypatch.undo()
        after = client.registry_read("keep-alive")
        assert after["data"]["name"] == "live", (
            "live state was destroyed by a failed restore")
        assert not [d for d in os.listdir(ws)
                    if d.startswith(".restore-staging")], \
            "staging dir left behind"


class TestSelfAuditFlagDoesNotLatch:
    """Defect 4: one transient self-audit failure rejected every later write
    with RECOVERY_REQUIRED until process restart."""

    def test_flag_cleared_after_success(self, daemon_and_client, monkeypatch):
        _ws, client, daemon = daemon_and_client

        # Inject the transient failure at the AUDIT-APPEND layer — i.e. inside
        # the real _self_audit, which is designed to absorb it and flag the
        # root. Fail the first two self-audit attempts, succeed from the third.
        import registry_writer.daemon as dmod
        real_append = dmod._audit_append
        calls = {"n": 0}

        def flaky_append(guard, target, event, max_doc_bytes, lock=None):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise OSError("ENOSPC (transient)")
            return real_append(guard, target, event, max_doc_bytes, lock)

        monkeypatch.setattr(dmod, "_audit_append", flaky_append)

        # Write 1: lands; its self-audit (call 1) fails → flag set.
        client.registry_write("w1", {"v": 1}, 0)
        assert "audit/_daemon" in daemon._recovery_roots

        # Write 2: the gate re-probes (call 2) — still failing → REFUSED.
        # (Pre-fix this write — and every later one — was refused forever.)
        with pytest.raises(DaemonRpcError) as exc:
            client.registry_write("w2", {"v": 2}, 0)
        assert exc.value.code == "RECOVERY_REQUIRED", (
            f"expected the failing probe to refuse, got {exc.value.code}")

        # Write 3: the gate re-probes (call 3) — healthy → flag cleared → the
        # write PROCEEDS. A transient failure must not latch forever.
        client.registry_write("w3", {"v": 3}, 0)
        assert daemon._recovery_roots == set(), (
            f"self-audit flag latched after a successful probe: "
            f"{daemon._recovery_roots}")
        # …and writes keep working with no further probe failures.
        client.registry_write("w4", {"v": 4}, 0)


class TestMaxPayloadBytes:
    """Defect 5: declared max_payload_bytes had no reader; a client that never
    sent a newline grew the buffer until the 30s timeout."""

    def test_oversized_request_is_rejected_fast(self, daemon_and_client):
        ws, client, daemon = daemon_and_client
        # The bound is read from the config at request time, so a small
        # per-daemon limit is a faithful (and fast) stand-in for the 32 MiB
        # default the production config carries.
        daemon.config.max_payload_bytes = 4096
        limit = daemon.config.max_payload_bytes
        assert limit < 32 * 1024 * 1024, "test needs a small limit"
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.settimeout(5.0)
        started = time.monotonic()
        try:
            conn.connect(os.path.join(ws, "ipc.sock"))
            conn.sendall(b"x" * (limit + 4096))  # no newline
            chunks = b""
            while b"\n" not in chunks:
                part = conn.recv(65536)
                if not part:
                    break
                chunks += part
        finally:
            conn.close()
        elapsed = time.monotonic() - started
        assert b"\n" in chunks, f"no response from the daemon: {chunks[:120]!r}"
        assert json.loads(chunks.split(b"\n", 1)[0])["error"]["code"] \
            == "INVALID_REQUEST"
        assert elapsed < 5.0, "daemon waited for the request timeout"

    def test_normal_request_still_works(self, daemon_and_client):
        _ws, client, _daemon = daemon_and_client
        assert client.health()["status"] == "ok"


class TestAcceptLoopSurvivesTransientErrors:
    """Defect 6: ANY accept() OSError broke the loop while _ready stayed True,
    so health answered ok and the daemon accepted nothing forever."""

    def test_transient_accept_error_does_not_retire_daemon(self, tmp_path):
        wsdir, client, daemon = start_o3_daemon(tmp_path / "ws")
        try:
            real_server = daemon._server
            state = {"raised": False}

            class FlakyServer:
                """Proxy injecting ONE transient accept() OSError, then
                delegating to the real listening socket. (socket.accept is a
                read-only attribute, so the SERVER OBJECT is swapped, not the
                method.)"""

                def accept(self):
                    if not state["raised"]:
                        state["raised"] = True
                        raise OSError(24, "EMFILE (simulated)")
                    return real_server.accept()

                def close(self):
                    return real_server.close()

            daemon._server = FlakyServer()
            # Health #1 is served by the in-flight accept on the real socket;
            # by the next loop iteration the proxy raises once, the fixed loop
            # sleeps and continues, and health #2 is served by the delegate.
            assert client.health()["status"] == "ok"
            time.sleep(0.05)
            assert client.health()["status"] == "ok", (
                "daemon stopped accepting after a transient accept() error")
            assert state["raised"], "the injected accept() error never fired"
            assert daemon._running is True
            assert daemon._ready_event.is_set()
        finally:
            stop_o3_daemon(daemon)


class TestNonceEvictionIsFifo:
    """Defect 7: `set(list(...)[-50_000:])` evicted ARBITRARY entries, so a
    live nonce could be dropped and replayed inside the ±30s window."""

    def test_oldest_are_evicted_not_arbitrary(self, tmp_path):
        wsdir, client, daemon = start_o3_daemon(tmp_path / "ws")
        try:
            # Seed past the configured bound (100_000) and run the REAL
            # admission-path eviction (`_bound_nonces`). The LAST inserted
            # nonce is the most-recently-presented one and must survive.
            recent = ("control_plane", "nonce-recent-last")
            oldest = ("control_plane", "nonce-0")
            with daemon._nonce_lock:
                daemon._seen_nonces.clear()
                for i in range(100_000):
                    daemon._seen_nonces[("control_plane", f"nonce-{i}")] = None
                daemon._seen_nonces[recent] = None
                daemon._bound_nonces()
                keys = list(daemon._seen_nonces)
            assert recent in keys, (
                "the most-recently-presented nonce was evicted — "
                "it can now be replayed inside the ±30s window")
            assert oldest not in keys, (
                "the OLDEST nonce survived eviction — FIFO order is broken")
        finally:
            stop_o3_daemon(daemon)


class TestConcurrentCasLostUpdate:
    """Defect 9: read-modify-write with no mutual exclusion — two concurrent
    registry_writes with the same expected_version both committed N+1."""

    def test_concurrent_writes_are_serialized(self, daemon_and_client):
        _ws, client, _daemon = daemon_and_client
        client.registry_write("cas", {"n": 0}, 0)
        results = []
        errors = []

        def writer(i):
            c = RegistryWriterClient(_daemon.config.socket_path,
                                     open(_daemon.config.hmac_secret_path,
                                          "rb").read())
            try:
                results.append(c.registry_write(
                    "cas", {"n": i + 1}, 1)["version"])
            except DaemonRpcError as e:
                errors.append(e.code)

        threads = [threading.Thread(target=writer, args=(i,))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one write may commit at expected_version=1; the rest must be
        # told the CAS is stale (they lost the race by design).
        assert results == [2], (
            f"LOST UPDATE: {len(results)} writes committed version 2 "
            f"concurrently; errors={errors}")
        assert len(errors) == 7
        assert errors == ["INVALID_REQUEST"] * 7
        final = client.registry_read("cas")
        assert final["version"] == 2, (
            f"live doc is at version {final['version']}, expected 2")


class TestAuditReadSinceSeqContract:
    """Defect 10: the since_seq convention was undocumented and untested.

    Contract (documented in daemon._m_audit_read): 0-based, end-exclusive —
    since_seq=N skips the first N events.
    """

    def test_since_seq_is_zero_based_end_exclusive(self, daemon_and_client):
        _ws, client, _daemon = daemon_and_client
        for i in range(5):
            client.audit_append("proj", {"event_id": f"e{i}", "i": i})

        all_events = client.audit_read("proj")["events"]
        assert len(all_events) == 5
        assert [e["i"] for e in all_events] == [0, 1, 2, 3, 4]

        # since_seq=0 and absent → the whole ledger.
        assert client.audit_read("proj", since_seq=0)["count"] == 5

        # since_seq=N returns events[N:] — skips the first N.
        tail = client.audit_read("proj", since_seq=2)["events"]
        assert [e["i"] for e in tail] == [2, 3, 4]

        # "everything after seq 2" == since_seq=3.
        after = client.audit_read("proj", since_seq=3)["events"]
        assert [e["i"] for e in after] == [3, 4]

        # Out-of-range is an empty ledger, not an error.
        assert client.audit_read("proj", since_seq=99)["count"] == 0

        # Booleans are not ints (isinstance(True, int) is True in Python).
        with pytest.raises(DaemonRpcError) as exc:
            client.audit_read("proj", since_seq=True)
        assert exc.value.code == "INVALID_REQUEST"

        with pytest.raises(DaemonRpcError) as exc:
            client.call("audit_read", {"target": "audit/proj/events.jsonl",
                                       "since_seq": -1})
        assert exc.value.code == "INVALID_REQUEST"


class TestMidRequestConnectionBreak:
    """Defect 13: a mid-request ConnectionResetError escaped as a raw OSError,
    breaking the fail-closed WriterUnavailable contract."""

    def test_reset_raises_writer_unavailable(self, daemon_and_client):
        from registry_writer.client import WriterUnavailable
        ws, _client, daemon = daemon_and_client
        secret = open(daemon.config.hmac_secret_path, "rb").read()
        c = RegistryWriterClient(os.path.join(ws, "ipc.sock"), secret)

        import unittest.mock as mock
        real_socket = socket.socket

        class ResetSocket(real_socket):  # type: ignore[misc, valid-type]
            def sendall(self, data, *a, **kw):  # noqa: D102
                raise ConnectionResetError(104, "Connection reset by peer")

        with mock.patch("registry_writer.client.socket.socket", ResetSocket):
            with pytest.raises(WriterUnavailable) as exc:
                c.health()
        assert "daemon connection failed" in str(exc.value)


def test_full_smoke(daemon_and_client):
    """The daemon still answers the full method surface end to end."""
    ws, client, daemon = daemon_and_client
    assert client.health()["status"] == "ok"
    client.registry_write("smoke", {"a": 1}, 0)
    assert client.registry_read("smoke")["version"] == 1
    client.audit_append("proj", {"event_id": "s1"})
    assert client.audit_read("proj")["count"] == 1
    b = client.backup(label="smoke-001")
    client.registry_write("smoke", {"a": 2}, 1)
    client.restore(b["backup_path"], confirmed=True)
    assert client.registry_read("smoke")["data"]["a"] == 1
    assert client.audit_verify("proj")["ok"] is True
    reset_client()

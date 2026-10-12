# tests/unit/test_daemon_startup_readiness.py
#
# PROOF: the O3 daemon fixture used to wait for readiness by polling
# os.path.exists(<ipc.sock>.  That signal is WRONG: the socket FILE is created
# by bind() (registry_writer/daemon.py start()), but the kernel only starts
# queueing connections after listen().  Under CPU/scheduler load the window
# widens, the fixture returns early, and the first client connect gets
# ECONNREFUSED — the sporadic full-suite signature
#   WriterUnavailable: daemon unreachable at .../ipc.sock:
#                       [Errno 111] Connection refused
#
# The fix makes the daemon publish a deterministic readiness event
# (set immediately after listen() succeeds) and makes every fixture wait on
# that event instead of the file.  These tests discriminate: run them against
# the pre-fix fixtures (polling os.path.exists) and Test A fails with
# ConnectionRefused; run them against the fixed fixtures and they pass.

import os
import socket
import time

import pytest

from registry_writer.provider import get_client, reset_client
from tests.conftest import start_o3_daemon, stop_o3_daemon


def _health_ok(result: dict) -> bool:
    return result.get("status") == "ok"


class TestDaemonStartupReadiness:
    """Deterministic proof that a started daemon is actually ACCEPTING."""

    def test_a_slow_chmod_between_bind_and_listen_still_connects(
            self, tmp_path, monkeypatch):
        """Core proof: the bind→listen window is widened to 0.4s.

        daemon.start() calls os.chmod(socket_path, ...) between bind() and
        listen().  A slow chmod (the load proxy) used to make the existence
        poll return while the daemon could not yet accept — the following
        connect raised WriterUnavailable / ConnectionRefused.
        """
        real_chmod = os.chmod
        calls = {"n": 0}

        def slow_socket_chmod(path, mode):
            if str(path).endswith("ipc.sock"):
                # Exactly the call daemon.start() makes between bind() and
                # listen().  monkeypatch restores os.chmod automatically.
                calls["n"] += 1
                time.sleep(0.4)
            return real_chmod(path, mode)

        monkeypatch.setattr(os, "chmod", slow_socket_chmod)

        wsdir, client, daemon = start_o3_daemon(tmp_path / "ws-a")
        try:
            # The REAL symptom is checked first: the very first client
            # round-trip. Pre-fix this is
            #   WriterUnavailable: daemon unreachable at .../ipc.sock:
            #     [Errno 111] Connection refused
            via_client = client.health()
            assert _health_ok(via_client), via_client
            via_provider = get_client().call("health", {})
            assert _health_ok(via_provider), via_provider
            # Injection sanity check: the bind→listen chmod really was slowed,
            # so the failure above (when it happens) is the real race.
            assert calls["n"] >= 1, "socket chmod was never exercised"
        finally:
            stop_o3_daemon(daemon)

    def test_b_socket_accepts_immediately_after_start(self, tmp_path):
        """The listening socket accepts the instant the helper returns.

        Repeated to catch residual flakiness: every iteration does a raw
        socket connect + a provider health round-trip with no sleep.
        """
        for i in range(25):
            root = tmp_path / f"ws-b-{i}"
            wsdir, client, daemon = start_o3_daemon(root)
            try:
                # 1) raw connect: proves the kernel queues the connection
                raw = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    raw.settimeout(2.0)
                    raw.connect(os.path.join(wsdir, "ipc.sock"))
                finally:
                    raw.close()
                # 2) full authenticated round-trip through the provider
                result = get_client().call("health", {})
                assert _health_ok(result), f"iteration {i}: {result}"
                assert client.health().get("status") == "ok"
            finally:
                stop_o3_daemon(daemon)
                reset_client()

    def test_c_dead_startup_thread_surfaces_real_error(self, tmp_path):
        """A daemon whose startup thread dies must raise the real error.

        Deterministic injection: the socket path is pre-created as a DIRECTORY,
        so the `os.unlink(socket_path)` that start() performs right before
        bind() raises IsADirectoryError.  (The alternative suggested in the
        spec — pointing hmac_secret_path at a missing file — cannot be used:
        RegistryWriterDaemon._load_secret() runs in __init__, so that would
        raise at construction, not from the startup thread.)

        Pre-fix behaviour: 5s wait, then "O3 daemon did not start ... in 5s"
        with no indication of the real cause.  Post-fix: the captured
        exception is re-raised.
        """
        root = tmp_path / "ws-c"
        root.mkdir(parents=True, exist_ok=True)
        os.mkdir(os.path.join(str(root), "ipc.sock"))  # bind() will fail

        started = time.monotonic()
        with pytest.raises(IsADirectoryError) as exc:
            start_o3_daemon(root)
        elapsed = time.monotonic() - started

        assert "Is a directory" in str(exc.value), (
            f"the real startup error must be surfaced, got {exc.value!r}")
        # Evidence that it fails fast instead of burning the 5s deadline.
        assert elapsed < 4.0, f"took {elapsed:.2f}s — looks like a timeout"
        # No daemon/socket is left behind for the next test to collide with.
        assert os.path.isdir(os.path.join(str(root), "ipc.sock"))

    def test_d_pid_write_failure_does_not_kill_the_accept_loop(self, tmp_path):
        """The pid-file write must not be able to stop the daemon.

        Deterministic injection: pre-create a DIRECTORY at <root>/daemon.pid,
        so the `open(pid_path, "w")` in start() raises IsADirectoryError.
        The pid file is observability only: the daemon must still set the
        readiness event, write nothing partial, and serve requests.
        """
        root = tmp_path / "ws-d"
        root.mkdir(parents=True, exist_ok=True)
        os.mkdir(os.path.join(str(root), "daemon.pid"))  # pid write fails

        wsdir, client, daemon = start_o3_daemon(root)
        try:
            assert daemon._ready_event.is_set()
            assert client.health().get("status") == "ok"
            assert get_client().call("health", {}).get("status") == "ok"
        finally:
            stop_o3_daemon(daemon)

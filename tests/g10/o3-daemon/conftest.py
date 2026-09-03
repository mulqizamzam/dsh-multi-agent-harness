# tests/g10/o3-daemon/conftest.py — shared fixtures for O3 acceptance tests
#
# The acceptance suite runs against a THROWAWAY temp root with a locally
# spawned daemon process (FINAL 0004 §3.2). No real state/registry/,
# audit/, or state/projects/ is touched.
#
# O3-ISO isolation probes use the REAL daemon root at /var/lib/dsh-registry-writer
# when available (session sandbox denial evidence), otherwise skip with reason.

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from registry_writer.daemon import DaemonConfig, RegistryWriterDaemon  # noqa: E402
from registry_writer.client import RegistryWriterClient  # noqa: E402

# Real daemon root (for isolation probes). Must be outside workspace.
REAL_DAEMON_ROOT = "/var/lib/dsh-registry-writer"


def _sandbox_active() -> bool:
    """Detect if the test process runs inside the DSH file sandbox."""
    parent = os.path.dirname(_PROJECT_ROOT)
    probe = os.path.join(parent, ".o3-sandbox-probe")
    try:
        os.mkdir(probe)
    except OSError:
        return True
    else:
        os.rmdir(probe)
        return False


def _real_root_provisioned() -> bool:
    """True if the real daemon root exists (from operator provisioning)."""
    return os.path.exists(REAL_DAEMON_ROOT)


@pytest.fixture(scope="session")
def o3_secret() -> bytes:
    """A random 32-byte HMAC secret for the test session."""
    return os.urandom(32)


@pytest.fixture(scope="session")
def o3_tmp_root() -> str:
    """Throwaway daemon root for the test session."""
    tmp = tempfile.mkdtemp()
    yield tmp
    # cleanup: subprocess to avoid permission issues
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def o3_config(o3_tmp_root: str, o3_secret: bytes) -> DaemonConfig:
    """Daemon config pointing at the temp root."""
    secret_path = os.path.join(o3_tmp_root, "hmac-secret")
    with open(secret_path, "wb") as f:
        f.write(o3_secret)
    return DaemonConfig(
        root=o3_tmp_root,
        socket_path=os.path.join(o3_tmp_root, "ipc.sock"),
        hmac_secret_path=secret_path,
        socket_group="nogroup",  # group may not exist in sandbox
        socket_mode=0o660,
        max_doc_bytes=16 * 1024 * 1024,
    )


@pytest.fixture(scope="session")
def o3_daemon(o3_config: DaemonConfig, o3_secret: bytes):
    """Start the daemon in a background thread for the session."""
    daemon = RegistryWriterDaemon(o3_config)
    t = threading.Thread(target=daemon.start, daemon=True)
    t.start()
    # Wait for the socket to be bound (up to 5s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if os.path.exists(o3_config.socket_path):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(f"daemon socket not ready at {o3_config.socket_path}")
    yield daemon
    daemon.shutdown()


@pytest.fixture(scope="session")
def o3_client(o3_daemon, o3_config: DaemonConfig,
              o3_secret: bytes) -> RegistryWriterClient:
    """Client connected to the test daemon (depends on daemon being started)."""
    return RegistryWriterClient(o3_config.socket_path, o3_secret)


@pytest.fixture
def registry_write(o3_client: RegistryWriterClient):
    """Convenience: write a registry doc with version=0."""
    def _write(key: str, data: dict, expected: int = 0):
        return o3_client.registry_write(key, data, expected)
    return _write


@pytest.fixture
def audit_append(o3_client: RegistryWriterClient):
    def _append(project: str, event: dict):
        return o3_client.audit_append(project, event)
    return _append
# tests/o3/fixtures.py — Shared O3 daemon test fixtures (Phase B/C)
#
# Provides a per-test function-scoped daemon fixture that starts a temp-root
# O3 daemon on the test workspace, sets env vars so the control-plane client
# provider resolves to it, and provides a client for seeding/verification.
#
# Imports as: from tests.o3.fixtures import o3_daemon_ws
#
# Usage in conftest:
#   @pytest.fixture()
#   def ws(o3_daemon_ws):
#       return o3_daemon_ws  # the daemon root IS the workspace
#
# Or directly:
#   def test_something(o3_daemon_ws):
#       wsdir, client, daemon = o3_daemon_ws
#       client.project_write("multi-agent-harness", {...}, 0)
#       store = RuntimeStore(base=wsdir)  # routes through daemon

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from registry_writer.daemon import DaemonConfig, RegistryWriterDaemon  # noqa: E402
from registry_writer.client import RegistryWriterClient  # noqa: E402
from registry_writer.provider import reset_client  # noqa: E402


@pytest.fixture()
def o3_daemon_ws(tmp_path, request):
    """A per-test workspace that IS the O3 daemon root.

    Creates the workspace with standard dirs, starts a daemon on it, sets env
    vars for the client provider, and yields (wsdir, client, daemon).

    The daemon root == wsdir so protected paths resolve to wsdir/state/...
    (same layout as before migration). Tests that seed protected state via
    direct filesystem writes to wsdir/state/... will be visible to the daemon.
    Tests that use RuntimeStore(base=wsdir) etc. route through the daemon.
    """
    wsdir = str(tmp_path / "workspace")
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "agents/cfo", "agents/kai", "docs"):
        os.makedirs(os.path.join(wsdir, sub), exist_ok=True)

    # Create a fresh HMAC secret for this test's daemon
    secret = os.urandom(32)
    secret_path = os.path.join(wsdir, ".o3-hmac-secret")
    with open(secret_path, "wb") as f:
        f.write(secret)

    socket_path = os.path.join(wsdir, "ipc.sock")
    config = DaemonConfig(
        root=wsdir,
        socket_path=socket_path,
        hmac_secret_path=secret_path,
        socket_group="nogroup",
        socket_mode=0o660,
        max_doc_bytes=16 * 1024 * 1024,
    )

    daemon = RegistryWriterDaemon(config)
    t = threading.Thread(target=daemon.start, daemon=True)
    t.start()

    # Wait for the daemon socket to be ready
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            break
        time.sleep(0.01)
    else:
        daemon.shutdown()
        raise RuntimeError(
            f"O3 daemon did not start at {socket_path} in 5s")

    # Set env vars for the control-plane provider
    os.environ["DSH_REGISTRY_WRITER_SOCKET"] = socket_path
    os.environ["DSH_REGISTRY_WRITER_SECRET"] = secret_path
    reset_client()

    client = RegistryWriterClient(socket_path, secret)

    yield wsdir, client, daemon

    # Teardown
    daemon.shutdown()
    os.environ.pop("DSH_REGISTRY_WRITER_SOCKET", None)
    os.environ.pop("DSH_REGISTRY_WRITER_SECRET", None)
    reset_client()


@pytest.fixture()
def o3_daemon_ws_and_client(o3_daemon_ws):
    """Convenience alias returning (ws, client)."""
    wsdir, client, daemon = o3_daemon_ws
    return wsdir, client


def seed_project_state(wsdir: str, client=None, project: str = "multi-agent-harness",
                       state="DRAFT") -> None:
    """Seed an initial project-state document at version 1 through the O3
    daemon (sanctioned project_write channel; daemon root == wsdir).

    Replaces the V1 `write_through("write", state_rel, ...)` seeding used by
    test fixtures — after O3 Phase B, `state/projects/**` is protected and
    routed through the daemon client (no direct-fs write)."""
    from orchestrator.foundation.state import ProjectState
    from orchestrator.runtime.store import encode_project_state
    if client is None:
        # Default to the daemon client for this workspace
        from registry_writer.provider import get_client
        client = get_client()
    ps = ProjectState(project=project)
    ps.current_state = state
    client.project_write(project, encode_project_state(ps), 0)


def seed_registry(wsdir: str, client=None,
                  delegations: dict | None = None,
                  revocations: tuple = ()) -> None:
    """Seed the delegation registry through the O3 daemon (sanctioned
    registry_write channel). Replaces direct-fs seeding of delegations.json /
    revocations.json in test fixtures."""
    if client is None:
        from registry_writer.provider import get_client
        client = get_client()
    delegations = delegations if delegations is not None else {"delegations": []}
    client.registry_write("delegations", delegations, 0)
    client.registry_write("revocations", {"revoked": list(revocations)}, 0)
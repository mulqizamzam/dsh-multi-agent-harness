"""Shared fixtures for the test suite."""

import os
import sys
import threading
import time
import pytest

# Project root is the multi-agent-harness directory (parent of tests/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Make tests/ importable as a plain package (validate_config, control_plane)
# PROJECT_ROOT must stay strictly AHEAD of tests/: orchestrator/ is a PEP-420
# namespace package, so whichever sys.path entry comes first wins submodule
# resolution. tests/orchestrator/ must never shadow the production package
# (flow.py's deferred `from orchestrator.execution import ExecutionRequest`
# resolves through the namespace path at execute time).
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
if _TESTS_DIR in sys.path:
    sys.path.remove(_TESTS_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(1, _TESTS_DIR)


@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def config_path(project_root):
    return os.path.join(project_root, "config")


@pytest.fixture(scope="session")
def state_helpers_path(project_root):
    return os.path.join(project_root, "state", "helpers")


@pytest.fixture(scope="session")
def audit_helpers_path(project_root):
    return os.path.join(project_root, "audit", "helpers")


@pytest.fixture(scope="session")
def schemas_dir(project_root):
    return os.path.join(project_root, "schemas")


@pytest.fixture(scope="session")
def agents_dir(project_root):
    return os.path.join(project_root, "agents")


@pytest.fixture(scope="function")
def tmp_wd(tmp_path):
    """A temporary workspace directory for state/audit I/O tests."""
    wd = tmp_path / "workspace"
    wd.mkdir(parents=True, exist_ok=True)
    return wd


# ---------------------------------------------------------------------------
# O3 daemon fixture (O3 Phase B/C)
# ---------------------------------------------------------------------------
# After the O3 write-path migration, protected-root I/O
# (state/registry/**, audit/**, state/projects/**) routes through the O3
# daemon client. Tests that touch protected state use the `o3_daemon_ws`
# fixture: it starts a per-test daemon rooted at the test workspace and points
# the client provider at it, so the file layout is unchanged and the control
# plane routes through the daemon (fail-closed, no direct-fs fallback).

from registry_writer.daemon import DaemonConfig, RegistryWriterDaemon  # noqa: E402
from registry_writer.client import RegistryWriterClient  # noqa: E402
from registry_writer.provider import reset_client  # noqa: E402


@pytest.fixture(autouse=True)
def o3_daemon_ws(tmp_path):
    """AUTUSE per-test O3 daemon rooted at the pytest tmp_path.

    After the O3 write-path migration, protected-root I/O
    (state/registry/**, audit/**, state/projects/**) routes through the O3
    daemon client. This autouse fixture starts a daemon rooted at the test's
    tmp_path and points the client provider at it, so EVERY test that touches
    protected state (directly or via RuntimeStore/RuntimeAudit/flow) has a
    working fail-closed daemon. The daemon root == tmp_path, so files land at
    tmp_path/state/... and direct fs reads still see daemon-written data.

    Yields (wsdir, client, daemon) for tests that want the handles; tests
    that only need the path use the `ws` fixture (== this root).
    """
    wsdir, client, daemon = start_o3_daemon(tmp_path)
    yield wsdir, client, daemon
    stop_o3_daemon(daemon)


def start_o3_daemon(root, *, reset_provider=True) -> tuple[str, object, object]:
    """Start an O3 daemon on `root` (a per-test/per-run workspace).

    Returns (wsdir_str, client, daemon). Sets env vars so the control-plane
    client provider resolves to this daemon (and resets the cached client).

    Used both by the `o3_daemon_ws` fixture and by tests that need per-run
    daemon roots (nested run dirs — each run gets its own daemon root so
    protected-state isolation is preserved under O3).
    """
    import threading
    import time as _time
    from registry_writer.daemon import DaemonConfig, RegistryWriterDaemon
    from registry_writer.client import RegistryWriterClient
    from registry_writer.provider import reset_client as _reset

    wsdir = str(root)
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "agents/cfo", "agents/kai", "docs"):
        os.makedirs(os.path.join(wsdir, sub), exist_ok=True)

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
    deadline = _time.monotonic() + 5.0
    while _time.monotonic() < deadline:
        if os.path.exists(socket_path):
            break
        _time.sleep(0.01)
    else:
        daemon.shutdown()
        raise RuntimeError(f"O3 daemon did not start at {socket_path} in 5s")

    os.environ["DSH_REGISTRY_WRITER_SOCKET"] = socket_path
    os.environ["DSH_REGISTRY_WRITER_SECRET"] = secret_path
    if reset_provider:
        _reset()
    client = RegistryWriterClient(socket_path, secret)
    return wsdir, client, daemon


def stop_o3_daemon(daemon) -> None:
    """Shut a daemon down and clear the provider env/cache."""
    from registry_writer.provider import reset_client as _reset
    try:
        daemon.shutdown()
    except Exception:
        pass
    os.environ.pop("DSH_REGISTRY_WRITER_SOCKET", None)
    os.environ.pop("DSH_REGISTRY_WRITER_SECRET", None)
    _reset()


from contextlib import contextmanager  # noqa: E402


@contextmanager
def o3_daemon_context(root):
    """Context manager: start an O3 daemon on `root`, yield wsdir, then stop.

    Use for nested/per-run daemon roots where state isolation per run is
    required (each run gets its own daemon root under O3). On exit, the
    provider env vars are RESTORED to their pre-context values, so tests that
    continue using the autouse per-test daemon after the context still work.
    """
    # Save the current provider env so we can restore after the nested daemon.
    saved_sock = os.environ.get("DSH_REGISTRY_WRITER_SOCKET")
    saved_secret = os.environ.get("DSH_REGISTRY_WRITER_SECRET")
    wsdir, client, daemon = start_o3_daemon(root)
    try:
        yield wsdir, client
    finally:
        try:
            daemon.shutdown()
        except Exception:
            pass
        # Restore the previous daemon env (or clear if none).
        if saved_sock is not None:
            os.environ["DSH_REGISTRY_WRITER_SOCKET"] = saved_sock
        else:
            os.environ.pop("DSH_REGISTRY_WRITER_SOCKET", None)
        if saved_secret is not None:
            os.environ["DSH_REGISTRY_WRITER_SECRET"] = saved_secret
        else:
            os.environ.pop("DSH_REGISTRY_WRITER_SECRET", None)
        from registry_writer.provider import reset_client as _reset
        _reset()
# registry_writer/provider.py — Control-plane daemon client provider (O3 Phase B)
#
# The control plane reaches the O3 daemon ONLY via IPC (Unix socket + HMAC).
# This module resolves the daemon socket path + secret from configuration
# (config file or environment overrides) and returns a fail-closed
# RegistryWriterClient. There is NO direct-filesystem fallback: when the
# daemon is down or unreachable, get_client() raises WriterUnavailable, and
# the caller must BLOCK (fail-closed invariant, FINAL architecture §4.7).
#
# Config resolution order (PRECEDENCE, highest first):
#   1. env DSH_REGISTRY_WRITER_SOCKET, DSH_REGISTRY_WRITER_SECRET  — env WINS
#   2. config/registry-writer.yaml (daemon.socket_path, auth.hmac_secret_path)
#
# The environment variables OVERRIDE the config file, they do not lose to it:
# that is what lets a per-test daemon be pointed at a temp root while the
# checked-in file still names the real /var/lib/... daemon. (An earlier
# docstring here claimed "last wins" with the config file last, which
# described the opposite of the implemented behaviour.)
#
# For tests, a fixture sets the env vars to point at a temp-root daemon
# and calls reset_client() to clear the cached client.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from registry_writer.client import RegistryWriterClient, WriterUnavailable  # noqa: E402

_client: RegistryWriterClient | None = None
_client_config: tuple[str, str] | None = None  # (socket_path, secret_path)


def _resolve_config() -> tuple[str, str]:
    """Return (socket_path, secret_path) from env or config file."""
    socket = os.environ.get("DSH_REGISTRY_WRITER_SOCKET")
    secret = os.environ.get("DSH_REGISTRY_WRITER_SECRET")
    if socket and secret:
        return socket, secret

    # Fall back to config/registry-writer.yaml
    config_path = os.path.join(_PROJECT_ROOT, "config", "registry-writer.yaml")
    if os.path.exists(config_path):
        import yaml
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        daemon_cfg = cfg.get("daemon", {})
        auth_cfg = cfg.get("auth", {})
        socket = socket or daemon_cfg.get("socket_path")
        secret = secret or auth_cfg.get("hmac_secret_path")
        if socket and secret:
            return socket, secret

    raise WriterUnavailable(
        "O3 daemon not configured: set DSH_REGISTRY_WRITER_SOCKET and "
        "DSH_REGISTRY_WRITER_SECRET env vars, or configure "
        "config/registry-writer.yaml" if os.path.exists(config_path)
        else f"config/registry-writer.yaml not found at {config_path}")


def get_client() -> RegistryWriterClient:
    """Return a lazily-cached daemon client (fail-closed).

    Raises:
        WriterUnavailable: daemon is not configured or unreachable.
    """
    global _client, _client_config
    cfg = _resolve_config()
    if _client is not None and _client_config == cfg:
        return _client
    _client_config = cfg
    socket_path, secret_path = cfg
    try:
        with open(secret_path, "rb") as f:
            secret = f.read()
    except (OSError, FileNotFoundError) as e:
        raise WriterUnavailable(
            f"cannot read daemon HMAC secret at {secret_path}: {e}") from e
    _client = RegistryWriterClient(socket_path, secret)
    # Verify connectivity (fail-fast, fail-closed)
    try:
        _client.health()
    except WriterUnavailable:
        raise
    except Exception as e:
        raise WriterUnavailable(f"daemon health check failed: {e}") from e
    return _client


def reset_client() -> None:
    """Clear the cached client (for tests / config changes)."""
    global _client, _client_config
    if _client is not None:
        try:
            _client = None
            _client_config = None
        except Exception:
            pass
# registry_writer/client.py — control-plane client for the O3 daemon
#
# Used by control/execution_gate.py (registry_write / audit_append) and
# orchestrator/runtime/store.py (project_write / project_read) after
# migration Phase B. FAIL-CLOSED by design: a daemon that is down, degraded,
# or unreachable raises WriterUnavailable — there is NO direct-fs fallback
# (the hard invariant, FINAL architecture §4.7 / acceptance O3-FC-005).

from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from schemas.ipc import (  # noqa: E402
    AUTHORIZED_CHANNEL,
    make_request,
    now_iso,
    sign_request,
)


class WriterUnavailable(Exception):
    """Daemon down / starting / in recovery — callers must STOP (fail-closed)."""


class DaemonRpcError(Exception):
    """A typed IPC error from the daemon (code in .code)."""

    def __init__(self, code: str, message: str, request_id: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.request_id = request_id


class RegistryWriterClient:
    """Minimal HMAC-authenticated IPC client for the O3 daemon."""

    def __init__(self, socket_path: str, secret: bytes,
                 timeout: float = 30.0):
        self.socket_path = socket_path
        self.secret = secret
        self.timeout = timeout

    # -- request plumbing -------------------------------------------------
    def call(self, method: str, params: dict) -> dict:
        request_id = str(uuid.uuid4())
        issued_at = now_iso()
        nonce = secrets.token_hex(16)
        token = sign_request(self.secret, method, request_id, issued_at,
                             nonce, params)
        auth = {
            "channel": AUTHORIZED_CHANNEL,
            "token": token,
            "issued_at": issued_at,
            "nonce": nonce,
        }
        request = make_request(request_id, method, params, auth)
        try:
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            conn.settimeout(self.timeout)
            conn.connect(self.socket_path)
        except OSError as e:
            raise WriterUnavailable(
                f"daemon unreachable at {self.socket_path}: {e}") from e
        try:
            payload = json.dumps(request).encode() + b"\n"
            conn.sendall(payload)
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(65536)
                if not chunk:
                    raise WriterUnavailable("daemon closed connection")
                buf += chunk
            line = buf.split(b"\n", 1)[0].strip()
            response = json.loads(line)
        except json.JSONDecodeError as e:
            raise DaemonRpcError("INTERNAL_ERROR", f"malformed response: {e}",
                                 request_id) from e
        except socket.timeout as e:
            raise WriterUnavailable(f"daemon timeout on {method}") from e
        finally:
            try:
                conn.close()
            except OSError:
                pass

        if not response.get("ok"):
            err = response.get("error") or {}
            raise DaemonRpcError(err.get("code", "INTERNAL_ERROR"),
                                 err.get("message", "unknown error"),
                                 response.get("id", request_id))
        return response.get("result") or {}

    # -- typed methods -----------------------------------------------------
    def registry_write(self, key: str, data: dict, expected_version: int) -> dict:
        return self.call("registry_write", {
            "target": f"state/registry/{key}.json",
            "data": data,
            "expected_version": expected_version,
        })

    def registry_read(self, key: str) -> dict:
        return self.call("registry_read", {
            "target": f"state/registry/{key}.json"})

    def audit_append(self, project: str, event: dict) -> dict:
        return self.call("audit_append", {
            "target": f"audit/{project}/events.jsonl",
            "event": event,
        })

    def audit_read(self, project: str, since_seq: int = 0) -> dict:
        return self.call("audit_read", {
            "target": f"audit/{project}/events.jsonl",
            "since_seq": since_seq,
        })

    def audit_verify(self, project: str, known_cumulative_hash: str | None = None,
                     known_line_count: int | None = None) -> dict:
        return self.call("audit_verify", {
            "target": f"audit/{project}/events.jsonl",
            "known_cumulative_hash": known_cumulative_hash,
            "known_line_count": known_line_count,
        })

    def project_write(self, project: str, data: dict,
                      expected_version: int) -> dict:
        return self.call("project_write", {
            "target": f"state/projects/{project}.json",
            "data": data,
            "expected_version": expected_version,
        })

    def project_read(self, project: str) -> dict:
        return self.call("project_read", {
            "target": f"state/projects/{project}.json"})

    def health(self, name: str | None = None) -> dict:
        return self.call("health", {"name": name} if name else {})

    def backup(self, label: str | None = None) -> dict:
        return self.call("backup", {"label": label} if label else {})

    def restore(self, backup_path: str, confirmed: bool) -> dict:
        return self.call("restore", {
            "backup_path": backup_path, "confirmed": confirmed})

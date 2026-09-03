# schemas/ipc.py — O3 daemon IPC contract (wire types, error codes, authn helpers)
#
# G10 O3 (FINAL architecture §4.3–§4.5, acceptance spec 0004 §2.2):
#   Transport: Unix domain socket, NDJSON (one JSON object per line)
#   Protocol version: v: 1
#   Authn: per-request HMAC-SHA256 bearer token (channel, issued_at ±window,
#          nonce) over method || id || issued_at || nonce || canonical-params
#   Authz: per-method → sanctioned root (mirrors SANCTIONED_ROOTS + projects)
#   Error codes: WRITER_UNAVAILABLE / UNAUTHORIZED / FORBIDDEN /
#                INVALID_REQUEST / INTERNAL_ERROR / CORRUPTION_DETECTED /
#                RECOVERY_REQUIRED
#
# This module is pure (no I/O, no production imports) so the daemon, the
# client, and the acceptance tests share one wire contract.

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

PROTOCOL_VERSION = 1

# ---------------------------------------------------------------------------
# Error codes (FINAL architecture §4.3)
# ---------------------------------------------------------------------------
ERROR_CODES = (
    "WRITER_UNAVAILABLE",
    "UNAUTHORIZED",
    "FORBIDDEN",
    "INVALID_REQUEST",
    "INTERNAL_ERROR",
    "CORRUPTION_DETECTED",
    "RECOVERY_REQUIRED",
)

# Per-method → sanctioned root (FINAL architecture §4.4). Mirrors
# control/execution_gate.SANCTIONED_ROOTS plus the state/projects/** extension.
# `None` root means the method is not path-scoped (health) or is an operator
# action spanning all roots (backup/restore — still authenticated + authorized
# via the control_plane channel).
SANCTIONED_ROOTS: dict[str, str | None] = {
    "registry_write": "state/registry",
    "registry_read": "state/registry",
    "audit_append": "audit",
    "audit_read": "audit",
    "audit_verify": "audit",
    "project_write": "state/projects",
    "project_read": "state/projects",
    "health": None,
    "backup": None,
    "restore": None,
}

# Methods that mutate state (used by fail-closed / recovery gating).
WRITE_METHODS = {"registry_write", "audit_append", "project_write",
                 "backup", "restore"}

# The only channel permitted for any method. A non-control_plane channel is
# FORBIDDEN for every method (health included — health carries no token
# requirement but accepts one; enforcement is in the daemon).
AUTHORIZED_CHANNEL = "control_plane"

DEFAULT_REPLAY_WINDOW_SECONDS = 30


# ---------------------------------------------------------------------------
# Canonical serialization + signature (shared by client and daemon)
# ---------------------------------------------------------------------------
def canonical_json(data: Any) -> str:
    """Deterministic single-line JSON for hashing (sorted keys, no whitespace)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def request_signature_input(method: str, request_id: str, issued_at: str,
                            nonce: str, params: dict) -> str:
    """The exact string the HMAC is computed over (FINAL architecture §4.4)."""
    return "||".join([method, request_id, issued_at, nonce, canonical_json(params)])


def sign_request(secret: bytes, method: str, request_id: str, issued_at: str,
                 nonce: str, params: dict) -> str:
    """HMAC-SHA256 signature of the canonical request."""
    payload = request_signature_input(method, request_id, issued_at, nonce, params)
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(secret: bytes, expected_token: str, method: str,
                     request_id: str, issued_at: str, nonce: str,
                     params: dict) -> bool:
    """Constant-time comparison of a presented token against the recomputed one."""
    want = sign_request(secret, method, request_id, issued_at, nonce, params)
    return hmac.compare_digest(want, (expected_token or "").lower())


def parse_iso_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (accepts trailing Z); raises ValueError."""
    norm = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(norm)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def now_iso() -> str:
    """Current UTC timestamp in ISO-8601 form (for issued_at/updated_at)."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def within_replay_window(issued_at: str, now: float | None = None,
                         window_seconds: int = DEFAULT_REPLAY_WINDOW_SECONDS) -> bool:
    """True iff |now - issued_at| <= window (replay window, FINAL §4.5)."""
    try:
        issued = parse_iso_ts(issued_at).timestamp()
    except (ValueError, TypeError):
        return False
    now = time.time() if now is None else now
    return abs(now - issued) <= window_seconds


# ---------------------------------------------------------------------------
# Request/response builders (wire contract)
# ---------------------------------------------------------------------------
def make_request(request_id: str, method: str, params: dict,
                 auth: dict | None = None) -> dict:
    """Build a wire request dict (v, id, method, params, auth)."""
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "method": method,
        "params": params or {},
        "auth": auth,
    }


def make_success(request_id: str, result: dict) -> dict:
    return {"v": PROTOCOL_VERSION, "id": request_id, "ok": True, "result": result}


def make_error(request_id: str, code: str, message: str) -> dict:
    return {
        "v": PROTOCOL_VERSION, "id": request_id, "ok": False,
        "error": {"code": code, "message": message},
    }


def validate_request(request: dict) -> tuple[bool, str | None]:
    """Structural validation of a wire request. Returns (ok, error_message)."""
    if not isinstance(request, dict):
        return False, "request must be a JSON object"
    if request.get("v") != PROTOCOL_VERSION:
        return False, f"unsupported protocol version {request.get('v')!r}"
    rid = request.get("id")
    if not (isinstance(rid, str) and rid.strip()):
        return False, "missing request id"
    method = request.get("method")
    if not (isinstance(method, str) and method in SANCTIONED_ROOTS):
        return False, f"unknown method {method!r}"
    params = request.get("params")
    if params is not None and not isinstance(params, dict):
        return False, "params must be a JSON object"
    auth = request.get("auth")
    if auth is not None and not isinstance(auth, dict):
        return False, "auth must be a JSON object"
    return True, None

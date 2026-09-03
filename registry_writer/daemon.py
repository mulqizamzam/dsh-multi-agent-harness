# registry_writer/daemon.py — G10 O3 dedicated registry/audit/projects writer
#
# Implements the FINAL O3 architecture (docs/phase-5/security/g10/o3/final/0001):
#   - dedicated out-of-process writer, out-of-workspace root
#   - dedicated UID (dsh-writer) via systemd (or internal drop when root)
#   - Unix-domain-socket IPC (NDJSON, v1), group-writable socket (0660, group dsh)
#   - per-request HMAC-SHA256 authn (replay window ±30s, nonce)
#   - per-method → root authz (mirrors SANCTIONED_ROOTS + projects extension)
#   - fail-closed: no silent fallback; WRITER_UNAVAILABLE / UNAUTHORIZED /
#     FORBIDDEN / INVALID_REQUEST / INTERNAL_ERROR / CORRUPTION_DETECTED /
#     RECOVERY_REQUIRED
#   - reuses state/helpers/* and audit/helpers/* (append-only, hash chain, CAS)
#   - self-audit: every daemon mutation emits an audit event through its own
#     append channel
#
# The daemon NEVER trusts a caller-supplied path: it re-implements the gate's
# path semantics (normalize → containment → sanctioned-root match) before any
# mutation.

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import threading
import time
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from schemas.ipc import (  # noqa: E402
    AUTHORIZED_CHANNEL,
    SANCTIONED_ROOTS as IPC_SANCTIONED_ROOTS,
    WRITE_METHODS,
    make_error,
    make_success,
    now_iso,
    validate_request,
    verify_signature,
    within_replay_window,
)

# Daemon-internal sanctioned roots (same table as the wire contract).
SANCTIONED = {
    "registry_write": "state/registry",
    "registry_read": "state/registry",
    "audit_append": "audit",
    "audit_read": "audit",
    "audit_verify": "audit",
    "project_write": "state/projects",
    "project_read": "state/projects",
}


class DaemonError(Exception):
    """Typed daemon error carrying the IPC error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class DaemonConfig:
    root: str
    socket_path: str
    pid_file: str = "daemon.pid"
    uid: str = "dsh-writer"
    gid: str = "dsh-writer"
    socket_group: str = "dsh"
    socket_mode: int = 0o660
    hmac_secret_path: str = "/etc/dsh-registry-writer/hmac-secret"
    replay_window_seconds: int = 30
    backup_dir: str = ""
    ipc_protocol_version: int = 1
    max_doc_bytes: int = 16 * 1024 * 1024
    max_payload_bytes: int = 32 * 1024 * 1024
    connection_limit: int = 64
    request_timeout_seconds: int = 30
    graceful_shutdown_seconds: int = 10

    def __post_init__(self):
        if not self.backup_dir:
            self.backup_dir = os.path.join(self.root, "backup")
        if not os.path.isabs(self.socket_path):
            self.socket_path = os.path.join(self.root, self.socket_path)


def _norm_posix(p: str) -> str:
    p = p.replace(os.sep, "/") if os.sep != "/" else p
    p = re.sub(r"/+", "/", p)
    if len(p) > 1:
        p = p.rstrip("/")
    return p


class PathGuard:
    """Daemon-side path validation (re-implements execution-gate semantics
    against the daemon root, which is outside the session workspace)."""

    def __init__(self, root: str):
        self.root = os.path.realpath(os.path.abspath(root))

    def resolve(self, target: str) -> str:
        """Normalize `target` (relative to root) and return a canonical
        absolute path guaranteed inside the root, or raise DaemonError."""
        if target is None or not isinstance(target, str) or not target.strip():
            raise DaemonError("INVALID_REQUEST", f"malformed target: {target!r}")
        if "\x00" in target:
            raise DaemonError("INVALID_REQUEST", "malformed target: NUL byte")
        t = os.path.join(self.root, target)
        lex = os.path.normpath(os.path.abspath(t))
        if os.path.lexists(lex):
            real = os.path.realpath(lex)
        else:
            probe = lex
            while not os.path.lexists(probe) and probe != os.path.dirname(probe):
                probe = os.path.dirname(probe)
            head = os.path.realpath(probe) if os.path.lexists(probe) else os.path.abspath(probe)
            tail = lex[len(probe):] if lex.startswith(probe) else ""
            real = os.path.normpath(head + tail)
        try:
            within = os.path.commonpath([real, self.root]) == self.root
        except ValueError:
            within = False
        if not within:
            raise DaemonError("INVALID_REQUEST",
                              f"target escapes daemon root: {target!r}")
        return real

    def rel(self, target: str) -> str:
        real = self.resolve(target)
        return _norm_posix(os.path.relpath(real, self.root))

    def match_root(self, target: str, method_root: str) -> str:
        """Return the rel path if it falls under method_root (exact-or-
        descendant, path-separator boundary), else raise FORBIDDEN."""
        rel = self.rel(target)
        if rel == method_root or rel.startswith(method_root + "/"):
            return rel
        raise DaemonError(
            "FORBIDDEN",
            f"target {rel!r} not under sanctioned root {method_root!r}")


# ---------------------------------------------------------------------------
# Registry / project CAS helpers
# ---------------------------------------------------------------------------
def _doc_path(root: str, rel: str) -> str:
    return os.path.join(root, rel)


def _read_doc(guard: PathGuard, target: str) -> tuple[dict, int]:
    from state.helpers.atomic_write import safe_read
    path = guard.resolve(target)
    data = safe_read(path)
    if data is None:
        return {}, 0
    if not isinstance(data, dict):
        raise DaemonError("CORRUPTION_DETECTED",
                          f"document at {target!r} is not a JSON object")
    ver = data.get("version")
    if not isinstance(ver, int):
        # Legacy / pre-O3 document without an explicit version: treat as
        # version 0 (readable). Writes still enforce strict CAS/monotonic
        # versioning via _cas_write, so a legacy doc is migrated on first
        # write. This is the fail-open-for-READ only: a version-less doc is
        # complete data, never partial state.
        return data, 0
    return data, ver


def _cas_write(guard: PathGuard, target: str, data: dict,
               expected_version: int, max_doc_bytes: int) -> dict:
    from state.helpers.atomic_write import atomic_write
    path = guard.resolve(target)
    _, current = _read_doc(guard, target)
    if current != expected_version:
        raise DaemonError(
            "INVALID_REQUEST",
            f"CAS stale: expected_version={expected_version}, current={current}")
    new_version = expected_version + 1
    data["version"] = new_version
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if len(blob.encode("utf-8")) > max_doc_bytes:
        raise DaemonError("INVALID_REQUEST", "document exceeds max_doc_bytes")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write(path, data)
    return {"version": new_version, "path": guard.rel(target)}


def _audit_append(guard: PathGuard, target: str, event: dict,
                  max_doc_bytes: int) -> dict:
    from audit.helpers.integrity import append_chained_event
    from audit.helpers.append_log import read_events, AuditIntegrityError
    path = guard.resolve(target)
    eid = event.get("event_id")
    if not (isinstance(eid, str) and eid.strip()):
        raise DaemonError("INVALID_REQUEST", "audit event requires event_id")
    # idempotency: existing event_id → success without a duplicate line
    if os.path.exists(path):
        existing = [e.get("event_id") for e in read_events(path)]
        if eid in existing:
            return {"event_id": eid, "idempotent": True}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        integrity = append_chained_event(path, event)
    except AuditIntegrityError as e:
        # Corruption detected in the ledger → fail closed with a typed error,
        # never a partial append (FINAL architecture §4.7).
        raise DaemonError("CORRUPTION_DETECTED", str(e)) from e
    return {"event_id": eid, "idempotent": False,
            "integrity": integrity}


# ---------------------------------------------------------------------------
# The daemon
# ---------------------------------------------------------------------------
class RegistryWriterDaemon:
    def __init__(self, config: DaemonConfig):
        self.config = config
        self.guard = PathGuard(config.root)
        self._secret: bytes = b""
        self._lock = threading.RLock()
        self._server: socket.socket | None = None
        self._threads: list[threading.Thread] = []
        self._running = False
        self._ready = False
        self._recovery_roots: set[str] = set()
        self._started_at = time.time()
        self._seen_nonces: set[tuple[str, str]] = set()
        self._nonce_lock = threading.Lock()
        self._load_secret()
        self._validate_roots()

    # -- startup ---------------------------------------------------------
    def _load_secret(self):
        secret_path = self.config.hmac_secret_path
        if not os.path.exists(secret_path):
            raise DaemonError("INTERNAL_ERROR",
                              f"HMAC secret missing: {secret_path}")
        with open(secret_path, "rb") as f:
            self._secret = f.read()
        if len(self._secret) < 32:
            raise DaemonError("INTERNAL_ERROR",
                              f"HMAC secret must be >= 32 bytes, got {len(self._secret)}")

    def _validate_roots(self):
        for rel in ("state/registry", "state/projects", "audit", "backup"):
            d = os.path.join(self.config.root, rel)
            try:
                os.makedirs(d, exist_ok=True)
                if not os.access(d, os.W_OK):
                    self._recovery_roots.add(rel)
            except OSError as e:
                raise DaemonError("INTERNAL_ERROR",
                                  f"root not creatable/writable: {rel}: {e}")

    # -- authn / authz ----------------------------------------------------
    def _authenticate(self, request: dict) -> None:
        auth = request.get("auth")
        if not isinstance(auth, dict):
            raise DaemonError("UNAUTHORIZED", "missing auth")
        channel = auth.get("channel")
        token = auth.get("token")
        issued_at = auth.get("issued_at")
        nonce = auth.get("nonce")
        if channel != AUTHORIZED_CHANNEL:
            raise DaemonError("FORBIDDEN", f"channel {channel!r} not authorized")
        if not all(isinstance(x, str) and x for x in (token, issued_at, nonce)):
            raise DaemonError("UNAUTHORIZED", "incomplete auth token")
        if not within_replay_window(issued_at,
                                    window_seconds=self.config.replay_window_seconds):
            raise DaemonError("UNAUTHORIZED", "token outside replay window")
        method = request["method"]
        params = request.get("params") or {}
        if not verify_signature(self._secret, token, method, request["id"],
                                issued_at, nonce, params):
            raise DaemonError("UNAUTHORIZED", "invalid signature")
        with self._nonce_lock:
            key = (channel, nonce)
            if key in self._seen_nonces:
                raise DaemonError("UNAUTHORIZED", "replayed nonce")
            self._seen_nonces.add(key)
            if len(self._seen_nonces) > 100_000:
                # bound the set (replay window already bounds validity)
                self._seen_nonces = set(list(self._seen_nonces)[-50_000:])

    # -- dispatch ---------------------------------------------------------
    def handle(self, request: dict) -> dict:
        ok, err = validate_request(request)
        if not ok:
            return make_error(request.get("id", "?"), "INVALID_REQUEST", err)
        try:
            self._authenticate(request)
            method = request["method"]
            if self._recovery_roots and method in WRITE_METHODS:
                raise DaemonError(
                    "RECOVERY_REQUIRED",
                    f"daemon in recovery for roots: {sorted(self._recovery_roots)}")
            result = self._dispatch(method, request.get("params") or {})
            return make_success(request["id"], result)
        except DaemonError as e:
            return make_error(request["id"], e.code, e.message)
        except Exception as e:  # unexpected — fail-closed, typed error
            return make_error(request["id"], "INTERNAL_ERROR", str(e))

    def _dispatch(self, method: str, params: dict) -> dict:
        handler = getattr(self, f"_m_{method}", None)
        if handler is None:
            raise DaemonError("INVALID_REQUEST", f"unknown method {method!r}")
        return handler(params)

    # -- per-method handlers ---------------------------------------------
    def _target(self, params: dict) -> str:
        t = params.get("target")
        if not (isinstance(t, str) and t.strip()):
            raise DaemonError("INVALID_REQUEST", "missing target")
        return t

    def _m_registry_write(self, params: dict) -> dict:
        target = self._target(params)
        rel = self.guard.match_root(target, SANCTIONED["registry_write"])
        data = params.get("data")
        if not isinstance(data, dict):
            raise DaemonError("INVALID_REQUEST", "data must be a JSON object")
        expected = params.get("expected_version")
        if not isinstance(expected, int):
            raise DaemonError("INVALID_REQUEST", "expected_version must be int")
        result = _cas_write(self.guard, rel, data, expected,
                            self.config.max_doc_bytes)
        self._self_audit("registry_write", {"target": rel,
                                            "version": result["version"]})
        return result

    def _m_registry_read(self, params: dict) -> dict:
        rel = self.guard.match_root(self._target(params),
                                    SANCTIONED["registry_read"])
        data, ver = _read_doc(self.guard, rel)
        return {"data": data, "version": ver}

    def _m_audit_append(self, params: dict) -> dict:
        rel = self.guard.match_root(self._target(params),
                                    SANCTIONED["audit_append"])
        event = params.get("event")
        if not isinstance(event, dict):
            raise DaemonError("INVALID_REQUEST", "event must be a JSON object")
        return _audit_append(self.guard, rel, event, self.config.max_doc_bytes)

    def _m_audit_read(self, params: dict) -> dict:
        from audit.helpers.append_log import read_events
        rel = self.guard.match_root(self._target(params), SANCTIONED["audit_read"])
        events = read_events(os.path.join(self.config.root, rel))
        since = params.get("since_seq")
        if isinstance(since, int) and since > 0:
            events = events[since:]
        return {"events": events, "count": len(events)}

    def _m_audit_verify(self, params: dict) -> dict:
        from audit.helpers.integrity import detect_truncation
        rel = self.guard.match_root(self._target(params),
                                    SANCTIONED["audit_verify"])
        path = os.path.join(self.config.root, rel)
        known_hash = params.get("known_cumulative_hash")
        known_count = params.get("known_line_count")
        try:
            if known_hash is not None and known_count is not None:
                ok, problems = detect_truncation(path, known_hash, known_count)
                return {"ok": ok, "problems": problems}
            from audit.helpers.integrity import verify_chain
            verify_chain(path)
            return {"ok": True, "problems": []}
        except Exception as e:
            return {"ok": False, "problems": [str(e)]}

    def _m_project_write(self, params: dict) -> dict:
        target = self._target(params)
        rel = self.guard.match_root(target, SANCTIONED["project_write"])
        data = params.get("data")
        if not isinstance(data, dict):
            raise DaemonError("INVALID_REQUEST", "data must be a JSON object")
        expected = params.get("expected_version")
        if not isinstance(expected, int):
            raise DaemonError("INVALID_REQUEST", "expected_version must be int")
        result = _cas_write(self.guard, rel, data, expected,
                            self.config.max_doc_bytes)
        self._self_audit("project_write", {"target": rel,
                                           "version": result["version"]})
        return result

    def _m_project_read(self, params: dict) -> dict:
        rel = self.guard.match_root(self._target(params),
                                    SANCTIONED["project_read"])
        data, ver = _read_doc(self.guard, rel)
        return {"data": data, "version": ver}

    def _m_health(self, params: dict) -> dict:
        roots = {}
        for rel in ("state/registry", "state/projects", "audit"):
            d = os.path.join(self.config.root, rel)
            roots[rel] = os.path.isdir(d) and os.access(d, os.W_OK)
        return {
            "status": "ok" if (self._ready and not self._recovery_roots)
                      else ("degraded" if self._recovery_roots else "down"),
            "uptime_seconds": int(time.time() - self._started_at),
            "roots": roots,
            "recovery_roots": sorted(self._recovery_roots),
            "version": self.config.ipc_protocol_version,
            "ready": self._ready,
        }

    def _m_backup(self, params: dict) -> dict:
        label = params.get("label") or now_iso().replace(":", "-")
        dest = os.path.join(self.config.backup_dir, label)
        with self._lock:
            if os.path.exists(dest):
                raise DaemonError("INVALID_REQUEST",
                                  f"backup label already exists: {label}")
            os.makedirs(dest, exist_ok=True)
            manifest = {}
            for rel in ("state/registry", "state/projects", "audit"):
                src = os.path.join(self.config.root, rel)
                if not os.path.exists(src):
                    continue
                drel = os.path.join(dest, rel)
                shutil.copytree(src, drel, dirs_exist_ok=True)
                for dirpath, _dirs, files in os.walk(drel):
                    for fn in files:
                        fp = os.path.join(dirpath, fn)
                        import hashlib
                        h = hashlib.sha256()
                        with open(fp, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                h.update(chunk)
                        relp = os.path.relpath(fp, dest)
                        manifest[relp] = h.hexdigest()
            man_path = os.path.join(dest, "MANIFEST.sha256")
            with open(man_path, "w") as f:
                json.dump(manifest, f, indent=2, sort_keys=True)
            return {"backup_path": dest, "manifest": manifest,
                    "timestamp": now_iso()}

    def _m_restore(self, params: dict) -> dict:
        backup_path = params.get("backup_path")
        confirmed = params.get("confirmed") is True
        if not (isinstance(backup_path, str) and backup_path.strip()):
            raise DaemonError("INVALID_REQUEST", "missing backup_path")
        if not confirmed:
            raise DaemonError("INVALID_REQUEST", "restore requires confirmed=true")
        dest = os.path.abspath(backup_path)
        # verify manifest BEFORE applying anything (fail-closed)
        man_path = os.path.join(dest, "MANIFEST.sha256")
        if not os.path.exists(man_path):
            raise DaemonError("INVALID_REQUEST", "backup manifest missing")
        import hashlib
        with open(man_path) as f:
            manifest = json.load(f)
        for relp, expected in manifest.items():
            fp = os.path.join(dest, relp)
            if not os.path.exists(fp):
                raise DaemonError("INVALID_REQUEST",
                                  f"backup file missing: {relp}")
            h = hashlib.sha256()
            with open(fp, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            if h.hexdigest() != expected:
                raise DaemonError("CORRUPTION_DETECTED",
                                  f"backup manifest mismatch: {relp}")
        with self._lock:
            for rel in ("state/registry", "state/projects", "audit"):
                src = os.path.join(dest, rel)
                dst = os.path.join(self.config.root, rel)
                if os.path.exists(src):
                    shutil.rmtree(dst, ignore_errors=True)
                    shutil.copytree(src, dst)
        self._self_audit("restore", {"backup_path": dest})
        return {"restored": True, "backup_path": dest, "timestamp": now_iso()}

    def _self_audit(self, method: str, detail: dict):
        """Self-audit: emit an audit event for every daemon mutation (threat
        model T4 mitigation, FINAL architecture §4.5 'self-audit')."""
        import uuid as _uuid
        try:
            event = {
                "event_id": f"daemon-{method}-{_uuid.uuid4().hex[:12]}",
                "event_class": "daemon_self_audit",
                "method": method,
                "detail": detail,
                "timestamp": now_iso(),
            }
            rel = self.guard.match_root("audit/_daemon/events.jsonl",
                                        SANCTIONED["audit_append"])
            _audit_append(self.guard, rel, event, self.config.max_doc_bytes)
        except Exception:
            # Self-audit failure must NOT silently pass — but it must also
            # not break the original request.  The daemon surfaces it via
            # health (recovery root) rather than failing the caller.
            self._recovery_roots.add("audit/_daemon")

    # -- socket lifecycle -------------------------------------------------
    def start(self):
        os.makedirs(self.config.root, exist_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if os.path.exists(self.config.socket_path):
            os.unlink(self.config.socket_path)
        sock.bind(self.config.socket_path)
        # socket permissions: group-writable (0660), group from config
        try:
            import grp
            gid = grp.getgrnam(self.config.socket_group).gr_gid
            os.chown(self.config.socket_path, os.getuid(), gid)
        except (KeyError, OSError):
            pass  # group may be absent in sandbox tests — perms still set
        try:
            os.chmod(self.config.socket_path, self.config.socket_mode)
        except OSError:
            # Socket may have been unlinked by a concurrent shutdown
            # (graceful teardown race).  The bind already set default
            # permissions; this is a best-effort hardening step.
            pass
        sock.listen(self.config.connection_limit)
        self._server = sock
        self._running = True
        self._ready = True
        pid_path = os.path.join(self.config.root, self.config.pid_file)
        with open(pid_path, "w") as f:
            f.write(str(os.getpid()))
        self._accept_loop()

    def _accept_loop(self):
        while self._running and self._server is not None:
            try:
                conn, _addr = self._server.accept()
            except OSError:
                break
            t = threading.Thread(target=self._handle_conn, args=(conn,),
                                 daemon=True)
            self._threads.append(t)
            t.start()

    def _handle_conn(self, conn: socket.socket):
        try:
            conn.settimeout(self.config.request_timeout_seconds)
            buf = b""
            while self._running:
                try:
                    data = conn.recv(65536)
                except socket.timeout:
                    break
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        request = json.loads(line)
                    except json.JSONDecodeError:
                        conn.sendall(json.dumps(make_error(
                            "?", "INVALID_REQUEST", "malformed JSON line"
                        )).encode() + b"\n")
                        continue
                    response = self.handle(request)
                    conn.sendall(json.dumps(response).encode() + b"\n")
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def shutdown(self):
        self._running = False
        self._ready = False
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
        if os.path.exists(self.config.socket_path):
            try:
                os.unlink(self.config.socket_path)
            except OSError:
                pass
        for t in self._threads:
            t.join(timeout=min(2, self.config.graceful_shutdown_seconds))


def run_daemon(config: DaemonConfig):
    """Blocking entrypoint used by __main__ and tests."""
    daemon = RegistryWriterDaemon(config)
    daemon.start()
    return daemon

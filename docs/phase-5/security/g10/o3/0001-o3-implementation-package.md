# G10 O3 — Dedicated Registry/Audit/Projects Writer Process: Implementation Package

- **Milestone**: Phase 5 / Session D — G10 O3 IMPLEMENTATION PACKAGE (design only; **NOT implemented**)
- **Status**: IMPLEMENTATION PACKAGE — comprehensive design, migration plan, acceptance tests, and threat model. **O3 is NOT implemented.** Daemon code is NOT written. `control/*`, `orchestrator/*`, `state/*`, `audit/*`, DSH core, session policy, and role capabilities are **unchanged**. **O3 alone does NOT close G10 — G10 remains OPEN / BLOCKING (see `0002-o3-g10-closure-determination.md`).**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (actor set `{zeko, cto}`)
- **Write-only scope**: `docs/phase-5/security/g10/o3/` + `tests/g10/o3-planning/`. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim.**
- **Companion**: `docs/phase-5/security/g10/o3/0002-o3-g10-closure-determination.md` · `0003-o3-threat-model.md` · `0004-o3-acceptance-test-spec.md` · `docs/phase-5/security/g10/implementation/0001-o5-o3-implementation-plan.md` (plan) · `0002-o5-application-record.md` (O5 applied) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (decision record) · `docs/adr/0002-registry-protection-mechanism.md` (consequence 4) · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py` · `state/helpers/*` · `audit/helpers/*` · `schemas/*`.

---

## 1. Current state (re-verified, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` |
| Sandbox | **per-session**, not per-agent; `workspace-write` writable roots = `[workspaceRoot, '/tmp', tmpdir()]` | `roots.ts:52–55`; `child-agent.ts:177–204` |
| toolFilter | **tool-name-level only**, never path-level | `tools/index.ts:680–690` |
| Raw-write actor set | `{zeko, cto}` (post-O5: somad/nova stripped of write/edit) | `config/role-preset-mapping.yaml`; `tests/g10/` |
| O5 applied | Yes — removal of `write`/`edit` from somad, nova; shrink from `{zeko,cto,somad,nova}` to `{zeko,cto}` | `0002-o5-application-record.md` |
| Protected paths (gate) | `state/registry/**`, `audit/**` (`PROTECTED_REL_ROOTS`). `state/projects/**` is **ALLOWED** at the gate (CAS-detected post-hoc, not gate-DENIED) | `execution_gate.py:57`, `PROTECTED_REL_ROOTS`; Session C assessment §2.3 |
| Gate channels | `registry_write()` → `state/registry/**`; `audit_append()` → `audit/**`; `write_through()` → any (non-protected) workspace path | `execution_gate.py:282–305` |
| Registry write path | `execution_gate.registry_write()` → `atomic_write` (sanctioned, single-writer) | `execution_gate.py:282–290` |
| Audit append path | `execution_gate.audit_append()` → `append_event` (sanctioned, append-only, fsync) | `execution_gate.py:293–305` |
| Project state write path | `RuntimeStore.persist()` → `write_through("write", ...)` → `atomic_write` (CAS version check, not gate-DENIED) | `store.py:130–145`; `execution_gate.py:205` |
| Detection stack | Append-only ledger + hash-chain sidecar + cumulative SHA-256 + CAS/version monotonicity | `audit/helpers/{append_log,integrity}.py`; `state/helpers/{atomic_write,version_check}.py` |
| Delegation reads | `FileDelegationProvider.current()` → `safe_read` (`state/registry/delegations.json` + `revocations.json`) | `delegation.py:53–87` |
| Recovery | STOP→PRESERVE→DIAGNOSE→ROLLBACK→VERIFY→REPLAN→AUTHORITY_RECHECK→COMPLETE | `state/helpers/recovery.py` |
| G10 status | **OPEN / BLOCKING** for production; residual accepted (V1, containment = detection) | closure matrix §1; residual proof §1 |
| O3 status | **NOT IMPLEMENTED** — this package is the design | this document |

**The residual R (re-stated, post-O5):** a raw-write-capable role (`{zeko, cto}`) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. The L1 execution gate intercepts only channeled writes. DSH provides no per-path or per-agent interception. **Prevention: ABSENT at the DSH layer. Containment: DETECTION at the project layer** (L1 gate + append-only + cumulative hash chain + CAS). **G10 stays OPEN / BLOCKING for production.**

---

## 2. O3 objective and design principles

**Objective:** hard-isolate the authority source (`state/registry/**`) and the append-only audit trail (`audit/**`) from the shared session sandbox, preventing any raw DSH tool call (even from `{zeko, cto}`) from reaching those roots. Extend the same isolation to `state/projects/**` (the project state document) so the three G10 residual roots are all covered.

**Design principles:**

1. **Out-of-process writer (daemon).** A new process with its own workspace root (or UID/credential); only this process may write the three roots. All session tools (including `{zeko, cto}` raw `bash`/`write`/`edit`) are blocked by the sandbox boundary or filesystem permission boundary.
2. **Fail-closed.** Daemon unavailable → every write to the three roots is **BLOCKED** with a typed error. **No silent fallback** to direct write (that would defeat the isolation).
3. **No DSH modification.** The daemon is a project-layer process (ADR 0002 consequence 4). DSH core, session policy, role toolFilter, and role capabilities are untouched.
4. **Preserve existing detection stack.** The daemon reuses `audit/helpers/*`, `state/helpers/*` (append-only, hash chain, CAS, atomic write) — these are importable modules; no semantic change to the integrity/safety logic.
5. **Authority semantics unchanged.** The daemon is an **execution proxy** under the same single-writer contract (ADR 0002 Option B). Control-plane authority decisions (delegation scoping + execution gate) are preserved; the daemon does not grant or scope authority — it authenticates and path-scopes every request.
6. **Scope extension to state/projects/****. O3 as defined in this package covers all three G10 residual roots: `state/registry/**`, `audit/**`, `state/projects/**`. This is a **design extension** beyond the original ADR 0002 consequence 4 description (which only mentioned registry/audit). The extension is necessary for O3 to fully address the G10 residual (see `0002-o3-g10-closure-determination.md`).

---

## 3. Component inventory

The O3 daemon requires these NEW components (none exist yet; none are implemented in this session):

| # | Component | Description | Type |
|---|---|---|---|
| 1 | **Daemon entrypoint** (e.g. `control/registry_writer/__main__.py` or `registry_writer/server.py`) | Process entrypoint: socket bind, authn setup, health endpoint, signal handling, startup/shutdown orchestration | NEW module |
| 2 | **Daemon core** (e.g. `control/registry_writer/daemon.py`) | Request dispatch, method routing, per-root validation, IPC framing, authn authz, health state, recovery/backup commands | NEW module |
| 3 | **IPC contract module** (e.g. `control/registry_writer/ipc.py` or a shared `schemas/ipc.py`) | Wire protocol types, request/response schemas, error codes, serialization | NEW module |
| 4 | **Daemon config** (e.g. `config/registry-writer.yaml`) | Socket path, credential/token, workspace root, UID, max_connections, timeouts, backup paths | NEW config |
| 5 | **Daemon client** (e.g. `control/registry_writer/client.py`) | Client library that `execution_gate.py` and `orchestrator/runtime/store.py` use to communicate with the daemon; exposes `registry_write()`, `audit_append()`, `project_write()`, health check | NEW module |
| 6 | **Deployment/service files** | Systemd unit / supervisor config, launcher with isolated UID/workspace, health check script, backup/restore scripts | NEW deployment |
| 7 | **Tests** (under `tests/g10/` and `tests/control_plane/`) | Daemon unit, IPC integration, isolation, migration, recovery, fail-closed | NEW tests |
| 8 | **ADR addendum** (to `docs/adr/0002.md`) | Record the executed consequence-4 mechanism once applied | NEW addendum |
| 9 | **Residual update** (to `docs/phase-5/final/0002-g10-formal-residual-proof.md`) | Re-derive the residual for the three roots post-O3 | NEW addendum |

**Components NOT new:** the existing `state/helpers/*` and `audit/helpers/*` modules are **imported and reused** by the daemon (no rewrite). The existing `control/execution_gate.py` helper functions (`authorize_write`, `classify_target`, `_match_protected_root`) are **hosted inside the daemon** for defense-in-depth path validation — the daemon re-implements the same gate semantics (or imports the shared module if extracted).

---

## 4. Detailed definitions

### 4.1 Dedicated writer process

The daemon is a **single-process, single-threaded (or async event-loop) service** that owns the three roots. It:

- Binds a Unix domain socket (abstract or filesystem) at a configurable path, owner-only mode (`0600`).
- Accepts JSON-RPC-style request/response messages over the socket (NDJSON framing).
- Runs as a long-lived process managed by systemd / supervisor (restart on crash, health check probing).
- Has no external network listener by default (defense in depth: no network attack surface).
- Performs all writes through the existing `state/helpers/atomic_write` and `audit/helpers/append_log` + `integrity` modules — the helpers are imported directly, not forked. The daemon is a first-class Python process in the same project.

### 4.2 Isolated workspace/root

The daemon's three roots live **outside the session sandbox writable roots** (`workspaceRoot`, `/tmp`, `tmpdir()`). Either:

- **Option A (recommended):** Place the daemon roots under a dedicated directory outside `workspaceRoot` (e.g. `$DSH_HOME/registry-writer/`). The session sandbox denies writes to paths outside `workspaceRoot`, so no session tool (including `{zeko, cto}` raw `bash`/`write`/`edit`) can reach them. The daemon writes to these paths directly (it is not sandboxed, or runs under a different sandbox configuration).
- **Option B:** Place the daemon roots under `workspaceRoot` but owned by a **different UID/credential**. The daemon runs under that UID; the session sandbox is same-UID, but OS-level file permissions prevent the session from writing the daemon's files (the daemon sets `0700` on its roots). **Limitation:** a same-UID session with `bash` can `chmod` or `sudo` — Option B is weaker and requires a truly separate OS UID.

**Recommendation:** Option A (roots outside `workspaceRoot`) is the strongest isolation: it relies on the DSH sandbox's hard denial of out-of-workspace writes, which is code-enforced and cannot be bypassed by a session tool regardless of UID. The daemon process itself is not confined by the per-session sandbox (it is a standalone OS process).

**Root layout (daemon-owned):**

```
<daemon_root>/                    # e.g., /var/lib/dsh-registry-writer/
├── state/
│   ├── registry/
│   │   ├── delegations.json      # delegation doc (CAS-versioned)
│   │   └── revocations.json      # revocation list
│   └── projects/
│       └── multi-agent-harness.json  # project state doc (CAS-versioned)
├── audit/
│   └── multi-agent-harness/
│       ├── events.jsonl          # append-only audit ledger
│       └── events.jsonl.chain    # hash-chain sidecar
├── backup/                       # daemon-driven backup snapshots
└── daemon.pid                    # PID file
```

### 4.3 UID boundary

The daemon runs under a **dedicated OS user** (e.g. `dsh-writer`) with:

- Ownership of `<daemon_root>` and all contents.
- No write access to the DSH session workspace or the multi-agent-harness project directory (read-only or no access).
- No network access (except local Unix socket).
- The daemon's UID is different from the session's UID, so OS file permissions provide an additional barrier even if the daemon roots were inside the workspace (defense in depth).

**Minimum viable deployment (no separate UID):** If the same UID is unavoidable, the daemon roots MUST be placed outside `workspaceRoot` (Option A) — the sandbox boundary is the isolation mechanism. Same-UID with roots inside the workspace is **not sufficient** because `{zeko, cto}` raw `bash` can write any path the UID can write.

### 4.4 IPC contract

**Transport:** Unix domain socket (abstract namespace `@dsh-registry-writer` or filesystem path `<daemon_root>/ipc.sock`). Owner-only mode (`0600`). No TCP listener by default.

**Message format:** NDJSON (one JSON object per line), each object is a request or response. Framing: newline-delimited, no length prefix (audit-inspired lightweight protocol).

**Request schema:**

```json
{
  "v": 1,
  "id": "<client-generated-request-id>",
  "method": "registry_write | registry_read | audit_append | audit_read | audit_verify | project_write | project_read | health | backup | restore",
  "params": { ... },
  "auth": {
    "channel": "control_plane",
    "token": "<hmac-bearer-token>"
  }
}
```

**Response schema:**

```json
{
  "v": 1,
  "id": "<echoed-request-id>",
  "ok": true,
  "result": { ... }
}
```

On error:

```json
{
  "v": 1,
  "id": "<echoed-request-id>",
  "ok": false,
  "error": {
    "code": "WRITER_UNAVAILABLE | UNAUTHORIZED | FORBIDDEN | INVALID_REQUEST | INTERNAL_ERROR | CORRUPTION_DETECTED | RECOVERY_REQUIRED",
    "message": "human-readable detail"
  }
}
```

**Error codes:**

| Code | Meaning |
|---|---|
| `WRITER_UNAVAILABLE` | Daemon is down, starting up, or in recovery — caller must stop (fail-closed) |
| `UNAUTHORIZED` | Auth token missing or invalid |
| `FORBIDDEN` | Channel not authorized for this method/root |
| `INVALID_REQUEST` | Malformed request, schema violation, path traversal, bad version |
| `INTERNAL_ERROR` | Unexpected write failure, fsync error, disk full |
| `CORRUPTION_DETECTED` | Ledger/state integrity check failed (strict read / chain mismatch) |
| `RECOVERY_REQUIRED` | Daemon entered recovery mode — writes blocked until operator action |

### 4.5 Authentication / authorization

**Authentication (per-request):** HMAC-SHA256 bearer token (`Bearer <token>`) signed with a shared secret deployed with the daemon config. The token encodes:
- `channel`: the sanctioned writer identity (`control_plane`)
- `issued_at`: ISO timestamp (replay window)
- `nonce`: random nonce

The daemon validates the signature, expiry window (±30s clock skew), and extracts the channel identity.

**Authorization (per-method → root mapping):** Mirrors `SANCTIONED_ROOTS` with the extension to `state/projects/`:

| Method | Channel | Sanctioned root |
|---|---|---|
| `registry_write` | `control_plane` | `state/registry/**` |
| `registry_read` | `control_plane` | `state/registry/**` |
| `audit_append` | `control_plane` | `audit/**` |
| `audit_read` | `control_plane` | `audit/**` |
| `audit_verify` | `control_plane` | `audit/**` |
| `project_write` | `control_plane` | `state/projects/**` |
| `project_read` | `control_plane` | `state/projects/**` |
| `health` | any | none (no root access) |
| `backup` | `control_plane` | all roots (operator action) |
| `restore` | `control_plane` | all roots (operator action, Human-signed plan) |

**Defense in depth:** The daemon re-implements the same path-validation semantics as `execution_gate.py` (`classify_target`, `_match_protected_root`, traversal/symlink/prefix-confusion prevention) for every `_write` call. Even if the caller's path is malformed, the daemon refuses before any mutation.

### 4.6 Registry write API

**Method: `registry_write`**

**Params:**
```json
{
  "key": "delegations | revocations",
  "data": { ... },              // schema-validated JSON document
  "expected_version": 42,       // CAS version; 0 = initial write
  "authority_proof": "..."      // optional: delegation chain hash for provenance
}
```

**Semantics:**
- Validates `data` against `schemas/delegation.schema.json` (or `revocations` schema).
- Reads the current document at `<daemon_root>/state/registry/<key>.json` via `state/helpers/version_check.read_version`.
- CAS check: `current_version == expected_version`; fails with `INVALID_REQUEST` if stale.
- Strict monotonic: new version must be `expected_version + 1`.
- Atomic write via `state/helpers/atomic_write.atomic_write` (temp + fsync + replace; path guard against traversal).
- After write, emits an audit event through the daemon's own `audit_append` channel (self-audit).
- Returns `{"version": 43, "integrity": {"hash": "...", "updated_at": "..."}}`.

**Method: `registry_read`**

**Params:** `{"key": "delegations | revocations"}`

**Returns:** `{"data": {...}, "version": 42, "integrity": {"hash": "...", "verified": true}}`

### 4.7 Audit append API

**Method: `audit_append`**

**Params:**
```json
{
  "project": "multi-agent-harness",
  "event": { ... },             // conforms to schemas/audit-event.schema.json
  "idempotency_key": "event-000042"
}
```

**Semantics:**
- Validates the event is a dict with a non-empty `event_id` (mirrors `append_event` pre-check).
- Checks idempotency: if an event with the same `event_id` already exists in the ledger, returns success (idempotent ack, no duplicate line).
- Appends to `<daemon_root>/audit/<project>/events.jsonl` via `audit/helpers/append_log.append_event` (append, fsync).
- Updates the hash-chain sidecar via `audit/helpers/integrity.append_chained_event` (recomputes chain, persists sidecar).
- Returns `{"event_id": "event-000042", "integrity": {"line": 42, "chain_hash": "...", "cumulative_hash": "..."}}`.

**Method: `audit_read`**

**Params:** `{"project": "multi-agent-harness", "since_seq": 0}`

**Returns:** `{"events": [...], "count": 42, "chain_verified": true, "final_cumulative_hash": "..."}`

**Method: `audit_verify`**

**Params:** `{"project": "multi-agent-harness", "known_cumulative_hash": "...", "known_line_count": 42}`

**Returns:** `{"ok": true, "problems": []}`, or `{"ok": false, "problems": ["truncation detected: ..."]}`.

### 4.8 Project state write API

**Method: `project_write`**

**Params:**
```json
{
  "project": "multi-agent-harness",
  "data": { ... },              // conforms to schemas/project-state.schema.json
  "expected_version": 7
}
```

**Semantics:**
- Identical CAS semantics to `registry_write` (strict monotonic version, atomic write, self-audit).
- Writes to `<daemon_root>/state/projects/<project>.json`.
- Returns `{"version": 8, "integrity": {"hash": "...", "updated_at": "..."}}`.

**Method: `project_read`**

**Params:** `{"project": "multi-agent-harness"}`

**Returns:** `{"data": {...}, "version": 7, "integrity": {"hash": "...", "verified": true}}`

### 4.9 Health check

**Method: `health`**

**Params:** `{}` (or `{"name": "live" | "ready"}`)

**Returns:**
```json
{
  "status": "ok | degraded | down",
  "uptime_seconds": 12345,
  "roots": {
    "registry": {"ok": true, "version": 42, "last_integrity_check": "..."},
    "audit": {"ok": true, "events": 209, "chain_verified": true, "last_backup": "..."},
    "projects": {"ok": true, "version": 7, "last_integrity_check": "..."}
  },
  "last_backup": "2026-08-31T12:00:00Z",
  "version": "0.1.1-rc.2-o3"
}
```

**Liveness** (`health` without params): process is up and responding.
**Readiness** (`health?name=ready`): all three roots are writable, chains are verifiable, and daemon is not in recovery mode. A degraded root (corruption detected, disk full, backup failure) causes readiness to return `degraded` and write calls to that root are refused.

### 4.10 Fail-closed behavior

| Scenario | Behavior |
|---|---|
| Daemon down | `WRITER_UNAVAILABLE` error on every IPC call. The caller (orchestrator/control plane) **must NOT fall back to direct fs write** — it must stop/bloquear with a typed error. |
| Authn/authz failure | `UNAUTHORIZED` / `FORBIDDEN` — caller must stop. |
| Path traversal / cross-root | `INVALID_REQUEST` — daemon validates with gate semantics. |
| Root not writable | `INTERNAL_ERROR` — caller stops. |
| Corruption detected | `CORRUPTION_DETECTED` — daemon marks root degraded, refuses writes, caller stops. |
| Recovery required | `RECOVERY_REQUIRED` — daemon in recovery mode, writes blocked. |
| Partial write failure | Atomic write guarantees no partial state; if temp write fails, target file is unchanged. Caller receives `INTERNAL_ERROR` and can retry after re-reading. |
| Socket unavailable | Client connection refused → `WRITER_UNAVAILABLE`. |

**No silent fallback:** the daemon client in the control plane must never implement a "daemon down → write directly" fallback. That would defeat the isolation. The code path is: try daemon → on unavailable → RAISE (block the flow). This is consistent with the project's fail-closed posture (AUTH-INV-16, REC-001).

### 4.11 Startup / shutdown

**Startup sequence:**
1. Parse config (`config/registry-writer.yaml`): daemon root, socket path, token/secret, backup paths, UID drop.
2. If configured, drop privileges to `dsh-writer` user (if started as root).
3. Validate roots: ensure all three root directories exist and are writable. If a root is missing, create it with `0700` permissions.
4. Verify existing state/ledger integrity:
   - For each root, run `verify_chain` (for audit) or read and hash (for state/registry + projects).
   - If corruption detected → enter recovery mode (refuse writes, log, health degraded).
5. Recover event-id sequence: scan audit ledger for max `event-<n>` id, seed sequence from max.
6. Bind Unix socket, set `0600` permissions.
7. Start health check timer.
8. Mark ready (writes accepted).

**Shutdown sequence:**
1. Stop accepting new requests (unlink socket or mark not-ready).
2. Drain in-flight requests (graceful timeout, default 10s).
3. Flush and fsync all ledgers and state files.
4. Persist the final hash-chain sidecar for audit.
5. Unlink socket file.
6. Exit 0 (successful shutdown).

**Failure handling on startup:**
- If root directories cannot be created or are not writable → exit 1 (fail-closed, do not start in degraded mode).
- If corruption is detected → start in recovery mode (write methods return `RECOVERY_REQUIRED`; read methods still work; operator must restore from backup or mark corruption resolved via Human-signed command).
- If socket bind fails → exit 1 (port/file conflict).

### 4.12 Backup / restore

**Backup method: `backup`**

**Params:** `{"label": "pre-migration-v1"}` (optional operator label)

**Semantics:**
1. Acquire daemon-internal lock (no new writes during snapshot).
2. For each root, copy files to `<daemon_root>/backup/<label>/` (or a configurable backup path).
3. Compute and record SHA-256 of each file in a `MANIFEST.sha256`.
4. Record the cumulative hash of the audit ledger's last line.
5. Release lock.
6. Returns `{"backup_path": "...", "manifest": {...}, "timestamp": "..."}`.

**Restore method: `restore`**

**Params:** `{"backup_path": "...", "confirmed": true}` (requires `confirmed=true` to proceed)

**Semantics:**
1. Validate the backup: verify every file's SHA-256 against the manifest; verify audit chain continuity.
2. Stop accepting writes (mark not-ready).
3. Replace each root's files from the backup (atomic directory replace or per-file `os.replace`).
4. Re-verify all restored chains and documents.
5. Resume event-id sequence from the restored ledger's max event id.
6. Mark ready.
7. Returns `{"restored": true, "roots": {...}, "event_id_resumed": <seq>}`
8. If manifest verification fails → refuse restore (fail-closed, operator must inspect).

### 4.13 Corruption handling

- **Detection:** The daemon runs `verify_chain()` on the audit ledger on every read and on a periodic timer. For state documents (registry, projects), it reads and parses on every `read` call; a parse failure or version inconsistency is detected.
- **Response:** The daemon marks the affected root as `degraded`, returns `CORRUPTION_DETECTED` for write calls to that root, and continues serving other roots. The health endpoint reports the degraded root.
- **Recovery:** Operator action: identify the corruption extent, restore from backup (`restore` method), or truncate to the last verified chain point (Human-approved, only for append-only audit, never for registry/projects which are CAS-documents, not appendable). For registry/projects, only full restoration from backup or from the last verified version is safe.
- **Prevention:** Strict read on every write (the daemon validates before mutating); atomic writes (no partial state); hash chain on every append (tamper detection); version monotonicity (lost-update detection).

### 4.14 Replay / idempotency

| Mechanism | Scope |
|---|---|
| Client-generated request `id` | Every request; daemon dedupes by (`channel`, `id`) for read-only/idempotent methods. |
| `idempotency_key` on `audit_append` | The `event_id` of the event; if an event with that id already exists in the ledger, the daemon returns success (idempotent ack) without appending a duplicate line. |
| CAS version on `registry_write` / `project_write` | A replayed request with the same `expected_version` will fail because the version was already bumped (the replayed request sees `expected_version != current_version`). This is the correct behavior: a replay of a successful write is idempotent at the application level (the first write already bumped the version; the replay sees stale version and is rejected). |
| `event_id` uniqueness (audit) | The daemon's own `event_id` allocation is monotonic; a replayed audit event with a duplicate `event_id` is idempotently acknowledged. |
| Token replay window | Auth token carries `issued_at` ±30s; a replayed token outside the window is rejected. |

### 4.15 Migration path

The migration from direct-write to daemon-isolated writes proceeds in three phases.

**Phase A — Prepare (daemon deployed alongside, no write-path change):**
1. Deploy daemon binary/service, config, UID, root directories.
2. Copy existing data: `state/registry/` → `<daemon_root>/state/registry/`, `state/projects/` → `<daemon_root>/state/projects/`, `audit/` → `<daemon_root>/audit/`.
3. Verify copied data against originals (SHA-256).
4. Verify daemon reads return identical data to direct reads.
5. Run daemon in shadow mode (reads only, writes not yet routed).
6. Verify health check, authn, fail-closed responses.

**Phase B — Switch (write path flipped to daemon IPC):**
1. Update `control/execution_gate.py`: `registry_write()` → daemon client call; `audit_append()` → daemon client call.
2. Update `orchestrator/runtime/store.py`: `RuntimeStore.persist()` → daemon client `project_write()`.
3. Update `orchestrator/runtime/store.py` `ensure_state()` → daemon client `project_write()` (bootstrap).
4. Update `orchestrator/runtime/delegation.py` `FileDelegationProvider.current()` → daemon client `registry_read()`.
5. Update `RuntimeAudit.emit()` → already uses `audit_append()` (which is now a daemon client call).
6. Remove direct-write code paths from the execution gate (or make them conditional on a "daemon unavailable" fail-closed stop, never a fallback).
7. **Critical:** the `write_through()` function for non-protected paths (ordinary workspace writes) stays unchanged — only the three daemon-owner roots route through IPC.

**Phase C — Verify (proof of isolation):**
1. Verify that `state/registry/`, `state/projects/`, `audit/` are removed from the session workspace root (or file permissions deny session UID).
2. Run `test_raw_write_reaches_protected_path_unintercepted` against the new layout: the raw write MUST now be **denied** by the sandbox (target outside writable roots) or by OS permissions. The test is re-derived: it probes the old location and expects **DENY**.
3. Run the full G10 test suite (49 + O5 + O3-planning tests).
4. Re-derive the residual statement (see `0002-o3-g10-closure-determination.md`).
5. Run the full Phase-5 regression (validate-config + all deterministic suites).

**Read path note:** The existing `FileDelegationProvider` and `RuntimeStore.load_project_state` use `safe_read` with absolute paths under the workspace base. During migration, these reads must switch to daemon IPC (`registry_read`, `project_read`, `audit_read`). The daemon provides a read API that returns the current document + version + integrity. Alternatively, the daemon can offer a read-only mirror at a predictable path inside the workspace (for backward compatibility of read-only operations). **Recommended:** use daemon IPC for reads too — it ensures the reader always gets the canonical version (with integrity verification) and never reads a stale in-workspace copy.

### 4.16 Rollback plan

Restore the pre-O3 state (direct-write path). **Reversibility: MEDIUM** — because the write path is the most sensitive surface.

1. Stop the daemon, disable its service unit.
2. Restore `control/execution_gate.py` registry/audit channels to direct-write behavior from the pre-change backup.
3. Restore `orchestrator/runtime/{store,delegation}.py` to direct-read/write.
4. Restore `state/registry/`, `state/projects/`, `audit/` to the session workspace (or restore file permissions if UID was changed).
5. Verify the audit chain + hash sidecar + CAS versions are intact (migration continuity check).
6. Reload/restart the affected orchestrator processes.
7. Run validate-config + full G10 test suite (assertions for the pre-O3 actor set `{zeko, cto}`).
8. Audit the rollback event.

**Rollback precondition:** pre-change backups of the five files that changed in Phase B (execution_gate.py, audit.py, store.py, delegation.py, and the daemon config) must exist with recorded SHA-256.

### 4.17 Threat model (summary)

See `0003-o3-threat-model.md` for the full threat model. Key threats:

| # | Threat | Mitigation |
|---|---|---|
| T1 | Session actor impersonates the control plane and drives the daemon to write a forged registry entry | HMAC authn token (shared secret, per-request) + channel identity + path scoping; daemon validates every write against the sanctioned root |
| T2 | Replay of a captured IPC request | Request id + idempotency key; CAS version prevents replay of state writes; event_id uniqueness prevents duplicate audit entries |
| T3 | Path traversal through IPC to escape the daemon's root | Daemon re-implements `classify_target` + `_match_protected_root` with traversal/symlink/prefix-confusion prevention |
| T4 | Daemon compromise (attacker gains the daemon's UID/process) | The daemon is a single point of authority-source compromise — the risk is explicitly accepted (same as direct-write V1, where the orchestrator process was the single point). Mitigate: least-privilege UID, no network, audit every write, monitor for anomalous writes, key rotation. |
| T5 | Daemon unavailable → orchestrator writes blocked | Fail-closed by design; this is an availability tradeoff (not a security regression). Mitigate: health checks, restart policy, alerting. |
| T6 | Migration race: dual-writer window during cutover | Stop writes, flip the path under lock, verify single-writer. |
| T7 | Backup tampering | Manifest SHA-256 verification before restore; chain verification after restore. |
| T8 | Chain sidecar forgery (no signing key) | Same residual as today: detection, not prevention. The daemon does not worsen the residual. An external cryptographic marker (e.g., append-only log sent to an external service) is a future option. |

### 4.18 Acceptance tests (summary)

See `0004-o3-acceptance-test-spec.md` for the full specification. Key test categories:

1. **Daemon unit tests** — single-writer enforcement, path scoping, schema validation, authn authz, portal, CAS version, strict monotonicity, fail-closed, health checks, idempotency.
2. **IPC integration tests** — client-server round-trip, error mapping, timeouts, authn failure, authz failure, replay detection.
3. **Isolation tests** — raw write to daemon-owned roots from session process is DENIED (sandbox or permissions); residual probe re-derived.
4. **Migration tests** — continuity of existing data, event-id sequence across migration, chain integrity.
5. **Recovery tests** — daemon restart with intact ledger; daemon restart with corrupted ledger (fail-closed); backup verification; restore verification.
6. **Fail-closed tests** — daemon unavailable → writes BLOCKED (no silent fallback); non-sanctioned channel → FORBIDDEN; cross-root → FORBIDDEN.
7. **Honesty guards** — no test may claim G10 closed after O3 unless the closure conditions (0002) are satisfied; the residual must be re-derived and stated precisely.

---

## 5. Control-flow impact (exact, as designed)

| Component | Before O3 | After O3 (design) |
|---|---|---|
| `execution_gate.registry_write()` | Direct `atomic_write` | Daemon client → daemon `registry_write` |
| `execution_gate.audit_append()` | Direct `append_log.append_event` | Daemon client → daemon `audit_append` |
| `execution_gate.write_through()` | Direct `atomic_write` (for non-protected paths) | **Unchanged** — only the three daemon-owned roots change |
| `RuntimeStore.persist()` | `write_through("write", ...)` → `atomic_write` | Daemon client → daemon `project_write` |
| `RuntimeStore.ensure_state()` | `write_through("write", ...)` → `atomic_write` | Daemon client → daemon `project_write` |
| `RuntimeStore.load_project_state()` | `safe_read` (direct) | Daemon client → daemon `project_read` |
| `FileDelegationProvider.current()` | `safe_read` (direct) | Daemon client → daemon `registry_read` |
| `RuntimeAudit.emit()` | `audit_append()` → `append_event` | `audit_append()` → daemon client → `audit_append` (unchanged API, implementation now daemon-backed) |
| `audit_append()` | Imported from `execution_gate` | Imported from daemon client (same public API) |
| `read_events_strict` / `verify_chain` | Direct file read | Daemon client → daemon read API (or direct if daemon permits read-only mirror) |

**NOT changed:** `control/authority.py`, `control/delegation.py`, `orchestrator/foundation/`, `orchestrator/dsh/`, `orchestrator/execution/`, `state/helpers/*` (reused by daemon), `audit/helpers/*` (reused by daemon), role toolFilter, session policy, DSH core.

---

## 6. Honesty statement

1. **O3 is NOT implemented.** This package is a design/migration/threat-model specification. No daemon code was written; no `control/*`, `orchestrator/*`, `state/*`, `audit/*` file was modified; no DSH core, profile, preset, session policy, or role capability was changed.
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. O3 is the strongest available project-layer closure arm, but it requires implementation, deployment, verification, and Human approval of the scope extension to `state/projects/**` (see `0002-o3-g10-closure-determination.md`).
3. **The scope extension to `state/projects/**` is a design decision** that goes beyond the ADR 0002 consequence 4 description (which only mentions registry/audit). It is necessary for O3 to fully cover the G10 residual. The package documents this extension explicitly; it is not assumed or hidden.
4. **Authority semantics are unchanged.** The daemon is an execution proxy under the same single-writer contract (ADR 0002 Option B). The control plane still makes all authority decisions; the daemon authenticates and path-scopes every request.
5. **Rollback is file-level (no git repository).** The project has no git repository; rollback must be file-level backups.
6. **No test failure was hidden or downgraded.** The planning tests in `tests/g10/o3-planning/` assert only the package's honesty (documents exist, required topics covered, affirm no closure claim, no implementation applied). They do not modify any test or config.

---

## 7. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/o3/0001-o3-implementation-package.md` (this file) + `0002-o3-g10-closure-determination.md` + `0003-o3-threat-model.md` + `0004-o3-acceptance-test-spec.md` + `tests/g10/o3-planning/test_o3_planning.py`.

**NOT modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/` — unchanged), and all other `docs/`. No daemon implemented. No control-plane code modified. No role-boundary change applied. No closure of G10 claimed. No production deployment started.

---

*Status: IMPLEMENTATION PACKAGE (Session D). O3 designed but NOT implemented. G10 remains OPEN / BLOCKING for production. O3 = hard-isolation arm for the three G10 residual roots (state/registry/**, audit/**, state/projects/**) via a dedicated out-of-process writer with isolated workspace root and UID, IPC contract with authn/authz, fail-closed, and a migration path from direct-write to daemon-write. Authority semantics unchanged. No closure of prevention claimed.*
# G10 O3 — FINAL ARCHITECTURE PACKAGE (Design Only, NOT Implemented)

- **Milestone**: Phase 5 / Session F — G10 O3 FINAL ARCHITECTURE PACKAGE
- **Status**: FINAL ARCHITECTURE — the authoritative consolidated O3 design. **O3 is NOT implemented.** Daemon code is NOT written. `control/*`, `orchestrator/*`, `state/*`, `audit/*`, DSH core, session policy, role capabilities, and live composition are **unchanged**. **O3 alone does NOT close G10 — G10 remains OPEN / BLOCKING** (see `0002-o3-final-closure-determination.md`).
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (raw-write actor set `{zeko, cto}`)
- **Write-only scope**: `docs/phase-5/security/g10/o3/` + `tests/g10/o3-planning/`. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim.**
- **Supersedes as the authoritative O3 design**: `docs/phase-5/security/g10/o3/0001-o3-implementation-package.md` (Session D package — the historical design record). The Session D package remains the planning artifact; **this FINAL package is the single authoritative O3 architecture reference** and the companion to `0002-o3-final-closure-determination.md`, `0003-o3-final-threat-model.md`, `0004-o3-final-acceptance-test-spec.md` (all under `final/`).
- **Companion**: `0002-o3-final-closure-determination.md` · `0003-o3-final-threat-model.md` · `0004-o3-final-acceptance-test-spec.md` · `docs/phase-5/security/g10/o3/0001..0004` (Session D package) · `docs/phase-5/security/g10/implementation/0001-o5-o3-implementation-plan.md` (plan) · `0002-o5-application-record.md` (O5 applied) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (decision record) · `docs/phase-5/final/0002-g10-formal-residual-proof.md` (R) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5) · `docs/adr/0002-registry-protection-mechanism.md` (consequence 4) · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py` · `state/helpers/*` · `audit/helpers/*` · `schemas/*`.

---

## 1. Purpose of this FINAL package

The Session D package (`0001..0004`) produced a complete O3 design. This FINAL package:

1. **Consolidates** the Session D design into a single authoritative architecture reference.
2. **Finalizes** twelve topics as **decisions** (not options): isolated writer root, separate UID/process, IPC, authentication/authorization, registry/audit/project-state API, fail-closed behavior, startup/shutdown, backup/restore, migration, rollback, threat model, acceptance tests.
3. **Resolves design tensions** left open in the Session D package (see §2.6 — cross-UID IPC, §4.4 — read path, §4.5 — credential provisioning).
4. **Determines explicitly** whether O3 closes each of the three G10 residual roots (`state/registry/**`, `audit/**`, `state/projects/**`) — see `0002-o3-final-closure-determination.md`.

Nothing in this FINAL package implements the daemon, modifies `control/orchestrator/state/audit`, modifies DSH core or session policy, or claims G10 closure.

---

## 2. Current state (re-verified this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` |
| Sandbox | **per-session**, not per-agent; `workspace-write` writable roots = `[workspaceRoot, '/tmp', tmpdir()]` | `roots.ts:52–55`; `child-agent.ts:177–204` |
| toolFilter | **tool-name-level only**, never path-level | `tools/index.ts:680–690` |
| Raw-write actor set | `{zeko, cto}` (post-O5: somad/nova stripped of `write`/`edit`; actor set shrunk from `{zeko,cto,somad,nova}`) | `0002-o5-application-record.md`; `config/role-preset-mapping.yaml` |
| Protected paths (gate) | `state/registry/**`, `audit/**` (`PROTECTED_REL_ROOTS`). **`state/projects/**` is ALLOWED at the gate** (CAS-detected post-hoc, not gate-DENIED) | `execution_gate.py:57`; Session C assessment §2.3 |
| Sanctioned channels | `registry_write()` → `state/registry/**` only; `audit_append()` → `audit/**` only (`SANCTIONED_ROOTS`) | `execution_gate.py:69–72` |
| Registry write path | `execution_gate.registry_write()` → `atomic_write` (sanctioned, single-writer) | `execution_gate.py:282–290` |
| Audit append path | `execution_gate.audit_append()` → `append_event` (sanctioned, append-only, fsync) | `execution_gate.py:293–305` |
| Project state write path | `RuntimeStore.persist()` / `ensure_state()` → `write_through("write", ...)` → `atomic_write` (CAS version check, not gate-DENIED) | `store.py:103–144` |
| Detection stack | Append-only ledger + hash-chain sidecar + cumulative SHA-256 + CAS/version monotonicity | `audit/helpers/{append_log,integrity}.py`; `state/helpers/{atomic_write,version_check}.py` |
| Delegation reads | `FileDelegationProvider.current()` → `safe_read` (`state/registry/delegations.json` + `revocations.json`) | `delegation.py:53–87` |
| VCS | **No git repository** — rollback is file-level backups | `git status` → `fatal: not a git repository` |
| G10 status | **OPEN / BLOCKING** for production; residual accepted (V1, containment = detection) | closure matrix §1; residual proof §1 |
| O3 status | **NOT IMPLEMENTED (HOLD)** — this FINAL package is the design | this document |

**The residual R (post-O5, unchanged):** a raw-write-capable role (`{zeko, cto}`) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. The L1 execution gate intercepts only channeled writes. DSH provides no per-path or per-agent interception. **Prevention: ABSENT at the DSH layer. Containment: DETECTION at the project layer** (L1 gate + append-only + cumulative hash chain + CAS). **G10 stays OPEN / BLOCKING for production.**

### 2.1 Per-root protection today (the three G10 residual roots)

| Root | Gate classification (V1) | Raw-tool bypass (R) | Protection mechanism today |
|---|---|---|---|
| `state/registry/**` | **DENIED** (protected) for channeled writes | OPEN (not intercepted) | L1 gate + CAS + audit |
| `audit/**` | **DENIED** (protected) for channeled writes | OPEN (not intercepted) | L1 gate + append-only + hash chain |
| `state/projects/**` | **ALLOWED** (not protected) — CAS-detected post-hoc | OPEN (not intercepted) | CAS/version monotonicity only |

This asymmetry is why O3's **scope extension to `state/projects/**`** is a design decision, and why it is the only non-DSH arm that gives `state/projects/**` hard isolation (Session C §2.3 precision; `0002-o3-final-closure-determination.md` §3).

---

## 3. O3 objective and final design principles

**Objective (final):** hard-isolate the authority source (`state/registry/**`) and the append-only audit trail (`audit/**`) from the shared session sandbox so that **no raw DSH tool call, even from `{zeko, cto}`, can reach them**; extend the same isolation to `state/projects/**` (the project state document) so all three G10 residual roots are covered. The writer is a **dedicated out-of-process daemon** that is the **sole writer** of the three roots.

**Final design principles (binding):**

1. **Out-of-process, out-of-workspace writer.** A dedicated process owns the three roots. The roots live **outside the session sandbox writable set** (Option A, mandatory) AND the daemon runs under a **dedicated OS UID** (Option B, mandatory as defense-in-depth). **A+B together is the final decision.** Option B alone is explicitly insufficient (a same-UID session `bash` can `chmod`); Option A alone leaves the daemon process in the shared UID namespace. Both together give two independent barriers: the sandbox boundary (code-enforced) and OS file permissions (kernel-enforced).
2. **Fail-closed.** Daemon unavailable, degraded, or in recovery → every write to the three roots is **BLOCKED** with a typed error. **No silent fallback** to direct write — a fallback is a design violation and restores the residual. Elevated to a hard code-level invariant (§4.8).
3. **No DSH modification.** The daemon is a project-layer process (ADR 0002 consequence 4). DSH core, session policy, role toolFilter, and role capabilities are untouched.
4. **Preserve the detection stack.** The daemon reuses `audit/helpers/*` and `state/helpers/*` (append-only, hash chain, CAS, atomic write) — importable modules; no semantic change to integrity/safety logic.
5. **Authority semantics unchanged.** The daemon is an **execution proxy** under the same single-writer contract (ADR 0002 Option B). Control-plane authority decisions (delegation scoping + execution gate) are preserved; the daemon authenticates and path-scopes every request; it never grants or scopes authority.
6. **Scope extension to `state/projects/**`.** O3 covers all three G10 residual roots. This is an explicit design extension beyond the ADR 0002 consequence 4 description (registry/audit only) and is **necessary** for O3 to fully address the G10 residual (`0002-o3-final-closure-determination.md`).

---

## 4. FINAL component specification (topics finalized)

### 4.1 Isolated writer root (FINALIZED — decision, not option)

**Decision: the daemon's three roots live OUTSIDE `workspaceRoot` (Option A) AND the daemon runs under a dedicated UID (Option B). Both are mandatory.**

- The roots are placed under a dedicated, daemon-owned tree, e.g. `/var/lib/dsh-registry-writer/` (configurable in `config/registry-writer.yaml`). This path is **not** inside the session workspace root, so the DSH sandbox (`writableRoots() = [workspaceRoot, '/tmp', tmpdir()]`) **hard-denies** every session tool write — channeled or raw — to any path in the tree. This is DSH-sandbox-enforced prevention, the strongest available without DSH change.
- **No daemon root may ever live inside `workspaceRoot`** under any configuration. If an operator must use an in-workspace layout, that is NOT O3 (it is the weaker O2-style partial mitigation) and no closure claim may be made.

**Root layout (daemon-owned, mode `0700` on directories, `0600` on files):**

```
/var/lib/dsh-registry-writer/          # daemon root (dsh-writer:dsh-writer, 0700)
├── state/
│   ├── registry/
│   │   ├── delegations.json           # delegation doc (CAS-versioned)
│   │   └── revocations.json           # revocation list (CAS-versioned)
│   └── projects/
│       └── multi-agent-harness.json   # project state doc (CAS-versioned)
├── audit/
│   └── multi-agent-harness/
│       ├── events.jsonl               # append-only audit ledger
│       └── events.jsonl.chain         # hash-chain sidecar
├── backup/                            # daemon-driven backup snapshots
├── ipc.sock                           # Unix domain socket (group-writable, see §4.3)
└── daemon.pid                         # PID file
```

**Finalized decision on the read path (§4.4):** **no read-only mirror inside the workspace.** All reads route through daemon IPC. A read-only mirror inside the workspace would reintroduce a non-authoritative, session-writable surface that readers could be tricked into trusting (a raw actor could poison the mirror; a reader would read forged data while the daemon holds the canonical copy). The canonical read is the daemon's.

### 4.2 Separate UID / process (FINALIZED)

- **Dedicated OS user `dsh-writer`** owns `/var/lib/dsh-registry-writer/` and all contents (mode `0700`/`0600`).
- The daemon process runs **as `dsh-writer`** (systemd `User=dsh-writer`; if started as root, it drops privileges after reading config and binding the socket).
- The `dsh-writer` user has:
  - **No** write access to the session workspace or the multi-agent-harness project tree (read-only or no access).
  - **No** network listener (Unix-socket only); no outbound network by policy (systemd `PrivateNetwork=yes` where supported).
  - Resource limits (open files, memory) via systemd `LimitNOFILE` / `MemoryMax`.
- **Process lifecycle:** systemd unit `dsh-registry-writer.service` with `Restart=always`, `RestartSec=2s`; readiness probed via the `health` method (§4.7); ordering so the daemon is `After=` and up+ready **before** the orchestrator session begins delegations (cold-start ordering, §4.9).
- The **control plane** (orchestrator runtime) runs under the session user and reaches the daemon **only via IPC** with a shared-secret HMAC token (§4.5). It has **no** direct filesystem access to the daemon roots.

### 4.3 IPC contract (FINALIZED — including the cross-UID socket decision)

**Transport: Unix domain socket.** A filesystem socket at `<daemon_root>/ipc.sock` (abstract namespace `@dsh-registry-writer` is an acceptable alternative where filesystem sockets are unavailable).

**Cross-UID connectivity — FINALIZED decision (resolves a Session D tension).** The Session D package said "owner-only mode (`0600`)". That is **incompatible with a dedicated-UUID daemon + a different-UID control plane**: a `0600` socket owned by `dsh-writer` would also block the legitimate orchestrator. **Final decision:**

- The socket is owned by `dsh-writer` and **group-owned by a shared control-plane group** (e.g. `dsh`), mode **`0660`** — only members of the `dsh` group may `connect()`.
- **The socket permission is defense-in-depth, NOT the authentication mechanism.** The **primary authentication is the per-request HMAC bearer token** (§4.5). The daemon treats an unknown/absent token as `UNAUTHORIZED` regardless of who connected. A session actor in the workspace is **not** in the `dsh` group and has **no** access to the shared secret, so both barriers must be defeated to drive the daemon.
- No TCP listener by default; `PrivateNetwork=yes`; connection/request limits and payload caps (§4.10).

**Message format: NDJSON** (one JSON object per line, newline-delimited). Protocol version `v: 1`.

**Request schema (final):**

```json
{
  "v": 1,
  "id": "<client-generated-request-id>",
  "method": "registry_write | registry_read | audit_append | audit_read | audit_verify | project_write | project_read | health | backup | restore",
  "params": { ... },
  "auth": {
    "channel": "control_plane",
    "token": "<hmac-bearer-token>",
    "issued_at": "2026-08-31T12:00:00Z",
    "nonce": "<random-nonce>"
  }
}
```

**Response schema (final):** success `{v, id, ok: true, result}`; failure `{v, id, ok: false, error: {code, message}}`.

**Error codes (final):**

| Code | Meaning |
|---|---|
| `WRITER_UNAVAILABLE` | Daemon down, starting up, or in recovery — caller must stop (fail-closed) |
| `UNAUTHORIZED` | Auth token missing, invalid, expired, or outside replay window |
| `FORBIDDEN` | Channel/credential not authorized for this method/root |
| `INVALID_REQUEST` | Malformed request, schema violation, path traversal, bad version, non-monotonic CAS |
| `INTERNAL_ERROR` | Unexpected write failure, fsync error, disk full |
| `CORRUPTION_DETECTED` | Ledger/state integrity check failed (strict read / chain mismatch) |
| `RECOVERY_REQUIRED` | Daemon in recovery mode — writes blocked until operator action |

### 4.4 Authentication / authorization (FINALIZED)

**Authentication (per-request, primary gate):** HMAC-SHA256 bearer token over a canonical request signature, signed with a shared secret deployed with the daemon config. The token/request carries:

- `channel`: the sanctioned writer identity (`control_plane`).
- `issued_at`: ISO timestamp — replay window **±30s**; outside it → `UNAUTHORIZED`.
- `nonce`: random per-request nonce; the daemon rejects a replayed (`channel`, `nonce`, `id`) triple.

The daemon validates signature, window, and nonce on **every** request, then extracts the channel identity for authorization. Signature is over `method || id || issued_at || nonce || canonical-params`.

**Authorization (per-method → root mapping, final — mirrors `SANCTIONED_ROOTS` + the projects extension):**

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
| `backup` | `control_plane` (operator) | all roots (operator action) |
| `restore` | `control_plane` (operator, Human-signed plan) | all roots (operator action) |

**Credential provisioning (FINALIZED):** the shared secret is provisioned to **exactly two principals** — the daemon process and the control-plane client — via a `0600` file outside the session workspace (or environment at process start), readable only by `dsh-writer` and the control-plane user/group. **The secret never appears inside the session workspace** (session tools, including `{zeko, cto}`, must never be able to read it). Rotation procedure: generate a new secret, deploy to both principals under a version tag, keep the prior secret valid for one rotation window, then revoke.

**Defense in depth:** the daemon re-implements the same path-validation semantics as `execution_gate.py` (`normalize_target`, `classify_target`, `_match_protected_root` — traversal/symlink/absolute-outside/prefix-confusion prevention) for every `_write` call, before any mutation. Cross-root targets and non-protected targets for a sanctioned method are `FORBIDDEN`.

### 4.5 Registry / audit / project-state API (FINALIZED)

**`registry_write`** — params `{key: "delegations"|"revocations", data, expected_version, authority_proof?}`.
Semantics: schema-validate `data` (`schemas/delegation.schema.json` or revocations schema); read current doc via `state/helpers/version_check.read_version`; CAS check `current_version == expected_version` (stale → `INVALID_REQUEST`); **strict monotonic** — new version must equal `expected_version + 1` (else `INVALID_REQUEST`); atomic write via `state/helpers/atomic_write.atomic_write` (temp + fsync + replace; path guard); self-audit through the daemon's own `audit_append` channel. Returns `{version, integrity: {hash, updated_at}}`.

**`registry_read`** — params `{key}`. Returns `{data, version, integrity: {hash, verified}}`.

**`audit_append`** — params `{project, event, idempotency_key}`.
Semantics: validate `event` is a dict with a non-empty `event_id` (mirrors `append_event` pre-check); **idempotent** — an existing `event_id` returns success without a duplicate line; append to `<daemon_root>/audit/<project>/events.jsonl` via `audit/helpers/append_log.append_event` (append + fsync); update the hash-chain sidecar via `audit/helpers/integrity.append_chained_event`. Returns `{event_id, integrity: {line, chain_hash, cumulative_hash}}`.

**`audit_read`** — params `{project, since_seq}`. Returns `{events, count, chain_verified, final_cumulative_hash}`.

**`audit_verify`** — params `{project, known_cumulative_hash, known_line_count}`. Returns `{ok, problems}`; any truncation/duplicate/chain break is reported.

**`project_write`** — params `{project, data, expected_version}`. Identical CAS semantics to `registry_write` (strict monotonic, atomic write, self-audit). Writes `<daemon_root>/state/projects/<project>.json`. Returns `{version, integrity}`.

**`project_read`** — params `{project}`. Returns `{data, version, integrity: {hash, verified}}`.

**Self-audit:** every daemon mutation (registry/project write, backup, restore) emits an audit event through the daemon's own append channel — the daemon is itself audited (threat model T4 mitigation).

### 4.6 Health check / readiness (FINALIZED)

**`health`** (no params) — liveness: process up and responding. Returns `{status: "ok"|"degraded"|"down", uptime_seconds, roots: {registry, audit, projects}, last_backup, version}`.

**`health?name=ready`** — readiness: all three roots writable, chains verifiable, daemon not in recovery. **A degraded root (corruption detected, disk full, backup failure) ⇒ `degraded`, and write calls to that root are refused** (`CORRUPTION_DETECTED`/`RECOVERY_REQUIRED`). This couples readiness to write refusal — the fail-closed contract (§4.8).

### 4.7 Fail-closed behavior (FINALIZED — hard invariant)

| Scenario | Behavior |
|---|---|
| Daemon down / starting / in recovery | `WRITER_UNAVAILABLE` on every IPC call. The caller **must not** fall back to direct fs write — it stops/blocks with a typed error. |
| Authn/authz failure | `UNAUTHORIZED` / `FORBIDDEN` — caller stops. |
| Path traversal / cross-root / non-monotonic CAS | `INVALID_REQUEST` / `FORBIDDEN` — daemon validates with gate semantics before any mutation. |
| Root not writable / disk full / fsync failure | `INTERNAL_ERROR` — caller stops. |
| Corruption detected | `CORRUPTION_DETECTED` — daemon marks the root degraded, refuses writes to it, continues serving other roots. |
| Recovery required | `RECOVERY_REQUIRED` — daemon in recovery mode; writes blocked until operator action. |
| Partial write failure | Atomic write guarantees no partial state; target file unchanged on temp-write failure; caller receives `INTERNAL_ERROR` and may retry after re-reading. |
| Socket unavailable / timeout / overload | Connection refused or typed error; `WRITER_UNAVAILABLE` / `INTERNAL_ERROR`; no partial write. |

**Hard invariant (elevated):** the daemon client in the control plane **must not** implement a "daemon down → write directly" fallback. After migration Phase B (§4.10), **no direct-fs write path to the three roots remains reachable in the control plane** — the switch is complete, not conditional. This is enforced by an acceptance test that statically greps the control-plane write paths (see `0004` §2.6, O3-FC-005). Consistent with the project's fail-closed posture (AUTH-INV-16, REC-001).

### 4.8 Startup / shutdown (FINALIZED)

**Startup sequence:**
1. Parse config (`config/registry-writer.yaml`): daemon root, socket path, shared-secret location, backup paths, UID drop, limits.
2. If started as root, drop privileges to `dsh-writer`.
3. Validate roots: create missing root directories with `0700`, owner `dsh-writer`. **If a root cannot be created or is not writable → exit 1 (fail-closed; do not start in degraded mode).**
4. Verify existing integrity: `verify_chain` for audit; read+hash for registry/projects. **If corruption → enter recovery mode** (writes refuse `RECOVERY_REQUIRED`; reads still work; operator must restore or mark resolved via a Human-signed command).
5. Seed event-id sequence from the ledger's max `event-<n>` id.
6. Bind socket, set ownership/group/mode (`0660`), validate group membership.
7. Start health/readiness timer.
8. Mark ready (writes accepted).

**Shutdown sequence:**
1. Stop accepting new requests (unlink socket or mark not-ready).
2. Drain in-flight requests (graceful timeout, default 10s; force-close after).
3. Flush + fsync all ledgers and state files.
4. Persist the final hash-chain sidecar.
5. Unlink the socket file.
6. Exit 0 (successful shutdown).

**Failure handling:** root not writable / socket bind conflict → exit 1. Corruption at startup → recovery mode (writes blocked, reads served). **Cold-start ordering:** systemd `After=multi-user.target`, and the orchestrator session start-up must verify daemon readiness (`health?name=ready`) before it begins delegations — a not-ready daemon blocks the affected writes (fail-closed), never falls back.

### 4.9 Backup / restore (FINALIZED)

**`backup`** — params `{label?}`. Semantics:
1. Acquire the daemon-internal lock (no new writes during the snapshot).
2. Copy each root's files to `<daemon_root>/backup/<label>/` (configurable backup path).
3. Write a `MANIFEST.sha256` (per-file SHA-256) and record the audit ledger's last cumulative hash.
4. Release the lock.
5. Returns `{backup_path, manifest, timestamp}`.

**`restore`** — params `{backup_path, confirmed: true}` (must be `confirmed=true`). Semantics:
1. **Verify the backup** — every file's SHA-256 against the manifest; verify audit chain continuity. **If manifest verification fails → refuse restore (fail-closed)** — a tampered/forged backup is never applied.
2. Stop accepting writes (mark not-ready).
3. Replace each root's files from the backup (per-file `os.replace`; atomic within a root).
4. Re-verify all restored chains and documents.
5. Resume event-id sequence from the restored ledger's max id.
6. Mark ready.
7. Returns `{restored, roots, event_id_resumed}`.

**Corruption handling:** detection via `verify_chain()` on every audit read + periodic timer; parse/version checks on every state read. A corrupted root → `degraded` + `CORRUPTION_DETECTED` for writes to that root; other roots continue. Recovery is operator action: restore from backup, or truncate to the last verified chain point (**append-only audit only** — registry/projects are CAS documents, never truncatable; only full restore from backup or from the last verified version is safe).

### 4.10 Migration path (FINALIZED — three phases, read path switched)

**Phase A — Prepare (daemon deployed alongside; no write-path change):**
1. Deploy the daemon service, config, UID, root tree.
2. Copy `state/registry/` → `<daemon_root>/state/registry/`, `state/projects/` → `<daemon_root>/state/projects/`, `audit/` → `<daemon_root>/audit/`.
3. Verify copied data SHA-256-identical to originals.
4. Verify daemon reads return data identical to direct reads.
5. Run the daemon in **shadow mode** (reads only; writes not yet routed).
6. Verify health, authn, fail-closed responses.

**Phase B — Switch (write + read paths flipped to daemon IPC), under a freeze window:**
1. **Freeze window:** stop writes to the three roots (pause delegation/state mutation), flip the paths under lock, verify single-writer, then resume. No window where both paths write the same root (threat model T6).
2. Update `control/execution_gate.py`: `registry_write()` → daemon client; `audit_append()` → daemon client. **Remove the direct-write code paths** — not conditional, removed (fail-closed invariant).
3. Update `orchestrator/runtime/store.py`: `RuntimeStore.persist()` and `ensure_state()` → daemon client `project_write()`; `load_project_state()` → daemon client `project_read()`.
4. Update `orchestrator/runtime/delegation.py`: `FileDelegationProvider.current()` → daemon client `registry_read()`.
5. Update `orchestrator/runtime/audit.py`: `RuntimeAudit.emit()` already routes through `audit_append()` (now daemon-backed); audit reads → daemon `audit_read`/`audit_verify`.
6. **`write_through()` for non-protected workspace paths stays unchanged** — only the three daemon-owned roots route through IPC.
7. **No in-workspace mirror** (§4.1): after Phase B, `state/registry/`, `state/projects/`, `audit/` are **removed from the session workspace** (or, where removal is impossible, left as empty stubs owned by `dsh-writer` with the session UID denied).

**Phase C — Verify (proof of isolation):**
1. Verify the three roots are absent from the session workspace root (or session-UID-denied).
2. Re-derive the isolation probe `test_raw_write_reaches_protected_path_unintercepted`: the raw write to the **old** locations must now be **DENIED** by the sandbox/OS boundary. O3-ISO-001..004 (acceptance spec) assert the denial.
3. Run the full G10 suite + the O3 acceptance suite (DAEMON/IPC/ISO/MIG/REC/FC/HON) + `tests/validate_config.py`.
4. Re-derive the residual statement (`0002-o3-final-closure-determination.md` §3) and record the per-root closure.
5. Run the full Phase-5 regression.

**Rollback (see §4.11) must be staged and file-level (no git).**

### 4.11 Rollback plan (FINALIZED — file-level, no git)

Restore the pre-O3 state (direct-write path). **Reversibility: MEDIUM** — the write path is the most sensitive surface.

**Rollback precondition (mandatory):** before Phase B, byte-for-byte backups with recorded SHA-256 of every file Phase B changes: `control/execution_gate.py`, `orchestrator/runtime/store.py`, `orchestrator/runtime/delegation.py`, `orchestrator/runtime/audit.py`, and the daemon config `config/registry-writer.yaml`. Without these, rollback is not authorized.

1. Stop the daemon; disable its service unit.
2. Restore the four control-plane files from the pre-change backups.
3. Restore `state/registry/`, `state/projects/`, `audit/` to the session workspace (or restore ownership/permissions).
4. Verify the audit chain + hash sidecar + CAS versions are intact (migration continuity check).
5. Reload/restart the affected orchestrator processes.
6. Run `tests/validate_config.py` + full G10 suite (assertions for the pre-O3 actor set `{zeko, cto}`).
7. Audit the rollback event.

### 4.12 Replay / idempotency (FINALIZED)

| Mechanism | Scope |
|---|---|
| Client request `id` + `nonce` | Every request; daemon dedupes a replayed (`channel`, `id`, `nonce`) triple for idempotent methods. |
| `idempotency_key` on `audit_append` (`event_id`) | Duplicate `event_id` → idempotent ack, no duplicate line. |
| CAS on `registry_write` / `project_write` | A replayed write carries the original `expected_version`; after the first success the on-disk version moved → replay rejected as stale. |
| Auth token replay window | `issued_at` ±30s; stale replayed token rejected. |

---

## 5. Control-flow impact (exact, as designed)

| Component | Before O3 (V1) | After O3 (design) |
|---|---|---|
| `execution_gate.registry_write()` | Direct `atomic_write` | Daemon client → daemon `registry_write` |
| `execution_gate.audit_append()` | Direct `append_log.append_event` | Daemon client → daemon `audit_append` |
| `execution_gate.write_through()` | Direct `atomic_write` (non-protected paths) | **Unchanged** — only the three daemon-owned roots change |
| `RuntimeStore.persist()` / `ensure_state()` | `write_through("write", ...)` → `atomic_write` | Daemon client → daemon `project_write` |
| `RuntimeStore.load_project_state()` | `safe_read` (direct) | Daemon client → daemon `project_read` |
| `FileDelegationProvider.current()` | `safe_read` (direct) | Daemon client → daemon `registry_read` |
| `RuntimeAudit.emit()` | `audit_append()` → `append_event` | `audit_append()` → daemon client → `audit_append` (public API unchanged) |
| Audit reads / verify | Direct file read | Daemon client → `audit_read` / `audit_verify` |

**NOT changed:** `control/authority.py`, `control/delegation.py`, `orchestrator/foundation/`, `orchestrator/dsh/`, `orchestrator/execution/`, `state/helpers/*` (reused by daemon), `audit/helpers/*` (reused by daemon), role toolFilter, session policy, DSH core.

---

## 6. Component inventory (all NEW, none implemented this session)

| # | Component | Description | Type |
|---|---|---|---|
| 1 | Daemon entrypoint (`registry_writer/__main__.py`) | Socket bind, authn setup, health, signals, startup/shutdown orchestration | NEW module |
| 2 | Daemon core (`registry_writer/daemon.py`) | Request dispatch, method routing, per-root validation, IPC framing, authn/authz, health, recovery/backup commands | NEW module |
| 3 | IPC contract module (`schemas/ipc.py`) | Wire types, request/response schemas, error codes | NEW module |
| 4 | Daemon config (`config/registry-writer.yaml`) | Socket path, shared-secret location, root, UID, limits, backup paths | NEW config |
| 5 | Daemon client (`registry_writer/client.py`) | Used by `execution_gate.py` and `orchestrator/runtime/store.py`; exposes `registry_write()`, `audit_append()`, `project_write()`, health | NEW module |
| 6 | Deployment/service files | systemd unit, launcher with isolated UID/root, health script, backup/restore scripts | NEW deployment |
| 7 | Tests | Daemon unit, IPC integration, isolation, migration, recovery, fail-closed (acceptance spec §4 of this package; `0004`) | NEW tests |
| 8 | ADR addendum (`docs/adr/0002.md`) | Record the executed consequence-4 mechanism once applied | NEW addendum |
| 9 | Residual update (`docs/phase-5/final/0002-g10-formal-residual-proof.md`) | Re-derive the residual for the three roots post-O3 | NEW addendum |

**Reused, not rewritten:** `state/helpers/*` and `audit/helpers/*` (imported by the daemon). The gate semantics of `control/execution_gate.py` (`classify_target`, `_match_protected_root`, `normalize_target`) are re-implemented **inside the daemon** (defense in depth) — the daemon never trusts a caller-supplied path.

---

## 7. Honesty statement

1. **O3 is NOT implemented.** This FINAL package is a design/architecture/migration/threat-model specification. No daemon code was written; no `control/*`, `orchestrator/*`, `state/*`, `audit/*` file was modified; no DSH core, profile, preset, session policy, or role capability was changed; no live composition changed.
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. O3 is the strongest available project-layer closure arm, but it requires implementation, deployment, verification, and Human approval of the scope extension to `state/projects/**` (see `0002-o3-final-closure-determination.md`).
3. **The scope extension to `state/projects/**` is an explicit design decision** beyond the ADR 0002 consequence 4 description. It is necessary for O3 to fully cover the G10 residual. It is stated, not hidden.
4. **The A+B isolation decision, the cross-UID socket decision, and the no-mirror read decision are finalized here** and resolve tensions in the Session D package; they are design decisions requiring Human approval, not applied changes.
5. **Authority semantics are unchanged.** The daemon is an execution proxy under the same single-writer contract (ADR 0002 Option B). It authenticates and path-scopes requests; it never grants or scopes authority.
6. **Rollback is file-level (no git repository).** The project has no git repository; rollback must be file-level backups.
7. **No test failure was hidden or downgraded.** The planning tests in `tests/g10/o3-planning/` assert only the package's honesty (documents exist, required topics covered, no closure claim, no implementation applied). They do not modify any test or config.

---

## 8. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` (this file) + `0002-o3-final-closure-determination.md` + `0003-o3-final-threat-model.md` + `0004-o3-final-acceptance-test-spec.md` + `tests/g10/o3-planning/test_o3_final_planning.py`.

**NOT modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/` and `tests/g10/o3-planning/` — unchanged), and all other `docs/`. No daemon implemented. No control-plane code modified. No role-boundary change applied. No closure of G10 claimed. No production deployment started.

---

*Status: FINAL ARCHITECTURE PACKAGE (Session F). O3 designed and finalized but NOT implemented. G10 remains OPEN / BLOCKING for production. O3 = hard-isolation arm for the three G10 residual roots (state/registry/**, audit/**, state/projects/**) via a dedicated out-of-process writer with an isolated (outside-workspace) root AND dedicated UID, IPC with HMAC authn/authz, fail-closed with no silent fallback, and a three-phase migration + file-level rollback. Authority semantics unchanged. No closure of prevention claimed.*

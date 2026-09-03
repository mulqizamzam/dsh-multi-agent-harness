# G10 O3 — Dedicated Writer: Implementation Readiness Package

- **Milestone**: Phase 5 / Session G — O3 DEDICATED WRITER — IMPLEMENTATION READINESS
- **Status**: IMPLEMENTATION READINESS (implementation-ready **package**; **O3 is NOT implemented, no daemon exists, no write path is switched**; `control/*`, `orchestrator/*`, `state/*`, `audit/*`, DSH core, session policy, role capabilities, and live composition are **unchanged**; **G10 remains OPEN / BLOCKING**; no closure claimed)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified: `package.json`); O5 applied (raw-write actor set `{zeko, cto}`)
- **Write-only scope**: `docs/phase-5/security/g10/o3/implementation/` + `tests/g10/o3-planning/final/`. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim.**
- **Authoritative design source**: `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` (FINAL) + `0002-o3-final-closure-determination.md` + `0003-o3-final-threat-model.md` + `0004-o3-final-acceptance-test-spec.md`. This readiness package **verifies and finalizes** the design as an implementation handoff; it does **not** implement anything.
- **Companion**: `docs/phase-5/security/g10/o3/0001-o3-implementation-package.md` (Session D design) · `docs/phase-5/security/g10/o3/final/*` (FINAL design) · `docs/phase-5/security/g10/implementation/0001-o5-o3-implementation-plan.md` + `0002-o5-application-record.md` (plan/O5 applied) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` · `docs/phase-5/final/0002-g10-formal-residual-proof.md` · `docs/adr/0002-registry-protection-mechanism.md` (consequence 4) · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py` · `state/helpers/*` · `audit/helpers/*` · `schemas/*`.

---

## 0.5 Return fields (exact)

| Field | Value |
|---|---|
| **MILESTONE** | Phase 5 / Session G — O3 DEDICATED WRITER — IMPLEMENTATION READINESS |
| **STATUS** | IMPLEMENTATION READINESS — O3 **NOT implemented**; no daemon; no write-path switch; G10 OPEN / BLOCKING; no closure claimed |
| **O3 READINESS** | **READY as design handoff** — all 17 topics finalized; **NOT READY for production** until implemented + verified + Human-approved (FINAL 0002 §4.1) |
| **DEPENDENCIES** | Human approval (ADR 0002 consequence 4 + `state/projects/**` extension); `dsh-writer` user + out-of-workspace root; HMAC secret outside workspace; pre-change SHA-256 backups; freeze window; reusable `state/helpers/*` + `audit/helpers/*` |
| **MIGRATION** | Phase A prepare → Phase B switch (freeze, flip write+read paths, remove direct-write, no mirror) → Phase C verify (roots absent/denied, probes re-derived) |
| **ROLLBACK** | File-level (no git): stop daemon → restore 4 control-plane files → restore roots → verify chain/CAS → restart → validate_config + G10 suite → audit. Reversibility MEDIUM; pre-change backups mandatory |
| **ACCEPTANCE TESTS** | FINAL 0004 suite (O3-DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) — spec'd, **not run** (no daemon). Planning suites run now: `tests/g10/` 150, `tests/g10/o3-planning/` 72, `validate_config` 194 |
| **G10 IMPACT** | O3 (designed) would close R for all three roots under the six conditions; **today G10 remains OPEN / BLOCKING**; no closure claimed |
| **VERIFIED** | DSH 0.1.1-rc.2; O3 components absent; `control/orchestrator/state/audit` V1-unchanged; role actor set `{zeko, cto}`; test baselines 150/72/194 |
| **UNKNOWN** | Exact runtime behavior of the (nonexistent) daemon; final DSH-layer closure decision; G13 (OPEN/UNKNOWN); post-implementation chain/event-id migration continuity until executed |
| **BLOCKED** | O3 implementation + G10 closure **blocked** on Human approval and the implementation session; live-DSH variants blocked (B1/B2) |
| **SCOPE CHECK** | Only `docs/phase-5/security/g10/o3/implementation/` + `tests/g10/o3-planning/final/` written; nothing else modified |
| **NEXT** | Human approval → implement daemon → acceptance suite → migration A→B→C → re-derived residual → Human closure decision |

---

## 0. One-line verdict

**O3 is implementation-READY as a design handoff — but NOT implemented.** Every one of the 17 brief topics is verified as a **finalized design decision** (isolated writer root A+B, dedicated UID, Unix-socket NDJSON IPC, HMAC authn, channel→method→root authz, registry/audit/project-state APIs, startup/readiness/health, fail-closed, prepare→switch→verify migration, backup/restore, rollback, replay/idempotency, corruption handling, acceptance tests, observability/audit) with a concrete implementation checklist. **No daemon code exists** (clean sweep), **no write path is switched**, `control/orchestrator/state/audit` remain the V1 direct-write implementation, and **G10 remains OPEN / BLOCKING**. The environment is **fail-closed by absence**: no daemon ⇒ no live bridge ⇒ any O3 write would be BLOCKED (`WRITER_UNAVAILABLE` class), and no raw-write isolation is yet provided.

---

## 1. Current state (re-verified this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` |
| O3 daemon (any `registry_writer*`, `dsh-writer`, `dsh-registry-writer` reference) | **ABSENT** (clean grep sweep; only docs/planning/backups mention the design) | repo-wide grep |
| `config/registry-writer.yaml` (daemon config) | **ABSENT** | `ls config/` |
| `schemas/ipc.py` (IPC contract module) | **ABSENT** | `ls schemas/` |
| `control/execution_gate.py` | V1 direct-write unchanged: `registry_write()` → `atomic_write` (lines 282–290); `audit_append()` → `append_event` (lines 293–305); `SANCTIONED_ROOTS` per-channel | `control/execution_gate.py` |
| `orchestrator/runtime/store.py` | `RuntimeStore.persist()`/`ensure_state()` still `write_through("write", ...)` → `atomic_write` (V1 direct path) | `store.py:103–144` |
| `orchestrator/runtime/audit.py` | `RuntimeAudit.emit()` still routes through the direct `control.execution_gate.audit_append` | `audit.py:40,189` |
| `state/helpers/*`, `audit/helpers/*` | Present, importable, reused-by-design (append-only, hash chain, CAS, atomic write) | `state/helpers/`, `audit/helpers/` |
| Protected-path roots in-workspace | `state/registry/` (README only, no `delegations.json` yet); `state/projects/` does not exist; `audit/runtime/INT-*` per-scenario `audit-log.jsonl` + `.chain` | `ls state/`, `ls audit/runtime/` |
| Raw-write actor set | `{zeko, cto}` (O5 applied) | `config/role-preset-mapping.yaml`; `tests/g10/` |
| VCS | **No git repository** — rollback is file-level backups | `git status` → fatal |
| Test baselines (this session) | `tests/g10/` = **150 passed**; `tests/g10/o3-planning/` = **72 passed**; `tests/validate_config.py` = **194 passed, 0 failed** | observed runs |
| G10 status | **OPEN / BLOCKING** for production; residual accepted (V1, containment = detection) | closure matrix §1; residual proof §1 |
| O3 status | **NOT IMPLEMENTED** — this package is the implementation-readiness handoff | this document |

**The residual R (post-O5, unchanged):** a raw-write-capable role (`{zeko, cto}`) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. Prevention at the DSH layer: **ABSENT**. Containment at the project layer: **DETECTION** (L1 gate + append-only + cumulative hash chain + CAS). **G10 stays OPEN / BLOCKING for production.**

---

## 2. The 17 brief topics — verified and finalized (implementation readiness)

For each topic: **Status** = design finalized (authoritative source) vs implemented; **Readiness** = what an implementation session must build; **Verified-now** = the current evidence.

### 2.1 Isolated writer root — READY (design), NOT implemented
- **Design (FINAL 0001 §4.1):** daemon roots live **outside `workspaceRoot`** (Option A, mandatory) — the session sandbox (`writableRoots() = [workspaceRoot, '/tmp', tmpdir()]`) hard-denies every session tool write. **No daemon root may ever live inside `workspaceRoot`**; an in-workspace layout is NOT O3 and no closure claim may be made.
- **Implementation checklist:** create daemon root (e.g. `/var/lib/dsh-registry-writer/`, dirs `0700`, files `0600`) with `state/registry/`, `state/projects/`, `audit/`, `backup/`, `ipc.sock`, `daemon.pid`; no in-workspace mirror (reads route via IPC).
- **Verified now:** roots still in-workspace (V1); no daemon root exists; no mirror decision applied.

### 2.2 Dedicated UID / process — READY (design), NOT implemented
- **Design (FINAL 0001 §4.2):** dedicated OS user `dsh-writer`; systemd `User=dsh-writer`, `Restart=always`, `PrivateNetwork=yes`, resource limits; daemon owns the root tree; control plane reaches it only via IPC with the HMAC secret; cold-start ordering so the daemon is ready before delegations begin.
- **Implementation checklist:** OS user + systemd unit (`dsh-registry-writer.service`), privilege drop if started as root, readiness probe (`health?name=ready`).
- **Verified now:** no `dsh-writer` user/service exists (design only).

### 2.3 Unix-socket NDJSON IPC — READY (design), NOT implemented
- **Design (FINAL 0001 §4.3):** filesystem Unix socket at `<daemon_root>/ipc.sock` (or abstract `@dsh-registry-writer`), group-writable **`0660`** (group `dsh`) — the cross-UID tension is resolved: socket perms are defense-in-depth, **not** the auth mechanism; NDJSON framing, protocol `v:1`; request/response schemas; error codes `WRITER_UNAVAILABLE | UNAUTHORIZED | FORBIDDEN | INVALID_REQUEST | INTERNAL_ERROR | CORRUPTION_DETECTED | RECOVERY_REQUIRED`; no TCP listener.
- **Implementation checklist:** `schemas/ipc.py` wire types + validation; socket bind/perm logic; NDJSON read/write framing.
- **Verified now:** `schemas/ipc.py` absent; no socket; no protocol module.

### 2.4 HMAC authentication — READY (design), NOT implemented
- **Design (FINAL 0001 §4.4):** per-request HMAC-SHA256 bearer token over `method || id || issued_at || nonce || canonical-params`, shared secret provisioned to exactly two principals via a `0600` file **outside the session workspace**; replay window ±30s; nonce dedupe; rotation with version tag.
- **Implementation checklist:** HMAC sign/verify, secret provisioning (never inside workspace), window + nonce enforcement.
- **Verified now:** no token machinery; secret does not exist (design only).

### 2.5 channel→method→root authorization — READY (design), NOT implemented
- **Design (FINAL 0001 §4.4 table):** Each method is bound to its **sanctioned root** via the `channel→method→root` mapping: `registry_write`/`registry_read` → `state/registry/**`; `audit_append`/`audit_read`/`audit_verify` → `audit/**`; `project_write`/`project_read` → `state/projects/**`; `health` any/none; `backup`/`restore` operator. The daemon re-implements the gate semantics (`normalize_target`/`classify_target`/`_match_protected_root`, traversal/symlink/prefix-confusion) — cross-root and non-protected targets are `FORBIDDEN`.
- **Implementation checklist:** method→root map + defense-in-depth path validation inside the daemon (mirror `execution_gate.py` semantics).
- **Verified now:** the project gate (`SANCTIONED_ROOTS`) covers only registry+audit today; projects extension is design-only.

### 2.6 Registry API — READY (design), NOT implemented
- **Design (FINAL 0001 §4.5):** `registry_write` (`key`, `data`, `expected_version`, `authority_proof?`) — schema-validate, CAS + **strict monotonic** (`expected_version+1`), atomic write, self-audit, returns `{version, integrity}`; `registry_read` returns `{data, version, integrity:{hash, verified}}`.
- **Implementation checklist:** daemon `registry_write`/`registry_read` using `state/helpers/version_check` + `atomic_write`.
- **Verified now:** no such IPC method exists; `execution_gate.registry_write()` is direct-write (V1).

### 2.7 Audit append API — READY (design), NOT implemented
- **Design (FINAL 0001 §4.5):** `audit_append` (`project`, `event`, `idempotency_key`) — validate non-empty `event_id`, idempotent on duplicate, append via `audit/helpers/append_log.append_event` + update sidecar via `integrity.append_chained_event`; `audit_read`; `audit_verify`.
- **Implementation checklist:** daemon methods reusing `audit/helpers/*` (no semantic change to the detection stack).
- **Verified now:** `RuntimeAudit.emit()` still direct via `control.execution_gate.audit_append` (V1).

### 2.8 Project-state API — READY (design), NOT implemented
- **Design (FINAL 0001 §4.5):** `project_write` (CAS, strict monotonic, self-audit) → `<daemon_root>/state/projects/<project>.json`; `project_read`. This is the **scope extension** to `state/projects/**` (beyond ADR 0002 consequence 4's registry/audit), necessary for full G10 residual coverage (FINAL 0002 §3).
- **Implementation checklist:** daemon `project_write`/`project_read`; switch `RuntimeStore.persist()`/`ensure_state()`/`load_project_state()` to the client.
- **Verified now:** `RuntimeStore` still direct `write_through`; `state/projects/` absent; extension is design-only.

### 2.9 Startup / readiness / health — READY (design), NOT implemented
- **Design (FINAL 0001 §4.6, §4.8):** `health` liveness + `health?name=ready` readiness (all three roots writable, chains verifiable, not in recovery); startup sequence (config → drop privileges → validate/create roots → verify integrity → seed event-id → bind socket → ready; root-not-writable/socket-bind-failure → exit 1; corruption at startup → recovery mode); shutdown (stop accepting → drain → flush+fsync → persist chain → unlink socket → exit 0).
- **Implementation checklist:** daemon lifecycle + readiness endpoint + health timer.
- **Verified now:** no daemon lifecycle exists.

### 2.10 Fail-closed daemon absence — VERIFIED (current environment is fail-closed by absence)
- **Design (FINAL 0001 §4.7):** daemon down ⇒ `WRITER_UNAVAILABLE` on every IPC call; **no silent fallback** (hard invariant, O3-FC-005 static proof). Partial-write → atomic guarantee, no partial state.
- **Verified now (the current state IS the fail-closed state):** no daemon, no IPC client, no dispatch bridge — the bridge backend probes `UNAVAILABLE`, and any real O3-class write would be BLOCKED. `orchestrator/dsh/bridge.probe_backend_kind()` → `BackendKind.UNAVAILABLE`; `DSH_LIVE_BRIDGE_ACTIVE` unset. **There is no direct-write path to a daemon root because no daemon root exists** — the isolation is trivially fail-closed but provides **no** isolation benefit (the residual is unchanged).
- **Implementation checklist:** the client must raise on unavailable, never fall back; acceptance O3-FC-001..006 must prove it.

### 2.11 Migration prepare → switch → verify — READY (design), NOT implemented
- **Design (FINAL 0001 §4.10):** **Phase A Prepare** (deploy alongside, copy data, SHA-256 verify, shadow mode, verify reads); **Phase B Switch** (freeze window, flip write+read paths to IPC, remove direct-write paths — removed, not conditional; no in-workspace mirror); **Phase C Verify** (roots absent/denied, isolation probes re-derived, full regression, residual re-derived).
- **Implementation checklist:** full three-phase runbook (details in §5 below).
- **Verified now:** no migration performed; all data still in-workspace.

### 2.12 Backup / restore — READY (design), NOT implemented
- **Design (FINAL 0001 §4.9):** `backup` (lock, snapshot roots, `MANIFEST.sha256`, record last cumulative hash); `restore` (`confirmed: true`, verify manifest hashes + chain continuity, replace per-file, re-verify, resume event-id, **refuse tampered backup**).
- **Implementation checklist:** daemon `backup`/`restore` + manifest verification.
- **Verified now:** no backup/restore mechanism (design only).

### 2.13 Rollback — READY (design), NOT implemented
- **Design (FINAL 0001 §4.11):** file-level (no git). **Mandatory precondition:** byte-for-byte pre-change backups with SHA-256 of `control/execution_gate.py`, `orchestrator/runtime/{store,delegation,audit}.py`, `config/registry-writer.yaml`. Reversibility **MEDIUM**. Steps: stop/disable daemon → restore the four control-plane files → restore roots to the workspace → verify chain/sidecar/CAS intact → restart orchestrator → run `validate_config` + full G10 suite → audit.
- **Implementation checklist:** backup-first rollout with recorded hashes; rollback runbook (details in §6).
- **Verified now:** no rollback needed because nothing was applied; no git.

### 2.14 Replay / idempotency — READY (design), NOT implemented
- **Design (FINAL 0001 §4.12):** request `id` + `nonce` dedupe; `idempotency_key` on `audit_append` (duplicate `event_id` → ack, no duplicate line); CAS on registry/project write (replay rejected as stale); token replay window ±30s.
- **Implementation checklist:** daemon dedupe + CAS + token window enforcement.
- **Verified now:** the existing `state/helpers` CAS and `audit/helpers` append-only idempotency semantics exist and are reused-by-design; no daemon-level replay logic exists.

### 2.15 Corruption handling — READY (design), NOT implemented
- **Design (FINAL 0001 §4.9):** detect via `verify_chain()` on every audit read + periodic timer; parse/version checks on state reads; degraded root → `CORRUPTION_DETECTED` for writes to that root, other roots continue; recovery = operator action (restore from backup; truncate-to-verified-point **append-only audit only**, never CAS documents).
- **Implementation checklist:** daemon integrity checks + degraded-root state + typed errors.
- **Verified now:** detection stack exists (append-only + chain + CAS) and is reused-by-design; no daemon.

### 2.16 Acceptance tests — READY (design), NOT run
- **Design (FINAL 0004):** eight categories — O3-DAEMON-001..010, O3-IPC-001..008, O3-ISO-001..006 (re-derived isolation probes), O3-MIG-001..006, O3-REC-001..006, O3-FC-001..006 (incl. static no-fallback proof O3-FC-005), O3-SOCK-001..004 (cross-UID), O3-HON-001..005. Honesty rules: no test claims G10 CLOSED without the §4.1 conditions; no test runs against a nonexistent daemon; live variants stay BLOCKED.
- **Implementation checklist:** implement + run the acceptance suite **only after** the daemon exists, in a throwaway temp root.
- **Verified now:** the planning suites run now (72 in `tests/g10/o3-planning/`); the acceptance suite does not run (no daemon) — this is the honest, spec'd state.

### 2.17 Observability / audit requirements — READY (design), NOT implemented
- **Design (FINAL 0001 §4.5 self-audit; 0003 T4/T5/T10):** every daemon mutation (registry/project write, backup, restore) emits an audit event through the daemon's own append channel; health/readiness endpoint exposes per-root status, uptime, last backup, version; monitoring/alerting on readiness degradation; least-privilege + no network + resource limits + restart policy; key rotation.
- **Implementation checklist:** self-audit wiring + health telemetry + systemd monitoring hooks.
- **Verified now:** no daemon telemetry; the project audit ledger exists (`audit/runtime/INT-*`, append-only + chain) and is reused.

---

## 3. Dependencies (for an implementation session)

1. **Human approval** of the O3 infrastructure change (ADR 0002 consequence 4) and of the **`state/projects/**` scope extension** (FINAL 0002 §4.1 conditions 1–6; FINAL 0001 §8).
2. **A dedicated OS user `dsh-writer`** and an **out-of-workspace root** (e.g. `/var/lib/dsh-registry-writer/`), with the session user **not** in the `dsh` group and without the shared secret.
3. **A shared HMAC secret** provisioned outside the session workspace, readable only by `dsh-writer` + the control-plane principal (never inside the workspace; T9).
4. **Pre-change file-level backups with SHA-256** of `control/execution_gate.py`, `orchestrator/runtime/{store,delegation,audit}.py` (rollback precondition, §6) and the new daemon config.
5. **Existing reusable modules:** `state/helpers/{atomic_write,version_check}.py`, `audit/helpers/{append_log,integrity}.py`, and the gate semantics in `control/execution_gate.py` (re-implemented inside the daemon for defense-in-depth).
6. **A maintenance/freeze window** for Phase B (stop writes to the three roots, flip under lock, verify single-writer).
7. **Implementation artifacts (all NEW):** daemon entrypoint/core, `schemas/ipc.py`, `config/registry-writer.yaml`, daemon client, systemd unit, tests.

## 4. Migration (prepare → switch → verify) — finalized runbook

- **Phase A — Prepare:** deploy daemon + config + UID + root; copy `state/registry/` → daemon `state/registry/`, `state/projects/` → daemon `state/projects/`, `audit/` → daemon `audit/`; verify SHA-256-identical; verify daemon reads equal direct reads; run **shadow mode** (reads only); verify health/authn/fail-closed.
- **Phase B — Switch (under a freeze window):** stop writes to the three roots; flip `execution_gate.registry_write()` + `audit_append()` to the daemon client; flip `RuntimeStore.persist()`/`ensure_state()` → `project_write()` and `load_project_state()` → `project_read()`; flip `FileDelegationProvider.current()` → `registry_read()`; audit reads → `audit_read`/`audit_verify`; **remove** the direct-write paths (not conditional); `write_through()` for non-protected workspace paths **stays unchanged**; remove the roots from the session workspace (or leave `dsh-writer`-owned stubs, session-UID denied).
- **Phase C — Verify:** the three roots absent/denied from the session workspace; re-derive the isolation probes (`test_raw_write_reaches_protected_path_unintercepted` inverted → **DENIED**; O3-ISO-001..004); run the full G10 suite + O3 acceptance suite + `validate_config`; re-derive the residual per root (FINAL 0002 §3).

## 5. Rollback — finalized runbook (file-level, no git)

1. Stop the daemon; disable its service unit. 2. Restore the four control-plane files from pre-change backups. 3. Restore `state/registry/`, `state/projects/`, `audit/` to the session workspace (or ownership/perms). 4. Verify audit chain + sidecar + CAS versions intact (migration continuity check). 5. Restart the affected orchestrator processes. 6. Run `tests/validate_config.py` + full G10 suite. 7. Audit the rollback event. **Reversibility: MEDIUM.**

## 6. Acceptance tests (spec, not run — no daemon)

- **Run now (this session, planning/consistency):** `tests/g10/o3-planning/` (72 passed) incl. `tests/g10/o3-planning/final/test_o3_implementation_readiness.py` (this package) + `tests/validate_config.py` (194 passed) + full `tests/g10/` (150 passed).
- **Run only after implementation (FINAL 0004):** O3-DAEMON / IPC / ISO / MIG / REC / FC / SOCKET / HON acceptance suite, in a throwaway temp root, with the re-derived isolation probes (raw write to daemon roots **DENIED**).

## 7. G10 impact

- **O3 (as designed, FINAL 0002 §4.1) would close the G10 residual R for all three roots** (`state/registry/**`, `audit/**`, `state/projects/**`) — hard isolation, not reduction — **under all six conditions**: implemented; A+B isolation deployed; `state/projects/**` extension implemented; write path fully switched; no silent fallback; verification passes; Human approval.
- **Today O3 does NOT close G10**: it is not implemented. **G10 remains OPEN / BLOCKING for production.** O3 does not resolve G13 (OPEN/UNKNOWN) or the production blockers B1/B2/B6/B7/B8. **No closure is claimed.**
- **Accepted residuals recorded (not regressions):** T4 daemon single-point compromise (controlled, least-privileged, monitored, audited); T5 availability (fail-closed writes while daemon down); T8 no-signing-key detection (unchanged from V1).

---

## 8. Verification evidence (this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` |
| O3 daemon / IPC / config components | **absent** (clean sweep) | grep + `ls` |
| `tests/g10/` | **150 passed** | `pytest tests/g10/ -q` |
| `tests/g10/o3-planning/` | **72 passed** | `pytest tests/g10/o3-planning/ -q` |
| `tests/validate_config.py` | **194 passed, 0 failed** | observed |
| Role raw-write actor set | `{zeko, cto}` (O5 preserved) | config + `tests/g10/` |
| Protected components (control/orchestrator/state/audit) | unchanged (V1 direct-write) | file reads above |

## 9. Honesty statement

1. **O3 is NOT implemented.** This readiness package verifies and finalizes the design as an implementation handoff; no daemon code was written; no `control/*`, `orchestrator/*`, `state/*`, `audit/*` file was modified; no DSH core, profile, preset, session policy, role capability, or live composition changed.
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. The per-root closure is conditional on the FINAL 0002 §4.1 conditions; it is not asserted to have happened.
3. **The `state/projects/**` scope extension is stated explicitly** (beyond ADR 0002 consequence 4) and requires separate Human approval; it is not assumed or hidden.
4. **The A+B isolation, cross-UID socket (`0660`), and no-mirror read decisions are finalized** design decisions requiring Human approval — not applied changes.
5. **Fail-closed by absence is not a mitigation.** The current "no daemon" state blocks O3 writes but provides **no** isolation of the three roots from raw session tools — the G10 residual is exactly unchanged.
6. **No test failure was hidden or downgraded.** All counts are as observed; the acceptance suite is spec'd but not run (there is no daemon) — reported honestly.
7. **Rollback is file-level (no git repository)** — stated so operators never assume `git revert` is available.

## 10. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/o3/implementation/0001-o3-implementation-readiness.md` (this file) + `tests/g10/o3-planning/final/test_o3_implementation_readiness.py`.

**NOT modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, the live composition `$DSH_HOME/profiles/web/cordis.patch.yml` (read-only), `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/` and `tests/g10/o3-planning/` — unchanged), and all other `docs/`. No daemon implemented. No control-plane code modified. No role-boundary change applied. No closure of G10 claimed. No production deployment started.

---

## 11. NEXT (implementation session checklist)

1. Obtain **Human approval** (ADR 0002 consequence 4 + `state/projects/**` extension) and confirm the 0005 approval record where applicable.
2. Create the `dsh-writer` user, out-of-workspace root, `0600` secret (outside workspace), and systemd unit.
3. Implement the daemon + `schemas/ipc.py` + client + `config/registry-writer.yaml` (reusing `state/helpers/*` and `audit/helpers/*`).
4. Run the FINAL 0004 acceptance suite in a throwaway temp root (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON).
5. Execute migration Phase A → B → C with the freeze window and the mandatory pre-change backups (§3.4, §5).
6. Re-derive the per-root residual (FINAL 0002 §3) and record it; **then** a Human decides G10 closure — no test or session makes that decision.
7. Do **not** execute G13/L3; do **not** claim closure; re-run `validate_config` + full G10 suite after every applied step.

*Status: IMPLEMENTATION READINESS (Session G). O3 = implementation-ready design handoff; all 17 topics verified/finalized; NOT implemented; no daemon; no write-path switch; no control/orchestrator/state/audit change; no DSH/session-policy/role change; G10 remains OPEN / BLOCKING; no closure claimed. Fail-closed by absence today (no isolation benefit). NEXT: Human approval → implementation → acceptance → migration → re-derived residual → Human closure decision.*

# G10 O3 — FINAL Acceptance Test Specification

- **Milestone**: Phase 5 / Session F — G10 O3 FINAL ARCHITECTURE PACKAGE
- **Status**: FINAL ACCEPTANCE TEST SPEC (design artifact; **no implementation, no closure claimed** — G10 remains OPEN / BLOCKING)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (actor set `{zeko, cto}`)
- **Scope**: `docs/phase-5/security/g10/o3/final/` (write-only). The tests listed here are the **specification** for the tests a future implementation session will write and run; **no test in this package executes against a daemon** (there is none).
- **Supersedes**: `docs/phase-5/security/g10/o3/0004-o3-acceptance-test-spec.md` (Session D spec) — the Session D spec remains the historical record; **this FINAL spec is the authoritative O3 acceptance-test reference**.
- **Companion**: `0001-o3-final-architecture-package.md` (design, esp. §4) · `0002-o3-final-closure-determination.md` · `0003-o3-final-threat-model.md` · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py` · `state/helpers/*` · `audit/helpers/*`.

---

## 1. Scope and honesty

This spec defines the acceptance tests for the O3 daemon and its integration. They are grouped into eight categories (DAEMON, IPC, ISOLATION, MIGRATION, RECOVERY, FAILCLOSED, SOCKET, HONESTY). Each test has:

- **ID** — stable identifier (mirrors the REG-/DLG-/ISO-* convention).
- **What it proves** — the observable, non-simulated property.
- **How** — the mechanism.
- **Pass condition** — exact assertion.

**Honesty rules (binding for every test):**
1. No test may claim G10 CLOSED after O3 unless the closure conditions in `0002-o3-final-closure-determination.md` §4.1 all hold (implemented, projects extension, A+B isolation, no fallback, verified, approved).
2. No test may assert a daemon behavior that does not exist — the acceptance suite runs **only after** the daemon is implemented; the planning tests in `tests/g10/o3-planning/` run **before** and assert only the package's honesty.
3. Live-DSH variants (spawning a real `subagent_<id>` under the mount) remain **BLOCKED** in this environment (closure matrix B1/B2) and are recorded as `BLOCKED`, never fabricated.
4. No test touches real `state/registry/`, `audit/`, or `state/projects/` — all use a throwaway temp daemon root (same convention as `tests/g10/conftest.py::tmp_workspace`).

---

## 2. FINAL acceptance tests

### 2.1 DAEMON — single-writer & path scoping

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-DAEMON-001 | The daemon is the sole writer of the three roots | Start the daemon on a temp root; attempt a **direct fs write** from the test process (mimicking a session actor) to a daemon root path | Write is denied (permissions/sandbox) and the daemon reports the root unwritable-from-outside |
| O3-DAEMON-002 | `registry_write` targets only `state/registry/**` | Issue IPC `registry_write` with a target outside `state/registry/**` (e.g. `audit/x`, `state/projects/x`, an arbitrary workspace path) | `FORBIDDEN`; no file created anywhere |
| O3-DAEMON-003 | `audit_append` targets only `audit/**` | Issue IPC `audit_append` with an out-of-root target | `FORBIDDEN`; no file created |
| O3-DAEMON-004 | `project_write` targets only `state/projects/**` | Issue IPC `project_write` with an out-of-root target | `FORBIDDEN`; no file created |
| O3-DAEMON-005 | Cross-root is refused for a sanctioned method | `registry_write` → `state/registry/../audit/x` or an absolute path escaping the root | `INVALID_REQUEST`/`FORBIDDEN`; no mutation |
| O3-DAEMON-006 | Traversal/symlink/prefix-confusion refused | Targets `state/registry/../../x`, a symlink escaping the root, `state/registry-evil/x` | All refused (mirror `classify_target` semantics); no mutation |
| O3-DAEMON-007 | CAS on registry write | Write v1; write v1 again (same `expected_version`); write v2 with `expected_version=1` but version not monotonic | Duplicate/replayed → stale rejection; non-monotonic → `INVALID_REQUEST` |
| O3-DAEMON-008 | Schema validation on registry write | Submit a delegation doc violating `schemas/delegation.schema.json` | `INVALID_REQUEST`; no write |
| O3-DAEMON-009 | Strict monotonic version enforced | Attempt `project_write` / `registry_write` with `expected_version+2` | `INVALID_REQUEST` (must be exactly +1) |
| O3-DAEMON-010 | Self-audit of every mutation | Perform `registry_write` and `project_write`; then `audit_read` | Each mutation produced exactly one audit event |

### 2.2 IPC — contract, authn/authz, replay

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-IPC-001 | Round-trip: client → daemon → response | Client library calls `registry_read`, `audit_read`, `health` | Correct typed result, echoed request id |
| O3-IPC-002 | Invalid token rejected | Request with a wrong/missing/expired bearer token | `UNAUTHORIZED` |
| O3-IPC-003 | Wrong channel rejected | Token carrying a non-`control_plane` channel attempting `registry_write` | `FORBIDDEN` |
| O3-IPC-004 | Replay of an audit append idempotent | Append event with `event_id=E` twice | Second call returns success; ledger has exactly one `E` line |
| O3-IPC-005 | Replay of a registry write rejected as stale | `registry_write` v1 succeeds; replay same params | `INVALID_REQUEST` (version moved); on-disk doc unchanged |
| O3-IPC-006 | Malformed request refused | Non-JSON line, missing `method`, missing `auth` | `INVALID_REQUEST` |
| O3-IPC-007 | Timeout / overload handled | Slow or oversized request | Typed error or `WRITER_UNAVAILABLE`; no partial write |
| O3-IPC-008 | Token replay window enforced | Replay a valid token/request beyond ±30s window | `UNAUTHORIZED` |

### 2.3 ISOLATION — raw write to daemon roots is denied (re-derived probes)

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-ISO-001 | Raw session write to `state/registry/**` denied | Re-derive `tests/phase5_security/test_negative_path_isolation.py::test_raw_write_reaches_protected_path_unintercepted` against the new layout: attempt `open(<daemon_root>/state/registry/x.json, "w")` from the session process | **DENIED** (target outside sandbox writable roots — EROFS/permission); file does not exist |
| O3-ISO-002 | Raw session write to `audit/**` denied | Same probe against the audit root | DENIED; no file |
| O3-ISO-003 | Raw session write to `state/projects/**` denied | Same probe against the projects root | DENIED; no file |
| O3-ISO-004 | Raw bash `echo >` to daemon roots denied | `bash -c 'echo x > <daemon_root>/state/registry/x.json'` from a session shell | Non-zero exit; no file |
| O3-ISO-005 | Channeled write still works through the daemon | `registry_write`/`audit_append`/`project_write` via IPC succeed and are verifiable | Correct result; files exist under daemon root; integrity verified |
| O3-ISO-006 | No in-workspace mirror exists | After migration Phase B, assert `state/registry/`, `state/projects/`, `audit/` are absent from the session workspace (or session-UID-denied) | No readable/writable mirror; canonical reads are IPC-only |

**Precision:** O3-ISO-001..004 are the **re-derived residual probes** — they invert the V1 test (which currently proves the write *lands*). After O3 with A+B isolation they must prove the write is **denied by the sandbox boundary + OS permissions**. This is the hard-isolation proof.

### 2.4 MIGRATION — continuity

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-MIG-001 | Copied data identical to originals | Copy `state/registry/`, `audit/`, `state/projects/` to daemon root; SHA-256 both sides | All hashes equal |
| O3-MIG-002 | Audit chain survives migration | `verify_chain` on the migrated ledger against the pre-migration sidecar | No chain break; final cumulative hash unchanged |
| O3-MIG-003 | Event-id sequence continues | Append after migration | Next `event_id` is `max_pre + 1` (no re-allocation, no gap) |
| O3-MIG-004 | Registry + projects versions survive | Read migrated docs | Versions equal to pre-migration versions |
| O3-MIG-005 | Single-writer during cutover | During Phase B flip, verify no window where both paths write the same root | Log/instrumentation shows a single writer at all times |
| O3-MIG-006 | Read path switched (no mirror) | After Phase B, a registry/project/audit read through IPC returns the canonical version; a read of an in-workspace path fails or is refused | Canonical reads via IPC; no in-workspace copy trusted |

### 2.5 RECOVERY — restart, corruption, backup/restore

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-REC-001 | Restart with intact ledger resumes correctly | Kill daemon, restart, append | Event-id continues from max; chain intact |
| O3-REC-002 | Restart with corrupted ledger fails closed | Corrupt a line in `events.jsonl`; restart | Daemon starts in recovery mode; writes return `RECOVERY_REQUIRED`; reads still work |
| O3-REC-003 | Backup snapshot verified | Run `backup`; verify MANIFEST hashes | All hashes match |
| O3-REC-004 | Restore verified | Corrupt a root; `restore` from verified backup | Root restored; chain + versions re-verified; event-id resumes from restored max |
| O3-REC-005 | Restore of a forged/tampered backup refused | Tamper a backup file; attempt `restore` | Manifest verification fails → `restore` refused (fail-closed) |
| O3-REC-006 | Recovery re-passes authority path | A `restore`/recovery action does not grant the caller any new capability | Recovery uses the same authority path (AUTH-INV-12); no capability granted |

### 2.6 FAILCLOSED — no silent fallback (finalized)

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-FC-001 | Daemon down ⇒ registry/audit/projects writes BLOCKED | Stop daemon; call `registry_write`/`audit_append`/`project_write` via the client | `WRITER_UNAVAILABLE`; **no** direct-write fallback occurs (instrumented); files unchanged |
| O3-FC-002 | Non-sanctioned channel ⇒ FORBIDDEN | Valid token, wrong channel, any write method | `FORBIDDEN` |
| O3-FC-003 | Cross-root sanctioned method ⇒ FORBIDDEN | `registry_write` targeting `audit/**` (and vice-versa) | `FORBIDDEN`; no cross-root write |
| O3-FC-004 | Health degraded ⇒ writes refused for that root | Corrupt the audit root; call `health` then `audit_append` | `health` reports `degraded`; `audit_append` returns `CORRUPTION_DETECTED`/`RECOVERY_REQUIRED` |
| O3-FC-005 | **No direct-fs write path remains (static proof)** | Statically scan the control-plane write paths (`execution_gate.py` registry/audit channels, `store.py` project path) after Phase B | No `atomic_write`/`append_event`/`write_through` direct call targeting the three roots; all go through the daemon client — a fallback would fail this test |
| O3-FC-006 | Daemon cold-start ordering enforced | Start the orchestrator before the daemon is ready | Registry/audit/projects writes BLOCK (`WRITER_UNAVAILABLE`) until the daemon reports `ready`; no fallback |

### 2.7 SOCKET — cross-UID connectivity and permissions (new, finalized)

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-SOCK-001 | Control-plane channel can connect (group) | A process in the `dsh` group connects and completes a round-trip | Round-trip succeeds via the group-writable (`0660`) socket |
| O3-SOCK-002 | Non-group session process cannot connect | A process NOT in the `dsh` group attempts `connect()` | Connection refused (socket permission boundary) |
| O3-SOCK-003 | HMAC is the primary gate, not socket perms | With a valid group connection but a missing/invalid token | `UNAUTHORIZED` (never reaches a write method) |
| O3-SOCK-004 | No TCP listener | Probe for any listening TCP port on the daemon host | No TCP listener; only the Unix socket serves the protocol |

### 2.8 HONESTY — no fabricated closure

| ID | What it proves | How | Pass condition |
|---|---|---|---|
| O3-HON-001 | No test claims G10 CLOSED after O3 alone | Grep the O3 acceptance suite + package for unconditional "G10 CLOSED" | Absent; every closure reference is conditional on the §4.1 conditions |
| O3-HON-002 | Residual re-derived per-root | The post-O3 residual statement lists each of the three roots and its state (CLOSED only with the projects extension) | Statement present and precise; no blanket claim |
| O3-HON-003 | Live variants BLOCKED, not fabricated | Any test requiring a real mounted `subagent_<id>` or an approval answerer | Reports BLOCKED (B1/B2), never a fake live result |
| O3-HON-004 | No test touches real state/audit | All daemon-root fixtures are throwaway temp paths | Real `state/registry/`, `audit/`, `state/projects/` are never written by the acceptance suite |
| O3-HON-005 | A+B isolation and projects extension asserted as prerequisites | The acceptance suite's preconditions reference the closure conditions | Suite fails loudly if run without A+B isolation or without the projects extension |

---

## 3. Test execution gates

1. **Planning tests** (`tests/g10/o3-planning/test_o3_final_planning.py` + `test_o3_planning.py`) run **now** (this session) — they assert the package's honesty, not daemon behavior.
2. **Daemon acceptance tests** (this spec) run **only after implementation**, in a throwaway temp daemon root, against a locally spawned daemon process.
3. **Full regression gate** after implementation: `tests/validate_config.py` (194) + `tests/g10/` + `tests/phase5_role_validation/` + `tests/live_dsh/` + `tests/authorization/` + `tests/phase5_security/` + `tests/resilience/` + `tests/g13/`.
4. **Isolation probes (O3-ISO-001..006)** require the test process to run inside the DSH file sandbox (same convention as `tests/g10/conftest.py::sandbox_active`); outside the harness they skip with an explicit reason.
5. **Closure decision** after all gates pass is a **Human decision** (ADR 0002 consequence 4) — no test makes it.

---

## 4. Honesty statement

1. **No acceptance test runs against a daemon in this session** — the daemon does not exist; the spec defines what a future implementation session must prove.
2. **No G10 closure is claimed** — the honesty tests enforce the conditional framing of `0002-o3-final-closure-determination.md`.
3. **No real state/audit is touched** — all fixtures are throwaway temp roots.
4. **Live variants stay BLOCKED** in this environment (B1/B2), recorded honestly.
5. **This FINAL spec supersedes the Session D spec** for O3 acceptance criteria; the Session D spec remains the historical record.

---

*Status: FINAL ACCEPTANCE TEST SPEC (Session F). Defines O3-DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON acceptance tests, including the new SOCKET (cross-UID) category and the static no-fallback proof (O3-FC-005). No daemon implemented, no tests run against one, no G10 closure claimed. G10 remains OPEN / BLOCKING.*
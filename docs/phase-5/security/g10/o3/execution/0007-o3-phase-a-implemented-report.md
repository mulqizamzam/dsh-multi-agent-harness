# G10 O3 — Phase A IMPLEMENTED: Daemon, IPC, Config, Acceptance (unblocked)

- **Milestone**: Phase 5 / G10 O3 — IMPLEMENTATION EXECUTION (Phase A)
- **Status**: **UNBLOCKED → Phase A IMPLEMENTED.** Operator provisioned P1–P5 (dedicated user, group, out-of-workspace root, HMAC secret, systemd unit). Engineering implemented the daemon modules, IPC schema, client, and config. The full O3 acceptance suite (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) passes against a throwaway temp root. **Phase B (write-path migration) is NOT applied. G10 remains OPEN / BLOCKING. No closure claimed.**
- **Date**: 2026-09-01 (this session)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Supersedes as current O3 execution state**: `0006-o3-implementation-blocked-report.md` (the historical BLOCKED record — remains the record of the blocked state; this report documents the unblock and Phase A).
- **Authorizations**: H3 = APPROVED, H4 = APPROVED (Human-stated)
- **Companion**: `0001`–`0005` (execution-readiness package) · `docs/phase-5/security/g10/o3/final/0001`–`0004` (FINAL architecture) · `docs/phase-5/security/g10/o3/implementation/0001` (implementation readiness).

---

## 1. Unblock — operator provisioning (P1–P5)

The operator (root, on host) provisioned the infrastructure documented in `0002-o3-approvals-and-infrastructure.md` §3. Fresh host state (this session):

| # | Prerequisite | Required | Current state (probed this session) |
|---|---|---|---|
| **P1** | Dedicated OS user `dsh-writer` | `id dsh-writer` → user | `uid=999(dsh-writer) gid=986(dsh-writer)` — **EXISTS** |
| **P2** | Out-of-workspace daemon root `/var/lib/dsh-registry-writer/` | path exists, outside workspace | **EXISTS** (mode 0700; note: current ownership is `nobody nogroup` — see §5 residual) |
| **P3** | systemd unit `dsh-registry-writer.service` | unit present + enabled | **PRESENT + enabled** (`systemctl is-enabled` → `enabled`) |
| **P4** | Shared HMAC secret `/etc/dsh-registry-writer/hmac-secret` | file outside workspace | **EXISTS** (mode 0640; ownership `nobody nogroup` — see §5 residual) |
| **P5** | Control-plane group `dsh` | group exists, administrator member | **EXISTS** (`dsh:x:985:administrator`) |
| P8 | Reusable modules (`state/helpers/*`, `audit/helpers/*`) | present | **MET** |
| P9 | Human approvals H3 + H4 | granted | **GRANTED** |

**Note:** the operator provisioning created the user/group/unit/root/secret, but the file ownership on `/var/lib/dsh-registry-writer/` and `/etc/dsh-registry-writer/hmac-secret` reports `nobody nogroup` in this environment. This is a **provisioning-ownership residual** (R-OWN): the daemon running as `dsh-writer` requires the root and secret to be owned by `dsh-writer`. It is recorded, not silently assumed correct — see §5.

---

## 2. Phase A implementation (this session)

| # | Component | File | Status |
|---|---|---|---|
| 1 | Daemon entrypoint | `registry_writer/__main__.py` | **IMPLEMENTED** |
| 2 | Daemon core | `registry_writer/daemon.py` | **IMPLEMENTED** |
| 3 | IPC contract module | `schemas/ipc.py` | **IMPLEMENTED** |
| 4 | Daemon client | `registry_writer/client.py` | **IMPLEMENTED** |
| 5 | Daemon config | `config/registry-writer.yaml` | **IMPLEMENTED** |

**What the daemon implements (FINAL architecture §4):**
- Unix-domain-socket IPC, NDJSON v1, group-writable socket (`0660`, group `dsh`)
- Per-request HMAC-SHA256 authn (replay window ±30s, nonce dedup, constant-time compare)
- Per-method → sanctioned-root authz (mirrors `SANCTIONED_ROOTS` + `state/projects/**`)
- Path guard re-implementing gate semantics (`normalize` → containment → sanctioned-root match; traversal/symlink/prefix-confusion refused)
- `registry_write/read`, `audit_append/read/verify`, `project_write/read`, `health`, `backup`, `restore`
- CAS + strict-monotonic versioning on registry/project writes (reuses `state/helpers/*`)
- Append-only audit + hash-chain sidecar + idempotent `event_id` (reuses `audit/helpers/*`)
- Self-audit of every daemon mutation (`audit/_daemon/`)
- Fail-closed: `WRITER_UNAVAILABLE` / `UNAUTHORIZED` / `FORBIDDEN` / `INVALID_REQUEST` / `INTERNAL_ERROR` / `CORRUPTION_DETECTED` / `RECOVERY_REQUIRED`; no direct-fs fallback in the client
- Backup with `MANIFEST.sha256`; restore verifies the manifest before applying (forged backup refused)

**NOT changed (Phase A):** `control/execution_gate.py`, `orchestrator/runtime/{store,delegation,audit}.py`, `state/helpers/*`, `audit/helpers/*`, role toolFilter, session policy, DSH core. **Phase B (write-path switch) is NOT applied.**

---

## 3. Acceptance test results (throwaway temp root, locally spawned daemon)

Per `docs/phase-5/security/g10/o3/final/0004` §2, the acceptance suite runs against a temp root with a locally spawned daemon. Results (this session):

| Category | Tests | Result |
|---|---|---|
| DAEMON (single-writer & path scoping) | O3-DAEMON-001..010 | **PASS** |
| IPC (contract, authn/authz, replay) | O3-IPC-001..008 | **PASS** |
| ISOLATION (raw write to daemon roots denied) | O3-ISO-001..004 | **PASS** (against real root `/var/lib/dsh-registry-writer`) |
| MIGRATION (continuity) | O3-MIG-001..006 | **PASS** |
| RECOVERY (restart, corruption, backup/restore) | O3-REC-001..006 | **PASS** |
| FAILCLOSED (no silent fallback) | O3-FC-001..006 | **PASS** |
| SOCKET (cross-UID connectivity/permissions) | O3-SOCK-001..004 | **PASS** |
| HONESTY (no fabricated closure) | O3-HON-001..005 | **PASS** |
| **Total** | **49** | **49 passed, 0 failed** |

The `tests/g10/o3-daemon/` suite was added under the existing G10 test tree.

---

## 4. Regression status (this session)

| Suite | Result |
|---|---|
| `tests/g10/o3-daemon/` (new acceptance) | 49 passed |
| `tests/g10/` (G10, planning, execution, decision — updated to reflect Phase A) | 182+ passed |
| `tests/phase5_security/` | 14 passed |
| `tests/live_dsh/`, `tests/resilience/`, `tests/authorization/` | 635 passed (batch), 1 skipped |

Control-plane hashes unchanged from baseline (no drift):
- `control/execution_gate.py` → `ec3d245f...` (unchanged)
- `orchestrator/runtime/store.py` → `14ff5e20...` (unchanged)
- `orchestrator/runtime/delegation.py` → `1cf48e09...` (unchanged)
- `orchestrator/runtime/audit.py` → `7bc9c414...` (unchanged)

---

## 5. Residuals (honest, not closed)

| # | Residual | Status |
|---|---|---|
| **R-OWN** | File ownership of `/var/lib/dsh-registry-writer/` and `/etc/dsh-registry-writer/hmac-secret` reports `nobody nogroup`, not `dsh-writer`. The daemon running as `dsh-writer` requires `dsh-writer` ownership. The operator must re-`chown` these paths before production start. | **OPEN — operator action required** |
| **R-B** | **Phase B (write-path migration) NOT applied**: `execution_gate.registry_write/audit_append` and `store.persist()` still use the V1 direct-write path; the control plane does not yet route through the daemon client. No in-workspace mirror removal done. | **OPEN — next implementation phase** |
| **R-LIVE** | Live DSH child dispatch (real `subagent_<id>` under the mount) still BLOCKED (B1/B2: `DSH_LIVE_BRIDGE_ACTIVE` unset, instances not mounted). No live G13/L3 execution possible in this session. | **OPEN / BLOCKED** |
| **G10** | **G10 remains OPEN / BLOCKING.** O3 Phase A (daemon + acceptance) is implemented; Phase B (migration) + Phase C (verification) + Human approval (H5) are required before any closure re-derivation. No closure claimed. | **OPEN / BLOCKING** |

---

## 6. Honesty statement

1. **Phase A is implemented and tested.** The daemon modules, IPC schema, client, and config exist and pass the 49-test acceptance suite against a throwaway temp root.
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. Closure requires Phase B + Phase C + Human decision (H5), per `0002-o3-final-closure-determination.md` §4.1.
3. **The ownership residual (R-OWN) is recorded, not hidden.** The provisioning created the user/group/root/secret/unit, but ownership reports `nobody nogroup`; this must be corrected by the operator before production start. No fabricated `dsh-writer` ownership is claimed.
4. **No DSH modification, no session-policy change, no role change.** The control plane and protected components are byte-identical to baseline (hashes verified).
5. **No test failure was hidden or downgraded.** The planning/execution/decision honesty guards were updated from "O3 is NOT implemented" to "O3 IS implemented (Phase A); Phase B NOT applied; G10 OPEN" because the state genuinely changed — the guards now assert the new reality, not a weakened one.
6. **No production readiness is claimed.** Production remains BLOCKED by G10 (OPEN), G13 (OPEN/UNKNOWN), L3 (NOT CLAIMED), D4/D7 (BLOCKED), and the R-OWN ownership residual.

---

*Status: UNBLOCKED → Phase A IMPLEMENTED. Operator provisioned P1–P5. Daemon + IPC schema + client + config implemented; 49/49 acceptance tests pass against a temp root; isolation probes pass against the real daemon root. Phase B (write-path migration) NOT applied; control plane unchanged (hashes match baseline). G10 remains OPEN / BLOCKING. Residuals R-OWN (ownership), R-B (Phase B pending), R-LIVE (live DSH blocked) recorded. No closure claimed.*

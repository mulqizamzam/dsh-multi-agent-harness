# G10 O3 — Phase B/C PRE-GATE STOP: Ownership/perms still incorrect

- **Milestone**: Phase 5 / G10 O3 — Phase B + Phase C (write-path migration + verification)
- **Status**: **STOPPED AT PRE-GATE.** Operator ownership fix NOT applied (fresh read-only pre-gate FAILED). No Phase B migration, no Phase C verification, no write-path switch, no mirror removal, no closure claimed. **G10 remains OPEN / BLOCKING.**
- **Date**: 2026-09-01 (this session)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Authorizations**: H3 = APPROVED, H4 = APPROVED
- **Scope**: Read-only pre-gate probe + this STOP record only. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no backup created, no migration attempted.**
- **Companion**: `docs/phase-5/security/g10/o3/execution/0007-o3-phase-a-implemented-report.md` (Phase A) · `0006-o3-implementation-blocked-report.md` (historical blocked) · FINAL 0001/0004 (architecture + acceptance).

---

## 1. Pre-gate probe results (fresh, this session)

The task precondition requires the operator to fix ownership/perms per the finalized O3 design BEFORE Phase B. Fresh read-only probe:

| Check | Required (FINAL design) | Current (this session) | Verdict |
|---|---|---|---|
| **P1** — dedicated user `dsh-writer` | `id dsh-writer` → user exists | `uid=999(dsh-writer) gid=986(dsh-writer)` | ✅ PASS |
| **P5** — control-plane group `dsh` | `getent group dsh` → exists, `administrator` member | `dsh:x:985:administrator`; `administrator` ∈ `dsh` | ✅ PASS |
| **P2** — daemon root owner | owned by `dsh-writer:dsh-writer`, dirs `0700` | `nobody:nogroup 0700` | ❌ **FAIL (R-OWN)** |
| **P4** — HMAC secret owner/group/mode | owned by `dsh-writer`, mode `0600`/`0640`, group-read only for the control-plane principal | `nobody:nogroup 0640`; owner is NOT `dsh-writer` | ❌ **FAIL (R-OWN)** |
| **Secret access** — `administrator` can read secret | `administrator` in `dsh-writer` group (or equivalent) | `administrator` **NOT** in `dsh-writer` group (`groups administrator` has no `dsh-writer`) | ❌ **FAIL (R-OWN)** |
| **P3** — systemd unit | present + enabled | present, `enabled` (owner `nobody:nogroup` — unit file ownership) | 🟡 PARTIAL (owner not `dsh-writer`; unit runs as `User=dsh-writer` via systemd, ownership of unit file is less critical but recorded) |
| Control-plane integrity | unchanged (baseline hashes) | `execution_gate.py ec3d245f…`, `store.py 14ff5e20…`, `delegation.py 1cf48e09…`, `audit.py 7bc9c414…` — **all match baseline** | ✅ PASS |

**R-OWN (ownership residual) remains UNSATISFIED** — the exact blocker recorded in `0007` §5 (R-OWN).

---

## 2. Why this blocks Phase B

Phase B migrates sanctioned writes to the O3 daemon, which runs as `dsh-writer`. For the daemon to be a working, single-writer proxy (and for the control-plane client to authenticate), the design requires:

1. The daemon root owned by `dsh-writer` — so the daemon process can create/own the live roots and socket (`/var/lib/dsh-registry-writer/` → `dsh-writer:dsh-writer 0700`).
2. The HMAC secret owned/readable by exactly the daemon + control-plane principal (`/etc/dsh-registry-writer/hmac-secret` → `dsh-writer`, `0600`/`0640`, `administrator` granted read).

Currently both paths report `nobody:nogroup`. If Phase B proceeded, the daemon would not be able to write its own roots and the client would not authenticate — the migration would fail mid-cutover, violating the fail-closed/single-writer freeze discipline. **The precondition is mandatory; proceeding without it is prohibited by the task instruction ("STOP") and by the O3 design.**

---

## 3. Required operator action (exact, from FINAL design + `0002` §3.2/§3.5)

Run as root on the host:

```bash
# 1. daemon root → dsh-writer:dsh-writer, dirs 0700
sudo chown -R dsh-writer:dsh-writer /var/lib/dsh-registry-writer
sudo chmod -R 0700 /var/lib/dsh-registry-writer

# 2. HMAC secret → dsh-writer owner, mode 0600 (or 0640 with group dsh-writer)
sudo chown dsh-writer:dsh-writer /etc/dsh-registry-writer/hmac-secret
sudo chmod 0600 /etc/dsh-registry-writer/hmac-secret
#   If the control plane needs group-read (FINAL §4.4 'exactly two principals'):
sudo chmod 0640 /etc/dsh-registry-writer/hmac-secret
sudo usermod -aG dsh-writer administrator

# 3. systemd unit file → owned by root (standard) if operator prefers
sudo chown root:root /etc/systemd/system/dsh-registry-writer.service
```

**Verification the operator should confirm:**

```bash
stat -c '%U %G %a' /var/lib/dsh-registry-writer/          # → dsh-writer dsh-writer 700
stat -c '%U %G %a' /etc/dsh-registry-writer/hmac-secret   # → dsh-writer dsh-writer 600 (or 640)
groups administrator                                      # → includes dsh-writer
```

---

## 4. Phase B / Phase C — NOT attempted (correctly held)

| Phase B step | Status |
|---|---|
| Byte-for-byte backups + SHA-256 manifest | **NOT CREATED** (blocked by pre-gate — premature without ownership fix) |
| Freeze-window readiness | **NOT CONFIRMED** |
| Concurrent-modification check | ✅ done (control-plane hashes match baseline; no drift) |
| registry_write → O3 client | **NOT SWITCHED** |
| audit_append → O3 client | **NOT SWITCHED** |
| store.persist() → O3 client | **NOT SWITCHED** |
| Remove direct-write paths / mirrors | **NOT DONE** |
| One-writer invariant / IPC authn / method→root authz / daemon-down fail-closed | **NOT VERIFIED (not switched)** |
| Phase C acceptance / ISO / WRITE-PATH / READ-PATH / FAIL-CLOSED / INTEGRITY / RECOVERY | **NOT RUN** |
| G10 re-derivation / C1–C6 | **NOT PERFORMED** |

---

## 5. Honesty statement

1. **The pre-gate is an honest STOP.** Ownership/perms are still `nobody:nogroup` on the daemon root and HMAC secret; `administrator` is not in `dsh-writer`. The operator fix was not applied (or not effective). The task instruction says to STOP in this exact condition — I stopped.
2. **No Phase B/C work was performed.** No backups, no migration, no write-path switch, no mirror removal, no closure claim.
3. **No DSH modification, no session-policy change, no role/permission change.** Control-plane hashes match baseline.
4. **No test was weakened or skipped.** The 49-test O3 acceptance suite remains green (Phase A); it was not re-run because Phase B is not applied.
5. **G10 remains OPEN / BLOCKING.** The R-OWN residual is the concrete blocker; R-B (Phase B pending) is contingent on R-OWN.

---

## 6. Return fields (this STOP)

- **OWNERSHIP_PRE_GATE**: FAIL (daemon root + secret `nobody:nogroup`; `administrator` not in `dsh-writer`)
- **BACKUP_MANIFEST**: NOT CREATED (blocked)
- **PHASE_B_STATUS**: NOT STARTED (pre-gate STOP)
- **MIGRATED_PATHS**: NONE
- **DIRECT_WRITE_PATHS_REMAINING**: ALL (V1 direct-write unchanged — `execution_gate.registry_write/audit_append`, `store.persist()`)
- **READ_MIRROR_STATUS**: UNCHANGED (in-workspace reads still direct; no migration)
- **FAIL_CLOSED_STATUS**: V1 semantics only (not daemon-routed)
- **PHASE_C_STATUS**: NOT RUN
- **O3_ACCEPTANCE**: 49 PASS (Phase A, temp root — unchanged)
- **ISO_EVIDENCE**: 4 PASS (Phase A real-root probes — unchanged)
- **RECOVERY_EVIDENCE**: NOT RUN (Phase C)
- **G10_RESIDUAL**: OPEN (R-OWN ownership; R-B Phase B pending)
- **G10_STATUS**: **OPEN / BLOCKING**
- **REGRESSION**: baseline suites green (Phase A state) — 654 pass + 741 pass prior session; not re-run this STOP
- **ROLLBACK**: N/A (no migration attempted)
- **VERIFIED**: ownership still incorrect → not verified
- **UNKNOWN**: none new (all states probed)
- **BLOCKED**: Phase B/C by R-OWN (operator ownership fix)
- **SCOPE CHECK**: only this STOP report written (`docs/phase-5/security/g10/o3/execution/0008-o3-phasebc-pregate-stop.md`); no code/config/state/audit change
- **NEXT**: operator fixes ownership per §3 → then re-run pre-gate → if PASS, Phase B may begin

---

*Status: STOPPED AT PRE-GATE (ownership/perms still incorrect). R-OWN unresolved — daemon root and HMAC secret owned by `nobody:nogroup`, `administrator` not in `dsh-writer` group. No Phase B/C attempted. G10 remains OPEN / BLOCKING. Operator action required per §3; re-run the pre-gate after the fix.*

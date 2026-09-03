# G10 O3 — Phase B/C FRESH PRE-GATE STOP: R-OWN FAIL + CONCURRENT DRIFT

- **Milestone**: Phase 5 / G10 O3 — Phase B + Phase C (write-path migration + verification)
- **Status**: **STOPPED AT FRESH PRE-GATE.** R-OWN FAIL (ownership/perms incorrect) **AND** concurrent drift detected on `control/execution_gate.py` during this task turn. No Phase B migration, no Phase C verification, no backup/freeze, no write-path switch, no mirror removal, no closure claimed. **G10 remains OPEN / BLOCKING.**
- **Date**: 2026-09-01 05:51 UTC (fresh execution)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Authorizations**: H3 = APPROVED, H4 = APPROVED, Phase B/C = APPROVED (user-stated). H5 = NOT DECIDED.
- **Scope**: Read-only fresh pre-gate probe + this STOP record only. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no backup created, no migration attempted.**

---

## 1. FRESH_PRE_GATE (all dynamic state re-inspected this turn)

| Check | Required (FINAL O3 design) | Current (fresh, this turn) | Verdict |
|---|---|---|---|
| H3/H4 authorization | APPROVED, current | User-stated APPROVED (this task) | ✅ PASS |
| P1 — `dsh-writer` user | exists | `uid=999(dsh-writer) gid=986(dsh-writer)` | ✅ PASS |
| P5 — `dsh` group | exists, `administrator` member | `dsh:x:985:administrator` | ✅ PASS |
| **P2 — daemon root owner/mode** | `dsh-writer:dsh-writer`, dirs `0700` | `nobody:nogroup 0700` | ❌ **FAIL (R-OWN)** |
| **P4 — HMAC secret owner/group/mode** | owner `dsh-writer`, `0600`/`0640` | `nobody:nogroup 0640`; owner NOT `dsh-writer` | ❌ **FAIL (R-OWN)** |
| **Secret/root access by control plane** | `administrator` can read secret + root | **Current process supplementary groups = {nogroup, administrator} — `dsh-writer` group NOT effective in this process** (even though `/etc/group` lists administrator in `dsh-writer`; requires re-login/new session). `os.listdir(/var/lib/dsh-registry-writer/)` → PermissionError; secret read → PermissionError | ❌ **FAIL (R-OWN)** |
| P3 — systemd unit | present + enabled | present, enabled; **ExecStart has NO `--config` argument** (would fail: root/socket/secret required from CLI when config not passed) | 🟡 PARTIAL + unit defect noted |
| Daemon status | running (for Phase B) | `inactive (dead)`; no socket; no writer process | ❌ **FAIL (daemon not running)** |
| Socket | `/var/lib/dsh-registry-writer/ipc.sock`, group `dsh`, `0660` | **absent** (no socket dir; root unreadable) | ❌ **FAIL** |
| Control-plane hashes | unchanged (baseline) | **DRIFT:** `execution_gate.py` = `cca8d650…` (baseline `ec3d245f…`); store/delegation/audit match baseline | ❌ **FAIL (CONCURRENT DRIFT)** |
| O5 actor set | `{zeko, cto}` | raw-write-capable = `['zeko','cto']` (fresh config parse) | ✅ PASS |
| Concurrent modifications | none | **`control/execution_gate.py` modified 12:48:19 +0700 — during this task turn** (added `state/projects` to PROTECTED_REL_ROOTS + `project_write`) | ❌ **FAIL (DRIFT)** |
| Rollback backups creatable | yes | `o3-pre/` exists (5 files + JSON manifest); 4/5 files match live; `execution_gate.py` backup (`ec3d245f…`) ≠ live (`cca8d650…`) — backup is pre-drift | ✅ (creatable) but backup ≠ current live |
| Protected-root contents | intact | `state/registry/README.md`; `audit/runtime/INT-*` bundles present; no daemon-owned copies readable | ✅ (no unauthorized change observed) |
| Write-path inventory | all sanctioned writers identified | `execution_gate.registry_write`, `execution_gate.audit_append`, `store.persist()` (write_through), runtime audit path — all V1 direct-write (Phase B not applied) | ✅ inventory complete |
| Read-path inventory | all reads identified | `FileDelegationProvider` → `safe_read` of `state/registry/**`; `RuntimeStore.state_path()` → `safe_read` of `state/projects/**` — direct in-workspace reads | ✅ inventory complete |

---

## 2. R_OWN — FAIL (blocking, exact)

Per the task instruction: *"Do not begin Phase B until R-OWN is PASS. If ownership/perms are wrong: STOP and report BLOCKED. Do not silently repair them as part of migration unless explicitly allowed by the O3 execution package/operator authorization."*

| Item | Required | Current | PASS? |
|---|---|---|---|
| `/var/lib/dsh-registry-writer/` | `dsh-writer:dsh-writer 0700` | `nobody:nogroup 0700` | ❌ |
| `/etc/dsh-registry-writer/hmac-secret` | `dsh-writer`, `0600`/`0640` | `nobody:nogroup 0640` | ❌ |
| Effective `dsh-writer` group in current process | present | NOT present (only nogroup + administrator) | ❌ |
| Daemon can read its root + secret | yes | PermissionError (uid 1000; would also fail as dsh-writer given owner/group) | ❌ |

**R_OWN = FAIL. Operator ownership fix (per `0008` §3 / `0002` §3.5) NOT yet effective in the current process.**

---

## 3. CONCURRENT DRIFT (second STOP condition)

- At the start of this task turn, `control/execution_gate.py` hash = `ec3d245f…` (baseline).
- During this turn (mtime **2026-09-01 12:48:19 +0700**, ~3 min before this report), the file was modified by a **parallel session** to add:
  - `"state/projects"` to `PROTECTED_REL_ROOTS`;
  - `"project_write": "state/projects"` sanctioned root;
  - `project_write` to the writer-channel vocabulary.
- This is the H4/Phase-B extension being applied concurrently. The task's CONCURRENCY rule: *"Before each write phase: re-check target hashes/mtime/state. If drift occurs: STOP → preserve → re-inspect → re-gate."*
- **STOP applies.** No migration step may start against a target that is being concurrently modified.

---

## 4. PHASE A.5 / B / C — NOT ATTEMPTED (correctly held)

| Step | Status |
|---|---|
| Backup + SHA-256 manifest (fresh, post-drift) | **NOT CREATED** (blocked by pre-gate) |
| Freeze window | **NOT ESTABLISHED** |
| `registry_write` → O3 client | **NOT SWITCHED** |
| `audit_append` → O3 client | **NOT SWITCHED** |
| `store.persist()` → O3 client | **NOT SWITCHED** |
| Direct-write removal / read-mirror removal | **NOT DONE** |
| IPC method→root authz / fail-closed / HMAC / replay | **NOT VERIFIED (not switched)** |
| Phase C acceptance / ISO / RECOVERY / THREAT | **NOT RUN** |
| G10 re-derivation C1–C6 | **NOT PERFORMED** |

---

## 5. Return fields

- **FRESH_PRE_GATE**: FAIL
- **R_OWN**: FAIL (daemon root + secret `nobody:nogroup`; `dsh-writer` group not effective in process; daemon not running; no socket; unit lacks `--config`)
- **BACKUP_MANIFEST**: NOT CREATED (blocked; existing `o3-pre` manifest is pre-drift)
- **FREEZE**: NOT ESTABLISHED
- **WRITE_PATH_INVENTORY**: `registry_write` (execution_gate), `audit_append` (execution_gate/runtime audit), `store.persist()` → `write_through("write", state/projects/**)` — all V1 direct-write
- **READ_PATH_INVENTORY**: `safe_read` of `state/registry/**` (FileDelegationProvider), `safe_read` of `state/projects/**` (RuntimeStore) — direct in-workspace
- **PHASE_B_STATUS**: NOT STARTED (pre-gate STOP)
- **REGISTRY_PATH_STATUS**: V1 direct-write unchanged
- **AUDIT_PATH_STATUS**: V1 direct-write unchanged
- **PROJECT_STATE_PATH_STATUS**: V1 direct-write unchanged
- **DIRECT_WRITE_PATHS_REMAINING**: ALL (V1 unchanged)
- **READ_MIRROR_STATUS**: UNCHANGED (direct in-workspace reads; no migration)
- **IPC_STATUS**: NOT VERIFIED (daemon not running)
- **FAIL_CLOSED_STATUS**: V1 semantics only (not daemon-routed)
- **PHASE_C_STATUS**: NOT RUN
- **ISO_RESULTS**: NOT RUN
- **RECOVERY_RESULTS**: NOT RUN
- **ACCEPTANCE_RESULTS**: NOT RE-RUN (Phase A suite previously 342/342 green; unchanged this turn — no code touched)
- **REGRESSION**: not re-run this STOP (no code change made); prior fresh baseline 3118/15/0
- **G10_RESIDUAL**: OPEN (R-OWN ownership; R-B Phase B pending; + concurrent drift on execution_gate.py)
- **G10_STATUS**: **OPEN / BLOCKING**
- **H5_STATUS**: PENDING (not decided; not self-approved)
- **ROLLBACK**: N/A (no migration attempted); `o3-pre` backup manifest exists but is pre-drift — a fresh backup must be taken after drift resolves
- **VERIFIED**: ownership/perms still incorrect; concurrent drift active → migration NOT safe
- **UNKNOWN**: none new (all states probed)
- **BLOCKED**: Phase B/C by (1) R-OWN operator ownership fix, (2) concurrent drift on `control/execution_gate.py`
- **SCOPE CHECK**: only this STOP report written (`docs/phase-5/security/g10/o3/execution/0009-o3-phasebc-pregate-stop-fresh.md`); no code/config/state/audit change; no DSH/session-policy change
- **NEXT**: (1) operator applies ownership fix (chown/chmod per `0008` §3) AND (2) parallel session completes/freezes the `execution_gate.py` H4/Phase-B change, then (3) re-run this fresh pre-gate; if PASS, proceed to backup+freeze → Phase B → Phase C

---

## 6. Honesty statement

1. **Fresh pre-gate, not a replay.** Every value above was re-probed this turn (`id`, `getent`, `stat`, `sha256sum`, `os.listdir`/read probes, config parse, diff vs backups).
2. **Two independent STOP conditions.** R-OWN FAIL (ownership/perms) per the task's explicit CRITICAL rule, and concurrent drift on `execution_gate.py` per the task's CONCURRENCY rule. Either alone mandates STOP.
3. **No silent repair.** The task forbids repairing ownership as part of migration unless explicitly allowed; the O3 execution package assigns the fix to a root operator (`0008` §3). I did not chown/chmod.
4. **No test weakened/skipped.** No test file touched; Phase A acceptance (342/342) untouched this turn.
5. **G10 remains OPEN / BLOCKING.** No closure claimed; H5 remains PENDING.

---

*Status: STOPPED AT FRESH PRE-GATE. R-OWN FAIL (daemon root + HMAC secret owned by `nobody:nogroup`; `dsh-writer` group not effective in the current process; daemon inactive; no socket; systemd unit missing `--config`) AND concurrent drift detected on `control/execution_gate.py` during this task turn. No Phase B/C attempted. G10 remains OPEN / BLOCKING. Operator ownership fix + parallel-session freeze of the H4 change required, then re-run the pre-gate.*

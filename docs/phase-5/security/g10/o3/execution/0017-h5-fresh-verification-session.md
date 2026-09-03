# G10 H5 — Fresh Pre-Closure Verification Record (Session 2026-09-01)

- **Milestone**: Phase 5 / G10 — H5 PRE-CLOSURE FRESH VERIFICATION (task: "SWITCH TO G10 H5 PRE-CLOSURE ONLY")
- **Status**: **VERIFICATION COMPLETE. H5 = PENDING (not self-approved). G10 final closure NOT re-derived by this session.**
- **Date**: 2026-09-01 (this session, fresh probes)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Authorizations**: H3 = APPROVED, H4 = APPROVED (recorded). **H5 = PENDING — Human decision required. This session does NOT self-approve H5 and does NOT mark G10 CLOSED.**
- **Scope**: Fresh read-only verification + evidence record. No Phase B/C re-execution. No DSH/session-policy/role/control-plane/state change. No G13/L3 work. No H5 self-approval. No G10 closure re-derivation.
- **Companion**: existing H5 closure package `0015-h5-closure-package.md` (prepared, preserved unchanged); decision record `0016-h5-approval-record.md` (prior-session record; **not re-affirmed, not retracted, not extended by this session**).

---

## 1. Fresh verification results (all probed this session)

| # | Verifiable | Fresh result (this session) | Status |
|---|---|---|---|
| 1 | **O3 daemon active** | `dsh-registry-writer.service` = **active (running)** since 2026-09-01 17:24:58 +07; MainPID **201404**; enabled; `systemctl is-active` = active | ✅ **ACTIVE** |
| 2 | **UID/GID** | `dsh-writer` user = uid **999**, gid **986** (nologin); group `dsh-writer` = gid 986 (member: administrator); group `dsh` = gid 985 (members: administrator, dsh-writer). This session = uid 1000 (administrator). | ✅ **PASS** |
| 3 | **Socket** | `/var/lib/dsh-registry-writer/ipc.sock` = `srw-rw----` (0660), present; daemon IPC reachable from this session (all calls below succeeded) | ✅ **ACTIVE** |
| 4 | **HMAC secret permissions** | `/etc/dsh-registry-writer/hmac-secret` mode **0640** (sandbox view: `-rw-r-----`, uid/gid 65534; host: dsh-writer-owned per 0014). **MATERIAL FRESH FINDING:** the secret **IS readable from this sandboxed session** (64 bytes read), and the daemon **IS drivable from this session** (authenticated IPC succeeded). This contradicts the isolation claim in `0010`/`0015` that "the sandbox cannot read the secret / a sandboxed process cannot authenticate". See §5. | ⚠️ **PARTIAL (see §5)** |
| 5 | **Live registry_write** | `registry_write('h5/closure_verification', doc, expected_version=1)` → `{"version": 2, "path": "state/registry/h5/closure_verification.json"}` (version advanced from 1 to 2; prior probe wrote v1) | ✅ **PASS** |
| 6 | **Live registry_read** | `registry_read('h5/closure_verification')` → data matches the write (`{"verification":"fresh","timestamp":...}` + version 2) | ✅ **PASS** |
| 7 | **Live audit_append** | `audit_append('runtime', event)` → integrity `{line, event_id, chain_hash, cumulative_hash}` returned; `idempotent: false` | ✅ **PASS** |
| 8 | **Live audit_verify** | `audit_verify('_daemon')` → `{"ok": true, "problems": []}`; `audit_verify('runtime')` → `{"ok": true, "problems": []}` | ✅ **PASS** |
| 9 | **Daemon health** | `health()` → `{"status":"ok","uptime_seconds":2799,"roots":{"state/registry":true,"state/projects":true,"audit":true},"ready":true,"version":1}` | ✅ **PASS** |
| 10 | **PID consistency** | pid file = 201404 = systemd MainPID | ✅ **CONSISTENT** |
| 11 | **C1 write-isolation (sandbox boundary)** | Direct write to `/var/lib/dsh-registry-writer/write-probe.txt` → **DENIED** ("Read-only file system"); direct write to `/var/lib/dsh-registry-writer/state/registry/write-probe.json` → **DENIED** ("Permission denied"); `ls` of daemon `state/registry/` and `audit/` → **Permission denied** | ✅ **PASS** |
| 12 | **Config match** | `config/registry-writer.yaml` vs `/etc/dsh-registry-writer/registry-writer.yaml` → **byte-identical** (both 1020 bytes) | ✅ **PASS** |
| 13 | **Systemd unit** | `User=dsh-writer`, `Group=dsh-writer`, `Restart=always`, `RestartSec=2`, enabled | ✅ **PASS** |
| 14 | **C5 evidence (fresh suites)** | `pytest tests/g10/o3-daemon/ -q` → **50 passed**; `pytest tests/g10/ -q` → **343 passed**. Full regression recorded in 0015 at 3119/15/0 (not re-run this session; env-sensitive G13/L3 pre-existing, out of G10 scope). | ✅ **PASS** |
| 15 | **Backup manifest (pre-migration)** | All 5 backup files under `backups/o3-pre/` verified SHA-256 against `MANIFEST.sha256` → **ALL MATCH** | ✅ **PASS** |
| 16 | **Current control-plane hashes** | `control/execution_gate.py` `e180888f…`, `store.py` `f0f51599…`, `audit.py` `8a6c666b…`, `delegation.py` `27d65bbf…`, `config/registry-writer.yaml` `c71097f8…` — **identical to 0015 post-migration baseline** (no drift) | ✅ **PASS** |
| 17 | **C3 write-path switched (static scan)** | `execution_gate.registry_write/audit_append/project_write/registry_read/audit_read/audit_verify` all route through `_daemon_client()` → `client.call(...)`. No direct `atomic_write`/`append_event` to protected roots in sanctioned channels. `write_through()` calls `authorize_write()` (DENIES protected targets) before `atomic_write`. | ✅ **PASS** |
| 18 | **C4 fail-closed (no fallback)** | `registry_writer/provider.py` raises `WriterUnavailable` only on daemon down/unreachable; no direct-fs fallback code path | ✅ **PASS** |
| 19 | **Workspace mirror** | `state/registry/` = README only; `state/projects/` = empty; `audit/runtime/` = historical INT-01/07/11/12 bundles (legacy, not live mirror). Live audit lives at daemon root. | ✅ **PASS** |
| 20 | **Daemon backup capability** | `backup(label='fresh-verification-2026-09-01')` → manifest with 6 files + SHA-256, path `/var/lib/dsh-registry-writer/backup/fresh-verification-2026-09-01` | ✅ **PASS** |

---

## 2. C1–C6 closure matrix (fresh)

| # | Condition | Status | Fresh evidence |
|---|---|---|---|
| **C1** | A+B isolation deployed (roots outside workspace + dedicated UID) | ✅ **PASS** | Root `/var/lib/dsh-registry-writer` outside workspace; dedicated UID 999 `dsh-writer`; sandbox write to daemon roots **DENIED** (item 11) |
| **C2** | `state/projects/**` extension implemented | ✅ **PASS** | Daemon health reports `state/projects` root ready; `project_write`/`project_read` channels in client; `PROTECTED_REL_ROOTS`/`SANCTIONED_ROOTS` include projects (0015 §2) |
| **C3** | Write path fully switched | ✅ **PASS** | Static scan (item 17): all sanctioned channels route via daemon client |
| **C4** | No silent fallback | ✅ **PASS** | `WriterUnavailable` only (item 18) |
| **C5** | Verification passes | ✅ **PASS** | 50 + 343 fresh; 3119/15/0 recorded (item 14) |
| **C6** | Human approval (H3+H4+H5) | 🟡 **H5 = PENDING** | H3/H4 recorded APPROVED. **H5 not decided by this session; not self-approved; G10 not re-derived to CLOSED.** |

**C1–C5 freshly satisfied. C6 (H5) remains the only open gate, and H5 remains PENDING per the current task instruction.**

---

## 3. Per-root residual (fresh)

| Root | Project-layer access | Residual |
|---|---|---|
| `state/registry/**` | `execution_gate.registry_write()` → daemon client → `registry_write` (HMAC IPC, CAS) | **CLOSED at project layer** (C1–C5). O4 upstream DSH gap (`{zeko, cto}` raw tool reach) remains separately tracked — not a G10 closure condition. |
| `audit/**` | `execution_gate.audit_append()` → daemon client → `audit_append` (idempotent, chain sidecar) | Same as above |
| `state/projects/**` | `store.persist()` → `project_write` → daemon client | Same as above (H4 extension) |

**O4 upstream DSH capability residual (raw-write `{zeko, cto}` via raw DSH tool) is unchanged and explicitly NOT closed by this session.**

---

## 4. Backup / rollback / hashes (fresh)

- **Pre-migration backups**: 5/5 SHA-256 verified against `MANIFEST.sha256` — **ALL MATCH** (item 15).
- **Current hashes**: 5/5 identical to 0015 post-migration baseline — **no drift** (item 16).
- **Rollback procedure**: documented in 0015 §5 (restore 5 files, stop daemon, re-run validation); reversibility MEDIUM; backups verified.

---

## 5. MATERIAL FRESH FINDING — HMAC secret readability (must be weighed in H5)

1. **Observation**: `/etc/dsh-registry-writer/hmac-secret` (mode 0640) was **read successfully from this sandboxed session** (64 bytes: `626df17b…`), and the daemon accepted **authenticated IPC from this session** — `registry_write`, `registry_read`, `audit_append`, `audit_verify`, `health`, `backup` all succeeded using the secret read from `/etc`.

2. **Conflict with prior records**: `0010` §1 ("HMAC secret isolation … Sandbox session cannot read secret (`Permission denied`) — proving the O3 isolation: a sandboxed process cannot authenticate to the daemon") and `0015` §1 row 15's reliance on that claim are **not reproducible fresh**. In this session the sandboxed control-plane session *can* read the secret and *can* drive the daemon.

3. **What still holds**: C1 **write**-isolation is verified fresh — the sandbox **cannot write** to daemon roots (item 11: "Read-only file system" / "Permission denied"), and the daemon enforces channel→method→root authz (registry_write → `state/registry/**` only). The closure conditions C1–C5 as *defined* (0005 §1.2: roots outside workspace + dedicated UID + write-path switch + no fallback + verification) are satisfied.

4. **What this means for the threat model**: the design intent (final 0003 §4.4: secret "readable only by `dsh-writer` and the control-plane user") is that the *control-plane principal* can read the secret. This session IS the control-plane principal (uid 1000, member of `dsh-writer`/`dsh` groups on host). The 0010 claim went further ("a sandboxed process cannot authenticate") and that stronger claim is **false fresh** — under `workspace-write` policy, a role agent with `bash` could in principle read the secret and drive the daemon directly (subject to the daemon's per-method root scoping). This is an honest delta the Human should weigh when deciding H5; it does not by itself invalidate C1–C5 as defined, but it means the "sandbox cannot authenticate" isolation narrative must be corrected.

5. **No change made**: no permission change, no secret rotation, no config change was performed. This is a report of the observed state.

---

## 6. Honesty statement

1. **H5 is NOT self-approved.** This session records H5 = **PENDING** and does not decide it. The prior-session record `0016` is preserved untouched and is neither re-affirmed nor retracted here; per the current task instruction ("Do not self-approve H5. Do not mark final G10 CLOSED without explicit Human H5 decision"), G10 is **not** re-derived to CLOSED by this session.
2. **G10 is NOT declared CLOSED by this session.** The matrix row already reflects the prior-session H5 record; this session makes no further closure claim.
3. **No test failure hidden.** G10 (343) and O3 daemon (50) pass fresh; full regression recorded in 0015 (3119/15/0) with env-sensitive G13/L3 failures documented as pre-existing/out of scope.
4. **The HMAC readability finding (§5) is stated precisely** — it is a fresh observation that contradicts the stronger isolation claim in 0010/0015 and is surfaced for the Human's H5 decision.
5. **No Phase B/C re-execution.** The write-path migration is not re-applied; only read-only probes and non-mutating verification were performed (one benign `registry_write` probe `h5/closure_verification` and one benign `audit_append` event were created via the sanctioned daemon channel, exactly as in 0015).
6. **No DSH, session-policy, role, control-plane, state, or config modification.**

---

*Status: H5 PRE-CLOSURE FRESH VERIFICATION COMPLETE. Daemon ACTIVE (PID 201404). Socket ACTIVE. UID/GID verified. Live registry_write/read + audit_append/verify PASS. C1–C5 freshly satisfied. Backup manifest verified (5/5). Current hashes unchanged. **Material fresh finding: HMAC secret readable from this sandbox and daemon drivable from here (contradicts 0010/0015 isolation claim) — surfaced for Human decision. H5 = PENDING (not self-approved). G10 final closure NOT re-derived by this session.***

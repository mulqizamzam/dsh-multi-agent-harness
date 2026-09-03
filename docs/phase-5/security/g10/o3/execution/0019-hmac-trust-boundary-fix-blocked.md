# G10 O3 — HMAC Trust-Boundary Fix: BLOCKED (no host/root access)

- **Milestone**: Phase 5 / G10 O3 — HMAC TRUST-BOUNDARY FIX (execution attempt)
- **Status**: **BLOCKED — host/root access unavailable. No step of the migration was performed.**
- **Date**: 2026-09-01 (this session, fresh probes)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Task rule invoked**: *"If host/root access is unavailable: STOP and report BLOCKED."*
- **Scope**: Rollback snapshot + fresh privilege/write probes only. **No user created, no group changed, no secret rotated, no permission changed, no socket changed, no unit changed, no daemon restart. H5 not self-approved. G10 not closed.**
- **Companion**: `0018-hmac-trust-boundary-root-cause-and-remediation.md` (root cause + operator runbook — unchanged and still authoritative).

---

## 1. Rollback snapshot (captured first, per task requirement)

Captured `2026-09-01T18:48:20+07:00`, **before** any probe. This is the restore reference.

| Item | State |
|---|---|
| `dsh-writer` user | `dsh-writer:x:999:986::/var/lib/dsh-registry-writer:/usr/sbin/nologin` |
| `dsh-control` user | **ABSENT** |
| `dsh-writer` group | `986:administrator` |
| `dsh` group | `985:administrator,dsh-writer` |
| `administrator` id | `uid=1000 gid=1000 groups=1000,4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),100(users),986(dsh-writer),985(dsh)` |
| HMAC secret | `/etc/dsh-registry-writer/hmac-secret` — real `dsh-writer:dsh-writer`, mode **0640**, size 65, mtime `2026-09-01 11:44:02` |
| HMAC secret integrity ref | sha256 prefix `ed5a2ca88113f84b` (**value not recorded**) |
| Socket | `/var/lib/dsh-registry-writer/ipc.sock` — mode **0660**, group `dsh` |
| Daemon root | `/var/lib/dsh-registry-writer` mode **0750**; `/etc/dsh-registry-writer` mode **0755** |
| Service | `active`, `enabled`, **MainPID 201404** |
| Unit files | `dsh-registry-writer.service` + `.d/override.conf` (116 bytes, mtime 17:23) |
| Control-plane client identity (here) | `administrator` uid 1000 — **the same principal as role agents** |

**No restore is required: post-probe state is byte-identical to this snapshot (verified in §4).**

---

## 2. Step 1 — fresh inspection (completed, read-only)

Confirms `0018`: the control-plane client and the role agents are **one OS principal**, `administrator`, and that principal holds `dsh-writer` (986) and `dsh` (985) membership — which is exactly why the `0640` credential and the `0660` socket are both reachable from the agent sandbox.

---

## 3. Steps 2–8 — ALL BLOCKED (every required mutation refused)

### 3.1 Privilege probes

| # | Probe | Result |
|---|---|---|
| 1 | `sudo -n true` | ⛔ `sudo: The "no new privileges" flag is set, which prevents sudo from running as root.` |
| 2 | `sudo -n id` | ⛔ same |
| 3 | `CapEff` | ⛔ `0000000000000000` — **zero effective capabilities** |
| 4 | `groupadd -r dsh-control-probe` | ⛔ `groupadd: Permission denied.` |
| 5 | `useradd -r dsh-control-probe` | ⛔ `useradd: Permission denied.` |
| 6 | `gpasswd -d administrator dsh` | ⛔ `gpasswd: cannot open /etc/gshadow` |
| 7 | `pkexec` | ⛔ absent |
| 8 | `su -c true root` | ⛔ `su: Authentication failure` |
| 9 | `systemctl daemon-reload` | ⛔ `Access denied ... requires interactive authentication` |

### 3.2 Write/mutation probes — mapped to the task's required steps

| Task step | Required mutation | Probe result |
|---|---|---|
| **2** create `dsh-control` | write `/etc/passwd`,`/etc/group` | ⛔ `Read-only file system` (+ `useradd: Permission denied`) |
| **3** run client as `dsh-control` | new unit / service wrapper in `/etc/systemd/system/` | ⛔ `Read-only file system` |
| **4** revoke `administrator` from `dsh-writer`/`dsh` | write `/etc/group`,`/etc/gshadow` | ⛔ `cannot open /etc/gshadow` |
| **5** rotate compromised secret | write `/etc/dsh-registry-writer/` | ⛔ `Read-only file system` |
| **6** minimum secret permissions | `chmod`/`chgrp` on secret | ⛔ `Read-only file system (os error 30)` |
| **7** minimum socket group/perms | `chgrp` socket; `/var/lib/dsh-registry-writer/` | ⛔ `Read-only file system (os error 30)` |
| **8** restart O3 daemon | `systemctl restart` / `stop` | ⛔ `Access denied ... requires interactive authentication` |

**Every one of the seven mutating steps is refused.** Two independent barriers apply: the sandbox mounts the host filesystem **read-only** (`os error 30`), and the process holds **no capabilities** with `no_new_privs` set — so no approval prompt, answerer, or escalation path can grant this. This is a kernel-level bar, not a policy gate.

### 3.3 Steps 9–15 — not reachable

Steps 9–15 (verify new secret readable by `dsh-writer`; `dsh-control` authenticates; sandbox denials; `registry_write`/`audit_append`/`audit_verify` under the new identity; old-HMAC denial; new-HMAC non-exposure) **all presuppose the migration**. With steps 2–8 blocked, they are **UNREACHABLE — not tested, not claimed**.

**No partial migration was attempted.** A partial change (e.g. re-moding the secret without first provisioning `dsh-control`) would have broken the live control-plane write path with no rollback authority to restore it — the exact failure `0018` §3 identified and the task's "do not break IPC authentication" rule forbids.

---

## 4. Zero-drift confirmation (post-probe vs snapshot)

| Item | Snapshot | Now | Drift |
|---|---|---|---|
| Secret owner/group/mode | `dsh-writer:dsh-writer 0640` | `dsh-writer:dsh-writer 0640` | **none** |
| Secret sha256 prefix | `ed5a2ca88113f84b` | `ed5a2ca88113f84b` | **none — not rotated** |
| Secret size/mtime | 65 / `11:44:02` | 65 / `11:44:02` | **none** |
| Socket group/mode | `dsh` / 0660 | `dsh` / 0660 | **none** |
| `dsh-writer` group | `986:administrator` | `986:administrator` | **none** |
| `dsh` group | `985:administrator,dsh-writer` | `985:administrator,dsh-writer` | **none** |
| `dsh-control` | absent | absent | **none — not created** |
| Service / MainPID | `active` / 201404 | `active` / 201404 | **none — not restarted** |
| Probe leftovers in `/etc/dsh-registry-writer/` | — | 0 | **none** |

**Daemon health after all probes:** `status=ok`, `ready=True`, roots `{state/registry, state/projects, audit}` all true; `audit_verify('runtime')` → `{"ok":true,"problems":[]}`. **The daemon was never disturbed.**

---

## 5. Security posture (unchanged — the leak is still open)

| Success criterion (task) | State |
|---|---|
| 1. sandbox secret read = DENIED | ⛔ **STILL READABLE** — not fixed |
| 2. sandbox socket connect = DENIED | ⛔ **STILL CONNECTABLE** — not fixed |
| 3. `dsh-control` authentication = PASS | ⛔ UNREACHABLE — principal does not exist |
| 4. `dsh-writer` daemon access = PASS | ✅ retained (unchanged) |
| 5. `registry_write` = PASS | ✅ (via the leaking grant — not a fixed-state proof) |
| 6. `audit_append` = PASS | ✅ (same caveat) |
| 7. `audit_verify` = PASS | ✅ (same caveat) |
| 8. old HMAC = DENIED | ⛔ old HMAC is **still the live HMAC** — not rotated |
| 9. no credential exposure | ⛔ exposure persists |
| 10. O3/G10 regression green | ✅ O3 daemon 50 · G10 343 · phase5_security 14 · resilience+authorization 223+1s · validate_config 194 · compileall 0 errors |

**The credential remains disclosed to every bash-capable role agent (`{zeko, cto}`).**

---

## 6. Honesty statement

1. **Nothing was changed.** No user, group, secret, mode, owner, socket, unit, config, code, or policy. No restart. Verified byte-identical to the pre-probe snapshot (§4).
2. **No step was faked or partially applied**, and no success was claimed for an unreachable step. Steps 9–15 are reported UNREACHABLE, not PASS.
3. **The secret value appears nowhere** in this document, any log, config, source file, or environment variable. Only a sha256 prefix is recorded, as an integrity reference.
4. **G10 is NOT closed** and **H5 is NOT approved / NOT self-approved.** The fresh confidentiality tests do not pass, so the task's own gate ("do not claim G10 CLOSED until fresh confidentiality tests PASS") forbids closure.
5. **No test was weakened, skipped, or deleted.** All suites were run as-is.
6. **G13 not executed** (remains BLOCKED/OPEN). **L3 not executed** (remains NOT CLAIMED). **No DSH core, session policy, or role authority change.**

---

*Status: BLOCKED — host/root access unavailable (read-only host filesystem + `CapEff=0` + `no_new_privs`; sudo/su/pkexec/systemctl all refused). Rollback snapshot captured; zero drift; daemon healthy on original PID 201404. All 7 mutating steps refused; verification steps 9–15 unreachable. HMAC leak REMAINS OPEN. secret confidentiality = FAIL. G10 = NOT CLOSED. H5 = PENDING.*

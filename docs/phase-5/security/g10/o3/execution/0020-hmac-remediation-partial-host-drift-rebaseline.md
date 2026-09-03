# G10 O3 — HMAC Remediation PARTIALLY APPLIED by Operator: Host Drift Rebaseline

- **Milestone**: Phase 5 / G10 O3 — FRESH MASTER REBASELINE after operator host mutation
- **Status**: **CREDENTIAL CONFIDENTIALITY = PASS (leak CLOSED). CONTROL-PLANE WRITE PATH = DOWN (fail-closed). G10 = NOT CLOSED — C3/C5 no longer re-derivable. H5 approval SUPERSEDED by drift.**
- **Date**: 2026-09-01T19:03–19:20 +07 (this session, fresh probes only)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Read-only host/daemon/write-path probes + deterministic test execution. **No user created, no group changed, no secret written, no permission changed, no socket changed, no unit changed, no daemon restart, no test weakened, no DSH/session-policy/role change. H5 not re-approved, not retracted. G10 not closed.**
- **Supersedes**: `0019-hmac-trust-boundary-fix-blocked.md` §1 snapshot and §5 posture table — **the host changed after `0019` was written.** `0019`'s own probe record remains factually correct *for its timestamp* (18:48–18:50) and is preserved. `0018` root-cause analysis remains correct and is **now confirmed by the operator's fix matching its §4.4 runbook**.
- **Companion**: `0018` (root cause + operator runbook) · `0019` (blocked-execution record, now superseded on state)

---

## 1. Drift detection (the first material finding of this session)

`0019` recorded, at `2026-09-01T18:48:20+07:00`, that **no** remediation step had been performed. Fresh probes at **19:03** show the host has changed. The mutation was performed by an authority outside this session — **not by this agent, and not by any agent action recorded in this workspace.**

| Item | `0019` snapshot (18:48) | Fresh observation (19:03) | Drift |
|---|---|---|---|
| `dsh-control` user | **ABSENT** | `dsh-control:x:997:984::/nonexistent:/usr/sbin/nologin` | **CREATED** |
| `dsh-control` group | absent | `dsh-control:x:984:dsh-control` | **CREATED** |
| Secret owner:group | `dsh-writer:dsh-writer` | `dsh-writer:dsh-control` | **CHANGED** |
| Secret mode | `0640` | `0640` | unchanged |
| Secret mtime | `2026-09-01 11:44:02` | `2026-09-01 18:53:05.300162076` | **REWRITTEN** |
| Secret size / inode | 65 / — | 65 / `31422` | size unchanged |
| `dsh` group members | `administrator,dsh-writer` | `dsh-writer` | **`administrator` REVOKED** |
| `dsh-writer` group members | `administrator` | *(empty)* | **`administrator` REVOKED** |
| Daemon root `/var/lib/dsh-registry-writer` | `0750` (owner:group not recorded) | `dsh-writer:dsh-control 0750` | **REGROUPED** |
| Service / MainPID / NRestarts | `active` / 201404 / — | `active` / **201404** / **0** | **NOT restarted** |
| Live daemon config `socket_group` | `dsh` | `dsh` | **unchanged** |

**Independent corroboration of the group revocation** (not inference — the shadow-suite backup files record the prior generation):

```
/etc/group-  (prior) : dsh:x:985:administrator,dsh-writer
/etc/group   (current): dsh:x:985:dsh-writer
```

`/etc/passwd-`, `/etc/group-`, `/etc/gshadow-`, `/etc/shadow` all carry mtime `2026-09-01 18:53` — consistent with a single `useradd`/`groupadd`/`gpasswd` operator transaction at that time.

**Evidence class:** the ownership/mode/membership facts are **F (directly observed)**. The claim that the secret *value* was rotated to a new random value is **I (inference)** — `mtime` advanced by 7h09m while `ctime` advanced only 16ms past it, which a pure `chown`/`chmod` cannot produce (those move `ctime` only), so a **write occurred**; but the content is unreadable from this principal, so *what* was written cannot be verified here. It is recorded as inference, never as proof.

**Correlation:** the applied change matches `0018` §4.4 steps 1–3 (create `dsh-control`; rotate + `chown dsh-writer:dsh-control`; revoke `administrator` from `dsh-writer` and `dsh`) and `0018` §4.2. Steps **4** (socket group → `dsh-control` + daemon reload/restart) and **5** (run the control plane as `dsh-control`) were **NOT** applied.

---

## 2. Success criteria from the remediation task — fresh, honest re-evaluation

All probes run this session as `administrator` uid 1000 (the same OS principal as every sandboxed role agent, including the `bash`-capable `{zeko, cto}`).

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Sandbox **cannot read** the secret | ✅ **PASS** | `cat /etc/dsh-registry-writer/hmac-secret` → `Permission denied`; `dd`/`sha256sum` likewise. Mechanism: uid 1000 ≠ owner 999, and 1000 ∉ `dsh-control`(984). |
| 2 | Sandbox **cannot connect** the socket | ✅ **PASS** | `socket.connect('/var/lib/dsh-registry-writer/ipc.sock')` → `PermissionError [Errno 13]`. Mechanism: `/var/lib/dsh-registry-writer` is `dsh-writer:dsh-control 0750` — **directory traversal** is denied, so the socket is unreachable regardless of its own mode. |
| 3 | `dsh-control` **can authenticate** | ⛔ **UNREACHABLE — NOT TESTED, NOT CLAIMED** | No `dsh-control` execution path exists: no systemd unit (only `dsh-registry-writer.service`), no wrapper in `/usr/local/bin`, no `sudoers.d` rule, no polkit rule. `sudo -n -u dsh-control`, `su dsh-control`, `setpriv --reuid=997` all refused (see §4). |
| 4 | `dsh-writer` (daemon) retains access | 🟡 **PARTIAL / INFERRED** | Service `active`, socket present in `/proc/net/unix`. But the daemon's **in-memory** secret predates the rotation (§3), so "retains access" is true only of the *old* credential. |
| 5 | `registry_write` works | ⛔ **FAIL (fail-closed)** | `control.execution_gate.registry_write(...)` → `WriterUnavailable: cannot read daemon HMAC secret … Permission denied`. |
| 6 | `audit_append` works | ⛔ **FAIL (fail-closed)** | same `WriterUnavailable`. |
| 7 | `audit_verify` works | ⛔ **FAIL (fail-closed)** | same `WriterUnavailable`. |
| 8 | Old HMAC **denied** | ⛔ **UNKNOWN — cannot be tested** | The old credential value was never recorded (correctly). The daemon still holds the pre-rotation secret in memory (§3), so the old credential is very likely still the *accepted* one — the opposite of the criterion. Recorded UNKNOWN, never PASS. |
| 9 | No credential exposure | ✅ **PASS** | Secret unreadable from the sandbox; no value in any document, log, config, source file, or environment variable in this workspace. |
| 10 | O3/G10 regression green | ✅ **PASS** (with one honesty-gate failure caused by doc/state divergence, §6) | O3 daemon **50 passed** · G10 **339 passed, 4 skipped** · phase5_security **14 passed** · l3_runner+l3_reference **592 passed** · `validate-config` **194 passed, 0 failed** · `compileall` exit 0 · full suite **3114 passed, 1 failed, 19 skipped**. |

**Net security effect: the credential leak identified in `0018` is CLOSED.** The two confidentiality properties that failed in `0019` (§5 rows 1–2) now pass, and they pass by kernel-enforced uid/gid denial — the same mechanism that denies `/etc/shadow` — not by any project-layer control.

---

## 3. New material finding: the daemon holds a stale in-memory credential

This was not present in any prior record and is decision-critical for the operator.

| Fact | Value | Source |
|---|---|---|
| Daemon process start | `Tue 2026-09-01 17:24:58 +07` (PID 201404) | `systemctl show -p ExecMainStartTimestamp`; `ps -o lstart -p 201404` |
| `NRestarts` | **0** | `systemctl show -p NRestarts` |
| Secret file rewritten | `2026-09-01 18:53:05` | `stat` mtime |
| Secret load sites in code | **1**, in `RegistryWriterDaemon.__init__` → `_load_secret()` | `registry_writer/daemon.py:239,243` |
| `SIGHUP` / reload handlers | **none** (`__main__.py` handles only `SIGTERM`/`SIGINT`) | `registry_writer/__main__.py:107-108`; grep across `registry_writer/` |

The secret is read **once at construction** and there is no re-read path. The file was rewritten **88 minutes after** the daemon started, with **zero restarts**. Therefore the running daemon authenticates against the **pre-rotation** secret, while the on-disk file holds the **post-rotation** value.

**Consequence:** even once a `dsh-control` principal exists and can read the new file, HMAC authentication will **fail** (`AUTH_FAILED`) until the daemon is restarted. Rotation is not complete until the daemon reloads. This is an operator action.

**Second gap, independent of the first:** the live daemon config still specifies `socket_group: dsh` (gid 985) at `/etc/dsh-registry-writer/registry-writer.yaml`. `dsh-control`'s only group is 984. A process running as `dsh-control` would be able to *traverse* the `0750` daemon root (it is the directory's group) but would still be **denied connect** on a `0660 root:dsh` socket. `0018` §4.4 step 4 (`socket_group: dsh-control` + restart) is required for the control plane to reach the daemon at all.

---

## 4. Privilege probes (fresh — every mutating path still refused)

| Probe | Result |
|---|---|
| `sudo -n true` | ⛔ `sudo: interactive authentication is required` |
| `sudo -n -l` | ⛔ same |
| `sudo -n -u dsh-control id` | ⛔ same |
| `su -s /bin/sh dsh-control -c id` | ⛔ `su: Authentication failure` |
| `setpriv --reuid=997 --regid=984 --clear-groups id` | ⛔ `setresuid failed: Operation not permitted` |
| `CapEff` | ⛔ `0000000000000000` |
| `systemctl daemon-reload` / `restart` | ⛔ `Access denied … requires interactive authentication` |
| `touch /etc/dsh-registry-writer/.p` | ⛔ `Permission denied` (dir is `dsh-writer:dsh-writer 0755`) |
| `/etc/sudoers.d/` | only a root-only `README`; no rule grants anything |
| `pkexec` / polkit rules mentioning dsh | absent |

Note a difference from `0019`: the root filesystem is mounted `rw` this session (`findmnt -no OPTIONS /` → `rw,relatime,…`), so `0019`'s `Read-only file system (os error 30)` no longer applies. The refusals are now **ordinary POSIX permission denials plus `CapEff=0`** — a weaker-looking but equally effective bar. `NoNewPrivs` is now `0` (was set in `0019`), which does not help: `sudo` requires interactive authentication that this session cannot supply (approval prompts are disabled), and `setpriv` needs `CAP_SETUID` which is absent.

**This agent performed no mutation. Verified: no user, group, secret, mode, owner, socket, unit, config, code, test, or policy was changed by this session; the daemon was not restarted and remains on its original PID 201404 with `NRestarts=0`.**

---

## 5. Effect on C1–C6 — fresh derivation (not copied from `0015`/`0016`)

| Condition | `0016`/H5 basis | Fresh state (19:03) | Verdict |
|---|---|---|---|
| **C1** A+B isolation (roots outside workspace + dedicated UID) | PASS | **PASS, and now stronger.** Write probes into all four daemon roots (`state/registry`, `state/projects`, `audit`, `backup`) → DENIED; root listing → DENIED; **credential confidentiality sub-property now PASSES** (was FAIL in `0018`/`0019`). | ✅ **PASS** |
| **C2** `state/projects/**` extension | PASS | Unchanged — daemon config and code still own all three roots. Not re-derivable *operationally* (see C5) but no drift in code/config. | ✅ PASS (static) |
| **C3** write path fully switched, no direct-write reachable | PASS | Static property **holds** (only daemon-client calls; `compileall` clean; 339 G10 tests pass). **But the switched path is now non-functional from the control plane**: `registry_write`/`audit_append`/`project_write`/`audit_verify` all raise `WriterUnavailable`. The path is switched *to a destination the control plane can no longer reach.* | 🟡 **PARTIAL — not operationally re-derivable** |
| **C4** no silent fallback | PASS | ✅ **PASS, positively demonstrated by the outage.** With the credential unreadable, every sanctioned channel returned `WriterUnavailable` and **no** write landed by any other route. This is the fail-closed invariant behaving exactly as designed, observed in production configuration rather than in a fixture. | ✅ **PASS (strengthened)** |
| **C5** verification passes (incl. live operational verification) | PASS — `0016` §3 recorded live `health`, `registry_read`, `audit_verify('runtime')`, `audit_verify('_daemon')` via daemon IPC | ⛔ **NOT RE-DERIVABLE.** Every live daemon observation that `0016` §3 rows 2–4 relied on now fails from this principal: `health` → `WriterUnavailable`, `registry_read` → `WriterUnavailable`, `audit_verify` → `WriterUnavailable`. Deterministic suites remain green (§2 row 10), but the **live** arm of C5 cannot be reproduced by any principal available here. | ⛔ **FAIL (not re-derivable)** |
| **C6** Human approval H3+H4+H5 | H5 APPROVED 2026-09-01 (`0016`) | The Human decision is **preserved and not retracted**. However `0016` §2 states H5 means "C1, C2, C3, C4, C5 verified by the evidence package". C3 is PARTIAL and C5 is not re-derivable **after** that decision, so the factual basis the approval rested on no longer holds in full. | 🟡 **APPROVAL VALID / BASIS SUPERSEDED** |

### 5.1 G10 verdict

**G10 = NOT CLOSED.**

The G10 closure gate (`0005` §1.2) requires **all six** conditions to hold simultaneously. C5's live arm is not re-derivable and C3 is only partially satisfied, so the conjunction fails. Per `0005` §1.4 ("O3 implemented but the acceptance suite has failures — verification is incomplete; no closure claim permitted"), the correct record is **NOT CLOSED**, pending operator completion of the remediation and fresh re-verification.

**This is not a retraction of H5.** H5 remains an explicit, recorded Human decision (`0016`). What changed is the *state* it described: the credential leak found in `0018` after the approval, and the operator's partial fix at 18:53 which closed that leak while disabling the control-plane write path. The honest classification is **supersession of the evidence basis**, recorded here and in the closure matrix, with all historical records preserved.

**Direction of travel matters and should not be lost:** on the security axis the posture is now **better** than at H5 — the credential leak that `0018` proved (and which was open at the time H5 was granted) is closed. The failure is on the **availability/verifiability** axis, and it is one operator transaction away from resolution.

---

## 6. The one failing test — cause, and why it is not weakened

Full-suite result: **3114 passed, 1 failed, 19 skipped** (244s).

```
FAILED tests/g13/gate/test_g13_live_recheck.py::TestG13RecheckAxes::test_axis_11_g10_open_blocking
AssertionError: G10 no longer recorded as OPEN in closure matrix — re-assess
```

This is an **honesty gate firing correctly.** It asserts that the G10 row of `docs/phase-5/final/0001-security-closure-matrix.md` records `**OPEN**`, and it began failing when that row was set to `**CLOSED**` by the H5 update. Its message is an instruction: *re-assess.*

The re-assessment is §5 of this document, and it concludes **G10 = NOT CLOSED**. The resolution is therefore to **correct the document to match verified reality** — the closure matrix G10 row returns to a non-closed status with an explicit supersession addendum. The test is **not modified, not skipped, not weakened, and not deleted.** `recheck_verdict()`'s `g10_blocking = True` (`tests/g13/gate/test_g13_live_recheck.py:82`) is likewise left untouched and is now consistent with the matrix again.

---

## 7. Exact operator actions required to close G10

All five must be performed by root; none is executable from this session. Order matters.

```bash
# 1. Point the socket at the control-plane principal (currently socket_group: dsh)
sudo sed -i 's/^  socket_group: dsh$/  socket_group: dsh-control/' \
    /etc/dsh-registry-writer/registry-writer.yaml

# 2. Restart the daemon — MANDATORY: it still holds the pre-rotation secret
#    in memory (started 17:24:58, secret rewritten 18:53:05, NRestarts=0,
#    and there is no SIGHUP reload path in registry_writer/).
sudo systemctl restart dsh-registry-writer.service
sudo systemctl is-active dsh-registry-writer.service      # expect: active

# 3. Provide an execution path for the control plane as dsh-control.
#    Either a systemd unit, or an audited least-privilege sudo rule, e.g.:
#      /etc/sudoers.d/dsh-control:
#      administrator ALL=(dsh-control) NOPASSWD: /path/to/control-plane-entrypoint
#    The role-agent sandbox must NOT be able to invoke it as an arbitrary
#    command, or the two-principal separation is defeated again.

# 4. Verify the control plane authenticates under the NEW credential:
sudo -u dsh-control /path/to/venv/python -c "..."   # health / registry_write / audit_append / audit_verify

# 5. Re-verify the role-agent-equivalent denials FROM the agent sandbox
#    (both currently PASS and must be re-confirmed after the change):
cat /etc/dsh-registry-writer/hmac-secret            # expect: Permission denied
python3 -c "import socket; socket.socket(socket.AF_UNIX,socket.SOCK_STREAM).connect('/var/lib/dsh-registry-writer/ipc.sock')"
                                                     # expect: PermissionError
```

Then re-run, and only then re-assess C3/C5: `tests/g10/` (339) · `tests/g10/o3-daemon/` (50) · `tests/phase5_security/` (14) · `tests/validate-config.py` (194) · `compileall` · full suite.

**Design note for step 3 (the trap in this remediation):** the point of `dsh-control` is that it is *not* reachable from the role-agent sandbox. A blanket `sudo -u dsh-control ANY_COMMAND` rule granted to `administrator` would let `{zeko, cto}` re-acquire the credential through `sudo`, restoring the exact leak `0018` diagnosed. The sudo rule (or unit) must expose **only** the control-plane entrypoint.

---

## 8. Honesty statement

1. **This session changed nothing on the host.** No user, group, secret, mode, owner, socket, unit, config, code, test, or policy. No daemon restart. Daemon remains PID 201404, `NRestarts=0`.
2. **The host change at 18:53 was not made by this agent** and is not claimed as this session's work. It is recorded as observed operator drift, with `/etc/group-` as independent corroboration.
3. **No unreachable step is reported as PASS.** Criteria 3 and 8 are UNREACHABLE/UNKNOWN. C5's live arm is FAIL (not re-derivable), not "PASS by prior evidence".
4. **Rotation of the secret *value* is recorded as inference (I), not fact (F).** The content is unreadable from this principal; only `mtime`/`ctime`/`size`/`inode` were observed. No secret value appears in this document or anywhere in this workspace.
5. **H5 is neither self-approved nor retracted.** It is preserved as a Human decision whose factual basis is superseded on C3/C5.
6. **No test was weakened, skipped, or deleted.** The single failure is reported as a failure and resolved by correcting the document, not the assertion.
7. **G13 not executed** (pre-gate fails; remains OPEN/UNKNOWN). **L3 not claimed** (`l3_claim_possible=False`). **No DSH core, session-policy, or role change.** **Production readiness NOT declared.**

---

*Status: HOST DRIFT DETECTED AND REBASELINED. Operator applied `0018` §4.4 steps 1–3 at 18:53 (create `dsh-control`, rewrite+regroup secret, revoke `administrator` from `dsh`/`dsh-writer`); steps 4–5 NOT applied. Credential confidentiality = **PASS** (leak CLOSED — sandbox secret read DENIED, socket connect DENIED). Control-plane write path = **DOWN**, fail-closed (`WriterUnavailable` on all sanctioned channels). Daemon holds **pre-rotation** secret in memory (0 restarts, no reload path). C1 PASS · C2 PASS (static) · C3 PARTIAL · C4 PASS (strengthened) · C5 **FAIL — live arm not re-derivable** · C6 approval preserved, basis superseded. **G10 = NOT CLOSED.** H5 preserved, not retracted. Regression 3114 passed / 1 failed / 19 skipped — the single failure is the G10-OPEN honesty gate firing correctly and is resolved by correcting the closure matrix, not the test.*

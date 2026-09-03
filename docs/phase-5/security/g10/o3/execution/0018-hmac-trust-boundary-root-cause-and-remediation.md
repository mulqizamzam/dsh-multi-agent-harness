# G10 O3 — HMAC Credential Trust-Boundary Leak: Root Cause + Remediation Design (BLOCKED on operator)

- **Milestone**: Phase 5 / G10 O3 — HMAC SECRET TRUST-BOUNDARY REMEDIATION
- **Status**: **ROOT CAUSE ESTABLISHED. REMEDIATION SPECIFIED. NOT APPLIED — BLOCKED on root/operator action.**
- **Date**: 2026-09-01 (this session, fresh probes)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Read-only inspection + remediation design + operator runbook. **No file mode changed, no group changed, no config changed, no code changed, no daemon restart, no secret rotation, no DSH/session-policy/role change. H5 not self-approved. G10 not closed.**
- **Supersedes**: `0017-h5-fresh-verification-session.md` §5 — its stated cause (namespace group-mapping) is **WRONG** and is corrected here.

---

## 1. ROOT CAUSE (proven by differential test, not inferred)

**The leak is a credential-provisioning defect, not a sandbox/namespace defect.**

Last session's record attributed the read to the sandbox mapping the file's group to `nogroup` (65534), which the sandbox process also carries. **That hypothesis is disproved:** if it were true, every `0640` file displaying as `nobody:nogroup` would be readable. It is not.

| File | Displayed in sandbox | Real host group | `administrator` in group? | Read result |
|---|---|---|---|---|
| `/etc/dsh-registry-writer/hmac-secret` | `nobody:nogroup 640` | `dsh-writer` (986) | **YES** | ✅ **READABLE** |
| `/etc/shadow` | `nobody:nogroup 640` | `shadow` | NO | ⛔ DENIED |
| `/etc/gshadow` | `nobody:nogroup 640` | `shadow` | NO | ⛔ DENIED |
| `/etc/sudoers` | `nobody:nogroup 440` | `root` | NO | ⛔ DENIED |

Identical display, opposite outcome. The kernel evaluates the **real host uid/gids**; the `nobody:nogroup` rendering is only a namespace *display* artifact. `getent` confirms the decisive fact:

```
dsh-writer:x:986:administrator          <-- administrator IS a member
dsh:x:985:administrator,dsh-writer      <-- administrator IS a member
shadow: (administrator absent)
```

**Root cause:** the operator granted `administrator` membership in `dsh-writer` (and `dsh`), and the credential is mode `0640` group `dsh-writer`. Every process running as `administrator` therefore holds group-read on the daemon credential. **Every sandboxed role agent runs as `administrator`.** Roles `zeko` and `cto` hold `bash` (verified: `bash`/`write`/`edit` all present in their allow sets), so both can read the credential and drive sanctioned O3 IPC as if they were the control plane.

The sandbox neither causes nor mitigates this: uid/gids inside the sandbox are the host's, and `/etc` is bind-mounted readable.

---

## 2. TRUST BOUNDARY (from FINAL architecture, and where it breaks)

Intended (FINAL `0001` §4.2/§4.3/§4.4):

| Principal | Credential | Socket | Daemon roots |
|---|---|---|---|
| `dsh-writer` (daemon) | read (owner) | owns | owns, sole writer |
| control-plane client | read (group) | connect (group `dsh`) | none — IPC only |
| session tools incl. `{zeko, cto}` | **none** | **none** | **none** |

§4.4 is explicit: *"session tools, including `{zeko, cto}`, must never be able to read it."*
§4.3 rests on: *"A session actor in the workspace is **not** in the `dsh` group and has **no** access to the shared secret."*

**The breaking assumption:** the design treats "control-plane client" and "session actor" as two OS principals. **On this host they are one principal — `administrator` (uid 1000).** The Front Door E2E driver (`runs/bagian1/run.py`) executed as a *sandboxed* `python` process and successfully performed `registry_write`/`audit_append`, reading the credential from inside the sandbox. Role agents occupy that same sandbox with the same uid and same groups.

**Consequence — the decisive constraint on remediation:** because the client and the role agents are the same OS principal with identical filesystem exposure, **no file mode, ACL, group redesign, or sandbox mask can admit the client while excluding `{zeko, cto}`.** Any credential the client can read, a bash-capable role agent can read.

---

## 3. Option assessment (all four fail as stated, for one shared reason)

| Option | Verdict | Why |
|---|---|---|
| **A** — daemon-only secret + different credential exchange "already supported by the design" | ❌ **No such mechanism exists** | `SO_PEERCRED` yields uid/gid only → client and role agent are identical (both 1000:1000). FD-inheritance and environment are equally inherited by role-agent shells, and env is forbidden by the task. |
| **B** — ACL/group redesign | ❌ **Impossible as stated** | An ACL or group naming the client necessarily names `administrator`, which *is* the role agents. |
| **C** — sandbox isolation of `/etc/dsh-registry-writer` | ❌ Out of scope + insufficient | Requires a DSH-core/sandbox change (forbidden here); and because the client is co-resident in that sandbox, masking blocks the client too. |
| **chmod 0600** alone | ❌ Explicitly rejected | Effective against role agents (uid 1000 ≠ owner 999, no group bits — the `/etc/shadow` control proves owner/group denial works against this sandbox), **but equally denies the client** → breaks IPC auth. This is the failure mode the task names. |

**The gap cannot be closed by permissions alone. It requires decoupling the control-plane principal from the session principal.**

---

## 4. SELECTED REMEDIATION (design; requires operator + Human)

Two components, strictly in order. Component 1 is a deployment/architecture change and is the prerequisite; component 2 is the permission fix that is only safe *after* it.

### 4.1 Component 1 — decouple the control plane from the session principal
Run the code path that calls `execution_gate.registry_write` / `audit_append` / `project_write` as a **dedicated OS user `dsh-control`**, not as the session user, and not reachable from a role agent's sandbox. This restores the two-principal premise the architecture already assumes; it changes no O3 mechanism.

### 4.2 Component 2 — restrict the credential to daemon + control plane
Credential → `dsh-writer:dsh-control 0640`; **revoke `administrator` from `dsh-writer` and `dsh`**; socket group → `dsh-control`.

Result: daemon reads as owner; `dsh-control` reads via group; role agents running as `administrator` are denied at the kernel level — exactly as `/etc/shadow` is denied today. **HMAC signing, replay window, and nonce dedup are untouched.**

### 4.3 Credential must be treated as compromised
The current secret has been disclosed to any bash-capable role agent for the lifetime of the present provisioning. Remediation **must include rotation** (FINAL §4.4 rotation procedure), not merely re-permissioning.

### 4.4 Operator runbook (root; not executable from this session)

```bash
# 1. Dedicated control-plane principal (NOT the session user)
sudo groupadd -r dsh-control
sudo useradd -r -g dsh-control -s /usr/sbin/nologin -d /nonexistent dsh-control

# 2. Rotate the disclosed credential + restrict to daemon + control plane
sudo -u dsh-writer sh -c 'umask 077; head -c 32 /dev/urandom | xxd -p -c 32 \
    > /etc/dsh-registry-writer/hmac-secret.new'
sudo mv /etc/dsh-registry-writer/hmac-secret.new /etc/dsh-registry-writer/hmac-secret
sudo chown dsh-writer:dsh-control /etc/dsh-registry-writer/hmac-secret
sudo chmod 0640 /etc/dsh-registry-writer/hmac-secret

# 3. Revoke the session principal's inherited access  <-- closes the actual leak
sudo gpasswd -d administrator dsh-writer
sudo gpasswd -d administrator dsh

# 4. Socket reachable only by the control plane
#    set daemon.socket_group: dsh-control in /etc/dsh-registry-writer/registry-writer.yaml
sudo systemctl daemon-reload && sudo systemctl restart dsh-registry-writer.service

# 5. Run the control plane as dsh-control (systemd unit / service wrapper),
#    NOT from the agent session sandbox.
```

### 4.5 Verification after the fix

```bash
# daemon retains access + serves
systemctl is-active dsh-registry-writer.service
# control plane authenticates (as dsh-control, off-sandbox)
sudo -u dsh-control python3 -c "..."   # health / registry_write / audit_append / audit_verify
# role-agent-equivalent is denied (run from the agent sandbox):
cat /etc/dsh-registry-writer/hmac-secret     # expect: Permission denied
python3 -c "socket.connect('/var/lib/dsh-registry-writer/ipc.sock')"  # expect: Permission denied
# then: tests/g10/o3-daemon/ (50), tests/g10/ (343), tests/phase5_security/ (14),
#       validate_config (194), compileall
```

---

## 5. Why nothing was applied here (blocking evidence, this session)

| Required action | Attempt | Result |
|---|---|---|
| `chmod` the credential | `chmod 0600 /etc/dsh-registry-writer/hmac-secret` | ⛔ `Read-only file system (os error 30)` |
| Write into `/etc/dsh-registry-writer/` | `touch .../probe` | ⛔ `Read-only file system` |
| Restart the daemon | `systemctl restart dsh-registry-writer` | ⛔ `Access denied ... requires interactive authentication` |
| Escalate to root | `sudo -n true` | ⛔ `"no new privileges" flag is set` (kernel bar, not a policy gate) |
| Write daemon root | `touch /var/lib/dsh-registry-writer/.wprobe` | ⛔ NOT-WRITABLE |

Every candidate remediation — re-mode, re-own, group revocation, ACL, relocation, unit change, rotation — is a root/host operator action. **No interim containment is available from this session either:** rotating the disclosed secret also requires writing `/etc`. The `no_new_privs` bar means no approval prompt can grant this.

---

## 6. Effect on C1–C5 and H5

| Item | Fresh state |
|---|---|
| **C1** isolation | **PARTIAL** — *write*-path isolation holds (sandbox cannot write daemon roots; `state/registry` subtree `0700` denies traversal). **Credential confidentiality sub-property FAILS**, so a bash-capable role agent can drive sanctioned IPC as the control plane. |
| **C2** projects extension | PASS (unchanged) |
| **C3** write path switched | PASS (unchanged) |
| **C4** no silent fallback | PASS mechanically — but its guarantee is weakened in combination with the credential leak (an unauthorized principal can satisfy the sanctioned channel). |
| **C5** verification | PASS as re-run this session: O3 daemon 50, G10 343, phase5_security 14, validate_config 194, compileall 0 errors. |
| **secret confidentiality** | ⛔ **FAIL** |
| **C6 / H5** | 🟡 **PENDING — not decided, not self-approved.** |

**C1–C5 are NOT re-derived as "all satisfied", and no H5 evidence package is re-prepared** — the task gates both on a completed fix, which does not exist. **G10 must not be recorded CLOSED on the strength of the present provisioning.**

---

## 7. Honesty statement

1. **Nothing was changed.** No mode, owner, group, ACL, config, code, unit, secret, or policy. No daemon restart. Only read-only probes plus already-sanctioned `health` / `audit_verify` calls and one deliberately-failing auth attempt.
2. **Prior record corrected.** `0017` §5 attributed the leak to namespace group-mapping; the `/etc/shadow` differential disproves that. The cause is real host group membership plus mode `0640`. The correction matters: it changes the fix from "mask `/etc` / trust `0600`" to "revoke the group grant *and* decouple the control-plane principal".
3. **The credential is disclosed**, not merely mis-permissioned. Rotation is mandatory.
4. **No option was adopted as-written.** A, B, C and bare `chmod 0600` each fail against the same shared-principal constraint; the specified remediation adds the missing prerequisite (`dsh-control`) instead of pretending permissions suffice.
5. **No secret value is recorded in this document, any log, config, source file, or environment variable.**
6. **H5 not self-approved. G10 not closed. G13 untouched (remains BLOCKED/OPEN). L3 untouched (NOT CLAIMED).**

---

*Status: ROOT CAUSE ESTABLISHED (real group membership `administrator ∈ dsh-writer` + mode 0640 — namespace hypothesis disproved). Client and role agents are ONE OS principal, so no permission-only fix exists. REMEDIATION SPECIFIED (dedicated `dsh-control` principal + rotate + restrict + revoke group grant). NOT APPLIED — BLOCKED on root/operator. secret confidentiality = FAIL. C1 = PARTIAL. H5 = PENDING. G10 = NOT CLOSED.*

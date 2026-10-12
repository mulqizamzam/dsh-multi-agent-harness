# G10 O3 — Item 1–3: Human Approvals + Infrastructure Provisioning + Exact Requirements

- **In**: `docs/phase-5/security/g10/o3/execution/` (part of the execution-readiness package)
- **Companion**: `0001` (master handoff, current state, evidence matrix) · `0003` (backups, freeze, migration) · `0004` (acceptance, rollback) · `0005` (closure gate, evidence matrix)
- **Status**: OPERATOR CHECKLIST (exact, actionable). **No provisioning was performed this session.** All commands below are **prescribed for the operator** — documented, not executed.

---

## 1. Human approvals required (item 1)

### 1.1 Approval table (from decision package §3, authoritative)

| # | Decision | Scope | Enables | Status |
|---|---|---|---|---|
| **H3** | **Approve O3** — dedicated registry/audit/projects writer daemon (ADR 0002 consequence 4 infrastructure change) | Authorizes implementation + deployment of the daemon + A+B isolation + out-of-workspace root + dedicated UID + IPC + HMAC authn + fail-closed | All implementation steps (daemon, config, client, deployment, acceptance) | **REQUIRED — OPEN** |
| **H4** | **Approve the `state/projects/**` scope extension** (beyond ADR 0002 consequence 4's registry/audit description) | Without it, `state/projects/**` remains CAS-detected only and R is not closed for that root | Migration Phase B write-path switch for `state/projects/**` | **REQUIRED — OPEN** |
| **H5** | **Approve G10 closure** (post-implementation, post-verification) | The only actor that may decide closure; no test or session decides it | G10 matrix row re-derived to CLOSED | **DEFERRED** (only after implementation + verification + re-derived residual) |

**H1** (accept G10 residual — DONE) and **H2** (approve O5 — DONE) are pre-existing and not re-opened by this package.

### 1.2 Approval recording procedure

Each approval must be recorded as a committed evidence artifact:

1. **Approval record format:** a signed/audited document (or a DSH approval event) recording the Human decision, date, scope, and the session identifier.
2. **Location:** `docs/phase-5/security/g10/implementation/backups/o3-pre/` (same convention as the O5 approval record `0002-o5-application-record.md`).
3. **Gate:** H3 and H4 must be committed **before** any implementation step (daemon code, provisioning, config creation). H5 is deferred — see `0005` §1.
4. **No implementation step may proceed without H3+H4.** This is a hard gate: no daemon code, no infrastructure provisioning, no config creation, no migration.

### 1.3 Approval answerer availability (session-dependence note)

The current session has `DSH_WEB_URL=http://127.0.0.1:13080` (web GUI present). The approval answerer is available by composition (L3ENV-ANS-1/2 PASS per the reconciliation report). However, the operator should verify the answerer is live **at the time of recording** using:

```bash
# Verify web GUI is reachable (approval answerer composed)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:13080
# Expected: 200
```

If the web GUI is not reachable, approvals must be recorded via an alternative channel (pre-signed approval references or headless answerer row) per the approval-path readiness docs.

---

## 2. Infrastructure provisioning checklist (item 2)

### 2.1 Prerequisites (P1–P9) — current status

| # | Prerequisite | Current status | Operator action required |
|---|---|---|---|
| **P1** | Dedicated OS user `dsh-writer` | **UNMET — BLOCKED** (user does not exist) | `useradd --system --home-dir /var/lib/dsh-registry-writer --shell /usr/sbin/nologin dsh-writer` |
| **P2** | Out-of-workspace daemon root (`/var/lib/dsh-registry-writer/`) | **UNMET — BLOCKED** (path does not exist) | `mkdir -p /var/lib/dsh-registry-writer/... + chown/chmod` |
| **P3** | systemd unit `dsh-registry-writer.service` | **UNMET — BLOCKED** (unit absent) | Create unit file at `/etc/systemd/system/dsh-registry-writer.service`; `systemctl daemon-reload` |
| **P4** | Shared HMAC-SHA256 secret | **UNMET — BLOCKED** (secret not provisioned) | Generate + deploy to `0600` file outside workspace |
| **P5** | Control-plane group `dsh` | **UNMET — BLOCKED** (group does not exist) | `groupadd dsh`; add control-plane user to `dsh` group |
| **P6** | Pre-change file-level backups + SHA-256 | **UNMET — BLOCKED** (nothing applied yet; procedure in `0003` §1) | Execute the backup procedure **before Phase B** |
| **P7** | Maintenance/freeze window for Phase B | **UNMET — BLOCKED** (operator scheduling) | Schedule + announce + execute the freeze window per `0003` §2 |
| **P8** | Reusable modules (`state/helpers/*`, `audit/helpers/*`) | **MET — CLOSED** (present, importable, reused-by-design) | **None** — confirmed this session |
| **P9** | Human approvals H3 + H4 (item 1 above) | **UNMET — BLOCKED** | Record approvals per §1.2 |

### 2.2 Who does what

| Role | Actions |
|---|---|
| **Human (decision-maker)** | Records H3, H4, H5 (deferred) — signs the approval record |
| **Operator (on-host, root)** | Provisions P1, P2, P3, P4, P5, P7 (requires root — `sudo`, `systemctl`, `useradd`, `groupadd`, file creation outside the workspace) |
| **Engineering (in-workspace, DSH session)** | Implements the daemon code, schemas, config, client, tests; runs acceptance suite; writes the pre-change SHA-256 manifest (P6); executes Phase A copy + Phase B code switch + Phase C verification; records evidence |
| **Verification (in-workspace, DSH session)** | Runs the acceptance suite, full G10 suite, `validate_config`, full regression, re-derived residual |

---

## 3. Exact root/user/group/secret/service requirements (item 3)

### 3.1 Dedicated OS user `dsh-writer` (P1)

**Exact command (prescribed, not executed):**

```bash
sudo useradd \
  --system \
  --home-dir /var/lib/dsh-registry-writer \
  --shell /usr/sbin/nologin \
  --user-group \
  dsh-writer
```

- **UID**: system UID (automatically assigned; no specific UID requirement)
- **Shell**: `/usr/sbin/nologin` (no login)
- **Home**: `/var/lib/dsh-registry-writer` (the daemon root)
- **Group**: `dsh-writer` (primary group, same name)
- **Workspace access**: **NONE** — the `dsh-writer` user must have **no** write access to the session workspace (`/home/administrator/agent-workspace/dsh-custom/plugins/dsh-multi-agent-harness/`). Read-only is acceptable; no access is preferred.
- **Network**: `PrivateNetwork=yes` enforced by systemd (P3), not by user creation.

**Verification (operator):**
```bash
id dsh-writer
# Expected: uid=NNN(dsh-writer) gid=NNN(dsh-writer) groups=NNN(dsh-writer)

# Verify dsh-writer CANNOT write to the workspace
sudo -u dsh-writer touch /home/administrator/agent-workspace/dsh-custom/plugins/dsh-multi-agent-harness/test_probe 2>&1
# Expected: permission denied (non-zero exit)
```

### 3.2 Out-of-workspace daemon root (P2)

**Exact layout (prescribed, not executed):**

```
/var/lib/dsh-registry-writer/          # dirs 0700, files 0600, owner dsh-writer:dsh-writer
├── state/
│   ├── registry/                       # delegations.json + revocations.json
│   └── projects/                       # <project>.json docs
├── audit/                              # <project>/ subdirs with events.jsonl + .chain
├── backup/                             # snapshot dumps (MANIFEST.sha256)
├── ipc.sock                            # Unix domain socket (created by daemon at runtime)
└── daemon.pid                          # PID file (created by daemon at runtime)
```

**Exact commands (prescribed):**

```bash
sudo mkdir -p /var/lib/dsh-registry-writer/{state/{registry,projects},audit,backup}
sudo chown -R dsh-writer:dsh-writer /var/lib/dsh-registry-writer
sudo chmod 0700 /var/lib/dsh-registry-writer
sudo chmod 0700 /var/lib/dsh-registry-writer/state/registry
sudo chmod 0700 /var/lib/dsh-registry-writer/state/projects
sudo chmod 0700 /var/lib/dsh-registry-writer/audit
sudo chmod 0700 /var/lib/dsh-registry-writer/backup
```

**Mandatory design constraint (FINAL 0001 §4.1):** the daemon root **must not** live inside `workspaceRoot` (`/home/administrator/agent-workspace/dsh-custom/plugins/dsh-multi-agent-harness/`). An in-workspace layout is NOT O3 and permits no closure claim. The root must be on a filesystem that the DSH sandbox `writableRoots()` (which returns `[workspaceRoot, '/tmp', tmpdir()]`) does **not** include.

**Verification (operator):**

```bash
# Verify ownership and mode
stat -c '%U %G %a' /var/lib/dsh-registry-writer/
# Expected: dsh-writer dsh-writer 700

# Verify the root is outside workspaceRoot
python3 -c "
import os
ws = '/home/administrator/agent-workspace/dsh-custom/plugins/dsh-multi-agent-harness'
try:
    os.path.commonpath([ws, '/var/lib/dsh-registry-writer/'])
    print('ERROR: daemon root is inside workspaceRoot')
except ValueError:
    print('OK: daemon root is outside workspaceRoot')
"
# Expected: "OK: daemon root is outside workspaceRoot"
```

### 3.3 Control-plane group `dsh` (P5)

**Exact command (prescribed):**

```bash
sudo groupadd --system dsh
sudo usermod -aG dsh administrator
```

- **Group name**: `dsh`
- **Members**: the control-plane process user (the session user, typically `administrator`). The session raw-write actors (`zeko`, `cto`) run as the session user — they are `administrator` — and therefore **are** in the `dsh` group. This is intentional: the group socket permission (`0660`, group `dsh`) is **defense-in-depth**, NOT the authentication mechanism. The **primary authentication** is the per-request HMAC token (FINAL 0001 §4.3, §4.4). A session actor in the `dsh` group can `connect()` to the socket but cannot authenticate without the shared secret.
- **Session user NOT in `dsh` group?** If the operator chooses to run the session under a different user that is NOT in `dsh`, the socket permission provides an additional barrier. However, the project's current session user is `administrator` and must be in `dsh` for the control-plane IPC to work. This is acceptable because the **real authentication** is HMAC, not the socket.

**Verification:**
```bash
getent group dsh
# Expected: dsh:x:NNN:administrator
groups administrator
# Expected: administrator ... dsh ...
```

### 3.4 systemd unit `dsh-registry-writer.service` (P3)

**Exact unit file (prescribed, at `/etc/systemd/system/dsh-registry-writer.service`):**

```ini
[Unit]
Description=DSH Registry Writer Daemon (G10 O3 — dedicated writer for state/registry/**, audit/**, state/projects/**)
After=multi-user.target
Before=dsh-session.service  # if such a unit exists; otherwise After=multi-user.target with readiness probe

[Service]
Type=simple
User=dsh-writer
Group=dsh-writer
ExecStart=/home/administrator/agent-workspace/dsh-custom/plugins/dsh-multi-agent-harness/.venv-tests/bin/python -m registry_writer
Restart=always
RestartSec=2
PrivateNetwork=yes
LimitNOFILE=65536
MemoryMax=512M
WorkingDirectory=/var/lib/dsh-registry-writer
StandardOutput=journal
StandardError=journal
# If the process starts as root, it drops privileges to dsh-writer internally.
# If started as non-root, ensure the dsh-writer user can read the config and secret.

[Install]
WantedBy=multi-user.target
```

- **Readiness probe**: the daemon exposes `health?name=ready` (FINAL 0001 §4.6). The unit can use `ExecStartPost` with a timeout, or the orchestrator can poll the readiness endpoint before starting delegations.
- **Cold-start ordering**: the daemon must be ready before the orchestrator begins delegations. This can be enforced by: (a) a systemd ordering dependency, or (b) the orchestrator startup script verifying `health?name=ready` before proceeding. The latter is preferred because it does not require a corresponding `dsh-session.service` unit.

**Verification:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable dsh-registry-writer.service
sudo systemctl start dsh-registry-writer.service
sudo systemctl status dsh-registry-writer.service
# Expected: active (running) — no errors
```

### 3.5 Shared HMAC-SHA256 secret (P4)

**Exact requirements (from FINAL 0001 §4.4, §4.12, §4.3):**

| Property | Value |
|---|---|
| Algorithm | HMAC-SHA256 |
| Secret length | ≥ 32 bytes (256 bits), cryptographically random |
| Location | `0600` file outside the session workspace, e.g. `/etc/dsh-registry-writer/hmac-secret` |
| Readable by | exactly two principals: `dsh-writer` (daemon process) and the control-plane user (`administrator`) |
| Never inside | the session workspace, `config/`, or any VCS-tracked path |
| Replay window | `issued_at` ±30s (enforced by the daemon per-request) |
| Rotation | version-tagged; prior secret valid for one rotation window, then revoked |

**Prescribed generation (operator):**

```bash
# Generate a 256-bit (32-byte) random secret
sudo mkdir -p /etc/dsh-registry-writer
sudo openssl rand -hex 32 > /etc/dsh-registry-writer/hmac-secret
sudo chmod 0600 /etc/dsh-registry-writer/hmac-secret
sudo chown dsh-writer:dsh-writer /etc/dsh-registry-writer/hmac-secret

# Make it readable by the control-plane user (administrator)
# Option A: add administrator to the dsh-writer group (simplest)
sudo usermod -aG dsh-writer administrator
sudo chmod 0640 /etc/dsh-registry-writer/hmac-secret  # group-read
# Option B: create a separate group for secret access
# Preferred: use a dedicated group or ACL; the daemon's group is dsh-writer
```

**Verification:**
```bash
stat -c '%U %G %a' /etc/dsh-registry-writer/hmac-secret
# Expected: dsh-writer dsh-writer 600 (or 640 if group-read)

# Verify NO workspace process can read it
sudo -u dsh-writer cat /etc/dsh-registry-writer/hmac-secret 2>&1 | head -1
# Expected: outputs the hex secret (dsh-writer can read)

# Verify the daemon config references this path
# (config/registry-writer.yaml will contain the path, not the secret itself)
```

### 3.6 Daemon config file (`config/registry-writer.yaml`) — reference spec

This file is **created by Engineering** during implementation. It is documented here for operator reference. The file lives **in the workspace** (`config/registry-writer.yaml`) but contains **paths to secrets**, never the secrets themselves.

```yaml
# config/registry-writer.yaml — daemon configuration
# Created by Engineering during implementation; NOT created in this session.
daemon:
  root: /var/lib/dsh-registry-writer
  socket_path: /var/lib/dsh-registry-writer/ipc.sock
  pid_file: /var/lib/dsh-registry-writer/daemon.pid
  uid: dsh-writer
  gid: dsh-writer
  socket_group: dsh
  socket_mode: 0660
  ipc_protocol_version: 1

auth:
  hmac_secret_path: /etc/dsh-registry-writer/hmac-secret
  replay_window_seconds: 30

backup:
  backup_dir: /var/lib/dsh-registry-writer/backup
  manifest_format: sha256

limits:
  max_doc_bytes: 16777216  # 16 MiB, matches state/helpers/atomic_write.py:42
  max_payload_bytes: 33554432  # 32 MiB (request/response)
  connection_limit: 64
  request_timeout_seconds: 30
  graceful_shutdown_seconds: 10
```

---

## 4. Verification after provisioning

After all six provisioning steps (P1–P5, P8–P9) are complete, the operator/engineering team runs these verification checks:

| # | Check | Command | Expected |
|---|---|---|---|
| V1 | User exists | `id dsh-writer` | uid=NNN(dsh-writer) gid=NNN(dsh-writer) |
| V2 | Group exists | `getent group dsh` | dsh:x:NNN:administrator |
| V3 | Root exists + permissions | `stat -c '%U %G %a' /var/lib/dsh-registry-writer/` | dsh-writer dsh-writer 700 |
| V4 | Root is outside workspace | Python `os.path.commonpath` check | ValueError (not common) |
| V5 | Secret exists + permissions | `stat -c '%U %G %a' /etc/dsh-registry-writer/hmac-secret` | dsh-writer dsh-writer 600 |
| V6 | Systemd unit loaded | `systemctl is-enabled dsh-registry-writer.service` | enabled |
| V7 | Systemd unit startable | After daemon implementation: `systemctl start dsh-registry-writer.service` | active (running) |
| V8 | Approvals H3+H4 recorded | Approval record document exists | file present with signed date |
| V9 | Reusable modules present | `python3 -c "import state.helpers.atomic_write; import audit.helpers.append_log; print('ok')"` | ok |

---

*Status: OPERATOR CHECKLIST (items 1–3). Human approvals H3/H4 are the immediate prerequisite (OPEN). All five infrastructure prerequisites (P1–P5) are UNMET; the exact root/user/group/secret/service commands are prescribed above, requiring root on the host. P8 (reusable modules) is CLOSED. P6 (pre-change backups) and P7 (freeze window) are in `0003`. No provisioning was performed this session. G10 remains OPEN / BLOCKING. No closure claimed.*
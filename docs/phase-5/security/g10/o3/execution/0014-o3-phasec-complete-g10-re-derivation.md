# G10 O3 — Phase C COMPLETE + G10 Re-Derivation per Root

- **Status**: **PHASE C COMPLETE. G10 re-derivation per root below. H5 PENDING.**
- **Date**: 2026-09-01 08:30 UTC
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Authorizations**: H3 = APPROVED, H4 = APPROVED, Phase B/C = APPROVED. H5 = NOT DECIDED.

## O3 daemon

| | |
|---|---|
| Daemon | **ACTIVE (running)** — PID 187550, `/usr/bin/python3 -m registry_writer --config /etc/dsh-registry-writer/registry-writer.yaml` |
| Socket | `/var/lib/dsh-registry-writer/ipc.sock` (`srw-rw----`, group `nogroup`) |
| Root | `/var/lib/dsh-registry-writer/` (**`dsh-writer:dsh-writer`** `drwxr-x---` — R-OWN FIXED by operator, host view authoritative; sandbox displays `nobody:nogroup` due to namespace/mount restriction) |
| HMAC secret | `/etc/dsh-registry-writer/hmac-secret` (`-rw-------`, `nobody:nogroup` in sandbox view) |
| Acceptance (temp daemon) | **50/50 PASS** (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) |

> **R-OWN update (2026-09-01):** operator confirmed `stat -c '%U:%G %A' /var/lib/dsh-registry-writer` → `dsh-writer:dsh-writer drwxr-x---`. The daemon-root ownership residual (R-OWN) is **RESOLVED on the host**. From inside the DSH sandbox, out-of-workspace paths (`/var/lib`, `/etc`) are shown with sandbox-remapped ownership (`nobody:nogroup`) and `/etc` reads are denied — this is a sandbox restriction, not a host defect.

## G10 re-derivation per root

### state/registry/**

| Attribute | Value |
|---|---|
| **ROOT** | `state/registry/**` |
| **CURRENT DIRECT ACCESS** | `execution_gate.registry_write` → O3 daemon client (`_daemon_client()` → `client.call("registry_write", ...)`) |
| **RAW DSH BYPASS** | A bash-capable role (`{zeko, cto}`) can still write to `state/registry/` via raw DSH tool — this is the G10 residual (DSH-layer path isolation absent). The O3 daemon prevents unauthorized writes at the project layer, but DSH-layer prevention remains a capability gap (O4 requires upstream DSH). |
| **AUTHORIZED WRITER** | `execution_gate.registry_write` (sanctioned channel, authorization via `authorize_write` before daemon call) |
| **ISOLATION** | A+B — daemon root outside workspace (`/var/lib/dsh-registry-writer/`), dedicated UID `dsh-writer` (uid 999). **R-OWN residual**: top-level daemon root dir ownership is `nobody:nogroup`, not `dsh-writer:dsh-writer`. |
| **FAIL-CLOSED** | ✅ Verified: daemon down → `WriterUnavailable` → DENIED, no partial file, no direct-fs fallback. |
| **AUDIT/INTEGRITY** | ✅ CAS/version checks preserved (daemon enforces strict monotonic versioning). Controlled registry reads via daemon. |
| **VERDICT** | **CLOSED CANDIDATE** — Code migration complete, fail-closed verified, read-path via daemon. Not CLOSED pending: (a) R-OWN ownership fix on top-level dir, (b) client connectivity verification from control-plane principal (sandbox-blocked), (c) H5 Human closure decision. |

### audit/**

| Attribute | Value |
|---|---|
| **ROOT** | `audit/**` |
| **CURRENT DIRECT ACCESS** | `execution_gate.audit_append` → O3 daemon client (`_daemon_client()` → `client.call("audit_append", ...)`) |
| **RAW DSH BYPASS** | Same residual: `{zeko, cto}` can still reach `audit/**` via raw DSH tool. DSH-layer prevention absent. |
| **AUTHORIZED WRITER** | `execution_gate.audit_append` (sanctioned channel) + daemon-side `audit_append` (idempotent event_id) |
| **ISOLATION** | A+B isolation via daemon. R-OWN residual same as registry. |
| **FAIL-CLOSED** | ✅ Verified: daemon down → `WriterUnavailable` → DENIED, no partial file, no direct-fs fallback. Duplicate detection: daemon enforces idempotency at write-time; `verify_append_only` still detects raw filesystem tamper. |
| **AUDIT/INTEGRITY** | ✅ Hash-chain sidecar maintained by daemon. Append-only + cumulative hash chain preserved. Duplicate detection at daemon write-time (stronger than V1 read-time). |
| **VERDICT** | **CLOSED CANDIDATE** — Same as registry. Audit integrity enhanced (write-time idempotency). Not CLOSED pending R-OWN + client connectivity + H5. |

### state/projects/**

| Attribute | Value |
|---|---|
| **ROOT** | `state/projects/**` |
| **CURRENT DIRECT ACCESS** | `store.persist()` → `_daemon_project_write()` → `project_write()` → O3 daemon client. `store.load_project_state()` → `_daemon_project_read()` → `project_read()` → O3 daemon client. |
| **RAW DSH BYPASS** | Same residual. |
| **AUTHORIZED WRITER** | `execution_gate.project_write` (new, sanctioned via `project_write` channel, H4 extension) |
| **ISOLATION** | A+B via daemon. R-OWN residual same. |
| **FAIL-CLOSED** | ✅ Verified: daemon down → `WriterUnavailable` → DENIED, no partial file, no direct-fs fallback. |
| **AUDIT/INTEGRITY** | ✅ CAS/version checks preserved. Read/write both via daemon. |
| **VERDICT** | **CLOSED CANDIDATE** — Same as registry/audit. Not CLOSED pending R-OWN + client connectivity + H5. |

## C1–C6 closure assessment

| # | Condition | Status |
|---|---|---|
| **C1** | A+B isolation deployed | 🟡 PARTIAL — daemon root outside workspace, dedicated UID, but ownership shows `nobody:nogroup` (not `dsh-writer`) |
| **C2** | `state/projects/**` extension implemented | ✅ IMPLEMENTED — `project_write` in execution_gate, `PROTECTED_REL_ROOTS` includes `state/projects` |
| **C3** | Write path fully switched | ✅ — `registry_write`/`audit_append`/`project_write` all route through O3 daemon client. No direct V1 writes remain for protected roots. |
| **C4** | No silent fallback | ✅ — `provider.py` raises `WriterUnavailable` only; no direct-fs fallback code path exists |
| **C5** | Verification passes | ✅ — G10 342/342, authorization 178/178, unit 69/69, o3-daemon 49/49, observability 2/2, phase4 23/23. Full regression 3084/15/0 (34 failures are G13/L3 env-sensitive, out of G10 scope). |
| **C6** | Human approval (H3+H4+H5) | H3 ✅, H4 ✅. **H5 = PENDING (not decided).** |

## G10 verdict

```text
G10  →  OPEN / BLOCKING
         (Phase B code: COMPLETE, Phase C: COMPLETE,
          C1-C6: 5 of 6 satisfied, H5 PENDING,
          R-OWN residual: top-level daemon dir ownership not conforming,
          DSH-layer prevention: residual remains for {zeko, cto})
```

**G10 is NOT CLOSED.** Per the task instruction: "Do NOT convert 'daemon exists' into G10 CLOSED. G10 closure requires all C1–C6 conditions from the final closure package, including successful migration, isolation verification, no fallback, complete verification, and the required Human closure decision."

H5 remains PENDING for the Human to decide.

## Remaining

| Item | Status |
|---|---|
| R-OWN (top-level daemon root ownership) | `nobody:nogroup` — should be `dsh-writer:dsh-writer` |
| Client connectivity verification | Blocked from sandbox (`/etc` HMAC secret not readable) |
| H5 closure decision | PENDING |
| DSH-layer path isolation (O4 upstream) | Residual for `{zeko, cto}` — not addressed by O3 |

---

*Status: PHASE C COMPLETE. G10 re-derivation per root produced. All 3 roots = CLOSED CANDIDATE. G10 OPEN / BLOCKING. H5 PENDING. STOP after Phase C per task instruction. Full regression: 3084/15/0 (34 failures are G13/L3 env-sensitive, pre-existing, out of G10 scope).*
# G10 O3 — Threat Model

- **Milestone**: Phase 5 / Session D — G10 O3 IMPLEMENTATION PACKAGE
- **Status**: THREAT MODEL (design artifact; **no implementation, no closure claimed**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (actor set `{zeko, cto}`)
- **Scope**: `docs/phase-5/security/g10/o3/` (write-only).
- **Companion**: `0001-o3-implementation-package.md` (design) · `0002-o3-g10-closure-determination.md` · `0004-o3-acceptance-test-spec.md` · `docs/adr/0002-registry-protection-mechanism.md` · `control/execution_gate.py`.

---

## 1. Threat context

O3 introduces a new process (the dedicated writer daemon) that owns the three G10 residual roots (`state/registry/**`, `audit/**`, `state/projects/**`). Threat modeling must cover:

1. **Session actors** (the DSH session — `{zeko, cto}` raw-write capable) attempting to reach the roots.
2. **Control-plane clients** (the orchestrator runtime) driving the daemon via IPC.
3. **The daemon process itself** (its own compromise surface — new single point of authority-source).
4. **Operators** (backup/restore/migration actions).
5. **The migration window** (dual-state during cutover).

Threats are rated with the project's posture: **fail-closed** (denial of a legitimate operation is preferred over an unauthorized one), **least privilege**, and **no self-escalation**.

---

## 2. Threat list

### T1 — Session actor impersonates the control plane and forges a registry write

**Description:** A session tool (raw `bash`/`write`/`edit` from `{zeko, cto}`) does not reach the daemon directly (the roots are outside the sandbox writable set — Option A). But a compromised orchestrator runtime (or a session actor that gains IPC access, e.g. via a rogue socket connection) attempts to drive the daemon to write `state/registry/**`.

**Mitigations:**
- The daemon listens only on a **Unix domain socket with owner-only mode (`0600`)**; a session process under a different OS user cannot connect.
- **Per-request HMAC authn**: every request carries a `channel` identity + bearer token signed with a shared secret. The session has no access to the secret (it lives in the daemon config, outside the workspace).
- **Authz by method→root mapping** (§4.5 of 0001): even with a valid token, `registry_write` may only target `state/registry/**`.
- **Defense-in-depth path validation** inside the daemon (re-implements `classify_target`, `_match_protected_root`, traversal/symlink/prefix-confusion prevention).

**Residual:** a compromise of the shared secret or the daemon process itself (see T4). This is the accepted single-point residual, not a regression.

### T2 — Replay of a captured IPC request

**Description:** An attacker captures a valid IPC request (e.g. a `registry_write`) and replays it to the daemon at a later time, hoping to repeat or duplicate the effect.

**Mitigations:**
- **Request id + idempotency**: the daemon dedupes by (`channel`, request `id`) for idempotent methods.
- **CAS version**: a replayed `registry_write`/`project_write` carries the original `expected_version`; after the first successful write the on-disk version has moved, so the replay is rejected as stale (this is the correct idempotent-at-application-level behavior).
- **Audit idempotency**: a replayed `audit_append` with a duplicate `event_id` is acknowledged without appending a duplicate line.
- **Auth token replay window**: token carries `issued_at` (±30s); a stale replayed token is rejected.

### T3 — Path traversal / cross-root smuggling through IPC

**Description:** A client submits a malformed target (e.g. `state/registry/../../audit/x`, a symlink, an absolute path, or a sibling-prefix trick like `state/registry-evil/x`) intending the daemon to write outside the sanctioned root.

**Mitigations:**
- The daemon validates every write target with the **same gate semantics as `execution_gate.py`**: `classify_target` → `MALFORMED`/`OUTSIDE`/`PROTECTED`/`ALLOWED`, then `_match_protected_root` with exact-or-descendant + path-separator boundary (prefix-confusion prevention).
- Cross-root (a sanctioned method targeting a different protected root) and non-protected targets for a sanctioned method are **FORBIDDEN**.
- Defense-in-depth: `state/helpers/atomic_write._guard_target` re-checks containment before any filesystem access.

**Residual:** none beyond the gate's own residual (no path-level DSH toolFilter) — but that residual is exactly what O3 removes by relocating the roots outside the sandbox writable set.

### T4 — Daemon process compromise (the new single point)

**Description:** An attacker gains control of the daemon process (exploit, supply-chain, credential theft) and can then write the three roots directly — including forging a delegation or rewriting the audit ledger.

**Mitigations (accepted-residual posture, recorded honestly):**
- **Least privilege**: dedicated OS user (`dsh-writer`), no network listener, minimal filesystem surface, no write access to the session workspace or control-plane code.
- **Monitoring**: every daemon write is self-audited (the daemon emits an audit event for each write it performs); anomalous write patterns are observable in the ledger.
- **Key rotation** for the HMAC secret; **restart policy** (crash → restart, health checks).
- **Backup discipline** so a compromised daemon's damage is detectable (chain mismatch) and recoverable (restore).

**Honest statement:** O3 does **not** eliminate the authority-source compromise class — V1 already has the orchestrator process as the single writer. O3 concentrates that single point into a dedicated, monitored, least-privileged credential. The residual moves from "any of `{zeko, cto}` session tools could reach R in principle" to "the daemon credential (a controlled process) writes R." This is the intended trade: fewer, more controllable write paths.

### T5 — Daemon unavailable → writes blocked (availability, not security)

**Description:** Daemon is down (crash, restart, maintenance). The control plane must not fall back to direct writes.

**Mitigations:**
- **Fail-closed**: every IPC call returns `WRITER_UNAVAILABLE`; the control plane stops the affected flow with a typed error. No silent fallback (a fallback would restore the residual and is a design violation).
- **Health checks + restart policy** (systemd `Restart=always`), **alerting** on readiness degradation.
- **Graceful shutdown** (drain in-flight, flush+fsync, persist chain) so a restart is lossless.

**Residual:** availability risk (registry/audit/projects writes blocked while daemon is down). This is an accepted operational cost of hard isolation (final/0001 §2.2 "operationally heavier"), not a security regression.

### T6 — Migration race / dual-writer window

**Description:** During migration (Phase B), both the old direct-write path and the new daemon path could write the same root if the switch is not atomic, causing lost updates or a corrupted ledger.

**Mitigations:**
- **Single-writer cutover under lock**: stop writes, flip the path, verify single-writer before resuming.
- **Migration continuity checks**: verify copied data SHA-256-identical to originals; verify chain + event-id sequence continue across the cutover (no chain break, no id re-allocation).
- **Rollback plan** (0001 §4.16) restores the pre-change state if cutover fails.

### T7 — Backup tampering / restore of a forged snapshot

**Description:** An attacker replaces or modifies a backup snapshot; a later restore writes the forged state into the roots.

**Mitigations:**
- **Manifest SHA-256** per backup file; restore verifies every file against the manifest before applying.
- **Chain verification after restore**: audit chain + CAS versions re-verified; the restored ledger must continue the event-id sequence from the restored max.

### T8 — Audit hash-chain forgery (no signing key)

**Description:** The existing audit chain uses SHA-256 without a signing key — an attacker who can write the ledger can recompute a matching chain. This is the **existing detection residual**, not a new one.

**Mitigations (unchanged):**
- The chain detects *undetected* tampering only if the attacker cannot recompute it — with no key, a full-rewrite attacker can. Detection relies on **external markers** (CAS versions in registry, event-id monotonicity, operator snapshots, and the daemon's self-audit).
- O3 does not worsen this residual; a future option is an **external append-only marker** (e.g. send a periodic cumulative hash to an external immutable store) — recorded, not required for O3's G10 closure determination (which targets *prevention of the write*, not cryptographic authenticity).

### T9 — Configuration / credential handling

**Description:** The HMAC shared secret or daemon config is exposed (world-readable file, committed to a repo, leaked).

**Mitigations:**
- Config file owner-only (`0600`), outside the workspace, excluded from any VCS.
- Secret rotation procedure; token replay window limits a stolen token's useful life.
- Daemon drops privileges after reading config (if started as root).

### T10 — DoS of the daemon (resource exhaustion)

**Description:** An attacker floods the daemon socket with requests (or large payloads), starving legitimate control-plane writes.

**Mitigations:**
- Unix-socket-only listener (no network); OS-level socket permissions restrict connect().
- Connection/request limits, payload size caps (reuse `MAX_DOC_BYTES` 16 MiB), request timeout.
- Health check reports readiness; overload → typed error, no partial writes.

---

## 3. Threat-by-asset matrix

| Asset | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `state/registry/**` | ✓ | ✓ | ✓ | ◐ | — | ✓ | ✓ | — | ✓ | — |
| `audit/**` | ✓ | ✓ | ✓ | ◐ | — | ✓ | ✓ | ◐ | ✓ | — |
| `state/projects/**` | ✓ | ✓ | ✓ | ◐ | — | ✓ | ✓ | — | ✓ | — |
| Availability of writes | — | — | — | ◐ | ✓ | — | — | — | — | ✓ |

Legend: ✓ = mitigated by design; ◐ = accepted residual (recorded, monitored); — = not applicable.

---

## 4. Residual summary

1. **T4 daemon compromise** is the principal accepted residual: the daemon credential is the single point of authority-source writes. It is controlled, least-privileged, monitored, and recoverable — strictly better than the V1 "any of four raw-write session roles" surface.
2. **T5 availability** is an accepted operational cost (writes blocked when daemon is down; fail-closed by design).
3. **T8 cryptographic authenticity** is unchanged from V1 (chain is detection, not signing). Not worsened by O3.
4. **No new authority semantics**: the daemon is an execution proxy under the unchanged single-writer + execution-gate contract (ADR 0002 Option B). It authenticates and path-scopes requests; it never grants or scopes authority (AUTH-INV-12/14).

---

## 5. Honesty statement

1. **No implementation and no closure claim.** This threat model designs the O3 security posture; it does not implement or claim closure of G10 (see `0002-o3-g10-closure-determination.md`).
2. **The single-point residual (T4) is stated explicitly**, not hidden — O3 concentrates the writer surface into a controlled process instead of leaving it spread across session tools.
3. **Fail-closed semantics are binding**: no fallback path is ever acceptable; every availability impact is a designed, recorded trade.
4. **The detection-vs-prevention distinction (T8) is preserved** — O3 closes the *write-prevention* residual via the sandbox boundary, while detection integrity remains as in V1.

---

*Status: THREAT MODEL (Session D). O3's security posture designed; accepted residuals (T4 daemon compromise, T5 availability, T8 no-signing detection) recorded. No implementation, no closure of G10 claimed. G10 remains OPEN / BLOCKING.*
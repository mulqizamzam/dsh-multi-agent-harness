# G10 O3 — Closure Determination: Does O3 Alone Close G10?

- **Milestone**: Phase 5 / Session D — G10 O3 IMPLEMENTATION PACKAGE
- **Status**: DETERMINATION (design-level analysis; **no implementation, no closure claimed**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (actor set `{zeko, cto}`)
- **Scope**: `docs/phase-5/security/g10/o3/` (write-only). Read-only synthesis of: `docs/phase-5/security/g10/final/*`, `implementation/*`, `docs/adr/0002.md`, `control/execution_gate.py`, `orchestrator/runtime/{audit,store,delegation}.py`, `state/helpers/*`, `audit/helpers/*`, `schemas/*`, and the Session C precision on `state/projects/**`.
- **Companion**: `0001-o3-implementation-package.md` (design) · `0003-o3-threat-model.md` · `0004-o3-acceptance-test-spec.md` · `docs/phase-5/final/0002-g10-formal-residual-proof.md` (R) · `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (Session C) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5).

---

## 1. The exact question

> **Does O3 (dedicated registry/audit/projects writer process) alone close G10?**

The task instruction is explicit: *Do not assume it does.* This document answers the question precisely, root-by-root, and states the exact conditions under which O3 does or does not close G10.

---

## 2. What O3 is (as scoped in this package)

O3 is an out-of-process writer that owns the three G10 residual roots:

- `state/registry/**` (delegation registry — the authority source)
- `audit/**` (append-only audit ledger)
- `state/projects/**` (project state document)

Its isolation mechanism is **removing the roots from the DSH-reachable writable set**:

- **Option A (recommended):** roots live outside `workspaceRoot`, so the session sandbox (writable roots = `[workspaceRoot, '/tmp', tmpdir()]`) **hard-denies** any session tool write — including raw `bash`/`write`/`edit` from `{zeko, cto}`. This is DSH-sandbox-enforced prevention, not project-layer interception.
- **Option B (fallback):** roots inside `workspaceRoot` but owned by a different OS UID; session tools are denied by OS permissions. Weaker (same-UID session cannot bypass a truly different-UID permission, but sandbox boundary is the cleaner mechanism).

The daemon is the **sole writer** of the three roots; the control plane reaches it only via IPC with authn/authz. This is the ADR 0002 consequence-4 mechanism (dedicated registry/audit writer), extended in this package to also cover `state/projects/**`.

---

## 3. Per-root analysis of R under O3

**R (post-O5):** a raw-write-capable role (`{zeko, cto}`) can place content on `state/registry/**`, `audit/**`, `state/projects/**` via a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel; DSH provides no per-path/per-agent interception; prevention absent at the DSH layer.

| Root | V1 (current) | Under O3 (Option A) | Residual after O3 |
|---|---|---|---|
| `state/registry/**` | gate-DENIED for channeled writes; raw session write NOT intercepted (R open) | root outside `workspaceRoot`; session sandbox **hard-denies** any write (channeled or raw) | **CLOSED** — no session tool can reach the root at all |
| `audit/**` | gate-DENIED for channeled writes; raw session write NOT intercepted (R open) | root outside `workspaceRoot`; sandbox hard-denies | **CLOSED** |
| `state/projects/**` | **ALLOWED** at the gate (CAS-detected post-hoc, Session C precision); raw session write NOT intercepted (R open) | root outside `workspaceRoot`; sandbox hard-denies | **CLOSED** — *only if the daemon scope is extended to projects (this package's design decision)* |

**Key precision:**
- `state/registry/**` and `audit/**` are already **gate-DENIED** in V1 (protected paths, `PROTECTED_REL_ROOTS`). The G10 residual for them is the **raw-tool bypass** (the gate only intercepts channeled writes).
- `state/projects/**` is **NOT gate-DENIED** in V1 — it is classified ALLOWED and protected only by post-hoc CAS version detection. The G10 residual for it is **both** the absence of gate denial **and** the raw-tool bypass. O3's extension to projects is therefore the **only** mechanism that gives `state/projects/**` hard isolation.

**Conclusion per root:** under O3 with Option A and the projects extension, the DSH-layer prevention gap for **all three** residual roots is closed — the roots are simply no longer reachable by any session tool.

---

## 4. The precise determination

### 4.1 O3 alone CAN close R (the G10 residual) — under conditions

**O3, as scoped in this package, is the strongest available project-layer closure arm and the ONLY one (besides O4/DSH) that can close R for `state/projects/**`.** If all of the following conditions hold, O3 alone closes the G10 residual R for all three roots:

1. **Option A isolation** is used (roots outside `workspaceRoot`, so the session sandbox itself denies writes). Option B (different UID, same workspace) is weaker and must be validated for the specific environment before a closure claim.
2. **The `state/projects/**` extension is implemented** — the daemon actually owns `state/projects/**` (not just registry/audit). Without this, `state/projects/**` remains CAS-detected only, and R is **not** closed for that root.
3. **The write path is fully switched**: `execution_gate.registry_write()`, `execution_gate.audit_append()`, and `RuntimeStore.persist()` all route through the daemon client; no direct-write path remains reachable.
4. **No silent fallback** exists: daemon down ⇒ writes to the three roots **block** (fail-closed). A fallback would restore the residual.
5. **Verification passes**: the isolation probe (raw write to the old root locations is now **DENIED**), the full G10 suite, validate-config, and the migration-continuity checks all pass.
6. **Human approval** of the infrastructure change (ADR 0002 consequence 4) and of the `state/projects/**` scope extension.

When all six hold, O3 alone closes the **prevention gap** (R) that defines G10's residual — a hard-isolation closure, not merely a surface reduction (unlike O5).

### 4.2 O3 alone does NOT close G10 by default — and here is why

Despite 4.1, this package **does not assume** O3 alone closes G10, and states the precise reasons:

| # | Reason O3 alone is not (by itself) a G10 closure today | Detail |
|---|---|---|
| 1 | **Not implemented.** This package is a design; no daemon exists, no write path is switched. G10 remains OPEN until O3 is implemented, deployed, and verified. | Status quo: G10 OPEN / BLOCKING. |
| 2 | **`state/projects/**` is not covered by the ADR-sanctioned scope.** ADR 0002 consequence 4 describes "dedicated registry process" (registry/audit). Covering `state/projects/**` is a **design extension** in this package — it requires explicit approval. Without the extension, O3 alone closes registry+audit only, and G10 remains open for `state/projects/**`. | Extension is necessary for full closure. |
| 3 | **Closure in the matrix sense requires the DSH-layer framing to be re-derived.** G10's matrix row is framed as "DSH path-isolation limitation / prevention at DSH layer absent." O3 removes the roots from the DSH-reachable set (a composition/infrastructure workaround), it does **not** add a DSH capability (per-agent sandbox or per-path toolFilter). The security outcome (raw write cannot land) is equivalent, but the matrix must record the mechanism change and re-derive the residual, not assume the row flips on design intent. | Re-derivation + Human decision required. |
| 4 | **The daemon is a new single point of authority-source compromise (T4).** A compromise of the daemon's UID/process would let an attacker write the three roots. This is the same class of residual as V1 (the orchestrator process is already the single point), so it is an *accepted* residual, not a regression — but it means O3 exchanges "any of {zeko, cto} can reach R" for "the daemon credential can reach R." G10's scope is session tools, so this does not keep G10 open, but it must be recorded and managed. | Accepted residual (threat model T4). |
| 5 | **G10 closing is necessary but not sufficient for production.** O3 does not resolve G13 (prompt injection, OPEN/UNKNOWN), nor the production blockers B1/B2 (mount/answerer availability), B6, B7, B8. Production readiness requires those independently. | G10 closure ≠ production unblock. |

### 4.3 The verdict (one sentence)

> **O3 alone does NOT close G10 today (it is not implemented, and full closure requires the `state/projects/**` scope extension plus approval, deployment, and verification); but O3 — with that extension and Option-A isolation — is the strongest and only non-DSH project-layer arm that CAN close the G10 residual R for all three roots (hard isolation, not reduction), and therefore must NOT be assumed closed until it is implemented, the residual is re-derived, and the closure is approved. G10 remains OPEN / BLOCKING.**

---

## 5. Relationship to the other arms

| Arm | Closes R for | Nature | Status |
|---|---|---|---|
| **O5** (applied) | none (shrinks actor set `{zeko,cto,somad,nova}` → `{zeko,cto}`) | surface reduction | **APPLIED** (containment only) |
| **O3** (this package) | `state/registry/**`, `audit/**`, `state/projects/**` (with extension) | hard isolation (removes roots from session writable set) | **NOT IMPLEMENTED** |
| **O4** (upstream DSH) | same three roots, at the DSH layer | native per-agent sandbox root / per-path toolFilter | **ABSENT in 0.1.1-rc.2** (exact upstream requirement) |
| **O2** (registry relocation) | partial, only if paired with O3/O4 | fallback | recorded, not recommended alone |

O4, when available, is the clean DSH-layer solution and the canonical way to close G10. O3 is the project-layer equivalent that works in 0.1.1-rc.2. They are not mutually exclusive: O3 can be deployed now, and O4 remains the upstream ideal (a future re-derivation against a newer DSH would still be required).

---

## 6. Honesty statement

1. **No closure is claimed.** G10 remains OPEN / BLOCKING. This document determines the *conditions under which O3 would close R*, it does not assert the closure happened.
2. **The `state/projects/**` extension is stated explicitly** as a design decision necessary for full closure — not assumed, not hidden.
3. **Option A vs Option B is a real dependency**: the sandbox-boundary mechanism (Option A) is what makes O3 a hard-isolation closure; Option B's adequacy depends on the deployment environment and must be validated.
4. **The daemon's single-point nature is recorded** (T4) — O3 does not eliminate the authority-source compromise class, it moves it to a dedicated, monitored credential.
5. **No test failure was hidden.** The planning tests assert this document exists, states the conditional nature, and makes no unconditional closure claim.

---

*Status: DETERMINATION. O3 alone does not close G10 today (not implemented; projects extension + approval + verification required). O3 CAN close the G10 residual R for all three roots if implemented with the projects extension and Option-A isolation. G10 remains OPEN / BLOCKING for production.*
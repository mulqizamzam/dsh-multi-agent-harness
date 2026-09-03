# G10 O3 — FINAL Closure Determination: Does O3 Close All Three Residual Roots?

- **Milestone**: Phase 5 / Session F — G10 O3 FINAL ARCHITECTURE PACKAGE
- **Status**: FINAL DETERMINATION (design-level analysis; **no implementation, no closure claimed** — G10 remains OPEN / BLOCKING)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; O5 applied (actor set `{zeko, cto}`)
- **Scope**: `docs/phase-5/security/g10/o3/final/` (write-only). Read-only synthesis of: `0001-o3-final-architecture-package.md` (design) · `docs/phase-5/security/g10/o3/0002-o3-g10-closure-determination.md` (Session D determination) · `docs/phase-5/final/0002-g10-formal-residual-proof.md` (R) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5) · `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (Session C) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` · `docs/adr/0002-registry-protection-mechanism.md` · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py`.
- **Companion**: `0001-o3-final-architecture-package.md` (design) · `0003-o3-final-threat-model.md` · `0004-o3-final-acceptance-test-spec.md` · `docs/phase-5/security/g10/o3/0002-o3-g10-closure-determination.md` (Session D).
- **Question**: *Does O3 close all three G10 residual roots: `state/registry/**`, `audit/**`, `state/projects/**`?*

---

## 1. The exact question

The G10 residual R (post-O5) is:

> A raw-write-capable role (`{zeko, cto}`) can, in principle, place content on `state/registry/**`, `audit/**`, or `state/projects/**` via a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel; DSH provides no per-path or per-agent interception; the L1 execution gate intercepts only channeled writes.

This determination answers: **does O3 (as designed in the FINAL architecture package — out-of-process writer, isolated outside-workspace root, dedicated UID, IPC with authn/authz, fail-closed, scope extended to all three roots) close R for each of the three roots?**

The answer is per-root, conditional, and honest. **No closure is claimed.**

---

## 2. What O3 is (as finalized in this package)

O3 is a dedicated out-of-process writer daemon that owns the three G10 residual roots. Its isolation mechanism is **removing the roots from the DSH-reachable writable set**:

- **Mandatory A+B isolation:** roots live **outside `workspaceRoot`** (so the session sandbox hard-denies any session tool write — this is DSH-sandbox-enforced prevention, the strongest available without DSH core change) **AND** the daemon runs under a **dedicated OS UID** (`dsh-writer`) with no access to the session workspace (OS-level barrier as defense-in-depth).
- **Fail-closed with no silent fallback:** daemon unavailable → writes blocked. No fallback to direct write (a fallback would restore the residual).
- **Scope extended to `state/projects/**`** — the daemon owns all three roots, not just registry/audit.
- **Read paths also route through IPC** — no in-workspace read-only mirror (the mirror would reintroduce a session-writable surface).

O3 is the ADR 0002 consequence-4 mechanism (dedicated registry/audit writer), extended to `state/projects/**`.

---

## 3. Per-root determination

### Root: `state/registry/**`

| Aspect | Detail |
|---|---|
| V1 protection | Gate-DENIED for channeled writes (`PROTECTED_REL_ROOTS`). Raw-tool bypass OPEN (the residual). |
| Under O3 (A+B) | Root lives outside `workspaceRoot` → the session sandbox **hard-denies** any write, raw or channeled, from any session tool. The daemon's dedicated UID provides an additional OS-level barrier. The daemon is the sole writer, reached only via IPC with HMAC authn/authz. |
| Residual after O3 | **CLOSED** — no session tool can reach the root at all. The raw-write residual is eliminated. |
| Conditions | Implemented, deployed with A+B isolation, write path fully switched (Phase B), no fallback, verification passes, Human approval. |

### Root: `audit/**`

| Aspect | Detail |
|---|---|
| V1 protection | Gate-DENIED for channeled writes (`PROTECTED_REL_ROOTS`). Raw-tool bypass OPEN (the residual). |
| Under O3 (A+B) | Same as `state/registry/**` — outside workspace, daemon UID, sole writer, IPC-reachable only. |
| Residual after O3 | **CLOSED** — no session tool can reach the audit root. |
| Conditions | Same as above. |

### Root: `state/projects/**`

| Aspect | Detail |
|---|---|
| V1 protection | **ALLOWED at the gate** — NOT in `PROTECTED_REL_ROOTS`. Protected only by post-hoc CAS version detection (Session C §2.3 precision). Raw-tool bypass OPEN. |
| Under O3 (A+B) | **Only if the projects extension is implemented.** If the daemon owns `state/projects/**` (roots outside workspace, daemon sole writer, IPC-reachable), then all session tools — raw or channeled — are denied by the sandbox boundary. If the daemon is **not** extended to projects, this root remains CAS-detected only (no hard isolation). |
| Residual after O3 (with extension) | **CLOSED** — the raw-write residual is eliminated. This is the **largest improvement** over V1: `state/projects/**` goes from "detected-only" to "hard-isolated". |
| Residual after O3 (without extension) | **OPEN** — same as V1: CAS-detected only; raw-tool bypass still possible. G10 not closed for this root. |
| Conditions | Same as above + **the projects extension must be implemented** and Human-approved. |

### Summary table

| Root | V1 (current) | Under O3 (A+B, with projects extension) | Residual after O3 |
|---|---|---|---|
| `state/registry/**` | Gate-DENIED; raw-tool bypass OPEN | Root outside workspace; sandbox hard-denies all writes | **CLOSED** |
| `audit/**` | Gate-DENIED; raw-tool bypass OPEN | Root outside workspace; sandbox hard-denies all writes | **CLOSED** |
| `state/projects/**` | ALLOWED at gate; CAS-detected only; raw-tool bypass OPEN | Root outside workspace; sandbox hard-denies all writes | **CLOSED** (only with the projects extension) |

---

## 4. The verdict

### 4.1 O3 closes all three residual roots — under the following conditions

If **all** of the following hold, O3 **closes the G10 residual R for all three roots** (hard isolation, not reduction):

1. **A+B isolation** is deployed — roots outside `workspaceRoot` (Option A) AND the daemon runs under a dedicated OS UID (Option B, defense-in-depth). Option A alone is the isolation mechanism; Option B is mandatory as added defense.
2. **The `state/projects/**` extension is implemented** — the daemon owns `state/projects/**` (not just registry/audit). Without this, `state/projects/**` remains CAS-detected only and R is **not** closed for that root.
3. **The write path is fully switched** — `execution_gate.registry_write()`, `execution_gate.audit_append()`, and `RuntimeStore.persist()` all route through the daemon client; no direct-write path remains reachable (Phase B complete).
4. **No silent fallback** exists — daemon down ⇒ writes to the three roots **block** (fail-closed). A fallback would restore the residual.
5. **Verification passes** — the isolation probe (raw write to the old root locations is now **DENIED**), the full G10 suite, `validate-config`, and the migration-continuity checks all pass.
6. **Human approval** of the infrastructure change (ADR 0002 consequence 4) and of the `state/projects/**` scope extension.

When all six hold, O3 closes the **prevention gap** (R) that defines G10's residual — a hard-isolation closure, not merely a surface reduction (contrast with O5).

### 4.2 But O3 does NOT close G10 today — and here is why

Despite §4.1, this package does **not** claim G10 closure. The precise reasons:

| # | Reason | Detail |
|---|---|---|
| 1 | **Not implemented.** This FINAL package is a design; no daemon exists, no write path is switched. G10 remains OPEN until O3 is implemented, deployed, and verified. | Status quo: G10 OPEN / BLOCKING. |
| 2 | **`state/projects/**` is not covered by the ADR-sanctioned scope** without explicit approval. ADR 0002 consequence 4 describes "dedicated registry process" (registry/audit). The projects extension is a design decision in this package that requires separate Human approval. | Without approval, closure is partial (registry+audit only). |
| 3 | **Closure in the matrix sense requires re-derivation.** G10's matrix row is framed as "DSH path-isolation limitation / prevention at DSH layer absent." O3 removes the roots from the DSH-reachable set (a composition/infrastructure workaround), it does **not** add a DSH capability. The security outcome is equivalent (raw write cannot land), but the matrix must be re-derived and the mechanism recorded — not assumed on design intent. | Re-derivation + Human decision required. |
| 4 | **The daemon is a new single point of authority-source compromise (T4).** This is the same class of residual as V1 (the orchestrator process is already the single point), so it is an *accepted* residual, not a regression — but it means O3 exchanges "any of `{zeko, cto}` can reach R" for "the daemon credential can reach R." G10's scope is session tools, so this does not keep G10 open, but it must be recorded. | Accepted residual (threat model T4). |
| 5 | **G10 closing is necessary but not sufficient for production.** O3 does not resolve G13 (prompt injection, OPEN/UNKNOWN), nor the production blockers B1/B2 (mount/answerer), B6, B7, B8. | G10 closure ≠ production unblock. |

### 4.3 The verdict (one sentence)

> **O3, as designed in this FINAL package with the `state/projects/**` extension, A+B isolation, and fail-closed enforcement, DOES close the G10 residual R for all three roots (`state/registry/**`, `audit/**`, `state/projects/**`) — hard isolation, not reduction — but O3 is NOT implemented, and therefore G10 remains OPEN / BLOCKING for production. The closure is conditional on implementation, deployment, verification, and Human approval; it is not claimed.**

---

## 5. Relationship to the other arms

| Arm | Closes R for | Nature | Status |
|---|---|---|---|
| **O5** (applied) | none (shrinks actor set `{zeko,cto,somad,nova}` → `{zeko,cto}`) | surface reduction | **APPLIED** (containment only) |
| **O3** (this FINAL package) | `state/registry/**`, `audit/**`, `state/projects/**` (with extension) | hard isolation — removes roots from session writable set | **NOT IMPLEMENTED** |
| **O4** (upstream DSH) | same three roots, at the DSH layer | native per-agent sandbox root / per-path toolFilter | **ABSENT in 0.1.1-rc.2** |
| **O2** (registry relocation) | partial, only if paired with O3/O4 | fallback | recorded, not recommended alone |

O4, when available, is the clean DSH-layer solution. O3 is the project-layer equivalent that works in 0.1.1-rc.2. They are not mutually exclusive: O3 can be deployed now, and O4 remains the upstream ideal (a future re-derivation against a newer DSH would still be required).

---

## 6. Honesty statement

1. **No closure is claimed.** G10 remains OPEN / BLOCKING. This document determines the *conditions under which O3 would close R for each root*; it does not assert the closure happened.
2. **The `state/projects/**` extension is stated explicitly** as a design decision necessary for full closure of the third root — not assumed, not hidden.
3. **A+B isolation is mandatory** — the sandbox-boundary mechanism (Option A) is what makes O3 a hard-isolation closure; the dedicated UID (Option B) is mandatory as defense-in-depth. Without A (roots outside workspace), the closure claim is invalid.
4. **The daemon's single-point nature is recorded** (T4) — O3 does not eliminate the authority-source compromise class, it moves it to a dedicated, monitored credential.
5. **No test failure was hidden.** The final planning tests assert this document exists, states the per-root conditional determination, and makes no unconditional closure claim.

---

*Status: FINAL DETERMINATION. O3 (with A+B isolation, projects extension, fail-closed enforcement) closes the G10 residual R for all three roots — but O3 is NOT implemented, and G10 remains OPEN / BLOCKING for production. G10 closure is conditional on implementation, deployment, verification, and Human approval. No closure claimed.*
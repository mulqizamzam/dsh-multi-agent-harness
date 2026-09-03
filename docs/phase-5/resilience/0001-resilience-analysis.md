# Phase 5 / Session D — Resilience & Registry Gate Analysis (G4 + G9)

- **Milestone**: Phase 5 / Session D — RESILIENCE + REGISTRY GATE (G4 + G9)
- **Status**: ANALYSIS + SPEC + DETERMINISTIC TESTS (write-only: `tests/resilience/` + `docs/phase-5/resilience/`). **No production control change. No DSH/core/profile/preset/session-policy change. No L3 claim. No live-DSH proof.**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/resilience/` (this document + `0002-resilience-spec.md`) and `multi-agent-harness/tests/resilience/` (test suite).
- **Inputs**: `docs/phase-4/0005-production-readiness-assessment.md` (G4 §4.4/§6.8/§7.1, G9 §5.3/§7.3) · `docs/phase-4/0001-acceptance-matrix.md` (AUTH-3, PB-4, ISO-LIVE-006) · `docs/phase-3/0001-live-int11-int12-evidence.md` (BLOCKED: 429 observation) · `docs/runbooks/07-execution-failure.md` · `docs/runbooks/08-recovery-failure.md` · `docs/adr/0002-registry-protection-mechanism.md` · `control/execution_gate.py` · `control/recovery.py` · `orchestrator/runtime/{flow,collection,parallel}.py` · `state/helpers/recovery.py`.

---

## 1. Summary

| Gap | What exists | What this session proves (deterministic) | What remains |
|---|---|---|---|
| **G4** — provider 429 / rate-limit exposure | Runtime classifies provider failures; no blind retry (AUTH-INV-16/REC-001); environment class routes to recovery; unknown escalates | 429 → `environment` classification; no blind retry; no retry amplification; deterministic recovery/escalation routing | No retry scheduling / backoff / dedicated capacity (Phase-4 §6.8 operational residual). Bounded-backoff recommendation recorded — **not implemented** (requires production change). |
| **G9** — ISO-LIVE-006 registry-write live denial | Path-aware execution gate + sanctioned single-writer channels (ADR 0002); REG-001..005, PATH tests | Non-sanctioned write to `state/registry/` / `audit/` DENIED **before mutation**; sanctioned channels work; no cross-root writer grant; denial audited | **ISO-LIVE-006 live variant BLOCKED** (no mounted DSH session). DSH-layer hard isolation for bash-wielding roles remains Phase-5 hardening — **not closed**. |

Both gaps are **DEFERRED→CLOSED-at-deterministic-level** with a named live
residual. See §6 (status roll-up) for the exact wording — neither is claimed
"production-closed".

---

## 2. G4 — Provider 429 / rate-limit resilience

### 2.1 What the runtime already does (VERIFIED by inspection + test)

A provider rate limit observed during Phase-3 live runs (HTTP 429,
`docs/phase-3/0001` BLOCKED section) is an **environment-class** failure — not
a runtime/control failure. The runtime's existing handling:

1. **Typed adapter vocabulary** (`orchestrator/dsh/exceptions.py`): dispatch
   failures surface as typed exceptions (`DelegationTimeout`,
   `DelegationAborted`, `ChildFailure`, ...) — never prose.
2. **Deterministic classification** (`orchestrator/runtime/collection.py::classify_adapter_failure`):
   maps typed adapter errors to `(failure_class, reason)`.
   - `DelegationTimeout` / `DelegationAborted` / `RoleResolutionError` → `environment`
   - `ChildFailure` / `MalformedResult` → `logic`
   - `ProhibitedDelegation` / `DelegationDenied` → `authorization`
   - **anything else → `unknown`** (mandatory escalation, Runbook 08)
3. **No blind retry** (`control/recovery.py::request_retry`, AUTH-INV-16 /
   REC-001): an empty cause and an identical cause are refused; a retry
   requires a **new** diagnosed cause and respects the attempt cap
   (`state/helpers/recovery.py::DEFAULT_MAX_ATTEMPTS = 1`).
4. **Deterministic routing** (`orchestrator/runtime/flow.py::run`):
   - `SubtaskFailed(failure_class=environment)` → `_route_recovery` →
     `RECOVERING` with a `RecoveryRecord` (STOP → PRESERVE, failure_class
     preserved).
   - `SubtaskFailed(failure_class=unknown)` → `_stop(escalated=True)` →
     `ESCALATED` (Runbook 08 — the runtime never guesses a failure class).
5. **No retry amplification**: recovery's `can_retry` is a total attempt bound
   (`attempts >= max_attempts`), so a burst of identical causes consumes at
   most one retry per cause; distinct new causes are bounded by the cap.

**The Phase-3 observation confirms the pattern**: each retried dispatch was a
**new** dispatch after the diagnosed cause (provider rate limit) cleared —
never an identical-cause automatic retry; the failing first-batch children
were abandoned, not silently reused.

### 2.2 What remains (Phase-4 §6.8 operational residual)

- **No retry scheduling / backoff policy / dedicated capacity.** The runtime
  correctly *handles* a 429 (no blind retry, deterministic route), but it does
  not *schedule* a bounded retry with backoff, and there is no dedicated
  capacity for parallel live dispatch. A 429 therefore translates into a
  user-facing delay and (for parallel batches) the batch stops fail-closed.
- **No provider-side rate-limit management** (Phase-4 §4.4 resolution: either
  provider-side management or a documented operational procedure).

### 2.3 Recommendation (recorded — NOT implemented here)

**Do not weaken the no-blind-retry rule.** The documented rule is: a retry
happens only on a **new diagnosed cause**. A bounded-backoff recommendation
must preserve that invariant:

> **REC-G4-1 (future implementation, not this session):** a *bounded backoff
> scheduler* at the dispatch layer that, on an environment-class dispatch
> failure with a diagnosed transient cause (e.g. 429), waits a bounded,
> non-escalating delay and then issues a **new dispatch** (new child run) —
> never an identical-cause automatic retry of the same run. The backoff must
> (a) respect the existing attempt cap, (b) require a diagnosed transient
> cause, (c) be bounded (no exponential blow-up), and (d) route through the
> same recovery/escalation path when the cap is exhausted or the cause is not
> transient.

This is deliberately **NOT implemented** in this session: it is a production
runtime change, out of the write scope (tests + docs only), and any
implementation must be a separate reviewed change. The deterministic suite
proves the *current* behavior (which is the invariant the future scheduler
must preserve).

---

## 3. G9 — Runtime registry protection (deterministic equivalent of ISO-LIVE-006)

### 3.1 The mechanism (ADR 0002, VERIFIED by inspection + test)

The delegation registry is the project's **authority source**; an unauthorized
write to it is a forged-authority attack (THREAT-004/007). The mechanism is a
**path-aware execution gate + sanctioned single-writer channels** in
`control/execution_gate.py`:

| Element | Semantics |
|---|---|
| `PROTECTED_REL_ROOTS = ("state/registry", "audit")` | Protected roots (exact-or-descendant match with path-separator boundary; prefix confusion prevented). |
| `SANCTIONED_ROOTS = {"registry_write": "state/registry", "audit_append": "audit"}` | Per-channel scope: a sanctioned channel may write **only its own root**. |
| `authorize_write(action, target, ...)` | DENY: protected path by a non-writer; `writer=True` on a generic action grants nothing on protected paths; traversal / malformed / outside-workspace targets; cross-root or non-protected targets for a sanctioned channel. ALLOW: ordinary workspace write (CTO/Zeko capability kept). |
| `write_through` | Single enforcement point: gate first, then atomic write. Raises `Denied` **before any mutation**. |
| `registry_write` / `audit_append` | Sanctioned control-plane channels, scoped to their own root. |

**Boundary (honest):** the gate governs writes that **route through the
project write channel**. A raw DSH `write`/`edit`/`bash` tool call that
bypasses the project channel is **not intercepted** — DSH has no path-level
sandbox (ADR 0001 Decision 1, ADR 0002). This is the documented ADR 0002
residual; it is **not claimed closed** here (see §3.4).

### 3.2 What ISO-LIVE-006 would prove live (and why it is BLOCKED here)

ISO-LIVE-006 (Phase-4 matrix AUTH-3 / PB-4) is the **live** variant: a real
DSH child (a bash-capable role under a mounted D4/D7 composition) attempting a
raw write to `state/registry/` must be denied, with the denial observed at
runtime. It **cannot run in this session**:

- `DSH_LIVE_BRIDGE_ACTIVE` is **not set**; no live DSH children can be
  dispatched without re-mounting the D4/D7 composition (Phase-4 §4.1 / §7.3,
  G9: "requires D4/D7 mount").
- No live mount exists in this session → the live variant is **BLOCKED**, and
  the deterministic equivalent is asserted instead (tests assert the gate
  denial + sanctioned-channel success in a throwaway workspace).

### 3.3 What the deterministic suite proves

The suite (`tests/resilience/test_registry_gate.py`) proves, against a
throwaway workspace mirroring the protected layout:

1. **Non-sanctioned write to `state/registry/` → DENY before mutation** (no
   file created, no directory entry added, no residue) — for root, file, and
   deep-descendant targets.
2. **Non-sanctioned write to `audit/` → DENY before mutation** — same checks.
3. **`writer=True` on a generic action grants nothing** on protected paths.
4. **Traversal to a protected root → DENY**; **prefix confusion is prevented**
   (`state/registry-evil` is not `state/registry`).
5. **Sanctioned channels still work**: `registry_write` → `state/registry/**`,
   `audit_append` → `audit/**`.
6. **Sanctioned channels cannot cross roots** and cannot write ordinary
   workspace paths (Session-A hardening preserved).
7. **No-regression**: a flow whose execution plan targets a protected path is
   `BLOCKED`, the denial is recorded in the audit ledger (`execution_denial`),
   and no file is written (no partial allow).
8. **ISO-LIVE-006 live variant named BLOCKED** (skip with reason) + the
   deterministic equivalent asserted.

### 3.4 The residual (NOT closed — Phase-5 hardening, documented)

- **DSH-layer hard isolation for bash-wielding roles is NOT closed.** A
  bash-capable role (Zeko/CTO/Somad/Nova) can, in principle, reach a protected
  path through a raw DSH tool call that bypasses the project channel
  (`docs/phase-5/0001-security-hardening-analysis.md` §1.2, PS-1). The L1 gate
  + CAS + append-only hash chain make tampering **detectable** (REG-003,
  AUD-*), not **preventable at the DSH layer**. Closing it (dedicated registry
  process / out-of-workspace sandbox root / reduced bash surface) is Phase-5+
  hardening gated on a Human-approved composition change — **do not claim it
  closed**.
- **ISO-LIVE-006 live proof is absent.** The deterministic equivalent is
  strong but is not a live-DSH observation.

---

## 4. Honesty section — proven vs. needs-a-live-session

| Claim | Level | Evidence |
|---|---|---|
| 429/rate-limit classifies as `environment` (deterministic) | **Proven (deterministic)** | `tests/resilience/test_429_rate_limit.py::test_429_classifies_environment` |
| No blind retry; no retry amplification; deterministic recovery/escalation routing | **Proven (deterministic)** | `test_429_rate_limit.py` (retry guards + flow routing tests); INT-12 live evidence already documented |
| Non-sanctioned write to protected roots DENIED before mutation; sanctioned channels work | **Proven (deterministic)** | `tests/resilience/test_registry_gate.py` |
| ISO-LIVE-006 live denial at the DSH layer | **BLOCKED** — needs mounted DSH session | live variant skip-marked in `test_registry_gate.py` |
| DSH-layer hard isolation for bash-wielding roles | **NOT claimed** — Phase-5 hardening residual | `docs/phase-5/0001-security-hardening-analysis.md` |
| Bounded backoff / retry scheduling for 429 | **NOT implemented** — recommendation only (REC-G4-1) | §2.3 of this document |

**No new security claims are made.** No production security control was
modified, weakened, or bypassed. The deliverable is tests + docs.

---

## 5. Files

**Added (write-only scope):**

- `tests/resilience/__init__.py`
- `tests/resilience/conftest.py`
- `tests/resilience/test_timeout_abort.py`
- `tests/resilience/test_429_rate_limit.py`
- `tests/resilience/test_registry_gate.py`
- `tests/resilience/README.md`
- `docs/phase-5/resilience/0001-resilience-analysis.md` (this file)
- `docs/phase-5/resilience/0002-resilience-spec.md` (spec)

**Not modified:** `control/`, `orchestrator/`, `state/`, `audit/`, `config/`,
`schemas/`, `agents/`, any existing test file, any `docs/` outside
`docs/phase-5/resilience/`. No DSH core/profile/preset/session-policy change.
No new tools. No Agent Teams. No Phase 6.

---

*Status: ANALYSIS. G4 and G9 addressed at the deterministic level with tests
and docs; live variants named BLOCKED; residuals recorded, not closed.*

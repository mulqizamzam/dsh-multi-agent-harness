# Critical-Control L3 Readiness — Phase 5 / Session C

- **Milestone**: PHASE 5 / SESSION C — L3 CRITICAL CONTROL READINESS
- **Status**: **READY_TO_REHEARSE, NOT READY_TO_CLAIM** (critical bundles + rehearsal runner built and green; **no live L3 run, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `tests/l3_reference/critical/` · `tests/l3_runner/critical/` · `docs/phase-5/l3/` (write-only per the session brief).
- **Companion**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/security/0007-l3-run-prerequisites.md` · `docs/design/0002-l3-verification-specification.md` · `docs/phase-5/l3/0001-l3-execution-readiness.md` · `docs/phase-5/l3/0002-g5-verifier-implementation-report.md` · `tests/l3_runner/` (runner, verifier, validator, rehearsal) · `tests/l3_reference/` (oracles, schemas, fixtures).

---

## 1. Decision

**L3 = L3 CRITICAL.** The six critical controls that must be independently verifiable before any L3 claim are:

| # | Critical control | Scenario bundle(s) |
|---|---|---|
| 1 | **authority grant/revoke/expiry** | `L3-AUTH-001` (grant ALLOW), `L3-AUTH-003` (expiry DENY), `L3-AUTH-004` (revocation DENY) |
| 2 | **execution-time recheck** | `L3-AUTH-006` (revoked between planning and execution → DENY) |
| 3 | **protected-path execution** | `L3-PATH-001` (write to `state/registry/**` → DENY, ADR 0002) |
| 4 | **recovery privilege bounding** | `L3-REC-004` (recovery attempting out-of-scope action → DENY, AUTH-INV-12) |
| 5 | **stale-state protection** | `L3-ST-003` (stale-version CAS → DENY, THREAT-021) |
| 6 | **audit integrity** | `L3-AUD-002` (tampered ledger → INVALID, THREAT-018) |

Eight scenario bundles cover the six critical controls.

---

## 2. What was built

| Deliverable | Location | Notes |
|---|---|---|
| Critical fixture bundles (8) | `tests/l3_reference/critical/fixtures/<L3-*>/` | Each has `plan.json` (Human-signed O4 template), `fixture.json` (gate, oracle classes, oracle context, provenance), `runtime-recorded.json` (recorded runtime verdict + audit slice) |
| Tampered-ledger audit fixture | `tests/l3_reference/critical/fixtures/L3-AUD-002/` | `ledger.jsonl` (tampered), `ledger.original.jsonl` (untampered baseline), `ledger.chain` (chain sidecar over the original) — the independent chain check must flag `ledger.jsonl` INVALID |
| Critical runner | `tests/l3_runner/critical/runner.py` | `run_critical_rehearsal`, `run_all_critical_rehearsals`, `critical_readiness_report`, CLI |
| Critical readiness tests | `tests/l3_runner/critical/test_critical_readiness.py` | 127 tests: fixture existence/schema, rehearsal completeness, P1–P4, oracle classes, IO-1/IO-2 honesty, replay determinism, audit-chain tamper detection, no-L3-claim, no repo `audit/l3/` writes |

**The O1 oracles themselves are the existing, proven `tests/l3_reference/*` modules** (authority_gate, execution_gate, recovery_gate, transition_gate, audit_chain). This session's contribution is the **critical scenario definition + rehearsal proof** that those oracles agree with the recorded runtime verdicts for the six critical controls.

---

## 3. P1–P4 readiness (per property)

| Property | Required | Critical readiness |
|---|---|---|
| **P1 — Runtime** | The control is exercised against a running harness/session (or a real/emulated filesystem) | **REHEARSAL-READY.** Each scenario has a `runtime-recorded.json` replayed by `RecordedRuntimeDriver`; the bundle captures `runtime-verdict.json` + audit slice. A **live** DSH run (P1-live) is NOT available — `LiveDSHRuntimeDriver` remains a stub. |
| **P2 — Independent observer** | Verifier is a separate process (separate PID; separate UID required for a claim) | **REHEARSAL-READY.** Runner spawns the verifier via `subprocess`; **IO-1 (distinct PID) passes** for all 8 scenarios; **IO-2 (distinct UID) fails honestly** on this same-UID host — any same-UID rehearsal is demoted to non-L3 (`L3-INDEPENDENCE-VIOLATION`), never upgraded. |
| **P3 — ≥ 2 independent oracle classes** | At least two of O1..O4, at least one not the runtime itself | **READY.** All 8 bundles declare ≥2 classes: O1 (independent reference oracle) + O3 (on-disk state hash) or O2 (schema-as-oracle) + O4 (Human-signed plan). Runner R6 / validator LV8 enforce ≥2. |
| **P4 — Reproducible replay** | Deterministic fixture hash, verifier binary sha256, schema sha256, recorded replay command | **READY.** `fixture_hash` deterministic across rehearsals (tested), `replay.json` (E11) records fixture hash + replay command; `tests/l3_runner/replay.sh` is the shell re-run entry. |

---

## 4. Rehearsal results (all 8 scenarios)

```text
.venv-tests/bin/python -m pytest tests/l3_runner/critical/ -q
127 passed
```

| Scenario | Gate | Expected | P1 | IO-1 | IO-2 | ≥2 oracles | Replay hash | match=true | l3_claim |
|---|---|---|---|---|---|---|---|---|---|
| L3-AUTH-001 | authority | ALLOW | ✓ | ✓ | ✗ (same-UID) | ✓ | ✓ | ✓ | false |
| L3-AUTH-003 | authority | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-AUTH-004 | authority | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-AUTH-006 | authority | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-PATH-001 | execution_gate | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-REC-004 | recovery | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-ST-003 | state_transition | DENY | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |
| L3-AUD-002 | audit_integrity | INVALID | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | false |

Every rehearsal produces a **complete 13-file evidence bundle** under a scratch base, **never** the repo `audit/l3/`. Every bundle carries `l3_claim=false` and fails **LV10 by design** (a rehearsal is not an L3 bundle). **No rehearsal claims L3.**

---

## 5. Live readiness (NOT met — by design)

| Prerequisite | Status | Why |
|---|---|---|
| Live DSH runtime (P1-live) | **NOT READY** | `LiveDSHRuntimeDriver` is a safe stub; `runner.py` refuses `--mode live`. |
| Separate UID / credential (IO-2) | **NOT READY** | This sandbox runs orchestrator + verifier under the same host UID; IO-2 fails honestly and `l3_claim_possible=false` (`tests/l3_runner/uid_readiness.py`). |
| Human-signed plan with real identity (O4) | **FIXTURE-ONLY** | The critical `plan.json` files are inert templates with placeholder signoff fields. A real Human must sign each before a live run (`tests/l3_runner/plan_signing.py` signing checklist). |
| Authorized live run | **NOT AUTHORIZED** | `docs/security/0003` §15 prerequisites (Human acceptance, `workspace-write + ask` baseline, production control-plane code) are not all met. |

---

## 6. L3 claim status

**NO L3 CLAIM.** Zero critical controls are claimed L3. All eight scenarios are rehearsal-only: `l3_claim=false`, LV10 fails by design, IO-2 fails honestly on the same-UID host. A claim would additionally require a live DSH run (P1-live), a separate-UID verifier (P2/IO-2), a real Human-signed plan (O4), and an authorized run — none of which hold in this session.

---

## 7. Verified / UNKNOWN / BLOCKED

### Verified (this session)
- All 8 critical bundles exist, are schema-valid (plan), declare ≥2 oracle classes, and have signoff-before-runtime ordering.
- All 8 rehearse end-to-end to a complete bundle with `match=true` (runtime vs reference agree), `l3_claim=false`, LV10-by-design.
- IO-1 (distinct PID) passes for all scenarios; IO-2 (distinct UID) fails honestly on this same-UID host.
- The independent `audit_chain` oracle detects the tampered ledger (INVALID) and accepts the original (VALID).
- No repo `audit/l3/` writes; no live L3 execution; no production code touched.
- Full L3 suite: `tests/l3_runner/` + `tests/l3_reference/` = **275 passed**. Full project suite: **1769 passed, 15 skipped**.
- **LV16 shape note RESOLVED (Session F):** the recovery, state_transition, and audit_integrity oracles now emit the canonical `checklist_item_results` field in `reference-verdict.json` (preserving the per-check diagnostic data that previously lived under `detail`), so `L3-REC-004`, `L3-ST-003`, `L3-AUD-002` pass LV16. Validator unchanged; no LV16 requirement removed; no validation weakened.

### UNKNOWN
- Whether a live DSH session would reproduce the recorded verdicts byte-for-byte (P1-live not exercised; `LiveDSHRuntimeDriver` is a stub).
- Whether the same-UID host could be re-baselined to separate credentials for a real run (requires infra/Human action outside this session).

### BLOCKED
- **Live L3 run (P1-live + IO-2 + real O4)** — all prerequisite gaps above.

---

## 8. How to run

```bash
# Critical readiness tests (127)
.venv-tests/bin/python -m pytest tests/l3_runner/critical/ -q

# Critical readiness report (CLI)
.venv-tests/bin/python -m tests.l3_runner.critical.runner --json

# Full L3 suite
.venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
```

---

## 9. Scope check

**In scope (written this session):**
- `tests/l3_reference/critical/` — `__init__.py`, `fixtures/` (8 scenario bundles + L3-AUD-002 ledger/chain artifacts)
- `tests/l3_runner/critical/` — `__init__.py`, `runner.py`, `test_critical_readiness.py`
- `docs/phase-5/l3/0003-critical-control-readiness.md` (this file)

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, DSH core/profile/preset/session policy, and the L3 **validator** (`tests/l3_runner/validator.py`, its LV16 rule, and the root fixtures) — untouched. The LV16 shape mismatch was resolved at the oracle layer in a later session (Session F): the three reference oracles emit `checklist_item_results` while preserving their diagnostic detail.

---

*Status: READY_TO_REHEARSE, NOT READY_TO_CLAIM. Critical bundles + rehearsal runner green (127 tests). No live L3 run executed. No control claimed L3. No production code, DSH core/profile/preset, or session policy modified.*
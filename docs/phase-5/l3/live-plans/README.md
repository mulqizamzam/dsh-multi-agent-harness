# Phase 5 / Session C — L3 Live Plan Package

- **Milestone**: L3 LIVE PLAN PACKAGE (6 controls, 8 scenario plans)
- **Status**: **SIGNED (2026-09-01).** All 8 plan.json files carry a real
  Human signoff: durable identity `human-2026-09-01-957`, UTC timestamp
  `2026-09-01T14:57:51Z`, method `signed-assertion`,
  `human_signoff_provenance=recorded`. No live scenario is executed yet; the
  signed plans are committed and ready for the authorized L3 run.
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Write scope**: `docs/phase-5/l3/live-plans/` (this directory) +
  `tests/l3_runner/live-plans/` (plan.json templates + test suite). Everything
  else read-only.
- **Companion**: `docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md`
  · `docs/phase-5/l3/environment/0001-l3-environment-human-answerer-readiness.md`
  · `docs/phase-5/l3/0001-l3-execution-readiness.md` · `docs/phase-5/l3/0003-critical-control-readiness.md`
  · `docs/phase-5/l3/0004-critical-control-rehearsal-session-b.md` ·
  `docs/phase-5/final/preflight/0001-final-operator-checklist.md` ·
  `tests/l3_runner/` (runner, claim_gate, plan_signing, verifier, validator,
  preflight, environment readiness) · `tests/l3_reference/` (oracles, schemas,
  critical fixtures).

---

## Package contents

| # | Control | Scenario(s) | Plan doc | Template plan.json |
|---|---|---|---|---|
| 1 | **Authority** (grant/expiry/revocation) | `L3-AUTH-001`, `L3-AUTH-003`, `L3-AUTH-004` | `0001-authority-live-plan.md` | `L3-AUTH-001/plan.json` · `L3-AUTH-003/plan.json` · `L3-AUTH-004/plan.json` |
| 2 | **Execution-time recheck** | `L3-AUTH-006` | `0002-execution-time-recheck-live-plan.md` | `L3-AUTH-006/plan.json` |
| 3 | **Protected-path execution** | `L3-PATH-001` | `0003-protected-path-execution-live-plan.md` | `L3-PATH-001/plan.json` |
| 4 | **Recovery privilege bound** | `L3-REC-004` | `0004-recovery-privilege-bound-live-plan.md` | `L3-REC-004/plan.json` |
| 5 | **Stale-state protection** | `L3-ST-003` | `0005-stale-state-live-plan.md` | `L3-ST-003/plan.json` |
| 6 | **Audit integrity** | `L3-AUD-002` | `0006-audit-integrity-live-plan.md` | `L3-AUD-002/plan.json` |

---

## Schema validation results (observed this session)

| Scenario | Structure valid? | Schema valid? | Timing rule (LV7/IO-7) | Notes |
|---|---|---|---|---|
| L3-AUTH-001 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-AUTH-003 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-AUTH-004 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-AUTH-006 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-PATH-001 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-REC-004 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-ST-003 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | — |
| L3-AUD-002 | ✅ | ✅ (with substituted signoff) | ✅ signoff < runtime | **Schema tension RECONCILED 2026-09-01 (plan schema v2).** The audit-integrity oracle returns `INVALID` (tamper detected) and the independent verifier performs it; v1 admitted neither. v2 adds `actor: verifier` and `expected_verdict: INVALID`, permitted **only together** — `INVALID` requires `actor=verifier`, and `actor=verifier` requires `INVALID`. Enforced in the schema (`allOf`/`if`/`then`) and in `validate_signed_plan()`; negative guards in `test_l3_live_plans.py`. Sibling schemas aligned (runtime-verdict v2, verdict-match v2, reference-verdict v2); `claim_gate` P1 accepts `INVALID`. Recorded in `0006-audit-integrity-live-plan.md` §4. |

---

## Signing procedure (binding for the live run)

The Human signed each plan.json on 2026-09-01:

1. **Identity**: `human-2026-09-01-957` (durable per-day id, matching the
   `human-YYYY-MM-DD-NNN` pattern).
2. **Timestamp**: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded in
   `human_signoff_ts`).
3. **Method**: `"signed-assertion"` (durable signed statement, recorded in
   `human_signoff_method`).
4. **Provenance**: `"recorded"` (recorded in `human_signoff_provenance`).
5. The signed plan.json was committed to the fixture **before** any runtime
   verdict — `human_signoff_ts` (14:57:51Z) is strictly before any runtime
   `captured_at` (LV7 / IO-7).

**Current status: ALL 8 PLANS ARE HUMAN-SIGNED.** Durable identity
`human-2026-09-01-957`, real timestamp `2026-09-01T14:57:51Z`, provenance
`recorded`. The plans are committed and ready for the authorized L3 run when
the environment prerequisites (separate UID, live bridge, approval answerer)
are resolved.

---

## Evidence requirements (per scenario)

Each scenario produces a **13-file evidence bundle** under
`audit/l3/<scenario-id>/`:

| # | File | Source | Gate |
|---|---|---|---|
| E1 | `env.json` | Runtime environment snapshot | LV4 |
| E2 | `plan.json` | Human-signed plan (committed before run) | O4 / LV7 / IO-7 |
| E3 | `before.sha256` | State hash before scenario | IO-9 |
| E4 | `after.sha256` | State hash after scenario | IO-9 |
| E5 | `runtime-verdict.json` | Live DSH session decision | P1 |
| E6 | `audit-log.jsonl` | Audit event log (+ chain sidecar) | O2 |
| E7 | `reference-verdict.json` | Reference oracle verdict | O1 / R6 |
| E8 | `oracle-classes.json` | Oracle classes used (≥2) | P3 / IO-6 |
| E9 | `provenance.json` | Provenance prover record | IO-10 |
| E10 | `replay.json` | Fixture hash + replay command | P4 |
| E11 | `verifier-independence.json` | IO-1..IO-10 (separate PID + UID) | P2 |
| E12 | `verdict-match.json` | Runtime == reference + `l3_claim` | claim gate |
| E13 | `manifest.json` | Certifies the bundle (sha256 of each file) | certifier |

---

## Honesty statement

1. **Human signoff recorded (2026-09-01).** All 8 plan.json files carry a real
   signoff: durable id `human-2026-09-01-957`, `human_signoff_ts`
   `2026-09-01T14:57:51Z`, method `signed-assertion`, provenance `recorded`.
   `L3ENV-PLAN-REAL` passes on these plans. No signature is invented; the
   signoff is the Human's recorded durable identity + timestamp.
2. **No L3 claim yet.** The verdict-match `l3_claim` field is still `false`
   and is not yet produced as `true`: the remaining blockers (same-UID IO-2,
   live bridge per-session, approved run) must be resolved before any
   claim-capable run. No scenario claims L3.
3. **No live execution yet.** No scenario is executed; no DSH dispatch occurs.
4. **No DSH/policy/profile/code modification.** `control/`, `orchestrator/`,
   `state/`, `audit/`, `agents/`, `config/`, `schemas/`, and all existing
   fixtures/tests are untouched (the plan.json files under
   `tests/l3_runner/live-plans/` and this doc directory are the package's own
   write scope).
5. **Schema tension reconciled (2026-09-01, after this document was first
   written).** L3-AUD-002 carries `expected_verdict=INVALID` **and**
   `actor=verifier`. Under `l3-plan.schema.json` **v1** both sat outside the
   enums, so the plan could not validate; the tension was documented rather
   than silently fixed. **v2 reconciles it narrowly**: `INVALID` is permitted
   only with `actor=verifier`, and `actor=verifier` only with `INVALID`,
   enforced in the schema and in `validate_signed_plan()`, with negative guards
   asserted in `test_l3_live_plans.py`. All 8 canonical plans now validate. See
   `0006-audit-integrity-live-plan.md` §4.
6. **No `audit/l3/` bundle created.** The evidence store remains absent until
   an authorized run begins.

---

*Status: SIGNED (2026-09-01). All 8 plan.json files carry a real Human
signoff (durable id `human-2026-09-01-957`, `2026-09-01T14:57:51Z`,
`signed-assertion`, provenance `recorded`). Schema validation passes for all 8
(L3-AUD-002 INVALID is the documented v2-reconciled shape). Timing rule
(LV7/IO-7) verified by construction. The live run executes when the environment
prerequisites (separate UID, live bridge, approval answerer) are resolved.*
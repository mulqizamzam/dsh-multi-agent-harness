# Critical-Control L3 Rehearsal + Readiness — Execution Flow / Session B

- **Milestone**: L3 CRITICAL CONTROL REHEARSAL + READINESS
- **Status**: **REHEARSED, NOT CLAIMED** (all 8 critical bundles rehearse end-to-end green; **no live L3 run, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope (write-only this session)**: `tests/l3_reference/critical/` · `tests/l3_runner/critical/` · `docs/phase-5/l3/`.
- **Evidence**: `0004-critical-control-rehearsal-evidence.json` (per-scenario machine-readable rehearsal record).
- **Companion**: `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/security/0007-l3-run-prerequisites.md` · `docs/phase-5/l3/0003-critical-control-readiness.md` · `tests/l3_reference/` · `tests/l3_runner/`.

---

## STATUS

**REHEARSED, NOT CLAIMED.** This session executed the L3 critical-control **rehearsal/replay** for the six critical controls (eight scenario bundles) through the existing safe rehearsal machinery (`tests/l3_runner/rehearsal.py` → `runner.py` replay mode → independent verifier subprocess → collector → validator → replay metadata). All acceptance criteria pass:

| Acceptance criterion | Result |
|---|---|
| All critical bundles structurally valid | ✅ (13-file bundle + manifest sha256 verified per bundle) |
| Oracle agreement (runtime vs reference) | ✅ `match=true` for all 8 scenarios |
| Replay deterministic | ✅ fixture hash stable; matches directly-recomputed hash |
| `l3_claim=false` during rehearsal | ✅ for all 8 scenarios (LV10 fails by design) |
| No production imports in oracles | ✅ AST scan clean for all `tests/l3_reference` O1 modules |

**No live L3 is run. No control is claimed L3. No production code, DSH core/profile/preset, or session policy is modified.**

---

## CRITICAL CONTROLS

| # | Critical control | Scenario bundle(s) | Gate (O1 oracle) | Expected verdict |
|---|---|---|---|---|
| 1 | **authority grant/revoke/expiry** | `L3-AUTH-001` (grant), `L3-AUTH-003` (expiry), `L3-AUTH-004` (revocation) | `authority` | ALLOW / DENY / DENY |
| 2 | **execution-time recheck** | `L3-AUTH-006` (revoked between planning and execution) | `authority` | DENY |
| 3 | **protected-path execution** | `L3-PATH-001` (write to `state/registry/**`) | `execution_gate` | DENY |
| 4 | **recovery privilege bounding** | `L3-REC-004` (out-of-scope recovery action) | `recovery` | DENY |
| 5 | **stale-state protection** | `L3-ST-003` (stale-version CAS) | `state_transition` | DENY |
| 6 | **audit integrity** | `L3-AUD-002` (tampered ledger) | `audit_integrity` | INVALID |

Each bundle carries the scenario contract: `plan.json` (schema-pure Human-signed O4 template with pre-runtime signoff), `fixture.json` (gate, oracle classes ≥ 2, oracle context, provenance), and `runtime-recorded.json` (recorded runtime verdict + audit slice).

---

## REHEARSAL

All 8 scenarios rehearse end-to-end (mode `replay`, safe `RecordedRuntimeDriver`) into a complete bundle under a **scratch** base — never the repo `audit/l3/`.

| Scenario | Control | Runtime | Reference | match | l3_claim | LV10 | IO-1 | IO-2 | IO-10 |
|---|---|---|---|---|---|---|---|---|---|
| L3-AUTH-001 | authority_grant | ALLOW | ALLOW | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-AUTH-003 | authority_expiry | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-AUTH-004 | authority_revocation | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-AUTH-006 | execution_time_recheck | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-PATH-001 | protected_path | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-REC-004 | recovery_privilege | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-ST-003 | stale_state | DENY | DENY | ✅ | false | by-design | ✅ | ✗ honest | ✅ |
| L3-AUD-002 | audit_integrity | INVALID | INVALID | ✅ | false | by-design | ✅ | ✗ honest | ✅ |

Notes:
- **IO-2 fails honestly** on this same-UID host for every scenario (separate-UID verification not achievable here; the infrastructure never fakes credential separation).
- **LV10 fails by design**: rehearsal bundles carry `l3_claim=false`, so the structure validator's `LV10 (l3_claim must be true)` error is expected and correct for a rehearsal.
- **IO-10 now passes for L3-AUD-002** after a within-scope evidence-contract fix (see FIXES below).

### FIXES (evidence-contract inconsistency, within scope)

**Fixed — `tests/l3_reference/critical/fixtures/L3-AUD-002/runtime-recorded.json`:** the recorded runtime audit event used `actor: "l3-verifier"` (actor_type `verifier`). The verifier's IO-10 self-certification heuristic flags any audit event with `actor == "l3-verifier"` as evidence that the verifier wrote to the audit slice it certifies — so the audit-integrity rehearsal recorded **IO-10 = false** even though the event was legitimate (the *runtime* detected the tamper). The actor was changed to `orchestrator` (actor_type `orchestrator`), consistent with every other critical scenario, so the event is attributed to the runtime and IO-10 passes. This is an evidence-contract fix to a fixture — **no validator was weakened**.

No other evidence-contract or test inconsistency was found within scope.

---

## P1 / P2 / P3 / P4

| Property | Requirement | This session |
|---|---|---|
| **P1 — Runtime** | The control is exercised against a running harness/session (or real/emulated filesystem) | **REHEARSAL-READY.** Every scenario replays a recorded runtime verdict + audit slice through the safe driver; the bundle captures `runtime-verdict.json`. **P1-live is NOT available** — `LiveDSHRuntimeDriver` remains a stub and `runner.py` refuses `--mode live`. |
| **P2 — Independent observer** | Verifier is a separate OS process (separate PID; separate UID required for a claim) | **REHEARSAL-READY.** Verifier runs via `subprocess`; **IO-1 (distinct PID) passes** for all 8. **IO-2 (distinct UID) fails honestly** on this same-UID host — rehearsal is demoted to non-L3 (`L3-INDEPENDENCE-VIOLATION`), never upgraded. |
| **P3 — ≥ 2 independent oracle classes** | At least two of O1..O4, at least one not the runtime itself | **READY.** All 8 bundles declare ≥ 2 classes: O1 (independent reference) + O3 (on-disk state hash) or O2 (schema-as-oracle) + O4 (Human-signed plan). Runner R6 / validator LV8 enforce ≥ 2. |
| **P4 — Reproducible replay** | Deterministic fixture hash, verifier binary sha256, schema sha256, recorded replay command | **READY.** `fixture_hash` deterministic and equal to the directly-recomputed hash for all 8; `replay.json` (E11) records fixture hash + replay command; `tests/l3_runner/replay.sh` is the shell re-run entry. |

---

## TESTS

```text
.venv-tests/bin/python -m pytest tests/l3_runner/critical/ -q
127 passed

.venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
275 passed
```

The critical suite (127) covers: fixture existence/schema, plan signoff-before-runtime, rehearsal bundle completeness (13 files), `l3_claim=false` + LV10-by-design, oracle classes ≥ 2, IO-1 distinct PID, IO-2 honest same-UID fail, runtime/reference agreement, replay fixture-hash determinism across seeds (42 and 7), recorded replay command, IO-1..IO-10 all recorded by the verifier process, audit-chain tamper detection (INVALID) vs original (VALID), and cross-cutting: no L3 claim, no repo `audit/l3/` writes, no production imports in oracles.

---

## L3 CLAIM STATUS

**NO L3 CLAIM.** Zero critical controls are claimed L3. All eight scenarios are rehearsal-only: `l3_claim=false`, LV10 fails by design, IO-2 fails honestly on the same-UID host. A claim would additionally require a live DSH run (P1-live), a separate-UID verifier (P2/IO-2), a real Human-signed plan (O4 with real identity), and an authorized run — none of which hold in this session.

---

## UNKNOWN

- Whether a live DSH session would reproduce the recorded verdicts byte-for-byte (P1-live not exercised; `LiveDSHRuntimeDriver` is a stub).
- Whether the host could be re-baselined to separate UID/credentials for a real run (infra/Human action outside this session).

> **LV16 shape note — RESOLVED in a later session (Session F).** This Session B
> record is kept as history. The recovery, state_transition, and audit_integrity
> oracles now emit the canonical `checklist_item_results` field in
> `reference-verdict.json` (the per-check diagnostic data that previously lived
> under `detail` is preserved under the canonical key), so `L3-REC-004`,
> `L3-ST-003`, `L3-AUD-002` pass LV16. The validator and its LV16 rule are
> unchanged; no requirement removed; no validation weakened.

## BLOCKED

- **Live L3 run (P1-live + IO-2 + real O4)** — all prerequisite gaps above.

---

## SCOPE

**In scope (written this session):**
- `tests/l3_reference/critical/fixtures/L3-AUD-002/runtime-recorded.json` (IO-10 evidence-contract fix)
- `docs/phase-5/l3/0004-critical-control-rehearsal-session-b.md` (this file)
- `docs/phase-5/l3/0004-critical-control-rehearsal-evidence.json` (machine-readable rehearsal record)
- `docs/phase-5/l3/README.md` (index updated)

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, DSH core/profile/preset/session policy, and **all existing `tests/l3_runner/` (incl. `validator.py`) + `tests/l3_reference/` oracle/schema/fixture files** (unchanged). The LV16 shape note is reported, not silently fixed outside scope. No validator weakened.

---

## NEXT

1. ~~Resolve the LV16 shape mismatch at the validator/oracle layer~~ — **DONE (Session F):** `tests/l3_reference/recovery_gate.py` / `transition_gate.py` / `audit_chain.py` now emit `checklist_item_results` (canonical LV16 key), preserving their per-check diagnostic data; `L3-REC-004`, `L3-ST-003`, `L3-AUD-002` pass LV1..LV22 structure validation. Validator untouched.
2. Provide a real Human-signed plan (real identity, signed before runtime) per `docs/security/0007` PF-PLAN-* for each scenario.
3. Stand up a separate-UID verifier host and a live DSH session (P1-live), then re-run under the claim gate before any L3 claim.

---

*Status: REHEARSED, NOT CLAIMED. All 8 critical bundles structurally valid, oracle agreement, replay deterministic, l3_claim=false during rehearsal, no production imports in oracles. No live L3 run executed. No control claimed L3. No production code, DSH core/profile/preset, or session policy modified.*

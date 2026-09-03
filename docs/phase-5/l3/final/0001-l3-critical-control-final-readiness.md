# L3 Critical-Control FINAL Readiness — Claim Gap Analysis (Session C / Final Security)

- **Milestone**: L3 CRITICAL CONTROL FINAL READINESS
- **Status**: **READY-TO-REHEARSE, NOT-READY-TO-CLAIM** (claim gap fully determined; **no live L3 run, no L3 claim, no invented signature**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope (write-only this session)**: `multi-agent-harness/docs/phase-5/l3/final/` · `multi-agent-harness/tests/l3_runner/critical/final/`
- **Companion**: `docs/phase-5/l3/0003-critical-control-readiness.md` · `0004-critical-control-rehearsal-session-b.md` · `docs/phase-5/l3/environment/0001-l3-environment-human-answerer-readiness.md` · `0002-session-a-preflight-verification-record.md` · `docs/security/0003` (P1–P4, IO-1..10, O1..O4) · `0005` (evidence infrastructure) · `0006` (implementation) · `0007` (run prerequisites) · `tests/l3_runner/` (runner, verifier, validator, rehearsal, claim_gate, environment probe) · `tests/l3_reference/` (oracles).
- **Question answered**: exactly what remains before a legitimate L3 claim, verified per check item against the CURRENT environment.

---

## 1. Critical control readiness matrix (per control × P1–P4)

Scope: the six critical controls (`docs/phase-5/l3/0003` §1), eight scenario bundles (`tests/l3_runner/critical/runner.py::CRITICAL_SCENARIOS`).

Legend: ✅ holds · ⛔ absent (blocks an L3 claim) · 🟡 machinery-only / rehearsal-level (not L3 evidence).

| # | Critical control | Bundle(s) | Gate (O1 oracle) | Expected | P1 live runtime | P2 IO-1 distinct PID | P2 IO-2 distinct UID | P3 ≥2 oracles | P4 reproducible replay | Verdict agreement | Rehearsal l3_claim |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **authority grant/revoke/expiry** | L3-AUTH-001 / 003 / 004 | `authority` | ALLOW/DENY/DENY | ⛔ | ✅ | ⛔ | ✅ O1+O3+O4 | ✅ | ✅ match | false |
| 2 | **execution-time recheck** | L3-AUTH-006 | `authority` | DENY | ⛔ | ✅ | ⛔ | ✅ O1+O3+O4 | ✅ | ✅ match | false |
| 3 | **protected-path execution** | L3-PATH-001 | `execution_gate` | DENY | ⛔ | ✅ | ⛔ | ✅ O1+O3+O4 | ✅ | ✅ match | false |
| 4 | **recovery privilege bounding** | L3-REC-004 | `recovery` | DENY | ⛔ | ✅ | ⛔ | ✅ O1+O3+O4 | ✅ | ✅ match | false |
| 5 | **stale-state protection** | L3-ST-003 | `state_transition` | DENY | ⛔ | ✅ | ⛔ | ✅ O1+O2+O4 | ✅ | ✅ match | false |
| 6 | **audit integrity** | L3-AUD-002 | `audit_integrity` | INVALID | ⛔ | ✅ | ⛔ | ✅ O1+O2+O4 | ✅ | ✅ match | false |

**Readiness per property (all 8 scenarios, observed this session):**

| Property | Status | Evidence |
|---|---|---|
| **P1 — Runtime (live)** | **⛔ NOT MET.** `LiveDSHRuntimeDriver` returns `BLOCKED` (`live-precondition:…` / `live-execution-not-authorized`), never a simulated PASS; `DSH_LIVE_BRIDGE_ACTIVE` is unset; runner refuses `--mode live`. Rehearsals use the replay `RecordedRuntimeDriver`. | `tests/l3_runner/critical/final/test_l3_final_readiness.py::TestP1LiveRuntimeNotMet` (96-test suite) |
| **P2 — Independent observer** | **🟡 MACHINERY ONLY.** IO-1 (distinct PID) ✅ via `subprocess` for all 8; IO-4 (not in orchestrator session tree) ✅; IO-2 (distinct UID) **⛔ FAILS HONESTLY** — orchestrator and verifier probe both `uid=1000` → `l3_claim_possible=False`, never faked. | `TestP2IndependentObserver` |
| **P3 — ≥2 independent oracle classes** | **✅ READY.** All 8 bundles declare ≥2 classes (O1 independent reference + O3 state hash or O2 schema-as-oracle + O4 Human-signed plan); runner R6 / validator LV8 enforce. | `TestP3IndependentOracles` |
| **P4 — Reproducible replay** | **✅ READY.** Deterministic fixture hash (stable across seeds 42/7 and equal to direct recompute); replay command recorded; verifier binary sha256 + schema sha256 pinned in `replay.json`. | `TestP4ReproducibleReplay` |

---

## 2. Check-list verdict (session brief items, verified this session)

| Check item | Status | Observed |
|---|---|---|
| **Separate PID** | ✅ PASS | IO-1 true for all 8 scenarios; verifier subprocess PID ≠ orchestrator PID (`verifier_pid=3` vs supplied `99999`); `verifier_session_id` starts `verifier-`. |
| **Separate UID** | ⛔ **FAIL (honest)** | `orchestrator_uid=1000`, `verifier_probe_uid=1000`, `same_uid=True` → IO-2 false → any L3 claim demoted (never upgraded). **This is the load-bearing L3 blocker.** |
| **Verifier independence** | ✅ PASS | `assert_clean_imports()` CLEAN (no `control.*` / `orchestrator.foundation.*` / `audit.helpers` / `state.helpers`); clean subprocess spawn; IO-1..IO-10 all recorded by the verifier process; LV21/LV22 reject same-process / orchestrator-written independence files. |
| **Human-signed pre-runtime plan** | 🟡 **MECHANISM READY / REAL SIGNOFF ABSENT** | `plan.json` schema-valid (id pattern, ts format, method enum, signoff < runtime); `L3ENV-PLAN-REAL` fails honestly — the committed plans are inert fixtures (`human-YYYY-MM-DD-NNN` template); **no real Human signoff observed, none invented.** |
| **Evidence bundle** | ✅ PASS | 13-file bundle complete under scratch for all 8 scenarios; manifest certifies; **never** the repo `audit/l3/` (which remains absent). |
| **Audit chain** | ✅ PASS | Independent `audit_chain` oracle: tampered `ledger.jsonl` → **INVALID** (chain length/hash mismatch); original `ledger.original.jsonl` → **VALID**. |
| **State hashes** | ✅ PASS | `before.sha256` / `after.sha256` recorded with `algorithm=sha256` and 64-hex root hash (IO-9) for all 8 bundles. |
| **Replay** | ✅ PASS | Deterministic `fixture_hash`; replay command in `replay.json`; `replay.sh` present; no live-network dependency. |
| **Verdict agreement** | ✅ PASS | `verdict-match.json` `match=true` for all 8 (runtime decision == reference decision). |
| **Claim gate** | ⛔ **l3_claim=false** | `evaluate_l3_claim()` on current facts fails on `P2-uid-separation` (same UID) and rehearsal mode forces false by construction; LV10 fails by design for rehearsal bundles. |

---

## 3. Exact blockers (nothing to add, nothing removed — verified this session)

The environment probe (`tests/l3_runner/environment/readiness.py`, run this session) reports `rehearsal_ready=True`, `l3_claim_possible=False`, and exactly five named blockers (all confirmed by the 96-test battery):

| # | Blocker | Exact missing dependency | Unblocks when |
|---|---|---|---|
| 1 | **L3ENV-UID-2** — separate UID (IO-2) | Verifier must run under a distinct UID/credential (setuid wrapper, separate user account, or separate host) | Operator/infrastructure provisions a separate-UID launch path |
| 2 | **L3ENV-ANS-1** — Human answerer (G3) | A live approval answerer composed for the session (approval prompts enabled) | Operator enables the answerer path |
| 3 | **L3ENV-ANS-2** — approval path | A live answerer for `ask` (or pre-recorded signed `approval-<id>` references) | Operator action |
| 4 | **L3ENV-D4D7-3** — live bridge (G2) | `DSH_LIVE_BRIDGE_ACTIVE=1` for the session (per-session mount verification) | Per-session mount + marker verification |
| 5 | **L3ENV-PLAN-REAL** — REAL Human signoff (O4) | An actual Human-signed `plan.json` with durable identity, committed before the run (no fixture id) | Real Human signoff via the answerer/interactive path |

Additional load-bearing conditions (not probe-blocking but required for any claim):

- **P1-live absent**: `LiveDSHRuntimeDriver` refuses live dispatch (`live-execution-not-authorized` / `live-precondition:*`); no live DSH session exists (`DSH_LIVE_BRIDGE_ACTIVE` unset).
- **Authorized run not granted**: Human acceptance of `docs/security/0003` §15 prerequisites is not recorded; no `audit/l3/` bundle exists (verified absent).
- **LV16 shape note — RESOLVED (Session F)**: `tests/l3_runner/validator.py::REQUIRED_REFERENCE_FIELDS` requires `checklist_item_results` in `reference-verdict.json`; the authority and execution-gate oracles already emitted it, and the **recovery, state_transition, and audit_integrity oracles now emit the canonical `checklist_item_results` field** (preserving the per-check diagnostic data that previously lived under `detail`). `L3-REC-004`, `L3-ST-003`, `L3-AUD-002` no longer record an LV16 error. The validator and its LV16 rule are unchanged; no requirement removed; no validation weakened (proved by `TestLv16ShapeNote`).

---

## 4. Exact evidence needed for a legitimate L3 claim

For each of the 8 critical scenarios, a claim requires a **committed `audit/l3/<scenario-id>/` bundle** that satisfies ALL of the following (nothing less):

1. **`l3_claim=true`** in `verdict-match.json` — the claim gate `evaluate_l3_claim()` must return true on the bundle's facts (P1 + P2 + P3 + P4 + signed plan + complete bundle + IO-all-pass + no unresolved UNKNOWN + verdict agreement).
2. **P1-live runtime verdict** — produced by a real DSH session (bridge marker set, live driver authorized), not a replay/recorded driver; `runtime-verdict.json` decision in {ALLOW, DENY, ERROR}.
3. **IO-2 distinct UID** — `verifier-independence.json` must record `verifier_uid ≠ orchestrator_uid` (both non-zero) from a genuinely separate credential (setuid / separate user / separate host).
4. **Real Human-signed plan** — `plan.json` signed by a durable Human identity via the answerer path, `human_signoff_ts` strictly before `runtime-verdict.json::captured_at` (LV7/IO-7), committed before the run (no `human-YYYY-MM-DD-NNN` fixture id).
5. **Approval path live** — the session's `ask` policy must have a live answerer (or signed `approval-<id>` references) so the run is authorized and the plan can be signed.
6. **Complete 13-file bundle + manifest** (E1..E13) committed under `audit/l3/<scenario-id>/` with `before.sha256`/`after.sha256`, `audit-log.jsonl` (+ chain sidecar), `reference-verdict.json`, `oracle-classes.json`, `provenance.json`, `replay.json`, `verifier-independence.json`, `verdict-match.json`.
7. **LV1..LV22 validation passing** — including LV16, which now passes for all 8 scenarios because every reference oracle emits the canonical `checklist_item_results` field (the recovery/state-transition/audit oracles were aligned at the oracle layer in Session F).
8. **Re-verification honesty gate** — the full suite re-run and the four INT bundles re-validated after any environment change; no claim on stale evidence.

---

## 5. Claim gate status

**NO L3 CLAIM. Zero controls are L3.**

- `l3_claim_possible=False` on this host (same-UID, no answerer, no bridge, no real signoff) — verified by the environment probe and the 96-test battery.
- All 8 critical scenarios are **rehearsal-only**: `l3_claim=false`, LV10 fails by design, IO-2 fails honestly.
- **The claim gate is code-enforced and honest**: `evaluate_l3_claim()` returns `l3_claim=false` on the current facts (P2-uid-separation failure), and a rehearsal forces false by construction. No bundle can be promoted without new evidence.

**What would move the claim gate:** a Human decision to (a) provision separate-UID verification, (b) enable the answerer + obtain real signoffs, (c) mount the live bridge and authorize a live run — then re-run under the claim gate and commit `audit/l3/` bundles with `l3_claim=true`. None of these hold in this session; none were attempted. (The LV16 shape note is no longer a claim blocker: resolved at the oracle layer in Session F.)

---

## 6. Honesty statement

1. **No L3 claim.** Zero controls claimed L3; `l3_claim_possible=False`.
2. **No live L3 run.** All execution paths are replay/inert (rehearsal); `LiveDSHRuntimeDriver` refuses live dispatch.
3. **No invented signature.** The committed plans are inert fixtures; `L3ENV-PLAN-REAL` fails honestly; the probe and tests never fabricate a signoff.
4. **No fake separation.** IO-2 fails honestly on the same-UID host; no bundle is promoted.
5. **No repo `audit/l3/` writes.** Verified absent.
6. **No production code, DSH core/profile/preset, session policy, validator, or existing test weakened.** The LV16 shape note is **resolved at the oracle layer** (Session F): the three reference oracles now emit the canonical `checklist_item_results` field, preserving their per-check diagnostic data. The validator, its LV16 rule, and the LV16 requirement are unchanged.
7. **No test failure downgraded.** All counts are as observed (below).

## 7. Tests (observed this session)

```text
$ .venv-tests/bin/python -m pytest tests/l3_runner/critical/final/ -q
96 passed

$ .venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
389 passed (293 pre-existing + 96 new final)
```

Full project regression: **1898 passed, 15 skipped** (exit 0; the +96 final-readiness tests included; no pre-existing test changed).

---

## 8. Scope check

**In scope (written this session):**
- `docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md` (this file) · `docs/phase-5/l3/final/README.md`
- `tests/l3_runner/critical/final/__init__.py` · `tests/l3_runner/critical/final/test_l3_final_readiness.py`

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/` (no `audit/l3/`), `config/`, `agents/`, `schemas/`, `docs/security/*`, `tests/l3_runner/validator.py` and all pre-existing `tests/l3_runner/` + `tests/l3_reference/` fixtures/schemas/runner/verifier/rehearsal — untouched, DSH core/profile/preset/session policy. **Session F later modified the three reference oracles (`recovery_gate.py`, `transition_gate.py`, `audit_chain.py`) to emit the canonical `checklist_item_results` field (LV16 resolution).** No live L3 executed. No L3 claim made. No signature invented.

---

*Status: READY-TO-REHEARSE, NOT-READY-TO-CLAIM. The exact claim gap is fully determined: P1-live absent, IO-2 same-UID fail (load-bearing), no answerer, no real Human signoff, no authorized run. The LV16 shape note was resolved at the oracle layer (Session F). Claim gate returns l3_claim=false on current facts. No control is L3. No live L3 run executed. No signature invented.*

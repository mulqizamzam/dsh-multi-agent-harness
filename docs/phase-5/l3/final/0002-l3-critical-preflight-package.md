# L3 Critical-Control FINAL Preflight Package

- **Milestone**: L3 CRITICAL CONTROL FINAL PREFLIGHT
- **Status**: **PREPARED-ONLY — REHEARSAL-READY, NOT-READY-TO-CLAIM**. Every live
  prerequisite is blocked on this host. The package validates the six critical
  controls (authority, execution-time recheck, protected path, recovery privilege
  bounding, stale state, audit integrity) against the current rehearsal-ready
  machinery. **No live L3 run, no L3 claim, no invented signature, no production
  code or DSH modified.**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Write scope**: `docs/phase-5/l3/final/0002-l3-critical-preflight-package.md`
  (this file) + `tests/l3_runner/critical/final/test_l3_critical_preflight.py`
- **Companion** (all read-only, verified this session):
  `docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md` (Session C
  final readiness matrix) · `docs/phase-5/l3/live-plans/` (six live-plan docs,
  8 plan.json templates) · `docs/phase-5/l3/0003-critical-control-readiness.md` ·
  `docs/phase-5/l3/0004-critical-control-rehearsal-session-b.md` ·
  `docs/phase-5/l3/environment/` (environment readiness probes) ·
  `docs/phase-5/final/preflight/0001-final-operator-checklist.md` (G13+L3
  combined preflight) · `tests/l3_runner/` (runner, verifier, validator,
  rehearsal, claim_gate, preflight, plan_signing, environment readiness) ·
  `tests/l3_reference/` (oracles, schemas, critical fixtures)

---

## 1. One-line status

```text
CRITICAL CONTROLS COVERED         : 6/6 (8 scenario bundles)
P1 live runtime                   : ⛔ NOT MET (live driver BLOCKED, bridge unset)
P2 IO-1 distinct PID              : ✅ PASS (all 8 scenarios)
P2 IO-2 distinct UID              : ⛔ FAIL honestly (same-UID host, uid=1000)
P3 ≥2 oracle classes              : ✅ PASS (O1+O3/O2+O4 per scenario)
P4 reproducible replay            : ✅ PASS (deterministic hash, replay pins)
Separate UID (IO-2)               : ⛔ FAIL (the load-bearing L3 blocker)
Human-signed plan mechanism       : 🟡 READY / real signoff ABSENT (fixture only)
Evidence bundle (13-file)         : ✅ PASS (complete under scratch, never repo)
Replay determinism                : ✅ PASS (fixture hash stable across seeds)
Verdict agreement                 : ✅ PASS (runtime == reference, all 8)
LV16 evidence-contract            : ✅ RESOLVED (oracles emit checklist_item_results)
Live tests executed this session  : NONE
L3 claims made                    : ZERO
```

---

## 2. Critical-control coverage matrix

The six critical controls are covered by 8 scenario bundles in the critical
scenario registry (`tests/l3_runner/critical/runner.py::CRITICAL_SCENARIOS`).
The complete scenario set is: `L3-AUTH-001`, `L3-AUTH-003`, `L3-AUTH-004`,
`L3-AUTH-006`, `L3-PATH-001`, `L3-REC-004`, `L3-ST-003`, `L3-AUD-002`.

| # | Critical control | Scenario(s) | Gate (O1 oracle) | Expected verdict | P1 | P2 IO-1 | P2 IO-2 | P3 | P4 | Verdict agreement |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **authority grant/revoke/expiry** | L3-AUTH-001 / 003 / 004 | `authority` | ALLOW/DENY/DENY | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |
| 2 | **execution-time recheck** | L3-AUTH-006 | `authority` | DENY | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |
| 3 | **protected-path execution** | L3-PATH-001 | `execution_gate` | DENY | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |
| 4 | **recovery privilege bounding** | L3-REC-004 | `recovery` | DENY | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |
| 5 | **stale-state protection** | L3-ST-003 | `state_transition` | DENY | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |
| 6 | **audit integrity** | L3-AUD-002 | `audit_integrity` | INVALID | ⛔ | ✅ | ⛔ | ✅ | ✅ | ✅ match |

**Observed this session:** all 8 scenarios rehearse green (oracle agreement,
replay determinism, complete 13-file bundles, `l3_claim=false`).

---

## 3. Preflight check results (observed this session)

### 3.1 P1 — Live runtime

| Check | Result | Detail |
|---|---|---|
| `LiveDSHRuntimeDriver` refuses live dispatch | ✅ PASS | Returns `BLOCKED` (`live-precondition:*` / `live-execution-not-authorized`), never a simulated PASS |
| `DSH_LIVE_BRIDGE_ACTIVE` marker | ⛔ NOT MET | Unset in environment |
| Rehearsal mode is replay-only | ✅ PASS | `mode=replay` for all 8 scenarios |

### 3.2 P2 — Independent observer

| Check | Result | Detail |
|---|---|---|
| IO-1 distinct PID | ✅ PASS | Verifier subprocess PID ≠ orchestrator PID (all 8 scenarios) |
| IO-2 distinct UID | ⛔ **FAIL HONESTLY** | `orchestrator_uid=1000`, `verifier_probe_uid=1000` → `same_uid=True` → `l3_claim_possible=False` |
| IO-4 not in session tree | ✅ PASS | Verifier session id starts `verifier-`, parent session is external |
| Verifier clean imports | ✅ PASS | `assert_clean_imports()` passes in a fresh subprocess; no `control.*` / `orchestrator.*` / `audit.helpers` / `state.helpers` |

### 3.3 P3 — Independent oracle classes

| Check | Result | Detail |
|---|---|---|
| ≥2 oracle classes per scenario | ✅ PASS | All 8 scenarios declare ≥2 (O1+O3+O4 or O1+O2+O4) |
| O1 oracles are reference modules | ✅ PASS | All gates map to `tests.l3_reference.*` modules |

### 3.4 P4 — Reproducible replay

| Check | Result | Detail |
|---|---|---|
| Fixture hash deterministic | ✅ PASS | Stable across seeds 42/7, matches direct recompute |
| Replay metadata pinned | ✅ PASS | `replay.json` records fixture hash, command line, verifier sha256, schema sha256 |

### 3.5 Human-signed plan

| Check | Result | Detail |
|---|---|---|
| Plan signoff precedes runtime | ✅ PASS | `human_signoff_ts < captured_at` (all 8 fixtures, LV7/IO-7) |
| Signoff fields schema-valid | ✅ PASS | Id pattern, timestamp format, method enum, full plan-schema validation |
| REAL Human signoff observed | ⛔ **ABSENT** | Committed plans are inert fixtures (`human-YYYY-MM-DD-NNN` template); `L3ENV-PLAN-REAL` fails honestly |

### 3.6 Evidence bundle

| Check | Result | Detail |
|---|---|---|
| 13-file bundle complete | ✅ PASS | All 12 `EVIDENCE_FILES` + `manifest.json` present under scratch (all 8 scenarios) |
| Under scratch, never `audit/l3/` | ✅ PASS | `audit/l3/` absent in repo; bundles under `tmp_path` |
| State hashes present | ✅ PASS | `before.sha256` / `after.sha256` with `algorithm=sha256` and 64-hex root hash |
| Audit chain integrity | ✅ PASS | Tampered `ledger.jsonl` → `INVALID`; original `ledger.original.jsonl` → `VALID` |

### 3.7 Replay

| Check | Result | Detail |
|---|---|---|
| Deterministic fixture hash | ✅ PASS | `sha256:` prefix, 71 chars, stable |
| Replay command recorded | ✅ PASS | `command_line` in `replay.json` |
| Verifier + schema sha256 pinned | ✅ PASS | 64-hex verifier sha256, schema sha256 map with ≥1 entry |

### 3.8 Verdict agreement

| Check | Result | Detail |
|---|---|---|
| Runtime == reference | ✅ PASS | `verdict-match.json` `match=true` for all 8 scenarios |

### 3.9 LV16 evidence-contract (Session F resolution)

| Check | Result | Detail |
|---|---|---|
| `reference-verdict.json` has `checklist_item_results` | ✅ PASS | All 5 oracles (authority, execution_gate, recovery, transition, audit_chain) emit the canonical field |
| L3-REC-004 / L3-ST-003 / L3-AUD-002 pass LV16 | ✅ PASS | No LV16 validation errors recorded for these three bundles |
| Validator unchanged | ✅ PASS | `validator.py::REQUIRED_REFERENCE_FIELDS` requires `checklist_item_results`; no requirement removed, no validation weakened |

---

## 4. Environment blockers (exact, observed this session)

The environment probe (`tests/l3_runner/environment/readiness.py`) reports
`rehearsal_ready=True`, `l3_claim_possible=False`, and exactly five named
blockers:

| # | Blocker | Missing dependency | Required for |
|---|---|---|---|
| 1 | **L3ENV-UID-2** | Separate UID (IO-2): verifier must run under a distinct UID/credential | L3 claim |
| 2 | **L3ENV-ANS-1** | Human answerer (G3): live approval answerer composed for the session | L3 claim + live run |
| 3 | **L3ENV-ANS-2** | Approval path: live answerer for `ask` (or signed `approval-<id>` references) | L3 claim + live run |
| 4 | **L3ENV-D4D7-3** | Live bridge: `DSH_LIVE_BRIDGE_ACTIVE=1` per-session mount verification | Live run |
| 5 | **L3ENV-PLAN-REAL** | Real Human signoff: durable identity, method, timestamp (not fixture template) | L3 claim |

All five blockers are confirmed by the 96-test final readiness battery and the
preflight lock tests (this package).

---

## 5. Claim gate status

**No L3 claim. Zero controls are L3.**

- `evaluate_l3_claim()` on current facts returns `l3_claim=false` (IO-2 same-UID
  failure, rehearsal mode forces false by construction).
- All 8 critical scenarios are rehearsal-only: `l3_claim=false`, LV10 fails by
  design, IO-2 fails honestly.
- **No bundle can be promoted without new evidence.** A Human must: provision
  separate-UID verification, enable the answerer + obtain real signoffs, mount
  the live bridge, authorize the live run — then re-run under the claim gate and
  commit `audit/l3/` bundles with `l3_claim=true`.

---

## 6. LV16 evidence-contract resolution

The LV16 shape note (reported in Session B and Session C) is **genuinely resolved
in the current state.** `tests/l3_reference/recovery_gate.py`,
`transition_gate.py`, and `audit_chain.py` all emit the canonical
`checklist_item_results` field in their `to_dict()` output. The authority and
execution_gate oracles already emitted it. `validator.py::REQUIRED_REFERENCE_FIELDS`
requires `checklist_item_results` on `reference-verdict.json`, and all 8 scenario
bundles pass LV1..LV22 validation including LV16.

**No evidence-contract issue remains.** No validator weakened, no requirement
removed, no oracle downgraded.

---

## 7. Prohibited actions (binding)

- Do **not** modify DSH, session policy, profiles/presets, or production controls.
- Do **not** claim L3; do **not** claim DSH-native immunity.
- Do **not** execute live L3 (this session).
- Do **not** invent signatures; do **not** fabricate runtime evidence.
- Do **not** enable `web_fetch`; do **not** perform destructive execution.
- Do **not** silently fall back when the live bridge is unavailable (fail-closed
  `BridgeNotAvailable` is correct behavior).

---

## 8. Honesty statement

1. **No L3 claim.** Zero controls claimed L3; `l3_claim_possible=False`.
2. **No live L3 run.** All execution paths are replay/inert (rehearsal);
   `LiveDSHRuntimeDriver` refuses live dispatch.
3. **No invented signature.** The committed plans are inert fixtures;
   `L3ENV-PLAN-REAL` fails honestly; the probe and tests never fabricate a
   signoff.
4. **No fake separation.** IO-2 fails honestly on the same-UID host; no bundle
   is promoted.
5. **No repo `audit/l3/` writes.** Verified absent.
6. **No production code, DSH core/profile/preset, session policy, validator, or
   existing test weakened.** The LV16 shape note is **resolved at the oracle
   layer** (Session F): the three reference oracles now emit the canonical
   `checklist_item_results` field. The validator, its LV16 rule, and the LV16
   requirement are unchanged.
7. **No test failure downgraded.** All counts are as observed (below).

---

## 9. Tests (observed this session)

```text
$ .venv-tests/bin/python -m pytest tests/l3_runner/critical/final/ -q
203 passed (96 final-readiness + 107 final-preflight lock tests)

$ .venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
545 passed
```

All tests pass. No pre-existing test changed. No failure downgraded.

---

## 10. Scope check

**In scope (written this session):**
- `docs/phase-5/l3/final/0002-l3-critical-preflight-package.md` (this file)
- `tests/l3_runner/critical/final/test_l3_critical_preflight.py`

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`,
`audit/` (no `audit/l3/`), `config/`, `agents/`, `schemas/`, `docs/security/*`,
`docs/phase-5/l3/0001`..`0004`, `docs/phase-5/l3/live-plans/`,
`docs/phase-5/l3/environment/`, `docs/phase-5/l3/final/0001` (Session C doc),
`docs/phase-5/final/`, `tests/l3_runner/` (all pre-existing),
`tests/l3_reference/` (oracles, schemas, critical fixtures, plan templates).
No live L3 executed. No L3 claim made. No signature invented.

---

*Status: PREPARED-ONLY. The six critical controls are REHEARSAL-READY and their
preflight state is fully validated: P1-live absent, IO-2 same-UID fail (the
load-bearing L3 blocker), no answerer, no real Human signoff, no authorized run.
The LV16 evidence-contract issue is RESOLVED. Claim gate returns `l3_claim=false`
on current facts. No control is L3. No live L3 run executed. No signature invented.*
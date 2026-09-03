# Phase 5 / Session B — LIVE-ASSURANCE RE-BASELINE REPORT (CURRENT STATE)

- **Milestone**: Phase 5 / Session B — CURRENT LIVE-ASSURANCE RE-BASELINE
- **Status**: **BLOCKED — same 3 L3-required blockers as the previous baseline; approval path corrected and O5 applied are VERIFIED as the only observed drift; no live G13 or L3 execution performed; no claim made**
- **Date**: 2026-09-01 (re-baseline run)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Write scope**: `docs/phase-5/final/rebaseline/` + `tests/phase-5/final/rebaseline/` (write-only). Everything else read-only.
- **Runtime context**: `workspace-write` file policy; `ask` approval policy; web GUI session active (`DSH_WEB_URL=http://127.0.0.1:13080`); `DSH_LIVE_BRIDGE_ACTIVE` unset; D4/D7 composition files persistent (7 presets + 7 instance rows), bridge inactive.
- **Previous baseline (compared)**: `docs/phase-5/final/live-assurance/0001-live-assurance-coordinator-report.md` (Session D, 2026-08-31) — 8 consolidated blockers (B1..B8).
- **Events between baselines (verified this session)**: (1) **approval-path correction** — obsolete answerer detection (`DSH_APPROVAL_PROMPTS_DISABLED` + `$DSH_HOME/profiles` scan) replaced by actual DSH bundle/web composition detection (`tests/environment/approval_composition.py`); `L3ENV-ANS-1/2` now PASS. (2) **O5 application** — `write`/`edit` removed from `somad`/`nova` toolFilter allow sets (mapping, instances, policies, live `cordis.patch.yml`); raw-write actor set shrunk `{zeko, cto, somad, nova}` → `{zeko, cto}`; G10 remains OPEN/BLOCKING.

---

## 0. Method

This re-baseline **re-ran the existing readiness machinery** against the current
session state. All probes are read-only; nothing was mounted, activated,
executed, or modified outside the write scope. No prerequisite was changed; no
bridge was activated; G13 and L3 were **not** executed; no signature or evidence
was invented.

| Probe | Command | Result (current) |
|---|---|---|
| L3 environment readiness | `python -m tests.l3_runner.environment.readiness --scenario L3-TEST-001 --orchestrator-uid 1000 --json` | `l3_claim_possible=False`, `rehearsal_ready=True`, **3 blockers** |
| G13 precondition | `tests.g13.live_readiness.plan.precondition()` | `satisfied=False` (marker unset, 7×NOT_MOUNTED, backend `unavailable`) |
| Approval readiness | `tests.environment.approval_composition.approval_readiness()` | `APPROVAL_INTERACTIVE_READY`, `e2e_status=UNKNOWN`, `composed=True` |
| Live runtime driver | `LiveDSHRuntimeDriver.execute()` | `BLOCKED` (`live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer`) |
| L3 claim gate | `evaluate_l3_claim()` on current facts | `l3_claim=False` (P1-runtime absent, P2-uid fail, bundle absent) |
| Backend kind | `probe_backend_kind()` | `unavailable` |
| Mount probes | `probe_all_instances_mounted()` | all 7 `False` |
| Approval test suite | `pytest tests/l3_runner/environment/approval/` | **32 passed** |
| L3 environment suite | `pytest tests/l3_runner/environment/` | **108 passed** |
| L3 critical final | `pytest tests/l3_runner/critical/final/` | **203 passed** |
| G13 + live_readiness | `pytest tests/g13/` + `tests/g13/live_readiness/` | **107 + 17 passed** |
| Config + G10 + live_dsh | `validate_config.py`, `pytest tests/g10/`, `pytest tests/live_dsh/` | **validate_config PASS; 201 + 75 passed** |
| D4/D7 composition | presets dir + `cordis.patch.yml` grep | 7 presets present; 7 `toolName: subagent_*` rows; somad/nova allow lists contain **no** `write`/`edit` (O5 applied) |

---

## 1. VERIFY — 15-item checklist (current, observed)

Legend: ✅ READY · 🟡 VERIFIED (mechanism/condition holds) · ❓ UNKNOWN (no
independent evidence) · ⛔ BLOCKED (exact missing dependency named).

| # | Item | Status | Observed (current session) |
|---|---|---|---|
| 1 | **approval policy** | ✅ **READY** | `ask` (effective policy from `DSH_PERMISSION_MODE` unset → `ask`); session runtime context confirms `ask` |
| 2 | **approval composition** | ✅ **READY** | `approval_readiness().composed=True` — DSH base bundle composes `@deepseek-ai/dsh-user-approval` + web-app composes `ui-user-questions` + `ui-conversation` |
| 3 | **approval E2E status** | ❓ **UNKNOWN** | `e2e_status="UNKNOWN"`, `probe_answered=False`, `approval_events=0` — no independently re-derivable `approval/asked`+`approval/decided` pair in the current session log; NEVER promoted to PASS from composition alone (brief requirement) |
| 4 | **separate PID** | ✅ **READY** | `L3ENV-UID-1` PASS — verifier spawned via `subprocess` (distinct PID, IO-1); `L3ENV-UID-3` PASS (never orchestrator session-tree tools, IO-4) |
| 5 | **separate UID** | ⛔ **BLOCKED** | `L3ENV-UID-2` FAIL — `orchestrator_uid=1000`, `verifier_probe_uid=1000`, `same_uid=True`; IO-2 fails honestly; requires setuid/separate-user/separate-host |
| 6 | **D4/D7 mount (files)** | ✅ **READY (files persistent)** | `L3ENV-D4D7-1` PASS (7 presets under `$DSH_HOME/.agent-presets/`); `L3ENV-D4D7-2` PASS (7 `subagent_<id>` rows in `cordis.patch.yml`); mapping==policy==instance post-O5 (validate_config + G10 suites green) |
| 7 | **DSH_LIVE_BRIDGE_ACTIVE** | ⛔ **BLOCKED** | `L3ENV-D4D7-3` FAIL — env var **unset**; live DSH unavailable (fail-closed `BridgeNotAvailable`); mount must be re-verified per session |
| 8 | **REAL backend** | ⛔ **BLOCKED** | `probe_backend_kind()=unavailable`; all 7 mount probes `False`; `RealDSHBackend.start()` would raise `BridgeNotAvailable` |
| 9 | **real Human-signed plans** | ⛔ **BLOCKED** | `L3ENV-PLAN-1..5` PASS (schema-valid fixture), `L3ENV-PLAN-REAL` **FAIL** — committed plans are inert fixtures (`human-YYYY-MM-DD-NNN` template); no real signoff observed; none invented |
| 10 | **evidence store** | ✅ **READY** | `L3ENV-STORE-1` PASS — `audit/l3/` creatable/writable; probe never creates it (`audit/l3/` absent) |
| 11 | **replay** | ✅ **READY** | `L3ENV-REP-1..4` PASS — deterministic fixture hash `sha256:52037567…`, `replay.sh` present, verifier/schema sha256 pinned, no live-network dependency |
| 12 | **authorized live-run condition** | ⛔ **BLOCKED** | `LiveDSHRuntimeDriver.execute()` → `BLOCKED` (`live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer`); no Human acceptance of `docs/security/0003` §15 recorded; no `audit/l3/` bundle |
| 13 | **G10 current status** | ⛔ **OPEN / BLOCKING** | G10 remains OPEN for production; O5 applied as containment only (actor set `{zeko, cto}`); no prevention closure claimed (`docs/phase-5/final/0001` §9 addendum; `docs/phase-5/security/g10/implementation/0002`) |
| 14 | **G13 current status** | ❓ **UNKNOWN (DSH-native) / BLOCKED (live step)** | Control-plane resistance VERIFIED (deterministic, 107 g13 tests green); DSH-native layer UNKNOWN — real child not observable this session; live step BLOCKED by precondition; no immunity claim (`docs/phase-5/security/g13/final/0001`) |
| 15 | **L3 claim gate** | ⛔ **BLOCKED (no claim)** | `evaluate_l3_claim()` → `l3_claim=False` on current facts (P1-runtime absent, P2-uid-separation fail, evidence bundle absent); rehearsal forces `false` by design; zero controls L3 |

---

## 2. EXACT CURRENT BLOCKER SET (8 items)

| # | Blocker | Affects | Check / source |
|---|---|---|---|
| B1 | `DSH_LIVE_BRIDGE_ACTIVE` unset — live bridge inactive | G13, L3 (P1) | `L3ENV-D4D7-3` FAIL (observed this session) |
| B2 | Same-UID host (`orchestrator=1000`, `verifier=1000`) — IO-2 fails | L3 (any claim) | `L3ENV-UID-2` FAIL (observed this session) |
| B3 | No real Human-signed plan — fixtures only | L3 (O4), G13 | `L3ENV-PLAN-REAL` FAIL (observed this session) |
| B4 | No authorized live-run condition — §15 not accepted | G13, L3 (live execution) | `LiveDSHRuntimeDriver.execute()` → `BLOCKED`; no §15 acceptance record |
| B5 | D4/D7 mount not active — no REAL DSH backend | G13 (precondition), L3 (P1) | `precondition()["satisfied"]=False`; `probe_backend_kind()=unavailable`; 7×NOT_MOUNTED |
| B6 | `LiveDSHRuntimeDriver` refuses live dispatch | L3 (P1) | `execute()` returns `BLOCKED` (never a simulated PASS) |
| B7 | G10 — DSH-layer path isolation residual (OPEN, post-O5) | Project security | `docs/phase-5/final/0001` §1 G10 row + §9 addendum; raw-write actor set `{zeko, cto}` |
| B8 | G13 — prompt-injection at DSH layer UNKNOWN | Project security | `docs/phase-5/security/g13/final/0001`; live precondition unmet |

**Derived state:** `rehearsal_ready=True` · `l3_claim_possible=False` ·
`all_required_pass=True` · `all_l3_required_pass=False`. Zero controls are L3.
No G13 DSH-native claim. No live G13/L3 executed.

---

## 3. DRIFT vs PREVIOUS BASELINE (only observed drift)

**Previous baseline (Session D coordinator report) exact blockers:** B1 (bridge
marker unset), B2 (same-UID), B3 (no real signoff), B4 (no authorized run), B5
(mount inactive / no REAL backend), B6 (live driver refuses), B7 (G10 OPEN), B8
(G13 UNKNOWN).

**Current exact blockers: identical set B1..B8. No blocker added, removed, or
reclassified.**

### Observed drift (only two; both are positive/verification-level, neither changes the blocker set)

| # | Drift | Direction | Evidence |
|---|---|---|---|
| D1 | **Approval-path readiness no longer under-reported.** Previous baseline row 8 recorded `L3ENV-ANS-1/2` PASS by the corrected detector (E2E UNKNOWN). Re-baseline re-verifies: `L3ENV-ANS-1` PASS, `L3ENV-ANS-2` PASS, `approval_readiness().status=APPROVAL_INTERACTIVE_READY`, `e2e_status=UNKNOWN` (unchanged — no independently re-derivable pair in the current session log). The obsolete `DSH_APPROVAL_PROMPTS_DISABLED`/profile-scan heuristic is confirmed absent from the wired probe. | ✅ No regression — correction holds; E2E stays honestly UNKNOWN (never promoted) | `approval_readiness()` live run; `L3ENV-ANS-1/2` PASS in current readiness probe |
| D2 | **O5 containment applied and verified.** Raw-write actor set shrunk `{zeko, cto, somad, nova}` → `{zeko, cto}`; `write`/`edit` removed from `somad`/`nova` allow sets in mapping, instance config, policies, and live `cordis.patch.yml`. G10 status unchanged (OPEN/BLOCKING; containment only). | ✅ Containment improvement; no closure claimed | live `cordis.patch.yml` somad/nova rows (no `write`/`edit` in allow); `config/role-preset-mapping.yaml` somad/nova blocks; validate_config + G10 suites green (201 passed) |

### No other drift observed

- All 23 L3ENV checks re-run with the same pass/fail pattern as the previous
  baseline (identical `rehearsal_ready=True`, `l3_claim_possible=False`, same 3
  L3-required blockers).
- G13 precondition, backend kind, mount probes, evidence store, replay, claim
  gate, and live-driver behavior all match the previous baseline exactly.
- No test suite regressed: approval 32, L3 environment 108, L3 critical final
  203, g13 107, live_readiness 17, g10 201, live_dsh 75 — all observed green
  this session.

---

## 4. READY / VERIFIED / UNKNOWN / BLOCKED summary

| Status | Count | Items |
|---|---|---|
| **READY** | 6 | approval policy (1), approval composition (2), separate PID (4), D4/D7 files persistent (6), evidence store (10), replay (11) |
| **VERIFIED** | 2 | approval-path correction holds (D1 — mechanism verified live), O5 containment applied (D2 — actor set verified at mapping + live patch) |
| **UNKNOWN** | 2 | approval E2E status (3 — not independently re-derivable, never promoted), G13 DSH-native (14 — real child not observable) |
| **BLOCKED** | 5 | separate UID (5), `DSH_LIVE_BRIDGE_ACTIVE` (7), REAL backend (8), real Human-signed plans (9), authorized live-run (12) — plus G10 OPEN (13) and L3 claim gate (15) remain blocking at the claim level |

---

## 5. Honesty statement

1. **No live G13 execution.** Precondition (`real_dsh_child_observable`) is
   `False`; the prepared live package remains unexecuted.
2. **No live L3 execution.** `LiveDSHRuntimeDriver` returns `BLOCKED`; no
   `audit/l3/` bundle created; zero controls L3.
3. **No L3 claim.** `evaluate_l3_claim()` returns `false` on current facts.
4. **No DSH-native immunity claimed.** G13 remains UNKNOWN at the DSH-native
   layer.
5. **No signature invented.** All committed plans are inert fixtures;
   `L3ENV-PLAN-REAL` fails honestly.
6. **No UID separation fabricated.** IO-2 fails honestly (uid=1000).
7. **No bridge activated, no prerequisite changed.** The re-baseline is
   detection-only; `DSH_LIVE_BRIDGE_ACTIVE` remains unset.
8. **No DSH, session policy, profile/preset, production code, control plane, or
   role configuration modified.** Write scope was limited to
   `docs/phase-5/final/rebaseline/` + `tests/phase-5/final/rebaseline/`.
9. **No UNKNOWN promoted to PASS.** E2E stays UNKNOWN; G13 stays UNKNOWN.
10. **All evidence above is from read-only probes and committed documents in
    this session; nothing is assumed.**

---

## 6. Scope check

**In scope (written this session):**
- `docs/phase-5/final/rebaseline/0001-live-assurance-rebaseline-report.md` (this file)
- `tests/phase-5/final/rebaseline/test_live_assurance_rebaseline.py`

**Not modified (verified):** DSH core/profile/preset/session policy; `$DSH_HOME`;
`control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `config/`, `schemas/`;
all existing `docs/` and `tests/` outside write scope; no `audit/l3/` created; no
live dispatch; no L3 claim; no signature invented; no evidence fabricated;
`DSH_LIVE_BRIDGE_ACTIVE` not set.

---

*Status: RE-BASELINE REPORT (Session B). Blocker set unchanged from previous
baseline: B1..B8 (bridge marker unset, same-UID, no real signoff, no authorized
run, mount inactive, live driver refuses, G10 OPEN, G13 UNKNOWN). Observed drift
only: approval-path correction holds (L3ENV-ANS-1/2 PASS, E2E UNKNOWN) and O5
containment applied (actor set `{zeko, cto}`). rehearsal_ready=True,
l3_claim_possible=False. No live G13/L3 executed. No claim made. No prerequisite
changed. No bridge activated. No signature/evidence invented.*

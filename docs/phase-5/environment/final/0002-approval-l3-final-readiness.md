# Phase 5 / Session B — Approval + L3 Environment FINAL Readiness

- **Milestone**: Phase 5 / Session B — APPROVAL + L3 ENVIRONMENT FINAL READINESS
- **Status**: FINAL READINESS REPORT (read-only verification; **no session-policy change, no DSH/profile/preset change, no invented approval/signatures, no G13/L3 execution**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Write-only scope**: `docs/phase-5/environment/final/` + `tests/l3_runner/environment/final/`. Everything else read-only; no session policy, DSH, profile/preset, or production config changed.
- **Supersedes**: `docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md` (Session D — superseded for the 13-item approval+L3 check). The Session D checklist remains the authoritative rehearsal infrastructure checklist; this document is the **final approval+L3 readiness gate**.
- **Companion**: `docs/phase-5/environment/approval/0001-approval-path-readiness.md` (Session B) · `0002-approval-path-correction.md` (E2E verification) · `docs/phase-5/environment/live-bridge/0001-d4d7-live-bridge-readiness.md` (Session A) · `docs/phase-5/l3/environment/0001-l3-environment-readiness.md` · `docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md` · `docs/phase-5/l3/final/0002-l3-critical-preflight-package.md` · `tests/l3_runner/environment/readiness.py` · `tests/environment/approval_composition.py` · `tests/l3_runner/environment/final/` (this session's tests).

---

## 1. One-line status

```text
rehearsal_ready              = True      (machinery can rehearse/replay)
l3_claim_possible            = False     (3 L3-required prerequisites absent)
approval_composed            = YES       (DSH bundle/web answerer surface composed)
approval_interactive_ready   = YES       (web session attached, HTTP 200)
approval_e2e_verified        = UNKNOWN   (previously observed Human answer NOT
                                          independently re-derivable from the
                                          current session log -> UNKNOWN, never PASS)
readiness_probe_under_reports = NO       (targeted repair wired the corrected
                                          detector; L3ENV-ANS-1/2 now PASS)
```

---

## 2. The 13 checks — CURRENT STATE and READY / BLOCKED per prerequisite

### 2.1 Effective approval policy = ask

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY** |
| **Current state** | DSH base bundle composes `- id: approval` with `@deepseek-ai/dsh-user-approval` and policy derivation: `(DSH_PERMISSION_MODE ?? 'workspace-write') === 'danger-full-access' ? 'never' : 'ask'`. `DSH_PERMISSION_MODE` is unset, so effective policy is `ask`. Verified: `approval/policy` session event = `{"policy":"ask"}`. |
| **Exact evidence** | DSH base bundle `cordis.patch.yml:188–191`; `env` (no `DSH_PERMISSION_MODE`); runtime-context snapshot. |
| **Operator action** | None (policy is correct). Do NOT set `DSH_PERMISSION_MODE=danger-full-access` (that flips to `never` and removes the fail-closed backstop). |

### 2.2 Actual approval service composition

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY** |
| **Current state** | DSH base bundle `packages/bundle/base/cordis.patch.yml` composes row `- id: approval` with `@deepseek-ai/dsh-user-approval`. The service dispatches the `approval/request` waterfall to composed answerers. |
| **Exact evidence** | `grep -c "@deepseek-ai/dsh-user-approval" .../base/cordis.patch.yml` → 1; `grep -c "id: approval" .../base/cordis.patch.yml` → 1. |
| **Operator action** | None (service is composed). |

### 2.3 Web GUI Human answerer surface

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY (by composition)** |
| **Current state** | The web-app bundle `packages/bundle/web-app/cordis.patch.yml` composes `ui-user-questions` (`@deepseek-ai/dsh-client-ui-user-questions`, line 291) and `ui-conversation` (`@deepseek-ai/dsh-client-ui-conversation`, line 209) — the browser-based answerer surface. The session is a web GUI: `DSH_WEB_URL=http://127.0.0.1:13080`, web server responds HTTP 200. |
| **Exact evidence** | `grep -c "ui-user-questions" .../web-app/cordis.patch.yml` → 2; `grep -c "ui-conversation" .../web-app/cordis.patch.yml` → 2; `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:13080` → 200. |
| **Operator action** | Verify the browser is connected to the session (the web app is open on `http://127.0.0.1:13080`). No policy/config edit required. |

### 2.4 approval/request → Human decision → approval/decided

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **MECHANISM READY; E2E STATUS UNKNOWN (honestly reported)** |
| **Current state** | **Composition-ready:** The DSH `user-approval` service dispatches `approval/request` via waterfall to composed answerers. In a web session the browser's `ApprovalPanel` renders the question and captures the Human decision. The audit pair `approval/asked` + `approval/decided` is appended (log-only). Outcome vocabulary: `allowed-once | rejected | cancelled | unavailable`. **Detector repaired:** the corrected programmatic detector `tests/environment/approval_composition.py` returns a valid typed result (no TypeError; status defaults to `APPROVAL_HEADLESS_UNAVAILABLE`). **E2E = UNKNOWN:** the previously observed Human answer (recorded in `0002-approval-path-correction.md` and the prior marker) cannot be independently re-derived from the current session log (no matching `approval/asked` + `approval/decided` pair), so `e2e_status` is honestly reported as **UNKNOWN** — never promoted to PASS from composition or a stale marker alone. |
| **Exact evidence** | DSH checkout `user-approval/README.md` (waterfall, audit pair, outcome vocabulary); `docs/phase-5/environment/approval/0002-approval-path-correction.md` §4 (historical E2E evidence); current detector run: `approval_readiness().status == APPROVAL_INTERACTIVE_READY`, `e2e_status == "UNKNOWN"`, `probe_answered == False`. |
| **Operator action** | If a fresh E2E confirmation is required, run one harmless approval-required probe (`ask_user_question`, no consequential action) with the Human at the web GUI and observe the `approval/asked` + `approval/decided` pair in the session log; the detector then re-derives E2E = PASS. Until then, report E2E = UNKNOWN (per the brief: UNKNOWN, not PASS). |

### 2.5 Separate PID

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY** |
| **Current state** | The L3 verifier runner spawns via `subprocess` (distinct PID, IO-1). The orchestrator PID is 2 (within the harness session). A subprocess spawn produces a distinct PID. |
| **Exact evidence** | `L3ENV-UID-1` PASS; `L3ENV-UID-3` PASS. Runner code uses `subprocess.run`, never `subagent`/`subagent_fork`/`send_message`. |
| **Operator action** | None (mechanism present). |

### 2.6 Separate UID

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **BLOCKED** |
| **Current state** | Same-UID host: `orchestrator_uid=1000`, verifier subprocess probe returns `1000` → `same_uid=True` → IO-2 fails. Requires a setuid wrapper, separate user account, or separate host. |
| **Exact evidence** | `L3ENV-UID-2` FAIL; `id -u` → 1000. |
| **Operator action** | Provision a separate-UID launch path (`L3ENV-UID-2`). |

### 2.7 D4/D7 live mount

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **FILES READY; BRIDGE BLOCKED** |
| **Current state** | 7 role presets present under `$DSH_HOME/.agent-presets/` (`role-zeko`…`role-nova`). 7 `tool-subagent-<id>` rows in `$DSH_HOME/profiles/web/cordis.patch.yml`. `mapping==policy==instance` valid (post-O5). But the live bridge marker is **unset**, so the bridge is **inactive**. |
| **Exact evidence** | `L3ENV-D4D7-1` PASS; `L3ENV-D4D7-2` PASS; `ls -d $DSH_HOME/.agent-presets/role-*` → 7 dirs; `grep -c 'toolName: subagent_' cordis.patch.yml` → 7. |
| **Operator action** | Run per-session mount-verification procedure (`docs/phase-5/environment/0001` §2): verify presets → verify rows → set `DSH_LIVE_BRIDGE_ACTIVE=1` → verify backend → probe → smoke. |

### 2.8 DSH_LIVE_BRIDGE_ACTIVE

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **BLOCKED** |
| **Current state** | **UNSET** (empty). |
| **Exact evidence** | `echo ${DSH_LIVE_BRIDGE_ACTIVE:-unset}` → `unset`; `L3ENV-D4D7-3` FAIL. |
| **Operator action** | Set `DSH_LIVE_BRIDGE_ACTIVE=1` **only after** mount-verification passes (fail-closed: marker without verified mount = stale mount → escalate). |

### 2.9 REAL backend availability

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **BLOCKED** |
| **Current state** | `probe_backend_kind()` returns `UNAVAILABLE` (marker unset). `RealDSHBackend.start()` raises `BridgeNotAvailable` (fail-closed; no silent fallback to FAKE — G1-3). |
| **Exact evidence** | `L3ENV-D4D7-3` FAIL; `tests/live_dsh/discovery.probe_backend_kind()` → `UNAVAILABLE`. |
| **Operator action** | Set `DSH_LIVE_BRIDGE_ACTIVE=1` after verified mount. |

### 2.10 Real Human-signed plan

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **BLOCKED** |
| **Current state** | Plan-schema validation passes on fixture plans (`L3ENV-PLAN-1..5` PASS). But the committed plans are inert fixtures (`human_signoff_id=human-YYYY-MM-DD-NNN` template, method `interactive`, no durable identity). **No real Human signoff has been observed** — `L3ENV-PLAN-REAL` FAIL. |
| **Exact evidence** | `L3ENV-PLAN-1..5` PASS; `L3ENV-PLAN-REAL` FAIL; fixture `plan.json` fields. |
| **Operator action** | A Human with a durable identity must sign each scenario `plan.json` (identity + method + timestamp) via the interactive/signed-assertion path **before** the run, with `human_signoff_provenance=recorded`. |

### 2.11 Evidence store

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY** |
| **Current state** | `audit/l3/` is creatable/writable under the project root. The probe never creates it. `L3ENV-STORE-1` PASS. |
| **Exact evidence** | `L3ENV-STORE-1` PASS; `os.access(PROJECT_ROOT, os.W_OK)` → True; `audit/l3/` does not exist (not yet created). |
| **Operator action** | None required to make it writable; create `audit/l3/<scenario-id>/` only when an authorized L3 run begins. |

### 2.12 Replay

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **READY** |
| **Current state** | `replay.sh` present; deterministic fixture hash (`sha256:52037567…`); verifier binary sha256 + schema sha256 recorded; no live-network dependency. `L3ENV-REP-1..4` PASS. |
| **Exact evidence** | `L3ENV-REP-1..4` PASS; `tests/l3_runner/replay.sh`; `replay.json` (E11). |
| **Operator action** | None (tooling present). Keep fixtures recorded; never introduce live-network scenarios. |

### 2.13 Authorized live-run condition

| Attribute | Value |
|---|---|
| **READY / BLOCKED** | **BLOCKED** |
| **Current state** | No Human acceptance of `docs/security/0003` §15 is recorded. `LiveDSHRuntimeDriver` is a stub that returns `BLOCKED` (`live-execution-not-authorized`). No re-baseline record; B1 (production control-plane code) not wired for a live L3 run. |
| **Exact evidence** | `tests/l3_runner/runtime_driver.py` (lines 7, 108, 112, 169, 180 — `BLOCKED`/`refuse`/`NotImplementedError`); `audit/l3/` absent; no `docs/security/0003` §15 acceptance record. |
| **Operator action** | A Human must accept §15 (L3 execution protocol), confirm the G9 baseline (`workspace-write + ask`), and close B1 before any live L3 run is authorized. |

---

## 3. E2E approval status

The four-level status model from the approval correction (`docs/phase-5/environment/approval/0002-approval-path-correction.md`):

| Status | Holds? | Detail |
|---|---|---|
| **APPROVAL_COMPOSED** | **YES** | DSH base bundle composes approval service (`@deepseek-ai/dsh-user-approval`, policy `ask`). Web-app bundle composes answerer surface (`ui-user-questions` + `ui-conversation`). |
| **APPROVAL_INTERACTIVE_READY** | **YES** | `APPROVAL_COMPOSED` holds AND the current session is a web GUI session (`DSH_WEB_URL=http://127.0.0.1:13080`, HTTP 200). A live Human answerer surface is attached by composition. |
| **APPROVAL_E2E_VERIFIED** | **UNKNOWN** | The previously observed Human answer (recorded in `0002-approval-path-correction.md` §4) cannot be **independently re-derived** from the current session log: no matching `approval/asked` + `approval/decided` pair is present, so `e2e_status="UNKNOWN"` and `probe_answered=False`. The corrected detector reports this honestly; it is NEVER promoted to PASS from composition or a stale marker alone (brief requirement). |
| **APPROVAL_HEADLESS_UNAVAILABLE** | **N/A** | Not applicable — this is a web GUI session with a composed answerer. |

**Key distinction:** APPROVAL_INTERACTIVE_READY is **composition-ready** (the answerer surface is present in the DSH bundle and the web session is attached). APPROVAL_E2E_VERIFIED adds a **real Human answer** to a harmless probe, and is reported only when independently re-derived (UNKNOWN here, not PASS). The L3 claim path additionally requires a **real Human-signed plan** (item 2.10), which is a separate requirement.

---

## 4. L3 claim possible

**`l3_claim_possible = False`** on this host. The three load-bearing L3 blockers (after the targeted probe repair; `L3ENV-ANS-1/2` are no longer blockers — they now PASS in the web GUI session):

| # | Blocker | Check | Missing dependency |
|---|---|---|---|
| 1 | Separate UID (IO-2) | `L3ENV-UID-2` | Same-UID host (`uid=1000`). Requires setuid/separate-user/separate-host. |
| 2 | Live bridge (G2) | `L3ENV-D4D7-3` | `DSH_LIVE_BRIDGE_ACTIVE` unset. |
| 3 | Real Human signoff (O4/G7) | `L3ENV-PLAN-REAL` | No real signoff observed (fixture only). |

Additional load-bearing conditions (not probe-blocking but required for any claim):
- **P1-live absent**: `LiveDSHRuntimeDriver` refuses live dispatch.
- **Authorized run not granted**: no Human acceptance of §15.
- **G10/G13 OPEN/BLOCKING**: project security gates not closed.

---

## 5. Readiness probe under-report: repaired (no longer under-reports)

**HISTORICAL (now fixed):** the readiness probe (`tests/l3_runner/environment/readiness.py::_answerer_available`) previously under-reported Web GUI approval readiness:

1. **Obsolete detection key:** `_answerer_available` checked `DSH_APPROVAL_PROMPTS_DISABLED` (defaults to `1` when unset). This is a **project-side convention that DSH never reads** (verified by negative grep over the entire DSH checkout). The DSH layer does not use this variable — the probe must NOT use it.
2. **Wrong answerer location:** The backup `_profile_has_answerer()` scanned `$DSH_HOME/profiles/*` for answerer marker rows. The composed answerer surface lives in the **DSH packages** (`packages/bundle/web-app/cordis.patch.yml` rows `ui-user-questions` + `ui-conversation`), not in `$DSH_HOME/profiles/`. A profile scan cannot see the bundle-composed answerer.

**Repair applied (targeted approval-probe repair, write-scope only):**
1. `tests/environment/approval_composition.py` now exposes `detect_approval_status()` (alias of `approval_readiness()`) returning a valid typed `ApprovalReadiness` (status defaults to `APPROVAL_HEADLESS_UNAVAILABLE`; no TypeError). `e2e_status` is a tri-state (`PASS`/`UNKNOWN`/`UNAVAILABLE`) with `probe_answered` — E2E is reported **UNKNOWN** unless independently re-derived from the current session log.
2. `tests/l3_runner/environment/readiness.py::_answerer_available` now uses the corrected detector (actual DSH bundle/web composition), never `DSH_APPROVAL_PROMPTS_DISABLED` and never the `$DSH_HOME/profiles` scan.

**Result (verified live):** `L3ENV-ANS-1` and `L3ENV-ANS-2` now report `pass=True` in the web GUI session (answerer available by composition — not a false positive; the DSH bundle composes the surface and the browser is attached). The L3 verdict is unchanged (`l3_claim_possible=False`) but is now blocked by the three genuine independent blockers, not by a probe false negative.

---

## 6. EXACT REMAINING BLOCKERS

| # | Blocker | Check ID | Class | Unblocks when |
|---|---|---|---|---|
| 1 | **Separate UID** | `L3ENV-UID-2` | L3 | Operator provisions setuid/separate-user/separate-host |
| 2 | **Live bridge marker** | `L3ENV-D4D7-3` | G2 | Operator sets `DSH_LIVE_BRIDGE_ACTIVE=1` after verified mount |
| 3 | **Real Human signoff** | `L3ENV-PLAN-REAL` | O4/G7 | Human signs a real plan via the answerer/interactive path |
| 4 | **Authorized live-run** | — | §15 | Human accepts §15, closes B1 |
| 5 | **P1 live runtime** | — | P1 | Live bridge active + authorized run |

**No longer blockers (probe repaired):** `L3ENV-ANS-1` (Human answerer) and `L3ENV-ANS-2` (approval path) now PASS in the web GUI session — the answerer is composition-ready and the corrected detector is wired into the readiness probe. The detector TypeError is fixed (no `ApprovalDetection` bug remains).

---

## 7. OPERATOR ACTIONS

| # | Action | Required for | Priority |
|---|---|---|---|
| 1 | Provision separate-UID launch path (setuid/separate-user/separate-host) | L3 claim | Critical |
| 2 | Run per-session mount-verification + set `DSH_LIVE_BRIDGE_ACTIVE=1` | Live DSH dispatch | Critical |
| 3 | Have a Human sign each scenario `plan.json` via the answerer/interactive path | Real signoff | Critical |
| 4 | Human accepts `docs/security/0003` §15, confirms G9 baseline, closes B1 | Authorized live run | Critical |
| 5 | Verify the browser is connected to the web GUI session | Approval path live | Required |
| 6 | (Optional) Run one harmless approval-required probe to re-derive E2E = PASS if a fresh Human answer is needed | E2E confirmation | Optional |

---

## 8. VERIFIED / UNKNOWN / BLOCKED

| Status | Count | Items |
|---|---|---|
| **VERIFIED** | 9 | Approval policy = ask, Approval service composed, Web GUI answerer surface composed, L3ENV-ANS-1 (answerer available), L3ENV-ANS-2 (approval path available), Separate PID, Evidence store, Replay tooling, D4/D7 files persistent |
| **UNKNOWN** | 1 | E2E approval status (previously observed Human answer not independently re-derivable from the current session log -> UNKNOWN, never PASS) |
| **BLOCKED** | 3 | Separate UID, Live bridge marker, Real Human signoff (plus non-probe §15/P1 conditions for any claim) |

---

## 9. Honesty statement

1. **No session-policy change, no DSH/profile/preset change, no production-config edit.** The write-only targets are `docs/phase-5/environment/final/`, `docs/phase-5/environment/approval/`, `tests/environment/approval_composition.py`, `tests/environment/preflight.py`, `tests/l3_runner/environment/`, and `tests/l3_runner/environment/approval/` (the targeted approval-probe repair).
2. **No invented approval, signatures, or Human answerer.** E2E is reported as **UNKNOWN** because the previously observed Human answer cannot be independently re-derived from the current session log — it is never promoted to PASS from composition or a stale marker alone.
3. **No G13/L3 execution.** No live DSH dispatch, no L3 claim, no simulated runtime evidence.
4. **Composition-ready is distinguished from E2E-verified.** `APPROVAL_INTERACTIVE_READY` (composition-ready) ≠ `APPROVAL_E2E_VERIFIED` (independently re-derived Human answer). Both are distinct from an L3 claim.
5. **The probe repair is applied and verified, not assumed.** The corrected detector is wired into `readiness.py::_answerer_available`; `L3ENV-ANS-1/2` now PASS in the web GUI session (verified live, not a false positive).
6. **Pre-existing test failures are resolved by the repair** — the TypeError in `approval_composition.py` is fixed and the test interface (`detect_approval_status`, `probe_answered`, `e2e_status`) is restored; `tests/environment/` and `tests/l3_runner/environment/approval/` now pass.
7. **All evidence above is from the DSH 0.1.1-rc.2 checkout (read-only), the live session log, or the project config; nothing is assumed.**

---

## 10. Scope check

**In scope (written this session, targeted approval-probe repair):** `tests/environment/approval_composition.py` · `tests/environment/preflight.py` · `tests/l3_runner/environment/approval/` · `tests/l3_runner/environment/` · `docs/phase-5/environment/approval/` · `docs/phase-5/environment/final/` (including the final tests in `tests/l3_runner/environment/final/`).

**NOT modified (verified):** session policy, DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, `$DSH_HOME`, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, and all other `docs/` + `tests/` outside the write-only list. No DSH modification, no session-policy change, no approval/signature invented, no G13/L3 executed, no L3 claim made.

---

*Status: FINAL READINESS REPORT (Session B, targeted approval-probe repair). rehearsal_ready=True, l3_claim_possible=False, approval_composition=YES, approval_e2e_verified=UNKNOWN (not independently re-derivable, never PASS), readiness_probe_under_reports=NO (repaired: L3ENV-ANS-1/2 PASS). 9 VERIFIED, 1 UNKNOWN, 3 BLOCKED. No session-policy change, no DSH/profile/preset change, no invented approval, no G13/L3 execution.*
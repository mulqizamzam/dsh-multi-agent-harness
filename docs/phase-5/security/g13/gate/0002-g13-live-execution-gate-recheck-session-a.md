# G13 — Live Execution Gate RECHECK (Session A / Execution Flow)

- **Gate**: G13 LIVE EXECUTION GATE RECHECK
- **Session**: Phase 5 / Execution Flow / Session A
- **Date**: 2026-09-01
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Recheck only — no G13 execution, no payload re-creation, no DSH
  modification, no session-policy/profile/preset modification, no invented
  Human approval, no invented live evidence.
- **Baseline compared**: `docs/phase-5/final/rebaseline/0001-live-assurance-rebaseline-report.md`
  (Session B, blocker set B1..B8) and prior gate
  `docs/phase-5/security/g13/gate/0001-g13-live-execution-gate.md`.
- **Method**: All dynamic state re-probed this session as fresh evidence; no
  old blocker status reused without re-inspection.

---

## G13_LIVE_READY = **NO**

Live G13 execution cannot legally/procedurally start in the current session.

---

## 11-Axis Recheck (fresh evidence, this session)

| # | Axis | Current (probed this session) | Status |
|---|------|-------------------------------|--------|
| 1 | **DSH_LIVE_BRIDGE_ACTIVE** | `unset` — env var absent (`env \| grep -c DSH_LIVE_BRIDGE_ACTIVE` = 0) | ⛔ BLOCKED |
| 2 | **7 D4/D7 instances mounted** | All 7 `NOT_MOUNTED` (`probe_all_instances_mounted()` → zeko..nova all False; `all_mounted=False`). Files persistent (7 presets, 7 `subagent_*` rows) but bridge inactive | ⛔ BLOCKED |
| 3 | **REAL backend available** | `probe_backend_kind()` = `unavailable` (BackendKind.UNAVAILABLE); `RealDSHBackend` has no live bridge | ⛔ BLOCKED |
| 4 | **real child observable** | `precondition()` → `real_dsh_child_observable=False`, `satisfied=False` | ⛔ BLOCKED |
| 5 | **approval path** | `approval_readiness()` → `status=APPROVAL_INTERACTIVE_READY`, `composed=True`, `interactive_ready=True`, `effective_policy=ask`, web session attached (`web_server_reachable=True`); **`e2e_status=UNKNOWN`, `probe_answered=False`, `approval_events=[]`** — no independently re-derivable `approval/asked`+`approval/decided` pair | 🟡 PARTIAL (composition-ready; E2E UNKNOWN, never promoted) |
| 6 | **authorized G13 run** | `LiveDSHRuntimeDriver.execute()` → `final_status=BLOCKED`, `denial_path=live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer`, `stopReason=refused`; no Human acceptance of `docs/security/0003` §15 | ⛔ BLOCKED |
| 7 | **scratch workspace** | `tempfile.mkdtemp()` usable, writable, outside repo tree | ✅ READY |
| 8 | **evidence capture** | `audit/runtime/` exists (INT-01/07/11/12); plan defines 5 evidence requirements (GE-1..GE-5); payload fixtures define per-scenario evidence requirements | ✅ READY |
| 9 | **stop-at-first-failure** | No pytest config (`pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini`) sets `-x` or `maxfail=1`; documented invocation `pytest tests/g13/live_readiness/ -q` runs all 63 scenarios without fail-fast | ⛔ BLOCKED (not configured) |
| 10 | **rollback/cleanup** | Plan defines 4 rollback/cleanup steps (scratch-only, read-only role instances, no protected-path write, remove scratch) + 4 non-destructive guarantees (no web_fetch, no destructive dispatch, no DSH modification, no session-policy modification) | ✅ READY |
| 11 | **G10 current status** | **OPEN / BLOCKING** — O3 not implemented, no daemon, no write-path switch; O5 containment only (raw-write actor set `{zeko, cto}`); `docs/phase-5/security/g10/decision/0001-g10-o3-operator-decision-package.md` exists (handoff only, no closure) | ⛔ OPEN / BLOCKING (project security) |

---

## EXACT_CURRENT_BLOCKERS

| # | Blocker | Axis | Evidence (this session) |
|---|---------|------|-------------------------|
| B1 | **DSH_LIVE_BRIDGE_ACTIVE unset** | 1 | env var absent |
| B2 | **D4/D7 instances NOT_MOUNTED (all 7)** | 2 | `probe_all_instances_mounted()` all False |
| B3 | **No REAL backend** | 3 | `probe_backend_kind()=unavailable` |
| B4 | **No real DSH child observable** | 4 | `precondition()["satisfied"]=False` |
| B5 | **No authorized G13 run** | 6 | `LiveDSHRuntimeDriver` → `BLOCKED`; §15 not accepted |
| B6 | **Stop-at-first-failure not configured** | 9 | no `-x`/`maxfail=1` in any pytest config or documented invocation |
| B7 | **G10 OPEN / BLOCKING** | 11 | O3 not implemented; O5 containment only |

Not a hard blocker (PARTIAL, tracked): approval **composition** is READY
(`APPROVAL_INTERACTIVE_READY`) but approval **E2E** is UNKNOWN (no
independently re-derivable approval pair in the current session log).

---

## CHANGED_FROM_BASELINE

**Blocker set: unchanged (B1..B8 → B1..B7 + tracked PARTIAL). No blocker added,
removed, or reclassified on any G13-critical axis.** The G13 live execution
precondition is still not satisfied, exactly as recorded in the Session B
re-baseline and the prior gate report.

Observed facts since baseline (all re-verified this session, none changes the
verdict):

| # | Fact | Change? |
|---|------|---------|
| C1 | Approval composition re-verified live: `APPROVAL_INTERACTIVE_READY`, `composed=True`, E2E still UNKNOWN | No change (D1 holds; E2E stays UNKNOWN, never promoted) |
| C2 | O5 containment re-verified in live `cordis.patch.yml` (somad/nova allow lists contain no `write`/`edit`; raw-write actor set `{zeko, cto}`) | No change (D2 holds) |
| C3 | New G10 O3 operator decision/handoff package exists (`docs/phase-5/security/g10/decision/0001`) | **New artifact** — handoff only; G10 remains OPEN/BLOCKING; does not change G13 verdict |
| C4 | All 126 G13 tests green (90 Session D + 17 live_readiness + 19 gate) | No regression |
| C5 | No `audit/runtime/` G13 evidence created (no live run) | Unchanged — none expected |

---

## REQUIRED_OPERATOR_ACTIONS

To legally/procedurally unblock live G13 execution (in order):

1. **Human approves the per-session D4/D7 mount procedure (H7)** — required
   before any mount action.
2. **Operator runs the mount-verification procedure** (`docs/phase-5/environment/0001`
   §2.2): verify presets → verify instance rows → set the marker → resolve
   backend → probe → smoke dispatch. This is a per-session action; it must be
   re-verified every session.
3. **Human authorizes the G13 adversarial live test (H8)** — Human acceptance of
   `docs/security/0003` §15 (G13 live adversarial test authorization).
4. **Operator configures stop-at-first-failure** for the live G13 run: invoke
   with `-x`/`--maxfail=1` (or add `addopts = -x` to a pytest.ini) so the 63-case
   run stops at the first failure instead of cascading state contamination.
5. **Verify the approval answerer E2E path** before relying on it: confirm an
   independently re-derivable `approval/asked` + `approval/decided` pair exists
   in the session log (composition alone is not E2E evidence).
6. **Track G10 closure on a parallel track** (O3 implementation or DSH upgrade
   to a version with per-path/per-agent isolation). G10 OPEN/BLOCKING is a
   project-security blocker and must be recorded as such; it does not, by
   itself, block the non-destructive G13 live observation, but it must not be
   closed or bypassed by this gate.

---

## EVIDENCE_REQUIRED (to flip G13_LIVE_READY to YES)

Each of the following must be observed as committed, independently
re-derivable evidence before the live G13 run starts:

1. `echo ${DSH_LIVE_BRIDGE_ACTIVE:-unset}` → `1`
2. `probe_all_instances_mounted()` → all 7 `True` (subagent_zeko … subagent_nova)
3. `probe_backend_kind()` → `real-dsh` (BackendKind.REAL)
4. `precondition()["satisfied"]` → `True` (`real_dsh_child_observable=True`)
5. A minimal live `subagent_<id>` smoke dispatch settles with a real run id
   (per `docs/phase-5/environment/0001` §2.2)
6. `LiveDSHRuntimeDriver.execute(...)` no longer returns `BLOCKED` for the
   live preconditions (`human_signed_plan`, `d4_d7_mounted`, `approval_answerer`)
7. A pytest configuration with `-x`/`maxfail=1` present for the live G13 run
8. A Human acceptance record of `docs/security/0003` §15 (durable identity +
   timestamp) — no invented sign-off
9. An independently re-derivable `approval/asked` + `approval/decided` pair in
   the current session log (approval E2E verified, not assumed from composition)

Only after items 1–9 hold is the prepared 63-case live package
(`tests/g13/live_readiness/`) executable; then `audit/runtime/` G13 evidence
bundles (GE-1..GE-5) are required before any DSH-native observation is
recorded. No DSH-native immunity is claimed, now or at any point without a
runtime-observed denial on live DSH children.

---

## Constraints honored

- **No live G13 executed.** No payload re-created (7 channels / 56 vector×channel
  remain canonical and unchanged).
- **No DSH modification.** No session-policy/profile/preset change.
- **No invented Human approval.** No invented live evidence. Approval E2E stays
  UNKNOWN; G13 DSH-native stays UNKNOWN; G10 stays OPEN/BLOCKING.
- **No G13 PASS claimed.**

---

*Status: G13 LIVE EXECUTION GATE RECHECK — G13_LIVE_READY = NO. Blocker set
unchanged from baseline (B1..B7 + tracked approval-E2E PARTIAL). Prepared
63-case live package remains PREPARED, not executable. Required operator
actions and evidence items enumerated. No DSH/policy modification. No live
G13. No immunity claim.*

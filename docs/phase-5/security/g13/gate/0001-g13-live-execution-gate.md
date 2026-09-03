# G13 — Live Execution Gate (Precondition Assessment)

- **Gate**: G13 LIVE EXECUTION GATE
- **Status**: BLOCKED — prerequisites not satisfied
- **Date**: 2026-09-01
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Gate-only assessment. No payloads re-created. No DSH modified. No session policy modified. No G13 PASS claimed.
- **Prepared package**: `tests/g13/live_readiness/` — 63-case live G13 package (7 channels + 56 vector×channel)

---

## G13_PRECONDITION = BLOCKED

### 8-Axis Gate Check

| # | Axis | Required | Current | Status |
|---|------|----------|---------|--------|
| 1 | **REAL DSH child observable** | `precondition()["real_dsh_child_observable"]` must be `True` | `False` — confirmed by `precondition()` probe (see evidence) | ⛔ **BLOCKED** |
| 2 | **D4/D7 mounted** | All 7 `subagent_<id>` instances must be mounted | Files persistent (7 presets, 7 rows in `cordis.patch.yml`), but instances NOT_MOUNTED — all 7 mount probes `False`; `DSH_LIVE_BRIDGE_ACTIVE` (DISCOVERY_MARKER_ENV) unset | ⛔ **BLOCKED** |
| 3 | **DSH_LIVE_BRIDGE_ACTIVE** | Set to `1`, `true`, or `yes` | `unset` — not present in environment | ⛔ **BLOCKED** |
| 4 | **Backend kind** | `probe_backend_kind()` must be `real-dsh` | `unavailable` — `BackendKind.UNAVAILABLE`; `RealDSHBackend.start()` raises `BridgeNotAvailable` | ⛔ **BLOCKED** |
| 5 | **Scratch workspace** | Usable temp directory outside repo tree | Available — `tempfile.TemporaryDirectory()` works; plan explicitly defines "run only on a scratch workspace (never the repo tree)" | ✅ **READY** |
| 6 | **Evidence capture** | `audit/runtime/` writable; per-scenario evidence requirements defined | `audit/runtime/` exists (INT-01/07/11/12 bundles); plan defines 5 evidence requirements (GE-1..GE-5); payload fixtures define per-scenario evidence requirements | ✅ **READY** |
| 7 | **Stop-at-first-failure** | Test run must stop at first failure (`-x` / `maxfail=1`) | Not configured — documented invocation (`pytest tests/g13/live_readiness/ -q`) has no `-x`; no pytest config with `maxfail=1`; suite would run all 63 scenarios regardless of first failure | ⛔ **BLOCKED** (not configured) |
| 8 | **Authorization** | Human-authorized live-run condition; `LiveDSHRuntimeDriver` must allow live dispatch | `LiveDSHRuntimeDriver.execute()` → `BLOCKED` (missing: `human_signed_plan`, `d4_d7_mounted`, `approval_answerer`); no Human acceptance of `docs/security/0003` §15 recorded; session policy `ask` (composition ready, but E2E UNKNOWN) | ⛔ **BLOCKED** |

---

### Readiness Summary

| Axis | Result |
|------|--------|
| REAL DSH child observable | ❌ BLOCKED |
| D4/D7 mounted | ❌ BLOCKED |
| DSH_LIVE_BRIDGE_ACTIVE | ❌ BLOCKED |
| Backend kind | ❌ BLOCKED |
| Scratch workspace | ✅ READY |
| Evidence capture | ✅ READY |
| Stop-at-first-failure | ❌ BLOCKED (not configured) |
| Authorization | ❌ BLOCKED |

**6 of 8 axes are BLOCKED. 2 of 8 axes are READY.**

---

### Evidence

```text
precondition() = {
  "marker_set": False,
  "instances_mounted": {
    "subagent_zeko": False, "subagent_cto": False,
    "subagent_cfo": False, "subagent_kai": False,
    "subagent_somad": False, "subagent_badsector": False,
    "subagent_nova": False
  },
  "all_instances_mounted": False,
  "backend_kind": "unavailable",
  "real_dsh_child_observable": False,
  "satisfied": False
}

DSH_LIVE_BRIDGE_ACTIVE: unset
probe_backend_kind().value: unavailable
LiveDSHRuntimeDriver.execute() → BLOCKED (missing: human_signed_plan, d4_d7_mounted, approval_answerer)
```

---

### Gate Detail — Per Axis

#### 1. REAL DSH child observable
`precondition()["real_dsh_child_observable"]` evaluates to `False` because the marker is not set, no instances are mounted, and the backend is unavailable. A REAL DSH child cannot be dispatched in this session.

#### 2. D4/D7 mounted
The D4/D7 composition files are persistent (7 presets under `$DSH_HOME/.agent-presets/`; 7 `subagent_<id>` rows in `cordis.patch.yml`). However, the live bridge is not active — the marker env var `DSH_LIVE_BRIDGE_ACTIVE` is unset, so all 7 `check_instance_mounted()` probes return `False`. Per `docs/phase-5/environment/0001` (ENV-MOUNT-1), mount is per-session and must be re-verified every session.

#### 3. DSH_LIVE_BRIDGE_ACTIVE
The environment variable `DSH_LIVE_BRIDGE_ACTIVE` is unset. The `check_instance_mounted()` function checks for `1`, `true`, or `yes` — none are present. The orchestrator session must set this marker after verifying the D4/D7 composition is mounted.

#### 4. Backend kind
`probe_backend_kind()` returns `BackendKind.UNAVAILABLE`. The 3-state backend discrimination (`FAKE` / `REAL` / `UNAVAILABLE`) honestly reports `UNAVAILABLE` because no live DSH bridge is available. `RealDSHBackend.start()` raises `BridgeNotAvailable`.

#### 5. Scratch workspace
Available. `tempfile.TemporaryDirectory()` creates a writable scratch directory outside the repo tree. The live test plan explicitly defines rollback/cleanup step 1: "run only on a scratch workspace (never the repo tree)".

#### 6. Evidence capture
`audit/runtime/` directory exists with INT-01/07/11/12 evidence bundles. The plan defines 5 evidence requirements per scenario: ingestion record, authority-gate DENY record, child SubagentResult, protected-state hash comparison, and no delegation/approval/review record. The payload fixtures define per-scenario evidence requirements.

#### 7. Stop-at-first-failure
The documented invocation (`pytest tests/g13/live_readiness/ -q`) does not include `-x` or `--maxfail=1`. No pytest configuration file (pytest.ini, pyproject.toml, setup.cfg, tox.ini) exists in the workspace. The suite would run all 63 scenarios regardless of first failure. A live security test should stop at first failure to prevent cascading state contamination.

**Fix**: Add `-x` to the invocation command, or configure `addopts = -x` in a pytest.ini.

#### 8. Authorization
`LiveDSHRuntimeDriver.execute(scenario_id='G13-LIVE-C1', action='write', target='agents/**')` returns `BLOCKED` with denial path `live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer`. No Human acceptance of `docs/security/0003` §15 is recorded. Session policy is `ask` (composition-ready, but E2E status UNKNOWN — no independently re-derivable `approval/asked`+`approval/decided` pair in the current session log).

---

### Blocker Set (6 items)

| # | Blocker | Axis | Action required |
|---|---------|------|-----------------|
| B1 | No REAL DSH child observable | 1 | Set `DSH_LIVE_BRIDGE_ACTIVE=1` after verifying the D4/D7 composition is mounted per `docs/phase-5/environment/0001` §2.2 |
| B2 | D4/D7 instances NOT_MOUNTED | 2 | Run per-session mount-verification procedure: verify presets → verify rows → set marker → resolve backend → probe → smoke dispatch |
| B3 | `DSH_LIVE_BRIDGE_ACTIVE` unset | 3 | Set `DSH_LIVE_BRIDGE_ACTIVE=1` for the orchestrator session |
| B4 | Backend kind `unavailable` | 4 | Requires live bridge active (B1+B2+B3 resolved) |
| B5 | Stop-at-first-failure not configured | 7 | Add `-x` flag to the pytest invocation or configure via pytest.ini |
| B6 | No authorized live-run condition | 8 | Human must accept `docs/security/0003` §15; `LiveDSHRuntimeDriver` must allow live dispatch |

---

### Constraints

- **Not re-created**: Payloads remain at `tests/g13/live_readiness/payloads.py` (unchanged).
- **Not modified**: DSH core/profile/preset/session policy — unchanged.
- **Not claimed**: G13 PASS is not claimed. G13 remains UNKNOWN at the DSH-native layer.
- **Not executed**: No live G13 dispatch performed. No `audit/runtime/` G13 evidence created.

---

*Status: G13 LIVE EXECUTION GATE — BLOCKED (prerequisites not satisfied). 6 of 8 axes blocked. Prepared 63-case package at `tests/g13/live_readiness/` is ready to execute when all 6 blockers are resolved.*
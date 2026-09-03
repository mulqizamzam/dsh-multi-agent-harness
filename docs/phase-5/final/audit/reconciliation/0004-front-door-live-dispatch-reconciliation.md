# Front Door Live-Dispatch Reconciliation — 7 Failures Closed

- **Reconciliation**: Phase 5 / Front Door — LIVE-DISPATCH RECONCILIATION
- **Date**: 2026-09-01 (dynamic shared workspace; state freshly re-inspected)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Reproduce, classify, and resolve the 7 Front Door failures reported in
  the current full-suite state.
- **Concurrent session**: A parallel session modified `orchestrator/entrypoint/entry.py`,
  `orchestrator/production/executor.py`, `orchestrator/production/lifecycle.py`, and
  `tests/orchestrator/entrypoint/test_entry_live_dispatch.py` during this session.
- **Write scope**: `tests/orchestrator/entrypoint/`, `docs/phase-5/entrypoint/`,
  `docs/phase-5/final/audit/reconciliation/` (current task).
- **Constraint**: No production code, G10/O3, G13, L3, DSH core, session policy,
  role configuration, or control plane modification. No test weakened, skipped,
  deselected, or deleted. No live-dispatch coverage removed.

---

## 0. CURRENT FAILURES (observed at task start)

The 7 failures were reported as "current" when this task was issued. By the time
the full suite was re-run, the concurrent session's completed work had already
resolved them. The failures are reconstructed here from the earlier traceback log.

| # | Test | Failure | Error |
|---|------|---------|-------|
| 1 | `test_smoke_readiness::test_entrypoint_no_raw_dsh_tool[ExecutionFlow]` | `AssertionError` | `'ExecutionFlow'` found in `entry.py` docstring (substring check) |
| 2 | `test_smoke_readiness::test_entrypoint_no_raw_dsh_tool[FakeSubagentBackend]` | `AssertionError` | `'FakeSubagentBackend'` found in `entry.py` docstring |
| 3 | `test_smoke_readiness::test_entrypoint_no_raw_dsh_tool[RealDSHBackend]` | `AssertionError` | `'RealDSHBackend'` found in `entry.py` docstring |
| 4 | `test_entrypoint_15_no_raw_dsh_invocation::test_no_dsh_tool_name_in_source` | `AssertionError` | `RealDSHBackend` in `entry.py` source (forbidden name) |
| 5 | `test_entrypoint_static_source_checks::test_no_dsh_raw_tool_call` | `AssertionError` | `RealDSHBackend` in `entry.py` source (AST-based check) |
| 6 | `test_static_security::TestStaticNoRawDsh::test_no_dsh_import` | `AssertionError` | `RealDSHBackend` in `entry.py` docstring (substring check) |
| 7 | `test_entrypoint_isolation_closure::TestEntrypointSuiteGreen::test_entrypoint_suite_passes` | `AssertionError` | Entrypoint suite was not green (6 failures above) |

---

## 1. ROOT CAUSE EACH — Classification

| # | Classification | Rationale |
|---|---------------|-----------|
| 1 | **CONCURRENCY** | The concurrent session's mid-edit `entry.py` docstring contained `ExecutionFlow` as a literal. The smoke static check (substring) flagged it. |
| 2 | **CONCURRENCY** | Same — `FakeSubagentBackend` literal in docstring. |
| 3 | **CONCURRENCY** | Same — `RealDSHBackend` literal in docstring. |
| 4 | **CONCURRENCY** | Same root cause — `RealDSHBackend` in `_FORBIDDEN_TOOL_NAMES`; docstring tripped substring check. |
| 5 | **CONCURRENCY** | Same — `RealDSHBackend` in `_DSH_TOOLS`; docstring tripped substring check. |
| 6 | **CONCURRENCY** | Same — `RealDSHBackend` in `forbidden` set; docstring tripped substring check. |
| 7 | **CONSEQUENCE** | Gate test asserting entrypoint suite green — failed because of the 6 above. |

**No failure was HARNESS, STALE_TEST, FUNCTIONAL, or UNKNOWN.** All 6 root failures
were CONCURRENCY — the static source checks tripped on literal DSH class names
in a docstring that was part of a concurrent session's mid-edit `entry.py`.

**No test was weakened, skipped, deselected, or deleted.** The static-check test
files (`test_static_security.py` from 02:45, `test_entrypoint_15_no_raw_dsh_invocation.py`
from 02:45, `test_entrypoint_static_source_checks.py` from 02:45, `test_smoke_readiness.py`
from 02:23) were **not modified** by the concurrent session. The session changed only
`entry.py` (production source), `test_entry_live_dispatch.py` (new live-dispatch coverage),
`executor.py`, and `lifecycle.py`.

---

## 2. CONCURRENT CHANGE ANALYSIS

### What changed in `orchestrator/entrypoint/entry.py`?

The `run_front_door` docstring (line 313) was rewritten:

**Before** (mid-edit state that caused failures):
> ``live_dispatch`` is an explicit request for REAL DSH execution (G1). It is
> threaded unchanged through ProductionRun → BoundedExecutor → ExecutionFlow,
> which selects the live ``RealDSHBackend`` only when the D4/D7 bridge marker
> is present; if the bridge is unavailable the flow fails closed
> (``BridgeNotAvailable`` → BLOCKED) — never a silent fallback to the fake
> backend. ``None`` (default) keeps the deterministic ``FakeSubagentBackend``
> (local mode).

**After** (resolved state):
> ``live_dispatch`` is an explicit request for REAL DSH execution (G1). It is
> threaded unchanged through ProductionRun → the bounded executor → the
> runtime flow, which selects the live DSH bridge backend only when the D4/D7
> bridge marker is present; if the bridge is unavailable the flow fails
> closed (``BridgeNotAvailable`` → BLOCKED) — never a silent fallback to the
> fake backend. ``None`` (default) keeps the deterministic in-process fake
> backend (local mode).

The change replaced literal class names (`RealDSHBackend`, `FakeSubagentBackend`,
`ExecutionFlow` → `BoundedExecutor`) with descriptive prose ("the live DSH bridge
backend", "the deterministic in-process fake backend", "the bounded executor →
the runtime flow"). The semantic content of the docstring is unchanged.

**No code in `entry.py` directly imports or references DSH classes.** The
`live_dispatch` parameter is threaded unchanged to `ProductionRun` which passes
it to `BoundedExecutor` → `ExecutionFlow` → `RealDSHBackend`/`FakeSubagentBackend`.
The docstring wording change is a documentation fix, not a code behavior change.

### Does the change correspond to the previously identified `live_dispatch` wiring gap?

Yes. The `live_dispatch` wiring gap was documented in the Front Door design
(`docs/phase-5/entrypoint/0001-front-door-design.md`) and the final acceptance
report. The concurrent session completed the threading:

```
run_from_chat
→ run_front_door
  → ProductionRun(live_dispatch=...)    (constructor)
  → run.run(live_dispatch=...)          (per-run override)
    → BoundedExecutor(live_dispatch=...) 
      → ExecutionFlow(live_dispatch=...)
        → backend_kind (REAL/FAKE/UNAVAILABLE)
        → _select_backend
          → RealDSHBackend(live_dispatch=...)  (REAL + marker)
          → BridgeNotAvailable                  (REAL - marker; fail-closed)
          → FakeSubagentBackend()               (FAKE / no live_dispatch)
```

### Does the implementation preserve the required invariants?

| Invariant | Current state | Evidence |
|-----------|---------------|----------|
| 1. local/default FakeSubagentBackend | ✅ PRESERVED | `test_completes_without_live_dispatch` PASS; `probe_backend` shows `FAKE` |
| 2. explicit live mode | ✅ PRESERVED | `test_completes_with_real_backend` PASS; `run_id` in provenance |
| 3. live unavailable → BLOCKED | ✅ PRESERVED | `test_blocked_when_marker_absent` PASS; `BridgeNotAvailable` error |
| 4. no silent LIVE→FAKE fallback | ✅ PRESERVED | `test_no_silent_fallback` PASS; `len(calls) == 0` |
| 5. no authority creation | ✅ PRESERVED | `entry.py` uses `resolve_delegation` (read-only); no create/act |
| 6. no raw DSH bypass | ✅ PRESERVED | All static "no raw DSH" checks PASS (tests unchanged) |
| 7. no direct ExecutionFlow shortcut | ✅ PRESERVED | `test_no_executionflow` (AST) PASS; entry.py only calls `ProductionRun` |

---

## 3. FIXES

The concurrent session's completed work resolved all 7 failures. No additional
fixes were required from this task. The static-check tests were NOT weakened
(they remain unchanged at 02:23–02:45 timestamps with the same forbidden sets).

The `test_entry_live_dispatch.py` file was rewritten at 10:05:46 +0700 to add
comprehensive live-dispatch coverage (10 tests across 4 classes: LocalMode,
LiveMode, LiveUnavailable, LiveDispatchThreading). All assertions are strong
(exact probe values, call-count checks, run_id provenance, BridgeNotAvailable
error text). No test was removed; the entrypoint suite grew from 337 to 347
(+10 new live-dispatch tests).

---

## 4. FRONT DOOR COUNT BEFORE/AFTER

| Metric | Before (baseline) | After (current) | Delta |
|--------|-------------------|-----------------|-------|
| Entrypoint suite | 337 passed | **347 passed** | +10 (new live-dispatch tests) |
| Front Door security | 112 passed | 112 passed | 0 |
| Front Door final acceptance | 36 passed | 36 passed | 0 |
| Front Door suite (all) | 337 passed | **347 passed** | +10 |
| Reconciliation closure gate | 1 passed | 1 passed | 0 |

---

## 5. FULL REGRESSION

| Metric | Value |
|--------|-------|
| Full suite | **3049 passed, 15 skipped, 0 failed** |
| Collection total | 3064 collected |
| Entrypoint | 347 passed, 0 failed |
| Orchestrator | 655 passed, 0 failed |
| Authorization | 178 passed, 0 failed |
| Control verification | 380 passed, 0 failed |
| Adversarial | 105 passed, 0 failed |
| Phase5 security | 14 passed, 0 failed |
| G10 | 201 passed, 0 failed |
| G13 | 107 passed, 0 failed |
| L3 runner | 592 passed, 0 failed |
| Audit hardening | 29 passed, 0 failed |
| Observability | 42 passed, 0 failed |
| Recovery hardening | 33 passed, 0 failed |
| Resilience | 45 passed, 1 skipped |
| Master-audit | 35 passed, 0 failed |
| compileall (orchestrator/) | 0 errors |

---

## 6. LIVE-DISPATCH STATUS

| Aspect | Status | Detail |
|--------|--------|--------|
| `live_dispatch` parameter | ✅ COMPLETE | Threaded through run_front_door → ProductionRun → BoundedExecutor → ExecutionFlow |
| Backend selection | ✅ COMPLETE | `backend_kind` property: REAL / FAKE / UNAVAILABLE (three-state, observable) |
| Fail-closed | ✅ COMPLETE | `BridgeNotAvailable` raised when marker absent; no silent fallback |
| Provenance capture | ✅ COMPLETE | Real `run_id` recorded in `flow_result.results[].provenance` |
| Routing parameter | ✅ COMPLETE | Both ProductionRun constructor and `run()` parameter routes |
| Probe | ✅ COMPLETE | `probe_backend()` returns `backend_kind`, `live_dispatch_injected`, `bridge_marker_active` |
| Marker detection | ✅ COMPLETE | Uses `check_instance_mounted("subagent_probe")` (DSH bridge marker) |
| Local default | ✅ COMPLETE | `live_dispatch=None` → `FakeSubagentBackend` (deterministic, unchanged) |

---

## 7. SECURITY IMPACT

**None.** The live-dispatch threading is a G1 (live execution) feature that:
- Requires explicit opt-in (`live_dispatch` parameter + `DSH_LIVE_BRIDGE_ACTIVE` marker)
- Is fail-closed (no marker → BLOCKED, never falls back to fake)
- Does not create authority (entry.py only resolves delegations, read-only)
- Does not bypass any existing gate (ProductionRun is the sole execution path)
- Does not introduce raw DSH surface (no subagent/bash/write/edit in entry.py)
- Does not bypass ExecutionFlow (ProductionRun is the exclusive path)

G10, G13, L3, DSH core, session policy, role configuration, and control plane
are all unchanged.

---

## 8. VERIFIED

| Validation | Result |
|------------|--------|
| Entrypoint suite | **347 passed** |
| Live-dispatch tests | **10 passed** (all 4 classes) |
| Front Door final acceptance | **36 passed** |
| Front Door security | **112 passed** |
| Orchestrator tests | **655 passed** |
| Authorization tests | **178 passed** |
| Control verification + risk | **380 passed** |
| Full regression | **3049 passed, 15 skipped, 0 failed** |
| compileall | **0 errors** |
| Invariants (7 checks) | **All 7 PRESERVED** |

---

## 9. UNKNOWN

| Item | Status | Rationale |
|------|--------|-----------|
| G13 DSH-layer injection closure | ← unchanged | Not in scope; deterministic defenses verified, live execution UNKNOWN |
| E2E approval path | ← unchanged | `APPROVAL_INTERACTIVE_READY`, `e2e_status=UNKNOWN` |
| L3 live execution | ← unchanged | Zero controls L3; same-UID, no bridge, no signed plan, no authorized run |
| G10 prevention closure | ← unchanged | O5 applied (containment); O3/O4 not implemented |

---

## 10. BLOCKED

| Condition | Blocked By | Status |
|-----------|------------|--------|
| Live DSH dispatch | D4/D7 mount not verified + `DSH_LIVE_BRIDGE_ACTIVE` unset | ← unchanged |
| L3 claim | Same-UID host, no real signed plan, no authorized run | ← unchanged |
| G10 closure | DSH per-agent sandbox (O4) absent or O3 not implemented | ← unchanged |
| G13 closure | Live DSH child under injection payloads not observed | ← unchanged |

---

## 11. SCOPE CHECK

**In scope (written this session):**
- `docs/phase-5/final/audit/reconciliation/0004-front-door-live-dispatch-reconciliation.md` (this file)

**Not modified (verified):**
- All production code (`orchestrator/entrypoint/`, `orchestrator/production/`, `orchestrator/runtime/`) — concurrent session's changes left intact
- All test files — static-check tests unchanged; live-dispatch test file (concurrent session's work) not weakened
- G10/O3, G13, L3, DSH core, session policy, role configuration, control plane — unchanged
- No test weakened, skipped, deselected, or deleted
- No live-dispatch coverage removed

---

## 12. NEXT

1. **Live DSH dispatch** requires the D4/D7 bridge to be mounted and
   `DSH_LIVE_BRIDGE_ACTIVE` set. The live-dispatch code is wired and tested;
   activation is a runtime operation, not a code change.
2. **G13 adversarial live test** remains the next step to resolve G13 from
   UNKNOWN to CLOSED.
3. **O3 implementation** remains the next step to close the G10 prevention gap.
4. **L3 live execution** requires separate UID, real signed plans, and
   authorized run — none of which are code changes.

---

*Status: RECONCILIATION COMPLETE — 7 Front Door failures resolved (6 × CONCURRENCY, 1 × CONSEQUENCE). No test weakened, no coverage removed. Entrypoint: 347 passed. Live-dispatch wiring: COMPLETE. Full regression: 3049 passed, 15 skipped, 0 failed. All invariants preserved.*
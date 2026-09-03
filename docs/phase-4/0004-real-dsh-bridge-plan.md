# Session C — REAL DSH Bridge Implementation Plan

- **Status**: PLANNED (minimum non-implemented work defined; no implementation, no DSH/profile/preset/config change, no test modification)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `docs/phase-4/` (this document). Read-only inspection of `orchestrator/runtime/*`, `orchestrator/dsh/*`, `tests/live_dsh/*`, D4/D7 composition, and Phase-3 live evidence.
- **Rule**: define the minimum implementation plan to replace `FakeSubagentBackend` with REAL DSH runtime dispatch. Do not implement, do not modify DSH/profiles/presets/config/implementation/tests.

---

## 1. Current state (verified by inspection)

| Component | Current setup | How it was proven in Phase-3 closure |
|---|---|---|
| `ExecutionFlow._get_client()` | Hardcodes `self._client = DelegationClient(backend=FakeSubagentBackend())` (line 221) | Overridden manually via `subtask_runner` parameter in Phase-3 closure |
| `DelegationClient.__init__` | Accepts `backend` parameter; defaults to `FakeSubagentBackend()` | Injected `RealDSHBackend` with live `DSHBridgeDispatch` |
| `RealDSHBackend` | Exists in `tests/live_dsh/real_backend.py`; requires injected `DSHBridgeDispatch` + `require_marker` | Used for all four INT scenarios; `DSH_LIVE_BRIDGE_ACTIVE=1` set |
| D4/D7 composition | `config/role-preset-mapping.yaml` (finalized), `config/tool-subagent-instances.yaml` (draft) | Mounted and active during Phase-3 closure; all 7 `subagent_<id>` probes passed |
| Default execution path | `FakeSubagentBackend` (deterministic, no live DSH) | All Phase-3 unit tests use this |

**The `RealDSHBackend` already exists and has been proven working in Phase-3 closure. The remaining gap is production-owned wiring of the live backend selection into the default `ExecutionFlow` path.**

---

## 2. Minimum implementation plan

### 2.1 Insertion point

**File**: `orchestrator/runtime/flow.py`, method `_get_client()` (lines 219–222)

**Current code**:
```python
def _get_client(self) -> DelegationClient:
    if self._client is None:
        self._client = DelegationClient(backend=FakeSubagentBackend())
    return self._client
```

**Required change**: `_get_client()` must detect whether the live DSH bridge is available (e.g., via an environment marker `DSH_LIVE_BRIDGE_ACTIVE=1` and a resolved bridge dispatch) and select the appropriate backend. The `FakeSubagentBackend` remains the deterministic default for unit tests. The live backend is selected only when the marker is present and a bridge injection is provided.

**Design constraint**: This is a **backend selection** change, not a new authority path or a new gate. The `DelegationClient` and all downstream enforcement (role resolution, scope containment, context sanitization, result collection, provenance) are unchanged.

### 2.2 Lifecycle

| Phase | Current | Required |
|---|---|---|
| `ExecutionFlow.__init__` | `_client = None` (lazy) | Same — lazy creation |
| `_get_client()` — first call | Creates `DelegationClient(FakeSubagentBackend)` | Check live bridge marker; if active, create `DelegationClient(RealDSHBackend(dispatch))`; otherwise fall back to `FakeSubagentBackend` |
| `run()` — per call | Creates client once | Same |
| Backend disposal | `DelegationRun.dispose()` per child | Same — `RealDSHRun.dispose()` already implemented |

**The `RealDSHBackend` is created once per `ExecutionFlow` instance and reused across subtasks. No per-subtask lifecycle change is needed.**

### 2.3 Dispatch path

```
Existing:  DelegationClient.delegate(task, delegation)
           → backend.start(instance, context)
           → FakeSubagentBackend.start() → _FakeRun.result()
           → DelegationResult

Required:  DelegationClient.delegate(task, delegation)  [UNCHANGED]
           → backend.start(instance, context)           [UNCHANGED]
           → RealDSHBackend.start()                      [EXISTS]
             → build DSHInvocation from authorized context
             → check mount marker (require_marker=True)
             → dispatch(invocation, instance)            [live bridge boundary]
             → DSHBridgeResponse → DelegationResult
           → DelegationResult                            [UNCHANGED]
```

**Key constraints**:
- The `RealDSHBackend` is already implemented in `tests/live_dsh/real_backend.py` (234 lines, proven in Phase-3 closure).
- It must be moved or importable from the production `orchestrator.dsh` namespace without importing test-support code.
- The dispatch bridge injection must be provided by the orchestrator session environment (not by the test harness).
- `require_marker=True` (default) enforces the mount-marker gate; `BridgeNotAvailable` is raised if the marker is absent → fail-closed, never silent fallback to fake.

### 2.4 Result path

```
Existing:  DelegationClient.delegate()
           → backend.start() → DelegationRun.result()
           → DelegationResult (structured, stop_reason, diagnostic)
           → TaskResultCollector.collect() → TaskResult
           → DelegationProvenance.build()

Required:  [IDENTICAL — the RealDSHBackend already returns DelegationResult
            through DSHBridgeResponse.to_delegation_result()]
```

**No result-path change is needed.** The `RealDSHBackend` conforms to the existing `DelegationBackend` contract.

### 2.5 Provenance

```
Existing:  DelegationProvenance.build(delegation, task, instance, run,
                                       started_at, settled_at, result,
                                       result_status)
Required:  [IDENTICAL — RealDSHBackend returns real run_id from the
            DSHBridgeResponse, which is captured by DelegationProvenance]
```

Phase-3 closure proves provenance with real run IDs for all four scenarios. No change needed.

### 2.6 Timeout / abort

**Existing**: `DelegationClient._settle()` watchdog thread enforcing `timeout_seconds` + signal-based abort.

**Required**: No change. The watchdog works identically for any backend. `RealDSHBackend` accepts `signal` and `timeout_seconds` parameters per the `DelegationBackend` contract. The watchdog enforces timeouts at the orchestrator layer; the DSH tool-call budget (`toolCallTimeoutMs`) is enforced at the DSH layer.

### 2.7 Failure propagation

| DSH stop reason | Adapter exception | `failure_class` | Existing test |
|---|---|---|---|
| `completed` | (none — success) | n/a | `test_live_dsh` |
| `aborted` | `DelegationAborted` | environment | `test_timeout_abort.py` |
| `error` | `ChildFailure` | logic | `test_failure_propagation.py` |
| `max-tokens` | `ChildFailure` | environment | `test_failure_propagation.py` |
| `refusal` | `ChildFailure` | logic | `test_failure_propagation.py` |
| unknown | fail-closed error | unknown → escalate | `test_failure_propagation.py` |

**Required**: No change. The mapping is already implemented in `RealDSHBackend` and the `DelegationClient` path.

### 2.8 Cleanup

**Existing**: `DelegationRun.dispose()` — idempotent, releases resources.

**Required**: No change. `_RealDSHRun.dispose()` is implemented in `tests/live_dsh/real_backend.py` (line 119). Interrupt and child discovery are also implemented.

### 2.9 Rollback

**Not a backend concern.** Rollback is handled by the `ExecutionFlow` recovery lifecycle (`RecoveryController`), the state version guard (`RuntimeStore.check_current`), and the execution gate (`control/execution_gate.py`). The backend is stateless with respect to the project state; it only dispatches and collects. No rollback change is needed.

---

## 3. What must be implemented (exact scope)

| # | Item | Location | Description |
|---|---|---|---|
| 1 | **Live backend selection** | `orchestrator/runtime/flow.py` — `_get_client()` and `__init__` | Add a `live_dispatch` parameter (or equivalent) to `ExecutionFlow.__init__`; make `_get_client()` check the DSH live bridge marker and select `RealDSHBackend` when active, `FakeSubagentBackend` otherwise. |
| 2 | **RealDSHBackend import** | `tests/live_dsh/real_backend.py` | Move or expose `RealDSHBackend` through the production `orchestrator.dsh` namespace so `ExecutionFlow` can import it without depending on test-support packages. |
| 3 | **Bridge injection point** | `orchestrator/runtime/flow.py` or orchestrator session bootstrap | Define how the orchestrator session provides the `DSHBridgeDispatch` to `ExecutionFlow`. The Phase-3 closure used a manual injection; Phase-4 needs a durable, environment-aware injection mechanism. |
| 4 | **Mount-marker gate** | `RealDSHBackend` (already exists) | Already implemented (`require_marker=True`, `check_instance_mounted`). No change needed. |
| 5 | **Unit tests for backend selection** | New or extended tests under `tests/orchestrator/runtime/` or `tests/orchestrator/dsh/` | Prove that `ExecutionFlow` selects the correct backend based on the marker; prove that an absent marker falls back to `FakeSubagentBackend`; prove that `BridgeNotAvailable` is raised when the marker is absent but live dispatch is requested. |

---

## 4. What is reused (no change)

| Component | Reason |
|---|---|
| `DelegationClient` | Backend-agnostic; accepts any `DelegationBackend` |
| `DelegationBackend` / `DelegationRun` / `DelegationResult` | Contract interfaces; unchanged |
| `TaskResultCollector` | Structured result validation; unchanged |
| `DelegationProvenance` | Provenance stamp builder; unchanged |
| `RoleResolver` / `SubagentInstance` | Role resolution; unchanged |
| `build_task_context` / `assert_no_authority_in_payload` | Context sanitization; unchanged |
| `ExecutionEngine` | Authority re-check, verification, recovery; unchanged |
| `RuntimeStore` / `RuntimeAudit` | State/audit persistence; unchanged |
| `ParallelExecutor` | Parallel safety preflight; unchanged |

---

## 5. Required live tests

After the backend selection is implemented, the following tests must pass against the deployed live bridge:

| Test | What it proves | Existing evidence |
|---|---|---|
| Backend selection: marker present → `RealDSHBackend` | Selection logic works | Phase-3 closure proves manual injection works |
| Backend selection: marker absent → `FakeSubagentBackend` | Deterministic fallback is safe | Phase-3 unit tests |
| Backend selection: marker absent + live request → `BridgeNotAvailable` | Fail-closed; no silent fallback | `tests/live_dsh/test_backend_kind.py` |
| INT-01 live full lifecycle | Real child dispatch + verification PASSED + COMPLETE | `audit/runtime/INT-01/` |
| INT-07 live revocation lifecycle | Real child + execution-time DENY + BLOCKED | `audit/runtime/INT-07/` |
| INT-11 live parallel collection | 3 concurrent real children | `audit/runtime/INT-11/` |
| INT-12 live failure propagation | Real child failure + recovery entry | `audit/runtime/INT-12/` |
| 75-contract-test suite | Full contract compliance | `tests/live_dsh/` (75 passed) |

All four INT scenarios have existing canonical evidence bundles at `audit/runtime/<SCENARIO>/` that passed Phase-3 QA validation. The Phase-4 implementation must re-run against the same contract and produce matching evidence.

---

## 6. Rollback / cleanup

**If the live dispatch fails mid-session**:
- `ExecutionFlow` catch-all (`run()` lines 281–282) already catches `Exception` and `FlowStopped` → blocked, fail-closed.
- `RealDSHBackend.start()` raises `BridgeNotAvailable` when the marker is absent → `ExecutionFlow` catches it → blocked.
- `DelegationClient._settle()` watchdog raises `DelegationTimeout` → `ExecutionFlow` catches it → recovery path.
- `ChildFailure` from a real child propagates → `ExecutionFlow` routes to recovery (`SubtaskFailed` → `_route_recovery`).

**If the composition is rolled back (D4/D7 unmounted)**:
- Marker disappears → `RealDSHBackend.start()` raises `BridgeNotAvailable` → all subsequent `DelegationClient.delegate()` calls fail closed → flow stops.
- No silent fallback to `FakeSubagentBackend` after a live request is made.
- The `ExecutionFlow` can be re-initialized with `FakeSubagentBackend` for deterministic development.

---

*Status: PLANNED. No implementation, no DSH/profile/preset/config change, no test modification. No Phase 4 execution started.*
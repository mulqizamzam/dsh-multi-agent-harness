# Phase 4 Integration Test Plan — P4I-01..P4I-08

- **Milestone**: Phase 4 / Session E — Integration Testing
- **Status**: SPECIFIED + DEFECT CLOSED (test suite; the only production change is the targeted audit event-id allocator in `orchestrator/runtime/audit.py` + the consequential nested-flow correlation fix in `observability/ingest.py`)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `tests/phase4_integration/` (this suite) + `docs/phase-4/testing/` (this document)
- **Companion to**: `docs/phase-4/0001-acceptance-matrix.md` · `docs/phase-4/0002-acceptance-baseline-reconciliation.md` · `docs/phase-4/0003-approval-readiness.md` · `docs/phase-4/scenarios/` · `docs/testing/` · `orchestrator/production/` · `orchestrator/runtime/` · `observability/` · `tests/orchestrator/production/` · `tests/scenarios/`

---

## 1. Objective

Define and execute the **Phase-4 integration test suite** — a cross-module, end-to-end test suite that exercises the **real Phase-4 production runtime** by wiring together:

- `orchestrator.production` (ProductionRun, BoundedExecutor, ObjectivePlanner, ReportGenerator)
- `orchestrator.runtime` (ExecutionFlow, GateRunner, TaskLifecycle, RuntimeAudit, ParallelExecutor)
- `control.*` (risk, evidence, conflict, badsector, authority, verification, recovery, execution_gate)
- `state.helpers` (atomic write, version check, recovery)
- `audit.helpers` (append-only log, integrity)
- `observability` (build_index_from_ledger, RunIndex, metrics, queries)

The suite focuses on **seven Phase-4 focus areas**:

| # | Focus area | Test ID | Acceptance rows |
|---|---|---|---|
| 1 | Cross-module production flow | P4I-01 | AEF-1, VER-1, VER-3, AUD-1, AUD-3 |
| 2 | Bounded autonomy | P4I-02 | AEF-2, AEF-4, AUTH-1, AUTH-2, PB-1 |
| 3 | Parallel execution | P4I-03 | PAR-1, PAR-2, PAR-3 |
| 4 | Failure propagation | P4I-04 | REC-1, REC-2, REC-3, AEF-4 |
| 5 | Final report | P4I-05 | AEF-1 (report), AUD-1, AUD-3 |
| 6 | Observability correlation | P4I-06 | AUD-2, AUTH-INV-14 |
| 7 | Phase-4 acceptance criteria | P4I-07 | ALL rows (parameterised) |
| 8 | Audit event-id uniqueness (defect closure) | P4I-08 | AUD-1, AUD-2, AUTH-INV-14, append-only + hash-chain integrity |

---

## 2. ID convention

| Prefix | Domain | Source |
|---|---|---|
| **P4I-01** .. **P4I-07** | Phase-4 integration scenarios | This document |

Each scenario maps to one or more Phase-4 acceptance matrix rows (`docs/phase-4/0001-acceptance-matrix.md`). The mapping is detailed in `0002-acceptance-criteria-coverage.md`.

---

## 3. Test driver

The suite uses the **real Phase-4 production modules** — no mocks, no harness proxy. Each test creates a temporary workspace, seeds the minimal directory structure, and drives the production lifecycle through `ProductionRun` / `BoundedExecutor` / `ExecutionFlow`. Deterministic in-process child execution is provided by `FakeSubagentBackend` / stub runners (the same helpers used by `tests/orchestrator/production/`).

### 3.1 Cross-module data flow (asserted by each test)

```
ProductionRun.run()
  ├── ObjectivePlanner.plan()          → ProductionPlan (DATA)
  ├── BoundedExecutor.execute()        → FlowResult (DATA)
  │     └── ExecutionFlow.run()
  │           ├── GateRunner            → gate decisions
  │           ├── TaskLifecycle         → state machine transitions
  │           ├── ParallelExecutor      → concurrent subtask execution
  │           ├── ExecutionEngine       → execute + verify + recovery
  │           ├── RuntimeAudit          → audit events
  │           └── write_through         → execution gate (file write)
  ├── ReportGenerator.generate()       → FinalReport (DATA)
  └── RuntimeAudit (production)        → audit events
        └── observability.build_index_from_ledger() → RunIndex
```

### 3.2 Workspace layout

Each test workspace contains:
```
workspace/
  state/registry/         ← delegation registry (sanctioned write)
  state/projects/         ← project state (CAS versioned)
  audit/                  ← audit ledger (append-only)
  agents/cto/             ← cto output target
  agents/cfo/             ← cfo output target (parallel)
  agents/kai/             ← kai output target (parallel)
  docs/                   ← analysis result target
```

---

## 4. Scenario catalogue

### P4I-01 — Cross-module production flow

| Field | Value |
|---|---|
| **Objective** | Prove the full cross-module production flow: ProductionRun → ObjectivePlanner → BoundedExecutor → ExecutionFlow → gates → execution gate → state machine → audit → final report. All modules wire correctly, the flow reaches COMPLETE, the file is written through the execution gate, the audit ledger contains the full lifecycle, and the observability index correlates the run. |
| **Modules integrated** | ALL production modules (listed in §3.1) |
| **Setup** | Valid ACTIVE delegation for `write` on `agents/**`; engineering objective; CTO subtask returns SUCCEEDED with evidence |
| **Expected** | `state.outcome == "complete"`, `state.phase == "close"`, `flow_result.outcome == "COMPLETE"`, `final_state == "COMPLETE"`, 7 gate records ALL ALLOW, verification PASSED, file written at `agents/cto/output.txt`, audit contains 21+ event classes, report JSON-serializable with outcome COMPLETE |
| **Invariants** | AEF-1, VER-1, VER-3, AUD-1, AUD-3, AUTH-INV-05/15/20 |

### P4I-02 — Bounded autonomy

| Field | Value |
|---|---|
| **Objective** | Prove that autonomy is bounded by the delegation scope: no delegation → ESCALATED, scope mismatch → DENY, revocation mid-flow → DENY, HIGH without approval → ESCALATED. Every denial stops the flow fail-closed, produces no mutation, and records an audit event. |
| **Modules integrated** | ProductionRun, BoundedExecutor, ObjectivePlanner, ExecutionFlow (authority gate, execution gate, audit) |
| **Setup** | Varied delegations (none, read-only, revocable, HIGH-requires-approval) |
| **Expected** | Every denial raises `ProductionDenied` / `ProductionEscalated`; no file written; audit contains `execution_denial` / `gate_*` denial events; state.outcome is `stopped` / `escalated` |
| **Invariants** | AEF-2, AEF-4, AUTH-1, AUTH-2, PB-1, AUTH-INV-05/06/10/20 |

### P4I-03 — Parallel execution

| Field | Value |
|---|---|
| **Objective** | Prove that independent subtasks (cfo+kai) run concurrently through the production flow, the parallel safety check passes, results are collected in batch order, and the state version is preserved. |
| **Modules integrated** | ProductionRun, BoundedExecutor, ExecutionFlow (ParallelExecutor, assert_parallel_safe, DelegationClient), RuntimeAudit, observability |
| **Setup** | Pricing objective → route to {cfo, kai}; both subtasks return SUCCEEDED; parallel_subtasks=True; max_workers=4 |
| **Expected** | `flow_result.parallel.safe == True`, `mode == "parallel"`, `owners == {cfo, kai}`, `results` length 2, version preserved, audit `parallel_batch` event present, observability `parallel_batches` length 1 |
| **Invariants** | PAR-1, PAR-2, PAR-3, THREAT-021 |

### P4I-04 — Failure propagation

| Field | Value |
|---|---|
| **Objective** | Prove that an execution-stage failure propagates correctly: the flow enters the recovery lifecycle, produces a recovery audit event, and can complete when a new diagnosed cause is supplied. A persistent failure escalates. A subtask child failure propagates (no partial success). No blind retry is accepted. |
| **Modules integrated** | ProductionRun, BoundedExecutor, ExecutionFlow (ExecutionEngine, RecoveryController, SubtaskFailed), RuntimeAudit, observability |
| **Setup** | (a) Flaky executor fails once, then succeeds; (b) always-failing executor; (c) runner raising ChildFailure; (d) identical-cause retry |
| **Expected** | (a) `ProductionEscalated` → recovery → `BoundedExecutor.recover(cause="new", ...)` → COMPLETE; (b) `ProductionEscalated` with recovery audit event, no file; (c) `ProductionDenied` / `ProductionEscalated`, no partial results, audit `subtask_failed`; (d) `ProductionDenied` with "no blind retry" message |
| **Invariants** | REC-1, REC-2, REC-3, AUTH-INV-12/16, THREAT-017/022 |

### P4I-05 — Final report

| Field | Value |
|---|---|
| **Objective** | Prove the structured final report is generated on COMPLETE, is JSON-serializable, contains the correct outcome/gates/verification/selected_roles/synthesis/files_written, and that a non-COMPLETE flow yields an honest (non-success) report. |
| **Modules integrated** | ReportGenerator, FinalReport, FlowResult, ProductionRun |
| **Setup** | (a) COMPLETE flow result; (b) BLOCKED flow result; (c) failed ProductionRun |
| **Expected** | (a) Report outcome COMPLETE, gates 7+, verification PASSED, selected_roles=["cto"], files_written non-empty, JSON-serializable; (b) Report outcome BLOCKED with errors preserved; (c) ProductionRun state has errors, report is None (not fabricated) |
| **Invariants** | AEF-1 (report), AUD-1, AUD-3, AUTH-INV-13/14 |

### P4I-06 — Observability correlation

| Field | Value |
|---|---|
| **Objective** | Prove that the observability layer correlates the audit ledger emitted by a real ProductionRun into a RunIndex with correct run/task/delegation/failure/evidence/parallel records, that the run_id is preserved (not derived), and that the ingest is clean on a real ledger (no duplicate ids, no rejected events, healthy report) while still failing closed on genuinely malformed/duplicate/missing events. |
| **Modules integrated** | ProductionRun, RuntimeAudit, observability (build_index_from_ledger, RunIndex, find_*, compute_metrics, health_report) |
| **Setup** | (a) COMPLETE ProductionRun; (b) parallel ProductionRun; (c) BLOCKED ProductionRun; (d) synthetic clean event stream |
| **Expected** | (a) 1 run, run_id == state.run_id (derived=False), outcome COMPLETE, task-1 correlated, delegations present, evidence refs present, run.problems == [], idx.rejected == [], append_only_ok True, health healthy; (b) parallel_batches length 1, owners {cfo,kai}, metrics parallelism.parallel_batches == 1; (c) outcome BLOCKED, failures length 1, denials.authority_denials == 1; (d) clean stream → health_report healthy True |
| **Invariants** | AUD-2, AUTH-INV-14, fail-closed correlation rules (defect CLOSED: no duplicate ids) |

### P4I-07 — Phase-4 acceptance criteria

| Field | Value |
|---|---|
| **Objective** | Assert each Phase-4 acceptance matrix row in the deterministic runtime: AEF-1..4, PAR-1..3, VER-1/3, REC-1..3, AUD-1/3, AUTH-1/2, PB-1. Each row is a focused executable assertion with a labelled criterion id. |
| **Modules integrated** | All production modules (parameterised) |
| **Setup** | Per-criterion specialised setup (varies by row) |
| **Expected** | Each criterion passes at the deterministic-runtime level. Honesty note: live-DSH variants and L3-dependent rows (VER-2, L3-1..2) are BLOCKED and not asserted. |
| **Invariants** | ALL Phase-4 acceptance rows (deterministic-runtime portions) |

### P4I-08 — Audit event-id uniqueness (defect closure)

| Field | Value |
|---|---|
| **Objective** | Prove the per-ledger event-id allocator closes the dual-audit duplicate-id defect: ProductionRun + ExecutionFlow on the same ledger produce all-unique sequential event ids; a reopened ledger continues after the ids already on disk; concurrent writers never collide; append-only and hash-chain integrity hold; observability reconstruction is clean; a deliberately injected duplicate is still detected (fail-closed is NOT weakened). |
| **Modules integrated** | orchestrator.runtime.audit (allocate_event_id, RuntimeAudit), audit.helpers (append_event, verify_append_only, read_events_strict), audit.helpers.integrity (verify_chain, compute_chain), observability (build_index_from_ledger, health_report) |
| **Setup** | (a) ProductionRun → 31 unique ids; (b) two RuntimeAudit instances on one ledger; (c) threaded concurrent writers; (d) restart/reopen after pre-existing ids; (e) injected duplicate detected by verify_append_only + observability DUPLICATE_EVENT; (f) append-only + chain on a real ledger; (g) observability reconstruction single-run healthy |
| **Expected** | All event ids unique and monotonic; no rejected events on a real ledger; reopen continues after max existing id; concurrency yields no collisions; injected duplicate still rejected; verify_append_only/verify_chain pass; observability single run healthy. |
| **Invariants** | AUD-1, AUD-2, AUTH-INV-14, append-only + hash-chain integrity, fail-closed duplicate detection preserved |

---

## 5. Running

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/phase4_integration/ -v

# Run a single scenario
.venv-tests/bin/python3 -m pytest tests/phase4_integration/test_01_cross_module_production_flow.py -v
```

The suite uses the same virtual environment as the existing tests and requires no additional dependencies.

---

## 6. Honesty boundary

- **Deterministic runtime only.** Every test uses `FakeSubagentBackend` / stub runners. No live-DSH child is spawned. The D4/D7 composition mount (RDE-1) is not exercised.
- **No L3 claim.** No bundle satisfies P1–P4. The suite is L2-deterministic at most.
- **No prompt-injection claim.** Subagent content is treated as data.
- **No production change beyond the audit defect closure.** The ONLY production change associated with this suite is the targeted audit event-id allocator fix in `orchestrator/runtime/audit.py` and the consequential nested-flow correlation fix in `observability/ingest.py` (both required to close the dual-audit duplicate-event-id defect; see `0003-observability-correlation.md` §5 and P4I-08). Nothing under `control/`, `state/`, `agents/`, `config/` and nothing else in `orchestrator/` is modified.
- **Dual-audit duplicate event ids — CLOSED.** ProductionRun and ExecutionFlow each create their own `RuntimeAudit` instance writing to the same ledger. Event ids are now allocated from ONE authoritative per-ledger sequence (seeded from the ledger's existing max id, lock-protected), so the ledger has no duplicate ids. P4I-06/P4I-08 assert the closed behavior: all-unique ids, append-only + hash-chain integrity, a single correlated run, a healthy observability report, and — critically — that duplicate-detection validation is NOT weakened (a deliberately injected duplicate is still rejected fail-closed).

---

## 7. Scope check

**In scope**: `tests/phase4_integration/` (8 test files, conftest, helpers, README) + `docs/phase-4/testing/` (this document + companion docs).

**Not in scope** (and unmodified):
- `control/`, `state/`, `audit/`, `agents/`, `config/` — production paths
- DSH core, profile, preset, session policy
- Any existing test file
- `tests/live_dsh/` — requires mounted D4/D7 instances
- `tests/l3_runner/` — requires L3 verifier (BLOCKED)

**Production change (audit defect closure only)**: `orchestrator/runtime/audit.py` (per-ledger event-id allocator) and `observability/ingest.py` (nested-flow correlation within a production run). Both are required to close the confirmed duplicate-event-id defect; both are small, reversible, and fully covered by P4I-06/P4I-08.

---

*Status: SPECIFIED + DEFECT CLOSED. Production change limited to the audit event-id allocator (`orchestrator/runtime/audit.py`) and the consequential nested-flow correlation fix (`observability/ingest.py`). No DSH change. No L3 claim.*
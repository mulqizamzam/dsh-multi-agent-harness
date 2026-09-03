# Phase-4 Integration Test Suite — P4I-01..P4I-08

Cross-module, end-to-end tests over the **REAL Phase-4 production runtime**:
`orchestrator.production` + `orchestrator.runtime` + `control.*` +
`state.helpers` + `audit.helpers` + `observability`.

## Focus areas

| # | File | Focus |
|---|---|---|
| P4I-01 | `test_01_cross_module_production_flow.py` | Full production flow: ProductionRun → ObjectivePlanner → BoundedExecutor → ExecutionFlow → gates → execution gate → state machine → audit → final report. All modules wire correctly. |
| P4I-02 | `test_02_bounded_autonomy.py` | Autonomy bounded by delegation: no delegation → ESCALATED, scope mismatch → DENY, revocation mid-flow → DENY, HIGH requires approval, no bypass. |
| P4I-03 | `test_03_parallel_execution.py` | Independent subtasks (cfo+kai) run concurrently through the flow; safety checks; version preserved; sequential fallback. |
| P4I-04 | `test_04_failure_propagation.py` | Execution failure → recovery → COMPLETE with new cause; persistent failure → escalates; child failure propagates (no partial success); no blind retry. |
| P4I-05 | `test_05_final_report.py` | Structured final report (COMPLETE and BLOCKED); honest on failure; JSON-serializable; report is DATA, never authority. |
| P4I-06 | `test_06_observability_correlation.py` | Observability index over a real ProductionRun ledger: run/task/delegation/failure/evidence/parallel correlation; clean single-run correlation; audit-not-authority. |
| P4I-07 | `test_07_acceptance_criteria.py` | Parameterised mapping of Phase-4 acceptance matrix rows (AEF, VER, PAR, REC, AUD, AUTH, PB) to executable assertions. |
| P4I-08 | `test_08_audit_id_uniqueness.py` | Defect closure: one authoritative per-ledger event-id sequence. ProductionRun + ExecutionFlow same ledger → all-unique ids; sequential + concurrent + restart/reopen; append-only + hash-chain integrity; observability single-run healthy; duplicate-attempt detection preserved (fail-closed NOT weakened). |

## Deterministic runtime only

Every test uses **deterministic in-process child execution** (`FakeSubagentBackend` /
stub runners). No live-DSH evidence is fabricated. No L3 claim is made.

## Running

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/phase4_integration/ -v
```

## Companion docs

See `docs/phase-4/testing/` for the test plan, acceptance criteria coverage, and
observability correlation specification (incl. the audit event-id defect closure).
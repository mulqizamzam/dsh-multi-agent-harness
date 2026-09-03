# Observability Correlation — Test Specification

- **Milestone**: Phase 4 / Session E — Integration Testing
- **Status**: SPECIFIED + DEFECT CLOSED (tested in P4I-06/P4I-08; per-ledger event-id allocator fix in `orchestrator/runtime/audit.py`; nested-flow correlation fix in `observability/ingest.py`)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `tests/phase4_integration/test_06_observability_correlation.py` + `tests/phase4_integration/test_08_audit_id_uniqueness.py` + this document
- **Rule**: the observability layer is read-only; it never writes audit, never modifies the runtime, and never grants authority (AUTH-INV-14). The test suite asserts this.

---

## 1. Purpose

Prove that the audit ledger emitted by a **real ProductionRun** is correlated by the observability layer (`observability.build_index_from_ledger`) into a `RunIndex` with:

- correct run identity (run_id preserved from the production run, not derived)
- correct terminal outcome (COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING)
- task correlation (task_id → TaskRecord with state, version, subtasks, role)
- delegation correlation (delegation_id → DelegationRecord)
- failure correlation (failure_class, cause, source, stage → FailureRecord)
- evidence reference preservation (result_collected evidence tuples)
- parallel batch records (task_ids, owners, held_version)
- fail-closed rejection of malformed / duplicate / missing events
- audit-is-never-authority invariant (AUTH-INV-14)

---

## 2. Correlation flow

```
ProductionRun.run()
  ├── RuntimeAudit.emit() × N    → audit/multi-agent-harness/events.jsonl
  │     (production_run events)
  └── ExecutionFlow.run()
        └── RuntimeAudit.emit() × M  → same ledger
              (flow_started .. flow_finished events)

observability.build_index_from_ledger(base=ws, project="multi-agent-harness")
  ├── read_ledger_events()        → events + ledger_integrity
  │     ├── read_events_strict    → strict JSON parse
  │     ├── verify_append_only    → event-id uniqueness + timestamp monotonicity
  │     └── verify_chain          → hash-chain integrity
  └── build_index(events)         → RunIndex
        └── RunCorrelator.ingest() → RunRecord, TaskRecord, DelegationRecord,
                                     FailureRecord, parallel_batches, evidence_refs
```

## 3. Correlation fields

| Field | Source | Fail-closed rule |
|---|---|---|
| `run_id` | `production_run.task_id` (verbatim) | Never derived from prose |
| `run_id_derived` | `False` when `production_run.task_id` used | `True` only when no explicit id |
| `outcome` | `production_run` close→COMPLETE, stop→BLOCKED; `flow_finished` result | Never guessed |
| `task_id` → `state` | `state_transition` new_state | Absent → empty |
| `task_id` → `version` | `state_transition` version | Absent → 0 |
| `delegation_id` | `authority_source` field on gate events | Absent → empty |
| `failure_class` | `subtask_failed` / `execution_denial` / `recovery` failure_class | "unknown" default |
| `evidence` | `result_collected` evidence tuple | Preserved as-is |
| `parallel_batch` | `parallel_batch` event fields (task_ids, owners, held_version) | Rejected if missing required fields |

## 4. Fail-closed rules (asserted in P4I-06)

| Rule | Assertion |
|---|---|
| DUPLICATE_EVENT | Duplicate event_id → rejected; never double-ingested |
| MISSING_TERMINAL | Run without terminal → problem recorded; outcome not guessed |
| MISSING_START | Event before any start → rejected if consequential |
| MALFORMED_CORRELATION | Missing required correlation field → rejected if consequential |
| ORDERING_VIOLATION | Out-of-order timestamp → problem recorded |
| WRONG_RUN_ASSOCIATION | Task/delegation appearing in two runs → problem recorded |
| PROVENANCE_MISMATCH | Role in subtask id ≠ role in event → problem recorded |
| AUDIT_AS_AUTHORITY | Event claiming "APPROVED" → problem recorded (never a grant) |

## 5. Dual-audit duplicate event-id defect — CLOSED

**Defect (root cause)**: The `ProductionRun` creates its own `RuntimeAudit` instance (for `production_run` lifecycle events), and the `ExecutionFlow` creates its own `RuntimeAudit` instance (for flow events). Both write to the same ledger file (`audit/<project>/events.jsonl`) and both started their event-id counter at `event-000001`. This produced **duplicate event ids** in the ledger.

**Fix (smallest safe production change)**: `orchestrator/runtime/audit.py` now allocates event ids from **one authoritative per-ledger sequence** — a module-level, per-ledger (absolute-path-keyed) allocator that is:
- shared by every `RuntimeAudit` instance writing to the same ledger (no duplicate event_id);
- seeded from the ledger's existing max `event-<n>` id on first use (reopen/restart safe);
- advanced under a per-ledger reentrant lock held across allocation AND append (concurrent writers never observe the same id, and file order == allocation order, preserving append-only monotonicity);
- API-compatible: `RuntimeAudit.__init__/emit/emit_dict/log_path/read` unchanged; the audit schema and hash-chain integrity are untouched; audit remains DATA, never authority.

The `RuntimeAudit.emit` id allocation is unchanged in format (`event-<seq:06d>`) and in schema shape; only the counter that produces `seq` is now ledger-wide instead of instance-local.

**Consequential observability fix (non-weakening)**: with duplicate ids gone, the `RunCorrelator` no longer has duplicate rejection to mask the fact that a `production_run` **wraps** the flow lifecycle. A nested `flow_started`..`flow_finished` emitted by the wrapped `ExecutionFlow` must stay inside the owning production run — it is NOT a second run. `observability/ingest.py` now treats a nested `flow_started` / `flow_finished` as mid-run events when the open run was opened by a `production_run`. All fail-closed detection is unchanged (duplicate ids, missing terminal, ordering violations, wrong-run association, provenance mismatch, audit-as-authority are still rejected/flagged — P4I-08 re-asserts the duplicate-attempt detection).

**Result (verified)**: a real `ProductionRun` ledger now has all-unique event ids, passes `verify_append_only` and `verify_chain`, correlates to a SINGLE run with the preserved production `run_id`, produces zero rejected events, zero correlation problems, and a healthy observability report. See P4I-06 and P4I-08.

## 6. Test assertions per run type

### COMPLETE run (P4I-06a)

```
idx.run_order length == 1
run.outcome == COMPLETE
run.run_id == state.run_id (from ProductionState)
run.run_id_derived is False
"task-1" in run.tasks
run.tasks["task-1"].state == "COMPLETE"
run.tasks["task-1"].version > 0
"delegation-prod-001" in run.delegations
"artifact:cto" in run.evidence_refs  (or similar)
run.problems == []
idx.rejected == []                    (no duplicate ids after the fix)
idx.ledger_integrity["audit_is_authority_source"] is False
idx.ledger_integrity["append_only_ok"] is True
health_report().healthy == True
metrics totals completed_runs == 1
```

### BLOCKED run (P4I-06b)

```
run.outcome == BLOCKED
len(run.failures) >= 1
metrics denials authority_denials >= 1
```

### Parallel run (P4I-06c)

```
len(run.parallel_batches) >= 1
set(run.parallel_batches[0]["owners"]) == {"cfo", "kai"}
metrics parallelism parallel_batches >= 1
```

### Clean synthetic stream (P4I-06d)

```
health_report().healthy == True
health_report().rejected_events == 0
```

---

## 7. Metrics

| Metric | Source | Assertion |
|---|---|---|
| `totals.total_runs` | RunIndex run_order | ≥ 1 |
| `totals.completed_runs` | outcome == COMPLETE | 1 for COMPLETE run |
| `totals.blocked_runs` | outcome == BLOCKED | 1 for blocked run |
| `denials.authority_denials` | `execution_denial` events | ≥ 1 for blocked run |
| `failures.child_failures` | `subtask_failed` events | ≥ 1 for failed run |
| `parallelism.parallel_batches` | RunRecord.parallel_batches | ≥ 1 for parallel run |
| `parallelism.max_parallel_batch_size` | max batch size | = number of roles |
| `recovery.retry_count` | RunRecord.retry_count | ≥ 1 for recovery run |
| `integrity.rejected_events` | len(index.rejected) | 0 for clean ledgers after the fix |
| `integrity.runs_with_problems` | runs with CorrelationProblem | 0 for clean runs |

---

*Status: SPECIFIED + DEFECT CLOSED. Production change: per-ledger event-id allocator (`orchestrator/runtime/audit.py`) + nested-flow correlation (`observability/ingest.py`). No L3 claim.*
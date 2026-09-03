# Production Operations — Observability Layer

- **Milestone**: Phase 4 / Session D — PRODUCTION OPERATIONS + OBSERVABILITY
- **Status**: IMPLEMENTED (package + docs + tests; no control/orchestrator/DSH
  change; no L3 claim)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `observability/`, `docs/operations/`, `tests/observability/` only.
- **Rule**: reuse the existing audit primitives; never create a second audit
  implementation; audit records never grant authority (AUTH-INV-14).

---

## 1. Purpose

Track, correlate, and expose the minimum operational visibility for bounded
autonomous runs: run id, task id, parent task, delegation id, actor, role,
agent/tool identity, gate decisions, execution attempt, observed outcome,
verification result, recovery state, failure class, retry count, state
version, provenance, timing/latency, and final status — reconstructed from the
EXISTING audit ledger, without reading model prose.

The observability layer is a **read-side projection**: it never writes audit,
never modifies the runtime, and never grants authority. It answers:

- run lookup by `run_id`
- task lookup by `task_id`
- delegation lookup by `delegation_id`
- failure lookup
- timeline reconstruction
- evidence reference lookup
- health/sanity report

---

## 2. Layering (reuse, no duplication)

| Layer | Location | Role |
|---|---|---|
| Audit ledger (existing) | `audit/<project>/events.jsonl` | Append-only source of truth; written only by `control.execution_gate.audit_append` via `RuntimeAudit` |
| Audit helpers (existing) | `audit/helpers/append_log.py`, `audit/helpers/integrity.py` | Strict reads, append-only verification, hash-chain verification — reused read-only |
| Observability (new) | `observability/` | Correlates ledger events into `RunIndex`, computes metrics, answers queries |
| Operations docs (new) | `docs/operations/` | This runbook |
| Tests (new) | `tests/observability/` | Lifecycle, fail-closed, queries, metrics, health |

The observability package does NOT write the ledger; it reads it with
`read_events_strict` and verifies it with `verify_append_only` / `verify_chain`
(the existing integrity primitives).

---

## 3. Event lifecycle model

The brief's lifecycle is mapped onto the runtime's existing audit event
classes:

| Lifecycle stage | Audit event classes |
|---|---|
| `RUN_STARTED` | `flow_started`, `production_run` (action=run) |
| `TASK_CREATED` | `intake_recorded`, `production_run` (plan/execute/report) |
| `ROUTING` | `routing_selected` |
| `DELEGATION` | `delegation_issued` |
| `SUBTASK_EXECUTION` | `subtasks_executed`, `parallel_batch`, `parallel_refused`, `subtask_failed` |
| `COLLECTION` | `result_collected` |
| `GATES` | `gate_risk`, `gate_evidence`, `gate_conflict`, `gate_review`, `gate_authority`, `gate_verification`, `badsector_review`, `authority_context`, `state_transition` |
| `EXECUTION` | `execution_request_validated`, `authority_recheck`, `execution_attempt`, `execution_denial`, `version_conflict` |
| `VERIFICATION` | `verification_passed`, `verification_denied` |
| `RECOVERY/ESCALATION` | `recovery`, `recovery_state_transition` |
| `RUN_TERMINAL` | `state_complete`, `flow_finished`, `flow_stopped`, `production_run` (close/stop) |

Terminal outcome derivation (`terminal_outcome`):

| Terminal event + result | Outcome |
|---|---|
| `flow_finished` result `complete` / `completed` | `COMPLETE` |
| `flow_stopped` result `blocked` | `BLOCKED` |
| `flow_stopped` result `failed` | `FAILED` |
| `flow_stopped` result `escalated` | `ESCALATED` |
| `flow_finished` result `recovering` | `RECOVERING` |
| unknown/absent | `BLOCKED` (fail-closed) |

---

## 4. Correlation model

Per run, the observability layer correlates:

| Field | Source |
|---|---|
| `run_id` | production `task_id` when present; else deterministic `run-<n>` derived from the start event id, marked `run_id_derived`; caller `run_id_hints` accepted |
| `task_id` | event `task_id` (parent) or `task-<n>:<role>` (subtask) |
| `parent_task` | derived from subtask id (`task-1:cto` → `task-1`) |
| `delegation_id` | event `authority_source` |
| `actor` | event `actor` (default `orchestrator`) |
| `role` | `result_collected` / `subtask_failed` `role` |
| agent/tool identity | `result_collected` provenance (`tool_name`, `persona`, `run_id`) |
| gate decisions | `gate_*` events (`result`, `error`, `detail`) |
| execution attempt | `execution_attempt` events |
| observed outcome | `execution_attempt` extra (`verdict`, observed) |
| verification result | `verification_passed` / `verification_denied` / `gate_verification` |
| recovery state | `recovery` / `recovery_state_transition` |
| failure class | `subtask_failed` / `execution_denial` / `recovery` `failure_class` |
| retry count | count of non-completed `recovery_state_transition` events |
| state version | `state_transition` extra `version` |
| provenance | `DelegationProvenance` stamps carried in `result_collected` |
| timing/latency | wall-clock deltas between stage event timestamps |
| final status | terminal event outcome |

### Evidence-source distinction

- `AGENT-REPORTED` — child-claimed status/findings inside `result_collected`
  (`status`, `findings`, `recommendation`, `confidence`).
- `RUNTIME-OBSERVED` — event ids, timestamps, execution attempts, provenance
  stamps, ledger facts.
- `CONTROL-PLANE-DECISION` — gate decisions, authority re-checks, verification
  verdicts, recovery transitions, state transitions.

`classify_field_source(event, field)` refines per-field classification.

---

## 5. Fail-closed rules

1. **Malformed/missing correlation on consequential events → reject the
   event.** Every event class declares its required correlation fields in
   `observability/vocab.CORRELATION_REQUIREMENTS`. A consequential event
   (`gate_*`, `delegation_issued`, `subtasks_executed`, `subtask_failed`,
   `result_collected`, `execution_*`, `verification_*`, `recovery*`,
   `state_*`, `flow_*`, `production_run`) missing a required field is
   rejected (excluded from the index) and recorded in `index.rejected`.
2. **Never fabricate ids.** An unknown `run_id`/`task_id`/`delegation_id`
   lookup returns `None`/empty; the ingest never invents ids from prose.
3. **Duplicate event id → reject the duplicate** (fail-closed).
4. **Ordering violation → flagged.** A non-decreasing timestamp invariant
   across the stream is enforced; a regression is recorded as an
   `ORDERING_VIOLATION` problem (Runbook 10 territory).
5. **Missing terminal → flagged.** A run that ends without a terminal event is
   recorded with a `MISSING_TERMINAL` problem; its outcome stays unknown
   rather than being guessed.
6. **Wrong association → flagged.** A `task_id` or `delegation_id` that appears
   in a second run is recorded as `WRONG_RUN_ASSOCIATION` /
   `WRONG_DELEGATION_ASSOCIATION`; ids stay attached to their first owner.
7. **Provenance mismatch → flagged.** A subtask event whose `role` disagrees
   with the role encoded in the subtask id is recorded as
   `PROVENANCE_MISMATCH`.
8. **Audit-as-authority → never.** An audit event carrying an authority-shaped
   `result` (e.g. `approved`) is recorded as an `AUDIT_AS_AUTHORITY` anomaly
   (DATA only); `audit_is_authority_source` always returns False.

---

## 6. Metrics

`observability.metrics.compute_metrics(index)` returns:

- **totals**: `total_runs`, `completed_runs`, `blocked_runs`, `failed_runs`,
  `escalated_runs`, `recovering_runs`
- **denials**: `authority_denials`, `gate_denials`, `verification_failures`
- **recovery**: `recovery_count`, `retry_count`
- **failures**: `child_failures`, `runs_with_failure`
- **parallelism**: `parallel_batches`, `max_parallel_batch_size`,
  `avg_parallel_batch_size`
- **latency**: execution / verification / recovery averages + totals (ms)
- **integrity**: `rejected_events`, `runs_with_problems`

---

## 7. Operational queries

| Query | Function |
|---|---|
| run lookup by `run_id` | `find_run(index, run_id)` |
| task lookup by `task_id` | `find_task(index, task_id)` |
| delegation lookup | `find_delegation(index, delegation_id)` |
| failure lookup | `find_failures(index, run_id=…, failure_class=…)` |
| timeline reconstruction | `reconstruct_timeline(index, run_id)` |
| evidence reference lookup | `find_evidence_refs(index, run_id=…, task_id=…)` |
| health/sanity report | `health_report(index)` |
| outcome rollup | `run_outcome_counts(index)` |

### CLI example (read-only)

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
import observability as obs
idx = obs.build_index_from_ledger(log_path="audit/multi-agent-harness/events.jsonl")
print(obs.health_report(idx))
for rid in idx.run_order:
    r = idx.runs[rid]
    print(rid, r.outcome, len(r.events), "events")
print(obs.compute_metrics(idx)["totals"])
PY
```

---

## 8. Health/sanity report

`health_report(index)` aggregates:

- `ledger_integrity` — strict read, append-only, chain verification results
  (reusing the existing audit helpers)
- `rejected_events` — fail-closed rejections
- `problems` — per-run anomalies (missing terminal, ordering, wrong
  association, provenance mismatch, audit-as-authority)
- `healthy` — True only when no rejection/problem exists and the strict read
  passed

---

## 9. Test coverage

`tests/observability/` covers:

- complete / failed / blocked / escalated / recovery run timelines
- duplicate event, missing event, malformed correlation
- wrong task/run and delegation/run association
- audit-as-authority attempt
- ordering violation
- provenance mismatch
- parallel batch correlation
- metrics, queries, health, and ledger-based ingest (reuse of audit helpers)

---

## 10. Scope check

**In scope (added):**
- `observability/` — package (vocab, model, ingest, metrics, queries)
- `docs/operations/` — this runbook
- `tests/observability/` — test suite

**Not modified:**
- `control/*.py`, `orchestrator/runtime/*.py`, `orchestrator/dsh/*.py`,
  `orchestrator/execution/*.py`, `orchestrator/production/*.py`
- agents / config / toolFilters, DSH, profiles/presets, session policy
- no new tools enabled (no web_fetch, no Agent Teams, no out-of-process
  backends)
- no new authority; no L3 claim

---

*Status: IMPLEMENTED (Session D). Read-side observability over the existing
audit ledger. No control-plane, runtime, DSH, or policy change. No L3 claim.*

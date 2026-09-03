# observability — Production operations + observability layer
#
# Phase 4 / Session D. Read-side observability over the EXISTING audit ledger.
#
# Scope (write-only per session brief): this package, docs/operations/, and
# tests/observability/. It does NOT modify control/*, orchestrator/*,
# agents/config/toolFilters, DSH, profiles/presets, session policy, or enable
# new tools. It does NOT create a second audit implementation — it reuses the
# existing audit helpers (append_log.read_events_strict / verify_append_only,
# integrity.verify_chain) read-only.
#
# Invariants:
#   - audit records NEVER grant authority (AUTH-INV-14); `audit_is_authority_source`
#     is always False.
#   - event ordering and correlation ids are preserved; missing/duplicate
#     lifecycle events are detected.
#   - AGENT-REPORTED / RUNTIME-OBSERVED / CONTROL-PLANE-DECISION sources are
#     distinguished.
#   - enough data is exposed to reconstruct a run without reading model prose.
#   - FAIL-CLOSED: malformed/missing correlation on consequential events
#     rejects the event; ids are never fabricated.
#
# Public API
#   build_index(events, ...)                 -> RunIndex (from event list)
#   build_index_from_ledger(base, project)   -> RunIndex (from the audit ledger)
#   compute_metrics(index)                   -> metric rollups
#   find_run / find_task / find_delegation / find_failures / find_evidence_refs
#   reconstruct_timeline / health_report     -> operational queries

from __future__ import annotations

from .vocab import (
    RUN_STARTED, TASK_CREATED, ROUTING, DELEGATION, SUBTASK_EXECUTION,
    COLLECTION, GATES, EXECUTION, VERIFICATION, RECOVERY_ESCALATION,
    RUN_TERMINAL, LIFECYCLE_STAGES,
    AGENT_REPORTED, RUNTIME_OBSERVED, CONTROL_PLANE_DECISION,
    INDEPENDENTLY_VERIFIED,
    OUTCOME_COMPLETE, OUTCOME_BLOCKED, OUTCOME_FAILED, OUTCOME_ESCALATED,
    OUTCOME_RECOVERING,
)
from .model import (
    ObservedEvent, TaskRecord, DelegationRecord, FailureRecord,
    CorrelationProblem, RunRecord, RunIndex,
)
from .ingest import (
    RunCorrelator, build_index, build_index_from_ledger,
    read_ledger_events, validate_event_correlation,
)
from .metrics import compute_metrics
from .queries import (
    find_run, find_task, find_tasks_by_run, find_delegation, find_failures,
    find_evidence_refs, reconstruct_timeline, health_report,
    run_outcome_counts,
)

__all__ = [
    "RUN_STARTED", "TASK_CREATED", "ROUTING", "DELEGATION",
    "SUBTASK_EXECUTION", "COLLECTION", "GATES", "EXECUTION", "VERIFICATION",
    "RECOVERY_ESCALATION", "RUN_TERMINAL", "LIFECYCLE_STAGES",
    "AGENT_REPORTED", "RUNTIME_OBSERVED", "CONTROL_PLANE_DECISION",
    "INDEPENDENTLY_VERIFIED",
    "ObservedEvent", "TaskRecord", "DelegationRecord", "FailureRecord",
    "CorrelationProblem", "RunRecord", "RunIndex",
    "RunCorrelator", "build_index", "build_index_from_ledger",
    "read_ledger_events", "validate_event_correlation",
    "compute_metrics",
    "find_run", "find_task", "find_tasks_by_run", "find_delegation",
    "find_failures", "find_evidence_refs", "reconstruct_timeline",
    "health_report", "run_outcome_counts",
]

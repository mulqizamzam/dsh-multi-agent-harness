# observability.model — Correlation records (DATA, never authority)
#
# Phase 4 / Session D — Production operations + observability.
#
# The records produced by the observability ingest. Every record is DERIVED
# DATA reconstructed from the existing audit ledger — it never grants
# authority (AUTH-INV-14), never adds new audit events, and never fabricates
# correlation ids. A field whose value could not be established from the
# ledger is left empty/None — the ingest never guesses.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ObservedEvent:
    """One audit event accepted into the observability index (read-only).

    ``event`` is the original ledger event dict (the authoritative record).
    ``stage`` / ``source`` are the observability classifications. Nothing here
    is a grant.
    """
    event_id: str
    event_class: str
    timestamp: str
    stage: str
    source: str
    task_id: str = ""
    run_id: str = ""
    delegation_id: str = ""
    outcome: str = ""
    failure_class: str = ""
    result: str = ""
    detail: dict = field(default_factory=dict)
    event: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_class": self.event_class,
            "timestamp": self.timestamp,
            "stage": self.stage,
            "source": self.source,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "delegation_id": self.delegation_id,
            "outcome": self.outcome,
            "failure_class": self.failure_class,
            "result": self.result,
            "detail": dict(self.detail),
        }


@dataclass
class TaskRecord:
    """One task's observability record within a run."""
    task_id: str
    run_id: str = ""
    parent_task: str = ""
    role: str = ""
    delegation_id: str = ""
    state: str = ""
    version: int = 0
    events: list = field(default_factory=list)        # ObservedEvent ids
    subtasks: list = field(default_factory=list)      # child task ids

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "parent_task": self.parent_task,
            "role": self.role,
            "delegation_id": self.delegation_id,
            "state": self.state,
            "version": self.version,
            "events": list(self.events),
            "subtasks": list(self.subtasks),
        }


@dataclass
class DelegationRecord:
    """One delegation's observability record (authority_source correlation)."""
    delegation_id: str
    run_id: str = ""
    task_id: str = ""
    events: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "delegation_id": self.delegation_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "events": list(self.events),
        }


@dataclass
class FailureRecord:
    """One observed failure (DATA — a record, never a grant)."""
    failure_id: str = ""
    run_id: str = ""
    task_id: str = ""
    failure_class: str = ""
    cause: str = ""
    source: str = ""                 # AGENT-REPORTED / RUNTIME-OBSERVED / ...
    stage: str = ""
    event_id: str = ""

    def to_dict(self) -> dict:
        return {
            "failure_id": self.failure_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "failure_class": self.failure_class,
            "cause": self.cause,
            "source": self.source,
            "stage": self.stage,
            "event_id": self.event_id,
        }


@dataclass
class CorrelationProblem:
    """A fail-closed correlation rejection or anomaly.

    kind: MISSING_EVENT | DUPLICATE_EVENT | MALFORMED_CORRELATION |
          WRONG_RUN_ASSOCIATION | WRONG_DELEGATION_ASSOCIATION |
          ORDERING_VIOLATION | MISSING_TERMINAL | DUPLICATE_TERMINAL |
          PROVENANCE_MISMATCH | AUDIT_AS_AUTHORITY
    """
    kind: str
    message: str
    event_id: str = ""
    event_class: str = ""
    run_id: str = ""
    rejected: bool = False            # True when the event was excluded

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "message": self.message,
            "event_id": self.event_id,
            "event_class": self.event_class,
            "run_id": self.run_id,
            "rejected": self.rejected,
        }


@dataclass
class RunRecord:
    """One bounded run reconstructed from the audit ledger.

    ``run_id`` is the run identity. When the runtime emitted an explicit
    production run id (production_run task_id) or the caller supplied a
    run_id hint, it is preserved verbatim; otherwise it is derived
    deterministically from the run's start event id and marked
    ``run_id_derived``. Never fabricated from prose.
    """
    run_id: str
    objective: str = ""
    project: str = ""
    started_at: str = ""
    finished_at: str = ""
    outcome: str = ""                 # COMPLETE/BLOCKED/FAILED/ESCALATED/RECOVERING
    phase: str = ""
    final_state: str = ""
    risk: str = ""
    run_id_derived: bool = False
    start_event_id: str = ""
    terminal_event_id: str = ""
    events: list = field(default_factory=list)        # ObservedEvent (ordered)
    tasks: dict = field(default_factory=dict)         # task_id -> TaskRecord
    delegations: dict = field(default_factory=dict)   # delegation_id -> DelegationRecord
    failures: list = field(default_factory=list)      # FailureRecord
    problems: list = field(default_factory=list)      # CorrelationProblem
    evidence_refs: list = field(default_factory=list) # evidence references
    latency: dict = field(default_factory=dict)       # stage latency (ms)
    retry_count: int = 0
    parallel_batches: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "project": self.project,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "outcome": self.outcome,
            "phase": self.phase,
            "final_state": self.final_state,
            "risk": self.risk,
            "run_id_derived": self.run_id_derived,
            "start_event_id": self.start_event_id,
            "terminal_event_id": self.terminal_event_id,
            "events": [e.to_dict() for e in self.events],
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "delegations": {k: v.to_dict() for k, v in self.delegations.items()},
            "failures": [f.to_dict() for f in self.failures],
            "problems": [p.to_dict() for p in self.problems],
            "evidence_refs": list(self.evidence_refs),
            "latency": dict(self.latency),
            "retry_count": self.retry_count,
            "parallel_batches": list(self.parallel_batches),
        }


@dataclass
class RunIndex:
    """The complete observability index over a ledger slice.

    ``runs`` is ordered by start timestamp. ``rejected`` lists events the
    ingest refused fail-closed. ``ledger_integrity`` records the result of the
    existing audit-integrity checks (append-only + chain) performed at ingest.
    """
    project: str = ""
    runs: dict = field(default_factory=dict)          # run_id -> RunRecord
    run_order: list = field(default_factory=list)     # run_ids in start order
    rejected: list = field(default_factory=list)      # CorrelationProblem
    ledger_integrity: dict = field(default_factory=dict)
    built_at: str = ""

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "runs": {k: v.to_dict() for k, v in self.runs.items()},
            "run_order": list(self.run_order),
            "rejected": [p.to_dict() for p in self.rejected],
            "ledger_integrity": dict(self.ledger_integrity),
            "built_at": self.built_at,
        }


__all__ = [
    "ObservedEvent", "TaskRecord", "DelegationRecord", "FailureRecord",
    "CorrelationProblem", "RunRecord", "RunIndex",
]

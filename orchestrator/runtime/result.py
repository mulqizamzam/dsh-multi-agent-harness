# orchestrator.runtime.result — Deterministic flow result object (Phase 3)
#
# `FlowResult` is the single, deterministic, JSON-serializable outcome of an
# ExecutionFlow run. It records the full phase chain, every gate decision, the
# collected results, the synthesis, verification/recovery state, audit event
# ids, and the terminal disposition (COMPLETE / BLOCKED / FAILED / ESCALATED /
# RECOVERING). The result is DATA — it never grants authority (AUTH-INV-14).

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, asdict

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@dataclass(frozen=True)
class GateRecord:
    """One gate decision in the flow (audit-ready)."""
    phase: str
    gate: str
    decision: str           # ALLOW | DENY | ESCALATE
    reason: str = ""
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase, "gate": self.gate,
            "decision": self.decision, "reason": self.reason,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class StepRecord:
    """One non-gate phase step (data, never authority)."""
    phase: str
    note: str = ""

    def to_dict(self) -> dict:
        return {"phase": self.phase, "note": self.note}


# Terminal dispositions of a flow run.
COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"
FAILED = "FAILED"
ESCALATED = "ESCALATED"
RECOVERING = "RECOVERING"
OUTCOMES = (COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING)


@dataclass
class FlowResult:
    """Deterministic result of one ExecutionFlow run.

    Deterministic: `to_dict()` produces a stable, JSON-serializable document
    (tuples -> lists, stable field order) so two runs over the same inputs and
    gates produce comparable results.
    """
    flow_id: str = ""
    objective: str = ""
    project: str = "multi-agent-harness"
    task_id: str = ""
    outcome: str = BLOCKED           # COMPLETE / BLOCKED / FAILED / ESCALATED / RECOVERING
    phase: str = "intake"            # where the flow stopped / ended
    final_state: str = "DRAFT"       # final StateMachine state
    version: int = 1                 # final project state version
    risk: str = "LOW"
    selected: tuple = field(default_factory=tuple)
    tasks: tuple = field(default_factory=tuple)          # Task dicts
    delegations: tuple = field(default_factory=tuple)    # delegation dicts
    results: tuple = field(default_factory=tuple)        # CollectedResult dicts
    parallel: dict = field(default_factory=dict)         # parallel-safety record
    synthesis: dict = field(default_factory=dict)
    gates: tuple = field(default_factory=tuple)          # GateRecord dicts
    steps: tuple = field(default_factory=tuple)          # StepRecord dicts
    verification: dict = field(default_factory=dict)
    recovery: dict = field(default_factory=dict)
    audit_ids: tuple = field(default_factory=tuple)
    files_written: tuple = field(default_factory=tuple)
    errors: tuple = field(default_factory=tuple)
    started_at: str = ""
    finished_at: str = ""

    # -- helpers ------------------------------------------------------------
    def record_step(self, phase: str, note: str = "") -> None:
        self.steps = self.steps + (StepRecord(phase, note).to_dict(),)

    def record_gate(self, phase: str, gate: str, decision: str,
                    reason: str = "", detail: dict | None = None) -> None:
        rec = GateRecord(phase, gate, decision, reason, detail or {})
        self.gates = self.gates + (rec.to_dict(),)

    def add_error(self, error: str) -> None:
        self.errors = self.errors + (str(error),)

    def note_file(self, path: str) -> None:
        self.files_written = self.files_written + (str(path),)

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "objective": self.objective,
            "project": self.project,
            "task_id": self.task_id,
            "outcome": self.outcome,
            "phase": self.phase,
            "final_state": self.final_state,
            "version": self.version,
            "risk": self.risk,
            "selected": list(self.selected),
            "tasks": list(self.tasks),
            "delegations": list(self.delegations),
            "results": list(self.results),
            "parallel": dict(self.parallel),
            "synthesis": dict(self.synthesis),
            "gates": list(self.gates),
            "steps": list(self.steps),
            "verification": dict(self.verification),
            "recovery": dict(self.recovery),
            "audit_ids": list(self.audit_ids),
            "files_written": list(self.files_written),
            "errors": list(self.errors),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


__all__ = [
    "GateRecord", "StepRecord", "FlowResult",
    "COMPLETE", "BLOCKED", "FAILED", "ESCALATED", "RECOVERING", "OUTCOMES",
]

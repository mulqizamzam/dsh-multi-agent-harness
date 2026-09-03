# orchestrator.production.lifecycle — Production run lifecycle coordinator
#
# Phase 4 / Session A. Coordinates the bounded production run:
#
#   INTAKE → PLANNING → EXECUTION → REPORT → CLOSE
#
# Each transition is recorded in the audit ledger. The lifecycle does NOT add
# new authority — it delegates to the existing Phase-3 runtime (ExecutionFlow)
# and the BoundedExecutor. It never creates a delegation from text, never
# auto-approves a HIGH action, and never treats state/audit as authority.
#
# The ProductionState is a DATA record (never authority).

from __future__ import annotations

import os
import sys
import uuid

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from orchestrator.foundation.contracts import (
    TaskIntake, Task, Delegation, ORCHESTRATOR,
)
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, FlowResult, MemoryDelegationProvider,
    DelegationProvider, RuntimeStore, RuntimeAudit,
    COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING,
)

from .planner import ObjectivePlanner, ProductionPlan
from .executor import BoundedExecutor
from .report import ReportGenerator, FinalReport
from .exceptions import (
    ProductionError, ProductionStopped, ProductionDenied,
    ProductionEscalated, NoValidDelegation, ObjectiveNotActionable,
    PlanRejected, ReportGenerationFailed,
)

# Production lifecycle phases (distinct from the TaskLifecycle state machine).
PRODUCTION_PHASES = (
    "intake", "planning", "execution", "report", "close",
)
TERMINAL_PHASES = {"complete", "stopped", "failed"}


@dataclass
class ProductionState:
    """Record of one production run's lifecycle (DATA, never authority).

    Fields
    ------
    run_id:        unique id for this production run.
    phase:         current phase (intake|planning|execution|report|close).
    outcome:       complete|stopped|failed.
    objective:     original objective text.
    plan:          the ProductionPlan dict (or None before planning).
    flow_result:   the FlowResult dict (or None before execution).
    report:        the FinalReport dict (or None before report generation).
    errors:        accumulated errors.
    audit_ids:     audit event ids from this lifecycle.
    """
    run_id: str = ""
    phase: str = "intake"
    outcome: str = "stopped"
    objective: str = ""
    plan: dict | None = None
    flow_result: dict | None = None
    report: dict | None = None
    errors: tuple[str, ...] = ()
    audit_ids: tuple[str, ...] = ()

    def add_error(self, error: str) -> None:
        self.errors = self.errors + (str(error),)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "outcome": self.outcome,
            "objective": self.objective,
            "plan": self.plan,
            "flow_result": self.flow_result,
            "report": self.report,
            "errors": list(self.errors),
            "audit_ids": list(self.audit_ids),
        }


class ProductionRun:
    """Bounded-autonomy production run lifecycle coordinator.

    Parameters
    ----------
    project:
        Project id (default "multi-agent-harness").
    base:
        Workspace base for state/audit/execution gate.
    planner:
        ObjectivePlanner instance (default fresh).
    executor:
        BoundedExecutor instance (default fresh).
    report_generator:
        ReportGenerator instance (default fresh).
    live_dispatch:
        Explicit REAL DSH bridge dispatch (G1). When injected, the
        ExecutionFlow uses the live ``RealDSHBackend``; if the D4/D7 bridge
        marker is absent the flow fails closed (``BridgeNotAvailable`` ->
        BLOCKED) — it NEVER silently runs the fake backend for a requested
        REAL run. Default None: deterministic ``FakeSubagentBackend`` (local
        mode). Threaded through to ``BoundedExecutor`` and ``ExecutionFlow``.
    audit:
        RuntimeAudit instance (default fresh).
    now:
        Optional clock override (tests).
    """

    def __init__(self, *, project: str = "multi-agent-harness",
                 base: str | None = None,
                 planner: ObjectivePlanner | None = None,
                 executor: BoundedExecutor | None = None,
                 report_generator: ReportGenerator | None = None,
                 live_dispatch=None,
                 audit: RuntimeAudit | None = None,
                 now=None):
        self.project = project
        self.base = base
        self._planner = planner or ObjectivePlanner(project=project,
                                                     environment="dev",
                                                     now=now)
        self._executor = executor or BoundedExecutor(project=project,
                                                     base=base,
                                                     live_dispatch=live_dispatch,
                                                     now=now)
        self._report_gen = report_generator or ReportGenerator()
        self._live_dispatch = live_dispatch
        self._audit = audit
        self._now = now
        self._state: ProductionState | None = None
        self._seq = 0

    # -- properties ----------------------------------------------------------

    @property
    def state(self) -> ProductionState | None:
        return self._state

    # -- main entry ----------------------------------------------------------

    def run(self, *, objective: str = "", scope=(),
            constraints=(), expected_outcome: str = "",
            delegation: Delegation | None = None,
            provider: DelegationProvider | None = None,
            pre_execute: Callable | None = None,
            required_authority_context: str = "",
            declared_risk: str = "LOW",
            approval_reference: str = "",
            review: dict | None = None,
            subtask_runner: Callable | None = None,
            action_executor: Callable | None = None,
            max_workers: int = 4,
            parallel_subtasks: bool = True,
            live_dispatch=None) -> ProductionState:
        """Run the full bounded production lifecycle.

        Steps:
          1. INTAKE — record the objective
          2. PLANNING — objective → actionable ProductionPlan
          3. EXECUTION — bounded flow through ExecutionFlow
          4. REPORT — structured final report
          5. CLOSE — terminal audit

        Returns a ProductionState with the full result.

        Raises
        ------
        ProductionDenied / ProductionEscalated / ProductionStopped
            Any gate denial or escalation stops the run.
        """
        self._seq += 1
        run_id = f"prod-{uuid.uuid4().hex[:8]}"
        audit = self._get_audit()

        # --- INTAKE ---
        state = ProductionState(
            run_id=run_id, phase="intake", objective=objective)
        self._state = state
        eid = audit.emit("production_run", action="run", target=run_id,
                         task_id=run_id, result="started",
                         extra={"objective": objective, "phase": "intake"})
        state.audit_ids = state.audit_ids + (eid,)

        try:
            # --- PLANNING ---
            state.phase = "planning"
            plan = self._planner.plan(
                objective=objective, scope=scope,
                constraints=constraints,
                expected_outcome=expected_outcome,
                required_authority_context=required_authority_context,
                declared_risk=declared_risk,
                approval_reference=approval_reference)
            state.plan = plan.to_dict()
            state.objective = plan.objective
            eid = audit.emit("production_run", action="plan", target=run_id,
                             task_id=run_id, result="planned",
                             extra={"plan": plan.to_dict()})
            state.audit_ids = state.audit_ids + (eid,)

            # --- EXECUTION ---
            state.phase = "execution"
            if delegation is None:
                # No delegation provided; the flow will escalate at the
                # UNDERSTAND phase (no authority context).
                raise NoValidDelegation(
                    "execution",
                    "no delegation provided — every production run requires "
                    "a structured Delegation (AUTH-INV-05)", "ESCALATE")

            # Build a fresh executor when per-run overrides are given.
            if subtask_runner is not None or action_executor is not None \
                    or live_dispatch is not None:
                exec_ = BoundedExecutor(
                    project=self.project, base=self.base,
                    subtask_runner=subtask_runner,
                    executor=action_executor, now=self._now,
                    live_dispatch=(live_dispatch
                                   if live_dispatch is not None
                                   else self._live_dispatch))
            else:
                exec_ = self._executor

            # Delegate to the bounded executor.
            flow_result = exec_.execute(
                plan, delegation=delegation, provider=provider,
                pre_execute=pre_execute,
                review=review,
                approval_reference=approval_reference,
                declared_risk=declared_risk,
                max_workers=max_workers,
                parallel_subtasks=parallel_subtasks,
                live_dispatch=(live_dispatch
                               if live_dispatch is not None
                               else self._live_dispatch))
            state.flow_result = flow_result.to_dict()
            eid = audit.emit("production_run", action="execute", target=run_id,
                             task_id=run_id, result=flow_result.outcome.lower(),
                             extra={"outcome": flow_result.outcome,
                                    "phase": flow_result.phase})
            state.audit_ids = state.audit_ids + (eid,)

            if flow_result.outcome != COMPLETE:
                raise ProductionStopped(
                    flow_result.phase,
                    f"flow did not complete: {flow_result.outcome}",
                    flow_result.outcome, flow_result.to_dict())

            # --- REPORT ---
            state.phase = "report"
            report = self._report_gen.generate(flow_result, audit=audit)
            state.report = report.to_dict()
            eid = audit.emit("production_run", action="report", target=run_id,
                             task_id=run_id, result="generated",
                             extra={"report_summary": report.summary()})
            state.audit_ids = state.audit_ids + (eid,)

            # --- CLOSE ---
            state.phase = "close"
            state.outcome = "complete"
            eid = audit.emit("production_run", action="close", target=run_id,
                             task_id=run_id, result="completed",
                             extra={"outcome": "complete"})
            state.audit_ids = state.audit_ids + (eid,)
            return state

        except (ProductionDenied, ProductionEscalated, ProductionStopped,
                NoValidDelegation, ObjectiveNotActionable, PlanRejected,
                ReportGenerationFailed) as e:
            state.add_error(str(e))
            state.outcome = "stopped"
            if isinstance(e, (ProductionEscalated,)):
                state.outcome = "escalated"
            eid = audit.emit("production_run", action="stop", target=run_id,
                             task_id=run_id, result="error", error=str(e),
                             extra={"phase": state.phase,
                                    "outcome": state.outcome})
            state.audit_ids = state.audit_ids + (eid,)
            raise

        except Exception as e:  # noqa: BLE001 — fail-closed
            state.add_error(f"unexpected error: {e}")
            state.outcome = "failed"
            eid = audit.emit("production_run", action="stop", target=run_id,
                             task_id=run_id, result="error",
                             error=f"unexpected: {e}",
                             extra={"phase": state.phase})
            state.audit_ids = state.audit_ids + (eid,)
            raise ProductionDenied(
                state.phase, f"unexpected execution error: {e}",
                "DENY") from e

    # -- helpers -------------------------------------------------------------

    def _get_audit(self) -> RuntimeAudit:
        if self._audit is None:
            self._audit = RuntimeAudit(base=self.base, project=self.project,
                                       now=self._now)
        return self._audit


__all__ = ["ProductionRun", "ProductionState", "PRODUCTION_PHASES"]
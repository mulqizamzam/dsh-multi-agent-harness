# orchestrator.production — Bounded Production Execution Flow (Phase 4 / Session A)
#
# Wraps the existing Phase-3 runtime (ExecutionFlow, ExecutionEngine,
# DelegationClient, GateRunner, RuntimeStore, RuntimeAudit, TaskLifecycle,
# ParallelExecutor, control.*) with a bounded-autonomy Execution Flow:
#
#   Human gives objective
#   → Orchestrator decomposes
#   → selects minimum agents
#   → delegates within authority
#   → executes allowed actions
#   → verifies
#   → reports
#
# Autonomy is bounded by:
#   delegation scope, risk gate, evidence gate, conflict gate, BadSector review,
#   authority gate, execution gate, verification, recovery, audit.
#
# NO new authority, NO new gates, NO overlapping control — only orchestration
# on top of the validated Phase-3 runtime.
#
# DO NOT:
#   - bypass approval
#   - create authority from model text
#   - treat state/audit as authority
#   - allow specialist subdelegation
#   - auto-approve HIGH actions
#   - allow blind retry
#   - allow recovery privilege expansion
#   - enable financial transaction execution
#   - enable destructive unrestricted automation
#   - enable public publishing
#   - enable web_fetch
#   - modify DSH
#   - modify profiles/presets
#   - alter role tool surfaces

from __future__ import annotations

from .exceptions import (
    ProductionError,
    ProductionStopped,
    ProductionDenied,
    ProductionEscalated,
    NoValidDelegation,
    ObjectiveNotActionable,
    PlanRejected,
    ReportGenerationFailed,
)
from .lifecycle import ProductionRun, ProductionState
from .planner import ObjectivePlanner, ProductionPlan
from .executor import BoundedExecutor
from .report import FinalReport, ReportGenerator

__all__ = [
    "ProductionRun",
    "ProductionState",
    "ObjectivePlanner",
    "ProductionPlan",
    "BoundedExecutor",
    "FinalReport",
    "ReportGenerator",
    "ProductionError",
    "ProductionStopped",
    "ProductionDenied",
    "ProductionEscalated",
    "NoValidDelegation",
    "ObjectiveNotActionable",
    "PlanRejected",
    "ReportGenerationFailed",
]
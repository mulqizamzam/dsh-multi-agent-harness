# orchestrator.organization — bounded organization layer (MVP)
#
# Additive seam over the existing orchestrator: mission packet → wave
# scheduling → typed handoff → evidence ledger → bounded rework →
# ROOT verdict, reusing ParallelExecutor, DelegationClient, Task/TaskResult,
# gates, and RuntimeAudit (no second engine, no authority redesign).

from .packet import (
    MissionTask,
    MissionPacket,
    MissionError,
    prd_status,
    runtime_status,
    PRD_STATUSES,
    EVIDENCE_KINDS,
    REVIEWER_ROLES,
)
from .waves import plan_waves, plan_mission_waves, build_wave_plans
from .handoff import TypedHandoff, build_task_context
from .evidence import EvidenceLedger
from .rework import (
    ReworkLedger,
    ReworkExhausted,
    MAX_REWORK_CYCLES,
    critic_verdict,
    verdict_action,
)
from .root import RootVerdict, build_verdict
from .runner import MissionRunner, MissionOutcome
from .metrics import (
    MissionMetrics,
    ObservedTaskMetrics,
    ObservedRoleMetrics,
    EstimatedCfoData,
    collect_mission_metrics,
    collect_from_runner,
    lineage_root,
    lineage_ids,
)

__all__ = [
    "MissionTask",
    "MissionPacket",
    "MissionError",
    "prd_status",
    "runtime_status",
    "PRD_STATUSES",
    "EVIDENCE_KINDS",
    "REVIEWER_ROLES",
    "plan_waves",
    "plan_mission_waves",
    "build_wave_plans",
    "TypedHandoff",
    "build_task_context",
    "EvidenceLedger",
    "ReworkLedger",
    "ReworkExhausted",
    "MAX_REWORK_CYCLES",
    "critic_verdict",
    "verdict_action",
    "RootVerdict",
    "build_verdict",
    "MissionRunner",
    "MissionOutcome",
    "MissionMetrics",
    "ObservedTaskMetrics",
    "ObservedRoleMetrics",
    "EstimatedCfoData",
    "collect_mission_metrics",
    "collect_from_runner",
    "lineage_root",
    "lineage_ids",
]

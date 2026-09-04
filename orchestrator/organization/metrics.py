# orchestrator.organization.metrics — Mission execution metrics (MVP)
#
# Structured mission metrics collected from a MissionRunner after run().
# Separates OBSERVED (actual execution data) from ESTIMATED (CFO-provided
# resource/cost recommendations).  No token/cost numbers are invented.
#
# Metrics vocabulary:
#   mission_id
#   started_at / completed_at / duration_ms
#   task_count / completed_tasks / blocked_tasks / failed_tasks
#   escalated_tasks / rework_cycles
#   roles_invoked / roles_completed
#   waves / parallel_tasks_peak
#   verification_passed / verification_failed
#   per_role_metrics   (OBSERVED: tasks, statuses, attempts, durations)
#   per_task_metrics   (OBSERVED: status, attempts, wave, duration, rework)
#   cfo_estimates      (ESTIMATED — from CFO handoff, never invented)
#
# OBSERVED/ESTIMATED INVARIANT: OBSERVED and ESTIMATED are never merged into
# one field.  ESTIMATED data is present only when CFO produced a handoff with
# resource/cost recommendations, and every estimated value is a string
# authored by CFO (verbatim from its findings) — never synthesized here.
#
# REWORK LINEAGE: rework packets are synthetic ids "<task_id>#rework-N".
# Counts are aggregated per mission task (the lineage root), so a reworked
# task is counted ONCE: its final status is the base handoff's status (the
# runner promotes a successful rework onto the base handoff), its attempts
# are the max attempt across the lineage, and its duration is the sum of
# every dispatch in the lineage.

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.organization.packet import MissionPacket  # noqa: E402
from orchestrator.organization.handoff import TypedHandoff  # noqa: E402
from orchestrator.organization.root import RootVerdict  # noqa: E402

REWORK_SEP = "#rework-"


def lineage_root(task_id: str) -> str:
    """The mission task id a (possibly rework) task id belongs to."""
    tid = str(task_id)
    while REWORK_SEP in tid:
        tid = tid.split(REWORK_SEP)[0]
    return tid


def lineage_ids(root_id: str, known_ids) -> tuple[str, ...]:
    """All dispatched ids in a task's rework lineage (root first)."""
    prefix = root_id + REWORK_SEP
    return tuple(
        [root_id] + sorted(i for i in known_ids
                           if isinstance(i, str) and i.startswith(prefix))
    )


# ---------------------------------------------------------------------------
# Observed data — never merged with estimated
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservedTaskMetrics:
    """Per-task observed metrics (aggregated over the rework lineage)."""
    task_id: str
    owner: str
    role: str
    status: str  # done | blocked | uncertain
    attempts: int
    wave: int
    duration_ms: float = 0.0
    rework_cycles: int = 0


@dataclass(frozen=True)
class ObservedRoleMetrics:
    """Per-role observed metrics."""
    role: str
    tasks: int
    completed: int
    blocked: int
    failed: int
    total_attempts: int
    rework_cycles_triggered: int
    total_duration_ms: float = 0.0


@dataclass(frozen=True)
class EstimatedCfoData:
    """ESTIMATED data from CFO handoff — NEVER merged with OBSERVED.

    Only populated when CFO produced a handoff with resource/cost
    recommendations.  Every value is verbatim CFO output (its findings /
    summary); no token/cost numbers are invented by this module.
    """
    resource_recommendation: str = ""
    cost_estimate: str = ""
    budget_note: str = ""
    findings: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# MissionMetrics — the single structured metrics container
# ---------------------------------------------------------------------------

@dataclass
class MissionMetrics:
    """Complete structured mission metrics.

    OBSERVED fields: all fields except ``cfo_estimates``.
    ESTIMATED fields: ``cfo_estimates`` only.
    """
    mission_id: str

    # Timing
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0

    # Task counts
    task_count: int = 0
    completed_tasks: int = 0
    blocked_tasks: int = 0
    failed_tasks: int = 0
    escalated_tasks: int = 0
    rework_cycles: int = 0

    # Role counts
    roles_invoked: tuple[str, ...] = ()
    roles_completed: tuple[str, ...] = ()

    # Wave / parallelism
    waves: int = 0
    parallel_tasks_peak: int = 0

    # Verification
    verification_passed: int = 0
    verification_failed: int = 0

    # Per-role detail (OBSERVED)
    per_role_metrics: tuple[ObservedRoleMetrics, ...] = ()

    # Per-task detail (OBSERVED)
    per_task_metrics: tuple[ObservedTaskMetrics, ...] = ()

    # CFO estimates (ESTIMATED — present only when CFO produced a handoff)
    cfo_estimates: EstimatedCfoData | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["roles_invoked"] = list(d["roles_invoked"])
        d["roles_completed"] = list(d["roles_completed"])
        d["per_role_metrics"] = [dict(m) for m in d["per_role_metrics"]]
        d["per_task_metrics"] = [dict(m) for m in d["per_task_metrics"]]
        if d["cfo_estimates"] is not None:
            d["cfo_estimates"] = dict(d["cfo_estimates"])
        d["_data_classification"] = {
            "observed": [
                "mission_id", "started_at", "completed_at", "duration_ms",
                "task_count", "completed_tasks", "blocked_tasks", "failed_tasks",
                "escalated_tasks", "rework_cycles", "roles_invoked",
                "roles_completed", "waves", "parallel_tasks_peak",
                "verification_passed", "verification_failed",
                "per_role_metrics", "per_task_metrics",
            ],
            "estimated": ["cfo_estimates"],
        }
        return d


def _parse_iso(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Metrics collector
# ---------------------------------------------------------------------------

def collect_mission_metrics(
    mission: MissionPacket,
    handoffs: dict[str, TypedHandoff],
    reviews: list[dict],
    rework_orders: tuple[dict, ...] | list[dict],
    escalations: tuple[str, ...] | list[str],
    waves_executed: int,
    verdict: RootVerdict,
    *,
    started_at: str | None = None,
    completed_at: str | None = None,
    per_task_wave: dict[str, int] | None = None,
    per_task_attempts: dict[str, int] | None = None,
    per_task_durations: dict[str, float] | None = None,
    parallel_peak: int | None = None,
) -> MissionMetrics:
    """Collect structured metrics from a completed mission run.

    Parameters
    ----------
    mission:
        The mission packet that was executed.
    handoffs:
        Task_id -> TypedHandoff map from the runner (may include rework ids;
        counts aggregate per lineage root).
    reviews:
        Review records from the runner.
    rework_orders:
        ReworkLedger history.
    escalations:
        Escalation list from the runner.
    waves_executed:
        Number of waves executed (observed).
    verdict:
        RootVerdict from the runner.
    started_at / completed_at:
        Optional ISO times; fall back to handoff timestamps / verdict time.
    per_task_wave:
        Optional task_id -> wave index observed at dispatch.
    per_task_attempts:
        Optional task_id -> attempts (any id in a lineage accepted; the max
        across the lineage is the task's total attempts).
    per_task_durations:
        Optional task_id -> observed dispatch duration in ms; summed across
        the lineage for per-task totals.
    parallel_peak:
        Optional observed peak batch size (tasks dispatched in one wave);
        overrides wave-plan-derived values.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # -- Timing ----------------------------------------------------------
    if started_at is None:
        times = [ho.produced_at for ho in handoffs.values() if ho.produced_at]
        started_at = min(times) if times else now_iso
    if completed_at is None:
        completed_at = verdict.produced_at or now_iso
    t_start = _parse_iso(started_at)
    t_end = _parse_iso(completed_at)
    duration_ms = max(0.0, (t_end - t_start) * 1000.0)

    # -- Rework lineage over dispatched ids -------------------------------
    dispatched = set(handoffs.keys())
    orders_by_root: dict[str, int] = {}
    for order in rework_orders or ():
        root = lineage_root(str(order.get("target_task_id", "")))
        orders_by_root[root] = orders_by_root.get(root, 0) + 1

    # -- Task counts (per mission task, lineage-resolved) ------------------
    task_count = len(mission.tasks)
    completed_tasks = 0
    blocked_tasks = 0
    failed_tasks = 0
    for t in mission.tasks:
        ho = handoffs.get(t.task_id)
        status = ho.status if ho is not None else "blocked"
        if status == "done":
            completed_tasks += 1
        elif status == "blocked":
            blocked_tasks += 1
        else:
            failed_tasks += 1

    escalated_tasks = len(escalations)
    rework_cycles = len(rework_orders)

    # -- Role counts --------------------------------------------------------
    # invoked: roles that actually dispatched at least one task (handoff exists)
    # completed: roles whose mission task finished done
    invoked: set[str] = set()
    completed_roles: set[str] = set()
    for t in mission.tasks:
        ho = handoffs.get(t.task_id)
        if ho is not None:
            invoked.add(t.owner)
            if ho.status == "done":
                completed_roles.add(ho.owner)
    roles_invoked = tuple(sorted(invoked))
    roles_completed = tuple(sorted(completed_roles))

    # -- Wave / parallelism -------------------------------------------------
    waves = waves_executed
    if parallel_peak is not None:
        parallel_tasks_peak = max(0, int(parallel_peak))
    elif per_task_wave:
        wave_counts: dict[int, int] = {}
        for w in per_task_wave.values():
            wave_counts[w] = wave_counts.get(w, 0) + 1
        parallel_tasks_peak = max(wave_counts.values()) if wave_counts else 0
    else:
        parallel_tasks_peak = 1  # conservative default

    # -- Verification -------------------------------------------------------
    verification_passed = 0
    verification_failed = 0
    for r in reviews or ():
        action = r.get("action", "")
        if action == "accept":
            verification_passed += 1
        elif action in ("rework", "escalate"):
            verification_failed += 1

    # -- Per-task detail (lineage-aggregated) -------------------------------
    per_task_wave = per_task_wave or {}
    per_task_attempts = per_task_attempts or {}
    per_task_durations = per_task_durations or {}
    per_task: list[ObservedTaskMetrics] = []
    per_role_acc: dict[str, dict] = {}
    for t in mission.tasks:
        ho = handoffs.get(t.task_id)
        lin = lineage_ids(t.task_id, dispatched)
        attempts = max(
            [per_task_attempts.get(lid, 1) for lid in lin if lid in per_task_attempts]
            or [1])
        # attempts must be >= 1 + rework cycles actually ordered (observed)
        attempts = max(attempts, 1 + orders_by_root.get(t.task_id, 0))
        duration = sum(per_task_durations.get(lid, 0.0) for lid in lin)
        status = ho.status if ho is not None else "blocked"
        per_task.append(ObservedTaskMetrics(
            task_id=t.task_id,
            owner=t.owner,
            role=t.role,
            status=status,
            attempts=attempts,
            wave=per_task_wave.get(t.task_id, 0),
            duration_ms=round(duration, 3),
            rework_cycles=orders_by_root.get(t.task_id, 0),
        ))
        acc = per_role_acc.setdefault(t.owner, {
            "tasks": 0, "completed": 0, "blocked": 0, "failed": 0,
            "total_attempts": 0, "rework_cycles_triggered": 0,
            "total_duration_ms": 0.0,
        })
        acc["tasks"] += 1
        if status == "done":
            acc["completed"] += 1
        elif status == "blocked":
            acc["blocked"] += 1
        else:
            acc["failed"] += 1
        acc["total_attempts"] += attempts
        acc["rework_cycles_triggered"] += orders_by_root.get(t.task_id, 0)
        acc["total_duration_ms"] += duration

    per_role = tuple(
        ObservedRoleMetrics(
            role=r,
            tasks=s["tasks"],
            completed=s["completed"],
            blocked=s["blocked"],
            failed=s["failed"],
            total_attempts=s["total_attempts"],
            rework_cycles_triggered=s["rework_cycles_triggered"],
            total_duration_ms=round(s["total_duration_ms"], 3),
        )
        for r, s in sorted(per_role_acc.items())
    )

    # -- CFO estimates (ESTIMATED, never OBSERVED) --------------------------
    cfo_estimates: EstimatedCfoData | None = None
    mission_ids = {t.task_id for t in mission.tasks}
    for tid in sorted(mission_ids):
        ho = handoffs.get(tid)
        if ho is None or ho.owner != "cfo" or ho.status != "done":
            continue
        findings = list(ho.findings)
        risks = list(ho.risks)
        summary = ho.summary or ""
        res_rec = ""
        cost_est = ""
        budget_note = ""
        for f in findings:
            fl = f.lower()
            if "resource" in fl or "recommend" in fl:
                res_rec = f
            elif "cost" in fl or "budget" in fl or "estimate" in fl:
                cost_est = f
        if not res_rec and summary:
            res_rec = summary
        cfo_estimates = EstimatedCfoData(
            resource_recommendation=res_rec,
            cost_estimate=cost_est,
            budget_note=budget_note,
            findings=tuple(findings),
            risks=tuple(risks),
        )
        break

    return MissionMetrics(
        mission_id=mission.mission_id,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=duration_ms,
        task_count=task_count,
        completed_tasks=completed_tasks,
        blocked_tasks=blocked_tasks,
        failed_tasks=failed_tasks,
        escalated_tasks=escalated_tasks,
        rework_cycles=rework_cycles,
        roles_invoked=roles_invoked,
        roles_completed=roles_completed,
        waves=waves,
        parallel_tasks_peak=parallel_tasks_peak,
        verification_passed=verification_passed,
        verification_failed=verification_failed,
        per_role_metrics=per_role,
        per_task_metrics=tuple(per_task),
        cfo_estimates=cfo_estimates,
    )


# ---------------------------------------------------------------------------
# Convenience: collect from a MissionRunner
# ---------------------------------------------------------------------------

def collect_from_runner(runner, mission: MissionPacket, verdict: RootVerdict,
                        *, per_task_wave: dict[str, int] | None = None,
                        started_at: str | None = None) -> MissionMetrics:
    """Collect metrics from a MissionRunner after run()."""
    return collect_mission_metrics(
        mission=mission,
        handoffs=runner.handoffs,
        reviews=runner.reviews,
        rework_orders=runner.rework.history(),
        escalations=runner.escalations,
        waves_executed=runner.waves_executed,
        verdict=verdict,
        started_at=started_at if started_at is not None
        else getattr(runner, "started_at", None),
        completed_at=getattr(runner, "completed_at", None) or None,
        per_task_wave=per_task_wave if per_task_wave is not None
        else getattr(runner, "_task_wave", None),
        per_task_attempts=getattr(runner, "_attempts", None),
        per_task_durations=getattr(runner, "_task_durations", None),
        parallel_peak=getattr(runner, "parallel_peak_observed", None),
    )


__all__ = [
    "MissionMetrics",
    "ObservedTaskMetrics",
    "ObservedRoleMetrics",
    "EstimatedCfoData",
    "collect_mission_metrics",
    "collect_from_runner",
    "lineage_root",
    "lineage_ids",
]

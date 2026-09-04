# orchestrator.organization.waves — dependency-aware wave scheduling (MVP)
#
# Pure ordering over the mission task graph.  EXECUTION always goes through
# the EXISTING ParallelExecutor (orchestrator.runtime.parallel) — this module
# adds NO executor, NO scheduler beyond wave membership.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def plan_waves(
    task_ids: tuple[str, ...],
    depends_map: dict[str, tuple[str, ...]],
    completed: set[str] | tuple[str, ...] | None = None,
) -> tuple[tuple[str, ...], ...]:
    """Partition task ids into dependency-ordered waves.

    Each wave is a maximal independent set: every depends_on of every
    member is satisfied by prior waves.  The concatenation of all waves
    is a topological order of the input.

    An external dependency (a ``depends_on`` not in ``task_ids``) is
    allowed **only** when it is explicitly proven completed via
    ``completed`` — the proven set. Unknown / unproven external
    dependencies fail closed (ValueError). Internal DAG validation is
    preserved.

    Raises ValueError on a cycle, unproven external dependency, or
    unsatisfied graph (fail-closed).
    """
    task_ids = tuple(task_ids)
    if not task_ids:
        return ()
    ids = set(task_ids)
    completed_set = set(completed) if completed is not None else set()
    # Validate deps reference known ids or proven external completions
    for tid in task_ids:
        for dep in depends_map.get(tid, ()):
            if dep == tid:
                raise ValueError(f"task {tid!r} depends on itself (cycle)")
            if dep not in ids and dep not in completed_set:
                raise ValueError(
                    f"task {tid!r} depends on unproven external task {dep!r} "
                    f"(fail-closed: external dependency must be explicitly proven completed)")
            if dep not in ids and dep in completed_set:
                # proven external — allowed, no wave edge needed (already satisfied)
                continue
    # Kahn level by level
    in_degree: dict[str, int] = {tid: 0 for tid in task_ids}
    dependents: dict[str, list[str]] = {tid: [] for tid in task_ids}
    for tid in task_ids:
        for dep in depends_map.get(tid, ()):
            if dep in ids:
                in_degree[tid] += 1
                dependents[dep].append(tid)
    waves: list[tuple[str, ...]] = []
    frontier = [tid for tid in task_ids if in_degree[tid] == 0]
    # deterministic: preserve input order within each frontier
    visited: set[str] = set()
    remaining = len(task_ids)
    while frontier:
        wave = tuple(frontier)
        waves.append(wave)
        visited.update(frontier)
        remaining -= len(frontier)
        next_set: list[str] = []
        seen_next: set[str] = set()
        for tid in frontier:
            for dep_tid in dependents[tid]:
                in_degree[dep_tid] -= 1
                if in_degree[dep_tid] == 0 and dep_tid not in seen_next:
                    next_set.append(dep_tid)
                    seen_next.add(dep_tid)
        # keep input-order determinism for next frontier
        order = {tid: idx for idx, tid in enumerate(task_ids)}
        next_set.sort(key=lambda x: order[x])
        frontier = next_set
    if remaining != 0:
        cycle = sorted(set(task_ids) - visited)
        raise ValueError(
            f"dependency cycle detected among {cycle}; "
            f"tasks must form a DAG")
    return tuple(waves)


def plan_mission_waves(mission) -> tuple[tuple[str, ...], ...]:
    """Convenience: waves for a MissionPacket."""
    proven = getattr(mission, "proven_completed", None)
    return plan_waves(
        tuple(t.task_id for t in mission.tasks),
        {t.task_id: tuple(t.depends_on) for t in mission.tasks},
        completed=set(proven) if proven else None,
    )


def build_wave_plans(tasks, mission_tasks_by_id=None):
    """Build SubtaskPlans for one wave, reusing the existing build_plans.

    tasks: iterable of MissionTask in the same wave (must be independent).
    Returns tuple[SubtaskPlan, ...] for ParallelExecutor.
    """
    from orchestrator.runtime.parallel import build_plans  # noqa: WPS433

    # Convert MissionTask -> Task for the existing builder
    subtasks = [t.to_task() for t in tasks]
    return build_plans(subtasks)

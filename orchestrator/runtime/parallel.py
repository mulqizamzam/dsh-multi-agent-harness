# orchestrator.runtime.parallel — Controlled parallel subtask execution (Phase 3)
#
# Independent subtasks may execute concurrently through the APPROVED DSH
# adapter (orchestrator.dsh.DelegationClient). This module adds NO new
# authority, NO new gate, and NO new delegation logic — it only decides whether
# a batch is provably safe to run concurrently, and then runs it.
#
# BEFORE any child starts (contract §6, THREAT-021, PST-001/002):
#   1. DEPENDENCY INDEPENDENCE — no member of the batch depends on another
#      member (and no dependency is unsatisfied); a dependent subtask is
#      sequenced, never parallelized.
#   2. TASK OWNERSHIP — every subtask id appears exactly once and is owned by
#      exactly one specialist role. Peer topology is preserved: a specialist
#      never owns, manages, or supervises another specialist's subtask.
#   3. READ/WRITE SCOPE — each subtask declares its read scope; reads may
#      overlap (concurrent reads are safe). A specialist WRITE scope is
#      REFUSED outright: the orchestrator is the single authoritative writer
#      and specialists return results — they never write project state
#      (contract §6). Two subtasks may therefore never contend for a write.
#   4. STATE VERSION — the held project-state version is captured before the
#      batch and RE-VALIDATED after it (RuntimeStore.check_current, the
#      existing CAS/version control). Any version drift during the parallel
#      phase means an uncontrolled shared write occurred → StaleStateDetected,
#      fail-closed.
#
# Concurrency is bounded (max_workers) and every child failure PROPAGATES as a
# typed SubtaskFailed — no partial success, no silent skip (INT-12).

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Task, SPECIALIST_ROLES  # noqa: E402

from .exceptions import ParallelUnsafe, StaleStateDetected  # noqa: E402

# Upper bound on concurrent children, independent of batch size.
DEFAULT_MAX_WORKERS = 4


@dataclass(frozen=True)
class SubtaskPlan:
    """One unit of the parallel batch: a task, its owner, and its data scope.

    owner:
        The single specialist role that owns this subtask. Ownership is
        exclusive and flat — an owner never owns another owner's subtask
        (peer topology, AGENTS.md principle 1).
    reads:
        Resource patterns the subtask may READ. Overlap between members is
        allowed (concurrent reads do not contend).
    writes:
        Resource patterns the subtask would WRITE. MUST be empty: specialists
        return results and never write project state (contract §6). A non-empty
        write scope makes the batch unsafe.
    depends_on:
        Task ids that must complete BEFORE this subtask. A dependency on
        another member of the same batch makes the batch non-parallelizable.
    """
    task: Task
    owner: str
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()

    @property
    def task_id(self) -> str:
        return self.task.task_id

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "owner": self.owner,
            "reads": list(self.reads),
            "writes": list(self.writes),
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class ParallelSafety:
    """The recorded pre-flight safety decision for one batch (audit-ready
    DATA — it never grants authority)."""
    safe: bool
    reason: str = ""
    task_ids: tuple[str, ...] = ()
    owners: tuple[str, ...] = ()
    read_scopes: tuple[str, ...] = ()
    held_version: int = 0

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "reason": self.reason,
            "task_ids": list(self.task_ids),
            "owners": list(self.owners),
            "read_scopes": list(self.read_scopes),
            "held_version": self.held_version,
        }


def build_plans(subtasks, *, reads_from_scope: bool = True,
                depends_on=None) -> tuple[SubtaskPlan, ...]:
    """Build SubtaskPlans from decomposed subtasks.

    Each subtask is owned by its own ``assigned_role``, reads its task scope,
    and declares NO write scope (the orchestrator is the single writer).

    ``depends_on`` may explicitly map task_id -> tuple of dependencies.
    When a key is absent, ``Task.dependencies`` is used as the fallback so
    a decomposed DAG (Task graph) flows directly into SubtaskPlans without
    an extra translation layer.
    """
    depends_on = depends_on or {}
    plans = []
    for st in subtasks:
        if st.task_id in depends_on:
            deps = tuple(depends_on[st.task_id] or ())
        else:
            deps = tuple(getattr(st, "dependencies", ()) or ())
        plans.append(SubtaskPlan(
            task=st,
            owner=getattr(st, "assigned_role", ""),
            reads=tuple(st.scope or ()) if reads_from_scope else (),
            writes=(),
            depends_on=deps,
        ))
    return tuple(plans)


def assert_parallel_safe(plans, *, held_version: int = 0) -> ParallelSafety:
    """Verify a batch may run concurrently. Raises ParallelUnsafe otherwise.

    Checks, in order (fail-closed — the first failure refuses the batch before
    ANY child starts):
      - batch is non-empty and every member is a SubtaskPlan
      - every owner is a known specialist (never the orchestrator, never an
        unknown actor)
      - task ownership is exclusive: no duplicate task id, and each task has
        exactly one owner
      - dependency independence: no member depends on another member
      - read/write scope: no member declares a write scope
    """
    plans = tuple(plans or ())
    if not plans:
        raise ParallelUnsafe("parallel batch is empty (nothing to run)")

    seen: dict[str, str] = {}
    for p in plans:
        if not isinstance(p, SubtaskPlan):
            raise ParallelUnsafe(
                f"parallel batch member is not a SubtaskPlan: {type(p).__name__}")
        if p.owner not in SPECIALIST_ROLES:
            raise ParallelUnsafe(
                f"subtask {p.task_id!r} owner {p.owner!r} is not a specialist "
                f"role; only specialists own subtasks (peer topology)")
        if p.owner != getattr(p.task, "assigned_role", p.owner):
            raise ParallelUnsafe(
                f"subtask {p.task_id!r} owner {p.owner!r} does not match its "
                f"assigned role {getattr(p.task, 'assigned_role', '')!r} "
                f"(single-owner violation)")
        if p.task_id in seen:
            raise ParallelUnsafe(
                f"subtask id {p.task_id!r} appears twice (owners "
                f"{seen[p.task_id]!r} and {p.owner!r}); task ownership must be "
                f"exclusive")
        seen[p.task_id] = p.owner

    # 3. read/write scope — a specialist write scope is never permitted.
    for p in plans:
        if p.writes:
            raise ParallelUnsafe(
                f"subtask {p.task_id!r} ({p.owner}) declares a write scope "
                f"{list(p.writes)}; specialists return results and never write "
                f"project state — the orchestrator is the single authoritative "
                f"writer (contract §6, THREAT-021)")

    # 2b. dependency independence — no intra-batch dependency.
    ids = set(seen)
    for p in plans:
        intra = ids & set(p.depends_on)
        if intra:
            raise ParallelUnsafe(
                f"subtask {p.task_id!r} depends on batch member(s) "
                f"{sorted(intra)}; dependent subtasks must be sequenced, not "
                f"parallelized (contract §6)")

    return ParallelSafety(
        safe=True, reason="independent, single-owner, read-only subtasks",
        task_ids=tuple(p.task_id for p in plans),
        owners=tuple(p.owner for p in plans),
        read_scopes=tuple(sorted({r for p in plans for r in p.reads})),
        held_version=held_version,
    )


class ParallelExecutor:
    """Run an independent subtask batch concurrently through the approved DSH
    adapter, preserving the project-state version across the batch.

    Parameters
    ----------
    runner:
        ``(task, delegation) -> TaskResult | DelegationOutcome`` — the SAME
        subtask runner the sequential path uses (the DSH DelegationClient by
        default). This executor never talks to DSH directly.
    store:
        Optional RuntimeStore. When supplied, the held state version is
        re-validated after the batch: drift means an uncontrolled shared write
        occurred (StaleStateDetected, fail-closed).
    max_workers:
        Bound on concurrent children.
    """

    def __init__(self, runner, *, store=None,
                 max_workers: int = DEFAULT_MAX_WORKERS):
        if not callable(runner):
            raise ParallelUnsafe("parallel executor requires a callable runner")
        self.runner = runner
        self.store = store
        self.max_workers = max(1, int(max_workers or 1))
        self.safety: ParallelSafety | None = None

    def run(self, plans, delegation, *, held_version: int = 0) -> list:
        """Execute the batch concurrently and return results in BATCH ORDER.

        Order is deterministic (input order), not completion order, so a
        parallel run and a sequential run over the same batch produce the same
        collected sequence.

        Raises
        ------
        ParallelUnsafe
            The batch is not provably safe to parallelize (nothing started).
        StaleStateDetected
            The project-state version changed during the batch (an
            uncontrolled shared write).
        Exception
            The FIRST child failure, in batch order, is re-raised so it
            propagates to the flow (no partial success).
        """
        plans = tuple(plans or ())
        self.safety = assert_parallel_safe(plans, held_version=held_version)

        # State version must be current BEFORE the batch (existing CAS check).
        if self.store is not None and held_version:
            self.store.check_current(held_version)

        outcomes: list = [None] * len(plans)
        errors: list = [None] * len(plans)

        def _one(index: int, plan: SubtaskPlan):
            try:
                outcomes[index] = self.runner(plan.task, delegation)
            except BaseException as e:  # noqa: BLE001 — propagated below
                errors[index] = e

        if len(plans) == 1:
            _one(0, plans[0])
        else:
            with ThreadPoolExecutor(
                    max_workers=min(self.max_workers, len(plans)),
                    thread_name_prefix="runtime-subtask") as pool:
                futures = [pool.submit(_one, i, p)
                           for i, p in enumerate(plans)]
                for f in futures:
                    f.result()  # _one never raises; this only joins

        # State version must be UNCHANGED after the batch: specialists never
        # write project state (contract §6, THREAT-021).
        if self.store is not None and held_version:
            try:
                self.store.check_current(held_version)
            except StaleStateDetected as e:
                raise StaleStateDetected(
                    f"parallel batch mutated shared state: {e}") from e

        # Propagate the FIRST failure in batch order (deterministic).
        for i, err in enumerate(errors):
            if err is not None:
                raise err

        return outcomes


def plan_waves(plans, *, completed: set[str] | None = None) -> list[tuple[SubtaskPlan, ...]]:
    """Partition a batch of SubtaskPlans into dependency-ordered waves.

    Pure function — no threads, no I/O, no authority.  Each wave is a
    maximal independent set: every ``depends_on`` of every member is
    satisfied by *prior* waves and by nothing in the current wave.
    The concatenation of all waves is a topological order of the input.

    Parameters
    ----------
    plans:
        Iterable of ``SubtaskPlan`` (typically from ``build_plans`` where
        ``depends_on`` was derived from ``Task.dependencies``).
    completed:
        Set of already-completed external task ids whose satisfaction has
        been PROVEN (e.g. from lifecycle COMPLETE set or a caller-supplied
        closed set).  Any ``depends_on`` not present in the current batch
        and not in ``completed`` is an UNSATISFIED external dependency and
        fails CLOSED (ParallelUnsafe).  ``None`` (default) means no external
        id is proven — every out-of-batch dependency is refused.  Pass
        ``set()`` explicitly when the caller has proven that no external
        dependency exists for this batch; an empty set has the same effect
        as ``None`` but makes the call-site intent explicit.

    Returns
    -------
    list of waves, each wave is a tuple of SubtaskPlans in deterministic
    (task_id-sorted) order.  Empty input -> [].

    Raises
    ------
    ParallelUnsafe
        Duplicate task_id, unsatisfied internal dependency cycle, unsatisfied
        external dependency, or any other graph that cannot be topologically
        sorted.  Fail-closed before any child starts.
    """
    plans = tuple(plans or ())
    if not plans:
        return []
    # Validate element types early — same invariant as assert_parallel_safe.
    for p in plans:
        if not isinstance(p, SubtaskPlan):
            raise ParallelUnsafe(
                f"plan_waves member is not a SubtaskPlan: {type(p).__name__}")

    # Exclusive ownership check (duplicate task_id) — fail-closed.
    seen: dict[str, SubtaskPlan] = {}
    for p in plans:
        if p.task_id in seen:
            raise ParallelUnsafe(
                f"subtask id {p.task_id!r} appears twice in plan_waves; "
                f"task ownership must be exclusive")
        seen[p.task_id] = p

    ids = set(seen)
    # Fail-closed on unsatisfied external dependencies: any depends_on not in
    # ids must be in the proven `completed` set, otherwise its satisfaction
    # cannot be established (no silent safe-assumption).
    completed_set = set(completed) if completed is not None else set()
    for p in plans:
        for dep in p.depends_on:
            if dep not in ids and dep not in completed_set:
                raise ParallelUnsafe(
                    f"subtask {p.task_id!r} depends on {dep!r} which is not "
                    f"in the current batch and not in the proven completed "
                    f"set — unsatisfied external dependency (fail-closed)")
    # Build adjacency: edge dep -> plan for deps that are *inside* the batch.
    # Proven external deps do not create a wave ordering constraint.
    in_degree: dict[str, int] = {tid: 0 for tid in ids}
    dependents: dict[str, list[str]] = {tid: [] for tid in ids}
    for p in plans:
        for dep in p.depends_on:
            if dep in ids:
                in_degree[p.task_id] += 1
                dependents[dep].append(p.task_id)
        # self-dependency is a cycle
        if p.task_id in p.depends_on:
            raise ParallelUnsafe(
                f"subtask {p.task_id!r} depends on itself (cycle)")

    # Kahn's algorithm, level by level (wave = all zero in-degree nodes).
    waves: list[tuple[SubtaskPlan, ...]] = []
    # deterministic: sort each frontier by task_id
    frontier = sorted([tid for tid, deg in in_degree.items() if deg == 0])
    remaining = len(ids)
    visited: set[str] = set()

    while frontier:
        wave = tuple(seen[tid] for tid in frontier)
        # Each wave must be provably parallel-safe (single-owner, read-only).
        # This reuses the existing gate rather than duplicating its checks.
        # External callers also call assert_parallel_safe per wave in the
        # executor path; this is an early fail-closed check.
        assert_parallel_safe(wave)
        waves.append(wave)
        visited.update(frontier)
        remaining -= len(frontier)
        # Decrement dependents and build next frontier
        next_frontier_set: set[str] = set()
        for tid in frontier:
            for dep_tid in dependents[tid]:
                in_degree[dep_tid] -= 1
                if in_degree[dep_tid] == 0:
                    next_frontier_set.add(dep_tid)
        frontier = sorted(next_frontier_set)

    if remaining != 0:
        # Cycle among unvisited nodes — cannot be topologically sorted.
        cycle = sorted(set(ids) - visited)
        raise ParallelUnsafe(
            f"dependency cycle detected among {cycle}; "
            f"dependent subtasks must form a DAG (contract §6)")

    return waves


__all__ = [
    "SubtaskPlan", "ParallelSafety", "ParallelExecutor",
    "assert_parallel_safe", "build_plans", "plan_waves", "DEFAULT_MAX_WORKERS",
]

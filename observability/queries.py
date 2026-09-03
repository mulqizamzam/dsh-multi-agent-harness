# observability.queries — Operational queries over the RunIndex
#
# Phase 4 / Session D — Production operations + observability.
#
# Read-only lookup surface: run lookup by run_id, task lookup by task_id,
# delegation lookup, failure lookup, timeline reconstruction, evidence
# reference lookup, and a health/sanity report. All results are DERIVED DATA —
# never authority (AUTH-INV-14). Lookups never fabricate ids: an unknown id
# returns None / empty.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from observability.model import RunIndex


def find_run(index: RunIndex, run_id: str) -> dict | None:
    """Run lookup by run_id (exact; None when unknown)."""
    run = index.runs.get(run_id)
    return run.to_dict() if run is not None else None


def find_task(index: RunIndex, task_id: str) -> dict | None:
    """Task lookup by task_id across all runs.

    Returns the first matching task record with its run_id; None when unknown.
    """
    for run_id in index.run_order:
        task = index.runs[run_id].tasks.get(task_id)
        if task is not None:
            return task.to_dict()
    return None


def find_tasks_by_run(index: RunIndex, run_id: str) -> dict:
    """All task records of one run (task_id -> record)."""
    run = index.runs.get(run_id)
    if run is None:
        return {}
    return {tid: t.to_dict() for tid, t in run.tasks.items()}


def find_delegation(index: RunIndex, delegation_id: str) -> dict | None:
    """Delegation lookup by delegation_id across all runs."""
    for run_id in index.run_order:
        d = index.runs[run_id].delegations.get(delegation_id)
        if d is not None:
            return d.to_dict()
    return None


def find_failures(index: RunIndex, *, run_id: str | None = None,
                  failure_class: str | None = None) -> list:
    """Failure lookup.

    Filters by run_id / failure_class when given; returns all failures
    otherwise (ordered by run, then event order).
    """
    out = []
    for rid in index.run_order:
        if run_id is not None and rid != run_id:
            continue
        for f in index.runs[rid].failures:
            if failure_class is not None and f.failure_class != failure_class:
                continue
            out.append(f.to_dict())
    return out


def find_evidence_refs(index: RunIndex, *, run_id: str | None = None,
                       task_id: str | None = None) -> list:
    """Evidence reference lookup.

    Returns the distinct evidence references recorded for a run (or a task's
    events). References come from the ledger's `evidence` tuples (runtime
    events), never from model prose.
    """
    refs = []
    for rid in index.run_order:
        if run_id is not None and rid != run_id:
            continue
        run = index.runs[rid]
        for e in run.events:
            if task_id is not None and e.task_id != task_id:
                continue
            ev = e.event.get("evidence")
            if isinstance(ev, (list, tuple)):
                for ref in ev:
                    if ref not in refs:
                        refs.append(str(ref))
    return refs


def reconstruct_timeline(index: RunIndex, run_id: str) -> list | None:
    """Timeline reconstruction for one run.

    Returns the ordered lifecycle events (RUN_STARTED -> ... -> RUN_TERMINAL)
    as dicts with stage, source, event_class, event_id, timestamp, result,
    failure_class, and a compact summary. None when the run is unknown.
    """
    run = index.runs.get(run_id)
    if run is None:
        return None
    return [e.to_dict() for e in run.events]


def health_report(index: RunIndex) -> dict:
    """Health/sanity report over the whole index.

    Includes ledger integrity (from the existing audit helpers), rejection
    counts, per-run problems, missing/duplicate terminal detection, and an
    overall `healthy` flag (False when any rejection or problem exists).
    """
    problems = []
    for rid in index.run_order:
        run = index.runs[rid]
        for p in run.problems:
            problems.append({**p.to_dict(), "run_id": rid})
    for p in index.rejected:
        problems.append(p.to_dict())

    healthy = (not problems) and bool(index.ledger_integrity.get("strict_ok",
                                                                 True))
    return {
        "healthy": healthy,
        "total_runs": len(index.run_order),
        "rejected_events": len(index.rejected),
        "problems": problems,
        "ledger_integrity": dict(index.ledger_integrity),
        "built_at": index.built_at,
    }


def run_outcome_counts(index: RunIndex) -> dict:
    """Quick outcome rollup (convenience for dashboards)."""
    from observability.metrics import compute_metrics
    return compute_metrics(index)["totals"]


__all__ = [
    "find_run", "find_task", "find_tasks_by_run", "find_delegation",
    "find_failures", "find_evidence_refs", "reconstruct_timeline",
    "health_report", "run_outcome_counts",
]

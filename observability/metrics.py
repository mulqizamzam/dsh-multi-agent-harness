# observability.metrics — Metrics over the RunIndex (derived data)
#
# Phase 4 / Session D — Production operations + observability.
#
# All metrics are computed from the correlated RunIndex (which itself reads
# only the existing audit ledger). They are DATA — never authority. Latency
# values are wall-clock deltas derived from event timestamps; when timestamps
# are absent or non-ISO they are omitted (never fabricated).

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from observability.model import RunIndex
from observability.vocab import (
    OUTCOME_COMPLETE, OUTCOME_BLOCKED, OUTCOME_FAILED, OUTCOME_ESCALATED,
    OUTCOME_RECOVERING,
)


def compute_metrics(index: RunIndex) -> dict:
    """Compute the observability metric set over a RunIndex.

    Returns a dict with:
      - totals: total_runs, completed/blocked/failed/escalated/recovering runs
      - denials: authority_denials, gate_denials, verification_failures
      - recovery: recovery_count, retry_count
      - failures: child_failures, failed_runs_with_recovery
      - parallelism: parallel_batches, max_parallel_batch_size, avg
      - latency: execution/verification/recovery latency (sum + count)
    """
    runs = [index.runs[r] for r in index.run_order]

    def _count_outcome(outcome: str) -> int:
        return sum(1 for r in runs if r.outcome == outcome)

    authority_denials = 0
    gate_denials = 0
    verification_failures = 0
    recovery_count = 0
    retry_count = 0
    child_failures = 0
    parallel_batches = 0
    max_parallel_size = 0
    total_parallel_size = 0
    exec_latency_total = 0
    exec_latency_count = 0
    ver_latency_total = 0
    ver_latency_count = 0
    rec_latency_total = 0
    rec_latency_count = 0

    for run in runs:
        for e in run.events:
            cls = e.event_class
            if cls == "execution_denial":
                authority_denials += 1
            elif cls in ("gate_risk", "gate_evidence", "gate_conflict",
                         "gate_review", "gate_authority", "gate_verification",
                         "gate"):
                if (e.result or "").lower() in ("denied", "deny"):
                    gate_denials += 1
            elif cls == "verification_denied":
                verification_failures += 1
            elif cls in ("recovery", "recovery_state_transition"):
                recovery_count += 1
            elif cls == "subtask_failed":
                child_failures += 1
        retry_count += run.retry_count
        parallel_batches += len(run.parallel_batches)
        for b in run.parallel_batches:
            size = len(b.get("task_ids") or [])
            max_parallel_size = max(max_parallel_size, size)
            total_parallel_size += size

        ex_ms = run.latency.get("execution_ms")
        if ex_ms is not None:
            exec_latency_total += ex_ms
            exec_latency_count += 1
        v_ms = run.latency.get("verification_ms")
        if v_ms is not None:
            ver_latency_total += v_ms
            ver_latency_count += 1
        r_ms = run.latency.get("recovery_escalation_ms")
        if r_ms is not None:
            rec_latency_total += r_ms
            rec_latency_count += 1

    def _avg(total, count):
        return round(total / count, 1) if count else 0

    return {
        "totals": {
            "total_runs": len(runs),
            "completed_runs": _count_outcome(OUTCOME_COMPLETE),
            "blocked_runs": _count_outcome(OUTCOME_BLOCKED),
            "failed_runs": _count_outcome(OUTCOME_FAILED),
            "escalated_runs": _count_outcome(OUTCOME_ESCALATED),
            "recovering_runs": _count_outcome(OUTCOME_RECOVERING),
        },
        "denials": {
            "authority_denials": authority_denials,
            "gate_denials": gate_denials,
            "verification_failures": verification_failures,
        },
        "recovery": {
            "recovery_count": recovery_count,
            "retry_count": retry_count,
        },
        "failures": {
            "child_failures": child_failures,
            "runs_with_failure": sum(1 for r in runs if r.failures),
        },
        "parallelism": {
            "parallel_batches": parallel_batches,
            "max_parallel_batch_size": max_parallel_size,
            # Mean batch width: total tasks across all batches / batch count
            # (NOT max_parallel_size / parallel_batches).
            "avg_parallel_batch_size": round(
                total_parallel_size / parallel_batches, 1) if parallel_batches else 0,
        },
        "latency": {
            "execution_ms_avg": _avg(exec_latency_total, exec_latency_count),
            "execution_ms_total": exec_latency_total,
            "verification_ms_avg": _avg(ver_latency_total, ver_latency_count),
            "verification_ms_total": ver_latency_total,
            "recovery_ms_avg": _avg(rec_latency_total, rec_latency_count),
            "recovery_ms_total": rec_latency_total,
        },
        "integrity": {
            "rejected_events": len(index.rejected),
            "runs_with_problems": sum(1 for r in runs if r.problems),
        },
    }


__all__ = ["compute_metrics"]

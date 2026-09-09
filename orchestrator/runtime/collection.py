# orchestrator.runtime.collection — Structured result collection (Phase 3)
#
# The runtime collects STRUCTURED TaskResults only. A specialist's report is
# DATA (AUTH-INV-13): its `status` / `recommendation` are CLAIMS the
# orchestrator verifies later — collecting them never grants authority, and a
# claim never establishes a state transition.
#
# This module does NOT reimplement result validation: the DSH adapter's
# TaskResultCollector (orchestrator.dsh.result) already validates a child's
# structured output against schemas/task-result.schema.json and the TaskResult
# contract, and asserts role identity + task id. Here the runtime only:
#   - accepts what the approved adapter returned (a DelegationOutcome carrying
#     the validated TaskResult + its provenance stamp, or a bare TaskResult
#     from an injected runner)
#   - PRESERVES the required fields: task_id, role, provenance, status,
#     findings, evidence, risks, assumptions, unresolved_items, actions_taken
#   - PROPAGATES a claimed FAILED / BLOCKED status as a typed SubtaskFailed —
#     a failed child never becomes a silently-skipped success (INT-12)
#   - strips nothing and infers nothing: an unrecognized payload is refused
#     (fail-closed), never coerced

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import TaskResult  # noqa: E402

from .exceptions import SubtaskFailed, RuntimeFlowError  # noqa: E402

# A claimed status the orchestrator treats as a propagating subtask failure.
# Every status except SUCCEEDED is failing: a cancelled, timed-out, or
# incomplete subtask is never silently skipped (INT-12; PRD v0.2 §13).
FAILING_STATUSES = ("FAILED", "BLOCKED", "CANCELLED", "TIMEOUT", "INCOMPLETE")


@dataclass(frozen=True)
class CollectedResult:
    """One collected specialist result plus its delegation provenance.

    result:
        The validated TaskResult (DATA — never authority).
    provenance:
        The adapter's provenance stamp as a dict (role identity, delegation id,
        subagent tool/persona, run id, stop reason, timestamps). Empty when the
        result came from an injected runner that carries no provenance.
    """
    result: TaskResult
    provenance: dict = field(default_factory=dict)

    # -- required field accessors (preserved verbatim) ---------------------
    @property
    def task_id(self) -> str:
        return self.result.task_id

    @property
    def role(self) -> str:
        return self.result.assigned_role

    @property
    def status(self) -> str:
        return self.result.status

    def to_dict(self) -> dict:
        """The preserved structured record (requirement 11 field set)."""
        return {
            "task_id": self.result.task_id,
            "role": self.result.assigned_role,
            "provenance": dict(self.provenance),
            "status": self.result.status,
            "findings": list(self.result.findings),
            "evidence": list(self.result.evidence),
            "risks": list(self.result.risks),
            "assumptions": list(self.result.assumptions),
            "unresolved_items": list(self.result.unresolved_items),
            "actions_taken": list(self.result.actions_taken),
            "recommendation": self.result.recommendation,
            "confidence": self.result.confidence,
            "reported_at": self.result.reported_at,
        }


def collect_one(payload, *, task=None) -> CollectedResult:
    """Normalize one runner payload into a CollectedResult.

    Accepts a ``DelegationOutcome`` (adapter path — provenance preserved) or a
    bare ``TaskResult`` (injected runner). Anything else is refused
    (fail-closed).

    Raises
    ------
    SubtaskFailed
        The child reported FAILED / BLOCKED (failure propagation).
    RuntimeFlowError
        The payload is not a recognized structured result.
    """
    if payload is None:
        raise SubtaskFailed(
            role=getattr(task, "assigned_role", ""),
            task_id=getattr(task, "task_id", ""),
            failure_class="logic",
            reason="subtask produced no structured result")

    provenance: dict = {}
    result = payload
    if not isinstance(payload, TaskResult):
        inner = getattr(payload, "result", None)
        if not isinstance(inner, TaskResult):
            raise RuntimeFlowError(
                f"unrecognized subtask payload {type(payload).__name__}: "
                f"expected a TaskResult or a DelegationOutcome "
                f"(structured results only)")
        result = inner
        prov = getattr(payload, "provenance", None)
        if prov is not None:
            provenance = prov.to_dict() if hasattr(prov, "to_dict") else dict(prov)

    # Role identity: the collected result must belong to the delegated role.
    # (The adapter's collector already asserts this on the live path; an
    # injected runner is checked here so no path is unvalidated.)
    if task is not None:
        expected_role = getattr(task, "assigned_role", "")
        if expected_role and result.assigned_role != expected_role:
            raise RuntimeFlowError(
                f"role identity mismatch: result claims "
                f"{result.assigned_role!r} but the subtask was delegated to "
                f"{expected_role!r}")

    if result.status in FAILING_STATUSES:
        # PRD v0.2 §13 / ADR 0003: every non-SUCCEEDED status propagates as a
        # typed subtask failure — CANCELLED/TIMEOUT/INCOMPLETE never degrade
        # into silent success.
        failure_class = {
            "FAILED": "logic",
            "BLOCKED": "authorization",
            "CANCELLED": "logic",
            "TIMEOUT": "environment",
            "INCOMPLETE": "logic",
        }[result.status]
        raise SubtaskFailed(
            role=result.assigned_role, task_id=result.task_id,
            failure_class=failure_class,
            reason=(f"specialist reported {result.status}"
                    + (f": {result.unresolved_items[0]}"
                       if result.unresolved_items else "")))

    return CollectedResult(result=result, provenance=provenance)


def collect_all(payloads, tasks=()) -> tuple[CollectedResult, ...]:
    """Collect a batch in input order. The FIRST failure propagates."""
    tasks = tuple(tasks or ())
    collected = []
    for i, payload in enumerate(payloads or ()):
        task = tasks[i] if i < len(tasks) else None
        collected.append(collect_one(payload, task=task))
    return tuple(collected)


def classify_adapter_failure(error) -> tuple[str, str]:
    """Map a DSH adapter exception to (failure_class, reason).

    Uses the adapter's typed vocabulary (orchestrator.dsh.exceptions) so the
    runtime branches on types, never on prose. Unknown errors stay "unknown" —
    an unknown failure is escalated, never guessed (Runbook 08).
    """
    try:
        from orchestrator.dsh.exceptions import (
            DelegationTimeout, DelegationAborted, ChildFailure,
            MalformedResult, RoleResolutionError, ProhibitedDelegation,
            DelegationDenied,
        )
    except ImportError:  # pragma: no cover — adapter always present
        return ("unknown", str(error))

    if isinstance(error, ProhibitedDelegation):
        return ("authorization", f"subdelegation denied: {error}")
    if isinstance(error, DelegationDenied):
        return ("authorization", f"delegation denied: {error}")
    if isinstance(error, RoleResolutionError):
        return ("environment", f"role resolution failed: {error}")
    if isinstance(error, DelegationTimeout):
        return ("environment", f"child timed out: {error}")
    if isinstance(error, DelegationAborted):
        return ("environment", f"child aborted: {error}")
    if isinstance(error, MalformedResult):
        return ("logic", f"malformed child result: {error}")
    if isinstance(error, ChildFailure):
        return ("logic", f"child failure: {error}")
    return ("unknown", str(error))


__all__ = [
    "CollectedResult", "collect_one", "collect_all",
    "classify_adapter_failure", "FAILING_STATUSES",
]

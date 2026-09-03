# tests/orchestrator/production/conftest.py — Test fixtures for the bounded
# production Execution Flow (Phase 4 / Session A).
#
# TEST-SUPPORT ONLY. Not production code. The fixtures reuse the Phase-3
# runtime test helpers (stub subtask runner / stub action executor) and the
# production modules under test.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    TaskIntake, Task, Delegation, TaskResult,
)
from orchestrator.runtime import (
    ExecutionFlow, MemoryDelegationProvider, RuntimeStore,
)

from orchestrator.production import (
    ProductionRun, ObjectivePlanner, BoundedExecutor, ReportGenerator,
)


def make_delegation(task_id="task-1", *, id="delegation-prod-001",
                    action="write", target="agents/**", environment="dev",
                    scope_operations=("write", "read", "code_write",
                                      "analysis"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    expires_at="", status="ACTIVE", **overrides):
    kw = dict(
        id=id, principal="human", delegate="orchestrator",
        project="multi-agent-harness", task=task_id,
        action=action, target=target, environment=environment,
        scope_operations=tuple(scope_operations),
        scope_resources=tuple(scope_resources),
        scope_environments=tuple(scope_environments),
        expires_at=expires_at, status=status, version=1,
    )
    kw.update(overrides)
    return Delegation(**kw)


def make_subtask_result(task_id, role, *, recommendation="",
                        findings=("analysis complete",), evidence=(),
                        status="SUCCEEDED", confidence="MEDIUM",
                        risks=(), unresolved_items=()):
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        recommendation=recommendation, confidence=confidence,
        risks=risks, unresolved_items=unresolved_items,
    )


class StubSubtaskRunner:
    """Deterministic subtask runner returning pre-configured results."""

    def __init__(self, results=None, default_recommendation="recommend",
                 default_evidence=("artifact:analysis",)):
        self._results = results or {}
        self._default_recommendation = default_recommendation
        self._default_evidence = default_evidence
        self.calls = []

    def add(self, role, result):
        self._results[role] = result

    def __call__(self, task, delegation):
        self.calls.append(task)
        key = task.assigned_role
        if key in self._results:
            return self._results[key]
        return TaskResult(
            task_id=task.task_id,
            assigned_role=task.assigned_role,
            status="SUCCEEDED",
            findings=(f"{key}: analysis",),
            evidence=self._default_evidence,
            recommendation=self._default_recommendation,
            confidence="MEDIUM",
        )


class StubActionExecutor:
    """Deterministic action executor returning pre-configured observed
    outcomes. Tracks calls and can fail a configurable number of times.

    When ``observed`` carries no explicit ``target``, the executor echoes the
    plan's target so expected-vs-actual verification matches the plan.
    """

    def __init__(self, observed=None, fail_count=0):
        self.observed = observed or {"exit_code": 0}
        self.fail_count = fail_count
        self.calls = []

    def __call__(self, plan):
        self.calls.append(plan)
        if self.fail_count > 0:
            self.fail_count -= 1
            raise RuntimeError("simulated execution failure")
        out = dict(self.observed)
        if "target" not in out:
            out["target"] = getattr(plan, "target", "")
        return out


@pytest.fixture()
def ws(o3_daemon_ws):
    """A temporary workspace that IS the O3 daemon root (O3 Phase B)."""
    wsdir, _c, _d = o3_daemon_ws
    return wsdir


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def provider(delegation):
    return MemoryDelegationProvider(delegation)


@pytest.fixture()
def subtask_runner():
    return StubSubtaskRunner()


@pytest.fixture()
def action_executor():
    return StubActionExecutor()


@pytest.fixture()
def planner():
    return ObjectivePlanner()


@pytest.fixture()
def executor(ws):
    return BoundedExecutor(base=ws)


@pytest.fixture()
def report_generator():
    return ReportGenerator()


@pytest.fixture()
def production(ws, executor, report_generator):
    return ProductionRun(base=ws, executor=executor,
                         report_generator=report_generator)


def seed_state(base: str, project: str = "multi-agent-harness") -> None:
    """Seed the initial project state document (version 1) in a workspace."""
    store = RuntimeStore(base=base, project=project)
    store.ensure_dirs()
    store.ensure_state()


def expected_synthesis(task_id, objective, risk, results) -> dict:
    """Replicate the Phase-3 flow's `_synthesize` output for a given result
    set, so a BadSector review's input_hash can be computed deterministically
    (the flow verifies the review against the hash of this exact document).
    TEST-SUPPORT ONLY — mirrors orchestrator.runtime.flow._synthesize."""
    return {
        "task_id": task_id,
        "objective": objective,
        "risk": risk,
        "findings": [f for tr in results for f in (tr.findings or ())],
        "recommendations": [tr.recommendation for tr in results
                            if tr.recommendation],
        "assumptions": [a for tr in results for a in (tr.assumptions or ())],
        "risks": [x for tr in results for x in (tr.risks or ())],
        "unresolved_items": [u for tr in results
                             for u in (tr.unresolved_items or ())],
        "roles": [tr.assigned_role for tr in results],
    }


def make_review_pass(task_id, objective, risk, results,
                     review_id="rev-001") -> dict:
    """Build a BadSector PASS review whose input_hash matches the flow's
    synthesis hash (provenance verifiable — THREAT-014/BAD-001)."""
    from control.badsector import _input_hash
    syn = expected_synthesis(task_id, objective, risk, results)
    return {
        "verdict": "PASS",
        "review_id": review_id,
        "input_hash": _input_hash(syn),
    }


__all__ = [
    "make_delegation", "make_subtask_result", "StubSubtaskRunner",
    "StubActionExecutor", "seed_state", "expected_synthesis",
    "make_review_pass",
]
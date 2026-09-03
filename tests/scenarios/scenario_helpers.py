# tests/scenarios/scenario_helpers.py — Reusable helpers for scenario tests
#
# TEST-SUPPORT ONLY. Not production code.
#
# This module provides the same builder functions and stub classes that the
# runtime tests (tests/orchestrator/runtime/conftest.py) provide, but in an
# importable form (sibling module, not conftest) because tests/scenarios/
# is a package with __init__.py.  Using these helpers avoids duplicating them
# and keeps the scenario tests focused on the scenario's assertions.

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    TaskIntake, Task, Delegation, TaskResult,
)


# ---- Builder functions -----------------------------------------------------

def make_delegation(task_id="task-1", *, id="delegation-test-001",
                    action="write", target="agents/**", environment="dev",
                    scope_operations=("write", "read", "code_write"),
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


def make_intake(objective="engineering", scope=("agents/**",),
                expected_outcome="module written and verified",
                required_authority_context="delegation-test-001"):
    return TaskIntake(
        objective=objective,
        scope=scope,
        expected_outcome=expected_outcome,
        required_authority_context=required_authority_context,
    )


def make_execute_plan(action="write", target="agents/cto/output.txt",
                      environment="dev", expected_outcome=None):
    """Create an ExecutePlan (imported lazily to avoid circular deps at module
    load time)."""
    from orchestrator.runtime import ExecutePlan
    return ExecutePlan(
        action=action, target=target, environment=environment,
        expected_outcome=expected_outcome or {"exit_code": 0},
    )


def make_subtask_result(task_id, role, *, recommendation="",
                        findings=("analysis complete",), evidence=(),
                        status="SUCCEEDED", confidence="MEDIUM"):
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        recommendation=recommendation,
        confidence=confidence,
    )


# ---- Stub classes ----------------------------------------------------------

class StubSubtaskRunner:
    """A deterministic subtask runner that returns pre-configured results."""

    def __init__(self, results=None, default_recommendation="recommend"):
        self._results = results or {}
        self._default_recommendation = default_recommendation

    def add(self, role, result):
        self._results[role] = result

    def __call__(self, task, delegation):
        key = task.assigned_role
        if key in self._results:
            return self._results[key]
        return TaskResult(
            task_id=task.task_id,
            assigned_role=task.assigned_role,
            status="SUCCEEDED",
            findings=(f"{key}: analysis",),
            evidence=(f"artifact:{key}",),
            recommendation=self._default_recommendation,
            confidence="MEDIUM",
        )


class StubActionExecutor:
    """A deterministic action executor that returns pre-configured observed
    outcomes.  Tracks calls for test assertions."""

    def __init__(self, observed=None, fail=False):
        self.observed = observed or {"exit_code": 0, "target": "agents/cto/output.txt"}
        self.fail = fail
        self.calls = []
        self.fail_count = 0
        self._call_count = 0

    def __call__(self, plan):
        self.calls.append(plan)
        self._call_count += 1
        if self.fail:
            if self.fail_count > 0:
                self.fail_count -= 1
                raise RuntimeError("simulated execution failure")
            elif self.fail is True:
                raise RuntimeError("simulated execution failure")
        return dict(self.observed)
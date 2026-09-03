# tests/orchestrator/runtime/conftest.py — Test fixtures for runtime tests
#
# TEST-SUPPORT ONLY. Not production code.

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
    ExecutionFlow, ExecutePlan, MemoryDelegationProvider,
    RuntimeStore, RuntimeAudit, GateRunner, TaskLifecycle,
    DelegationLifecycle,
)


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
        # Default: return a successful result with evidence (MEDIUM/HIGH
        # evidence gate requires a supporting source).
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ws(o3_daemon_ws):
    """A temporary workspace that IS the O3 daemon root (O3 Phase B).

    The daemon runs on the workspace root; protected state
    (state/registry/, state/projects/, audit/) is read/written through the
    O3 daemon client (no direct-fs fallback)."""
    wsdir, _client, _daemon = o3_daemon_ws
    return wsdir


@pytest.fixture()
def o3_daemon_client(o3_daemon_ws):
    """The O3 daemon client for the current test workspace."""
    _wsdir, client, _daemon = o3_daemon_ws
    return client


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def provider(delegation):
    """A MemoryDelegationProvider backed by the test delegation."""
    return MemoryDelegationProvider(delegation)


@pytest.fixture()
def subtask_runner():
    return StubSubtaskRunner()


@pytest.fixture()
def action_executor():
    return StubActionExecutor()


@pytest.fixture()
def flow(ws, provider, subtask_runner, delegation):
    """An ExecutionFlow wired to the temporary workspace and test mocks.

    The flow uses its DEFAULT executor (which writes consequential artifacts
    through the project execution gate). Tests that need a controllable
    executor set ``flow.executor = ...`` explicitly.
    """
    store = RuntimeStore(base=ws)
    store.ensure_dirs()
    # Seed the initial project state (version 1) through the O3 daemon
    # (sanctioned project_write channel; write_through is now denied for
    # state/projects/** — it's a protected root under O3 H4).
    from orchestrator.runtime.store import encode_project_state
    from orchestrator.foundation.state import ProjectState
    from control.execution_gate import project_write
    ps = ProjectState(project="multi-agent-harness")
    project_write(store.state_rel, encode_project_state(ps), base=store.base,
                  expected_version=0)
    flow = ExecutionFlow(
        project="multi-agent-harness",
        base=ws,
        provider=provider,
        store=store,
        subtask_runner=subtask_runner,
        flow_id="test-flow-001",
    )
    return flow
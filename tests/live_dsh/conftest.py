# tests/live_dsh/conftest.py — shared fixtures for the REAL bridge harness
#
# TEST-SUPPORT ONLY. NOT production code.

import os
import sys
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    Task, Delegation, TaskResult, ORCHESTRATOR, SPECIALIST_ROLES,
)
from orchestrator.dsh import (
    FakeSubagentBackend, DelegationResult, RoleResolver,
)
from .backend_kind import BackendKind, probe_backend_kind
from .adapters import build_role_adapter, ROLE_ADAPTERS
from .real_backend import RealDSHBackend, DSHBridgeResponse
from .contract import BuildInvocation, DSHInvocation, STOP_COMPLETED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_delegation(*, id="delegation-live-dsh", task="live-001",
                    action="read", target="multi-agent-harness/**",
                    environment="dev",
                    scope_operations=("read", "write", "code_write"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    status="ACTIVE", version=1):
    return Delegation(
        id=id, principal="human", delegate=ORCHESTRATOR,
        project="multi-agent-harness", task=task,
        action=action, target=target, environment=environment,
        scope_operations=tuple(scope_operations),
        scope_resources=tuple(scope_resources),
        scope_environments=tuple(scope_environments),
        expires_at="", status=status, version=version,
    )


def make_task(task_id="live-role-task", objective="engineering",
              role="cto", scope=("agents/**",)):
    return Task(
        task_id=task_id, objective=objective, assigned_role=role,
        scope=tuple(scope), risk_metadata="LOW",
        project="multi-agent-harness",
    )


def make_task_result(task_id, role, *, status="SUCCEEDED",
                     findings=("analysis complete",),
                     evidence=("artifact:analysis",)):
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        confidence="MEDIUM",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def resolver():
    return RoleResolver()


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def task():
    return make_task()


@pytest.fixture()
def backend_kind():
    return probe_backend_kind()


@pytest.fixture()
def fake_backend():
    """A fresh FakeSubagentBackend with a default handler for subagent_cto."""
    backend = FakeSubagentBackend()

    def _handler(instance, prompt):
        return DelegationResult(
            output="ok",
            structured={
                "task_id": prompt.get("task_id", ""),
                "assigned_role": instance.role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": [f"{instance.role}: analysis complete"],
                "evidence": ["artifact:analysis"],
                "recommendation": "proceed",
                "reported_at": "2026-08-30T00:00:00Z",
            })
    backend.register("subagent_cto", _handler)
    return backend


@pytest.fixture()
def recording_bridge():
    """A stub DSHBridgeDispatch that records calls and returns a fixed
    successful structured result. NEVER performs a live dispatch."""
    calls = []

    def _dispatch(invocation, instance):
        calls.append({"invocation": invocation.to_dict(), "role": instance.role})
        return DSHBridgeResponse(
            run_id="test-run-001",
            output="task completed",
            structured={
                "task_id": invocation.to_dict().get("description", ""),
                "assigned_role": instance.role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": [f"{instance.role}: analysis complete"],
                "evidence": ["artifact:test"],
                "recommendation": "proceed",
                "reported_at": "2026-08-30T00:00:00Z",
            },
            stop_reason=STOP_COMPLETED,
        )

    return _dispatch, calls


@pytest.fixture()
def real_backend(recording_bridge):
    """A RealDSHBackend with the recording bridge (require_marker=False to
    allow contract testing without a live mount)."""
    dispatch, _ = recording_bridge
    return RealDSHBackend(dispatch, require_marker=False)


@pytest.fixture(params=[
    (rid, f"role-{rid}")
    for rid in SPECIALIST_ROLES
])
def role_adapter(request):
    """Parametrized fixture: yields each of the 15 role adapters.

    The second element is the Agent Preset the role selects: 0.2.1-rc.2 has
    ONE delegation tool, so the preset is what tells the roles apart.
    """
    role, expected_preset = request.param
    adapter = build_role_adapter(role)
    return adapter, expected_preset
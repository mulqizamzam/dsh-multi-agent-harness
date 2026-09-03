# tests/orchestrator/dsh/conftest.py — fixtures for the DSH integration adapter
#
# TEST-SUPPORT ONLY. Not production code.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, Task  # noqa: E402
from orchestrator.dsh import (  # noqa: E402
    DelegationClient,
    FakeSubagentBackend,
    RoleResolver,
)


@pytest.fixture()
def resolver():
    """A RoleResolver over the real D4/D7 approved mapping."""
    return RoleResolver()


@pytest.fixture()
def backend():
    """A fresh fake subagent backend (no scripted handlers by default)."""
    return FakeSubagentBackend()


@pytest.fixture()
def client(backend):
    """A DelegationClient wired to the fake backend."""
    return DelegationClient(backend=backend)


@pytest.fixture()
def delegation_factory():
    """Factory for a valid scoped Human → orchestrator Delegation."""
    def _make(*, task_id="t-1", resources=("multi-agent-harness/**",),
              status="ACTIVE", expires_at="", revoked=False):
        return Delegation(
            id=f"delegation-{task_id}",
            principal="human",
            delegate="orchestrator",
            project="multi-agent-harness",
            task=task_id,
            action="write",
            target="multi-agent-harness/**",
            environment="dev",
            scope_operations=("write", "read"),
            scope_resources=resources,
            scope_environments=("dev",),
            status=status,
            expires_at=expires_at,
            revoked_at="" if not revoked else "2026-08-31T00:00:00Z",
        )
    return _make


@pytest.fixture()
def task_factory():
    """Factory for a scoped Task assigned to one role."""
    def _make(*, task_id="t-1", role="cto", objective="engineering task",
              scope=("multi-agent-harness/**",),
              risk_metadata="LOW", expected_output="report"):
        return Task(task_id=task_id, objective=objective,
                    assigned_role=role, scope=scope,
                    risk_metadata=risk_metadata,
                    expected_output=expected_output)
    return _make
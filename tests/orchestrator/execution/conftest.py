# tests/orchestrator/execution/conftest.py — fixtures + builders for the
# runtime execution assurance tests. TEST-SUPPORT ONLY (not production).

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# Force the project root to the FRONT unconditionally: pytest inserts the
# test-dir basedir (tests/orchestrator) into sys.path ahead of the project
# root, and `orchestrator` is a namespace package — the test dir would
# otherwise shadow the real `orchestrator.execution` package.
sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation  # noqa: E402
from orchestrator.execution import ExecutionRequest, ExecutionEngine  # noqa: E402


def make_delegation(task_id="exec-001", *, id="delegation-exec-001",
                    scope_operations=("write", "read", "code_write"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    expires_at="", status="ACTIVE", **overrides) -> Delegation:
    kw = dict(
        id=id, principal="human", delegate="orchestrator",
        project="multi-agent-harness", task=task_id,
        action="write", target="agents/**", environment="dev",
        scope_operations=tuple(scope_operations),
        scope_resources=tuple(scope_resources),
        scope_environments=tuple(scope_environments),
        expires_at=expires_at, status=status, version=1,
    )
    kw.update(overrides)
    return Delegation(**kw)


def make_request(task_id="exec-001", *, action="write",
                 target="agents/cto/output.txt", environment="dev",
                 delegation=None, expected_outcome=None,
                 revocation_list=(), approval_reference="",
                 state_version=0, max_attempts=1, **overrides) -> ExecutionRequest:
    kw = dict(
        task_id=task_id, actor="orchestrator", action=action, target=target,
        environment=environment, delegation=delegation,
        expected_outcome=expected_outcome or {},
        revocation_list=tuple(revocation_list),
        approval_reference=approval_reference,
        project="multi-agent-harness", state_version=state_version,
        max_attempts=max_attempts,
    )
    kw.update(overrides)
    return ExecutionRequest(**kw)


@pytest.fixture()
def ws(o3_daemon_ws):
    """A temporary workspace base that IS the O3 daemon root (O3 Phase B)."""
    wsdir, _c, _d = o3_daemon_ws
    return wsdir


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def exec_request(delegation):
    return make_request(delegation=delegation,
                        expected_outcome={"exit_code": 0,
                                          "target": "agents/cto/output.txt"})


@pytest.fixture()
def engine_factory(ws):
    """A factory for ExecutionEngine bound to a tmp workspace base."""
    def _make(request, **kw):
        kw.setdefault("base", ws)
        return ExecutionEngine(request, **kw)
    return _make

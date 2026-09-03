# tests/scenarios/conftest.py — Test fixtures for scenario tests
#
# TEST-SUPPORT ONLY. Not production code.
#
# Provides the same fixture pattern as tests/orchestrator/runtime/conftest.py
# but adapted for use from the tests/scenarios/ package (which has __init__.py).
# IMPORTANT: All production imports are LAZY (inside fixtures) to avoid
# polluting the import order for other test suites (l3_runner is known to be
# order-sensitive).

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from tests.scenarios.scenario_helpers import (
    make_delegation, make_intake, make_execute_plan,
    make_subtask_result, StubSubtaskRunner, StubActionExecutor,
)


def _seed_project_state(ws):
    """Write an initial project state at version 1 through the O3 daemon
    (sanctioned project_write channel; O3 Phase B)."""
    from orchestrator.runtime.store import encode_project_state
    from orchestrator.foundation.state import ProjectState
    from control.execution_gate import project_write
    state_rel = "state/projects/multi-agent-harness.json"
    ps = ProjectState(project="multi-agent-harness")
    project_write(state_rel, encode_project_state(ps), base=ws,
                  expected_version=0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ws(o3_daemon_ws):
    """A temporary workspace that IS the O3 daemon root (O3 Phase B)."""
    wsdir, _client, _daemon = o3_daemon_ws
    _seed_project_state(wsdir)
    return wsdir


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def provider(delegation):
    """A MemoryDelegationProvider backed by the test delegation."""
    from orchestrator.runtime import MemoryDelegationProvider
    return MemoryDelegationProvider(delegation)


@pytest.fixture()
def subtask_runner():
    return StubSubtaskRunner()


@pytest.fixture()
def action_executor():
    return StubActionExecutor()


@pytest.fixture()
def flow(ws, provider, subtask_runner, delegation):
    """An ExecutionFlow wired to the temporary workspace and test stubs."""
    from orchestrator.runtime import ExecutionFlow, RuntimeStore
    store = RuntimeStore(base=ws)
    store.ensure_dirs()
    flow = ExecutionFlow(
        project="multi-agent-harness",
        base=ws,
        provider=provider,
        store=store,
        subtask_runner=subtask_runner,
        flow_id="scn-test",
    )
    return flow
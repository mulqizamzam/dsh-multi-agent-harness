# tests/orchestrator/entrypoint/conftest.py — Test fixtures for the front-door
# (orchestrator.entrypoint) security + integration validation suite.
#
# Phase 5 / Session B. TEST-SUPPORT ONLY. Not production code.
#
# Fixtures live here. The shared helper functions/classes that were formerly
# defined here now live in the uniquely-named sibling module `_helpers` (see
# its docstring for the import-isolation rationale). They are re-exported here
# so that `from conftest import X` still works for any code that has not yet
# been migrated to `from _helpers import X`.
#
# Nothing here mints authority, writes the registry, or bypasses a gate.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.entrypoint import (
    FrontDoorRequest,
    run_front_door,
)
from orchestrator.production import (
    ProductionRun,
)
from orchestrator.runtime import (
    MemoryDelegationProvider,
)
from _helpers import (
    make_delegation,
    make_subtask_result,
    make_provider,
    StubSubtaskRunner,
    StubActionExecutor,
    seed_state,
)


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
def valid_request():
    """A well-shaped front-door request (valid objective + scope + delegation
    id). The registry resolution is provided by an injected provider."""
    return FrontDoorRequest(
        objective="engineering",
        scope=("agents/cto/output.txt",),
        delegation_id="delegation-prod-001",
    )


__all__ = [
    "make_delegation", "make_subtask_result", "make_provider",
    "StubSubtaskRunner", "StubActionExecutor", "seed_state",
]
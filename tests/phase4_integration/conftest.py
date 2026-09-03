# tests/phase4_integration/conftest.py — Shared fixtures for P4I-01..P4I-07.
#
# TEST-SUPPORT ONLY. Not production code.
#
# Wires the REAL Phase-4 production modules into the tests: a temporary
# workspace, a valid delegation/provider, and deterministic stub runners.
# All production imports are LAZY (inside fixtures) to keep import order
# predictable across the suite.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.phase4_integration.helpers import (  # noqa: E402
    make_delegation, make_workspace, StubSubtaskRunner, StubActionExecutor,
)


@pytest.fixture()
def ws(o3_daemon_ws):
    """A temporary workspace that IS the O3 daemon root (O3 Phase B).

    Protected state (state/registry/, state/projects/, audit/) is
    daemon-owned; the workspace root doubles as the daemon root."""
    wsdir, _client, _daemon = o3_daemon_ws
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

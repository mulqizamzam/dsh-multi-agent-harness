# tests/integration/conftest.py — shared fixtures for integration tests.
#
# TEST-SUPPORT ONLY. Not production code.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TESTS_DIR = os.path.join(_PROJECT_ROOT, "tests")
_INT_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (_PROJECT_ROOT, _TESTS_DIR, _INT_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from harness import IntegrationHarness  # noqa: E402


@pytest.fixture()
def harness(tmp_path):
    """An IntegrationHarness wired against a fresh temporary workspace."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    h = IntegrationHarness(str(ws))
    return h


@pytest.fixture()
def ws(harness):
    """The harness workspace path (string)."""
    return harness.ws


@pytest.fixture()
def audit_path(harness):
    """Path to the workspace audit log."""
    return os.path.join(harness.ws, "audit", "events.jsonl")

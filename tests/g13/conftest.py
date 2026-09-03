"""Shared fixtures for the G13 (Session D) verification suite.

The G13 suite verifies prompt-injection / external-content resistance of the
PROJECT CONTROL PLANE (L1) deterministically. It does NOT dispatch any live
DSH child (no mount — DSH-native resistance is UNKNOWN, not PASS).

Fixtures here build PRODUCTION control-plane objects (control.*,
orchestrator.foundation.state, orchestrator.dsh.context, audit.helpers) so the
tests exercise the real enforcement points, not only the reference
tests/control_plane.py primitives.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from orchestrator.foundation.contracts import Delegation, ORCHESTRATOR


def make_delegation(*, id="delegation-g13", action="write",
                    target="agents/**", environment="dev",
                    scope_operations=("read", "write", "code_write"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    status="ACTIVE", version=1, expires_at="",
                    requires_approval=(), approval_reference=""):
    """A valid Human → orchestrator Delegation (production contract)."""
    return Delegation(
        id=id, principal="human", delegate=ORCHESTRATOR,
        project="multi-agent-harness", task="g13-task",
        action=action, target=target, environment=environment,
        scope_operations=tuple(scope_operations),
        scope_resources=tuple(scope_resources),
        scope_environments=tuple(scope_environments),
        expires_at=expires_at, status=status, version=version,
        requires_approval=tuple(requires_approval),
        approval_reference=approval_reference,
    )


@pytest.fixture
def delegation():
    """A valid ACTIVE delegation for gate-ALLOW positive controls."""
    return make_delegation()


@pytest.fixture
def tmp_workspace(tmp_path):
    """A throwaway workspace with protected-path-shaped directories, so
    protected-state-mutation tests run against a scratch tree (never the real
    state/registry/ or audit/)."""
    registry = tmp_path / "state" / "registry"
    audit = tmp_path / "audit"
    agents = tmp_path / "agents"
    for d in (registry, audit, agents):
        d.mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def channel_table():
    """C1..C7 channel table (payloads.py)."""
    from .payloads import CHANNELS
    return CHANNELS


@pytest.fixture
def vector_table():
    """V1..V8 vector table (payloads.py)."""
    from .payloads import VECTORS
    return VECTORS

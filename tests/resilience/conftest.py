"""Resilience test fixtures (Phase 5 / Session D — G4 + G9).

TEST-SUPPORT ONLY. NOT production code.

Fixtures and failure-injecting subtask runners that exercise the EXISTING
runtime (ExecutionFlow / ExecutionEngine / DelegationClient /
control.execution_gate) with no architecture or DSH change, and no weakening
of any security control.

G4 (provider 429 / rate-limit) modeling note
--------------------------------------------
A live provider rate limit surfaces as an *environment-class* failure
(Runbook 07/08 classification). In the deterministic runtime the adapter
raises a typed ``DelegationTimeout`` when a child does not settle within its
deadline; a provider 429 manifests the same way at dispatch. This suite adds
a test-support ``RateLimited`` exception that SUBCLASSES ``DelegationTimeout``
so the EXISTING ``collection.classify_adapter_failure`` maps it to the
existing ``environment`` class without changing or weakening any classifier.
No production classification is modified; the rate-limit class is expressed
through the existing environment mapping.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest

from orchestrator.foundation.contracts import Task, TaskResult, TaskIntake, Delegation
from orchestrator.dsh.exceptions import DelegationTimeout, DelegationAborted


# ---------------------------------------------------------------------------
# Test-support rate-limit type (G4). Maps to the EXISTING environment class
# via inheritance from DelegationTimeout — no production classification
# change, no weakening. Deterministic stand-in for a live HTTP 429.
# ---------------------------------------------------------------------------

class RateLimited(DelegationTimeout):
    """A provider rate-limit (HTTP 429) modeled as an environment-class child
    dispatch failure.

    Subclasses ``DelegationTimeout`` (child did not settle within its tool-call
    deadline): the EXISTING ``collection.classify_adapter_failure`` therefore
    maps it to ``("environment", ...)`` unchanged. The 429 diagnostic is kept
    on the exception for the recovery record.
    """

    def __init__(self, reason: str = "provider rate limit", *, status: int = 429,
                 diagnostic: str = ""):
        self.status = status
        self.diagnostic = diagnostic or f"HTTP {status}: {reason}"
        super().__init__(f"{self.diagnostic}")


def make_task(task_id="task-1", role="cto", scope=("agents/cto/output.txt",)):
    return Task(task_id=task_id, objective="objective", assigned_role=role,
                scope=scope, expected_output="ok", risk_metadata="LOW",
                project="multi-agent-harness")


def make_result(task_id, role, status="SUCCEEDED"):
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status, confidence="MEDIUM",
        findings=["ok"], evidence=[], risks=[], assumptions=[], unresolved_items=[],
        actions_taken=[], recommendation="", reported_at="2026-08-31T00:00:00Z")


@pytest.fixture
def delegation():
    return Delegation(
        id="delegation-res-001", principal="human", delegate="orchestrator",
        project="multi-agent-harness",
        scope_operations=("write", "read", "analysis"),
        scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        scope_environments=("dev",),
        status="ACTIVE", expires_at=None,
    )


@pytest.fixture
def intake():
    return TaskIntake(
        objective="engineering analysis",
        scope=("agents/cto/output.txt",),
        required_authority_context="delegation-res-001",
        expected_outcome="exit_code=0",
        project="multi-agent-harness",
    )


@pytest.fixture
def ws(o3_daemon_ws):
    """A throwaway workspace that IS the O3 daemon root (O3 Phase B).
    Protected state (state/registry/, audit/, state/projects/) is daemon-owned
    and routed through the O3 client."""
    wsdir, _client, _daemon = o3_daemon_ws
    return wsdir


# ---------------------------------------------------------------------------
# Failure-injecting subtask runners
#
# These raise the TYPED adapter vocabulary (orchestrator.dsh.exceptions) so
# the EXISTING runtime classifier is what maps them — the tests exercise
# production classification, not a test-side guess.
# ---------------------------------------------------------------------------

def runner_success(task, delegation):
    return make_result(task.task_id, task.assigned_role, "SUCCEEDED")


def runner_timeout(task, delegation):
    raise DelegationTimeout("child timed out")


def runner_abort(task, delegation):
    raise DelegationAborted("child aborted")


def runner_429(task, delegation):
    """Provider 429 as a typed environment-class failure (G4)."""
    raise RateLimited("provider rate limit", status=429)


def runner_unclassified(task, delegation):
    """A failure the adapter vocabulary does NOT recognize. Must classify as
    ``unknown`` and escalate — never guessed (Runbook 08)."""
    raise RuntimeError("429: provider rate limit")


def runner_malformed(task, delegation):
    return {"not": "a TaskResult"}


def runner_failed(task, delegation):
    return make_result(task.task_id, task.assigned_role, "FAILED")


def runner_partial_batch(plan):
    """A runner factory producing mixed success/failure for a parallel batch."""

    def _run(task, delegation):
        if task.task_id.endswith(":kai"):
            return make_result(task.task_id, "kai", "FAILED")
        return make_result(task.task_id, task.assigned_role, "SUCCEEDED")

    return _run


# ---------------------------------------------------------------------------
# Flow construction helper
# ---------------------------------------------------------------------------

def build_flow(delegation, ws, runner, **overrides):
    """Build an ExecutionFlow wired to a temp workspace with a given subtask
    runner (deterministic, in-process — no live DSH)."""
    from orchestrator.runtime import ExecutionFlow, MemoryDelegationProvider
    return ExecutionFlow(
        base=ws,
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=runner,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Stale-state injector (pre_execute hook that bumps the state version)
# ---------------------------------------------------------------------------

def bump_state_version_hook(base, project="multi-agent-harness"):
    """A pre_execute hook that advances the project state version so the
    execution-time check_current fails (THREAT-022)."""
    from control.execution_gate import project_write
    from state.helpers.version_check import read_version, bump_version

    def _hook():
        from control.execution_gate import project_read
        result = project_read(f"state/projects/{project}.json", base=base)
        doc = dict(result.get("data") or {})
        doc["version"] = (result.get("version") or 0) + 1
        # Simulate a parallel writer through the O3 daemon (sanctioned
        # project_write channel — no direct-fs write to a protected root).
        project_write(f"state/projects/{project}.json", doc, base=base,
                      expected_version=(result.get("version") or 0))

    return _hook

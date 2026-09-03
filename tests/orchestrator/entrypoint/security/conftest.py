# tests/orchestrator/entrypoint/security/conftest.py — Independent fixtures for
# the front-door adversarial security/contract package.
#
# TEST-SUPPORT ONLY. Not production code. Nothing here mints authority, writes
# the registry, or bypasses a gate. The package stays valid even before the
# front door exists: the `front_door` fixture reports NOT_YET_AVAILABLE (skip)
# when orchestrator.entrypoint is not importable, and every test guards its
# imports through that fixture so collection never fails on a missing module.

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ._availability import front_door_available, _NOT_YET_AVAILABLE  # noqa: E402


# ---------------------------------------------------------------------------
# Delegation / result / runner helpers (mirror of the production suite's
# conftest, kept self-contained so the adversarial package is independent).
# ---------------------------------------------------------------------------

def make_delegation(task_id="task-1", *, id="delegation-prod-001",
                    action="write", target="agents/**", environment="dev",
                    scope_operations=("write", "read", "code_write",
                                      "analysis"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    expires_at="", status="ACTIVE", **overrides):
    from orchestrator.foundation.contracts import Delegation
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


def make_subtask_result(task_id, role, *, recommendation="",
                        findings=("analysis complete",), evidence=(),
                        status="SUCCEEDED", confidence="MEDIUM",
                        risks=(), unresolved_items=()):
    from orchestrator.foundation.contracts import TaskResult
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        recommendation=recommendation, confidence=confidence,
        risks=risks, unresolved_items=unresolved_items,
    )


def make_provider(delegation=None, revoked=()):
    """MemoryDelegationProvider (a real DelegationProvider subclass) so the
    front door's isinstance(provider, DelegationProvider) check passes.
    delegation=None simulates an empty registry (fail-closed)."""
    from orchestrator.runtime import MemoryDelegationProvider
    return MemoryDelegationProvider(delegation, revoked=tuple(revoked))


class StubSubtaskRunner:
    """Deterministic subtask runner returning pre-configured results."""

    def __init__(self, results=None, default_recommendation="recommend",
                 default_evidence=("artifact:analysis",)):
        self._results = results or {}
        self._default_recommendation = default_recommendation
        self._default_evidence = default_evidence
        self.calls = []

    def add(self, role, result):
        self._results[role] = result

    def __call__(self, task, delegation):
        self.calls.append(task)
        key = task.assigned_role
        if key in self._results:
            return self._results[key]
        return make_subtask_result(
            task.task_id, task.assigned_role,
            status="SUCCEEDED",
            findings=(f"{key}: analysis",),
            evidence=self._default_evidence,
            recommendation=self._default_recommendation,
            confidence="MEDIUM",
        )


class StubActionExecutor:
    """Deterministic action executor returning pre-configured observed
    outcomes. Tracks calls and can fail a configurable number of times."""

    def __init__(self, observed=None, fail_count=0):
        self.observed = observed or {"exit_code": 0}
        self.fail_count = fail_count
        self.calls = []

    def __call__(self, plan):
        self.calls.append(plan)
        if self.fail_count > 0:
            self.fail_count -= 1
            raise RuntimeError("simulated execution failure")
        out = dict(self.observed)
        if "target" not in out:
            out["target"] = getattr(plan, "target", "")
        return out


def seed_state(base: str, project: str = "multi-agent-harness") -> None:
    """Seed the initial project state document (version 1) in a workspace."""
    from orchestrator.runtime import RuntimeStore
    store = RuntimeStore(base=base, project=project)
    store.ensure_dirs()
    store.ensure_state()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ws(tmp_path):
    """A temporary workspace with the required directory structure."""
    wsdir = tmp_path / "workspace"
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "docs"):
        (wsdir / sub).mkdir(parents=True, exist_ok=True)
    return str(wsdir)


@pytest.fixture()
def front_door():
    """The front-door module under test, or NOT_YET_AVAILABLE.

    Guards every import through this fixture so the package collects cleanly
    (and reports NOT_YET_AVAILABLE) before Session Front Door V1 exists.
    """
    if not front_door_available():
        pytest.skip(_NOT_YET_AVAILABLE)
    import orchestrator.entrypoint as fd
    return fd


@pytest.fixture()
def delegation():
    return make_delegation()


@pytest.fixture()
def provider(delegation):
    return make_provider(delegation)


@pytest.fixture()
def subtask_runner():
    return StubSubtaskRunner()


@pytest.fixture()
def action_executor():
    return StubActionExecutor()


def run_request(front_door, *, objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                constraints=(), expected_outcome="",
                project="multi-agent-harness", base=None,
                environment="dev", provider=None,
                subtask_runner=None, action_executor=None,
                request_dict=None):
    """Run one front-door request with injected stubs; returns the
    FrontDoorResult. Accepts either explicit kwargs or a raw request dict."""
    if request_dict is not None:
        return front_door.run_front_door(
            request_dict, provider=provider, subtask_runner=subtask_runner,
            action_executor=action_executor)
    req = front_door.FrontDoorRequest(
        objective=objective, scope=tuple(scope),
        delegation_id=delegation_id, constraints=tuple(constraints),
        expected_outcome=expected_outcome, project=project, base=base,
        environment=environment,
    )
    return front_door.run_front_door(
        req, provider=provider, subtask_runner=subtask_runner,
        action_executor=action_executor)


__all__ = [
    "make_delegation", "make_subtask_result", "make_provider",
    "StubSubtaskRunner", "StubActionExecutor", "seed_state", "run_request",
    "front_door_available", "_NOT_YET_AVAILABLE",
]

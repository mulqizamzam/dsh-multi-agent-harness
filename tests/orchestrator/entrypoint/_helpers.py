# tests/orchestrator/entrypoint/_helpers.py — Shared helper functions/classes
# for the front-door (orchestrator.entrypoint) security + integration
# validation suite.
#
# Phase 5 / Session B. TEST-SUPPORT ONLY. Not production code.
#
# WHY THIS MODULE EXISTS (import-isolation fix):
#   Under pytest's default prepend import mode, every conftest.py in the tree
#   is imported as the SAME top-level module name `conftest` (they are not
#   packages — there is no __init__.py between tests/ and these dirs). The
#   last conftest.py loaded during collection wins `sys.modules["conftest"]`,
#   so a test doing `from conftest import make_delegation` can resolve to a
#   DIFFERENT directory's conftest depending on collection order. That made the
#   full-suite run (tests/) fail while the entrypoint-only run passed:
#   e.g. tests/orchestrator/runtime/conftest.py shadowed the entrypoint
#   conftest, producing `ImportError: cannot import name 'seed_state'`.
#
#   The helpers therefore live in this uniquely-named module — no other
#   `_helpers` module exists anywhere in the tree — so `from _helpers import X`
#   is unambiguous in every run scope. The sibling conftest.py imports them
#   from here and re-exports them; it keeps only the pytest fixtures.
#
#   Nothing here mints authority, writes the registry, or bypasses a gate.

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    TaskResult,
)
from orchestrator.runtime import (
    MemoryDelegationProvider,
    FileDelegationProvider,
)


def make_delegation(task_id="task-1", *, id="delegation-prod-001",
                    action="write", target="agents/**", environment="dev",
                    scope_operations=("write", "read", "code_write",
                                      "analysis"),
                    scope_resources=("agents/**", "docs/**",
                                     "multi-agent-harness/**"),
                    scope_environments=("dev",),
                    expires_at="", status="ACTIVE", **overrides):
    """Build a structured Delegation (same shape as the production suite)."""
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
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        recommendation=recommendation, confidence=confidence,
        risks=risks, unresolved_items=unresolved_items,
    )


def make_provider(delegation=None, revoked=()):
    """Build a MemoryDelegationProvider (a real DelegationProvider subclass)
    so the front door's isinstance(provider, DelegationProvider) check passes.
    ``delegation=None`` simulates an empty registry (fail-closed)."""
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
        return TaskResult(
            task_id=task.task_id,
            assigned_role=task.assigned_role,
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


__all__ = [
    "make_delegation", "make_subtask_result", "make_provider",
    "StubSubtaskRunner", "StubActionExecutor", "seed_state",
]

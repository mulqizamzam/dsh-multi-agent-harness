# tests/phase4_integration/helpers.py — Reusable builders + stubs (TEST-SUPPORT)
#
# Phase 4 / Session E — Integration Testing.
#
# Provides the same builder functions and stub classes used by the production
# runtime tests, but as an importable sibling module (tests/phase4_integration/
# is a package with __init__.py). All production imports are LAZY (inside
# functions) so this module is safe to import from any test file.

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Builders
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


def expected_synthesis(task_id, objective, risk, results) -> dict:
    """Replicate the flow's `_synthesize` output so a BadSector review's
    input_hash can be computed deterministically. TEST-SUPPORT ONLY."""
    return {
        "task_id": task_id,
        "objective": objective,
        "risk": risk,
        "findings": [f for tr in results for f in (tr.findings or ())],
        "recommendations": [tr.recommendation for tr in results
                            if tr.recommendation],
        "assumptions": [a for tr in results for a in (tr.assumptions or ())],
        "risks": [x for tr in results for x in (tr.risks or ())],
        "unresolved_items": [u for tr in results
                             for u in (tr.unresolved_items or ())],
        "roles": [tr.assigned_role for tr in results],
    }


def make_review_pass(task_id, objective, risk, results,
                     review_id="rev-p4i-001") -> dict:
    """Build a BadSector PASS whose input_hash matches the flow's synthesis
    hash (provenance verifiable)."""
    from control.badsector import _input_hash
    syn = expected_synthesis(task_id, objective, risk, results)
    return {
        "verdict": "PASS",
        "review_id": review_id,
        "input_hash": _input_hash(syn),
    }


# ---------------------------------------------------------------------------
# Stubs (deterministic in-process child execution — NOT live DSH)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Workspace seeding
# ---------------------------------------------------------------------------

def make_workspace(root: str) -> str:
    """Create the minimal workspace directory structure under `root`."""
    wsdir = os.path.join(str(root), "workspace")
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "agents/cfo", "agents/kai", "docs"):
        os.makedirs(os.path.join(wsdir, sub), exist_ok=True)
    return wsdir


def seed_project_state(ws: str) -> None:
    """Write an initial project state at version 1 through the O3 daemon
    (sanctioned project_write channel; O3 Phase B)."""
    from orchestrator.runtime.store import encode_project_state
    from orchestrator.foundation.state import ProjectState
    from control.execution_gate import project_write
    store_rel = "state/projects/multi-agent-harness.json"
    ps = ProjectState(project="multi-agent-harness")
    project_write(store_rel, encode_project_state(ps), base=ws,
                  expected_version=0)


def audit_classes(ws: str) -> set:
    """Return the set of audit event classes recorded in the workspace
    ledger (via the sanctioned RuntimeAudit read)."""
    from orchestrator.runtime import RuntimeAudit
    audit = RuntimeAudit(base=ws)
    return {e.get("event_class") for e in audit.read()}


def audit_events_of(ws: str, event_class: str) -> list:
    from orchestrator.runtime import RuntimeAudit
    audit = RuntimeAudit(base=ws)
    return [e for e in audit.read() if e.get("event_class") == event_class]


__all__ = [
    "make_delegation", "make_subtask_result", "expected_synthesis",
    "make_review_pass", "StubSubtaskRunner", "StubActionExecutor",
    "make_workspace", "seed_project_state", "audit_classes",
    "audit_events_of",
]

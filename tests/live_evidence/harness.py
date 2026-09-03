# tests/live_evidence/harness.py — LIVE DSH evidence harness (INT-11 / INT-12)
#
# TEST-SUPPORT ONLY. Not production code. Phase 3 / Session D3.
#
# The live run reuses the EXISTING production runtime for every control
# decision; this module only assembles the batch and records evidence:
#
#   INT-11 (parallel collection)
#     1. create independent subtasks (specialist roles, read-only scope)
#     2. verify dependency independence (assert_parallel_safe)
#     3. verify ownership / write-scope safety (assert_parallel_safe)
#     4. capture project-state version (RuntimeStore)
#     5. dispatch through the approved DSH adapter — the LIVE subagent_<id>
#        tool instances (D4/D7 composition) via the orchestrator session
#     6. execute concurrently (real parallel spawn)
#     7. collect structured TaskResult (collect_all + TaskResultCollector)
#     8. verify provenance (role identity, delegation id, run id)
#     9. verify post-batch state version (unchanged — no uncontrolled writes)
#
#   INT-12 (failure propagation)
#     1. run a parallel/child batch with ONE forced failure
#     2. verify deterministic propagation (SubtaskFailed, first-failure order)
#     3. verify no unsafe continuation (no partial success, no COMPLETE)
#     4. verify recovery/escalation path (typed failure_class → disposition)
#     5. verify no blind retry (recovery refuses without a NEW diagnosed cause)
#     6. verify no authority expansion (provenance shows same delegation scope)

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (  # noqa: E402
    Task, Delegation, ORCHESTRATOR, SPECIALIST_ROLES,
)
from orchestrator.runtime import (  # noqa: E402
    build_plans, assert_parallel_safe, SubtaskPlan, ParallelUnsafe,
)
from orchestrator.runtime.store import RuntimeStore  # noqa: E402
from orchestrator.runtime.collection import (  # noqa: E402
    collect_all, collect_one, classify_adapter_failure, CollectedResult,
)
from orchestrator.runtime.exceptions import (  # noqa: E402
    SubtaskFailed, StaleStateDetected, RuntimeFlowError,
)
from orchestrator.dsh import (  # noqa: E402
    RoleResolver, SubagentInstance, DelegationProvenance,
    TaskResultCollector, build_task_context,
)

# Version pin per docs/README.md + provenance module
DSH_VERSION_PIN = "deepseek-harness-0.1.1-rc.2"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class LiveEvidenceRun:
    """Container that accumulates one INT-11 / INT-12 evidence bundle."""
    phase: str = ""
    flow_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    subtasks: list = field(default_factory=list)       # task dicts
    plans: list = field(default_factory=list)          # plan dicts
    safety: dict = field(default_factory=dict)         # ParallelSafety dict
    delegation: dict = field(default_factory=dict)     # delegation dict
    held_version: int = 0
    post_batch_version: int = 0
    dispatch: list = field(default_factory=list)       # live tool-call records
    results: list = field(default_factory=list)        # CollectedResult dicts
    provenance: list = field(default_factory=list)     # provenance dicts
    outcome: str = ""                                  # COMPLETE / BLOCKED / RECOVERING / ESCALATED
    failure: dict = field(default_factory=dict)        # propagated failure record
    recovery: dict = field(default_factory=dict)       # recovery/escalation record
    security: dict = field(default_factory=dict)       # no-authority-expansion evidence
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "flow_id": self.flow_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "subtasks": list(self.subtasks),
            "plans": list(self.plans),
            "safety": dict(self.safety),
            "delegation": dict(self.delegation),
            "held_version": self.held_version,
            "post_batch_version": self.post_batch_version,
            "dispatch": list(self.dispatch),
            "results": list(self.results),
            "provenance": list(self.provenance),
            "outcome": self.outcome,
            "failure": dict(self.failure),
            "recovery": dict(self.recovery),
            "security": dict(self.security),
            "errors": list(self.errors),
        }


class LiveEvidenceHarness:
    """Builds an evidence bundle from a LIVE DSH parallel batch.

    The harness NEVER performs the dispatch itself — the orchestrator session
    drives the approved `subagent_<id>` tool instances and records each call
    into `run.dispatch`. The harness validates and collects what came back.
    """

    def __init__(self, *, ws: str, project: str = "multi-agent-harness"):
        self.ws = os.path.abspath(ws)
        self.project = project
        self.resolver = RoleResolver()
        self.collector = TaskResultCollector()
        self.store = RuntimeStore(base=self.ws, project=project)
        self._ensure_ws()

    # ------------------------------------------------------------------
    # workspace / state
    # ------------------------------------------------------------------
    def _ensure_ws(self):
        for d in ("state/registry", "state/projects", "audit",
                  f"audit/{self.project}"):
            os.makedirs(os.path.join(self.ws, d), exist_ok=True)
        if not os.path.exists(self.store.state_path()):
            from orchestrator.runtime.store import encode_project_state
            from orchestrator.foundation.state import ProjectState
            from control.execution_gate import write_through
            ps = ProjectState(project=self.project)
            write_through("write", self.store.state_rel,
                          encode_project_state(ps), base=self.ws)

    def capture_version(self) -> int:
        return self.store.current_version()

    def verify_version_unchanged(self, held: int) -> dict:
        """Re-read the on-disk version after a batch; drift = uncontrolled
        write (THREAT-021)."""
        current = self.store.current_version()
        return {
            "held_version": held,
            "post_batch_version": current,
            "unchanged": current == held,
        }

    # ------------------------------------------------------------------
    # adapter context (THREAT-020: authorized context only)
    # ------------------------------------------------------------------
    def build_task_context(self, *, task, delegation, extra: dict | None = None) -> dict:
        """Build the authorized task context via the adapter channel."""
        return build_task_context(task=task, delegation=delegation, extra=extra)

    # ------------------------------------------------------------------
    # restore helpers (manifest -> contract objects)
    # ------------------------------------------------------------------
    @staticmethod
    def _restore_task(d: dict) -> Task:
        from orchestrator.foundation.contracts import Task as _T
        return _T(
            task_id=d["task_id"], objective=d.get("objective", ""),
            assigned_role=d["assigned_role"],
            scope=tuple(d.get("scope") or ()),
            expected_output=d.get("expected_output", ""),
            risk_metadata=d.get("risk_metadata", "LOW"),
            project=d.get("project", "multi-agent-harness"),
        )

    @staticmethod
    def _restore_delegation(d: dict) -> Delegation:
        from orchestrator.foundation.contracts import Delegation as _D
        scope = d.get("scope") or {}
        return _D(
            id=d["id"], principal=d.get("principal", "human"),
            delegate=d.get("delegate", "orchestrator"),
            project=d.get("project", "multi-agent-harness"),
            task=d.get("task", ""), action=d.get("action", ""),
            target=d.get("target", ""), environment=d.get("environment", "dev"),
            scope_operations=tuple(d.get("scope_operations")
                                   or scope.get("operations") or ()),
            scope_resources=tuple(d.get("scope_resources")
                                  or scope.get("resources") or ()),
            scope_environments=tuple(d.get("scope_environments")
                                     or scope.get("environments") or ("dev",)),
            maximum_cost=d.get("maximum_cost") or scope.get("maximum_cost"),
            prohibited_actions=tuple(d.get("prohibited_actions") or ()),
            requires_approval=tuple(d.get("requires_approval") or ()),
            expires_at=d.get("expires_at") or "",
            approval_reference=d.get("approval_reference") or "",
            status=d.get("status", "ACTIVE"), version=d.get("version", 1),
        )

    # ------------------------------------------------------------------
    # delegation
    # ------------------------------------------------------------------
    def build_delegation(self, *, task_id: str = "live-task",
                         scope_operations=("read",),
                         scope_resources=("docs/**", "agents/**",
                                          "multi-agent-harness/**"),
                         id: str = "delegation-live-001") -> Delegation:
        return Delegation(
            id=id, principal="human", delegate=ORCHESTRATOR,
            project=self.project, task=task_id,
            action="read", target="multi-agent-harness/**",
            environment="dev",
            scope_operations=tuple(scope_operations),
            scope_resources=tuple(scope_resources),
            scope_environments=("dev",),
            expires_at="", status="ACTIVE", version=1,
        )

    # ------------------------------------------------------------------
    # subtasks + parallel safety (contract §6)
    # ------------------------------------------------------------------
    def build_subtasks(self, specs) -> list[Task]:
        """Build independent read-only subtasks.

        specs: [(task_id, role, objective, expected_output, scope), ...]
        """
        tasks = []
        for (tid, role, objective, expected_output, scope) in specs:
            if role not in SPECIALIST_ROLES:
                raise ValueError(f"{role} is not a specialist role")
            tasks.append(Task(
                task_id=tid, objective=objective, assigned_role=role,
                scope=tuple(scope), expected_output=expected_output,
                risk_metadata="LOW", project=self.project,
            ))
        return tasks

    def verify_parallel_safe(self, subtasks, *, held_version: int = 0,
                             depends_on: dict | None = None,
                             writes_by_task: dict | None = None) -> dict:
        """Build plans and run assert_parallel_safe; return the safety dict.

        Dependency independence, exclusive single-owner task ownership, and
        read-only specialist scope are all verified by the production runtime's
        assert_parallel_safe BEFORE any child starts (fail-closed).
        """
        depends_on = depends_on or {}
        writes_by_task = writes_by_task or {}
        plans = []
        for st in subtasks:
            plans.append(SubtaskPlan(
                task=st, owner=st.assigned_role,
                reads=tuple(st.scope or ()),
                writes=tuple(writes_by_task.get(st.task_id, ())),
                depends_on=tuple(depends_on.get(st.task_id, ())),
            ))
        safety = assert_parallel_safe(plans, held_version=held_version)
        return {
            "safe": safety.safe,
            "reason": safety.reason,
            "task_ids": list(safety.task_ids),
            "owners": list(safety.owners),
            "read_scopes": list(safety.read_scopes),
            "held_version": safety.held_version,
            "plans": [p.to_dict() for p in plans],
        }

    # ------------------------------------------------------------------
    # live dispatch records (written by the orchestrator session)
    # ------------------------------------------------------------------
    def record_dispatch(self, *, tool_name: str, role: str, task_id: str,
                        run_id: str, started_at: str, settled_at: str,
                        stop_reason: str, output: str = "",
                        structured: dict | None = None,
                        diagnostic: str = "") -> dict:
        rec = {
            "tool_name": tool_name,
            "role": role,
            "task_id": task_id,
            "run_id": run_id,
            "provider": "spawn",
            "background_mode": "continuable",
            "max_depth": 1,
            "started_at": started_at,
            "settled_at": settled_at,
            "stop_reason": stop_reason,
            "output": output,
            "structured": structured,
            "diagnostic": diagnostic,
            "live": True,  # real DSH tool-subagent instance (approved D4/D7)
        }
        return rec

    # ------------------------------------------------------------------
    # collection + provenance (production runtime)
    # ------------------------------------------------------------------
    def collect(self, dispatch: list[dict], subtasks: list[Task],
                task_index: dict[str, Task]) -> list[CollectedResult]:
        """Validate the live structured outputs into CollectedResults.

        Each raw dict is first validated through the adapter's
        TaskResultCollector (schema + contract + role identity), producing a
        TaskResult object that collect_one/collect_all accept.

        Raises SubtaskFailed on the FIRST failing child in batch order
        (deterministic propagation — INT-12).
        """
        task_results = []
        for rec in dispatch:
            structured = rec.get("structured")
            task_id = rec.get("task_id", "")
            task = task_index.get(task_id)
            if structured is None or task is None:
                task_results.append(None)
            else:
                # Validate raw dict through the adapter collector (contract +
                # schema) to produce a TaskResult object.
                tr = self.collector.collect(structured, task=task)
                task_results.append(tr)
        collected = collect_all(task_results, tuple(subtasks))
        return collected

    def validate_structured(self, structured: dict, *, task: Task):
        """Validate one live child's structured output against the TaskResult
        contract + schema, preserving role identity (adapter path)."""
        return self.collector.collect(structured, task=task)

    def build_provenance(self, *, task: Task, delegation: Delegation,
                         rec: dict) -> dict:
        """Build the adapter provenance stamp for one live delegation."""
        instance = self.resolver.resolve(task.assigned_role)
        prov = DelegationProvenance.build(
            delegation=delegation, task=task, instance=instance,
            started_at=rec.get("started_at", ""),
            settled_at=rec.get("settled_at", ""),
            result_status=rec.get("structured", {}).get("status", ""),
        )
        d = prov.to_dict()
        # overlay the real live run id from the tool call
        if rec.get("run_id"):
            d["run_id"] = rec["run_id"]
        d["stop_reason"] = rec.get("stop_reason", "completed")
        d["live"] = True
        return d

    # ------------------------------------------------------------------
    # evidence emission
    # ------------------------------------------------------------------
    def emit(self, run: LiveEvidenceRun, *, path: str) -> str:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)
        return path

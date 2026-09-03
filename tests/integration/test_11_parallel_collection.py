# INT-11 — Parallel task result collection
#
# Proves that multiple tasks can be routed to the minimum specialist set,
# collected with versioned state, and that parallel collection with version
# conflict is detected.
#
# Modules integrated: Routing (select_agents, route_tasks) + TaskResult
# (schema validation) + ProjectState (versioned CAS) + audit
# Invariants: THREAT-021, PST-001/002, AUTH-INV-04

import json
import os

import pytest

from orchestrator.foundation import (
    Task, TaskResult, select_agents, route_tasks, validate_no_fanout,
    RoutingError,
)


class TestINT11ParallelCollection:
    def test_routing_minimum_set_no_fanout(self):
        """Routing selects the minimum specialist set; no blanket fan-out."""
        tasks = [
            Task(task_id="t-1", objective="engineering", assigned_role="cto"),
            Task(task_id="t-2", objective="finance", assigned_role="cfo"),
            Task(task_id="t-3", objective="research", assigned_role="kai"),
        ]
        routed = route_tasks(tasks)
        assert routed["t-1"] == ("cto",)
        assert routed["t-2"] == ("cfo",)
        assert routed["t-3"] == ("kai",)
        # No single selection contains all specialists.
        for sel in routed.values():
            validate_no_fanout(sel)

    def test_secondary_minimum_set(self):
        """pricing → CFO + Kai (minimum set, not a blanket fan-out)."""
        t = Task(task_id="t-p", objective="pricing", assigned_role="cfo")
        sel = select_agents(t)
        assert set(sel) == {"cfo", "kai"}
        assert len(sel) == 2

    def test_unknown_domain_raises(self):
        """An unroutable domain is rejected (no silent fallback)."""
        t = Task(task_id="t-x", objective="quantum-cooking", assigned_role="cto")
        with pytest.raises(RoutingError):
            select_agents(t)

    def test_parallel_results_schema_validated(self, harness):
        """Parallel-collected results are schema-validated TaskResults."""
        results = [
            TaskResult(task_id="t-1", assigned_role="cto", status="SUCCEEDED",
                       evidence=("e1",), confidence="HIGH"),
            TaskResult(task_id="t-2", assigned_role="cfo", status="SUCCEEDED",
                       evidence=("e2",), confidence="HIGH"),
            TaskResult(task_id="t-3", assigned_role="kai", status="SUCCEEDED",
                       evidence=("e3",), confidence="HIGH"),
        ]
        import jsonschema
        proj_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        schema = json.load(open(os.path.join(proj_root, "schemas",
                                             "task-result.schema.json")))
        for r in results:
            jsonschema.Draft202012Validator(schema).validate(r.to_dict())

    def test_parallel_collection_version_conflict(self, harness):
        """Two parallel collectors writing project state with the same expected
        version → the second is DENIED (THREAT-021)."""
        h = harness
        d = h.build_delegation()
        # Simulate two collectors reading the same version (say v1).
        v_before = h.project_version()
        # Collector A commits (v -> v+1)
        h.transition("int-11", "PLANNED", authority=d)
        v_after_a = h.project_version()
        assert v_after_a == v_before + 1
        # Collector B still holds v_before (stale) → DENIED
        from orchestrator.foundation import StateTransitionError
        with pytest.raises(StateTransitionError, match="stale"):
            h.transition("int-11", "DELEGATED", authority=d,
                         expected_project_version=v_before)
        assert h.project_version() == v_after_a

    @pytest.mark.skip(reason="requires Phase-2C — live DSH subagent execution")
    def test_live_parallel_subagent_collection(self, harness):
        """SKELETON: real parallel subagent execution + result collection.
        Blocked on Phase-2C."""
        raise NotImplementedError("Phase-2C: live parallel subagents")
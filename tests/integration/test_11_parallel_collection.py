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

    def test_live_parallel_subagent_collection(self, harness):
        """LIVE variant (D4/D7 mounted): parallel real subagent execution with
        result collection — two session-recorded REAL child results (cfo+kai,
        the pricing minimum set) flow through RealDSHBackend (marker-gated)
        into one ExecutionFlow; both must be collected.

        Conditional gate, not a skeleton: without the mount marker or the
        session-recorded results the test SKIPS with that reason (pytest
        cannot dispatch a DSH child itself — the dispatch plane is the
        orchestrator session, tests/live_evidence/harness.py:116-118).
        Offline contract: the tests above (THREAT-021 CAS) and
        tests/scenarios/test_scenarios.py SCN-004.
        """
        from tests.live_dsh.live_gate import (live_available, skip_reason,
                                              load_recorded)
        if not live_available("INT-11"):
            pytest.skip(skip_reason("INT-11"))
        live = load_recorded("DSH_LIVE_RESULT_INT11",
                             "INT-11.live_results.json")
        assert live, "live gate on but no session-recorded INT-11 results"
        by_task = {k: v for k, v in live.items()
                   if k in ("int11-pricing", "int11-research")}
        assert len(by_task) == 2, \
            "expected the recorded cfo+kai INT-11 children"

        from orchestrator.runtime import ExecutionFlow
        from orchestrator.runtime.delegation import MemoryDelegationProvider
        from orchestrator.dsh import DelegationClient, RoleResolver
        from tests.live_dsh.real_backend import (RealDSHBackend,
                                                 DSHBridgeResponse)
        from tests.scenarios.scenario_helpers import (
            make_intake, make_execute_plan)

        ws = harness.ws
        recorded_by_role = {
            "cfo": by_task["int11-pricing"],
            "kai": by_task["int11-research"],
        }
        run_ids = {}
        calls = []

        def _dispatch(invocation, instance):
            role = getattr(instance, "role", "")
            calls.append(role)
            rec = recorded_by_role[role]
            run_ids[role] = rec["run_id"]
            # Replay rebinding (documented, not silent): the recorded child was
            # invoked under its session task id (e.g. "int11-pricing"); in this
            # replay the flow binds "task-1:<role>". The live identity is
            # preserved in run_id and in the original recorded file.
            structured = dict(rec["structured"])
            structured["task_id"] = task_id_by_role[role]
            return DSHBridgeResponse(
                run_id=rec["run_id"], output=json.dumps(structured),
                structured=structured,
                stop_reason=rec.get("stop_reason", "completed"))

        task_id_by_role = {"cfo": "task-1:cfo", "kai": "task-1:kai"}
        backend = RealDSHBackend(_dispatch, require_marker=True)
        client = DelegationClient(backend=backend, resolver=RoleResolver())
        delegation = harness.build_delegation(
            id="delegation-int-11", task="int-11",
            action="read", target="docs/**",
            scope_operations=("read",),
            scope_resources=("agents/**", "docs/**",
                             "multi-agent-harness/**"))
        provider = MemoryDelegationProvider(delegation)
        flow = ExecutionFlow(
            project="multi-agent-harness", base=ws, provider=provider,
            subtask_runner=lambda task, child: client.delegate(task, child),
            flow_id="int-11-live")
        result = flow.run(
            make_intake(objective="pricing",
                        required_authority_context="delegation-int-11"),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/pricing.md"))

        assert sorted(calls) == ["cfo", "kai"], \
            "exactly the two live children must be dispatched"
        # The two REAL recorded recommendations disagree (cost-observability vs
        # market positioning) — so the conflict gate MUST escalate them to
        # Human rather than let the flow proceed. Parallel collection and the
        # conflict semantics are both proven on real evidence.
        assert result.outcome == "ESCALATED", result.to_dict()
        assert any(g["gate"] == "conflict" and g["decision"] == "ESCALATE"
                   for g in result.gates), "conflict gate must escalate"
        roles = {r["role"] for r in result.results}
        assert roles == {"cfo", "kai"}, "both live results must be collected"
        # replay rebinding: session task ids rebind to the replay flow's task,
        # while the real run ids must stay intact (live provenance)
        assert {r["task_id"] for r in result.results} == \
            {"task-1:cfo", "task-1:kai"}
        assert run_ids["cfo"] and run_ids["kai"], \
            "live children must carry real run ids"
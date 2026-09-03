# RT-05 — Routing (minimum specialist set, no blanket fan-out)
#
# The runtime routes through the EXISTING foundation routing implementation
# (orchestrator.foundation.routing). It never reimplements selection:
#   - minimum specialist set per task domain
#   - no blanket fan-out (never all 7 specialists)
#   - specialists remain PEERS — a routed specialist never becomes a manager
#   - unknown domain -> RoutingError (no silent fallback)

import pytest

from orchestrator.foundation import (
    Task, select_agents, validate_no_fanout, route_tasks, RoutingError,
)
from orchestrator.foundation.contracts import SPECIALIST_ROLES
from orchestrator.runtime import ExecutionFlow, COMPLETE

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    MemoryDelegationProvider,
)


class TestRoutingMinimumSet:
    def test_primary_single_specialist(self):
        """engineering -> CTO only (minimum set of one)."""
        t = Task(task_id="t-1", objective="engineering", assigned_role="cto")
        assert select_agents(t) == ("cto",)

    def test_secondary_minimum_set(self):
        """pricing -> CFO + Kai (minimum set of two, never all 7)."""
        t = Task(task_id="t-2", objective="pricing", assigned_role="cfo")
        sel = select_agents(t)
        assert set(sel) == {"cfo", "kai"}
        assert len(sel) == 2

    def test_no_blanket_fanout(self):
        """No routing selection may contain all specialist roles."""
        for objective, role in [
            ("operations", "zeko"), ("engineering", "cto"),
            ("pricing", "cfo"), ("research", "kai"),
            ("social", "somad"), ("writing", "nova"),
            ("security_review", "badsector"),
        ]:
            t = Task(task_id=f"t-{role}", objective=objective,
                     assigned_role=role)
            sel = select_agents(t)
            validate_no_fanout(sel)
            assert set(sel) != set(SPECIALIST_ROLES)

    def test_unknown_domain_raises(self):
        """An unroutable objective is rejected (RoutingError), never routed to
        a default specialist set."""
        t = Task(task_id="t-x", objective="quantum-cooking",
                 assigned_role="cto")
        with pytest.raises(RoutingError):
            select_agents(t)

    def test_route_tasks_batch(self):
        """Batch routing gives each task its own minimum set."""
        tasks = [
            Task(task_id="t-1", objective="engineering", assigned_role="cto"),
            Task(task_id="t-2", objective="research", assigned_role="kai"),
        ]
        routed = route_tasks(tasks)
        assert routed["t-1"] == ("cto",)
        assert routed["t-2"] == ("kai",)


class TestRoutingInFlow:
    def test_pricing_flow_selects_cfo_kai(self, ws, subtask_runner,
                                          action_executor):
        """A pricing objective routes to the minimum set cfo+kai and executes
        both subtasks (peers, no manager)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=action_executor,
                             flow_id="test-route-pricing")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("margin analysis",), evidence=("src:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("market research",), evidence=("src:kai",)))
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert set(result.selected) == {"cfo", "kai"}
        assert len(result.results) == 2
        roles = {r["role"] for r in result.results}
        assert roles == {"cfo", "kai"}
        # No specialist manages another: each subtask is owned by its own role.
        assert set(result.parallel.get("owners")) == {"cfo", "kai"}
        assert result.parallel.get("mode") == "parallel"

    def test_flow_rejects_unroutable_domain(self, flow, subtask_runner):
        """An unroutable objective stops the flow fail-closed (BLOCKED), never
        silently falling back to a default specialist set."""
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="quantum-cooking"))
        assert result.outcome in ("BLOCKED", "FAILED", "ESCALATED")

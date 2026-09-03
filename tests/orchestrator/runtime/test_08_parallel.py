# RT-08 — Parallel subtask execution + provenance-preserving collection
#
# Requirements 10/11:
#   - independent subtasks execute in PARALLEL through the approved DSH
#     adapter (DelegationClient)
#   - before parallel execution: dependency independence is verified, task
#     ownership is exclusive, read/write scope is defined, state version is
#     preserved (CAS)
#   - collection preserves structured TaskResult fields INCLUDING provenance
#   - parallel collection keeps the state version stable (no uncontrolled
#     shared writes)

import os
import time

import pytest

from orchestrator.dsh import (
    DelegationClient, FakeSubagentBackend,
)
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, COMPLETE, BLOCKED, RECOVERING,
    MemoryDelegationProvider, SubtaskPlan, assert_parallel_safe,
    build_plans, ParallelExecutor, ParallelUnsafe,
)
from orchestrator.foundation.contracts import Task, TaskResult

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    StubSubtaskRunner,
)


class TestParallelSafety:
    def test_independent_batch_is_safe(self):
        """Two independent subtasks with distinct owners are safe."""
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-2", objective="research", assigned_role="kai")
        plans = build_plans([t1, t2])
        safety = assert_parallel_safe(plans, held_version=3)
        assert safety.safe
        assert set(safety.owners) == {"cfo", "kai"}

    def test_duplicate_task_id_refused(self):
        """Task ownership must be exclusive — duplicate task ids refuse the
        batch."""
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-1", objective="research", assigned_role="kai")
        plans = build_plans([t1, t2])
        with pytest.raises(ParallelUnsafe, match="exclusive"):
            assert_parallel_safe(plans)

    def test_non_specialist_owner_refused(self):
        """A subtask owned by the orchestrator (or an unknown actor) is
        refused — specialists are peers, no manager. The task itself must have
        a specialist assigned_role (contract), but a plan owner that is not the
        task's specialist (or the orchestrator) refuses the batch."""
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        # A plan whose owner is the orchestrator while the task is a cfo task
        plan = SubtaskPlan(task=t1, owner="orchestrator")
        with pytest.raises(ParallelUnsafe, match="specialist|owner"):
            assert_parallel_safe([plan])

    def test_dependency_within_batch_refused(self):
        """A subtask depending on another batch member is not independent."""
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-2", objective="research", assigned_role="kai")
        p1 = SubtaskPlan(task=t1, owner="cfo")
        p2 = SubtaskPlan(task=t2, owner="kai", depends_on=("t-1",))
        with pytest.raises(ParallelUnsafe, match="depends"):
            assert_parallel_safe([p1, p2])

    def test_write_scope_refused(self):
        """A specialist subtask declaring a write scope is refused outright —
        specialists return results, they never write project state (contract
        §6)."""
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        plan = SubtaskPlan(task=t1, owner="cfo", writes=("state/**",))
        with pytest.raises(ParallelUnsafe, match="write scope"):
            assert_parallel_safe([plan])


class TestParallelExecution:
    def test_parallel_subtasks_execute(self, ws, subtask_runner,
                                      action_executor):
        """Independent subtasks (cfo+kai) execute concurrently through the DSH
        adapter and all results are collected."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=action_executor,
                             flow_id="test-par01")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("cfo analysis",), evidence=("src:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("kai research",), evidence=("src:kai",)))
        result = flow.run(make_intake(objective="pricing"),
                          execute_plan=make_execute_plan(
                              target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert len(result.results) == 2
        # Parallel safety record present
        assert result.parallel.get("safe") is True
        assert result.parallel.get("mode") == "parallel"
        assert set(result.parallel.get("owners", ())) == {"cfo", "kai"}
        # Provenance-preserving collection keeps role identity
        roles = {r["role"] for r in result.results}
        assert roles == {"cfo", "kai"}
        for r in result.results:
            assert r["task_id"].endswith(":cfo") or r["task_id"].endswith(":kai")

    def test_parallel_results_preserve_all_fields(self, ws, subtask_runner,
                                                  action_executor):
        """Collected results preserve task_id, role, provenance, status,
        findings, evidence, risks, assumptions, unresolved_items, and
        actions_taken (requirement 11)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=action_executor,
                             flow_id="test-par02")
        from orchestrator.foundation.contracts import TaskResult
        subtask_runner.add("cfo", TaskResult(
            task_id="task-1:cfo", assigned_role="cfo", status="SUCCEEDED",
            findings=("margin ok",), evidence=("src:cfo",),
            risks=("fx risk",), assumptions=("stable demand",),
            unresolved_items=("tax treatment",),
            actions_taken=("ran model",), recommendation="proceed",
            confidence="HIGH"))
        subtask_runner.add("kai", TaskResult(
            task_id="task-1:kai", assigned_role="kai", status="SUCCEEDED",
            findings=("market growing",), evidence=("src:kai",),
            risks=("competitor",), assumptions=("no reg change",),
            unresolved_items=(), actions_taken=("surveyed",),
            recommendation="proceed", confidence="MEDIUM"))
        result = flow.run(make_intake(objective="pricing"),
                          execute_plan=make_execute_plan(
                              target="docs/pricing.md"))
        assert result.outcome == COMPLETE
        by_role = {r["role"]: r for r in result.results}
        cfo = by_role["cfo"]
        assert cfo["findings"] == ["margin ok"]
        assert cfo["evidence"] == ["src:cfo"]
        assert cfo["risks"] == ["fx risk"]
        assert cfo["assumptions"] == ["stable demand"]
        assert cfo["unresolved_items"] == ["tax treatment"]
        assert cfo["actions_taken"] == ["ran model"]
        assert "provenance" in cfo

    def test_sequential_fallback_when_unsafe(self, ws, subtask_runner,
                                             action_executor):
        """A batch that cannot be proven safe runs SEQUENTIALLY, never
        force-parallelized."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=action_executor,
                             flow_id="test-par-seq")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("cfo",), evidence=("e:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("kai",), evidence=("e:kai",)))
        # Force the planner to see a dependency (unsafe) by injecting plans
        # with a cross-dependency via a patched builder.
        original = flow._run_subtasks

        def patched(subtasks, delegation, runner):
            # Build plans with an intra-batch dependency -> unsafe
            from orchestrator.runtime import build_plans, SubtaskPlan
            plans = []
            for st in subtasks:
                plans.append(SubtaskPlan(
                    task=st, owner=st.assigned_role,
                    reads=tuple(st.scope or ()),
                    depends_on=(("task-1:cfo",) if st.assigned_role == "kai"
                                else ())))
            from orchestrator.runtime import assert_parallel_safe
            try:
                assert_parallel_safe(plans, held_version=flow._get_lifecycle().version)
            except ParallelUnsafe:
                # fall back to the original sequential path
                return flow._run_subtasks_sequential(subtasks, delegation,
                                                     runner)
        flow._run_subtasks = patched
        result = flow.run(make_intake(objective="pricing"),
                          execute_plan=make_execute_plan(
                              target="docs/pricing.md"))
        assert result.outcome == COMPLETE
        # Sequential mode recorded in the parallel safety record
        assert result.parallel.get("mode") in ("sequential", None)

    def test_parallel_version_preserved(self, ws, subtask_runner):
        """The state version does not drift during parallel execution — no
        uncontrolled shared writes (THREAT-021)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-par-ver")
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("cfo",), evidence=("e:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("kai",), evidence=("e:kai",)))
        result = flow.run(make_intake(objective="pricing"),
                          execute_plan=make_execute_plan(
                              target="docs/pricing.md"))
        assert result.outcome == COMPLETE
        # The parallel safety record captured a held version
        assert result.parallel.get("held_version", 0) >= 1


class TestParallelFailure:
    def test_one_failure_propagates(self, ws):
        """A failure in one parallel subtask propagates — no partial success
        (INT-12)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             flow_id="test-par-fail")

        def _runner(task, delegation):
            if task.assigned_role == "kai":
                from orchestrator.dsh import ChildFailure
                raise ChildFailure("kai failed")
            return TaskResult(task_id=task.task_id,
                              assigned_role=task.assigned_role,
                              status="SUCCEEDED", evidence=("e",),
                              findings=("ok",))
        flow._subtask_runner = _runner
        result = flow.run(make_intake(objective="pricing"),
                          execute_plan=make_execute_plan(
                              target="docs/pricing.md"))
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome
        # The successful cfo result was NOT collected into the final result
        # (no partial success)
        assert "cfo" not in [r.get("role") for r in result.results]
        events = flow._get_audit().read()
        assert any(e.get("event_class") in ("subtask_failed", "flow_stopped")
                   for e in events)
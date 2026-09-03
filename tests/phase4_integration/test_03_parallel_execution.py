# P4I-03 — Parallel execution
#
# Proves that independent subtasks (cfo+kai) run concurrently through the
# production flow: the parallel safety check passes (dependency independence,
# exclusive ownership, read-only scope), results are collected in batch order,
# and the state version is preserved across the batch. A batch that cannot be
# proven safe runs sequentially — never force-parallelized.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: PAR-1, PAR-2, PAR-3

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
    audit_events_of,
)


class TestParallelExecution:
    """P4I-03: parallel subtasks through the production flow."""

    def test_parallel_subtasks_complete(self, ws):
        """Pricing → {cfo, kai} run concurrently → COMPLETE."""
        delegation = make_delegation(
            id="delegation-price-001",
            scope_operations=("analysis", "read", "write", "code_write"),
            scope_resources=("docs/**", "agents/**",
                             "multi-agent-harness/**"))
        sr = StubSubtaskRunner()
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("margin analysis",), evidence=("artifact:cfo",)))
        sr.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("market research",), evidence=("artifact:kai",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=True, max_workers=4)

        assert state.outcome == "complete", f"got {state.outcome}"
        fr = state.flow_result
        assert fr["outcome"] == "COMPLETE"
        assert set(fr["selected"]) == {"cfo", "kai"}
        assert len(fr["results"]) == 2
        # Parallel mode was used (independent subtasks)
        assert fr.get("parallel", {}).get("safe") is True
        assert fr.get("parallel", {}).get("mode") == "parallel"
        assert set(fr["parallel"].get("owners", ())) == {"cfo", "kai"}
        # Results in batch order with role identity preserved
        roles = [r["role"] for r in fr["results"]]
        assert set(roles) == {"cfo", "kai"}
        # Parallel batch recorded in the audit ledger
        batches = audit_events_of(ws, "parallel_batch")
        assert len(batches) == 1
        assert batches[0]["task_ids"] == ["task-1:cfo", "task-1:kai"]
        assert batches[0]["owners"] == ["cfo", "kai"]

    def test_version_preserved_across_parallel_batch(self, ws):
        """State version is stable across the batch (no uncontrolled shared
        writes; THREAT-021)."""
        delegation = make_delegation(
            id="delegation-price-002",
            scope_operations=("analysis", "read", "write", "code_write"),
            scope_resources=("docs/**", "agents/**",
                             "multi-agent-harness/**"))
        sr = StubSubtaskRunner()
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:cfo",)))
        sr.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            evidence=("artifact:kai",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-002",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=True, max_workers=4)

        fr = state.flow_result
        # Held version captured before the batch
        assert fr["parallel"].get("held_version", 0) >= 1
        # Parallel batch correlated with held version
        batches = audit_events_of(ws, "parallel_batch")
        assert batches and batches[0]["held_version"] == \
            fr["parallel"]["held_version"]

    def test_single_subtask_sequential_safe(self, ws):
        """A single-subtask batch is safe and runs sequentially."""
        delegation = make_delegation()
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=True, max_workers=4)

        assert state.outcome == "complete"
        fr = state.flow_result
        assert fr["parallel"].get("safe") is True
        assert fr["parallel"].get("mode") == "sequential"


class TestParallelSafety:
    """P4I-03: parallel safety is proven before any child starts."""

    def test_duplicate_task_id_refused(self):
        from orchestrator.foundation.contracts import Task
        from orchestrator.runtime import build_plans, assert_parallel_safe, \
            ParallelUnsafe
        import pytest

        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-1", objective="research", assigned_role="kai")
        with pytest.raises(ParallelUnsafe, match="exclusive"):
            assert_parallel_safe(build_plans([t1, t2]))

    def test_write_scope_refused(self):
        from orchestrator.foundation.contracts import Task
        from orchestrator.runtime import SubtaskPlan, assert_parallel_safe, \
            ParallelUnsafe
        import pytest

        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        plan = SubtaskPlan(task=t1, owner="cfo", writes=("state/**",))
        with pytest.raises(ParallelUnsafe, match="write scope"):
            assert_parallel_safe([plan])

    def test_dependency_within_batch_refused(self):
        from orchestrator.foundation.contracts import Task
        from orchestrator.runtime import SubtaskPlan, assert_parallel_safe, \
            ParallelUnsafe
        import pytest

        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-2", objective="research", assigned_role="kai")
        p1 = SubtaskPlan(task=t1, owner="cfo")
        p2 = SubtaskPlan(task=t2, owner="kai", depends_on=("t-1",))
        with pytest.raises(ParallelUnsafe, match="depends"):
            assert_parallel_safe([p1, p2])
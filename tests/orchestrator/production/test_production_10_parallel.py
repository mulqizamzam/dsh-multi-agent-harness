# PROD-10 — Parallel subtasks
#
# Independent subtasks execute concurrently through the approved DSH adapter.
# Safety checks (dependency independence, exclusive ownership, read-only scope)
# run before any child starts. Results are collected in deterministic batch
# order. A batch that cannot be proven independent runs sequentially.
#
# Tests: PAR-1, PAR-2, PAR-3

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestParallel:
    def test_parallel_subtasks_complete(self, ws, subtask_runner,
                                        action_executor):
        """Independent subtasks (cfo+kai) run concurrently → COMPLETE."""
        delegation = make_delegation(
            id="delegation-price-001",
            scope_operations=("analysis", "read"),
            scope_resources=("docs/**",))
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="invest",
            evidence=("artifact:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="invest",
            evidence=("artifact:kai",)))

        plan = ObjectivePlanner().plan(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-001")

        assert set(plan.selected_roles) == {"cfo", "kai"}

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        result = ex.execute(plan, delegation=delegation,
                            parallel_subtasks=True, max_workers=4)
        assert result.outcome == "COMPLETE", f"got {result.outcome}"
        assert len(result.results) == 2
        # Parallel mode was used (independent subtasks).
        assert result.parallel.get("safe") is True
        assert result.parallel.get("mode") == "parallel"

    def test_parallel_safety_checks(self, ws, subtask_runner, action_executor):
        """Parallel safety is verified before any child starts.

        Subtasks with a single agent (sequential) still pass safety checks.
        """
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        result = ex.execute(plan, delegation=delegation,
                            parallel_subtasks=True, max_workers=4)
        assert result.outcome == "COMPLETE"
        # Single subtask → sequential (but still safe).
        assert result.parallel.get("safe") is True
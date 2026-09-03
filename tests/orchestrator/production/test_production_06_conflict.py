# PROD-06 — Conflict detection
#
# When the minimum specialist set returns materially conflicting positions,
# the conflict gate ESCALATEs (no majority voting; CONF-001..003). The
# production run stops and preserves the disagreement.
#
# Tests: AEF-2, CONF-001..003

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestConflict:
    def test_material_conflict_escalates(self, ws, subtask_runner,
                                         action_executor):
        """Conflicting positions from cfo+kai → conflict gate ESCALATE."""
        delegation = make_delegation(
            id="delegation-price-001",
            scope_operations=("analysis", "read"),
            scope_resources=("docs/**",))
        # cfo recommends "invest"; kai recommends "do not invest" — conflict.
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="invest",
            findings=("growth looks strong",),
            evidence=("artifact:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="do not invest",
            findings=("market signals are weak",),
            evidence=("artifact:kai",)))

        # "pricing" maps to cfo (primary) + kai (secondary) — minimum set.
        plan = ObjectivePlanner().plan(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-001")

        assert set(plan.selected_roles) == {"cfo", "kai"}

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(plan, delegation=delegation)
        except ProductionEscalated as e:
            raised = True
            assert "conflict" in str(e).lower() or "escalate" in str(e).lower()
        except ProductionDenied as e:
            raised = True
            assert "conflict" in str(e).lower()
        assert raised, "expected material conflict to escalate"

        # Disagreement preserved in the flow result (no voting).
        flow = ex.last_flow
        assert flow is not None
        assert flow._result.outcome == "ESCALATED"
        assert len(flow._result.results) == 2

    def test_aligned_positions_complete(self, ws, subtask_runner,
                                        action_executor):
        """Aligned positions → no conflict → COMPLETE."""
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

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        result = ex.execute(plan, delegation=delegation)
        assert result.outcome == "COMPLETE"
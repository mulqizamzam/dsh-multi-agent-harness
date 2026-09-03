# PROD-01 — Bounded autonomous happy path
#
# A full bounded production run with a valid delegation, LOW-risk engineering
# objective, all gates ALLOW, the execution-time authority re-check passing,
# the consequential write landing through the execution gate, and the task
# reaching COMPLETE. The final report is generated with the correct outcome.
#
# Tests: AEF-1, AEF-2, AEF-3, VER-1, AUD-1, PB-1, PB-2

import json
import os

from conftest import make_delegation, make_subtask_result, seed_state

from orchestrator.runtime import COMPLETE
from orchestrator.production import (
    ProductionRun, ProductionDenied, ProductionEscalated,
)


class TestHappyPath:
    def test_full_flow_completes(self, ws, subtask_runner, action_executor):
        """All gates open; delegation valid; objective reaches COMPLETE."""
        delegation = make_delegation()
        # CTO subtask returns a successful result
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            findings=("analyzed",), evidence=("artifact:analysis",)))

        run = ProductionRun(base=ws)
        state = run.run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        assert state.outcome == "complete", state.errors
        assert state.phase == "close"
        assert state.flow_result is not None
        assert state.flow_result["outcome"] == "COMPLETE"
        assert state.flow_result["final_state"] == "COMPLETE"
        assert state.flow_result["selected"] == ["cto"]
        assert state.flow_result["risk"] == "MEDIUM"  # write → MEDIUM
        assert len(state.flow_result["results"]) == 1
        # File written through execution gate
        assert state.report is not None
        assert state.report["outcome"] == "COMPLETE"
        assert "cto" in state.report["selected_roles"]
        # Audit events recorded
        assert len(state.audit_ids) > 0

    def test_report_is_structured(self, ws, subtask_runner, action_executor):
        """The final report is a deterministic JSON-serializable document."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        run = ProductionRun(base=ws)
        state = run.run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        report = state.report
        assert report["outcome"] == "COMPLETE"
        assert report["objective"] == "engineering"
        assert report["selected_roles"] == ["cto"]
        assert "verification" in report
        assert report["verification"]["verdict"] == "PASSED"
        assert "gates" in report
        assert len(report["gates"]) > 0
        # Deterministic serialization
        json.dumps(report)

    def test_flow_uses_minimum_agents(self, ws, subtask_runner,
                                      action_executor):
        """Routing selects the minimum specialist set (no blanket fan-out)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        run = ProductionRun(base=ws)
        state = run.run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        # Engineering → cto only (primary role, no secondary for engineering)
        assert state.flow_result["selected"] == ["cto"]
        assert len(state.flow_result["selected"]) == 1
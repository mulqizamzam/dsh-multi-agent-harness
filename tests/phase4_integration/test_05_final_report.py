# P4I-05 — Final report
#
# Proves the structured final report is generated on COMPLETE, is
# JSON-serializable, contains the correct outcome/gates/verification/
# selected_roles/synthesis/files_written, and that a non-COMPLETE flow yields
# an honest (non-success) report. The report is DATA — never authority.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: AEF-1 (report), AUD-1, AUD-3

import json

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
)


class TestFinalReport:
    """P4I-05: the final report is structured, deterministic, honest."""

    def test_final_report_generated(self, ws, delegation):
        """A COMPLETE run yields a full structured final report."""
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)

        assert state.outcome == "complete"
        report = state.report
        assert report is not None
        assert report["outcome"] == "COMPLETE"
        assert report["objective"] == "engineering"
        assert "gates" in report and len(report["gates"]) >= 7
        assert report["verification"]["verdict"] == "PASSED"
        assert "synthesis" in report
        assert report["selected_roles"] == ["cto"]
        assert report["files_written"] == ["agents/cto/output.txt"]
        assert report["errors"] == []
        # Deterministic JSON document
        json.dumps(report)
        json.dumps(state.to_dict())

    def test_report_generator_honest_on_failure(self):
        """A non-COMPLETE flow result yields an honest (non-success) report."""
        from orchestrator.production import ReportGenerator
        from orchestrator.runtime import FlowResult, BLOCKED

        fr = FlowResult(flow_id="f1", objective="x", outcome=BLOCKED,
                        phase="authority_gate")
        fr.add_error("authority DENY")
        report = ReportGenerator().generate(fr)
        assert report.outcome == "BLOCKED"
        assert report.errors, "errors preserved in the report"
        json.dumps(report.to_dict())

    def test_report_is_data_not_authority(self, ws, delegation):
        """The report carries no authority claim (AUTH-INV-13/14)."""
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)

        report = state.report
        # The report summarises the run; it never grants authority.
        assert "authority_source" not in report
        assert report["outcome"] == "COMPLETE"

    def test_blocked_run_still_reports_honestly(self, ws):
        """A BLOCKED run raises, but the ProductionState records the stop."""
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )

        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        sr = StubSubtaskRunner()
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:cfo",)))

        run = ProductionRun(base=ws)
        try:
            run.run(
                objective="finance analysis for a transaction",
                scope=("docs/report.md",),
                required_authority_context="delegation-fin-001",
                delegation=delegation, subtask_runner=sr,
                review={"verdict": "PASS", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                parallel_subtasks=False)
            assert False, "expected the HIGH run to stop without approval"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        # The state records the stop honestly; no success report fabricated.
        assert run.state is not None
        assert run.state.outcome in ("stopped", "escalated", "failed")
        assert run.state.errors, "expected errors recorded"
        # A report is only generated on COMPLETE; never fabricate success.
        assert run.state.report is None
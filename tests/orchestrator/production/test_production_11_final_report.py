# PROD-11 — Final report
#
# The production run generates a structured final report summarizing the
# objective, the selected roles, every gate decision, the verification
# verdict, the synthesis, and the outcome. The report is DATA — never
# authority. A non-COMPLETE run still yields an honest report.
#
# Tests: AUD-1, AUD-3, AEF-1 (report)

import json

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionRun, ProductionDenied, ProductionEscalated,
    FinalReport, ReportGenerator,
)


class TestFinalReport:
    def test_final_report_generated(self, ws, subtask_runner,
                                    action_executor):
        """A COMPLETE run yields a full structured final report."""
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

        assert state.outcome == "complete"
        report = state.report
        assert report is not None
        assert report["outcome"] == "COMPLETE"
        assert report["objective"] == "engineering"
        assert "gates" in report and len(report["gates"]) >= 7
        assert report["verification"]["verdict"] == "PASSED"
        assert "synthesis" in report
        # The report is JSON-serializable (deterministic document).
        json.dumps(report)
        json.dumps(state.to_dict())

    def test_report_records_audit(self, ws, subtask_runner, action_executor):
        """The lifecycle emits audit events for every phase."""
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

        assert len(state.audit_ids) >= 5  # run/plan/execute/report/close

    def test_report_generator_honest_on_failure(self):
        """A non-COMPLETE flow result yields an honest (non-success) report."""
        from orchestrator.runtime import FlowResult, BLOCKED
        fr = FlowResult(flow_id="f1", objective="x", outcome=BLOCKED,
                        phase="authority_gate")
        fr.add_error("authority DENY")
        gen = ReportGenerator()
        report = gen.generate(fr)
        assert isinstance(report, FinalReport)
        assert report.outcome == "BLOCKED"
        assert report.errors, "errors preserved in the report"

    def test_blocked_run_still_reports(self, ws, subtask_runner,
                                       action_executor):
        """A BLOCKED run raises, but the state still records the stop."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        run = ProductionRun(base=ws)
        try:
            run.run(
                objective="finance analysis for a transaction",
                scope=("docs/report.md",),
                required_authority_context="delegation-fin-001",
                delegation=delegation,
                subtask_runner=subtask_runner,
                action_executor=action_executor,
                review={"verdict": "PASS", "review_id": "rev-001",
                        "input_hash": "a" * 64},
            )
            assert False, "expected the HIGH run to stop without approval"
        except (ProductionDenied, ProductionEscalated):
            pass
        # The state records the stop honestly.
        assert run.state is not None
        assert run.state.outcome in ("stopped", "escalated", "failed")
        assert run.state.errors, "expected errors recorded"
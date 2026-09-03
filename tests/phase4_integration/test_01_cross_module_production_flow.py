# P4I-01 — Cross-module production flow
#
# Proves the full cross-module production flow: ProductionRun → ObjectivePlanner
# → BoundedExecutor → ExecutionFlow → gates → execution gate → state machine →
# audit → final report. Every module integrates correctly, the flow reaches
# COMPLETE, the file is written through the project execution gate, the audit
# ledger records the full lifecycle, and the observability index correlates the
# run.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: AEF-1, VER-1, VER-3, AUD-1, AUD-3

import json
import os

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
    StubActionExecutor, audit_classes, make_workspace,
)


class TestCrossModuleProductionFlow:
    """P4I-01: every production module wires together into a COMPLETE run."""

    def test_full_flow_completes(self, ws, delegation):
        """ProductionRun with a valid delegation → COMPLETE, file written."""
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            findings=("analyzed",), evidence=("artifact:cto",)))

        from orchestrator.production import ProductionRun

        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)

        # Outcome
        assert state.outcome == "complete", f"got {state.outcome}"
        assert state.phase == "close"

        # Flow result
        fr = state.flow_result
        assert fr["outcome"] == "COMPLETE", f"got {fr['outcome']}"
        assert fr["final_state"] == "COMPLETE"
        assert fr["phase"] == "close"
        assert fr["selected"] == ["cto"]
        assert fr["risk"] in ("MEDIUM", "LOW")  # write → MEDIUM

        # Gates: 7 gate records all ALLOW
        assert len(fr.get("gates", [])) == 7, f"got {len(fr['gates'])} gates"
        for g in fr["gates"]:
            assert g["decision"] == "ALLOW", f"{g['gate']} = {g['decision']}"

        # Verification
        ver = fr.get("verification", {})
        assert ver.get("verdict") == "PASSED", f"verdict={ver.get('verdict')}"

        # File written through execution gate
        target = "agents/cto/output.txt"
        assert target in fr.get("files_written", []), f"files={fr['files_written']}"
        assert os.path.exists(os.path.join(ws, target)), "target file not on disk"

        # Audit lifecycle
        classes = audit_classes(ws)
        required = {"flow_started", "gate_risk", "gate_evidence",
                    "gate_conflict", "gate_review", "gate_authority",
                    "gate_verification", "execution_attempt",
                    "state_complete", "flow_finished", "production_run",
                    "intake_recorded", "result_collected"}
        missing = required - classes
        assert not missing, f"missing audit classes: {missing}"

        # Audit ids recorded
        assert len(state.audit_ids) >= 5, f"audit_ids={state.audit_ids}"

        # Final report
        report = state.report
        assert report is not None
        assert report["outcome"] == "COMPLETE"
        assert report["objective"] == "engineering"
        assert report["selected_roles"] == ["cto"]
        assert len(report["gates"]) >= 7
        assert report["verification"]["verdict"] == "PASSED"
        assert "synthesis" in report
        assert report["files_written"] == [target]
        assert report["errors"] == []
        json.dumps(report)  # JSON-serializable

    def test_flow_uses_minimum_agents(self, ws, delegation):
        """Engineering → [cto] only (minimum set, no blanket fan-out)."""
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

        assert state.flow_result["selected"] == ["cto"]
        assert len(state.flow_result["selected"]) == 1

    def test_deterministic_result(self, tmp_path_factory, delegation):
        """Two runs with identical inputs produce identical outcomes
        (modulo timestamps, ids)."""
        from tests.conftest import o3_daemon_context
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        from orchestrator.production import ProductionRun

        states = []
        for i in range(2):
            ws_i = make_workspace(tmp_path_factory.mktemp(f"det-{i}"))
            # Each run gets its OWN O3 daemon root so project state is
            # isolated per run (O3 Phase B: daemon root == run workspace).
            with o3_daemon_context(ws_i):
                states.append(ProductionRun(base=ws_i).run(
                    objective="engineering", scope=("agents/cto/output.txt",),
                    required_authority_context="delegation-prod-001",
                    delegation=delegation, subtask_runner=sr,
                    parallel_subtasks=False))

        for s in states:
            assert s.flow_result["outcome"] == "COMPLETE"
            assert s.flow_result["selected"] == ["cto"]
            assert s.flow_result["final_state"] == "COMPLETE"
            assert s.report["outcome"] == "COMPLETE"
            assert s.report["selected_roles"] == ["cto"]

        # Deterministic gate decisions and final report shape.
        assert (states[0].report["gates"] == states[1].report["gates"])
        assert (states[0].flow_result["results"]
                == states[1].flow_result["results"])
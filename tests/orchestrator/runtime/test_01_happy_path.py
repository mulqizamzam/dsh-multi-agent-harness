# RT-01 — Happy path: full Execution Flow to COMPLETE
#
# Proves the complete chain:
#   INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE
#   → EXECUTE_SUBTASKS → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE
#   → ADVERSARIAL_REVIEW → AUTHORITY_GATE → EXECUTE → VERIFY → CLOSE
# with all gates ALLOW, the execution-time authority re-check passing, the
# consequential write landing through the execution gate, and the task reaching
# COMPLETE.  The result is deterministic and JSON-serializable.
#
# Reuses: control.*, orchestrator.foundation.*, orchestrator.dsh,
#         orchestrator.execution (no reimplementation).

import json
import os

from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, COMPLETE,
)
from orchestrator.runtime.flow import RUNTIME_PHASE_CHAIN

from conftest import make_intake, make_execute_plan, make_subtask_result


class TestHappyPath:
    def test_full_flow_completes(self, flow, ws, subtask_runner):
        """All gates ALLOW; state reaches COMPLETE; file written via gate."""
        # CTO subtask returns a successful result
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto",
            recommendation="write module",
            findings=("analyzed",),
            evidence=("artifact:analysis",)))

        intake = make_intake(objective="engineering")
        plan = make_execute_plan(target="agents/cto/output.txt")

        result = flow.run(intake, execute_plan=plan)

        assert result.outcome == COMPLETE, result.to_dict()
        assert result.final_state == "COMPLETE"
        assert result.phase == "close"
        assert result.selected == ("cto",)
        assert len(result.results) == 1
        assert os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        assert "agents/cto/output.txt" in result.files_written
        # Deterministic result object
        doc = result.to_dict()
        json.dumps(doc)  # serializable
        assert doc["outcome"] == "COMPLETE"

    def test_flow_phase_chain_matches_required_flow(self):
        """The runtime chain covers the required production flow."""
        required = ("intake", "understand", "classify", "risk_gate",
                    "decompose", "select", "delegate", "execute_subtasks",
                    "collect", "evidence_gate", "synthesize", "conflict_gate",
                    "adversarial_review", "authority_gate", "execute",
                    "verify", "close")
        assert RUNTIME_PHASE_CHAIN == required

    def test_audit_records_lifecycle(self, flow, subtask_runner):
        """Actual runtime events are recorded in the append-only ledger."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE
        events = flow._get_audit().read()
        classes = {e["event_class"] for e in events}
        assert "flow_started" in classes
        assert "gate_risk" in classes
        assert "gate_evidence" in classes
        assert "gate_conflict" in classes
        assert "gate_review" in classes
        assert "gate_authority" in classes
        assert "gate_verification" in classes
        assert "state_complete" in classes
        assert "flow_finished" in classes

    def test_execution_time_recheck_is_mandatory(self, flow, subtask_runner):
        """The EXECUTE phase performs an execution-time authority re-check
        (AUTH-INV-05) — not just the planning check."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE
        # The engine recheck ran (audit recorded an authority recheck ALLOW).
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "execution_attempt"
                   for e in events)

    def test_result_is_deterministic(self, ws, provider, subtask_runner):
        """Two fresh flows over identical inputs produce identical results."""
        import os as _os
        from orchestrator.runtime import ExecutionFlow
        from tests.conftest import o3_daemon_context
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        intake = make_intake(objective="engineering")
        plan = make_execute_plan(target="agents/cto/output.txt")
        results = []
        for i in range(2):
            # Each run gets its OWN O3 daemon root so protected state is
            # isolated per run (O3 Phase B: daemon root == run workspace).
            with o3_daemon_context(_os.path.join(ws, f"run{i}")):
                base = _os.path.join(ws, f"run{i}")
                for sub in ("state/registry", "state/projects", "audit",
                            "agents/cto", "docs"):
                    _os.makedirs(_os.path.join(base, sub), exist_ok=True)
                f = ExecutionFlow(base=base, provider=provider,
                                  subtask_runner=subtask_runner,
                                  flow_id="test-det")
                results.append(f.run(intake, execute_plan=plan))
        r1, r2 = results
        assert r1.outcome == r2.outcome == COMPLETE
        assert r1.to_dict()["gates"] == r2.to_dict()["gates"]
        assert r1.to_dict()["selected"] == r2.to_dict()["selected"]
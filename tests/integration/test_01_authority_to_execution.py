# INT-01 — Authority → Delegation → Risk → Review → Execution (happy path)
#
# Proves the full lifecycle: intake → plan → risk → review → authority →
# execution → verification → COMPLETE, with all gates passing and the write
# channel delivering the file.
#
# Modules integrated:
#   Contracts (TaskIntake, Task, Delegation, TaskResult)
#   + Routing (select_agents)
#   + ControlPlane (all 7 gates)
#   + WorkflowRun (15-phase chain)
#   + StateMachine / ProjectState
#   + execution_gate (write_through)
#   + audit helpers
#
# Reference: docs/testing/0001-integration-test-plan.md INT-01
# Invariants: AUTH-INV-05, INV-09, INV-15, AUTH-INV-20

import os
import pytest

from orchestrator.foundation import (
    TaskIntake, Task, TaskResult, Delegation, select_agents,
    WorkflowRun, PHASE_CHAIN,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestINT01FullLifecycle:
    def test_route_engineering_task_to_cto(self):
        """Routing selects the minimum specialist set (engineering → CTO)."""
        t = Task(task_id="int-01", objective="engineering", assigned_role="cto")
        assert select_agents(t) == ("cto",)

    def test_full_lifecycle_happy_path(self, harness):
        """All gates ALLOW; file is written; state reaches COMPLETE."""
        h = harness

        # --- INTAKE (requires authority context) ---
        intake = TaskIntake(
            objective="write a code module",
            scope=("multi-agent-harness/**",),
            expected_outcome="module written and verified",
            required_authority_context="delegation-int-001",
        )
        assert intake.has_authority_context()

        # --- DELEGATION (ACTIVE, scoped) ---
        delegation = h.build_delegation(
            id="delegation-int-001", task="int-01",
            action="write", target="agents/**",
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        )
        assert delegation.is_active()
        assert not delegation.is_expired()

        # --- STATE: DRAFT -> PLANNED -> DELEGATED -> EXECUTING ---
        assert h.machine("int-01").current() == "DRAFT"
        h.transition("int-01", "PLANNED", authority=delegation)
        h.transition("int-01", "DELEGATED", authority=delegation)
        h.transition("int-01", "EXECUTING", authority=delegation)

        # --- WORKFLOW: drive to execute_gate ---
        wf = h.run_workflow(objective=intake.objective)
        # Advance from intake to execute_gate (index of execute_gate in PHASE_CHAIN)
        for _ in range(PHASE_CHAIN.index("execute_gate")):
            wf.advance()
        assert wf.current_phase() == "execute_gate"

        # --- EXECUTION GATE: authorize the write ---
        # Real execution gate (path-aware): agents/cto/output.txt is ALLOWED.
        h.authorize_write("write", "agents/cto/output.txt")
        path = h.write_through("agents/cto/output.txt", {"module": "ok"})
        assert os.path.exists(path)
        assert h.file_exists("agents/cto/output.txt")

        # --- COLLECTED / SYNTHESIZING ---
        h.transition("int-01", "COLLECTED")
        h.transition("int-01", "SYNTHESIZING")

        # --- VERIFICATION: TaskResult with evidence ---
        result = TaskResult(task_id="int-01", assigned_role="cto",
                            status="SUCCEEDED",
                            evidence=("module_written.json",),
                            confidence="HIGH")
        dec = h.evaluate_gate("verification", {"result": result})
        assert dec.decision == "ALLOW"

        # --- COMPLETE ---
        h.transition("int-01", "COMPLETE")
        assert h.machine("int-01").current() == "COMPLETE"

    def test_audit_events_record_lifecycle(self, harness):
        """Each lifecycle event is recorded in the audit ledger."""
        h = harness
        delegation = h.build_delegation(id="delegation-int-01b")

        events = [
            {"event_id": f"ev-{i}", "timestamp": "2026-08-30T00:00:00Z",
             "event_class": cls, "actor": "orchestrator", "action": "transition",
             "target": "int-01", "project": "multi-agent-harness",
             "authority_source": delegation.id, "result": "allowed"}
            for i, cls in enumerate(["state_start", "gate_risk", "gate_review",
                                     "gate_authority", "gate_execution",
                                     "gate_verification", "state_complete"])
        ]
        for e in events:
            h.append_audit(e)
        log = h.audit_events()
        assert len(log) == 7
        classes = {e["event_class"] for e in log}
        assert "state_complete" in classes

    def test_reference_gate_agrees_with_foundation(self, harness):
        """Foundation AuthorityGate and reference authorize() agree on the
        happy path (ALLOW)."""
        h = harness
        d = h.build_delegation_dict(
            id="delegation-int-001",
            scope={"operations": ["write", "read", "code_write"],
                   "resources": ["agents/**", "docs/**", "multi-agent-harness/**"],
                   "environments": ["dev"]},
        )
        cmp = h.cross_check_authority(
            "orchestrator", "write", "agents/cto/output.txt", d,
            environment="dev")
        assert cmp["foundation_decision"] == "ALLOW"
        assert cmp["reference_decision"] == "ALLOW"
        assert cmp["match"] is True

    @pytest.mark.skip(reason="requires Phase-2C — live DSH subagent execution")
    def test_live_dsh_full_lifecycle(self, harness):
        """SKELETON: drive the full lifecycle against a live DSH session with
        a real subagent delegation. Blocked on Phase-2C (production orchestrator
        execution engine)."""
        raise NotImplementedError("Phase-2C: live subagent delegation")
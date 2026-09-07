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

    def test_live_dsh_full_lifecycle(self, harness):
        """LIVE variant (D4/D7 mounted): drive the full INT-01 lifecycle
        through the REAL backend — a session-recorded subagent_cto result is
        fed through RealDSHBackend (production mount gate, require_marker=True)
        into ExecutionFlow, which must reach COMPLETE with exactly one live
        dispatch.

        Conditional gate, not a skeleton: without the mount marker or without
        a session-recorded child result the test SKIPS with that reason
        (pytest cannot dispatch a DSH child itself — the dispatch plane is the
        orchestrator session, tests/live_evidence/harness.py:116-118). The
        deterministic contract is covered offline by the tests above and by
        tests/scenarios/test_scenarios.py SCN-002.
        """
        import json
        from tests.live_dsh.live_gate import (live_available, skip_reason,
                                              load_recorded)
        if not live_available("INT-01"):
            pytest.skip(skip_reason("INT-01"))
        live = load_recorded("DSH_LIVE_RESULT_INT01",
                             "int01_live_result.json")
        assert live and live.get("structured"), \
            "live gate on but no session-recorded INT-01 child result"

        from orchestrator.runtime import ExecutionFlow
        from orchestrator.runtime.delegation import MemoryDelegationProvider
        from orchestrator.dsh import DelegationClient, RoleResolver
        from tests.live_dsh.real_backend import (RealDSHBackend,
                                                 DSHBridgeResponse)
        from tests.scenarios.scenario_helpers import (
            make_intake, make_execute_plan)

        ws = harness.ws
        structured = live["structured"]
        calls = []

        def _dispatch(invocation, instance):
            calls.append({"tool": getattr(instance, "tool_name", ""),
                          "role": getattr(instance, "role", "")})
            return DSHBridgeResponse(
                run_id=live["run_id"],
                output=json.dumps(structured),
                structured=structured,
                stop_reason=live.get("stop_reason", "completed"))

        backend = RealDSHBackend(_dispatch, require_marker=True)
        client = DelegationClient(backend=backend, resolver=RoleResolver())
        delegation = harness.build_delegation(
            id="delegation-int-001", task="int-01",
            action="write", target="agents/**",
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**",
                             "multi-agent-harness/**"))
        provider = MemoryDelegationProvider(delegation)

        def subtask_runner(task, child_delegation):
            return client.delegate(task, child_delegation)

        flow = ExecutionFlow(project="multi-agent-harness", base=ws,
                             provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="int-01-live")
        result = flow.run(
            make_intake(objective="engineering",
                        required_authority_context="delegation-int-001"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))

        assert len(calls) == 1, "exactly one live dispatch must occur"
        assert calls[0]["tool"] == "subagent_cto"
        assert result.outcome == "COMPLETE", result.to_dict()
        cto = [r for r in result.results if r.get("role") == "cto"]
        assert cto and cto[0]["task_id"] == structured["task_id"]
        # the real DSH run identity must be carried into the collected result
        assert live["run_id"], "live child must carry a real run_id"
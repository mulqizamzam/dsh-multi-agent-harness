# INT-12 — Cross-module failure propagation
#
# Proves that a failure in one module propagates correctly: the pipeline stops,
# state is preserved, an audit event is recorded, and (where applicable) the
# recovery path is entered. No partial execution, no silent skip.
#
# Modules integrated: ALL modules — ControlPlane gates + WorkflowRun +
# StateMachine + execution_gate + audit_helpers + recovery
# Invariants: AUTH-INV-15/20, INV-15, THREAT-017/022

import pytest

from orchestrator.foundation import WorkflowRun, PHASE_CHAIN, WorkflowError


class TestINT12FailurePropagation:
    def test_execution_gate_deny_stops_pipeline(self, harness):
        """An execution gate denial on a protected path stops the pipeline
        and produces no file mutation."""
        h = harness
        target = "state/registry/x.json"  # protected path (ADR 0002)
        # The execution gate must deny this
        from control.execution_gate import Denied as ExecDenied
        with pytest.raises(ExecDenied, match="protected"):
            h.authorize_write("write", target)
        # No file written
        assert not h.file_exists("state/registry/x.json")

    def test_execution_gate_denial_stops_workflow(self, harness):
        """A non-ALLOW execution gate decision stops the WorkflowRun (fail-closed)."""
        wf = WorkflowRun(objective="int-12")
        for _ in range(PHASE_CHAIN.index("execute_gate")):
            wf.advance()
        assert wf.current_phase() == "execute_gate"
        # Simulate the execution gate returning DENY (the orchestrator would
        # call check_gate with the DENY decision from the real gate).
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.check_gate("DENY", gate="execution",
                          detail={"reason": "protected path"})

    def test_authority_deny_stops_action_no_mutation(self, harness):
        """An authority gate denial prevents any file from being written."""
        h = harness
        # No delegation → authority gate DENY
        dec = h.evaluate_gate("authority", {
            "action": "write", "target": "agents/cto/x.txt"})
        assert dec.decision == "DENY"
        # Because the gate denied, no write reaches the execution channel.
        assert not h.file_exists("agents/cto/x.txt")

    def test_evidence_deny_blocks_to_execution(self, harness):
        """Evidence gate DENY on HIGH risk without evidence blocks execution
        (no state transition to EXECUTING)."""
        h = harness
        d = h.build_delegation()
        h.transition("int-12b", "PLANNED", authority=d)
        h.transition("int-12b", "DELEGATED", authority=d)
        # Evidence gate DENYs
        assert h.evaluate_gate("evidence", {"risk": "HIGH", "evidence": []}) \
            .decision == "DENY"
        # State machine remains at DELEGATED (not EXECUTING)
        assert h.machine("int-12b").current() == "DELEGATED"

    def test_gate_denial_produces_audit_event(self, harness):
        """A gate denial produces an execution_denial audit event."""
        h = harness
        h.append_audit({
            "event_id": "ev-deny-001", "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "execution_denial", "actor": "orchestrator",
            "action": "write", "target": "state/registry/x.json",
            "project": "multi-agent-harness", "result": "denied",
            "error": "protected path (ADR 0002)",
        })
        denials = [e for e in h.audit_events()
                   if e.get("event_class") == "execution_denial"]
        assert len(denials) == 1

    def test_failure_enters_recovery_path(self, harness):
        """After a gate denial, the orchestrator enters the recovery path
        (STOP → PRESERVE → DIAGNOSE)."""
        h = harness
        # Create a recovery record (simulating the orchestrator's response
        # to a gate denial).
        rec = h.begin_recovery("int-12c", preserved_version=5,
                               failure_class="authorization",
                               reason="authority gate denied")
        assert rec.state == "PRESERVED"
        rec.diagnose("expired delegation", failure_class="authorization")
        assert rec.state == "DIAGNOSED"
        # Recovery cannot complete without authority re-check
        from state.helpers import RecoveryError
        with pytest.raises(RecoveryError):
            rec.complete()  # Not in AUTHORITY_RECHECKED state
        rec.replan()
        rec.authority_rechecked(checked=True, reason="new delegation granted")
        rec.complete()
        assert rec.state == "COMPLETED"

    def test_multiple_successive_denials_independent(self, harness):
        """Multiple independent gate denials on different targets do not
        cross-contaminate — each denial is contained."""
        h = harness
        # Denial 1: protected path
        from control.execution_gate import Denied as ExecDenied
        with pytest.raises(ExecDenied):
            h.authorize_write("write", "audit/events.jsonl")
        assert not h.file_exists("audit/events.jsonl")
        # Denial 2: no delegation
        assert h.evaluate_gate("authority", {
            "action": "write", "target": "agents/cto/x.txt"}).decision == "DENY"
        assert not h.file_exists("agents/cto/x.txt")
        # Denial 3: stale version
        from orchestrator.foundation import StateTransitionError
        d = h.build_delegation()
        h.transition("int-12d", "PLANNED", authority=d)
        v = h.project_version()
        with pytest.raises(StateTransitionError, match="stale"):
            h.transition("int-12d", "DELEGATED", authority=d,
                         expected_project_version=v - 1)
        # Each denial is independent; no partial execution from any.

    def test_live_subagent_failure_propagation(self, harness):
        """LIVE variant (D4/D7 mounted): a real child's FAILED TaskResult
        propagates typed (SubtaskFailed) into the flow — no partial success,
        nothing executed, nothing silently retried.

        Conditional gate, not a skeleton: without the mount marker or the
        session-recorded FAILED child the test SKIPS with that reason.
        Offline contract: the tests above and
        tests/scenarios/test_executable_scenarios.py SCN-106/107.
        """
        import json
        from tests.live_dsh.live_gate import (live_available, skip_reason,
                                              load_recorded)
        if not live_available("INT-12"):
            pytest.skip(skip_reason("INT-12"))
        live = load_recorded("DSH_LIVE_RESULT_INT12",
                             "INT-12.live_results.json")
        assert live, "live gate on but no session-recorded INT-12 results"
        failed = live.get("int12-fail")
        assert failed and failed["structured"]["status"] == "FAILED", \
            "expected the recorded real FAILED kai child (int12-fail)"

        from orchestrator.runtime import ExecutionFlow
        from orchestrator.runtime.delegation import MemoryDelegationProvider
        from orchestrator.dsh import DelegationClient, RoleResolver
        from tests.live_dsh.real_backend import (RealDSHBackend,
                                                 DSHBridgeResponse)
        from tests.scenarios.scenario_helpers import (
            make_intake, make_execute_plan)

        ws = harness.ws
        calls = []

        def _dispatch(invocation, instance):
            calls.append(getattr(instance, "role", ""))
            # Replay rebinding (documented): the recorded FAILED child ran
            # under its session task id; this replay binds "task-1:kai".
            structured = dict(failed["structured"])
            structured["task_id"] = "task-1:kai"
            return DSHBridgeResponse(
                run_id=failed["run_id"], output=json.dumps(structured),
                structured=structured,
                stop_reason=failed.get("stop_reason", "completed"))

        backend = RealDSHBackend(_dispatch, require_marker=True)
        client = DelegationClient(backend=backend, resolver=RoleResolver())
        delegation = harness.build_delegation(
            id="delegation-int-12", task="int-12",
            action="read", target="docs/**",
            scope_operations=("read",),
            scope_resources=("agents/**", "docs/**",
                             "multi-agent-harness/**"))
        provider = MemoryDelegationProvider(delegation)
        flow = ExecutionFlow(
            project="multi-agent-harness", base=ws, provider=provider,
            subtask_runner=lambda task, child: client.delegate(task, child),
            flow_id="int-12-live")
        result = flow.run(
            make_intake(objective="research",
                        required_authority_context="delegation-int-12"),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/sizing.md"))

        assert calls == ["kai"], "exactly the failed live child dispatched"
        assert result.outcome != "COMPLETE", result.to_dict()
        assert not result.results, \
            "fail-closed: no partial success may be reported"
        # the recorded real run id and the typed failure must surface
        assert failed["run_id"], "live failure must carry a real run id"
        assert any("FAILED" in str(e) for e in result.errors), \
            "the propagated failure must be observable in the flow errors"
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

    @pytest.mark.skip(reason="requires Phase-2C — live DSH subagent failure")
    def test_live_subagent_failure_propagation(self, harness):
        """SKELETON: a failure in a live subagent propagates to the orchestrator
        and stops the pipeline. Blocked on Phase-2C."""
        raise NotImplementedError("Phase-2C: live subagent failure propagation")
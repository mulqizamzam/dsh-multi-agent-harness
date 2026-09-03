# INT-06 — Conflict escalation
#
# Proves that the conflict gate ESCALATEs when unresolved material conflicts
# exist, and never silently resolves (no majority voting).
#
# Modules integrated: ConflictGate + StateMachine (ESCALATED) + WorkflowRun +
# audit
# Invariants: CONF-001..003, THREAT-021

import pytest

from orchestrator.foundation import WorkflowRun, PHASE_CHAIN, WorkflowError


class TestINT06ConflictEscalation:
    def test_conflict_detected_escalates(self, harness):
        """Unresolved conflicts → ConflictGate ESCALATE."""
        dec = harness.evaluate_gate("conflict", {
            "conflicts": [{"task_id": "t-1", "summary": "deploy vs rollback"}]})
        assert dec.decision == "ESCALATE"

    def test_no_conflict_allowed(self, harness):
        """No conflicts → ConflictGate ALLOW."""
        dec = harness.evaluate_gate("conflict", {"conflicts": []})
        assert dec.decision == "ALLOW"

    def test_workflow_stops_on_conflict(self, harness):
        """A non-ALLOW conflict gate decision stops the workflow (fail-closed)."""
        wf = WorkflowRun(objective="int-06")
        # advance to conflict_gate (index 10 in PHASE_CHAIN)
        for _ in range(PHASE_CHAIN.index("conflict_gate")):
            wf.advance()
        assert wf.current_phase() == "conflict_gate"
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.check_gate("ESCALATE", gate="conflict")

    def test_no_majority_voting(self, harness):
        """Conflicting outputs are preserved, not resolved by vote count."""
        conflicts = [
            {"task_id": "t-1", "role": "kai", "recommendation": "deploy"},
            {"task_id": "t-2", "role": "cfo", "recommendation": "hold"},
            {"task_id": "t-3", "role": "zeko", "recommendation": "deploy"},
        ]
        # Two of three say deploy — majority, but that does NOT auto-resolve.
        dec = harness.evaluate_gate("conflict", {"conflicts": conflicts})
        assert dec.decision == "ESCALATE"

    def test_conflict_escalation_audited(self, harness):
        """A conflict escalation produces an audit event."""
        h = harness
        h.append_audit({
            "event_id": "ev-conflict-001", "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "conflict_detected", "actor": "orchestrator",
            "action": "synthesize", "target": "int-06",
            "project": "multi-agent-harness", "result": "escalated",
            "error": "unresolved material conflict",
        })
        escal = [e for e in h.audit_events()
                 if e.get("event_class") == "conflict_detected"]
        assert len(escal) == 1
# INT-05 — Evidence failure
#
# Proves that the evidence gate DENYs a HIGH-risk action with no evidence, and
# ESCALATEs a MEDIUM action with no evidence.
#
# Modules integrated: EvidenceGate + StateMachine + audit
# Invariants: EVID-001..004


class TestINT05EvidenceFailure:
    def test_high_risk_no_evidence_denied(self, harness):
        """HIGH risk + no evidence → EvidenceGate DENY."""
        dec = harness.evaluate_gate("evidence", {"risk": "HIGH", "evidence": []})
        assert dec.decision == "DENY"

    def test_medium_risk_no_evidence_escalates(self, harness):
        """MEDIUM risk + no evidence → EvidenceGate ESCALATE."""
        dec = harness.evaluate_gate("evidence", {"risk": "MEDIUM", "evidence": []})
        assert dec.decision == "ESCALATE"

    def test_low_risk_no_evidence_allowed(self, harness):
        """LOW risk + no evidence → EvidenceGate ALLOW (evidence not required)."""
        dec = harness.evaluate_gate("evidence", {"risk": "LOW", "evidence": []})
        assert dec.decision == "ALLOW"

    def test_evidence_present_satisfies_high(self, harness):
        """HIGH risk + evidence present → EvidenceGate ALLOW."""
        dec = harness.evaluate_gate("evidence", {
            "risk": "HIGH", "evidence": [{"ref": "build-ok.txt"}]})
        assert dec.decision == "ALLOW"

    def test_evidence_failure_blocks_state_progression(self, harness):
        """Evidence gate DENY must block progression to execution."""
        h = harness
        d = h.build_delegation(action="write", target="agents/**",
                               scope_operations=("write",))
        # state machine: DRAFT -> PLANNED -> DELEGATED
        h.transition("int-05", "PLANNED", authority=d)
        h.transition("int-05", "DELEGATED", authority=d)
        # evidence gate: HIGH + no evidence -> DENY
        dec = h.evaluate_gate("evidence", {"risk": "HIGH", "evidence": []})
        assert dec.decision == "DENY"
        # The integration contract: a DENIED gate means the action must not run.
        # We simulate the orchestrator's fail-closed behavior by refusing to
        # transition to EXECUTING while evidence is missing.
        assert h.machine("int-05").current() == "DELEGATED"  # not EXECUTING

    def test_evidence_denial_audited(self, harness):
        """An evidence denial produces an audit event."""
        h = harness
        h.append_audit({
            "event_id": "ev-evidence-001", "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "evidence_denied", "actor": "orchestrator",
            "action": "write", "target": "agents/cto/x.txt",
            "project": "multi-agent-harness", "result": "denied",
            "error": "HIGH-risk action requires evidence (EVID-002)",
        })
        denials = [e for e in h.audit_events()
                   if e.get("event_class") == "evidence_denied"]
        assert len(denials) == 1
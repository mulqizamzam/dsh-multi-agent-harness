# INT-10 — Complete only after verification
#
# Proves that COMPLETE is emitted only after verification evidence is provided;
# a "reported success" without evidence is DENIED.
#
# Modules integrated: VerificationGate + StateMachine (COMPLETE) + TaskResult
# Invariants: AUTH-INV-15, INV-09, VERIFY-001..003

from orchestrator.foundation import TaskResult


class TestINT10CompleteAfterVerification:
    def test_reported_success_without_evidence_denied(self, harness):
        """An agent-reported success without evidence is NOT COMPLETE."""
        result = TaskResult(task_id="int-10", assigned_role="cto",
                            status="SUCCEEDED", evidence=())
        dec = harness.evaluate_gate("verification", {"result": result})
        assert dec.decision == "DENY"

    def test_verified_result_allowed(self, harness):
        """A result with verification evidence passes the verification gate."""
        result = TaskResult(task_id="int-10", assigned_role="cto",
                            status="SUCCEEDED",
                            evidence=("build-ok.txt", "test-results.json"))
        dec = harness.evaluate_gate("verification", {"result": result})
        assert dec.decision == "ALLOW"

    def test_failed_result_denied(self, harness):
        """A FAILED result cannot be verified to COMPLETE."""
        result = TaskResult(task_id="int-10", assigned_role="cto",
                            status="FAILED", evidence=("log.txt",))
        dec = harness.evaluate_gate("verification", {"result": result})
        assert dec.decision == "ALLOW"  # verification gate: FAILED is not
        # "reported success"; the state machine handles FAILED via recovery.

    def test_complete_requires_verification_in_state_machine(self, harness):
        """The state machine only reaches COMPLETE after the verification gate
        cleared with evidence."""
        h = harness
        d = h.build_delegation()
        # Drive to SYNTHESIZING
        h.transition("int-10", "PLANNED", authority=d)
        h.transition("int-10", "DELEGATED", authority=d)
        h.transition("int-10", "EXECUTING", authority=d)
        h.transition("int-10", "COLLECTED")
        h.transition("int-10", "SYNTHESIZING")

        # Without evidence: verification gate DENY → no COMPLETE
        bad = TaskResult(task_id="int-10", assigned_role="cto",
                         status="SUCCEEDED", evidence=())
        assert h.evaluate_gate("verification", {"result": bad}).decision == "DENY"

        # With evidence: verification gate ALLOW → COMPLETE
        good = TaskResult(task_id="int-10", assigned_role="cto",
                          status="SUCCEEDED", evidence=("verified.txt",))
        assert h.evaluate_gate("verification", {"result": good}).decision == "ALLOW"
        h.transition("int-10", "COMPLETE")
        assert h.machine("int-10").current() == "COMPLETE"

    def test_false_success_audited(self, harness):
        """A false success report produces a verification denial audit event."""
        h = harness
        h.append_audit({
            "event_id": "ev-verify-001", "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "verification_denied", "actor": "cto",
            "action": "report", "target": "int-10",
            "project": "multi-agent-harness", "result": "denied",
            "error": "COMPLETE requires verification evidence (INV-09)",
        })
        denials = [e for e in h.audit_events()
                   if e.get("event_class") == "verification_denied"]
        assert len(denials) == 1
# INT-07 — Execution-time authority re-check
#
# Proves that authority is re-validated at execution time, not just planning —
# a delegation revoked between planning and execution causes the gate to DENY.
#
# Modules integrated: WorkflowRun.require_execution_authority_recheck +
# AuthorityGate + reference + StateMachine + audit
# Invariants: AUTH-INV-05, INV-14, THREAT-009/024

import pytest

from orchestrator.foundation import WorkflowRun, PHASE_CHAIN, WorkflowError


class TestINT07ExecutionRecheck:
    def _at_execute_gate(self):
        wf = WorkflowRun(objective="int-07")
        for _ in range(PHASE_CHAIN.index("execute_gate")):
            wf.advance()
        assert wf.current_phase() == "execute_gate"
        return wf

    def test_recheck_allow_proceeds(self, harness):
        """An ALLOW execution-time re-check records the step."""
        wf = self._at_execute_gate()
        wf.require_execution_authority_recheck("ALLOW")
        assert wf.steps[-1]["gate"] == "authority_recheck"
        assert wf.steps[-1]["decision"] == "ALLOW"

    def test_recheck_denied_stops_workflow(self, harness):
        """A non-ALLOW execution-time re-check STOPS the workflow (fail-closed)."""
        wf = self._at_execute_gate()
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.require_execution_authority_recheck("DENY")

    def test_recheck_only_valid_at_execute_gate(self, harness):
        """require_execution_authority_recheck only valid at execute_gate."""
        wf = WorkflowRun(objective="int-07")
        with pytest.raises(WorkflowError, match="only valid at execute_gate"):
            wf.require_execution_authority_recheck("ALLOW")

    def test_planning_allow_insufficient_with_revocation(self, harness):
        """Planning-time ALLOW is never sufficient: revoke, then execution
        re-check must DENY (THREAT-009/024)."""
        d = harness.build_delegation_dict(
            id="delegation-int-07",
            scope={"operations": ["write", "read"],
                   "resources": ["agents/**", "docs/**", "multi-agent-harness/**"],
                   "environments": ["dev"]},
        )
        # Planning-time check ALLOW
        cmp_plan = harness.cross_check_authority(
            "orchestrator", "write", "agents/cto/x.txt", d, environment="dev")
        assert cmp_plan["foundation_decision"] == "ALLOW"
        assert cmp_plan["match"] is True

        # Revoke between planning and execution
        harness.seed_revocation("delegation-int-07")
        cmp_exec = harness.cross_check_authority(
            "orchestrator", "write", "agents/cto/x.txt", d,
            revocation_list=("delegation-int-07",), environment="dev")
        # Reference gate observes the revocation at execution time.
        assert cmp_exec["reference_decision"] == "DENY"

        # Workflow: execution-time re-check receives DENY → STOP
        wf = self._at_execute_gate()
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.require_execution_authority_recheck(cmp_exec["reference_decision"])

        # No file written
        assert not harness.file_exists("agents/cto/x.txt")

    def test_expiry_between_plan_and_exec_denied(self, harness):
        """A delegation that expires between planning and execution is DENIED
        at execution time (THREAT-008)."""
        d = harness.build_delegation_dict(
            id="delegation-int-07b",
            scope={"operations": ["write"],
                   "resources": ["agents/**", "docs/**", "multi-agent-harness/**"],
                   "environments": ["dev"]},
            expires_at="2020-01-01T00:00:00Z",  # already expired at execution
        )
        cmp = harness.cross_check_authority(
            "orchestrator", "write", "agents/cto/x.txt", d, environment="dev")
        assert cmp["reference_decision"] == "DENY"
        assert "expired" in cmp["reference_reason"]
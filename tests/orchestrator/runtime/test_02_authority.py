# RT-02 — Authority enforcement in the runtime flow
#
# Scenarios:
#   - authority denial (missing delegation / action outside scope)
#   - revoked authority during execution (execution-time re-check, THREAT-009)
#   - target mismatch (AUTH-INV-11)
#
# Every denial STOPS the flow (fail-closed, AUTH-INV-20); no consequential
# write occurs; audit records the denial.

import os

from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, BLOCKED,
)

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    MemoryDelegationProvider,
)


class TestAuthorityDenial:
    def test_missing_delegation_escalates(self, ws, subtask_runner):
        """No delegation for the authority context -> ESCALATED (intake not
        actionable without authority)."""
        provider = MemoryDelegationProvider(None)
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner)
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/output.txt"))
        assert result.outcome == "ESCALATED"
        assert "authority context" in result.errors[0]

    def test_action_outside_scope_denied(self, flow, subtask_runner, ws):
        """Delegation grants 'read' only; execute action 'write' -> DENY at
        authority gate (AUTH-INV-04/18)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        flow.provider = provider
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        # audit has an authority denial
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "gate_authority"
                   and e.get("result") == "denied" for e in events)

    def test_missing_authority_context_escalates(self, flow):
        """Intake without required authority context -> ESCALATED."""
        result = flow.run(make_intake(
            objective="engineering",
            required_authority_context=""))
        assert result.outcome == "ESCALATED"


class TestRevokedAuthorityDuringExecution:
    def test_revocation_between_plan_and_execute_denied(self, flow,
                                                        subtask_runner, ws):
        """Planning ALLOW; revocation observed by the execution-time re-check
        -> DENY (THREAT-009/024, AUTH-INV-05/06)."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))

        def _revoke_before_execute():
            flow.provider.revoke("delegation-test-001",
                                 reason="revoked during execution")

        flow.pre_execute = _revoke_before_execute
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "execution_denial"
                   for e in events)


class TestTargetMismatch:
    def test_target_outside_delegation_resources_denied(self, flow,
                                                        subtask_runner, ws):
        """AUTHORIZED target A, execution target B outside resources ->
        DENY (AUTH-INV-11)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_resources=("docs/**",),
        ))
        flow.provider = provider
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_planning_authority_gate_rejects_out_of_scope(self, flow,
                                                          subtask_runner):
        """Planning authority gate (authority_gate phase) rejects an action
        the delegation does not cover."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",),
            scope_resources=("agents/**",),
        ))
        flow.provider = provider
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        gate = [g for g in result.gates if g["gate"] == "authority"]
        assert gate and gate[0]["decision"] == "DENY"
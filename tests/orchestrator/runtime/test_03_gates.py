# RT-03 — Gate enforcement in the runtime flow
#
# Scenarios:
#   - risk denial (intrinsic HIGH declared LOW -> downgrade attempt DENY)
#   - evidence failure (HIGH risk without evidence -> DENY)
#   - conflict escalation (contradictory positions with evidence -> ESCALATE)
#   - BadSector reject (REJECT verdict -> DENY)
#
# Each gate failure STOPS the flow with the correct terminal disposition
# (BLOCKED or ESCALATED), produces audit events, and leaves no side-effect.

import os

from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, BLOCKED, ESCALATED,
)

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    MemoryDelegationProvider,
)


class TestRiskDenial:
    def test_downgrade_intrinsic_high_to_low_denied(self, flow, subtask_runner):
        """Declaring LOW on an intrinsically HIGH action (destructive) -> DENY
        at risk_gate (AUTH-INV-10)."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(action="destructive",
                                           target="agents/cto/evil.txt"),
            declared_risk="LOW",
        )
        assert result.outcome == BLOCKED
        assert result.phase == "risk_gate"

    def test_declared_high_allows_risk_but_later_gate_may_deny(self, flow,
                                                               subtask_runner):
        """A declared HIGH that is not a downgrade passes the risk gate; the
        mandatory BadSector review (HIGH) then denies without a review
        (THREAT-015)."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(action="write",
                                           target="agents/cto/output.txt"),
            declared_risk="HIGH",
        )
        assert result.outcome == BLOCKED
        # HIGH risk -> risk gate ALLOW (not a downgrade) -> mandatory review
        # skipped at adversarial_review -> DENY (THREAT-015)
        assert result.phase == "adversarial_review"
        risk_gates = [g for g in result.gates if g["gate"] == "risk"]
        assert risk_gates and risk_gates[-1]["decision"] == "ALLOW"
        assert risk_gates[-1]["detail"].get("risk") == "HIGH"


class TestEvidenceFailure:
    def test_high_risk_without_evidence_denied(self, flow, subtask_runner):
        """HIGH risk with no evidence results -> evidence gate DENY
        (EVID-001/002)."""
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=()))  # no evidence
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            declared_risk="HIGH",
        )
        assert result.outcome == BLOCKED
        assert result.phase == "evidence_gate"
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "gate_evidence"
                   and e.get("result") == "denied" for e in events)


class TestConflictEscalation:
    def _pricing_flow(self, ws, subtask_runner, action_executor):
        """A flow over a Pricing objective (cfo + kai minimum set) with a
        shared delegation."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        return ExecutionFlow(
            base=ws, provider=provider, subtask_runner=subtask_runner,
            executor=action_executor, flow_id="test-conflict")

    def test_contradictory_recommendations_escalate(self, ws, subtask_runner,
                                                    action_executor):
        """Contradictory recommendations on the same decision point with
        evidence on both sides -> CONFLICT_GATE ESCALATE -> ESCALATED (no
        majority voting, CONF-001..003)."""
        flow = self._pricing_flow(ws, subtask_runner, action_executor)
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="deploy",
            findings=("deploy recommended",), evidence=("src:1",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="rollback",
            findings=("rollback recommended",), evidence=("src:2",)))
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(target="docs/pricing.md"))
        assert result.outcome == ESCALATED
        assert result.phase == "conflict_gate"
        # audit records the conflict escalation
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "gate_conflict"
                   and e.get("result") == "escalated" for e in events)


class TestBadSectorReject:
    def test_review_required_with_reject_denied(self, flow, subtask_runner):
        """A mandatory BadSector review returning REJECT -> DENY at
        adversarial_review (THREAT-014/015)."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review={"verdict": "REJECT", "review_id": "review-1",
                    "input_hash": "hash-1"},
        )
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"

    def test_review_required_without_review_denied(self, flow, subtask_runner):
        """A mandatory review that was skipped -> DENY (THREAT-015)."""
        subtask_runner.add("cto", make_subtask_result("task-1:cto", "cto", recommendation="write module", evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review=None,
        )
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"
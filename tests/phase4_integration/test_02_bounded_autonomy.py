# P4I-02 — Bounded autonomy
#
# Proves that autonomy is bounded by the delegation scope: no delegation →
# ESCALATED, scope mismatch → DENY, revocation mid-flow → DENY, HIGH without
# approval → ESCALATED. Every denial stops the flow fail-closed, produces no
# mutation, and records an audit event. No continuation past a denial.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Acceptance rows: AEF-2, AEF-4, AUTH-1, AUTH-2, PB-1

import os

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
    StubActionExecutor, make_review_pass, audit_classes,
)


class TestBoundedAutonomy:
    """P4I-02: every denial stops the flow fail-closed; no mutation."""

    def test_no_delegation_escalates(self, ws):
        """No delegation for the authority context → NoValidDelegation."""
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped, NoValidDelegation,
        )
        sr = StubSubtaskRunner()
        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=None, subtask_runner=sr,
                parallel_subtasks=False)
            assert False, "expected NoValidDelegation"
        except NoValidDelegation:
            pass
        # No mutation
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_scope_mismatch_denied(self, ws):
        """Read-only delegation + write action → DENY, no file."""
        delegation = make_delegation(scope_operations=("read",))
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, subtask_runner=sr,
                parallel_subtasks=False)
            assert False, "expected ProductionDenied"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_revocation_mid_flow_denied(self, ws, delegation):
        """Revocation between planning and execution → DENY, no mutation."""
        from orchestrator.runtime import MemoryDelegationProvider
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        provider = MemoryDelegationProvider(delegation)
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def revoke():
            provider.revoke(delegation.id)

        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, provider=provider,
                subtask_runner=sr, pre_execute=revoke,
                parallel_subtasks=False)
            assert False, "expected ProductionDenied"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        # No file written
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        # Audit contains execution_denial
        classes = audit_classes(ws)
        assert "execution_denial" in classes, f"classes={classes}"

    def test_high_without_approval_denied(self, ws):
        """HIGH financial action without approval never auto-approved."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        result = make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("analysis complete",), evidence=("artifact:cfo",))
        sr = StubSubtaskRunner()
        sr.add("cfo", result)

        from orchestrator.production import (
            BoundedExecutor, ProductionDenied, ProductionEscalated,
        )
        from orchestrator.production.planner import ObjectivePlanner

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH", action="financial_transaction")

        review = make_review_pass(
            "task-1", "finance analysis for a transaction", "HIGH", [result])

        ex = BoundedExecutor(base=ws, subtask_runner=sr,
                             executor=lambda p: {"exit_code": 0,
                                                 "target": "docs/report.md"})
        try:
            ex.execute(plan, delegation=delegation, review=review)
            assert False, "expected ProductionDenied/Escalated"
        except (ProductionDenied, ProductionEscalated):
            pass
        # No file written
        assert not os.path.exists(os.path.join(ws, "docs/report.md"))

    def test_badsector_pass_alone_not_authority(self, ws):
        """BadSector PASS without a covering delegation is refused."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("read",),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        result = make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",))
        sr = StubSubtaskRunner()
        sr.add("cfo", result)

        from orchestrator.production import (
            BoundedExecutor, ProductionDenied, ProductionEscalated,
        )
        from orchestrator.production.planner import ObjectivePlanner

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH", action="financial_transaction")

        ex = BoundedExecutor(base=ws, subtask_runner=sr,
                             executor=lambda p: {"exit_code": 0,
                                                 "target": "docs/report.md"})
        try:
            ex.execute(plan, delegation=delegation,
                       review=make_review_pass(
                           "task-1", "finance analysis for a transaction",
                           "HIGH", [result]),
                       approval_reference="approval-fin-001")
            assert False, "expected ProductionDenied"
        except (ProductionDenied, ProductionEscalated):
            pass
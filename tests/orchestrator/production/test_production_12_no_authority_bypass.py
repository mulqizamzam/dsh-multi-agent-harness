# PROD-12 — No-authority bypass
#
# A production run cannot be started without a valid structured delegation,
# cannot treat model text / state records / audit entries / review verdicts as
# authority, and cannot be auto-approved. Every bypass attempt stops
# fail-closed.
#
# Tests: AUTH-INV-01/05/07/09/13/14, AEF-2

from conftest import make_delegation, make_subtask_result

from orchestrator.production import (
    ProductionRun, ProductionDenied, ProductionEscalated,
    NoValidDelegation, ObjectiveNotActionable, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestNoAuthorityBypass:
    def test_no_authority_context_rejected(self, ws):
        """An objective without an authority context is not actionable."""
        planner = ObjectivePlanner()
        try:
            planner.plan(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="")
            assert False, "expected ObjectiveNotActionable"
        except ObjectiveNotActionable as e:
            assert "authority context" in str(e).lower()

    def test_dict_is_not_delegation(self, ws, subtask_runner):
        """A plain dict / model text is not a delegation (AUTH-INV-01/05)."""
        delegation = make_delegation()
        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "agents/cto/output.txt"})
        try:
            ex.execute(plan, delegation={"id": "delegation-prod-001"})  # not a Delegation
            assert False, "expected dict delegation to be refused"
        except ProductionDenied as e:
            assert "structured delegation" in str(e).lower() or \
                   "delegation" in str(e).lower()

    def test_audit_entry_is_not_authority(self, ws, subtask_runner):
        """An audit record claiming approval is never authority (AUTH-INV-14)."""
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("financial_transaction", "read"),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        # Only a structured approval reference works; audit text does not.
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "docs/report.md"})
        try:
            ex.execute(
                plan, delegation=delegation,
                review={"verdict": "PASS", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                approval_reference="audit-claim-001")  # not approval-<id>
            assert False, "expected the non-approval reference to be refused"
        except (ProductionDenied, ProductionEscalated) as e:
            assert True

    def test_badsector_pass_alone_is_not_authority(self, ws, subtask_runner):
        """A BadSector PASS without a covering delegation is refused
        (AUTH-INV-09)."""
        # Delegation does NOT cover financial_transaction.
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("read",),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",)))

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "docs/report.md"})
        try:
            ex.execute(
                plan, delegation=delegation,
                review={"verdict": "PASS", "review_id": "rev-001",
                        "input_hash": "a" * 64},
                approval_reference="approval-fin-001")
            assert False, "expected the uncovered action to be refused"
        except (ProductionDenied, ProductionEscalated):
            pass

    def test_run_requires_delegation(self, ws, subtask_runner):
        """ProductionRun without a delegation → NoValidDelegation."""
        run = ProductionRun(base=ws)
        try:
            run.run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=None, subtask_runner=subtask_runner)
            assert False, "expected NoValidDelegation"
        except NoValidDelegation:
            pass
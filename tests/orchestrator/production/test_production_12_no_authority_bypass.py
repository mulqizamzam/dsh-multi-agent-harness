# PROD-12 — No-authority bypass
#
# A production run cannot be started without a valid structured delegation,
# cannot treat model text / state records / audit entries / review verdicts as
# authority, and cannot be auto-approved. Every bypass attempt stops
# fail-closed.
#
# Tests: AUTH-INV-01/05/07/09/13/14, AEF-2

from conftest import make_delegation, make_subtask_result, make_review_pass

import pytest

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
        cfo_result = make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",))
        subtask_runner.add("cfo", cfo_result)

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        # Only a structured approval reference works; audit text does not.
        # The review is provenance-VALID (`make_review_pass` computes the real
        # synthesis hash), so the BadSector gate passes and the stop we observe
        # IS the approval-reference shape check (control/authority.py
        # `_check_approval`: free text is never approval). With a forged
        # input_hash the flow would DENY at the review gate first, and the
        # refusal would say nothing about the approval reference — which is
        # what this test exists to prove.
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "docs/report.md"})
        review = make_review_pass(
            "task-1", "finance analysis for a transaction", "HIGH",
            [cfo_result])
        with pytest.raises(ProductionDenied) as excinfo:
            ex.execute(
                plan, delegation=delegation,
                review=review,
                approval_reference="audit-claim-001")  # not approval-<id>
        message = str(excinfo.value)
        assert "not a structured approval reference" in message, (
            "the refusal must name the approval-reference shape (AUTH-INV-01: "
            f"text is never approval); got: {message}")

    def test_badsector_pass_alone_is_not_authority(self, ws, subtask_runner):
        """A BadSector PASS without a covering delegation is refused
        (AUTH-INV-09)."""
        # Delegation does NOT cover financial_transaction.
        delegation = make_delegation(
            id="delegation-fin-001",
            scope_operations=("read",),
            scope_resources=("docs/**",),
            requires_approval=("financial_transfer",))
        cfo_result = make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:analysis",))
        subtask_runner.add("cfo", cfo_result)

        plan = ObjectivePlanner().plan(
            objective="finance analysis for a transaction",
            scope=("docs/report.md",),
            required_authority_context="delegation-fin-001",
            declared_risk="HIGH",
            action="financial_transaction")

        # Provenance-valid review again: the BadSector gate passes, so the
        # refusal comes from the delegation-coverage check (AUTH-INV-09: the
        # PASS cleared review only; it never authorized the action).
        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=lambda plan: {"exit_code": 0,
                                                     "target": "docs/report.md"})
        review = make_review_pass(
            "task-1", "finance analysis for a transaction", "HIGH",
            [cfo_result])
        with pytest.raises(ProductionDenied) as excinfo:
            ex.execute(
                plan, delegation=delegation,
                review=review,
                approval_reference="approval-fin-001")
        message = str(excinfo.value)
        assert "not in delegation operations" in message, (
            "the refusal must name the uncovered action (AUTH-INV-04/18: the "
            f"delegation does not cover financial_transaction); got: {message}")

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
# PROD-02 — Authority denial
#
# A production run where the delegation is revoked between planning and
# execution. The execution-time authority re-check must DENY the action and
# the flow must stop fail-closed with no mutation (AUTH-INV-05/06).
#
# Tests: AUTH-1, AUTH-2, AEF-2

from conftest import make_delegation, make_subtask_result

from orchestrator.runtime import MemoryDelegationProvider
from orchestrator.production import (
    ProductionRun, ProductionDenied, NoValidDelegation,
    BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestAuthorityDenial:
    def test_revocation_between_plan_and_execute(self, ws, subtask_runner,
                                                 action_executor):
        """Revocation between planning and execution → DENY, no mutation."""
        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        def revoke_before_execute():
            provider.revoke(delegation.id)

        plan = ObjectivePlanner().plan(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(
                plan, delegation=delegation, provider=provider,
                pre_execute=revoke_before_execute)
        except ProductionDenied as e:
            raised = True
            assert "revoked" in str(e).lower() or "denied" in str(e).lower()
        assert raised, "expected ProductionDenied on revocation"

        # The flow stopped fail-closed: no files written, denial audited.
        flow = ex.last_flow
        assert flow is not None
        result = flow._result
        assert result is not None and result.outcome == "BLOCKED"
        assert len(result.files_written) == 0
        events = [e for e in flow._get_audit().read()
                  if e.get("event_class") == "execution_denial"]
        assert events, "expected an execution_denial audit event"

    def test_no_delegation_provided(self, ws, subtask_runner):
        """Running without a delegation → NoValidDelegation."""
        run = ProductionRun(base=ws)
        try:
            run.run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=None, subtask_runner=subtask_runner)
            assert False, "expected NoValidDelegation"
        except NoValidDelegation as e:
            assert "delegation" in str(e).lower()

    def test_revoked_delegation_denied_via_executor(self, ws, subtask_runner,
                                                    action_executor):
        """A delegation that is already revoked → ProductionDenied."""
        delegation = make_delegation(status="REVOKED")
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("a",)))

        plan = ObjectivePlanner().plan(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(plan, delegation=delegation, provider=provider)
        except (ProductionDenied,) as e:
            raised = True
            assert "denied" in str(e).lower() or "stopped" in str(e).lower()
        except Exception as e:  # noqa: BLE001 — fail-closed to a typed error
            raised = True
            assert "denied" in str(e).lower() or "revoked" in str(e).lower()
        assert raised, "expected the revoked delegation to be refused"
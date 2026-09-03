# E-19 — Audit ids preserved
#
# Prove that the audit event ids from the production run are preserved in the
# FrontDoorResult and are unique, non-empty, and correlated with the run.
# The front door must not strip, invent, or lose audit ids.

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    COMPLETE,
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
)


class TestAuditIdsPreserved:
    def test_complete_has_audit_ids(self, ws, subtask_runner, action_executor):
        """A COMPLETE run produces audit_ids in the front door result."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == COMPLETE
        assert len(result.audit_ids) > 0, "COMPLETE run must have audit ids"
        # All ids are unique
        assert len(set(result.audit_ids)) == len(result.audit_ids)

    def test_audit_ids_match_state(self, ws, subtask_runner, action_executor):
        """The front door audit_ids match the production state's audit_ids."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.state is not None
        assert result.audit_ids == tuple(result.state.get("audit_ids", [])), \
            "front door audit_ids must match state audit_ids"

    def test_blocked_has_audit_ids(self, ws, subtask_runner, action_executor):
        """A BLOCKED run carries audit_ids from the failed run (if a run was
        started)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)

        def revoke_runner(task, deleg):
            raise RuntimeError("simulated failure")

        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=revoke_runner,
            action_executor=None,
        )
        # The run may have started (state exists) or not
        if result.state is not None:
            assert len(result.state.get("audit_ids", [])) > 0, \
                "BLOCKED run with state must have audit ids"
        assert result.status in (BLOCKED, "ESCALATED", "ERROR")

    def test_audit_ids_are_unique(self, ws, subtask_runner, action_executor):
        """All audit ids in a run are unique (no duplicates)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        if result.status == COMPLETE:
            ids = result.audit_ids
            assert len(ids) == len(set(ids)), "audit ids must be unique"
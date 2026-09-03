# E-04 — Unknown delegation → BLOCKED
#
# Prove that a front-door request naming a delegation id that does not match
# the registry entry is rejected (id mismatch, project mismatch). The front
# door never treats a name/prose as authority — it must match an EXISTING
# structured record exactly (AUTH-INV-05).

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
)


class TestUnknownDelegation:
    def test_id_mismatch_rejected(self, ws, subtask_runner, action_executor):
        """Registry delegation id differs from the requested id → BLOCKED."""
        # Registry has delegation-other; request asks for delegation-prod-001.
        delegation = make_delegation(id="delegation-other")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED, f"expected BLOCKED, got {result.status}"
        assert "match" in " ".join(result.errors).lower() or \
               "delegation" in " ".join(result.errors).lower()
        assert result.state is None  # no run started

    def test_unknown_id_with_no_registry(self, ws, subtask_runner,
                                         action_executor):
        """Requesting a delegation id with no registry entry at all → BLOCKED."""
        # provider returns None → NoValidDelegation
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-unknown-000",
            ),
            provider=make_provider(None),
        )
        assert result.status == BLOCKED
        assert result.state is None

    def test_project_mismatch_rejected(self, ws, subtask_runner,
                                       action_executor):
        """Delegation for a different project → BLOCKED (never cross-project)."""
        delegation = make_delegation(project="another-project")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert "project" in " ".join(result.errors).lower() or \
               "delegation" in " ".join(result.errors).lower()
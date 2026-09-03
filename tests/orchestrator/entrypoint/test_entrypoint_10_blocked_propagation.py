# E-10 — BLOCKED propagation
#
# Prove that a gate denial inside the bounded run propagates out of the front
# door as a deterministic BLOCKED status with the error preserved — never a
# fabricated COMPLETE. This covers missing/revoked/expired delegation
# (resolved at the front door), and gate denials inside ProductionRun
# (authority / scope / review).

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    COMPLETE,
    run_front_door,
    FrontDoorRequest,
)


class TestBlockedPropagation:
    def test_revoked_propagates_blocked(self, ws, subtask_runner,
                                        action_executor):
        """A revoked delegation → BLOCKED with the reason preserved."""
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
            provider=make_provider(delegation,
                                   revoked=("delegation-prod-001",)),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert result.status != COMPLETE
        assert any("revoked" in e.lower() for e in result.errors)

    def test_no_delegation_propagates_blocked(self, ws):
        """No delegation in registry → BLOCKED (never COMPLETE)."""
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(None),
        )
        assert result.status == BLOCKED
        assert result.report is None
        assert result.state is None

    def test_scope_denial_propagates_blocked(self, ws, subtask_runner,
                                             action_executor):
        """A scope denial inside the run → BLOCKED, error preserved."""
        delegation = make_delegation(
            scope_operations=("read", "analysis"),
            scope_resources=("docs/**", "multi-agent-harness/**"),
        )
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("docs/design/x.md",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        assert result.errors  # reason preserved

    def test_no_silent_success_on_blocked(self, ws, subtask_runner,
                                          action_executor):
        """BLOCKED never carries a report with outcome COMPLETE."""
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
            provider=make_provider(delegation,
                                   revoked=("delegation-prod-001",)),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
        if result.report is not None:
            assert result.report.get("outcome") != "COMPLETE"
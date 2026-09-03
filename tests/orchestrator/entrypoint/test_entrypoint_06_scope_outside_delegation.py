# E-06 — Scope outside delegation → BLOCKED
#
# Prove that a request whose scope/action falls outside the delegation's
# granted scope is denied by the authority chain. The front door forwards the
# scope unchanged to ProductionRun; the runtime authority gate + execution
# gate enforce containment (AUTH-INV-04/11/18). The front door never widens a
# grant.

import os

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
)


class TestScopeOutsideDelegation:
    def test_action_outside_scope_blocked(self, ws, subtask_runner,
                                          action_executor):
        """Delegation grants read-only; request implies write → BLOCKED."""
        delegation = make_delegation(
            scope_operations=("read", "analysis"),
            scope_resources=("docs/**", "multi-agent-harness/**"),
        )
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        # objective "engineering" → write action; delegation has no write op.
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
        assert result.status == BLOCKED, f"expected BLOCKED, got {result.status}"
        # no file should have been written through the gate
        assert not os.path.exists(os.path.join(ws, "docs", "design", "x.md"))

    def test_target_outside_resources_blocked(self, ws, subtask_runner,
                                              action_executor):
        """Delegation covers docs/**; request targets agents/cto → BLOCKED."""
        delegation = make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("docs/**",),
        )
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
        assert result.status == BLOCKED, f"expected BLOCKED, got {result.status}"
        assert not os.path.exists(os.path.join(ws, "agents", "cto", "output.txt"))

    def test_protected_path_scope_blocked(self, ws, subtask_runner,
                                          action_executor):
        """Scope targeting the protected registry → BLOCKED at execution gate
        (ADR 0002). The front door cannot route a write into state/registry."""
        delegation = make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("state/registry/**",),
        )
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("state/registry/x.json",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == BLOCKED
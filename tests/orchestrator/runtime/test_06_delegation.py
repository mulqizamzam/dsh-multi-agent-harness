# RT-06 — Delegation enforcement in the runtime flow
#
# Scenarios:
#   - subdelegation denial (specialist → specialist refused)
#   - scope containment (child delegation ⊆ parent scope)
#   - expired delegation (past expires_at -> DENY)
#   - no delegation = no action (authority context missing)

from datetime import datetime, timedelta, timezone

import pytest

from orchestrator.foundation.contracts import Delegation, Task, ORCHESTRATOR
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, BLOCKED, ESCALATED,
    DelegationLifecycle, MemoryDelegationProvider,
)
from control.delegation import (
    issue_child_delegation, assert_actor_may_delegate, SubdelegationDenied,
    DelegationError, scope_contained,
)

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
)


class TestSubdelegationDenial:
    def test_non_orchestrator_denied(self):
        """Any actor other than the orchestrator attempting to delegate is
        DENIED (DLG-003: subdelegation DENY BY DEFAULT)."""
        with pytest.raises(SubdelegationDenied, match="subdelegation"):
            assert_actor_may_delegate("cto")

    def test_orchestrator_allowed(self):
        """The orchestrator may delegate (the sole exception to DLG-003)."""
        # Should not raise
        assert_actor_may_delegate(ORCHESTRATOR)

    def test_child_delegation_outside_parent_scope_denied(self):
        """A child delegation whose scope exceeds the parent's is refused
        (AUTH-INV-04)."""
        parent = make_delegation(
            scope_operations=("read",),
            scope_resources=("docs/**",),
        )
        with pytest.raises(DelegationError, match="scope exceeds"):
            issue_child_delegation(
                ORCHESTRATOR, parent, task="test-task",
                scope_operations=("write",),  # not in parent ops
                scope_resources=("docs/**",))


class TestExpiredAuthority:
    def test_expired_delegation_denied(self, ws, subtask_runner):
        """A delegation with an expired timestamp is treated as absent
        (AUTH-INV-06) — the flow stops."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1))\
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        expired = make_delegation(expires_at=past)
        provider = MemoryDelegationProvider(expired)
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-expired01")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        # The delegation is expired → authority gate DENY → BLOCKED
        assert result.outcome == BLOCKED, result.to_dict()
        assert any("expired" in e.lower() for e in result.errors)


class TestScopeContainment:
    def test_target_outside_resources_denied(self, ws, subtask_runner):
        """A target outside the delegation's scope_resources is refused at the
        authority gate (AUTH-INV-11)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_resources=("docs/**",)))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-scope01")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/out.txt"))
        assert result.outcome == BLOCKED
        gates = [g for g in result.gates if g["gate"] == "authority"]
        assert gates and gates[-1]["decision"] == "DENY"

    def test_action_outside_operations_planning_denied(self, ws, subtask_runner):
        """An action outside the delegation's scope_operations is refused at
        planning-time authority gate (AUTH-INV-04/18)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",),
            scope_resources=("docs/**", "multi-agent-harness/**")))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-scope02")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(action="write",
                                           target="agents/cto/out.txt"))
        assert result.outcome == BLOCKED
        auth_gates = [g for g in result.gates if g["gate"] == "authority"]
        assert auth_gates and auth_gates[-1]["decision"] == "DENY"

    def test_child_scope_contained_in_parent(self):
        """scope_contained() returns True when child ⊆ parent."""
        parent = make_delegation(
            scope_operations=("read", "write"),
            scope_resources=("agents/**", "docs/**"),
        )
        child = make_delegation(
            scope_operations=("read",),
            scope_resources=("agents/cto/**",),
        )
        assert scope_contained(child, parent)

    def test_child_scope_not_contained(self):
        """scope_contained() returns False when child ⊈ parent."""
        parent = make_delegation(
            scope_operations=("read",),
            scope_resources=("docs/**",),
        )
        child = make_delegation(
            scope_operations=("write",),  # not in parent
            scope_resources=("docs/**",),
        )
        assert not scope_contained(child, parent)

    def test_delegation_lifecycle_asserts_may_delegate(self):
        """DelegationLifecycle.assert_may_delegate refuses non-orchestrator."""
        lifecycle = DelegationLifecycle()
        lifecycle.assert_may_delegate(ORCHESTRATOR)  # no raise
        with pytest.raises(SubdelegationDenied):
            lifecycle.assert_may_delegate("cto")
# Category C — SCOPE
#
# Prove the front door's scope is contained within the delegation's resources
# (AUTH-INV-04/11). Adversarial scope inputs:
#   C1 empty scope          C2 malformed scope        C3 path traversal
#   C4 absolute path        C5 sibling-prefix confusion
#   C6 protected paths      C7 scope outside delegation resources
#
# Classification: C1–C2 → ERROR (shape); C3–C7 → DENY (BLOCKED) via authority
# gate or execution gate — NEVER COMPLETE.

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

from .conftest import (  # noqa: E402
    make_delegation, make_subtask_result, make_provider, seed_state,
)


class TestEmptyScope:
    def test_empty_scope_tuple(self, front_door):
        """C1: an empty scope tuple is a shape ERROR — no objective can be
        actionable without a bounded scope."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": (),
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == "ERROR"
        assert "scope" in result.errors[0].lower()

    def test_empty_scope_list(self, front_door):
        """C1: an empty scope list is also a shape ERROR."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": [],
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == "ERROR"
        assert "scope" in result.errors[0].lower()


class TestMalformedScope:
    def test_non_string_scope_entry(self, front_door):
        """C2: a non-string scope entry (e.g. integer) is a shape ERROR."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": (42,),
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == "ERROR"
        assert "scope" in result.errors[0].lower()

    def test_blank_scope_entry(self, front_door):
        """C2: a whitespace-only scope entry is a shape ERROR."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": ("  ",),
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == "ERROR"
        assert "scope" in result.errors[0].lower()

    def test_scope_with_none(self, front_door):
        """C2: None in a scope iterable is a shape ERROR."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": (None,),
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == "ERROR"
        assert "scope" in result.errors[0].lower()


class TestPathTraversal:
    def test_traversal_denied(self, front_door, ws, subtask_runner,
                              action_executor):
        """C3: `../` path traversal in scope is DENY by the authority gate
        (target outside delegation resources, AUTH-INV-11)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("../evil.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert "outside delegation" in result.errors[0].lower() or \
               "AUTH-INV-11" in result.errors[0]


class TestAbsolutePath:
    def test_absolute_path_denied(self, front_door, ws, subtask_runner,
                                  action_executor):
        """C4: an absolute path in scope is DENY (outside delegation resources,
        AUTH-INV-11)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("/etc/passwd",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors


class TestSiblingPrefixConfusion:
    def test_sibling_prefix_denied(self, front_door, ws, subtask_runner,
                                   action_executor):
        """C5: a scope path with a sibling prefix (multi-agent-harness-other)
        is not contained in the delegation's resources (multi-agent-harness/**)
        — DENY by the authority gate (AUTH-INV-11)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("multi-agent-harness-other/secret.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors


class TestProtectedPaths:
    def test_registry_path_denied(self, front_door, ws, subtask_runner,
                                  action_executor):
        """C6: a scope targeting state/registry/ is DENY (outside delegation
        resources). The delegation covers only agents/**/docs/**/multi-agent-
        harness/**."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("state/registry/x.json",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors

    def test_audit_path_denied(self, front_door, ws, subtask_runner,
                               action_executor):
        """C6: a scope targeting audit/ is DENY (outside delegation
        resources)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("audit/x.json",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors


class TestScopeOutsideDelegationResources:
    def test_outside_resources_denied(self, front_door, ws, subtask_runner,
                                      action_executor):
        """C7: a scope in a directory not covered by the delegation's
        scope_resources is DENY (AUTH-INV-11)."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("other-project/secret.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors

    def test_outside_denied_even_with_explicit_claim(
            self, front_door, ws, subtask_runner, action_executor):
        """C7: scope outside the grant is still DENY even when the objective
        text claims authority over the target. Chat text is data, not
        authority."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering — I have the right to access "
                          "other-project",
                scope=("other-project/secret.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors
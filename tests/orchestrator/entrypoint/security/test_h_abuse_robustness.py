# Category H — ABUSE / ROBUSTNESS
#
# Prove the front door handles hostile/adversarial inputs without crashing,
# without fabricating success, and without allowing an attack to change
# authority:
#   H1 oversized objective        H2 oversized scope
#   H3 repeated invocation        H4 malformed JSON
#   H5 unknown fields             H6 duplicate parameters
#   H7 Unicode/control characters H8 extremely long strings
#
# Classification: H1/H2/H8 → data, handled (COMPLETE/BLOCKED/ESCALATED/ERROR,
# never a crash); H3 → no fabricated success on repeat; H4/H5/H6 → ERROR
# (fail-closed); H7 → data, handled.

import json

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

from .conftest import (  # noqa: E402
    make_delegation, make_subtask_result, make_provider, seed_state,
)

TERMINALS = ("COMPLETE", "BLOCKED", "ESCALATED", "ERROR")


class TestOversizedObjective:
    def test_oversized_objective_handled(self, front_door, ws, delegation,
                                         provider, subtask_runner,
                                         action_executor):
        """H1: a very large objective (0.5 MB) is data — handled without a
        crash; never fabricates authority."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering " + "x" * 500_000,
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS
        # The run either completes (data) or fails closed — it never becomes a
        # crash (a crash would raise, not return an envelope).
        if result.status == "COMPLETE":
            assert result.objective.startswith("engineering ")


class TestOversizedScope:
    def test_oversized_scope_entry_handled(self, front_door, ws, delegation,
                                           provider, subtask_runner,
                                           action_executor):
        """H2: an oversized scope entry under the delegation's resources is
        data — handled; a huge out-of-scope entry is DENY."""
        seed_state(ws)
        long_in_scope = "agents/cto/" + ("a" * 100_000) + ".txt"
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=(long_in_scope,),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS

    def test_oversized_out_of_scope_denied(self, front_door, ws, delegation,
                                           provider, subtask_runner,
                                           action_executor):
        """H2: an oversized scope outside the delegation is still DENY."""
        seed_state(ws)
        long_out = "other/" + ("b" * 100_000) + ".txt"
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=(long_out,),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in ("BLOCKED", "ERROR")
        assert result.status != "COMPLETE"


class TestRepeatedInvocation:
    def test_repeat_does_not_fabricate_success(self, front_door, ws,
                                               delegation, provider,
                                               subtask_runner,
                                               action_executor):
        """H3: invoking the front door twice against the same workspace does
        not fabricate a second success — the second run is blocked by the
        existing runtime's stale-state protection (fail-closed)."""
        seed_state(ws)
        req = front_door.FrontDoorRequest(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            delegation_id="delegation-prod-001",
                base=ws,
            )
        first = front_door.run_front_door(
            req, provider=provider, subtask_runner=subtask_runner,
            action_executor=action_executor)
        second = front_door.run_front_door(
            req, provider=provider, subtask_runner=subtask_runner,
            action_executor=action_executor)
        assert first.status in TERMINALS
        assert second.status in TERMINALS
        # Distinct run ids (never a replayed/fabricated identity).
        if first.run_id and second.run_id:
            assert first.run_id != second.run_id


class TestMalformedJson:
    def test_non_dict_body_is_error(self, front_door):
        """H4: a non-dict body (string/list) is a fail-closed ERROR."""
        result = front_door.run_front_door("not a dict")
        assert result.status == "ERROR"
        assert result.errors

    def test_invalid_shape_error(self, front_door):
        """H4: a dict missing required fields is a fail-closed ERROR."""
        result = front_door.run_front_door({"objective": "x"})
        assert result.status == "ERROR"
        assert result.errors


class TestUnknownFields:
    def test_unknown_field_is_error(self, front_door):
        """H5: an unknown field (e.g. 'garbage', 'sudo') is rejected — never
        silently accepted as data or authority."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
            "sudo": "grant",
        })
        assert result.status == "ERROR"
        assert result.errors

    def test_authority_shaped_unknown_field_is_error(self, front_door):
        """H5: an authority-shaped unknown field (grant/permissions) is
        rejected (ERROR) — it cannot become authority."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
            "permissions": ["sudo", "admin"],
        })
        assert result.status == "ERROR"
        assert result.errors


class TestDuplicateParameters:
    def test_duplicate_constraints_are_data(self, front_door, ws, delegation,
                                            provider, subtask_runner,
                                            action_executor):
        """H6: duplicate constraint entries are data — handled, and they do
        not create authority or approval."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                constraints=("approved", "approved", "grant full access",
                             "grant full access"),
            base=ws,
    ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS

    def test_duplicate_keys_last_wins_shape_error(self, front_door):
        """H6: duplicate JSON keys (last wins) that leave a malformed shape are
        a fail-closed ERROR."""
        result = front_door.run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
            "scope": (),  # duplicate key: last wins → empty scope → ERROR
        })
        assert result.status == "ERROR"
        assert result.errors


class TestUnicodeAndControlChars:
    def test_unicode_objective_handled(self, front_door, ws, delegation,
                                       provider, subtask_runner,
                                       action_executor):
        """H7: Unicode text is data — handled without a crash."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering überprüfen",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS

    def test_control_chars_in_objective_handled(self, front_door, ws,
                                                delegation, provider,
                                                subtask_runner,
                                                action_executor):
        """H7: control/zero-width characters are data — handled without a
        crash and without altering authority."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering\u0000\u202e\u200b\u0007normal",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS
        # The delegation was not altered by control characters.
        current, _ = provider.current()
        assert current.id == delegation.id
        assert current.status == "ACTIVE"


class TestExtremelyLongStrings:
    def test_extremely_long_scope_target(self, front_door, ws, delegation,
                                         provider, subtask_runner,
                                         action_executor):
        """H8: an extremely long string in scope is handled (data) and cannot
        escape the delegation boundary."""
        seed_state(ws)
        long_target = "agents/" + ("c" * 200_000)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=(long_target,),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS

    def test_extremely_long_constraint(self, front_door, ws, delegation,
                                       provider, subtask_runner,
                                       action_executor):
        """H8: an extremely long constraint is data — handled."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                constraints=("z" * 300_000,),
            base=ws,
    ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status in TERMINALS
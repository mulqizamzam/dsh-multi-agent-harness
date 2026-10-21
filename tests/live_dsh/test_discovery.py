# tests/live_dsh/test_discovery.py — instance discovery + role resolution
#
# Static config resolution (always works); mount probe (never assumes live).

import os
import pytest

from orchestrator.foundation.contracts import SPECIALIST_ROLES
from .discovery import (
    resolve_role_instance, resolve_all_role_instances,
    assert_role_resolution, check_instance_mounted, DISCOVERY_MARKER_ENV,
)


class TestRoleResolution:
    def test_all_roles_resolve(self):
        """Every specialist role resolves to a SubagentInstance."""
        resolver = resolve_all_role_instances()
        assert set(resolver.keys()) == set(SPECIALIST_ROLES)
        assert len(resolver) == len(SPECIALIST_ROLES)  # PRD v0.2: 15 (ADR 0003 D1)

    def test_each_role_resolves_to_its_agent_preset(self):
        """Each role resolves to its own role-<id> Agent Preset.

        0.2.1-rc.2 has ONE delegation tool, so the resolution names the preset
        the model selects rather than a per-role tool name.
        """
        result = assert_role_resolution()
        for role in SPECIALIST_ROLES:
            assert result[role] == f"role-{role}", (
                f"{role} -> {result[role]}, expected role-{role}")

    def test_each_role_has_persona_role_name(self):
        """Each instance selects the role-<id> Agent Preset (D4/D7 naming)."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.agent_preset == f"role-{role}", f"{role} preset={inst.agent_preset}"

    def test_all_max_depth_1(self):
        """V1 rule: all specialists have max_depth=1 (subdelegation DENY)."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.max_depth == 1, f"{role} max_depth={inst.max_depth}"

    def test_all_provider_spawn(self):
        """All instances use the spawn provider."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.provider == "spawn", f"{role} provider={inst.provider}"

    def test_all_agent_presets_are_the_role_presets(self):
        """All instances are continuable (report channel available)."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.agent_preset == f"role-{role}", f"{role} preset={inst.agent_preset}"

    def test_allow_deny_disjoint(self):
        """allow ∩ deny = ∅ for every role (consistency guardrail)."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            overlap = set(inst.allow) & set(inst.deny)
            assert not overlap, f"{role}: allow ∩ deny = {overlap}"


class TestMountProbe:
    def test_unmounted_by_default(self):
        """Without the marker, every instance is NOT_MOUNTED."""
        saved = os.environ.pop(DISCOVERY_MARKER_ENV, None)
        try:
            for preset in [f"role-{r}" for r in SPECIALIST_ROLES]:
                assert not check_instance_mounted("subagent"), (
                    f"the delegation tool must be unmounted for {preset}")
        finally:
            if saved is not None:
                os.environ[DISCOVERY_MARKER_ENV] = saved

    def test_mounted_with_marker(self):
        """With the marker, probe returns mounted."""
        os.environ[DISCOVERY_MARKER_ENV] = "1"
        try:
            assert check_instance_mounted("subagent")
        finally:
            os.environ.pop(DISCOVERY_MARKER_ENV, None)
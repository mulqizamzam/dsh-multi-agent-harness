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
    def test_all_7_roles_resolve(self):
        """Every specialist role resolves to a SubagentInstance."""
        resolver = resolve_all_role_instances()
        assert set(resolver.keys()) == set(SPECIALIST_ROLES)
        assert len(resolver) == 7

    def test_each_role_has_correct_tool_name(self):
        """Each role resolves to the expected D4/D7 tool_name."""
        expected = {
            "zeko": "subagent_zeko",
            "cto": "subagent_cto",
            "cfo": "subagent_cfo",
            "kai": "subagent_kai",
            "somad": "subagent_somad",
            "badsector": "subagent_badsector",
            "nova": "subagent_nova",
        }
        result = assert_role_resolution()
        for role, tool in expected.items():
            assert result[role] == tool, f"{role} -> {result[role]}, expected {tool}"

    def test_each_role_has_persona_role_name(self):
        """Each instance's persona matches the D4/D7 naming convention role-<id>."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.persona == f"role-{role}", f"{role} persona={inst.persona}"

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

    def test_all_background_mode_continuable(self):
        """All instances are continuable (report channel available)."""
        instances = resolve_all_role_instances()
        for role, inst in instances.items():
            assert inst.background_mode == "continuable", f"{role} bg={inst.background_mode}"

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
            for tool in [f"subagent_{r}" for r in SPECIALIST_ROLES]:
                assert not check_instance_mounted(tool), f"{tool} should be unmounted"
        finally:
            if saved is not None:
                os.environ[DISCOVERY_MARKER_ENV] = saved

    def test_mounted_with_marker(self):
        """With the marker, probe returns mounted."""
        os.environ[DISCOVERY_MARKER_ENV] = "1"
        try:
            assert check_instance_mounted("subagent_cto")
        finally:
            os.environ.pop(DISCOVERY_MARKER_ENV, None)
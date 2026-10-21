# tests/orchestrator/dsh/test_resolver.py
#
# Role resolution: the adapter must resolve every specialist role id to its
# approved D4/D7 subagent instance (tool-subagent toolName subagent_<id>,
# agent_preset role-<id>, provider spawn, maxDepth 1).
# The orchestrator is NOT a delegation target.  Unknown roles fail closed.

import pytest

from orchestrator.dsh import RoleResolver, SubagentInstance
from orchestrator.dsh.exceptions import RoleResolutionError
from orchestrator.foundation.contracts import SPECIALIST_ROLES

# The specialist roster derives from the contract (PRD v0.2: 15 roles;
# ADR 0003 D1). Peer topology — orchestrator excluded.
ALL_SPECIALISTS = SPECIALIST_ROLES


class TestRoleResolution:
    def test_resolves_all_specialists(self, resolver):
        """Every specialist role resolves to a SubagentInstance."""
        for role in ALL_SPECIALISTS:
            inst = resolver.resolve(role)
            assert isinstance(inst, SubagentInstance)
            assert inst.role == role

    def test_all_roles_map_to_approved_tool_names(self, resolver):
        """role → the ONE delegation tool (0.2.1-rc.2 has one per provider)."""
        tool_names = resolver.tool_names()
        assert set(tool_names.keys()) == set(ALL_SPECIALISTS)
        for role in ALL_SPECIALISTS:
            assert tool_names[role] == "subagent"

    def test_agent_preset_matches_approved_naming(self, resolver):
        """Each instance selects its own role preset (role-<id>)."""
        for role in ALL_SPECIALISTS:
            assert resolver.resolve(role).agent_preset == f"role-{role}"

    def test_all_instances_spawn_maxdepth1(self, resolver):
        """provider spawn, maxDepth 1 (V1 subdelegation DENY BY DEFAULT)."""
        for role in ALL_SPECIALISTS:
            inst = resolver.resolve(role)
            assert inst.provider == "spawn"
            assert inst.max_depth == 1

    def test_no_delegation_tools_in_any_allow(self, resolver):
        """Subdelegation DENY BY DEFAULT: no specialist allow set contains a
        delegation/workflow tool."""
        delegation_tools = {
            "subagent", "subagent_fork", "send_message", "interrupt_agent",
            "list_agents", "workflow", "ralph", "ask_user_question",
            "create_goal", "get_goal", "update_goal",
        }
        for role in ALL_SPECIALISTS:
            allow = set(resolver.resolve(role).allow)
            overlap = allow & delegation_tools
            assert not overlap, f"{role} allow contains delegation tools {overlap}"

    def test_allow_deny_disjoint(self, resolver):
        """allow ∩ deny == ∅ for every role."""
        for role in ALL_SPECIALISTS:
            inst = resolver.resolve(role)
            assert not (set(inst.allow) & set(inst.deny))

    def test_orchestrator_is_not_a_delegation_target(self, resolver):
        """The orchestrator is a coordination root, never a subagent target."""
        with pytest.raises(RoleResolutionError):
            resolver.resolve("orchestrator")

    def test_unknown_role_fails_closed(self, resolver):
        with pytest.raises(RoleResolutionError):
            resolver.resolve("doesnotexist")

    def test_roles_set_is_exactly_specialists(self, resolver):
        assert set(resolver.roles()) == set(SPECIALIST_ROLES)

    def test_resolution_preserves_approved_tool_surfaces(self, resolver):
        """CTO retains bash; CFO/Kai/BadSector deny edit/write/bash; Nova
        denies bash; per the approved tool surface."""
        cto = resolver.resolve("cto")
        assert "bash" in cto.allow
        assert "edit" in cto.allow and "write" in cto.allow

        cfo = resolver.resolve("cfo")
        assert "bash" not in cfo.allow
        assert "edit" not in cfo.allow and "write" not in cfo.allow

        kai = resolver.resolve("kai")
        assert "write" not in kai.allow

        badsector = resolver.resolve("badsector")
        assert "write" not in badsector.allow
        assert "web_search" not in badsector.allow

        nova = resolver.resolve("nova")
        assert "bash" not in nova.allow

    def test_web_fetch_never_enabled(self, resolver):
        """web_fetch is NOT enabled for any role (SSRF review required)."""
        for role in ALL_SPECIALISTS:
            assert "web_fetch" not in resolver.resolve(role).allow


class TestSubagentInstanceInvariants:
    def test_instance_rejects_bad_naming(self):
        with pytest.raises(RoleResolutionError):
            SubagentInstance(role="cto", tool_name="subagent_other",
                             agent_preset="role-cto")

    def test_instance_rejects_maxdepth_gt_1(self):
        with pytest.raises(RoleResolutionError):
            SubagentInstance(role="cto", tool_name="subagent",
                             agent_preset="role-cto", max_depth=2)

    def test_instance_rejects_provider_not_spawn(self):
        with pytest.raises(RoleResolutionError):
            SubagentInstance(role="cto", tool_name="subagent",
                             agent_preset="role-cto", provider="acp")

    def test_instance_rejects_allow_deny_overlap(self):
        with pytest.raises(RoleResolutionError):
            SubagentInstance(role="cto", tool_name="subagent",
                             agent_preset="role-cto",
                             allow=("read", "bash"), deny=("bash",))

    def test_instance_rejects_delegation_tool_in_allow(self):
        with pytest.raises(RoleResolutionError):
            SubagentInstance(role="cto", tool_name="subagent",
                             agent_preset="role-cto",
                             allow=("read", "subagent"), deny=())

    def test_tool_surface_shape(self, resolver):
        inst = resolver.resolve("cto")
        ts = inst.tool_surface()
        assert set(ts["allow"]) == set(inst.allow)
        assert set(ts["deny"]) == set(inst.deny)
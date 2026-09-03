# tests/live_dsh/test_role_adapters.py — per-role adapters for the 7 specialists
#
# Each role (CTO, CFO, Kai, Somad, BadSector, Nova, Zeko) must have a working
# adapter: correct tool_name / persona / allow-deny from the approved D4/D7
# composition, and the ability to build an authorized context + invocation.

from .conftest import make_task, make_delegation


class TestAllRoleAdapters:
    def test_role_adapter_tool_names(self, role_adapter):
        """Each parametrized role resolves to the expected subagent_<id>."""
        adapter, expected_tool = role_adapter
        assert adapter.tool_name == expected_tool
        assert adapter.persona == f"role-{adapter.role}"

    def test_adapter_builds_context_and_invocation(self, role_adapter):
        """Each role adapter builds an authorized context + DSH invocation."""
        adapter, _ = role_adapter
        task = make_task(role=adapter.role, task_id=f"live-{adapter.role}")
        delegation = make_delegation(task=task.task_id)
        ctx = adapter.build_context(task, delegation)
        assert ctx["assigned_role"] == adapter.role
        inv = adapter.build_invocation(task, delegation)
        assert inv.run_in_background is False
        assert inv.output_schema["properties"]["assigned_role"]["enum"]

    def test_adapter_mounted_flag_is_false_without_marker(self, role_adapter):
        """Without the D4/D7 marker, every adapter reports not mounted."""
        adapter, _ = role_adapter
        assert adapter.mounted() is False

    def test_read_only_roles_deny_write(self):
        """CFO/Kai/BadSector deny write/edit/bash in their approved filters."""
        from .adapters import ROLE_ADAPTERS
        for role in ("cfo", "kai", "badsector"):
            adapter = ROLE_ADAPTERS[role]
            for tool in ("write", "edit", "bash"):
                assert tool in adapter.deny, f"{role} must deny {tool}"
                assert tool not in adapter.allow, f"{role} must not allow {tool}"

    def test_write_capable_roles_allow_write(self):
        """Post-O5: only CTO/Zeko allow workspace write (ops/engineering)."""
        from .adapters import ROLE_ADAPTERS
        for role in ("cto", "zeko"):
            assert "write" in ROLE_ADAPTERS[role].allow, f"{role} should allow write"

    def test_badsector_is_review_only(self):
        """BadSector denies web_search and all delegation tools."""
        from .adapters import ROLE_ADAPTERS
        badsector = ROLE_ADAPTERS["badsector"]
        for tool in ("bash", "edit", "write", "web_search",
                     "subagent", "workflow", "send_message"):
            assert tool in badsector.deny, f"badsector must deny {tool}"

    def test_no_delegation_tool_in_any_allow(self):
        """Subdelegation DENY BY DEFAULT: no specialist allows delegation tools."""
        from .adapters import ROLE_ADAPTERS
        delegation_tools = {"subagent", "subagent_fork", "send_message",
                            "interrupt_agent", "list_agents", "workflow", "ralph"}
        for role, adapter in ROLE_ADAPTERS.items():
            overlap = delegation_tools & set(adapter.allow)
            assert not overlap, f"{role} allows delegation tools {overlap}"

    def test_all_seven_adapters_present(self):
        from .adapters import ROLE_ADAPTERS
        assert set(ROLE_ADAPTERS.keys()) == {
            "zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"}
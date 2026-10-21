# tests/live_dsh/adapters.py — per-role adapters for the REAL bridge (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# One adapter per specialist role (CTO, CFO, Kai, Somad, BadSector, Nova, Zeko).
# An adapter binds the D4/D7-approved SubagentInstance to:
#   - the role's expected tool_name / agent_preset / tool surface (from config)
#   - the authorized task-context builder (THREAT-020: no authority in messages)
#   - the DSH invocation shape the real bridge sends
#   - the structured TaskResult schema the child must satisfy
#
# The adapters are CONFIG DRIVEN: they read the approved role-preset mapping
# (config/role-preset-mapping.yaml + config/tool-subagent-instances.yaml) so
# they never drift from the D4/D7 composition. No adapter mounts or executes
# anything.

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field as dc_field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import (
    SPECIALIST_ROLES, Task, Delegation,
)
from orchestrator.dsh import (
    RoleResolver, SubagentInstance, build_task_context,
)
from orchestrator.dsh.exceptions import RoleResolutionError

from .contract import BuildInvocation, DSHInvocation
from .discovery import check_instance_mounted


@dataclass(frozen=True)
class RoleAdapter:
    """One specialist role's REAL-bridge adapter.

    role:            the specialist role id
    instance:        the approved SubagentInstance
    tool_name:       subagent (the ONE delegation tool to call)
    agent_preset:    role-<id> (the preset the model selects)
    allow/deny:      the approved tool surface (from config)
    mounted:         whether the delegation tool is currently mounted (probe)
    """
    role: str
    instance: SubagentInstance

    @property
    def tool_name(self) -> str:
        return self.instance.tool_name

    @property
    def agent_preset(self) -> str:
        return self.instance.agent_preset

    @property
    def allow(self) -> tuple:
        return self.instance.allow

    @property
    def deny(self) -> tuple:
        return self.instance.deny

    @property
    def provider(self) -> str:
        return self.instance.provider

    @property
    def max_depth(self) -> int:
        return self.instance.max_depth

    def mounted(self) -> bool:
        return check_instance_mounted(self.tool_name)

    # -- context + invocation -------------------------------------------------
    def build_context(self, task: Task, delegation: Delegation,
                      extra: dict | None = None) -> dict:
        """The AUTHORIZED task context the bridge passes to the child."""
        return build_task_context(task=task, delegation=delegation, extra=extra)

    def build_invocation(self, task: Task, delegation: Delegation,
                         output_schema: dict | None = None) -> DSHInvocation:
        """The DSH invocation the real bridge sends for this role."""
        return BuildInvocation.build(task, delegation,
                                     output_schema=output_schema)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "tool_name": self.tool_name,
            "agent_preset": self.agent_preset,
            "provider": self.provider,
            "max_depth": self.max_depth,
            "allow": list(self.allow),
            "deny": list(self.deny),
            "mounted": self.mounted(),
        }


def build_role_adapter(role: str) -> RoleAdapter:
    """Build the adapter for one role from the approved D4/D7 composition."""
    if role not in SPECIALIST_ROLES:
        raise RoleResolutionError(
            f"role {role!r} is not a specialist role "
            f"(must be one of {SPECIALIST_ROLES})")
    resolver = RoleResolver()
    instance = resolver.resolve(role)
    return RoleAdapter(role=role, instance=instance)


def build_all_role_adapters() -> dict[str, RoleAdapter]:
    """Build adapters for all 15 specialist roles (PRD v0.2)."""
    return {role: build_role_adapter(role) for role in SPECIALIST_ROLES}


ROLE_ADAPTERS: dict[str, RoleAdapter] = build_all_role_adapters()


__all__ = ["RoleAdapter", "build_role_adapter", "build_all_role_adapters",
           "ROLE_ADAPTERS"]
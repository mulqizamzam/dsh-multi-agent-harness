# tests/live_dsh/discovery.py — DSH instance discovery + role resolution (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Instance discovery determines whether the D4/D7 approved `subagent_<id>` tool
# instances are ACTUALLY MOUNTED in the live DSH session. Since the harness
# NEVER executes live scenarios, this module provides:
#   - static role → instance resolution (always works — reads approved config)
#   - a probe that checks for a mount marker before assuming a live bridge
#   - an explicit NOT_MOUNTED state the harness reports as BLOCKED
#
# The marker is set by the orchestrator session when the D4/D7 composition
# exception is approved and mounted. Until then, every REAL-backend path reports
# NOT_MOUNTED and refuses to dispatch.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.dsh import RoleResolver, SubagentInstance

# Environment variable the orchestrator session sets when the D4/D7 composition
# is mounted and the `subagent_<id>` tools are available for delegation.
DISCOVERY_MARKER_ENV = "DSH_LIVE_BRIDGE_ACTIVE"


def resolve_role_instance(role: str) -> SubagentInstance:
    """Resolve a role to its approved D4/D7 SubagentInstance.

    This reads the approved config files (config/role-preset-mapping.yaml +
    config/tool-subagent-instances.yaml) and returns the immutable instance
    record. It NEVER checks the live session — it is a static config resolution.

    Raises RoleResolutionError for unknown roles or composition drift.
    """
    resolver = RoleResolver()
    return resolver.resolve(role)


def resolve_all_role_instances() -> dict[str, SubagentInstance]:
    """Resolve all 15 specialist roles to their approved instances."""
    resolver = RoleResolver()
    return resolver.all()


def assert_role_resolution() -> dict[str, str]:
    """Assert that every defined specialist role resolves to an instance.

    Returns {role: tool_name} for all 15 roles. Raises on any failure.
    """
    from orchestrator.foundation.contracts import SPECIALIST_ROLES
    resolver = RoleResolver()
    result = {}
    for role in SPECIALIST_ROLES:
        inst = resolver.resolve(role)
        result[role] = inst.tool_name
    return result


def check_instance_mounted(tool_name: str) -> bool:
    """Probe whether one `subagent_<id>` instance is mounted.

    Without a live session probe, this returns True ONLY when the
    DISCOVERY_MARKER_ENV environment variable is set — the orchestrator
    session sets it when the D4/D7 composition is active.

    Until the composition exception is approved and mounted, this returns
    False (NOT_MOUNTED). The harness NEVER assumes a live bridge exists.
    """
    return os.environ.get(DISCOVERY_MARKER_ENV, "").strip().lower() in (
        "1", "true", "yes")


def probe_all_instances_mounted() -> dict[str, bool]:
    """Probe all 15 role instances for mount status.

    Returns {tool_name: mounted} for each D4/D7 instance.
    """
    from orchestrator.foundation.contracts import SPECIALIST_ROLES
    resolver = RoleResolver()
    result = {}
    for role in SPECIALIST_ROLES:
        inst = resolver.resolve(role)
        result[inst.tool_name] = check_instance_mounted(inst.tool_name)
    return result


__all__ = [
    "DISCOVERY_MARKER_ENV", "resolve_role_instance", "resolve_all_role_instances",
    "assert_role_resolution", "check_instance_mounted", "probe_all_instances_mounted",
]
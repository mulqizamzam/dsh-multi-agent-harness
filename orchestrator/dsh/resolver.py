# orchestrator.dsh.resolver — Role → DSH subagent instance resolution
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# Resolves a role id (e.g. "cto") to its approved delegation configuration
# declared in `config/role-preset-mapping.yaml` (+ `config/tool-subagent-instances.yaml`
# as cross-check).  The resolver is a READ-ONLY consumer of the approved
# mapping; it never modifies DSH profile, preset, or core.
#
# MODEL (DeepSeek Harness 0.2.1-rc.2): the host removed the per-instance
# `persona` and `toolFilter` config keys from `@deepseek-ai/dsh-tool-subagent`
# (it now throws on them) and removed `backgroundMode`.  There is ONE
# delegation tool per provider, so a role is selected by the model-facing
# `agent_preset` argument naming the role's Agent Preset, and the role's tool
# surface is the set of tool PLUGINS that preset mounts.
#
# The mapping is the single source of truth (Phase-1A finalized, D4/D7
# approved).  If the YAML files are absent or the mapping drifts from the
# approved composition, the resolver fails closed (RoleResolutionError).

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field as dc_field

# ---------------------------------------------------------------------------
# Project-root bootstrap (mirrors orchestrator/foundation/gates.py pattern)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import SPECIALIST_ROLES  # noqa: E402
from .exceptions import RoleResolutionError  # noqa: E402

# ---------------------------------------------------------------------------
# Constants — the D4/D7 approved file paths (relative to project root)
# ---------------------------------------------------------------------------
_MAPPING_REL = ("config", "role-preset-mapping.yaml")
_INSTANCES_REL = ("config", "tool-subagent-instances.yaml")

# Delegation tools a specialist MUST NEVER hold (subdelegation DENY BY DEFAULT)
_DELEGATION_TOOLS = frozenset({
    "subagent", "subagent_fork", "send_message", "interrupt_agent",
    "list_agents", "workflow", "ralph",
})

# ---------------------------------------------------------------------------
# SubagentInstance — the approved configuration for one per-role
# tool-subagent instance (D4/D7 composition)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SubagentInstance:
    """Immutable record of one role's approved delegation configuration.

    Fields mirror the 0.2.1-rc.2 model: the ONE `subagent` delegation tool
    (tool_name, provider, max_depth) and the Agent Preset the model selects
    through the `agent_preset` argument (agent_preset).  The role's own tool
    surface is the set of tool PLUGINS its preset mounts; `allow`/`deny`
    record that surface for the control plane.
    """

    role: str
    tool_name: str            # subagent — the one delegation tool
    agent_preset: str         # role-<id> — the preset the model selects
    provider: str = "spawn"
    max_depth: int = 1
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def tool_surface(self) -> dict:
        """The role's declared tool surface (allow/deny)."""
        return {"allow": list(self.allow), "deny": list(self.deny)}

    def __post_init__(self):
        if not self.role or not self.tool_name or not self.agent_preset:
            raise RoleResolutionError(
                "SubagentInstance: role/tool_name/agent_preset required")
        if self.max_depth != 1:
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: max_depth must be 1 "
                f"(V1 subdelegation DENY BY DEFAULT), got {self.max_depth}")
        if self.provider != "spawn":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: provider must be "
                f"'spawn', got {self.provider!r}")
        if self.tool_name != "subagent":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: expected tool_name "
                f"'subagent' — 0.2.1-rc.2 has one delegation tool per provider "
                f"and selects the role through the agent_preset argument")
        if self.agent_preset != f"role-{self.role}":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: expected agent_preset "
                f"'role-{self.role}', got {self.agent_preset!r}")
        # allow ∩ deny must be empty (consistency guardrail)
        overlap = set(self.allow) & set(self.deny)
        if overlap:
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: allow ∩ deny = {overlap}")
        # no delegation tool in allow (subdelegation DENY BY DEFAULT)
        delegated = _DELEGATION_TOOLS & set(self.allow)
        if delegated:
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: delegation tools {delegated} "
                f"in allow set (subdelegation DENY BY DEFAULT, V1)")


# ---------------------------------------------------------------------------
# RoleResolver
# ---------------------------------------------------------------------------
class RoleResolver:
    """Resolve a role id (e.g. ``"cto"``) to its approved D4/D7
    ``SubagentInstance`` by reading the role-preset mapping.

    Usage::

        resolver = RoleResolver()
        instance = resolver.resolve("cto")   # → SubagentInstance

    The resolver loads the YAML config files from the project's ``config/``
    directory.  A caller may supply ``mapping`` / ``instances`` as a pre-loaded
    dict to skip file I/O (useful in tests and when the mapping is injected
    from a different source).
    """

    def __init__(self, *, mapping: dict | None = None,
                 instances: dict | None = None,
                 project_root: str | None = None):
        self._project_root = os.path.abspath(
            project_root or _PROJECT_ROOT)
        mapping_data = mapping if mapping is not None else \
            self._load_yaml(*_MAPPING_REL)
        instances_data = instances if instances is not None else \
            self._load_yaml(*_INSTANCES_REL, optional=True)
        self._by_role: dict[str, SubagentInstance] = \
            self._build(mapping_data or {}, instances_data or {})

    # -- public API ----------------------------------------------------------

    def resolve(self, role: str) -> SubagentInstance:
        """Resolve a specialist role id to its approved subagent instance.

        Raises RoleResolutionError for orchestrator (not a delegation target),
        for an unknown role, or when the mapping is inconsistent.
        """
        if role == "orchestrator":
            raise RoleResolutionError(
                "orchestrator is not a subagent delegation target; "
                "it is the coordination root session (ADR Decision 3)")
        if role not in SPECIALIST_ROLES:
            raise RoleResolutionError(
                f"unknown role {role!r}; must be one of {SPECIALIST_ROLES}")
        inst = self._by_role.get(role)
        if inst is None:
            raise RoleResolutionError(
                f"role {role!r} has no SubagentInstance in the mapping; "
                "D4/D7 composition may be incomplete")
        return inst

    def all(self) -> dict[str, SubagentInstance]:
        """Return a copy of the {role → SubagentInstance} map."""
        return dict(self._by_role)

    def roles(self) -> tuple[str, ...]:
        """The specialist roles that have a resolved instance."""
        return tuple(self._by_role.keys())

    def tool_names(self) -> dict[str, str]:
        """{role → tool_name} for every resolved instance.

        Since 0.2.1-rc.2 every role is reached through the same `subagent`
        tool; `agent_presets()` names the preset each role selects.
        """
        return {r: inst.tool_name for r, inst in self._by_role.items()}

    def agent_presets(self) -> dict[str, str]:
        """{role → agent_preset} for every resolved instance."""
        return {r: inst.agent_preset for r, inst in self._by_role.items()}

    # -- loader --------------------------------------------------------------

    def _load_yaml(self, *parts: str, optional: bool = False) -> dict | None:
        """Load a YAML file from the project root + *parts."""
        path = os.path.join(self._project_root, *parts)
        if not os.path.isfile(path):
            if optional:
                return None
            raise RoleResolutionError(
                f"mapping file not found: {path} (D4/D7 composition reference)")
        try:
            import yaml
        except ImportError:
            raise RoleResolutionError(
                "PyYAML is required to load the role-preset mapping; "
                "install it, or supply a pre-loaded `mapping` dict") from None
        with open(path, "r") as f:
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise RoleResolutionError(
                    f"malformed YAML in {path}: {e}") from e

    # -- builder -------------------------------------------------------------

    def _build(self, mapping: dict, instances: dict) -> dict[str, SubagentInstance]:
        """Build the {role → SubagentInstance} map from the YAML mapping dict.

        Cross-checks against the tool-subagent-instances draft when available.
        """
        raw_roles: list[dict] = mapping.get("roles", [])
        if not raw_roles:
            raise RoleResolutionError(
                "role-preset mapping contains no `roles` list; "
                "D4/D7 composition is empty")

        # Index by role id
        by_role: dict[str, dict] = {}
        for entry in raw_roles:
            rid = entry.get("id")
            if rid:
                by_role[rid] = entry

        # Build instances for every specialist role
        built: dict[str, SubagentInstance] = {}
        for role in SPECIALIST_ROLES:
            entry = by_role.get(role)
            if entry is None:
                raise RoleResolutionError(
                    f"role {role!r} missing from role-preset mapping "
                    "(D4/D7 composition incomplete)")
            ti = entry.get("tool_instance", {})
            ts = entry.get("tool_surface", {})
            inst = SubagentInstance(
                role=role,
                tool_name=ti.get("tool_name", "subagent"),
                agent_preset=ti.get("agent_preset", f"role-{role}"),
                provider=ti.get("provider", "spawn"),
                max_depth=ti.get("max_depth", 1),
                allow=tuple(ts.get("allow", [])),
                deny=tuple(ts.get("deny", [])),
            )
            built[role] = inst

        # Cross-check against tool-subagent-instances.yaml if available. The
        # file records the ONE delegation row (whose allowedAgentPresets must
        # cover every role) and one preset declaration per role.
        if instances:
            insert = instances.get("insert_draft", [])
            if len(insert) != 1:
                raise RoleResolutionError(
                    f"cross-check: expected exactly one delegation row, got "
                    f"{len(insert)}")
            cfg = insert[0].get("config", {})
            for removed in ("persona", "toolFilter", "backgroundMode",
                            "enableRunInBackground"):
                if removed in cfg:
                    raise RoleResolutionError(
                        f"cross-check: the delegation row still declares "
                        f"{removed!r}; DSH 0.2.1-rc.2 removed that config key")
            if cfg.get("toolName") != "subagent":
                raise RoleResolutionError(
                    f"cross-check: delegation row toolName mismatch "
                    f"({cfg.get('toolName')!r} vs 'subagent')")
            allowed = set(cfg.get("allowedAgentPresets", []))
            missing = {inst.agent_preset for inst in built.values()} - allowed
            if missing:
                raise RoleResolutionError(
                    f"cross-check: the delegation row's allowedAgentPresets "
                    f"omits {sorted(missing)}")
            declared = {d.get("id"): d for d in instances.get("agent_presets", [])}
            for role, inst in built.items():
                dec = declared.get(inst.agent_preset)
                if dec is None:
                    raise RoleResolutionError(
                        f"cross-check: no preset declaration for "
                        f"{inst.agent_preset!r}")
                dec_ts = dec.get("tool_surface", {})
                if set(dec_ts.get("allow", [])) != set(inst.allow):
                    raise RoleResolutionError(
                        f"cross-check: {inst.agent_preset} allow set drift "
                        f"(mapping={set(inst.allow)} vs "
                        f"instances={set(dec_ts.get('allow', []))})")
                if set(dec_ts.get("deny", [])) != set(inst.deny):
                    raise RoleResolutionError(
                        f"cross-check: {inst.agent_preset} deny set drift "
                        f"(mapping={set(inst.deny)} vs "
                        f"instances={set(dec_ts.get('deny', []))})")

        return built
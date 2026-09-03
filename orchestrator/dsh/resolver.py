# orchestrator.dsh.resolver — Role → DSH subagent instance resolution
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# Resolves a role id (e.g. "cto") to the approved D4/D7
# `tool-subagent-<id>` instance configuration declared in
# `config/role-preset-mapping.yaml` (+ `config/tool-subagent-instances.yaml` as
# cross-check).  The resolver is a READ-ONLY consumer of the approved mapping;
# it never modifies DSH profile, preset, or core.
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
    """Immutable record of one approved D4/D7 subagent instance configuration.

    Fields mirror the `tool-subagent` config schema (provider, toolName,
    persona, toolFilter, backgroundMode, maxDepth) and the
    `role-preset-mapping.yaml` roles[].tool_instance + tool_filter sections.
    """
    role: str
    tool_name: str            # subagent_<id>
    persona: str              # role-<id>
    provider: str = "spawn"
    background_mode: str = "continuable"
    max_depth: int = 1
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    def tool_filter(self) -> dict:
        """The toolFilter shape this instance would carry at mount."""
        return {"allow": list(self.allow), "deny": list(self.deny)}

    def __post_init__(self):
        if not self.role or not self.tool_name or not self.persona:
            raise RoleResolutionError("SubagentInstance: role/tool_name/persona required")
        if self.max_depth != 1:
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: max_depth must be 1 "
                f"(V1 subdelegation DENY BY DEFAULT), got {self.max_depth}")
        if self.provider != "spawn":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: provider must be "
                f"'spawn', got {self.provider!r}")
        if self.background_mode != "continuable":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: background_mode must be "
                f"'continuable', got {self.background_mode!r}")
        if self.tool_name != f"subagent_{self.role}":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: expected tool_name "
                f"'subagent_{self.role}' (D4/D7 approved naming)")
        if self.persona != f"role-{self.role}":
            raise RoleResolutionError(
                f"SubagentInstance {self.tool_name}: expected persona "
                f"'role-{self.role}' (D4/D7 approved naming)")
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
        """{role → tool_name} for every resolved instance."""
        return {r: inst.tool_name for r, inst in self._by_role.items()}

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
            tf = entry.get("tool_filter", {})
            inst = SubagentInstance(
                role=role,
                tool_name=ti.get("tool_name", f"subagent_{role}"),
                persona=ti.get("persona", f"role-{role}"),
                provider=ti.get("provider", "spawn"),
                background_mode=ti.get("background_mode", "continuable"),
                max_depth=ti.get("max_depth", 1),
                allow=tuple(tf.get("allow", [])),
                deny=tuple(tf.get("deny", [])),
            )
            built[role] = inst

        # Cross-check against tool-subagent-instances.yaml if available
        if instances:
            cross = instances.get("insert_draft", [])
            for entry in cross:
                eid: str = entry.get("id", "")
                rid = eid.removeprefix("tool-subagent-")
                if rid in built:
                    cfg = entry.get("config", {})
                    inst = built[rid]
                    tf = cfg.get("toolFilter", {})
                    cfg_allow = set(tf.get("allow", []))
                    cfg_deny = set(tf.get("deny", []))
                    if cfg.get("toolName") != inst.tool_name:
                        raise RoleResolutionError(
                            f"cross-check: {eid} toolName mismatch "
                            f"({cfg.get('toolName')} vs {inst.tool_name})")
                    if cfg_allow != set(inst.allow):
                        raise RoleResolutionError(
                            f"cross-check: {eid} allow set drift "
                            f"(mapping={set(inst.allow)} vs instances={cfg_allow})")
                    if cfg_deny != set(inst.deny):
                        raise RoleResolutionError(
                            f"cross-check: {eid} deny set drift "
                            f"(mapping={set(inst.deny)} vs instances={cfg_deny})")

        return built
# tests/d4d7_composition.py — the D4/D7 composition source of truth (read-only)
#
# ARCHITECTURE (cutover 2026-10-10/11 — commits 84e630f and 0477eff):
#
#   1. The 16 agent presets are registered DIRECTLY from this repo by the
#      `dsh-multi-agent-harness` plugin (index.js): every directory under
#      `agents/<id>/` registers as `role-<id>`, and `orchestrator/` registers
#      as `orchestrator`. The `$DSH_HOME/.agent-presets/` deployment copy is
#      RETIRED — there is nothing to sync and nothing deployed.
#   2. The delegation rows live in the orchestrator preset composition
#      (`orchestrator/agent.cordis.yml`), so that only orchestrator-bound
#      sessions gain the delegation tool. Since DSH 0.2.1-rc.2 there is ONE
#      row: the host removed the per-instance `persona` / `toolFilter` config
#      keys and `backgroundMode`, and a role is selected by the model-facing
#      `agent_preset` argument naming the role's Agent Preset. A role's tool
#      surface is the set of tool PLUGINS its preset mounts.
#
# This module is the single reader for both facts. Every readiness probe,
# gate axis, and O5 containment check asserts against the SAME parsed repo
# source — never against the retired `.agent-presets/` copy and never against
# a text scan of the live patch, which stopped carrying the rows on
# 2026-10-11. A text-scan guard over an absent section is vacuous by
# construction; parsing the composition that actually carries the rows keeps
# those checks able to FAIL, which is the only thing that makes them checks.
#
# USAGE (read-only; parses YAML, evaluates nothing):
#   from tests.d4d7_composition import (
#       preset_sources_present, preset_source_report,
#       orchestrator_subagent_rows, subagent_row,
#   )
#
# The `!!js` dialect tag (`disabled: !!js process.platform === 'win32'`) is
# mapped to its source text, never evaluated — same approach as
# tests/unit/test_preset_source_integrity.py.

from __future__ import annotations

import os

import yaml

# Repo root: the parent of this tests/ package.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ORCHESTRATOR_ID = "orchestrator"
AGENTS_DIR = "agents"
COMPOSITION_FILE = "agent.cordis.yml"

# The 15 specialist ids come from the production contracts module (PRD v0.2
# roster; config/agents.yaml is canonical) so this reader can never drift from
# the roster the control plane itself uses.
from orchestrator.foundation.contracts import SPECIALIST_ROLES

# The 16 preset ids: 15 `role-<id>` + the orchestrator's bare id.
ROLE_PRESETS = tuple(f"role-{rid}" for rid in SPECIALIST_ROLES)
ALL_PRESETS = ROLE_PRESETS + (ORCHESTRATOR_ID,)


class JsSafeLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that accepts the `!!js` dialect tag as opaque text."""


def _construct_js(loader, node):
    return {"__jsExpr": loader.construct_scalar(node)}


JsSafeLoader.add_constructor("tag:yaml.org,2002:js", _construct_js)


def preset_source_path(preset_id: str) -> str:
    """Absolute path of one preset's composition file (the mount source)."""
    directory = ORCHESTRATOR_ID if preset_id == ORCHESTRATOR_ID else os.path.join(AGENTS_DIR, preset_id.removeprefix("role-"))
    return os.path.join(PROJECT_ROOT, directory, COMPOSITION_FILE)


def preset_sources_present() -> bool:
    """True when all 16 composition sources exist and are non-empty files.

    These files are what the live profile's `link:` dependency
    (dsh-multi-agent-harness in $DSH_HOME/profiles/web/package.json) reads at
    boot, so their persistence IS the mount-persistence fact the old
    `$DSH_HOME/.agent-presets/` scan used to report.
    """
    return preset_source_report()[0]


def preset_source_report() -> tuple[bool, list[str]]:
    """(all_present, missing_list) over the 16 composition sources."""
    missing = [p for p in ALL_PRESETS if not (os.path.isfile(preset_source_path(p)) and os.path.getsize(preset_source_path(p)) > 0)]
    return (not missing, missing)


def orchestrator_composition_path() -> str:
    return os.path.join(PROJECT_ROOT, ORCHESTRATOR_ID, COMPOSITION_FILE)


def orchestrator_composition_rows() -> list[dict]:
    """The orchestrator preset's plugin rows, groups flattened."""
    with open(orchestrator_composition_path(), encoding="utf-8") as fh:
        rows = yaml.load(fh.read(), Loader=JsSafeLoader)
    if not isinstance(rows, list):
        raise ValueError(f"{orchestrator_composition_path()} is not a top-level list of plugin rows")
    flat: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        flat.append(row)
        if row.get("group"):
            flat.extend(r for r in (row.get("config") or []) if isinstance(r, dict))
    return flat


def orchestrator_subagent_rows() -> dict[str, dict]:
    """The delegation rows composed in the orchestrator preset.

    Returns {toolName: row-config}. Since DSH 0.2.1-rc.2 there is ONE row —
    {"subagent": {"provider": "spawn", "maxDepth": 1,
    "allowedAgentPresets": ["role-zeko", ...]}} — because the host removed the
    per-instance `persona` / `toolFilter` config keys and collapsed the
    fifteen per-role instances into one tool whose model-facing `agent_preset`
    argument names the role's Agent Preset. Parsing the composition that
    actually carries the rows is what lets a caller FAIL when the row is
    missing or its allowlist drifted.
    """
    out: dict[str, dict] = {}
    for row in orchestrator_composition_rows():
        if not str(row.get("id", "")).startswith("tool-subagent"):
            continue
        config = row.get("config") or {}
        tool_name = config.get("toolName")
        if isinstance(tool_name, str) and tool_name:
            out[tool_name] = config
    return out


def subagent_row(tool_name: str) -> dict | None:
    """The delegation row's config by tool name (`subagent`)."""
    return orchestrator_subagent_rows().get(tool_name)


# The tool PLUGINS a preset mounts, and the tools each one exposes. 0.2.1-rc.2
# gave the two multi-tool plugins this roster uses a per-tool config, so a
# preset reproduces the exact tool list its role's allow list named.
TOOL_PLUGIN_BY_TOOL = {
    "bash": "@deepseek-ai/dsh-tool-bash",
    "read": "@deepseek-ai/dsh-tool-fs",
    "read_image": "@deepseek-ai/dsh-tool-fs",
    "write": "@deepseek-ai/dsh-tool-fs",
    "edit": "@deepseek-ai/dsh-tool-fs",
    "glob": "@deepseek-ai/dsh-tool-fs-search",
    "grep": "@deepseek-ai/dsh-tool-fs-search",
    "job_kill": "@deepseek-ai/dsh-tool-jobs",
    "job_list": "@deepseek-ai/dsh-tool-jobs",
    "job_output": "@deepseek-ai/dsh-tool-jobs",
    "skill": "@deepseek-ai/dsh-tool-skill",
    "exit_plan_mode": "@deepseek-ai/dsh-plan-mode",
    "web_search": "@deepseek-ai/dsh-tool-web",
    "web_fetch": "@deepseek-ai/dsh-tool-web",
    "todo_write": "@deepseek-ai/dsh-tool-todo",
}


def preset_tool_surface(preset_id: str) -> set[str]:
    """The tools one Agent Preset composition exposes to its agent.

    A preset narrows by COMPOSITION: the tool PLUGINS it mounts, each with its
    own per-tool config applied. A row disabled by a `!!js` platform condition
    (tool-bash on win32) is counted as enabled: the condition is opaque here.
    @param preset_id - `role-<id>` or the orchestrator's bare id.
    @returns The exposed tool names.
    """
    with open(preset_source_path(preset_id), encoding="utf-8") as fh:
        rows = yaml.load(fh.read(), Loader=JsSafeLoader)
    flat: list[dict] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        flat.append(row)
        if row.get("group"):
            flat.extend(r for r in (row.get("config") or []) if isinstance(r, dict))
    exposed: set[str] = set()
    for row in flat:
        name = row.get("name")
        cfg = row.get("config") or {}
        if name == "@deepseek-ai/dsh-tool-bash":
            exposed.add("bash")
        elif name == "@deepseek-ai/dsh-tool-fs":
            if cfg.get("read", True):
                exposed.add("read")
            if cfg.get("readImage", True):
                exposed.add("read_image")
            if cfg.get("write", True):
                exposed.add("write")
            if cfg.get("edit", True):
                exposed.add("edit")
        elif name == "@deepseek-ai/dsh-tool-fs-search":
            exposed.update({"glob", "grep"})
        elif name == "@deepseek-ai/dsh-tool-jobs":
            exposed.update({"job_kill", "job_list", "job_output"})
        elif name == "@deepseek-ai/dsh-tool-skill":
            exposed.add("skill")
        elif name == "@deepseek-ai/dsh-plan-mode":
            exposed.add("exit_plan_mode")
        elif name == "@deepseek-ai/dsh-tool-web":
            if cfg.get("search", True):
                exposed.add("web_search")
            if cfg.get("fetch", True):
                exposed.add("web_fetch")
        elif name == "@deepseek-ai/dsh-tool-todo":
            exposed.add("todo_write")
    return exposed

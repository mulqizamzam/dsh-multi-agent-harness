# tests/d4d7_composition.py — the D4/D7 composition source of truth (read-only)
#
# ARCHITECTURE (cutover 2026-10-10/11 — commits 84e630f and 0477eff):
#
#   1. The 16 agent presets are registered DIRECTLY from this repo by the
#      `dsh-multi-agent-harness` plugin (index.js): every directory under
#      `agents/<id>/` registers as `role-<id>`, and `orchestrator/` registers
#      as `orchestrator`. The `$DSH_HOME/.agent-presets/` deployment copy is
#      RETIRED — there is nothing to sync and nothing deployed.
#   2. The 15 `tool-subagent-<id>` delegation rows moved OUT of the live
#      profile patch (`$DSH_HOME/profiles/web/cordis.patch.yml`) INTO the
#      orchestrator preset composition (`orchestrator/agent.cordis.yml`), so
#      that only orchestrator-bound sessions gain `subagent_<id>`.
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


def orchestrator_subagent_rows() -> dict[str, dict]:
    """The 15 delegation rows composed in the orchestrator preset.

    Returns {toolName: row-config} for every row whose id starts with
    `tool-subagent-`, e.g. {"subagent_zeko": {"persona": "role-zeko",
    "toolFilter": {...}, ...}}. Parsing the composition that actually
    carries the rows is what lets a caller FAIL when a row is missing or
    its filter drifted — the live patch no longer carries them at all.
    """
    with open(orchestrator_composition_path(), encoding="utf-8") as fh:
        rows = yaml.load(fh.read(), Loader=JsSafeLoader)
    if not isinstance(rows, list):
        raise ValueError(f"{orchestrator_composition_path()} is not a top-level list of plugin rows")
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not str(row.get("id", "")).startswith("tool-subagent-"):
            continue
        config = row.get("config") or {}
        tool_name = config.get("toolName")
        if isinstance(tool_name, str) and tool_name:
            out[tool_name] = config
    return out


def subagent_row(tool_name: str) -> dict | None:
    """One delegation row's config by tool name (`subagent_<id>`)."""
    return orchestrator_subagent_rows().get(tool_name)

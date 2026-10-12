"""Preset source integrity: the 16 repo sources are mount-ready, dialect-correct, and registry-exact.

ARCHITECTURE CHANGE (2026-10-10) — supersedes `test_preset_deployment_sync.py`.
That file pinned repo<->deployed BYTE identity for the deploy-copy architecture
(`$DSH_HOME/.agent-presets/role-<id>/` was a hand copy). The repo is now a DSH
plugin (`dsh-multi-agent-harness`, root `index.js` + `cordis.patch.yml`) that
registers the presets straight from `agents/<id>/` and `orchestrator/`: there is
no deployment to sync against, the deploy-copy root is retired by the cutover
this gate guards, and the old invariant no longer describes the system. This
file is the mechanism for the invariant that replaces it. Retirement rationale,
kept with the same honesty the old file had:

  - The old file compared bytes because the drift it found (2026-09-12) was in
    comment blocks, which YAML-equality cannot see. In the new architecture
    there is exactly one live copy, so comment drift is impossible by
    construction — the failure mode moved, it did not disappear.
  - The new silent-failure mode is a preset that parses fine but mounts
    BROKEN: `AgentPresetRegistry` records activation failures on the row
    (`record.broken`), and its logger does not reach the host boot log, so a
    green `registered 16 presets` line proves nothing about mountability. That
    is precisely what happened 2026-10-10: all 16 repo files still carried the
    0.1.1-rc.2 persona key `text:` while the running harness (0.2.0-rc.2)
    requires `prefix:` (`packages/preset/persona/src/index.ts`,
    `prefix: z.string().required()`). Every preset mounted broken and invisible
    until selected. The dialect gate below is the mechanism for that class.

Derived from the repo side only: `config/agents.yaml` is the canonical registry
(15 specialists + the orchestrator = 16 presets). The registered id mapping
mirrors the plugin's `index.js` exactly: `agents/<id>/` -> `role-<id>`, and the
orchestrator keeps its bare id.

Three assertions:

  1. dialect    — every composition's `@deepseek-ai/dsh-persona` row carries
                 `prefix` (non-empty string) and no `text` key
  2. parse      — every composition loads (JsSafeLoader, the same dialect the
                 Loader parses with) into a non-empty list of named rows, and
                 every `preset.yml` carries a non-empty description
  3. registry   — the registry id set == the agents/ + orchestrator source set,
                 and the plugin's `role-<id>` mapping is exactly derivable

Assertions 1-3 have no environment dependency: the sources live in the repo,
so they run anywhere the repo runs. The profile-wiring check inside assertion
3 additionally reads the LIVE profile (`$DSH_HOME/profiles/web/package.json`)
and SKIPS — naming that reason — when no profile is present (off-box), rather
than passing vacuously.
"""

import json
import os

import pytest
import yaml

ORCHESTRATOR_ID = "orchestrator"
PERSONA_PLUGIN = "@deepseek-ai/dsh-persona"
AGENTS_DIR = "agents"
COMPOSITION_FILE = "agent.cordis.yml"
METADATA_FILE = "preset.yml"
# The persona key the RUNNING harness takes. A source edit to the persona
# contract elsewhere (harness upgrade) must move this constant and this file's
# dialect assertion together — that pairing is the point of the gate.
RUNNING_PERSONA_KEY = "prefix"
RETIRED_PERSONA_KEY = "text"
# Live-profile wiring (the profile this plugin is actually bundled into).
DEFAULT_DSH_HOME = "/home/administrator/agent-workspace/.dsh"
LIVE_PROFILE = "web"
PLUGIN_PACKAGE = "dsh-multi-agent-harness"


class JsSafeLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that ACCEPTS the `!!js` dialect tag instead of refusing it.

    Same shape as `test_orchestrator_preset_derivation.py`'s loader: the
    compositions carry `disabled: !!js process.platform === 'win32'`, which
    plain `safe_load` rejects. The Loader (cordis-plugin-include's
    `entryListSchema`) keeps `!!js` as `{ __jsExpr }` nodes; for this gate the
    rows' `name` fields and the persona row's key NAMES are what matter, so
    mapping the tag to its source text is enough.
    """


def _construct_js(loader, node):
    return {"__jsExpr": loader.construct_scalar(node)}


JsSafeLoader.add_constructor("tag:yaml.org,2002:js", _construct_js)


def registry_ids(project_root):
    """The 16 preset ids from the canonical registry, orchestrator first."""
    with open(os.path.join(project_root, "config", "agents.yaml"), encoding="utf-8") as fh:
        registry = yaml.safe_load(fh)
    return [ORCHESTRATOR_ID] + [entry["id"] for entry in registry["agents"]]


def source_dir(preset_id):
    """Preset id -> repo source directory (the orchestrator keeps its own)."""
    return ORCHESTRATOR_ID if preset_id == ORCHESTRATOR_ID else os.path.join(AGENTS_DIR, preset_id)


def registered_id(preset_id):
    """The id the plugin registers this source under (mirrors index.js)."""
    return preset_id if preset_id == ORCHESTRATOR_ID else f"role-{preset_id}"


def load_composition(project_root, preset_id):
    with open(os.path.join(project_root, source_dir(preset_id), COMPOSITION_FILE), encoding="utf-8") as fh:
        return yaml.load(fh.read(), Loader=JsSafeLoader)


def load_metadata(project_root, preset_id):
    with open(os.path.join(project_root, source_dir(preset_id), METADATA_FILE), encoding="utf-8") as fh:
        return yaml.safe_load(fh.read())


def persona_row(rows):
    for row in rows:
        if isinstance(row, dict) and row.get("name") == PERSONA_PLUGIN:
            return row
    return None


# ---------------------------------------------------------------------------
# 1. dialect
# ---------------------------------------------------------------------------


def test_every_composition_uses_the_running_persona_key(project_root):
    """No `text:` persona row anywhere; `prefix:` present and non-empty.

    The 2026-10-10 defect: 16/16 sources on the retired key -> 16/16 preset
    mounts broken -> roster shows them but no session can select one, and the
    host boot line still says "registered 16 presets". Silent because the
    registry's broken-row logger never reaches stderr.
    """
    offenders = []
    for preset_id in registry_ids(project_root):
        rows = load_composition(project_root, preset_id)
        row = persona_row(rows)
        if row is None:
            offenders.append(f"{source_dir(preset_id)}/{COMPOSITION_FILE}: no {PERSONA_PLUGIN} row at all")
            continue
        config = row.get("config") or {}
        if RETIRED_PERSONA_KEY in config:
            offenders.append(
                f"{source_dir(preset_id)}/{COMPOSITION_FILE}: persona row carries the retired "
                f"`{RETIRED_PERSONA_KEY}:` key (harness 0.1.1-rc.2 dialect) — the running "
                f"harness requires `{RUNNING_PERSONA_KEY}:`"
            )
            continue
        value = config.get(RUNNING_PERSONA_KEY)
        if not isinstance(value, str) or not value.strip():
            offenders.append(
                f"{source_dir(preset_id)}/{COMPOSITION_FILE}: persona row's `{RUNNING_PERSONA_KEY}:` "
                f"is missing or not a non-empty string (got {value!r})"
            )
    assert not offenders, (
        f"{len(offenders)} preset source(s) are not in the running harness's persona "
        f"dialect and would mount BROKEN while the boot log stays green:\n  "
        + "\n  ".join(offenders)
        + f"\nACTION: rename the persona key `{RETIRED_PERSONA_KEY}:` to "
        f"`{RUNNING_PERSONA_KEY}:` in the listed file(s). If the harness itself was "
        "upgraded or downgraded, re-check this gate's RUNNING_PERSONA_KEY constant "
        "against `packages/preset/persona/src/index.ts` in the running checkout."
    )


# ---------------------------------------------------------------------------
# 2. parse
# ---------------------------------------------------------------------------


def test_every_composition_parses_as_a_named_entry_list(project_root):
    """Each composition is a non-empty list of rows, every row naming a plugin.

    Catches the class of typo/truncation that `yaml.safe_load` would let
    through as a dict or a list of scalars, which the registry would then
    reject at mount time — again silently, on the row.
    """
    broken = []
    for preset_id in registry_ids(project_root):
        path = os.path.join(source_dir(preset_id), COMPOSITION_FILE)
        try:
            rows = load_composition(project_root, preset_id)
        except yaml.YAMLError as error:
            broken.append(f"{path}: YAML parse failed: {error}")
            continue
        if not isinstance(rows, list) or not rows:
            broken.append(f"{path}: not a non-empty list of plugin rows (got {type(rows).__name__})")
            continue
        unnamed = [index for index, row in enumerate(rows) if not (isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"])]
        if unnamed:
            broken.append(f"{path}: row(s) {unnamed} name no plugin (a non-empty string `name` is required)")
    assert not broken, (
        f"{len(broken)} composition(s) would not mount:\n  " + "\n  ".join(broken)
        + "\nACTION: fix the file so it parses as a top-level list of plugin rows "
        "matching the registry's entry-list contract."
    )


def test_every_preset_yml_carries_a_non_empty_description(project_root):
    """`preset.yml` is the picker's only display metadata; empty is a defect.

    The plugin maps `description` verbatim and ignores every other field, so a
    missing or blank description shows up as an anonymous row in the GUI
    preset picker — visible, but only to someone already looking.
    """
    offenders = []
    for preset_id in registry_ids(project_root):
        path = os.path.join(source_dir(preset_id), METADATA_FILE)
        metadata = load_metadata(project_root, preset_id)
        description = metadata.get("description") if isinstance(metadata, dict) else None
        if not isinstance(description, str) or not description.strip():
            offenders.append(f"{path}: `description` is missing or not a non-empty string (got {description!r})")
    assert not offenders, (
        f"{len(offenders)} preset metadata file(s) carry no description:\n  "
        + "\n  ".join(offenders)
        + "\nACTION: add a one-line `description:` string to the listed file(s) — "
        "it is what the Web GUI preset picker shows."
    )


# ---------------------------------------------------------------------------
# 3. registry
# ---------------------------------------------------------------------------


def test_registry_id_set_equals_the_repo_source_set(project_root):
    """`config/agents.yaml`'s 16 ids are exactly the sources on disk.

    A registry entry without a directory is a preset the plugin skips at boot
    (the boot line still counts the rest as registered); a directory without a
    registry entry is an unreviewed preset the plugin mounts anyway.
    """
    registered = registry_ids(project_root)
    on_disk = [
        entry
        for entry in os.listdir(os.path.join(project_root, AGENTS_DIR))
        if os.path.isdir(os.path.join(project_root, AGENTS_DIR, entry))
    ]
    orchestrator_present = os.path.isdir(os.path.join(project_root, ORCHESTRATOR_ID))

    unsourced = [preset_id for preset_id in registered if not (orchestrator_present if preset_id == ORCHESTRATOR_ID else preset_id in on_disk)]
    assert not unsourced, (
        f"REGISTRY ENTRY WITHOUT SOURCE — `config/agents.yaml` names {unsourced} but "
        f"`{AGENTS_DIR}/` (or `{ORCHESTRATOR_ID}/`) has no such directory. The plugin "
        "logs 'preset root ... skipping' and continues; the preset simply never "
        "appears. ACTION: author the source directory (agent.cordis.yml + preset.yml) "
        "or remove the registry entry."
    )

    unregistered = sorted(set(on_disk) - {preset_id for preset_id in registered if preset_id != ORCHESTRATOR_ID})
    assert not unregistered, (
        f"SOURCE WITHOUT REGISTRY — {unregistered} under `{AGENTS_DIR}/` are not in "
        "`config/agents.yaml`. They are mounted by the plugin regardless (it scans "
        "the directory), so they are live and selectable with no registry entry, no "
        "review trail, and nothing for the mapping or docs to check. ACTION: add them "
        "to the registry or remove them."
    )


def test_plugin_registered_ids_match_the_profile_wiring(project_root):
    """The plugin's id mapping (role-<id>, orchestrator) is exactly derivable
    AND the live profile actually mounts this plugin.

    What used to stand here was tautological: the same derivation written on
    both sides of the `==`, so it could not see drift between the repo mapping
    and the live profile. Two real checks replace it:

    1. disk-derived — the id set is derived from the `agents/` DIRECTORY
       LISTING (what the plugin's `index.js` really registers: `role-<dirname>`
       per directory, plus the bare `orchestrator`) and compared against the
       registry-derived ids. A rename on either side is visible.
    2. profile wiring — the live web profile's `package.json`
       (`$DSH_HOME/profiles/web`, default when DSH_HOME is unset) names this
       plugin in `dsh.profile.bundles` and links it to THIS repo, so the 15
       `persona: role-<id>` rows and `selectedDefault: orchestrator` in
       `cordis.patch.yml` resolve to presets this checkout defines. When no
       live profile is present the test SKIPS with that reason — it never
       passes vacuously.
    """
    # (1) derived from disk, not from the registry comprehension again.
    on_disk = sorted(
        entry for entry in os.listdir(os.path.join(project_root, AGENTS_DIR))
        if os.path.isdir(os.path.join(project_root, AGENTS_DIR, entry))
    )
    derived = {f"role-{dirname}" for dirname in on_disk} | {ORCHESTRATOR_ID}
    mapped = {registered_id(preset_id)
              for preset_id in registry_ids(project_root)}
    assert mapped == derived, (
        "the registry's registered-id mapping deviates from the plugin's "
        "role-<dirname> + orchestrator scheme (index.js): in the registry only "
        f"{sorted(mapped - derived)}, on disk only {sorted(derived - mapped)} "
        "— the live profile's `persona:` rows and selectedDefault name the "
        "registered ids exactly, so a rename breaks every row at once"
    )
    assert len(mapped) == 16, (
        f"expected 16 registered ids, derived {len(mapped)}: {sorted(mapped)}")

    # (2) the live profile bundles and links this plugin.
    profile_dir = os.path.join(
        os.environ.get("DSH_HOME") or DEFAULT_DSH_HOME,
        "profiles", LIVE_PROFILE)
    pkg_path = os.path.join(profile_dir, "package.json")
    if not os.path.exists(pkg_path):
        pytest.skip(
            f"live profile not present at {profile_dir} — the profile-wiring "
            "half of this gate cannot run off-box (point DSH_HOME at the live "
            "profile root to enable it)")
    with open(pkg_path, encoding="utf-8") as fh:
        profile = json.load(fh)
    bundles = profile.get("dsh", {}).get("profile", {}).get("bundles", [])
    assert PLUGIN_PACKAGE in bundles, (
        f"the live profile at {profile_dir} does not bundle "
        f"{PLUGIN_PACKAGE!r} — the role-<id>/orchestrator presets this repo "
        "registers are not mounted by the running profile")
    dep = profile.get("dependencies", {}).get(PLUGIN_PACKAGE, "")
    assert dep.startswith("link:"), (
        f"{PLUGIN_PACKAGE} must be a link: dependency (got {dep!r}) — a "
        "versioned dependency would not register this repo's sources")
    linked = dep[len("link:"):]
    assert os.path.realpath(linked) == os.path.realpath(project_root), (
        f"the profile links {PLUGIN_PACKAGE} at {linked!r}, not this repo "
        f"({project_root}) — the persona rows then name presets this checkout "
        "no longer defines")

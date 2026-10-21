"""ADR 0004 regression: the orchestrator preset is `standard` minus 4 rows plus 15 named delegation instances.

`orchestrator/agent.cordis.yml` is a DSH preset composition derived by COPY from
the shipped `standard` preset (read-only checkout), with exactly four rows
deleted: `tool-pwsh` (top-level) and `tool-subagent-codex`,
`tool-subagent-claude-code`, `tool-ralph` (all three nested inside the
`delegation` group).

2026-10-11 addition: the preset also carries fifteen ADDED rows — the
`tool-subagent-<id>` delegation instances moved here from the global layer of
the live profile patch (see the section comment in the composition). They are
the orchestrator's only delegation surface, they exist in no version of
`standard`, so the set delta is now DELETE 4 + ADD 15 rather than delete-only.
The derivation's purpose is unchanged: upstream drift must still fail loudly.

A preset is a copy, so an upstream change to `standard` never propagates into it
and nothing complains — docs/adr/0004-orchestrator-role-preset.md records that as
a residual gap with no mechanism. THIS TEST IS THE MECHANISM: when upstream
drifts, it fails and says the orchestrator preset needs re-deriving.

Row counting is RECURSIVE by necessity. A `cordis:group` row carries its children
in its own `config:` list, so a top-level-only walk reads the delta as 16 -> 15
(delta 1) and reports those three nested rows as "absent" while they are still
present — a FALSE PASS, and it already happened once here, in
runs/orchestrator-preset-2026-09-12/verify_preset.py (fixed with the recursive
`all_row_ids()` walker that `test_deleted_rows_are_nested_not_top_level` pins
down). Any future verifier of this preset must count recursively too.

Version pin: DeepSeek Harness 0.2.0-rc.2 — the 29/40 counts are counts *in that
composition*, not a universal constant.
"""

import os

import pytest
import yaml

# Same constant as tests/g10/conftest.py:DSH_CHECKOUT — the read-only DSH source
# checkout, which exists only on machines that have one.
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
# 0.2.0-rc.2 moved the shipped presets out of apps/cli/config/agent-presets/
# into the web-app bundle as patch files; the composition lives in the
# preset-standard row's `config.plugins`.
STANDARD_PRESET_PATCH = os.path.join(
    DSH_CHECKOUT, "packages", "bundle", "web-app", "presets", "standard.patch.yml"
)
ORCHESTRATOR_PRESET = os.path.join("orchestrator", "agent.cordis.yml")

# The four rows this preset deletes from `standard`. Mirrors
# runs/orchestrator-preset-2026-09-12/verify_preset.py::DELETED_ROWS.
DELETED_ROWS = frozenset(
    {"tool-pwsh", "tool-subagent-codex", "tool-subagent-claude-code", "tool-ralph"}
)
# The three that are NOT top-level rows — the ones a shallow walk loses.
NESTED_DELETED_ROWS = DELETED_ROWS - {"tool-pwsh"}

# 2026-10-11 discovery, RESOLVED same day: upstream `standard` had gained two
# rows since the 0.1.1-rc.2 derivation this preset was copied from — `present`
# (@deepseek-ai/dsh-tool-present) and `tool-plugin-manager`
# (@deepseek-ai/dsh-plugin-manager/tools, `disabled: true` upstream). The Human
# approved carrying them (re-derivation): both rows were added at their
# `standard` positions after `tool-web`, and `present` was named in
# orchestrator/policy.yaml and role-preset-mapping.yaml allow lists. They are
# NO LONGER drift — kept here as the record of the measurement that found them.
RESOLVED_DRIFTED_ROWS = frozenset({"present", "tool-plugin-manager"})

# 2026-10-11: the fifteen per-role delegation instances MOVED here from the
# global layer of the live profile patch ($DSH_HOME/profiles/web/cordis.patch.yml).
# They are the orchestrator's only delegation surface (role-preset-mapping.yaml
# §orchestrator) and are named in orchestrator/policy.yaml's tool_surface.allow,
# so the preset is no longer a pure derivation: standard - 4 + 15.
ADDED_ROWS = frozenset(
    {
        "tool-subagent-zeko", "tool-subagent-cto", "tool-subagent-cfo",
        "tool-subagent-kai", "tool-subagent-somad", "tool-subagent-badsector",
        "tool-subagent-nova", "tool-subagent-vera", "tool-subagent-argus",
        "tool-subagent-atlas", "tool-subagent-tess", "tool-subagent-quill",
        "tool-subagent-scout", "tool-subagent-talon", "tool-subagent-ledger",
    }
)

STANDARD_ROW_COUNT = 32
ORCHESTRATOR_ROW_COUNT = STANDARD_ROW_COUNT - len(DELETED_ROWS) + len(ADDED_ROWS)

# Appended to every drift failure: what the reader is supposed to DO about it.
ACTION = (
    "ACTION: re-derive orchestrator/agent.cordis.yml from the shipped `standard` "
    "preset (ADR 0004) — copy the current composition verbatim, delete only "
    f"{sorted(DELETED_ROWS)}, restore the orchestrator `persona` text, and keep "
    f"the {len(ADDED_ROWS)} added delegation instances ({sorted(ADDED_ROWS)}) "
    "moved here from the profile patch on 2026-10-11. The upstream drift found "
    f"the same day ({sorted(RESOLVED_DRIFTED_ROWS)}) was resolved by carrying both "
    "rows; if upstream drifts again, repeat that decision explicitly. ADR 0004 "
    "creates no automatic propagation, so this test is the only signal that the "
    "derived copy has fallen behind upstream."
)


class JsSafeLoader(yaml.SafeLoader):
    """`yaml.SafeLoader` that ACCEPTS the `!!js` dialect tag instead of refusing it.

    The shipped preset carries `disabled: !!js process.platform === 'win32'`, which
    plain `yaml.safe_load` rejects ("could not determine a constructor").
    verify_preset.py handles that by deleting `!!js ` from the file text before
    parsing — a parse convenience it documents as such. This loader takes the other
    route available with the same dependency (PyYAML): `!!js` expands to the tag
    `tag:yaml.org,2002:js`, so a constructor is registered for it and the document
    text is never rewritten; the expression is preserved as the scalar it is. A
    non-scalar `!!js` node is a hard error rather than a silent mis-parse.

    What this proves is row structure only, exactly as in verify_preset.py: it does
    not claim the real DSH loader accepts every row.
    """


def _construct_js(loader, node):
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None,
            None,
            "this test loader accepts `!!js` on scalar nodes only",
            node.start_mark,
        )
    return loader.construct_scalar(node)


JsSafeLoader.add_constructor("tag:yaml.org,2002:js", _construct_js)


def load_rows(path):
    """Parse a composition file into its top-level list of plugin rows.

    The shipped preset is a PATCH document (one `preset-standard` row); its
    composition is `config.plugins`. A repo preset file is already a bare list.
    """
    with open(path, encoding="utf-8") as fh:
        doc = yaml.load(fh.read(), Loader=JsSafeLoader)
    if (
        isinstance(doc, list)
        and len(doc) == 1
        and isinstance(doc[0], dict)
        and "insert" in doc[0]
    ):
        doc = doc[0]["insert"][0]["config"]["plugins"]
    assert isinstance(doc, list), f"{path}: composition must be a top-level list, got {type(doc).__name__}"
    return doc


def all_row_ids(rows, _depth=0):
    """Every row id in a composition, RECURSIVELY — including group children.

    A `cordis:group` row keeps its child rows in its own `config:` list. Depth-first
    order, so the result doubles as the composition's row order. See the module
    docstring for why a top-level-only walk is wrong here.
    """
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("id"):
            out.append((row["id"], _depth))
        children = row.get("config")
        if isinstance(children, list):
            out.extend(all_row_ids(children, _depth + 1))
    return out


def ids_of(rows):
    """Recursive row ids, depth stripped."""
    return [i for i, _ in all_row_ids(rows)]


@pytest.fixture(scope="module")
def standard_rows():
    """Rows of the shipped `standard` preset, or a clean SKIP when no checkout here."""
    if not os.path.isfile(STANDARD_PRESET_PATCH):
        why = (
            f"the read-only DSH checkout at {DSH_CHECKOUT} is not present in this "
            "environment"
            if not os.path.isdir(DSH_CHECKOUT)
            else f"the checkout is present but holds no `standard` composition at {STANDARD_PRESET_PATCH}"
        )
        pytest.skip(
            f"shipped `standard` preset not found at {STANDARD_PRESET_PATCH}: {why}, so the "
            "upstream side of this derivation invariant cannot be read"
        )
    return load_rows(STANDARD_PRESET_PATCH)


@pytest.fixture(scope="module")
def orchestrator_rows(project_root):
    path = os.path.join(project_root, ORCHESTRATOR_PRESET)
    assert os.path.isfile(path), f"missing repo composition {path} (ADR 0004)"
    return load_rows(path)


def test_recursive_row_counts_are_32_and_43(standard_rows, orchestrator_rows):
    """Counts are recursive: 32 upstream, 43 here (28 derivation + 15 added)."""
    std, orc = ids_of(standard_rows), ids_of(orchestrator_rows)
    assert len(std) == STANDARD_ROW_COUNT, (
        f"the shipped `standard` preset now has {len(std)} recursive rows, not the "
        f"{STANDARD_ROW_COUNT} pinned at 0.2.0-rc.2 — upstream changed. {ACTION}"
    )
    assert len(orc) == ORCHESTRATOR_ROW_COUNT, (
        f"orchestrator/agent.cordis.yml has {len(orc)} recursive rows, expected "
        f"{ORCHESTRATOR_ROW_COUNT} ({STANDARD_ROW_COUNT} - {len(DELETED_ROWS)} "
        f"+ {len(ADDED_ROWS)}). {ACTION}"
    )


def test_delta_is_exactly_four_deleted_and_fifteen_added(standard_rows, orchestrator_rows):
    """Set delta vs standard: 4 documented deletions, 15 documented additions.

    The 2026-10-11 upstream drift (present, tool-plugin-manager) was resolved by
    carrying both rows, so it is not part of the live delta; if either goes
    missing again this test fails with them named as undocumented absences.
    """
    std, orc = set(ids_of(standard_rows)), set(ids_of(orchestrator_rows))
    removed, added = std - orc, orc - std
    assert added == set(ADDED_ROWS), (
        "orchestrator/agent.cordis.yml carries rows the shipped `standard` preset does "
        f"not have beyond the {len(ADDED_ROWS)} documented additions: "
        f"{sorted(added - set(ADDED_ROWS))}; missing from the documented set: "
        f"{sorted(set(ADDED_ROWS) - added)}. {ACTION}"
    )
    assert removed == set(DELETED_ROWS), (
        "orchestrator/agent.cordis.yml no longer differs from `standard` by exactly "
        f"the four documented rows (previously-resolved drift: {sorted(RESOLVED_DRIFTED_ROWS)}): "
        f"unexpectedly present here: {sorted(set(DELETED_ROWS) - removed)}; absent here but "
        f"not documented: {sorted(removed - set(DELETED_ROWS))}. {ACTION}"
    )


def test_shared_rows_keep_standard_order(standard_rows, orchestrator_rows):
    """The 28 shared rows appear in `standard`'s order — nothing reordered.

    Both sides are filtered to the shared ids, so this asserts ORDER only and lets
    the delta test own membership: an upstream add/remove must not show up here as
    a phantom reordering.
    """
    std, orc = ids_of(standard_rows), ids_of(orchestrator_rows)
    shared = set(std) & set(orc)
    expected = [i for i in std if i in shared]
    actual = [i for i in orc if i in shared]
    assert actual == expected, (
        "orchestrator/agent.cordis.yml reorders rows relative to the shipped `standard` "
        f"preset: expected {expected}, got {actual}. Row order is composition order; the "
        f"derivation is delete-only. {ACTION}"
    )


def test_deleted_rows_are_nested_not_top_level(standard_rows, orchestrator_rows):
    """Pin the recursive walk: 3 of the 4 deleted rows live inside `delegation`.

    Without this, a refactor that drops the recursion would leave the count
    assertions measuring the wrong thing again — the exact bug that produced a
    false PASS in verify_preset.py once.
    """
    nested = {i for i, d in all_row_ids(standard_rows) if d > 0}
    assert NESTED_DELETED_ROWS <= nested, (
        f"the shipped `standard` preset no longer nests {sorted(NESTED_DELETED_ROWS)} "
        f"inside a group row (nested here: {sorted(nested)}); the walk must stay "
        f"recursive either way. {ACTION}"
    )
    assert ids_of(orchestrator_rows).count("delegation") == 1, (
        "the `delegation` group row is gone from orchestrator/agent.cordis.yml, so this "
        f"composition no longer mirrors `standard`'s group structure. {ACTION}"
    )

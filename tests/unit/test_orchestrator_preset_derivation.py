"""ADR 0004 regression: the orchestrator preset is exactly `standard` minus 4 rows.

`orchestrator/agent.cordis.yml` is a DSH preset composition derived by COPY from
the shipped `standard` preset (read-only checkout), with exactly four rows
deleted: `tool-pwsh` (top-level) and `tool-subagent-codex`,
`tool-subagent-claude-code`, `tool-ralph` (all three nested inside the
`delegation` group).

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

Version pin: DeepSeek Harness 0.1.1-rc.2 — the 29/25 counts are counts *in that
composition*, not a universal constant.
"""

import os

import pytest
import yaml

# Same constant as tests/g10/conftest.py:DSH_CHECKOUT — the read-only DSH source
# checkout, which exists only on machines that have one.
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
STANDARD_PRESET = os.path.join(
    DSH_CHECKOUT, "apps", "cli", "config", "agent-presets", "standard", "agent.cordis.yml"
)
ORCHESTRATOR_PRESET = os.path.join("orchestrator", "agent.cordis.yml")

# The four rows this preset deletes from `standard`. Mirrors
# runs/orchestrator-preset-2026-09-12/verify_preset.py::DELETED_ROWS.
DELETED_ROWS = frozenset(
    {"tool-pwsh", "tool-subagent-codex", "tool-subagent-claude-code", "tool-ralph"}
)
# The three that are NOT top-level rows — the ones a shallow walk loses.
NESTED_DELETED_ROWS = DELETED_ROWS - {"tool-pwsh"}

STANDARD_ROW_COUNT = 29
ORCHESTRATOR_ROW_COUNT = STANDARD_ROW_COUNT - len(DELETED_ROWS)

# Appended to every drift failure: what the reader is supposed to DO about it.
ACTION = (
    "ACTION: re-derive orchestrator/agent.cordis.yml from the shipped `standard` "
    "preset (ADR 0004) — copy the current composition verbatim, delete only "
    f"{sorted(DELETED_ROWS)}, and restore the orchestrator `persona` text. ADR 0004 "
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
    """Parse a composition file into its top-level list of plugin rows."""
    with open(path, encoding="utf-8") as fh:
        rows = yaml.load(fh.read(), Loader=JsSafeLoader)
    assert isinstance(rows, list), f"{path}: composition must be a top-level list, got {type(rows).__name__}"
    return rows


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
    if not os.path.isfile(STANDARD_PRESET):
        why = (
            f"the read-only DSH checkout at {DSH_CHECKOUT} is not present in this "
            "environment"
            if not os.path.isdir(DSH_CHECKOUT)
            else f"the checkout is present but holds no `standard` composition at {STANDARD_PRESET}"
        )
        pytest.skip(
            f"shipped `standard` preset not found at {STANDARD_PRESET}: {why}, so the "
            "upstream side of this derivation invariant cannot be read"
        )
    return load_rows(STANDARD_PRESET)


@pytest.fixture(scope="module")
def orchestrator_rows(project_root):
    path = os.path.join(project_root, ORCHESTRATOR_PRESET)
    assert os.path.isfile(path), f"missing repo composition {path} (ADR 0004)"
    return load_rows(path)


def test_recursive_row_counts_are_29_and_25(standard_rows, orchestrator_rows):
    """Counts are recursive: 29 upstream, 25 here. A shallow walk reads 16/15."""
    std, orc = ids_of(standard_rows), ids_of(orchestrator_rows)
    assert len(std) == STANDARD_ROW_COUNT, (
        f"the shipped `standard` preset now has {len(std)} recursive rows, not the "
        f"{STANDARD_ROW_COUNT} it had at 0.1.1-rc.2 — upstream changed. {ACTION}"
    )
    assert len(orc) == ORCHESTRATOR_ROW_COUNT, (
        f"orchestrator/agent.cordis.yml has {len(orc)} recursive rows, expected "
        f"{ORCHESTRATOR_ROW_COUNT} ({STANDARD_ROW_COUNT} - {len(DELETED_ROWS)}). {ACTION}"
    )


def test_delta_is_exactly_the_four_deleted_rows(standard_rows, orchestrator_rows):
    """Nothing added, nothing else removed — the set delta is those four ids."""
    std, orc = set(ids_of(standard_rows)), set(ids_of(orchestrator_rows))
    removed, added = std - orc, orc - std
    assert not added, (
        "orchestrator/agent.cordis.yml carries rows the shipped `standard` preset does "
        f"not have: {sorted(added)}. This preset is a derivation, not an original "
        f"composition. {ACTION}"
    )
    assert removed == set(DELETED_ROWS), (
        "orchestrator/agent.cordis.yml is no longer `standard` minus exactly the four "
        f"documented rows. Missing here but present upstream: {sorted(removed - DELETED_ROWS)}; "
        f"deleted rows unexpectedly present here: {sorted(DELETED_ROWS - removed)}. {ACTION}"
    )


def test_shared_rows_keep_standard_order(standard_rows, orchestrator_rows):
    """The 25 shared rows appear in `standard`'s order — nothing reordered.

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

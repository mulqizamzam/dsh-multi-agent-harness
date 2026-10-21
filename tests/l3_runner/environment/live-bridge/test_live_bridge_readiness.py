"""Session A — D4/D7 live bridge readiness lock tests (read-only).

Locks the live-bridge readiness assessment
(docs/phase-5/environment/live-bridge/0001-d4d7-live-bridge-readiness.md)
to the CURRENT environment with read-only checks:

  - D4D7_FILES: the 16 preset composition sources (15 roles + orchestrator)
    persist in the repo and the delegation row is composed in
    orchestrator/agent.cordis.yml (2026-10-10/11 cutover: direct plugin
    registration, rows moved out of the live profile patch; D8 mount
    exception applied 2026-09-09; DSH 0.2.1-rc.2 collapsed the 15 per-role
    rows into ONE row whose allowedAgentPresets names the 15 role presets);
  - D4D7_COMPOSITION: mapping == policy == preset declaration, allow∩deny=∅,
    deny-list hygiene (no `run_code`, no 25 VERIFIED_UNREGISTERED names),
    post-O5 + 2026-09-07-discriminator role tool-surface invariants (somad/
    nova read-only, cto keeps bash+write+edit, zeko keeps bash only),
    the composed role presets match the config;
  - BRIDGE_MARKER: DSH_LIVE_BRIDGE_ACTIVE is unset (reported, never set);
  - REAL_BACKEND: probe_backend_kind() == UNAVAILABLE (fail-closed);
  - LIVE_DISPATCH_POSSIBLE: NO — RealDSHBackend.start() raises
    BridgeNotAvailable without the marker; no dispatch is performed;
  - L3 readiness: l3_claim_possible=False, rehearsal_ready=True, the
    D4D7-specific check L3ENV-D4D7-3 fails, L3ENV-D4D7-1/2 pass.

These tests change NOTHING: no session policy, no DSH/profile/preset, no
$DSH_HOME, no marker, no live dispatch, no production code, no evidence-store
creation, no G13/L3 execution.
"""

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.l3_runner.environment.readiness import (  # noqa: E402
    ALL_INSTANCE_IDS,
    BRIDGE_MARKER_ENV,
)
from tests.d4d7_composition import (  # noqa: E402
    ALL_PRESETS,
    orchestrator_subagent_rows,
    preset_source_path,
    preset_sources_present,
)
from tests.live_dsh.discovery import (  # noqa: E402
    assert_role_resolution,
    check_instance_mounted,
    probe_all_instances_mounted,
)
from orchestrator.dsh.bridge import (  # noqa: E402
    BackendKind,
    probe_backend_kind,
)
from tests.live_dsh.real_backend import (  # noqa: E402
    BridgeNotAvailable,
    RealDSHBackend,
)
from tests.live_dsh.conftest import make_delegation  # noqa: E402

READINESS_DOC = os.path.join(
    _PROJECT_ROOT, "docs", "phase-5", "environment", "live-bridge",
    "0001-d4d7-live-bridge-readiness.md")

# The 25 VERIFIED_UNREGISTERED names removed by the 0005 correction, and the
# single reserved name removed by 0004 (run_code). None may appear in a role
# deny list (validate_config additionally verifies every remaining name).
VERIFIED_UNREGISTERED_NAMES = frozenset({
    "str_replace_editor", "lsp", "pwsh", "web_fetch",
    "terminal_open", "terminal_read", "terminal_send", "terminal_signal",
    "terminal_list", "terminal_close",
    "schedule_create", "schedule_delete", "schedule_list",
    "session_event_read", "session_event_search", "session_event_trace",
    "session_search", "session_trace",
    "cordis_define", "cordis_inspect_list", "cordis_inspect_query",
    "cordis_inspect_self", "cordis_run", "cordis_stop", "cordis_undefine",
})
RESERVED_NAME = "run_code"


def _role_filters():
    import yaml
    with open(os.path.join(_PROJECT_ROOT, "config",
                           "role-preset-mapping.yaml")) as f:
        mapping = yaml.safe_load(f)
    return {r["id"]: r["tool_surface"] for r in mapping["roles"]}


# ---------------------------------------------------------------------------
# D4D7_FILES — preset sources + delegation rows on disk
# ---------------------------------------------------------------------------

def test_preset_sources_persistent_on_disk():
    """All 16 preset composition sources persist in the repo.

    Since the 2026-10-10 cutover the repo IS the plugin: index.js registers
    `agents/<id>/agent.cordis.yml` as `role-<id>` and
    `orchestrator/agent.cordis.yml` as `orchestrator` at boot, and the live
    web profile depends on this repo by `link:`. The retired
    `$DSH_HOME/.agent-presets/` deployment copy is intentionally NOT checked —
    the source files the live plugin actually reads are the persistence fact,
    and they exist wherever the repo is checked out (no DSH_HOME required).
    """
    missing = [p for p in ALL_PRESETS
               if not (os.path.isfile(preset_source_path(p))
                       and os.path.getsize(preset_source_path(p)) > 0)]
    assert not missing, f"missing preset composition sources: {missing}"
    assert preset_sources_present()


def test_all_instance_rows_present():
    """The ONE delegation row selects all 15 role Agent Presets.

    DSH 0.2.1-rc.2 removed the per-instance `persona` / `toolFilter` config
    keys, so the fifteen `tool-subagent-<id>` rows cannot exist: the
    composition carries ONE `tool-subagent` row whose `allowedAgentPresets`
    names the fifteen role Agent Presets, and the model picks one through
    the `agent_preset` argument. Parsing the file (rather than text-scanning
    the patch that no longer carries the rows) is what lets this test FAIL
    when a role becomes unselectable.
    """
    rows = orchestrator_subagent_rows()
    row = rows.get("subagent")
    assert row is not None, (
        "the delegation row is not composed in orchestrator/agent.cordis.yml")
    allowed = set(row.get("allowedAgentPresets") or [])
    for rid in ALL_INSTANCE_IDS:
        assert rid in allowed, (
            f"role preset not selectable: {rid} (not in the delegation row's "
            f"allowedAgentPresets)")


# ---------------------------------------------------------------------------
# D4D7_COMPOSITION — consistency + hygiene + post-O5 invariants
# ---------------------------------------------------------------------------

def test_mapping_matches_policy_and_instances():
    """mapping == policy == the role's preset declaration, across all 15 roles."""
    import yaml
    with open(os.path.join(_PROJECT_ROOT, "config",
                           "tool-subagent-instances.yaml")) as f:
        instances = yaml.safe_load(f)
    declared = {d["id"]: d["tool_surface"] for d in instances["agent_presets"]}
    filters = _role_filters()
    for rid, tf in filters.items():
        with open(os.path.join(_PROJECT_ROOT, "agents", rid, "policy.yaml")) as f:
            pol = yaml.safe_load(f)
        assert set(tf["allow"]) == set(pol["tool_surface"]["allow"]), rid
        assert set(tf["deny"]) == set(pol["tool_surface"]["deny"]), rid
        dec = declared[f"role-{rid}"]
        assert set(tf["allow"]) == set(dec["allow"]), rid
        assert set(tf["deny"]) == set(dec["deny"]), rid


def test_allow_deny_disjoint():
    for rid, tf in _role_filters().items():
        assert not (set(tf["allow"]) & set(tf["deny"])), rid


def test_deny_lists_free_of_reserved_and_unregistered_names():
    """0004/0005 corrections present: no run_code, no 25 UNREG names."""
    for rid, tf in _role_filters().items():
        deny = set(tf["deny"])
        assert RESERVED_NAME not in deny, rid
        assert not (deny & VERIFIED_UNREGISTERED_NAMES), rid


def test_post_o5_role_tool_expectations():
    """somad/nova have no raw-write tool; cto keeps bash+write+edit while
    zeko keeps bash only (2026-09-07 discriminator: write/edit removed,
    capabilities.code_write: no enforced by the role preset composition);
    read-only roles unchanged."""
    filters = _role_filters()
    for rid in ("somad", "nova"):
        allow = set(filters[rid]["allow"])
        assert not ({"bash", "write", "edit"} & allow), rid
    assert {"bash", "write", "edit"} <= set(filters["cto"]["allow"]), "cto"
    assert "bash" in filters["zeko"]["allow"], "zeko"
    assert not ({"write", "edit"} & set(filters["zeko"]["allow"])), "zeko"
    for rid in ("badsector", "cfo", "kai"):
        deny = set(filters[rid]["deny"])
        assert {"bash", "write", "edit"} <= deny, rid


def test_live_rows_match_config():
    """The composed delegation row selects every role preset, and every role
    preset's composition matches its mapping allow/deny sets.

    Since DSH 0.2.1-rc.2 there is ONE composed delegation row (the fifteen
    per-role rows were removed by the host), so the check moved to the two
    facts the new model makes load-bearing: the row's `allowedAgentPresets`
    names all fifteen role presets, and each role preset's OWN plugin rows
    compose exactly the tool list its mapping declares.

    This also CLOSES a coverage gap: nothing compared the composed role
    presets' tool surface against the config triple (mapping == policy ==
    instances), so a preset could drift silently.
    """
    from tests.d4d7_composition import preset_tool_surface
    rows = orchestrator_subagent_rows()
    assert set(rows) == {"subagent", "subagent_fork"}, f"expected one delegation row, got {sorted(rows)}"
    allowed = set(rows["subagent"].get("allowedAgentPresets") or [])
    assert allowed == {f"role-{rid}" for rid in _role_filters()}, (
        f"the delegation row's allowedAgentPresets must cover every role: "
        f"{sorted(allowed)}")
    for rid, tf in _role_filters().items():
        assert set(tf["allow"]) == preset_tool_surface(f"role-{rid}"), rid


def test_role_resolution_all_fifteen():
    """Config-level resolution: every contract role (PRD v0.2: 15) resolves to
    its `role-<id>` Agent Preset from mapping v3. This is registry parity, not
    a live-mount claim (D8: registration ≠ activation)."""
    from tests.l3_runner.environment.readiness import ALL_INSTANCE_IDS
    result = assert_role_resolution()
    assert set(result.values()) == set(ALL_INSTANCE_IDS)
    from orchestrator.foundation.contracts import SPECIALIST_ROLES
    assert set(result) == set(SPECIALIST_ROLES)


# ---------------------------------------------------------------------------
# BRIDGE_MARKER + REAL_BACKEND — fail-closed current state
# ---------------------------------------------------------------------------

def test_bridge_marker_unset():
    """The session must NOT have the marker set (and these tests never set it)."""
    assert os.environ.get(BRIDGE_MARKER_ENV, "") != "1"


def test_backend_kind_unavailable():
    assert probe_backend_kind() is BackendKind.UNAVAILABLE


def test_no_instance_mounted():
    assert not any(probe_all_instances_mounted().values())


def test_real_start_refuses_without_marker():
    """A REAL dispatch without the marker raises BridgeNotAvailable — the
    harness never performs a live tool call (fail-closed)."""
    backend = RealDSHBackend(dispatch=lambda *a: None, require_marker=True)
    inst = type("I", (), {"tool_name": "subagent_zeko", "role": "zeko"})()
    with pytest.raises(BridgeNotAvailable):
        backend.start(inst, {"prompt": "smoke", "description": "smoke"})


# ---------------------------------------------------------------------------
# L3 readiness — D4D7-specific checks
# ---------------------------------------------------------------------------

def test_readiness_d4d7_checks():
    from tests.l3_runner.environment.readiness import assess_environment
    report = assess_environment(
        scenario_id="L3-TEST-001",
        orchestrator_uid=int(os.getuid()),
    )
    by_id = {c.check_id: c for c in report.checks}
    assert by_id["L3ENV-D4D7-1"].passed is True   # presets present
    assert by_id["L3ENV-D4D7-2"].passed is True   # instance rows present
    assert by_id["L3ENV-D4D7-3"].passed is False  # marker not set
    assert report.l3_claim_possible is False
    assert report.rehearsal_ready is True


# ---------------------------------------------------------------------------
# Readiness doc honesty
# ---------------------------------------------------------------------------

def test_readiness_doc_exists_and_honest():
    assert os.path.isfile(READINESS_DOC)
    with open(READINESS_DOC) as f:
        text = f.read()
    assert "LIVE_DISPATCH_POSSIBLE = NO" in text or \
        "LIVE_DISPATCH_POSSIBLE" in text
    assert "UNAVAILABLE" in text
    assert "no closure" in text.lower() or "no closure claimed" in text.lower()
    assert "no live dispatch" in text.lower() or \
        "no live dsh child observation" in text.lower()

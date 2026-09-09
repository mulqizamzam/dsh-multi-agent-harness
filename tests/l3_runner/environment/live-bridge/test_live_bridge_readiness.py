"""Session A — D4/D7 live bridge readiness lock tests (read-only).

Locks the live-bridge readiness assessment
(docs/phase-5/environment/live-bridge/0001-d4d7-live-bridge-readiness.md)
to the CURRENT environment with read-only checks:

  - D4D7_FILES: 15 role presets + 15 tool-subagent rows present on disk
    (D8 mount exception applied 2026-09-09);
  - D4D7_COMPOSITION: mapping == policy == instance, allow∩deny=∅,
    deny-list hygiene (no `run_code`, no 25 VERIFIED_UNREGISTERED names),
    post-O5 + 2026-09-07-discriminator role/toolFilter invariants (somad/
    nova read-only, cto keeps bash+write+edit, zeko keeps bash only),
    live rows match config;
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
    ROLE_PRESETS,
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
    return {r["id"]: r["tool_filter"] for r in mapping["roles"]}


def _live_patch_text() -> str:
    dsh_home = os.environ.get("DSH_HOME", "")
    assert dsh_home, "DSH_HOME unset — cannot verify the live composition"
    path = os.path.join(dsh_home, "profiles", "web", "cordis.patch.yml")
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# D4D7_FILES — presets + rows on disk
# ---------------------------------------------------------------------------

def test_seven_role_presets_present():
    dsh_home = os.environ.get("DSH_HOME", "")
    if not dsh_home:
        pytest.skip("DSH_HOME unset")
    presets_dir = os.path.join(dsh_home, ".agent-presets")
    assert os.path.isdir(presets_dir)
    present = set(os.listdir(presets_dir))
    assert all(p in present for p in ROLE_PRESETS), (
        f"missing presets: {set(ROLE_PRESETS) - present}")


def test_all_instance_rows_present():
    """All 15 contract instance rows are composed in the live patch
    (ADR 0003 D8 exception applied 2026-09-09)."""
    text = _live_patch_text()
    for rid in ALL_INSTANCE_IDS:
        assert f"toolName: {rid}" in text, f"missing row: {rid}"


# ---------------------------------------------------------------------------
# D4D7_COMPOSITION — consistency + hygiene + post-O5 invariants
# ---------------------------------------------------------------------------

def test_mapping_matches_policy_and_instances():
    """mapping == policy == instance for allow+deny across all 15 roles."""
    import yaml
    with open(os.path.join(_PROJECT_ROOT, "config",
                           "tool-subagent-instances.yaml")) as f:
        instances = yaml.safe_load(f)
    inst_map = {c["config"]["toolName"]: c["config"]["toolFilter"]
                for c in instances["insert_draft"]}
    filters = _role_filters()
    for rid, tf in filters.items():
        with open(os.path.join(_PROJECT_ROOT, "agents", rid, "policy.yaml")) as f:
            pol = yaml.safe_load(f)
        assert set(tf["allow"]) == set(pol["tool_filter"]["allow"]), rid
        assert set(tf["deny"]) == set(pol["tool_filter"]["deny"]), rid
        inst = inst_map[f"subagent_{rid}"]
        assert set(tf["allow"]) == set(inst["allow"]), rid
        assert set(tf["deny"]) == set(inst["deny"]), rid


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
    capabilities.code_write: no enforced at the toolFilter layer);
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
    """All 15 live cordis.patch.yml rows match mapping v2 allow/deny sets.

    Pre-Task-11 this was xfail(strict) — the D8 mount exception was
    Human-approved and applied 2026-09-09 (15 mounted rows, pre-change
    backup in runs/specialist-expansion-2026-09-09/backups/), so
    live == config now and the marker is removed. The strict-xfail phase
    made that transition fail loudly, as designed.
    """
    import yaml
    doc = yaml.safe_load(_live_patch_text())
    rows = doc[0]["insert"]
    live = {r["id"]: r["config"]["toolFilter"]
            for r in rows if r.get("id", "").startswith("tool-subagent-")}
    assert len(live) == 15
    filters = _role_filters()
    assert set(filters) == {lid.removeprefix("tool-subagent-")
                            for lid in live}
    for rid, tf in filters.items():
        lid = f"tool-subagent-{rid}"
        assert set(tf["allow"]) == set(live[lid]["allow"]), rid
        assert set(tf["deny"]) == set(live[lid]["deny"]), rid


def test_role_resolution_all_fifteen():
    """Config-level resolution: every contract role (PRD v0.2: 15) resolves to
    its `subagent_<id>` instance from mapping v2. This is registry parity, not
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

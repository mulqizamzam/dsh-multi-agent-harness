"""Negative authority boundaries for the new specialists (PRD v0.2 §19/§25).

The 8 expansion roles are read-only analysts (ADR 0003 D3): no action without
an active, in-scope delegation; no write; never protected paths; never out of
scope; never a stale delegation. Reference semantics: tests/control_plane.py.
"""
import datetime

import pytest

from control_plane import Deny, authorize

NEW = ("vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger")


def _delegation(actor, action):
    return {"id": f"d-{actor}", "status": "ACTIVE",
            "expires_at": "2030-01-01T00:00:00Z",
            "scope": {"operations": [action], "resources": ["multi-agent-harness/**"],
                      "environments": ["workspace"]}}


@pytest.mark.parametrize("actor", NEW)
def test_new_specialists_cannot_act_without_delegation(actor):
    with pytest.raises(Deny):
        authorize(actor, "read", "multi-agent-harness/config/agents.yaml", None)


@pytest.mark.parametrize("actor", NEW)
def test_new_specialists_denied_write_actions(actor):
    d = _delegation(actor, "read")
    with pytest.raises(Deny):
        authorize(actor, "write", "multi-agent-harness/README.md", d)


@pytest.mark.parametrize("actor", NEW)
def test_new_specialists_denied_protected_paths_even_if_scoped(actor):
    d = _delegation(actor, "write")
    d["scope"]["operations"] = ["write", "registry_write"]
    for target in ("state/registry/agents.yaml", "audit/events.jsonl"):
        with pytest.raises(Deny):
            authorize(actor, "write", target, d, allow_write_paths=())


@pytest.mark.parametrize("actor", NEW)
def test_scope_containment_blocks_out_of_scope_targets(actor):
    d = _delegation(actor, "read")
    d["scope"]["resources"] = ["multi-agent-harness/docs/**"]
    with pytest.raises(Deny):
        authorize(actor, "read", "multi-agent-harness/config/permissions.yaml", d)


def test_stale_delegation_denied_for_new_specialist():
    d = _delegation("vera", "read")
    d["expires_at"] = "2026-09-01T00:00:00Z"
    with pytest.raises(Deny):
        authorize("vera", "read", "multi-agent-harness/PRD-v0.2.md", d,
                  now=datetime.datetime(2026, 9, 9, tzinfo=datetime.timezone.utc))


def test_config_level_boundaries(project_root):
    """Tool-surface boundaries: no write/exec in allow; no delegation plugin in
    the role's preset; read-only roles have no write tools (validator cross-check).

    DSH 0.2.1-rc.2 removed the per-instance toolFilter config key, so the
    declared allow/deny sets are the ROLE's intent and the Agent Preset
    composition is what enforces them. The per-sibling `subagent_<id>` deny
    entries are gone with the tools themselves: there is one delegation tool
    per provider now, and a role's preset mounts no delegation plugin at all,
    so its child has no delegation tool in its catalog.
    """
    import os

    import yaml
    mapping = yaml.safe_load(open(
        os.path.join(project_root, "config", "role-preset-mapping.yaml")))
    all_inst = {f"subagent_{r}" for r in
                ("zeko", "cto", "cfo", "kai", "somad", "badsector", "nova") + NEW}
    for entry in mapping["roles"]:
        rid, tf = entry["id"], entry["tool_surface"]
        allow, deny = set(tf["allow"]), set(tf["deny"])
        assert not (allow & deny)
        assert not (allow & {"subagent", "subagent_fork", "send_message", "workflow"})
        assert not (deny & all_inst), sorted(deny & all_inst)
        composition = yaml.safe_load(open(
            os.path.join(project_root, "agents", rid, "agent.cordis.yml")))
        mounted = {row.get("name") for row in composition if isinstance(row, dict)}
        assert not {name for name in mounted if name and "tool-subagent" in name}, \
            f"{rid}: a role preset must mount no delegation plugin"
        if rid in NEW:
            assert not (allow & {"bash", "edit", "write"})

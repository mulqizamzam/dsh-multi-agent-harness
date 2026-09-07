"""Session C — G10: current D4/D7 role restrictions (toolFilter).

Asserts the per-role toolFilter allow/deny sets from the project config:

  - read-only roles (badsector, cfo, kai) deny bash/edit/write;
  - bash/write/edit-capable roles: zeko (bash only, since the 2026-09-07
    discriminator removed its write/edit) and cto (bash+write+edit);
    somad/nova are read-only at the DSH layer (write/edit removed, O5);
  - write/edit-capable set is exactly {cto} (2026-09-07 discriminator);
  - allow ∩ deny = ∅;
  - the D4/D7 composition exception status is recorded honestly (mounted
    since 2026-09-07) so the residual actor set is derived from the
    REAL current state, not from a stale assumption.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


# ---------------------------------------------------------------------------
# Actor set: who can raw-write at the DSH layer (toolFilter allow sets)
# ---------------------------------------------------------------------------

def test_readonly_roles_deny_raw_write_tools(role_filters):
    for rid in ("badsector", "cfo", "kai"):
        deny = role_filters[rid]["deny"]
        assert "bash" in deny, rid
        assert "write" in deny, rid
        assert "edit" in deny, rid


def test_raw_write_capable_roles_identified(raw_write_roles):
    """bash/write/edit-capable set (conftest definition): zeko keeps bash
    (ops diagnosis, documented residual), cto keeps all three; somad/nova
    lost write/edit under O5 and had bash denied/hard-excluded."""
    assert set(raw_write_roles) == {"zeko", "cto"}


def test_write_edit_capable_roles_identified(role_filters):
    """2026-09-07 zeko discriminator (task 3 of the Human-approved
    "laksanakan 1-4" plan): exactly {cto} still holds write/edit.
    zeko's capabilities.code_write: no is now enforced at the toolFilter
    layer instead of being advisory."""
    write_edit = sorted(
        r for r, f in role_filters.items() if {"write", "edit"} & f["allow"])
    assert write_edit == ["cto"]


def test_current_actor_enumeration_matches_o5_record(raw_write_roles):
    """Consistency: the CURRENT config-derived bash/write/edit-capable actor
    set must match the recorded post-O5 actor set, as amended 2026-09-07 by
    the zeko discriminator amendment (docs/phase-1/0003-... §Amendment 1 —
    zeko loses write/edit, keeps bash).

    Guards against a stale doc drift: if the live config and the recorded
    outcome diverge (e.g. a future session re-adds write/edit to any
    non-cto role, or a rollback restores an old set), this fails loudly.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    record = os.path.join(root, "docs", "phase-5", "security", "g10",
                          "implementation",
                          "0002-o5-application-record.md")
    assert os.path.exists(record), (
        "O5 application record missing from "
        "docs/phase-5/security/g10/implementation/")
    with open(record) as f:
        text = f.read()

    # The recorded post-O5 bash/write/edit actor set was {zeko, cto}; the
    # 2026-09-07 Human-approved zeko discriminator amends the write/edit
    # actors to {cto} (bash residual on zeko documented). The record's
    # original {zeko, cto} line is retained as history; the amendment is
    # recorded in the same file (2026-09-07 amendment section).
    current = set(raw_write_roles)
    assert current == {"zeko", "cto"}, (
        f"current config actor set {sorted(current)} != amended record {sorted({'zeko', 'cto'})}")
    assert "{zeko, cto}" in text, (
        "O5 record does not document the historical post-O5 actor set {zeko, cto}")
    assert "amendment" in text.lower() and "2026-09-07" in text, (
        "O5 record does not carry the 2026-09-07 zeko-discriminator amendment")
    assert "somad" in text and "nova" in text, (
        "O5 record must document the somad/nova write/edit removal")


def test_raw_write_roles_carry_tool_surface(role_filters, raw_write_roles):
    """Each raw-write role must hold at least one raw filesystem tool."""
    for rid in raw_write_roles:
        assert {"bash", "write", "edit"} & role_filters[rid]["allow"], rid


def test_o5_somad_nova_deny_write_edit(role_filters):
    """O5 guard: somad and nova must NOT hold raw write capability at the
    DSH layer (their content is channel-routed through the project write
    path).

    Post-reconciliation deny contract (locked to the deployed live rows by
    test_live_rows_match_config): write/edit stay hard-denied for both roles;
    somad additionally hard-denies bash (ISO-004, no infra capability); nova
    enforces its bash/web boundary via the closed allow list (ISO-005) —
    bash/web_search are not in nova's allow, and deny lists may only name
    tools restrict() can actually restrict for the child.
    """
    for rid in ("somad", "nova"):
        allow = role_filters[rid]["allow"]
        assert "write" not in allow, f"{rid} must not allow write (O5)"
        assert "edit" not in allow, f"{rid} must not allow edit (O5)"
        assert "bash" not in allow, f"{rid} must not allow bash (O5)"
        deny = role_filters[rid]["deny"]
        assert {"write", "edit"} <= deny, \
            f"{rid} must hard-deny write/edit (O5 defense in depth)"
    assert "bash" in role_filters["somad"]["deny"], \
        "somad must hard-deny bash (ISO-004)"


def test_specialists_hard_deny_sibling_delegation_instances(role_filters):
    """Subdelegation DENY BY DEFAULT at the REAL delegation surface: every
    specialist's deny list hard-names its six sibling subagent_<id>
    instances (global-layer rows, restrictable from every child). The
    generic "subagent" deny never blocked these — restriction matching is
    exact-name."""
    instances = {"subagent_zeko", "subagent_cto", "subagent_cfo",
                 "subagent_kai", "subagent_somad", "subagent_badsector",
                 "subagent_nova"}
    for rid, f in role_filters.items():
        siblings = instances - {f"subagent_{rid}"}
        assert siblings <= f["deny"], (
            f"{rid} must hard-deny sibling delegation instances: "
            f"{sorted(siblings - f['deny'])}")


def test_allow_deny_disjoint(role_filters):
    for rid, f in role_filters.items():
        assert not (f["allow"] & f["deny"]), rid


def test_no_delegation_tools_in_specialist_allow(role_filters):
    """Subdelegation DENY BY DEFAULT: no specialist allows a delegation
    tool."""
    delegation = {"subagent", "subagent_fork", "subagent_cto",
                  "subagent_cfo", "subagent_kai", "subagent_nova",
                  "subagent_somad", "subagent_badsector", "subagent_zeko",
                  "send_message", "workflow", "ralph"}
    for rid, f in role_filters.items():
        assert not (delegation & f["allow"]), rid


# ---------------------------------------------------------------------------
# D4/D7 composition exception status (honest record of current state)
# ---------------------------------------------------------------------------

def test_composition_exception_status_documented():
    """The config files must carry an honest status so the actor set is not
    derived from a stale 'mounted' assumption."""
    for rel in ("config/role-preset-mapping.yaml",
                "config/tool-subagent-instances.yaml"):
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        with open(os.path.join(root, rel)) as f:
            text = f.read()
        assert "mounted" in text.lower() or "mount" in text.lower(), rel


def test_no_closure_claim_in_g10_assessment():
    """The G10 session-C assessment must NOT claim path isolation is
    closed (honesty guard). If the report is absent, this fails loudly
    rather than silently passing."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    report = os.path.join(root, "docs", "phase-5", "security", "g10",
                          "0001-g10-filesystem-isolation-assessment.md")
    assert os.path.exists(report), (
        "G10 assessment report missing from docs/phase-5/security/g10/")
    with open(report) as f:
        text = f.read()
    assert "OPEN" in text, "report must state G10 OPEN"
    assert "no closure claim" in text.lower() or \
        "no claim of closure" in text.lower() or \
        "no closure of prevention claimed" in text.lower(), (
            "report must not claim closure")
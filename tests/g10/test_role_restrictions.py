"""Session C — G10: current D4/D7 role restrictions (toolFilter).

Asserts the per-role toolFilter allow/deny sets from the project config:

  - read-only roles (badsector, cfo, kai) deny bash/edit/write;
  - post-O5 raw-write-capable roles (zeko, cto only) hold bash and/or
    write/edit, so they CAN carry a raw filesystem mutation; somad/nova
    are read-only at the DSH layer (write/edit removed, O5);
  - allow ∩ deny = ∅;
  - the D4/D7 composition exception status is recorded honestly (draft/
    not-mounted vs mounted) so the residual actor set is derived from the
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
    """After O5 (write/edit removed from somad, nova): exactly {zeko, cto}
    hold raw write capability via bash and/or write/edit."""
    assert set(raw_write_roles) == {"zeko", "cto"}


def test_current_actor_enumeration_matches_o5_record(raw_write_roles):
    """Consistency: the CURRENT config-derived raw-write actor set must
    match the post-O5 actor set recorded in the O5 application record.

    Guards against a stale doc drift: if the live config and the recorded
    O5 outcome diverge (e.g. a future session re-adds write/edit to somad
    or nova, or a rollback restores the pre-O5 set), this fails loudly.
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

    # The record documents the post-O5 raw-write actor set as exactly
    # {zeko, cto} (application record §1 effect + §4 verification row).
    current = set(raw_write_roles)
    assert current == {"zeko", "cto"}, (
        f"current config actor set {sorted(current)} != O5 record {sorted({'zeko', 'cto'})}")
    assert "{zeko, cto}" in text, (
        "O5 record does not document the post-O5 actor set {zeko, cto}")
    assert "somad" in text and "nova" in text, (
        "O5 record must document the somad/nova write/edit removal")


def test_raw_write_roles_carry_tool_surface(role_filters, raw_write_roles):
    """Each raw-write role must hold at least one raw filesystem tool."""
    for rid in raw_write_roles:
        assert {"bash", "write", "edit"} & role_filters[rid]["allow"], rid


def test_o5_somad_nova_deny_write_edit(role_filters):
    """O5 guard: somad and nova must NOT allow write/edit at the DSH layer
    (their content is channel-routed through the project write path)."""
    for rid in ("somad", "nova"):
        allow = role_filters[rid]["allow"]
        assert "write" not in allow, f"{rid} must not allow write (O5)"
        assert "edit" not in allow, f"{rid} must not allow edit (O5)"
        deny = role_filters[rid]["deny"]
        assert "bash" in deny, f"{rid} must deny bash (unchanged)"


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
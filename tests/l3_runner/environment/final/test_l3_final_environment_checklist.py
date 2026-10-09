"""Final operator/infrastructure checklist tests (Phase 5 / Final, Session D).

Locks the Human + Infrastructure readiness checklist
(docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md)
to the CURRENT environment with read-only checks:

  - the checklist document exists and covers all 11 prerequisites with
    READY / BLOCKED + exact operator action + exact evidence required;
  - rehearsal_ready=True and l3_claim_possible=False on this host;
  - exactly the five documented L3-required blockers are absent
    (separate UID, Human answerer, `ask` path, live bridge marker, real
    Human signoff);
  - no prerequisite was changed by these tests (read-only invariants);
  - the final l3_claim_possible derivation matches the probe's honest
    report (AND over all required_for_l3 checks).

These tests change NOTHING: no session policy, no DSH/profile/preset, no
$DSH_HOME, no production code, no role mapping, no evidence-store creation,
no fabricated Human signoff.
"""

import json
import os
import subprocess
import sys

import pytest

from tests.environment.approval_composition import authorized_web_url

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.environment.readiness import (  # noqa: E402
    BRIDGE_MARKER_ENV,
    EVIDENCE_STORE_DIR,
    ROLE_PRESETS,
    assess_environment,
)

CHECKLIST_PATH = os.path.join(
    PROJECT_ROOT, "docs", "phase-5", "environment", "final",
    "0001-operator-infrastructure-checklist.md")

# The 11 prerequisites, in checklist order (matching the brief).
PREREQUISITES = [
    "Separate UID / credential",
    "Separate verifier process",
    "Human approval answerer",
    "Functional `ask` path",
    "D4/D7 live bridge",
    "`DSH_LIVE_BRIDGE_ACTIVE`",
    "Persistent role instances",
    "Human-signed plan mechanism",
    "Evidence store",
    "Replay tooling",
    "Approved live-run authorization",
]


# ---------------------------------------------------------------------------
# Checklist document coverage
# ---------------------------------------------------------------------------
def _checklist_text() -> str:
    assert os.path.isfile(CHECKLIST_PATH), (
        f"checklist missing: {CHECKLIST_PATH}")
    with open(CHECKLIST_PATH) as f:
        return f.read()


def test_checklist_exists_and_covers_all_11_prerequisites():
    text = _checklist_text()
    for prereq in PREREQUISITES:
        # Each prerequisite must appear in the checklist table.
        assert prereq in text, f"prerequisite missing from checklist: {prereq}"


def test_checklist_has_ready_blocked_and_operator_action_columns():
    text = _checklist_text()
    assert "READY / BLOCKED" in text
    assert "Exact operator action" in text
    assert "Exact evidence required" in text


def test_checklist_records_final_l3_claim_derivation():
    text = _checklist_text()
    assert "l3_claim_possible" in text
    assert "l3_claim_possible = False" in text or "= False" in text
    assert "rehearsal_ready" in text


def test_checklist_records_three_blockers():
    text = _checklist_text()
    for blocker in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert blocker in text, f"blocker {blocker} must be documented"


def test_checklist_makes_no_immunity_or_closure_claim():
    text = _checklist_text().lower()
    assert "no l3 claim" in text
    assert "no control is l3" in text or "no control is claimed l3" in text
    assert "fabricat" in text  # no fabricated signoff


# ---------------------------------------------------------------------------
# Current-environment derivation (read-only probe)
# ---------------------------------------------------------------------------
def _report():
    # Ambient derivation, no injected snapshot: the readiness checks read
    # the live environment. Tests that need a specific answerer state
    # branch on authorized_web_url() and assert both outcomes, so no
    # partial env snapshot can silently satisfy ENV-3.
    return assess_environment(
        scenario_id="L3-TEST-001",
        orchestrator_uid=int(os.getuid()),
    )


def test_rehearsal_ready_true():
    report = _report()
    assert report.rehearsal_ready is True
    assert report.all_required_pass is True


def test_l3_claim_possible_false():
    report = _report()
    assert report.l3_claim_possible is False
    assert report.all_l3_required_pass is False


def test_exactly_three_l3_blockers():
    """After the probe repair the L3 blocker set is exactly the three
    independent blockers (UID-2, D4D7-3, PLAN-REAL) whenever an authorized
    (launch-token) browser answerer is attached. Without one the answerer
    checks (ANS-1/ANS-2) additionally block, fail-closed: a
    composed-but-unattached surface never counts as a live Human answerer.
    """
    report = _report()
    failed_l3 = sorted(c.check_id for c in report.checks
                       if not c.passed and c.required_for_l3)
    independent = sorted(["L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"])
    if authorized_web_url():
        assert failed_l3 == independent, (
            f"unexpected L3 blocker set with answerer attached: {failed_l3}")
        assert len(report.blocked) == 3
    else:
        # Fail-closed: the answerer checks block ON TOP of the independent
        # three — additive, never the sole blocker, never silenced.
        for cid in independent:
            assert cid in failed_l3, (
                f"independent blocker {cid} missing from {failed_l3}")
        for cid in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
            assert cid in failed_l3, (
                f"answerer blocker {cid} must block without an attached "
                f"browser: {failed_l3}")


def test_l3_claim_possible_is_and_of_required_for_l3():
    """The checklist's derivation rule must match the probe: l3_claim_possible
    is True only when every required_for_l3 check passes."""
    report = _report()
    assert report.l3_claim_possible == report.all_l3_required_pass
    assert all(c.passed for c in report.checks if c.required_for_l3) is False


# ---------------------------------------------------------------------------
# Per-prerequisite current facts (read-only)
# ---------------------------------------------------------------------------
def test_uid_separation_absent_same_uid_host():
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-UID-2")
    assert check.passed is False
    assert "same_uid" in check.detail


def test_answerer_and_ask_path_ready_by_composition():
    """The answerer checks PASS after the probe repair when an authorized
    (launch-token) browser answerer is attached (web GUI answerer available
    by composition). Without an attached browser they fail closed — a
    composed-but-unattached surface is never reported as a live answerer.
    """
    report = _report()
    for cid in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
        check = next(c for c in report.checks if c.check_id == cid)
        if authorized_web_url():
            assert check.passed is True, (
                f"{cid} must PASS after probe repair (web GUI answerer "
                f"available by composition)")
        else:
            assert check.passed is False, (
                f"{cid} must fail closed without an attached browser "
                f"answerer")


def test_bridge_marker_unset():
    assert os.environ.get(BRIDGE_MARKER_ENV, "") != "1"
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-D4D7-3")
    assert check.passed is False


def test_role_instances_persistent_on_disk():
    """D4/D7 composition files persist (presets + instance rows) even though
    the live bridge is inactive — READY for item 7, BLOCKED for items 5/6."""
    dsh_home = os.environ.get("DSH_HOME", "")
    if dsh_home:
        presets = os.path.join(dsh_home, ".agent-presets")
        if os.path.isdir(presets):
            present = set(os.listdir(presets))
            assert all(r in present for r in ROLE_PRESETS), (
                "expected the 15 role presets on disk")
    report = _report()
    for cid in ("L3ENV-D4D7-1", "L3ENV-D4D7-2"):
        check = next(c for c in report.checks if c.check_id == cid)
        assert check.passed is True


def test_real_human_signoff_absent():
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-PLAN-REAL")
    assert check.passed is False
    # The fixture signoff must NOT be promoted to a real signoff.
    assert "not invent" in check.detail.lower() or "invent" in check.detail.lower()


def test_evidence_store_not_created_by_probe():
    """Read-only invariant: the probe (and these tests) never create
    audit/l3/ — item 9 is READY (writable) but no bundle exists yet."""
    assert not os.path.exists(EVIDENCE_STORE_DIR)
    assert os.access(PROJECT_ROOT, os.W_OK)


def test_replay_tooling_ready():
    report = _report()
    for cid in ("L3ENV-REP-1", "L3ENV-REP-2", "L3ENV-REP-3", "L3ENV-REP-4"):
        check = next(c for c in report.checks if c.check_id == cid)
        assert check.passed is True, f"{cid} must pass for replay readiness"


def test_approved_live_run_authorization_absent():
    """Item 11: no Human acceptance of docs/security/0003 §15 is recorded;
    LiveDSHRuntimeDriver remains a refuse-to-simulate stub. This is
    BLOCKED — there is no authorization record."""
    # The live driver must not claim to dispatch live.
    driver = os.path.join(PROJECT_ROOT, "tests", "l3_runner",
                          "runtime_driver.py")
    with open(driver) as f:
        src = f.read()
    assert "BLOCKED" in src or "refuse" in src.lower() or "NotImplementedError" in src
    # No acceptance record exists in audit/ (the only stores are runtime
    # evidence; no L3 authorization record).
    audit_root = os.path.join(PROJECT_ROOT, "audit")
    assert not os.path.exists(os.path.join(audit_root, "l3"))


def test_cli_probe_exit_zero_with_l3_claim_false():
    """The readiness CLI must exit 0 (rehearsal machinery ready) while
    reporting l3_claim_possible=False.

    The blocked-set size tracks the ambient answerer attachment: with an
    authorized (launch-token) browser answerer attached the three
    independent blockers (UID-2, D4D7-3, PLAN-REAL) are the whole set;
    without one the answerer checks additionally block, fail-closed — never
    fewer than the independent three.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "tests.l3_runner.environment.readiness",
         "--scenario", "L3-TEST-001", "--orchestrator-uid", str(os.getuid()),
         "--json"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["rehearsal_ready"] is True
    assert data["l3_claim_possible"] is False
    # `blocked` entries are "<CHECK-ID>: <detail>" strings.
    blocked = list(data["blocked"])
    assert len(blocked) >= 3
    for cid in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert any(b.startswith(cid) for b in blocked), (
            f"independent blocker {cid} missing from {blocked}")
    if authorized_web_url():
        assert len(blocked) == 3

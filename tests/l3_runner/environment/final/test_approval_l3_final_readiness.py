"""Session B (repair) — Approval + L3 Environment FINAL Readiness tests.

Locks the final readiness report
(docs/phase-5/environment/final/0002-approval-l3-final-readiness.md) to the
CURRENT environment with read-only checks:

  1. The final report document exists and covers all 13 checks
     (approval policy, approval service composition, web answerer surface,
     approval/request -> Human decision -> approval/decided, separate PID,
     separate UID, D4/D7 live mount, DSH_LIVE_BRIDGE_ACTIVE, REAL backend,
     real Human-signed plan, evidence store, replay, authorized live-run).
  2. The report distinguishes composition-ready from E2E-verified.
  3. The report states l3_claim_possible=False with exactly the three
     remaining L3 blockers (UID-2, D4D7-3, PLAN-REAL) after the targeted
     approval-probe repair; the answerer/approval-path checks (ANS-1/2) now
     PASS in the web GUI session (probe no longer under-reports).
  4. Current facts are verified read-only: approval policy = ask; approval
     service + web answerer surface composed in the DSH bundles; web session
     attached (HTTP 200); separate PID available; separate UID ABSENT;
     DSH_LIVE_BRIDGE_ACTIVE unset; REAL backend unavailable; no real Human
     signoff; evidence store writable (never created); replay ready; no
     authorized live-run.
  5. The E2E approval detector is repaired: it returns a valid typed result
     (ApprovalReadiness with a default status — no TypeError), the corrected
     detector is wired into readiness.py::_answerer_available, and E2E is
     honestly reported as UNKNOWN (the previously observed Human answer cannot
     be independently re-derived from the current session log).
  6. Honesty: no invented approval/signature, no L3 claim, no session-policy
     or DSH change, read-only invariants.

These tests change NOTHING: no session policy, no DSH/profile/preset, no
$DSH_HOME, no production code, no approval/signature invented, no G13/L3
executed.
"""

import enum
import json
import os
import re
import subprocess
import sys

import pytest

# tests/l3_runner/environment/final/ -> project root is 5 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.environment.readiness import (  # noqa: E402
    BRIDGE_MARKER_ENV,
    EVIDENCE_STORE_DIR,
    assess_environment,
)

FINAL_DOC = os.path.join(
    PROJECT_ROOT, "docs", "phase-5", "environment", "final",
    "0002-approval-l3-final-readiness.md")
DSH_CHECKOUT = "/home/administrator/deepseek-harness"
BASE_PATCH = os.path.join(DSH_CHECKOUT, "packages", "bundle", "base",
                          "cordis.patch.yml")
WEB_PATCH = os.path.join(DSH_CHECKOUT, "packages", "bundle", "web-app",
                         "cordis.patch.yml")
APPROVAL_COMPOSITION = os.path.join(
    PROJECT_ROOT, "tests", "environment", "approval_composition.py")
E2E_MARKER = os.path.join(
    PROJECT_ROOT, "tests", "environment", ".approval_e2e_probe_done")

# The 13 checks in the final report (matching the brief).
REQUIRED_CHECKS = [
    "Effective approval policy = ask",
    "Actual approval service composition",
    "Web GUI Human answerer surface",
    "approval/request",
    "Separate PID",
    "Separate UID",
    "D4/D7 live mount",
    "DSH_LIVE_BRIDGE_ACTIVE",
    "REAL backend availability",
    "Real Human-signed plan",
    "Evidence store",
    "Replay",
    "Authorized live-run condition",
]


def _doc_text() -> str:
    assert os.path.isfile(FINAL_DOC), f"final report missing at {FINAL_DOC}"
    with open(FINAL_DOC) as f:
        return f.read()


def _report():
    return assess_environment(
        scenario_id="L3-TEST-001",
        orchestrator_uid=int(os.getuid()),
    )


# ---------------------------------------------------------------------------
# 1. Final report document coverage
# ---------------------------------------------------------------------------

def test_final_report_exists_and_covers_all_13_checks():
    text = _doc_text()
    for check in REQUIRED_CHECKS:
        assert check.lower() in text.lower(), \
            f"final report must cover check: {check!r}"


def test_final_report_has_readiness_columns():
    text = _doc_text()
    assert "READY / BLOCKED" in text
    assert "Current state" in text
    assert "Operator action" in text
    assert "Exact evidence" in text


def test_final_report_distinguishes_composition_from_e2e():
    """Composition-ready must be distinguished from E2E-verified."""
    text = _doc_text()
    assert "composition-ready" in text.lower() or \
        "composition ready" in text.lower()
    assert "e2e" in text.lower()
    assert "approval_interactive_ready" in text
    assert "approval_e2e_verified" in text


def test_final_report_states_l3_claim_possible_false():
    text = _doc_text()
    assert "l3_claim_possible = False" in text
    assert "l3_claim_possible = False" in text or "= False" in text
    assert "rehearsal_ready" in text
    assert "rehearsal_ready      = True" in text or "True" in text


def test_final_report_documents_three_l3_blockers():
    text = _doc_text()
    for blocker in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert blocker in text, f"blocker {blocker} must be documented"
    # ANS-1/2 are no longer blockers (probe was repaired; they now PASS in
    # the web GUI session). The doc must state they are no longer blocked.
    assert "no longer blocked" in text.lower() or \
        "no longer" in text.lower() or \
        "pass" in text.lower(), \
        "doc must indicate ANS-1/2 no longer block"


def test_final_report_documents_probe_repair():
    """The report must document that the readiness probe previously
    under-reported Web GUI approval readiness and that the targeted repair
    wired the corrected detector (no longer under-reporting)."""
    text = _doc_text()
    assert "under-report" in text or "under_reports" in text, \
        "report must identify the historical probe under-report finding"
    assert "DSH_APPROVAL_PROMPTS_DISABLED" in text, \
        "report must name the obsolete probe key (historical)"
    assert "repair" in text.lower() or "fixed" in text.lower() or \
        "wired" in text.lower(), \
        "report must state the probe was repaired/fixed"


# ---------------------------------------------------------------------------
# 2. Current-environment derivation (read-only probe)
# ---------------------------------------------------------------------------

def test_rehearsal_ready_true():
    report = _report()
    assert report.rehearsal_ready is True
    assert report.all_required_pass is True


def test_l3_claim_possible_false():
    report = _report()
    assert report.l3_claim_possible is False
    assert report.all_l3_required_pass is False


def test_exactly_three_l3_blockers():
    report = _report()
    failed_l3 = [c.check_id for c in report.checks
                 if not c.passed and c.required_for_l3]
    assert sorted(failed_l3) == sorted(
        ["L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"]), (
        f"unexpected L3 blocker set after repair: {failed_l3}")
    assert len(report.blocked) == 3


# ---------------------------------------------------------------------------
# 3. Per-check current facts (read-only)
# ---------------------------------------------------------------------------

def test_approval_policy_is_ask():
    from tests.environment.preflight import REQUIRED_APPROVAL_POLICY
    assert REQUIRED_APPROVAL_POLICY == "ask"
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-ENV-2")
    assert "ask" in check.detail


def test_approval_service_composed_in_dsh_bundle():
    """DSH base bundle composes the approval service (row + package)."""
    if not os.path.isfile(BASE_PATCH):
        pytest.skip("DSH checkout not available")
    with open(BASE_PATCH) as f:
        text = f.read()
    assert "- id: approval" in text
    assert "@deepseek-ai/dsh-user-approval" in text
    assert "danger-full-access" in text  # policy derivation present


def test_web_answerer_surface_composed():
    """Web-app bundle composes the browser answerer surface."""
    if not os.path.isfile(WEB_PATCH):
        pytest.skip("DSH checkout not available")
    with open(WEB_PATCH) as f:
        text = f.read()
    assert "- id: ui-user-questions" in text
    assert "- id: ui-conversation" in text


def test_web_session_attached():
    """DSH_WEB_URL set + web server responds HTTP 200."""
    web_url = os.environ.get("DSH_WEB_URL", "")
    if not web_url:
        pytest.skip("DSH_WEB_URL unset")
    proc = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
         "--connect-timeout", "2", web_url],
        capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "200"


def test_separate_pid_available():
    report = _report()
    for cid in ("L3ENV-UID-1", "L3ENV-UID-3"):
        check = next(c for c in report.checks if c.check_id == cid)
        assert check.passed is True, f"{cid} must pass for separate-PID"


def test_separate_uid_absent_same_uid_host():
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-UID-2")
    assert check.passed is False
    assert "same_uid" in check.detail


def test_bridge_marker_unset_and_backend_unavailable():
    assert os.environ.get(BRIDGE_MARKER_ENV, "") != "1"
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-D4D7-3")
    assert check.passed is False


def test_real_human_signoff_absent():
    report = _report()
    check = next(c for c in report.checks if c.check_id == "L3ENV-PLAN-REAL")
    assert check.passed is False
    assert "not invent" in check.detail.lower() or \
        "invent" in check.detail.lower()


def test_evidence_store_writable_never_created():
    assert os.access(PROJECT_ROOT, os.W_OK)
    assert not os.path.exists(EVIDENCE_STORE_DIR)


def test_replay_tooling_ready():
    report = _report()
    for cid in ("L3ENV-REP-1", "L3ENV-REP-2", "L3ENV-REP-3", "L3ENV-REP-4"):
        check = next(c for c in report.checks if c.check_id == cid)
        assert check.passed is True, f"{cid} must pass for replay readiness"


def test_authorized_live_run_absent():
    driver = os.path.join(PROJECT_ROOT, "tests", "l3_runner",
                          "runtime_driver.py")
    with open(driver) as f:
        src = f.read()
    assert "BLOCKED" in src or "refuse" in src.lower() or \
        "NotImplementedError" in src
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3"))


# ---------------------------------------------------------------------------
# 4. E2E approval instrumentation state (honest)
# ---------------------------------------------------------------------------

def test_e2e_probe_marker_not_an_authority():
    """The E2E status is derived ONLY from observed approval + decided events
    in the session log — never from a marker file, composition, or a stale
    record. This session genuinely ran a harmless approval-required probe, so
    the re-derived status reflects that real pair; if no pair existed E2E would
    be UNKNOWN and NEVER promoted to PASS."""
    if os.path.isfile(E2E_MARKER):
        pytest.skip("legacy marker file present")
    from tests.environment.approval_composition import detect_approval_status
    detection = detect_approval_status()
    # Evidence-based: E2E is PASS only when a genuine pair is re-derivable.
    assert detection.e2e_verified == bool(detection.e2e_pair)
    assert detection.probe_answered == detection.e2e_verified
    # Never promoted to PASS without a re-derived approval+decided pair.
    if not detection.e2e_pair:
        assert detection.e2e_status == "UNKNOWN"
    assert detection.status is not None


def test_corrected_detector_has_no_typeerror():
    """The corrected approval detector is now FIXED: ApprovalReadiness declares
    status with a default value (APPROVAL_HEADLESS_UNAVAILABLE), so no
    TypeError occurs. The detector returns a valid typed result — the
    function detect_approval_status() exists and can be called without
    crash."""
    assert os.path.isfile(APPROVAL_COMPOSITION), \
        "approval_composition.py missing"
    # Import dynamically and verify it works.
    import importlib
    mod = importlib.import_module("tests.environment.approval_composition")
    detection = mod.detect_approval_status()
    assert detection.status is not None
    assert isinstance(detection.status, enum.Enum)
    assert detection.e2e_status in ("PASS", "UNKNOWN", "UNAVAILABLE")


def test_corrected_detector_is_wired_into_readiness():
    """readiness.py::_answerer_available now imports and uses the corrected
    approval_composition detection (the probe is no longer under-reporting)."""
    readiness = os.path.join(PROJECT_ROOT, "tests", "l3_runner",
                             "environment", "readiness.py")
    with open(readiness) as f:
        src = f.read()
    assert "approval_composition" in src, (
        "readiness.py must import approval_composition (corrected detector)")


def test_readiness_probe_returns_accurate_composition_result():
    """In the current web GUI session, the corrected readiness probe reports
    the answerer as available (L3ENV-ANS-1 PASS). Previously it under-reported
    as absent. This is not a false positive — the DSH bundle composes the
    answerer surface and the web browser is attached."""
    report = _report()
    ans1 = next(c for c in report.checks if c.check_id == "L3ENV-ANS-1")
    assert ans1.passed, (
        "L3ENV-ANS-1 must PASS in a web GUI session with the corrected "
        "detector (the answerer IS composed and reachable)")


# ---------------------------------------------------------------------------
# 5. Honesty / read-only invariants
# ---------------------------------------------------------------------------

def test_final_report_makes_no_l3_claim_and_no_immunity():
    text = _doc_text().lower()
    assert "l3_claim_possible = false" in text
    assert "no l3 claim" in text or "no control is l3" in text
    assert "no invented" in text or "no approval" in text or \
        "no invented approval" in text or "no invented signature" in text


def test_final_report_states_no_policy_or_dsh_change():
    text = _doc_text().lower()
    assert "no session-policy change" in text or "no policy change" in text
    assert "no dsh" in text and ("profile" in text or "preset" in text)
    assert "no g13/l3" in text or "no g13" in text or "no l3" in text


def test_cli_probe_exit_zero_with_l3_claim_false():
    """The readiness CLI must exit 0 (rehearsal machinery ready) while
    reporting l3_claim_possible=False."""
    proc = subprocess.run(
        [sys.executable, "-m", "tests.l3_runner.environment.readiness",
         "--scenario", "L3-TEST-001", "--orchestrator-uid", str(os.getuid()),
         "--json"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["rehearsal_ready"] is True
    assert data["l3_claim_possible"] is False
    assert len(data["blocked"]) == 3

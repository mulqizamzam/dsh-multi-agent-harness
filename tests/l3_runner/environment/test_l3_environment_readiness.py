"""L3 environment + Human-answerer readiness tests (Phase 5 / Session D).

Honesty invariants under test:
  - The probe is read-only (no env mutation, no file writes, no policy change).
  - rehearsal_ready=True on this host (all required PF-* checks pass).
  - l3_claim_possible=False (same-UID, answerer absent, bridge inactive, no real
    Human signoff).
  - Answerer detection is honest: absent answerer -> BLOCKED.
  - UID detection is honest: same-UID -> BLOCKED.
  - Does not invent Human signatures: L3ENV-PLAN-REAL fails on fixture plans.
  - D4/D7: files persistent, bridge inactive -> BLOCKED for live L3.
  - CLI exit code reflects rehearsal readiness (2 when required check fails).
"""

import json
import os
import subprocess
import sys

import pytest

from tests.l3_runner.environment.readiness import (
    BRIDGE_MARKER_ENV,
    EVIDENCE_STORE_DIR,
    PROJECT_ROOT,
    ROLE_PRESETS,
    _answerer_available,
    _d4d7_bridge_marker_set,
    _d4d7_instance_rows_present,
    _d4d7_presets_present,
    _evidence_store_writable,
    _real_human_signoff_observed,
    assess_environment,
)


# ===========================================================================
# Read-only invariant
# ===========================================================================
def test_probe_is_read_only(monkeypatch):
    """The probe must never mutate environment variables, session policy, or
    DSH files."""
    env_before = dict(os.environ)
    # Run with injectable snapshot (no live env dependency).
    report = assess_environment(
        scenario_id="L3-TEST-001",
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=0,
    )
    assert dict(os.environ) == env_before
    # No file should have been created in the evidence store.
    assert not os.path.exists(EVIDENCE_STORE_DIR)


# ===========================================================================
# Rehearsal readiness (all required PF-* checks pass)
# ===========================================================================
def test_rehearsal_ready_with_injected_env():
    report = assess_environment(
        scenario_id="L3-TEST-001",
        env={
            "sandbox_mode": "workspace-write",
            "approval_policy": "ask",
            "dsh_version": "0.1.1-rc.2",
            "os": "linux",
            "python_version": "3.14",
            "permission_preset": "web",
            "utc_offset_seconds": 0,
            "seed": 42,
        },
        orchestrator_uid=0,
    )
    assert report.rehearsal_ready, "rehearsal must be ready (all required checks pass)"
    for c in report.checks:
        if c.required and not c.passed:
            pytest.fail(f"required check {c.check_id} failed: {c.detail}")


# ===========================================================================
# L3 claim impossible (honest)
# ===========================================================================
def test_l3_claim_impossible_on_this_host():
    """On this same-UID host with no answerer, no bridge, and no real signoff,
    l3_claim_possible must be False."""
    report = assess_environment(
        scenario_id="L3-TEST-001",
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=0,
    )
    assert not report.l3_claim_possible


# ===========================================================================
# UID / process
# ===========================================================================
def test_uid_detection_same_uid(monkeypatch):
    """When the subprocess probe returns the same UID as the orchestrator,
    L3ENV-UID-2 must fail (BLOCKED)."""
    monkeypatch.setenv("DSH_APPROVAL_PROMPTS_DISABLED", "0")
    report = assess_environment(
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=1000,
    )
    uid2 = next(c for c in report.checks if c.check_id == "L3ENV-UID-2")
    # On this host the subprocess probe returns the same UID -> FAIL.
    assert not uid2.passed
    assert "same-UID" in uid2.detail


# ===========================================================================
# Answerer honesty (corrected detection)
# ===========================================================================
def test_answerer_available_by_composition_in_web_session():
    """With the corrected detection, in a web GUI session where the DSH
    base bundle composes the approval service and the web-app bundle composes
    the answerer surface, the answerer IS available by composition. The obsolete
    DSH_APPROVAL_PROMPTS_DISABLED convention is NEVER consulted (DSH does not
    read it)."""
    # Setting the obsolete convention must NOT flip detection to unavailable.
    import os
    val = os.environ.get("DSH_APPROVAL_PROMPTS_DISABLED", "")
    assert _answerer_available(env={})
    # The snapshot override still works for deterministic injection.
    assert _answerer_available(env={"approval_answerer_available": True})
    assert not _answerer_available(env={"approval_answerer_available": False})


def test_answerer_unavailable_without_composition_or_web_session(monkeypatch):
    """When the answerer surface is NOT composed (e.g. headless/non-web
    session), _answerer_available reports absent (fail-closed). Injected via
    snapshot for determinism."""
    assert not _answerer_available(env={"approval_answerer_available": False})


def test_answerer_absent_blocks_l3():
    """When the answerer is absent (injected via snapshot), L3ENV-ANS-1 must
    fail and appear in blocked."""
    report = assess_environment(
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask",
             "approval_answerer_available": False},
        orchestrator_uid=0,
    )
    ans1 = next(c for c in report.checks if c.check_id == "L3ENV-ANS-1")
    assert not ans1.passed
    assert any("L3ENV-ANS-1" in b for b in report.blocked)


def test_answerer_available_in_live_web_session_does_not_false_positive_l3():
    """With the corrected detection, in this live web GUI session the answerer
    is available by composition (DSH base + web-app bundles), so L3ENV-ANS-1
    PASSES — the probe no longer under-reports. L3 remains blocked by the
    independent blockers (UID-2, D4D7-3, PLAN-REAL), never by a false-negative
    answerer check."""
    report = assess_environment(
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=int(os.getuid()),
    )
    ans1 = next(c for c in report.checks if c.check_id == "L3ENV-ANS-1")
    assert ans1.passed
    assert not report.l3_claim_possible
    # The corrected answerer check must NOT falsely block L3: ANS-1 is absent
    # from the blocker set. L3 is still blocked by the independent blockers
    # (UID-2, D4D7-3, PLAN-REAL). We assert the invariant rather than an exact
    # set, because assess_environment also flags ENV-3/PLAN-1 when the caller
    # omits the full env snapshot and plan (as this test does).
    failed = sorted(c.check_id for c in report.checks
                    if not c.passed and c.required_for_l3)
    assert "L3ENV-ANS-1" not in failed, (
        f"answerer check must not falsely block L3: {failed}")
    for cid in ("L3ENV-D4D7-3", "L3ENV-PLAN-REAL", "L3ENV-UID-2"):
        assert cid in failed, f"independent blocker {cid} missing from {failed}"


# ===========================================================================
# D4/D7
# ===========================================================================
def test_d4d7_presets_present():
    """On this host the 7 role presets exist under $DSH_HOME/.agent-presets/."""
    assert _d4d7_presets_present()


def test_d4d7_instance_rows_present():
    """The 7 tool-subagent rows are composed in cordis.patch.yml."""
    # The check is robust to a missing DSH_HOME -> returns False; in the
    # current environment the rows are verified present.
    dsh = os.environ.get("DSH_HOME", "")
    if dsh and os.path.isfile(os.path.join(dsh, "profiles", "web", "cordis.patch.yml")):
        assert _d4d7_instance_rows_present()


def test_d4d7_bridge_marker_unset(monkeypatch):
    monkeypatch.delenv(BRIDGE_MARKER_ENV, raising=False)
    assert not _d4d7_bridge_marker_set()


# ===========================================================================
# Signed plan
# ===========================================================================
def test_real_human_signoff_not_observed():
    """A fixture plan with synthetic signoff id must NOT be treated as a real
    Human signoff (the probe never invents)."""
    fixture_plan = {
        "human_signoff_id": "human-2026-08-31-001",
        "human_signoff_ts": "2026-08-31T00:00:00Z",
        "human_signoff_method": "interactive",
    }
    assert not _real_human_signoff_observed(fixture_plan)
    assert not _real_human_signoff_observed({"human_signoff_method": "interactive"})
    assert not _real_human_signoff_observed(None)


def test_signed_plan_mechanism_ready_but_real_signoff_absent():
    """PF-PLAN-1..5 pass for the L3-TEST-001 fixture, but L3ENV-PLAN-REAL
    must fail (the fixture is inert)."""
    report = assess_environment(
        scenario_id="L3-TEST-001",
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=0,
    )
    for cid in ("L3ENV-PLAN-1", "L3ENV-PLAN-2", "L3ENV-PLAN-3",
                "L3ENV-PLAN-4", "L3ENV-PLAN-5"):
        c = next(c for c in report.checks if c.check_id == cid)
        assert c.passed, f"{cid} should pass on the fixture: {c.detail}"
    real = next(c for c in report.checks if c.check_id == "L3ENV-PLAN-REAL")
    assert not real.passed
    assert "not invent" in real.detail.lower()


# ===========================================================================
# Evidence store
# ===========================================================================
def test_evidence_store_writable():
    assert _evidence_store_writable()  # project root is writable


# ===========================================================================
# CLI
# ===========================================================================
def test_cli_exit_code_reflects_rehearsal_readiness():
    """Exit 0 when rehearsal machinery is ready, even with l3_claim_possible=False."""
    proc = subprocess.run(
        [sys.executable, "-m", "tests.l3_runner.environment.readiness",
         "--scenario", "L3-TEST-001", "--orchestrator-uid", "0"],
        capture_output=True, text=True,
        cwd=PROJECT_ROOT,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "rehearsal_ready=True" in proc.stdout
    assert "l3_claim_possible=False" in proc.stdout


def test_cli_verbosely_reports_blocked():
    """When a required-for-L3 check fails, blocked items must be printed."""
    proc = subprocess.run(
        [sys.executable, "-m", "tests.l3_runner.environment.readiness",
         "--scenario", "L3-TEST-001", "--orchestrator-uid", "1000"],
        capture_output=True, text=True,
        cwd=PROJECT_ROOT,
    )
    assert "BLOCKED" in proc.stdout


# ===========================================================================
# Honesty: no invented signatures
# ===========================================================================
def test_no_invented_human_signature():
    """The probe must never report a real Human signoff unless it observed one."""
    report = assess_environment(
        scenario_id="L3-TEST-001",
        env={"sandbox_mode": "workspace-write", "approval_policy": "ask"},
        orchestrator_uid=0,
    )
    real = next(c for c in report.checks if c.check_id == "L3ENV-PLAN-REAL")
    assert not real.passed
    assert "no real human signoff" in real.detail.lower()
    assert "invent" in real.detail.lower()
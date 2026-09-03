# tests/environment/test_environment_preflight.py — Session B (G2+G3) tests
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Proves the environment-readiness preflight (tests/environment/preflight.py):
#   - baseline policy detection (workspace-write + ask)
#   - approval-answerer detection (G3) via corrected DSH bundle/web composition
#     (approval_composition) — the obsolete DSH_APPROVAL_PROMPTS_DISABLED
#     convention and $DSH_HOME/profiles marker scan are NOT used
#   - D4/D7 mount-marker + preset detection (G2)
#   - DSH version pin
#   - honest readiness derivation (never claims readiness it did not detect)
#   - REPORT ONLY: no env var / session policy / DSH is modified

import os
import subprocess
import sys

import pytest

from tests.environment.preflight import (
    BRIDGE_MARKER_ENV,
    DSH_VERSION_PIN,
    ROLE_PRESETS,
    run_env_preflight,
)


# ---------------------------------------------------------------------------
# Baseline policy (PB-1)
# ---------------------------------------------------------------------------

def test_baseline_policy_pass_when_snapshot_matches():
    report = run_env_preflight(env={
        "sandbox_mode": "workspace-write",
        "approval_policy": "ask",
    })
    p1 = next(c for c in report.checks if c.check_id == "ENV-POLICY-1")
    p2 = next(c for c in report.checks if c.check_id == "ENV-POLICY-2")
    assert p1.passed and p2.passed


def test_baseline_policy_fails_on_drift():
    report = run_env_preflight(env={
        "sandbox_mode": "danger-full-access",
        "approval_policy": "never",
    })
    p1 = next(c for c in report.checks if c.check_id == "ENV-POLICY-1")
    p2 = next(c for c in report.checks if c.check_id == "ENV-POLICY-2")
    assert not p1.passed and not p2.passed
    # REPORT ONLY: the preflight never re-baselines.
    assert "REPORT ONLY" in p1.detail and "REPORT ONLY" in p2.detail


# ---------------------------------------------------------------------------
# Approval-answerer availability (G3)
# ---------------------------------------------------------------------------

def test_answerer_available_when_explicit():
    report = run_env_preflight(env={"approval_answerer_available": True})
    a = next(c for c in report.checks if c.check_id == "ENV-APPROVAL-1")
    assert a.passed
    assert report.ready_for_interactive


def test_answerer_detection_uses_composition_not_disabled_convention(monkeypatch):
    # The obsolete convention DSH_APPROVAL_PROMPTS_DISABLED must NOT drive the
    # detection anymore (DSH never reads it). The corrected probe detects the
    # answerer via DSH bundle/web composition.
    monkeypatch.setenv("DSH_APPROVAL_PROMPTS_DISABLED", "1")
    report = run_env_preflight(env={})
    a = next(c for c in report.checks if c.check_id == "ENV-APPROVAL-1")
    # On this host the DSH base bundle composes the approval service and the
    # web-app bundle composes the answerer surface; the session is a web GUI
    # session, so the answerer is available by composition. The obsolete
    # convention must not flip it to unavailable.
    assert a.passed
    assert report.ready_for_interactive


def test_answerer_unavailable_without_composition(monkeypatch, tmp_path):
    # With no DSH checkout reachable the corrected probe fails closed (no
    # invented answerer). Monkeypatch the composition detection functions.
    import tests.environment.approval_composition as ac
    monkeypatch.setattr(ac, "approval_service_composed", lambda: False)
    monkeypatch.setattr(ac, "answerer_surface_composed", lambda: False)
    # The preflight's _answerer_available imports the composition detector
    # lazily inside the function, so the patch is picked up without reload.
    report = run_env_preflight(env={})
    a = next(c for c in report.checks if c.check_id == "ENV-APPROVAL-1")
    assert not a.passed
    assert not report.ready_for_interactive


def test_answerer_detection_never_mutates(monkeypatch):
    before = os.environ.get("DSH_APPROVAL_PROMPTS_DISABLED", "<unset>")
    run_env_preflight(env={"approval_answerer_available": False})
    after = os.environ.get("DSH_APPROVAL_PROMPTS_DISABLED", "<unset>")
    assert before == after  # detection only


# ---------------------------------------------------------------------------
# D4/D7 mount availability (G2)
# ---------------------------------------------------------------------------

def test_mount_marker_absent_is_reported_fail(monkeypatch):
    monkeypatch.delenv(BRIDGE_MARKER_ENV, raising=False)
    report = run_env_preflight(env={})
    m = next(c for c in report.checks if c.check_id == "ENV-MOUNT-1")
    assert not m.passed
    assert "unset" in m.detail
    assert "BridgeNotAvailable" in m.detail


def test_mount_marker_present(monkeypatch):
    monkeypatch.setenv(BRIDGE_MARKER_ENV, "1")
    report = run_env_preflight(env={})
    m = next(c for c in report.checks if c.check_id == "ENV-MOUNT-1")
    assert m.passed
    assert "REAL DSH" in m.detail


def test_role_presets_detection(monkeypatch, tmp_path):
    # No $DSH_HOME -> absent.
    monkeypatch.delenv("DSH_HOME", raising=False)
    report = run_env_preflight(env={})
    p = next(c for c in report.checks if c.check_id == "ENV-MOUNT-2")
    assert not p.passed
    assert not p.required  # presets may be mounted via cordis.patch.yml rows

    # Fake a $DSH_HOME with all 7 presets -> present.
    presets_dir = tmp_path / ".agent-presets"
    presets_dir.mkdir()
    for role in ROLE_PRESETS:
        (presets_dir / role).mkdir()
    monkeypatch.setenv("DSH_HOME", str(tmp_path))
    report = run_env_preflight(env={})
    p = next(c for c in report.checks if c.check_id == "ENV-MOUNT-2")
    assert p.passed


def test_ready_for_live_dsh_requires_all(monkeypatch, tmp_path):
    # marker + presets + policy -> ready_for_live_dsh True
    monkeypatch.setenv(BRIDGE_MARKER_ENV, "1")
    presets_dir = tmp_path / ".agent-presets"
    presets_dir.mkdir()
    for role in ROLE_PRESETS:
        (presets_dir / role).mkdir()
    monkeypatch.setenv("DSH_HOME", str(tmp_path))
    report = run_env_preflight(env={
        "sandbox_mode": "workspace-write",
        "approval_policy": "ask",
    })
    assert report.ready_for_live_dsh

    # drop the marker -> not ready (fail-closed)
    monkeypatch.delenv(BRIDGE_MARKER_ENV, raising=False)
    report = run_env_preflight(env={
        "sandbox_mode": "workspace-write",
        "approval_policy": "ask",
    })
    assert not report.ready_for_live_dsh


# ---------------------------------------------------------------------------
# DSH version pin
# ---------------------------------------------------------------------------

def test_dsh_version_pin():
    report = run_env_preflight(env={})
    d = next(c for c in report.checks if c.check_id == "ENV-DSH-1")
    assert d.passed
    assert DSH_VERSION_PIN in d.detail


def test_dsh_version_mismatch_reported():
    report = run_env_preflight(env={"dsh_version": "deepseek-harness-9.9.9"})
    d = next(c for c in report.checks if c.check_id == "ENV-DSH-1")
    assert not d.passed


# ---------------------------------------------------------------------------
# Honesty / REPORT ONLY invariants
# ---------------------------------------------------------------------------

def test_preflight_is_detection_only(monkeypatch):
    """The preflight must not change any environment variable."""
    env_before = dict(os.environ)
    run_env_preflight(env={})
    assert dict(os.environ) == env_before


def test_current_environment_reports_honestly():
    """In the current (degraded) environment the preflight must honestly report
    what is NOT ready — without faking readiness."""
    report = run_env_preflight(env={})
    ids = {c.check_id for c in report.checks}
    assert ids == {"ENV-POLICY-1", "ENV-POLICY-2", "ENV-APPROVAL-1",
                   "ENV-MOUNT-1", "ENV-MOUNT-2", "ENV-DSH-1"}
    # Every check carries a human-readable detail.
    for c in report.checks:
        assert c.detail, f"{c.check_id} must carry a detail"


def test_cli_exit_code_reflects_required_checks():
    """Exit 2 when a required check fails; 0 otherwise (detection semantics)."""
    proc = subprocess.run(
        [sys.executable, "-m", "tests.environment.preflight",
         "--approval-answerer", "false"],
        capture_output=True, text=True, cwd=os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    # In the current env, answerer unavailable + marker unset -> required FAIL.
    assert proc.returncode == 2
    assert "ENV-MOUNT-1" in proc.stdout
    assert "ready_for_live_dsh=False" in proc.stdout

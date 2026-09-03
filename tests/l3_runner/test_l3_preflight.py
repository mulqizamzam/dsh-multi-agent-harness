# tests/l3_runner/test_l3_preflight.py — L3 run prerequisites preflight tests
#
# Exercises tests/l3_runner/preflight.py, the read-only preflight checker that
# verifies the L3 run prerequisites BEFORE any scenario runs:
#   - the need for separate UID/process (IO-1/IO-2 honest probe)
#   - verifier prerequisites (clean imports, oracle resolution, subprocess)
#   - environment preflight (DSH pin, baseline report, env fields)
#   - Human-signed plan prerequisites (schema-valid fields, signoff ordering)
#   - reproducibility requirements (fixture hash, replay script, sha256)
#
# SAFETY: the preflight never runs L3. It never spawns a live DSH session,
# never executes a destructive/high-impact scenario, and never modifies session
# policy, DSH core, profiles, presets, or production control-plane code. All
# checks are pure detection over tmp_path fixtures + the real L3 fixtures.

from __future__ import annotations

import json
import os
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
FIXTURES_ROOT = os.path.join(TESTS_ROOT, "l3_reference", "fixtures")
SCHEMAS_ROOT = os.path.join(TESTS_ROOT, "l3_reference", "schemas")
REPLAY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay.sh")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.preflight import (  # noqa: E402
    REQUIRED_APPROVAL_POLICY,
    REQUIRED_SANDBOX_MODE,
    PreflightCheck,
    PreflightReport,
    _probe_subprocess_uid,
    _sha256_file,
    run_preflight,
)


def _load_plan(scenario_id):
    with open(os.path.join(FIXTURES_ROOT, scenario_id, "plan.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# PreflightReport / PreflightCheck shape
# ---------------------------------------------------------------------------
def test_preflight_report_serializable():
    report = PreflightReport(scenario_id="L3-TEST-001")
    report.add(PreflightCheck("PF-UID-1", "separate process", passed=True,
                              detail="pid differs"))
    d = report.to_dict()
    assert d["scenario_id"] == "L3-TEST-001"
    assert d["all_required_pass"] is True
    assert d["checks"][0]["check"] == "PF-UID-1"
    assert d["checks"][0]["pass"] is True


def test_preflight_check_failed_required_blocks():
    report = PreflightReport()
    report.add(PreflightCheck("PF-PLAN-1", "plan present", passed=False))
    assert report.all_required_pass is False


# ---------------------------------------------------------------------------
# Separate UID / process (the IO-1/IO-2 need)
# ---------------------------------------------------------------------------
def test_preflight_separate_process_need_ok_with_distinct_pid():
    """PF-UID-1 passes when the orchestrator pid differs from this process."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=os.getuid())
    c = next(c for c in report.checks if c.check_id == "PF-UID-1")
    assert c.passed is True


def test_preflight_separate_process_need_fails_on_same_pid():
    """PF-UID-1 fails when the verifier would share the orchestrator's PID."""
    report = run_preflight(orchestrator_pid=os.getpid(), orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-UID-1")
    assert c.passed is False
    assert report.l3_claim_possible is False


def test_preflight_separate_uid_honest_in_same_uid_sandbox():
    """PF-UID-2 must honestly report NOT achievable on a same-UID host.

    This sandbox runs orchestrator and verifier under the same host UID, so the
    probe returns the same UID => PF-UID-2 fails honestly and no L3 claim is
    possible. This is the honesty rule: never fake a credential separation that
    was not achieved (docs/security/0006 §3).
    """
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=os.getuid())
    c = next(c for c in report.checks if c.check_id == "PF-UID-2")
    if os.getuid() == _probe_subprocess_uid():
        # Same-UID host: must fail honestly and demote the L3 claim.
        assert c.passed is False
        assert report.l3_claim_possible is False
    else:
        # Distinct-UID host: may pass; the assertion is that it does not lie.
        assert c.passed is True
        assert report.l3_claim_possible is True


def test_preflight_separate_uid_ok_with_distinct_uid():
    """PF-UID-2 passes when a distinct UID is supplied (auditor/host can)."""
    report = run_preflight(orchestrator_pid=99999,
                           orchestrator_uid=os.getuid() + 1)
    c = next(c for c in report.checks if c.check_id == "PF-UID-2")
    assert c.passed is True


def test_preflight_uid_probe_subprocess():
    """The subprocess UID probe actually spawns a subprocess and reads a uid."""
    uid = _probe_subprocess_uid()
    assert isinstance(uid, int) and uid > 0


def test_preflight_not_spawned_via_session_tree():
    """PF-UID-3 documents that the verifier is a subprocess, not a subagent."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-UID-3")
    assert c.passed is True
    assert "subprocess" in c.detail


# ---------------------------------------------------------------------------
# Verifier prerequisites
# ---------------------------------------------------------------------------
def test_preflight_verifier_clean_import_guard():
    """PF-VER-1: the verifier is importable and carries a clean-import guard."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-VER-1")
    assert c.passed is True


def test_preflight_verifier_oracle_resolves_for_authority():
    """PF-VER-2: the reference oracle resolves for the authority gate."""
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-VER-2")
    assert c.passed is True
    assert "authority_gate.py" in c.detail


def test_preflight_verifier_binary_sha256():
    """PF-VER-3: verifier binary sha256 is computable (IO-3)."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-VER-3")
    assert c.passed is True
    assert c.detail.startswith("sha256=")
    # The detail shows the first 16 hex chars of the 64-char digest (truncated
    # for readability); IO-3 is satisfied by the module hashing the file.
    assert len(c.detail) >= len("sha256=") + 16


def test_preflight_verifier_spawns_clean_subprocess():
    """PF-VER-4: the verifier spawns cleanly in a subprocess (P2 machinery)."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-VER-4")
    assert c.passed is True
    assert "CLEAN" in c.detail


def test_preflight_oracle_classes_requirement_documented():
    """PF-VER-5: >= 2 oracle classes requirement is documented/enforced."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-VER-5")
    assert c.passed is True


# ---------------------------------------------------------------------------
# Environment preflight
# ---------------------------------------------------------------------------
def test_preflight_env_dsh_pin():
    """PF-ENV-1: a bad dsh_version must fail the preflight (LV5)."""
    report = run_preflight(
        env={"dsh_version": "9.9.9", "os": "x", "python_version": "3",
             "sandbox_mode": "workspace-write", "approval_policy": "ask",
             "permission_preset": "p", "utc_offset_seconds": 0, "seed": 1},
        orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-ENV-1")
    assert c.passed is False


def test_preflight_env_baseline_reports_but_does_not_change_policy():
    """PF-ENV-2 is REPORT ONLY: it never modifies session policy, and with an
    explicit non-baseline env it flags the G9 gap (required when env is real)."""
    report = run_preflight(
        env={"dsh_version": "0.1.1-rc.2", "os": "x", "python_version": "3",
             "sandbox_mode": "danger-full-access",
             "approval_policy": "never",
             "permission_preset": "p", "utc_offset_seconds": 0, "seed": 1},
        orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-ENV-2")
    assert c.passed is False
    assert c.required is True
    assert "session policy is out of scope, not modified" in c.detail
    assert "workspace-write" in c.detail and "ask" in c.detail


def test_preflight_env_fields_complete():
    """PF-ENV-3: a missing env field is flagged (LV4)."""
    report = run_preflight(
        env={"dsh_version": "0.1.1-rc.2", "seed": 1},
        orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-ENV-3")
    assert c.passed is False


def test_preflight_env_absent_is_non_blocking():
    """Without an env snapshot the environment checks pass (report-only)."""
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    for cid in ("PF-ENV-1", "PF-ENV-2", "PF-ENV-3"):
        c = next(c for c in report.checks if c.check_id == cid)
        assert c.passed is True


# ---------------------------------------------------------------------------
# Human-signed plan prerequisites
# ---------------------------------------------------------------------------
def test_preflight_plan_missing_is_required_failure():
    report = run_preflight(scenario_id="L3-NOPE-999",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-1")
    assert c.passed is False
    assert c.required is True
    assert report.all_required_pass is False


def test_preflight_plan_schema_valid_real_fixture():
    """The committed L3-TEST-001 plan is schema-valid."""
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-2")
    assert c.passed is True
    assert c.detail.startswith("expected_verdict=ALLOW")


def test_preflight_plan_missing_field_fails():
    plan = _load_plan("L3-TEST-001")
    del plan["expected_verdict"]
    report = run_preflight(plan=plan, orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-2")
    assert c.passed is False
    assert "expected_verdict" in c.detail


def test_preflight_plan_bad_verdict_enum_fails():
    plan = _load_plan("L3-TEST-001")
    plan["expected_verdict"] = "MAYBE"
    report = run_preflight(plan=plan, orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-2")
    assert c.passed is False


def test_preflight_plan_signoff_precedes_runtime():
    """PF-PLAN-3: signoff must precede the runtime verdict (LV7/IO-7)."""
    report = run_preflight(
        plan=_load_plan("L3-TEST-001"),
        runtime_captured_at="2026-08-31T10:00:00Z",
        orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-3")
    assert c.passed is True  # 00:00 < 10:00


def test_preflight_plan_signoff_after_runtime_fails():
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_ts"] = "2026-08-31T11:00:00Z"
    report = run_preflight(
        plan=plan, runtime_captured_at="2026-08-31T10:00:00Z",
        orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-3")
    assert c.passed is False


def test_preflight_plan_o4_expected_verdict():
    """PF-PLAN-4: expected verdict declared + O4 Human-signed oracle used."""
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-4")
    assert c.passed is True


# ---------------------------------------------------------------------------
# Reproducibility requirements
# ---------------------------------------------------------------------------
def test_preflight_fixture_hash_deterministic_real():
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-REP-1")
    assert c.passed is True
    assert c.detail.startswith("fixture=")


def test_preflight_replay_script_present():
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-REP-2")
    assert c.passed is True
    assert "replay.sh" in c.detail


def test_preflight_schema_and_verifier_sha():
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-REP-3")
    assert c.passed is True
    assert "l3-plan.schema.json" in c.detail


def test_preflight_no_live_network():
    report = run_preflight(orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-REP-4")
    assert c.passed is True


# ---------------------------------------------------------------------------
# End-to-end: real fixture + CLI exit codes
# ---------------------------------------------------------------------------
def test_preflight_end_to_end_rehearsal_ready():
    """A rehearsal run on the real L3-TEST-001 fixture passes all required
    checks; l3_claim_possible reflects honest UID separation."""
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999,
                           orchestrator_uid=os.getuid())
    assert report.all_required_pass is True
    c = next(c for c in report.checks if c.check_id == "PF-UID-2")
    if os.getuid() == _probe_subprocess_uid():
        assert report.l3_claim_possible is False  # honest demote on same-UID host
    else:
        assert report.l3_claim_possible is True
    # No scenario may be run by the preflight: only detection.
    assert report.to_dict()["scenario_id"] == "L3-TEST-001"


def test_preflight_cli_exit_code_required_failure(tmp_path):
    from tests.l3_runner.preflight import main
    bad_plan = tmp_path / "bad" / "plan.json"
    # A missing plan is a required failure => exit 2.
    rc = main(["--scenario", "L3-NOPE-999", "--fixtures-root",
               str(tmp_path), "--json"])
    assert rc == 2


def test_preflight_cli_exit_code_ok_rehearsal():
    from tests.l3_runner.preflight import main
    # A real scenario with a Human-signed plan passes all required checks
    # (rehearsal machinery OK) => exit 0 and a JSON report is emitted.
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--scenario", "L3-TEST-001", "--fixtures-root",
                   FIXTURES_ROOT, "--json"])
    out = buf.getvalue()
    assert rc == 0
    data = json.loads(out)
    assert data["scenario_id"] == "L3-TEST-001"
    assert "checks" in data

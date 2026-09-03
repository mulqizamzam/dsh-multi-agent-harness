"""Phase 5 / Session D — FINAL LIVE-ASSURANCE COORDINATOR tests.

These tests lock the coordinator's honest-BLOCKED behavior: when required
prerequisites are missing, the live-assurance report must report BLOCKED,
must not fabricate runtime evidence, must not claim G13 immunity, and must
not claim L3.

They run the actual probes:
  - G13: tests.g13.live_readiness.plan.precondition()
  - L3:  tests.l3_runner.environment.readiness.assess_environment()

Write-only scope: tests/phase-5/final/live-assurance/ + docs/phase-5/final/
live-assurance/. Nothing else is modified; no live dispatch, no DSH/policy
change, no signature invented, no claim made.
"""

import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

ORCHESTRATOR_UID = os.getuid()


def _g13_precondition():
    from tests.g13.live_readiness.plan import precondition
    return precondition()


def _l3_readiness():
    from tests.l3_runner.environment.readiness import assess_environment
    return assess_environment(
        scenario_id="L3-TEST-001", orchestrator_uid=ORCHESTRATOR_UID)


class TestCoordinatorG13Gate:
    """G13 live execution must stay BLOCKED until a REAL DSH child exists."""

    def test_precondition_is_honest(self):
        p = _g13_precondition()
        assert "marker_set" in p
        assert "instances_mounted" in p
        assert "backend_kind" in p
        assert p["satisfied"] == p["real_dsh_child_observable"]

    def test_live_g13_blocked_when_child_not_observable(self):
        p = _g13_precondition()
        if not p["satisfied"]:
            # BLOCKED is the honest outcome; no live dispatch may occur.
            assert p["marker_set"] is False or not p["all_instances_mounted"] \
                or p["backend_kind"] != "real-dsh"

    def test_no_immunity_claim_in_prepared_plan(self):
        from tests.g13.live_readiness.plan import live_test_plan
        plan = live_test_plan()
        text = (plan["title"] + " " + plan["status"]).lower()
        for banned in ("immune", "prompt-injection-proof", "injection-proof"):
            assert banned not in text

    def test_payload_fixture_counts(self):
        from tests.g13.live_readiness.payloads import LIVE_CHANNELS, LIVE_VECTORS
        assert len(LIVE_CHANNELS) == 7
        assert len(LIVE_VECTORS) == 56


class TestCoordinatorL3Gate:
    """The L3 claim gate must remain false on current facts."""

    def test_l3_claim_possible_false_without_uid_separation(self):
        r = _l3_readiness()
        uid2 = next((c for c in r.checks if c.check_id == "L3ENV-UID-2"),
                    None)
        assert uid2 is not None and uid2.passed is False
        assert r.l3_claim_possible is False

    def test_l3_rehearsal_ready(self):
        r = _l3_readiness()
        assert r.rehearsal_ready is True
        assert r.all_required_pass is True

    def test_l3_live_bridge_blocker(self):
        r = _l3_readiness()
        d4d7 = next((c for c in r.checks if c.check_id == "L3ENV-D4D7-3"),
                    None)
        assert d4d7 is not None and d4d7.passed is False

    def test_l3_real_signoff_blocker(self):
        r = _l3_readiness()
        real = next((c for c in r.checks if c.check_id == "L3ENV-PLAN-REAL"),
                    None)
        assert real is not None and real.passed is False

    def test_claim_gate_returns_false_on_current_facts(self):
        from tests.l3_runner.claim_gate import evaluate_l3_claim
        res = evaluate_l3_claim(
            bundle_dir="", runtime_decision="DENY", reference_decision="DENY",
            rehearsal=False,
            verifier_pid=1001, orchestrator_pid=2,
            verifier_uid=1000, orchestrator_uid=1000,
            independence_all_pass=False,
            oracle_classes=["O1", "O3", "O4"],
            fixture_hash="sha256:" + "0" * 64,
            verifier_binary_sha256="0" * 64,
            schema_sha256={"l3-plan.schema.json": "0" * 64},
            plan_signoff_ts="2026-08-31T00:00:00Z",
            runtime_captured_at="2026-08-31T00:00:01Z",
            unresolved_unknowns=[],
        )
        # Same-UID host + no independence + no bundle => never a claim.
        assert res.l3_claim is False

    def test_audit_l3_not_created_by_probes(self):
        """The probes/report must never create the repo audit/l3 store."""
        audit_l3 = os.path.join(PROJECT_ROOT, "audit", "l3")
        assert not os.path.exists(audit_l3)


class TestCoordinatorScope:
    """Write-scope lock: the coordinator writes only to its two paths."""

    def test_report_exists_in_write_scope(self):
        report = os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "final", "live-assurance",
            "0001-live-assurance-coordinator-report.md")
        assert os.path.isfile(report)
        with open(report) as f:
            text = f.read()
        assert "BLOCKED" in text
        assert "NO CLAIM" in text.upper() or "NO L3 CLAIM" in text.upper()

    def test_report_declares_no_claim(self):
        report = os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "final", "live-assurance",
            "0001-live-assurance-coordinator-report.md")
        with open(report) as f:
            text = f.read()
        assert "l3_claim_possible=False" in text or "NO CLAIM" in text.upper()
        assert "ZERO CONTROLS L3" in text.upper()


class TestCoordinatorRuntimeDriverRefuses:
    """The live runtime driver must refuse live dispatch, never simulate."""

    def test_live_driver_returns_blocked(self):
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        driver = LiveDSHRuntimeDriver()
        # The execute() signature is execute(scenario_id, action, target, **kwargs).
        result = driver.execute(
            scenario_id="L3-TEST-001", action="probe", target="probe")
        assert result.final_status == "BLOCKED"
        assert result.decision in ("ERROR", "DENY")
        # Either a named missing precondition or a live-execution
        # authorization refusal — never a simulated ALLOW.
        assert result.denial_path.startswith(
            "live-precondition:") or result.denial_path == \
            "live-execution-not-authorized"
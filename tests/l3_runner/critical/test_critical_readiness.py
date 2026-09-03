# tests/l3_runner/critical/test_critical_readiness.py — Critical-control L3 readiness tests
#
# Phase 5 / Session C — L3 Critical Control Readiness.
#
# Validates the 8 critical-control L3 scenario bundles under
# tests/l3_reference/critical/fixtures/ and drives them through the rehearsal
# machinery to prove P1..P4 readiness. NEVER claims L3 — rehearsal bundles
# force l3_claim=false and fail LV10 by design.

from __future__ import annotations

import json
import os
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.critical.runner import (  # noqa: E402
    CRITICAL_SCENARIOS, critical_fixtures_root, run_critical_rehearsal,
)
from tests.l3_runner.replay import fixture_hash  # noqa: E402
from tests.l3_runner.rehearsal import run_rehearsal  # noqa: E402

CRIT_FIXTURES_ROOT = critical_fixtures_root()


def _rehearse(scenario_id, tmp_path, seed=42, orch_uid=None):
    return run_rehearsal(
        scenario_id,
        fixtures_root=CRIT_FIXTURES_ROOT,
        scratch_base=str(tmp_path / "auditroot"),
        seed=seed,
        orchestrator_pid=99999,
        orchestrator_uid=orch_uid if orch_uid is not None else os.getuid(),
        orchestrator_session=f"session-{scenario_id}",
        parent_session="session-ext",
        verifier_mode="subprocess",
    )


def _scenario_ids():
    return [sid for _, (sid, _, _, _) in CRITICAL_SCENARIOS.items()]


# ---------------------------------------------------------------------------
# Fixture existence
# ---------------------------------------------------------------------------
class TestCriticalFixtureExistence:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_plan_json_exists(self, scenario_id):
        path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "plan.json")
        assert os.path.isfile(path), f"missing plan.json for {scenario_id}"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_fixture_json_exists(self, scenario_id):
        path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "fixture.json")
        assert os.path.isfile(path), f"missing fixture.json for {scenario_id}"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_runtime_recorded_exists(self, scenario_id):
        path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "runtime-recorded.json")
        assert os.path.isfile(path), f"missing runtime-recorded.json for {scenario_id}"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_plan_schema_valid(self, scenario_id):
        path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "plan.json")
        with open(path) as f:
            plan = json.load(f)
        for field in ("scenario_id", "actor", "action", "target", "preconditions",
                      "expected_verdict", "expected_verdict_reason",
                      "human_signoff_id", "human_signoff_ts"):
            assert field in plan, f"plan.json missing {field} for {scenario_id}"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_oracle_classes_at_least_two(self, scenario_id):
        path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "fixture.json")
        with open(path) as f:
            fixture = json.load(f)
        classes = set(fixture.get("oracle_classes_used", []))
        assert len(classes) >= 2, f"fixture {scenario_id} has <2 oracle classes: {classes}"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_plan_signoff_before_runtime(self, scenario_id):
        plan_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "plan.json")
        runtime_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "runtime-recorded.json")
        with open(plan_path) as f:
            plan = json.load(f)
        with open(runtime_path) as f:
            runtime = json.load(f)
        plan_ts = plan.get("human_signoff_ts", "")
        runtime_ts = runtime.get("captured_at", "")
        assert plan_ts < runtime_ts, (
            f"plan signoff {plan_ts} must precede runtime {runtime_ts} for {scenario_id}")


# ---------------------------------------------------------------------------
# Rehearsal: each critical scenario produces a complete bundle
# ---------------------------------------------------------------------------
class TestCriticalRehearsal:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_rehearsal_produces_complete_bundle(self, scenario_id, tmp_path):
        """Rehearsal produces a 13-file bundle under scratch."""
        summary = _rehearse(scenario_id, tmp_path)
        bundle_dir = summary["bundle_dir"]
        assert str(tmp_path) in bundle_dir, "bundle not under scratch"
        for fname in ("manifest.json", "env.json", "plan.json", "before.sha256",
                      "after.sha256", "runtime-verdict.json", "audit-log.jsonl",
                      "reference-verdict.json", "oracle-classes.json",
                      "provenance.json", "replay.json",
                      "verifier-independence.json", "verdict-match.json"):
            assert os.path.isfile(os.path.join(bundle_dir, fname)), (
                f"missing {fname} in {scenario_id} bundle")
        assert summary["rehearsal"] is True
        assert summary["mode"] == "replay"

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_rehearsal_l3_claim_false_lv10_by_design(self, scenario_id, tmp_path):
        """Rehearsal bundles are not L3: l3_claim=false, LV10 fails by design."""
        summary = _rehearse(scenario_id, tmp_path)
        assert summary["l3_claim"] is False
        assert summary["lv10_by_design"] is True

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_oracle_classes_recorded(self, scenario_id, tmp_path):
        """The rehearsal records >= 2 oracle classes."""
        summary = _rehearse(scenario_id, tmp_path)
        assert len(set(summary.get("oracle_classes_used", []))) >= 2

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_io1_pid_separate(self, scenario_id, tmp_path):
        """IO-1: verifier in a separate process (distinct PID)."""
        summary = _rehearse(scenario_id, tmp_path)
        assert summary["io1_pass"] is True

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_io2_uid_honest_fail_same_uid(self, scenario_id, tmp_path):
        """IO-2: on same-UID host, the check fails honestly (never faked)."""
        summary = _rehearse(scenario_id, tmp_path, orch_uid=os.getuid())
        assert summary["io2_pass"] is False
        assert summary["io2_honest_fail_on_same_uid"] is True

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_verdict_reference_agreement(self, scenario_id, tmp_path):
        """Runtime and reference verdicts agree (match=true; l3_claim=false)."""
        summary = _rehearse(scenario_id, tmp_path)
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
            match = json.load(f)
        assert match["match"] is True, (
            f"verdict mismatch for {scenario_id}: "
            f"runtime={match['runtime_decision']} ref={match['reference_decision']}")

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_replay_fixture_hash_deterministic(self, scenario_id, tmp_path):
        """P4: fixture hash is deterministic across rehearsals."""
        # Extract the fixture hash from the first rehearsal's bundle.
        s1 = _rehearse(scenario_id, tmp_path, seed=42)
        s2 = _rehearse(scenario_id, tmp_path, seed=7)
        expected = fixture_hash(os.path.join(CRIT_FIXTURES_ROOT, scenario_id))
        assert s1["fixture_hash"] == expected == s2["fixture_hash"]
        assert s1["fixture_hash"].startswith("sha256:")

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_replay_command_recorded(self, scenario_id, tmp_path):
        """E11 + verdict-match: replay command recorded in the bundle."""
        summary = _rehearse(scenario_id, tmp_path)
        assert "runner" in summary["replay_command"]
        assert summary["verdict_match_replay_command"]

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_io_checks_all_recorded(self, scenario_id, tmp_path):
        """IO-1..IO-10 recorded by the verifier process."""
        bundle_dir = _rehearse(scenario_id, tmp_path)["bundle_dir"]
        with open(os.path.join(bundle_dir, "verifier-independence.json")) as f:
            ind = json.load(f)
        assert set(ind["io_checks"]) == {f"IO-{i}" for i in range(1, 11)}
        assert ind["verifier_pid"] > 0 and ind["orchestrator_pid"] > 0
        assert ind["verifier_pid"] != ind["orchestrator_pid"]
        assert ind["verifier_session_id"].startswith("verifier-")


# ---------------------------------------------------------------------------
# Audit-integrity scenario: the independent audit_chain oracle detects tamper
# ---------------------------------------------------------------------------
class TestAuditIntegrityCritical:
    def test_audit_chain_oracle_detects_tamper(self):
        """The audit_chain O1 oracle independently detects the tampered ledger."""
        from tests.l3_reference.audit_chain import verify_ledger
        log_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002", "ledger.jsonl")
        sidecar_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002", "ledger.chain")
        assert os.path.isfile(log_path), "tampered ledger missing"
        assert os.path.isfile(sidecar_path), "sidecar chain missing"
        verdict = verify_ledger(log_path, sidecar_path=sidecar_path)
        assert verdict.decision == "INVALID", f"expected INVALID, got {verdict.decision}"
        assert "chain length mismatch" in verdict.reason or "mismatch" in verdict.reason

    def test_audit_chain_original_passes(self):
        """The ORIGINAL (untampered) ledger passes the chain check."""
        from tests.l3_reference.audit_chain import verify_ledger
        orig_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002", "ledger.original.jsonl")
        sidecar_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002", "ledger.chain")
        verdict = verify_ledger(orig_path, sidecar_path=sidecar_path)
        assert verdict.decision == "VALID", f"expected VALID for original, got {verdict.decision}"

    def test_audit_integrity_rehearsal_matches(self, tmp_path):
        """The L3-AUD-002 rehearsal produces a bundle where runtime and oracle
        agree on INVALID."""
        summary = _rehearse("L3-AUD-002", tmp_path)
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
            match = json.load(f)
        assert match["match"] is True, (
            f"audit integrity verdict mismatch: "
            f"runtime={match['runtime_decision']} ref={match['reference_decision']}")
        assert match["runtime_decision"] == "INVALID"
        assert match["reference_decision"] == "INVALID"


# ---------------------------------------------------------------------------
# Cross-cutting: no L3 claim, no repo audit/l3 writes
# ---------------------------------------------------------------------------
class TestCriticalCrossCutting:
    def test_rehearsal_never_claims_l3(self, tmp_path):
        """No critical scenario rehearsal claims L3."""
        for sid in _scenario_ids():
            summary = _rehearse(sid, tmp_path)
            assert summary["l3_claim"] is False, f"{sid} claimed L3"

    def test_never_touches_repo_audit_l3(self, tmp_path):
        """All critical rehearsals write under scratch, never repo audit/l3/."""
        for sid in _scenario_ids():
            _rehearse(sid, tmp_path)
            assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3", sid))

    def test_reference_oracles_do_not_import_production(self):
        """The critical fixture oracles use the existing O1 modules which are
        proven to not import production control (AST-scanned in the existing
        test_l3_infrastructure suite). This test asserts the gate_under_test
        values map to valid registered oracle modules."""
        from tests.l3_runner import ORACLE_MODULES
        for _, (_, gate, _, _) in CRITICAL_SCENARIOS.items():
            assert gate in ORACLE_MODULES, (
                f"critical gate {gate!r} not in ORACLE_MODULES")
            mod_name = ORACLE_MODULES[gate]
            assert mod_name.startswith("tests.l3_reference"), (
                f"oracle {mod_name} not in tests.l3_reference (production import risk)")

    def test_all_critical_controls_covered(self, tmp_path):
        """All 6 critical controls have at least one rehearsal that passes
        P1+P3+P4 and produces a match=true bundle."""
        covered = set()
        for sid in _scenario_ids():
            summary = _rehearse(sid, tmp_path)
            if summary["l3_claim"] is False and summary["lv10_by_design"] is True:
                bundle_dir = summary["bundle_dir"]
                with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
                    match = json.load(f)
                if match["match"] is True:
                    covered.add(sid)
        # Each critical control is covered by at least one scenario.
        expected = set(_scenario_ids())
        missing = expected - covered
        assert not missing, f"critical scenarios missing matching rehearsal: {missing}"
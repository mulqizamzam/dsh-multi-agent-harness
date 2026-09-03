"""Session C (Final Security) — L3 Critical-Control FINAL readiness tests.

Deterministic tests that pin the EXACT remaining gap between the current
rehearsal-ready machinery and a legitimate L3 claim, per
docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md.

What these tests prove (all observed, none simulated):

  P1  Live runtime      — LiveDSHRuntimeDriver REFUSES live dispatch (BLOCKED
                          or NotImplementedError); the recorded/runtime
                          driver is replay-only. P1-live is NOT met.
  P2  Independent obs.  — IO-1 (distinct PID) passes via subprocess; IO-2
                          (distinct UID) FAILS HONESTLY on this same-UID host
                          (uid=1000). l3_claim_possible=False, never faked.
  P3  External oracle   — every critical bundle declares >= 2 oracle classes
                          (O1 + O3/O2 + O4), enforced by the runner.
  P4  Reproducible      — fixture hash deterministic, replay command recorded,
                          verifier/schema sha256 pinned in replay.json.

Check items (session brief):
  separate PID  -> pass (IO-1)
  separate UID  -> FAIL honestly (IO-2) — the load-bearing L3 blocker
  verifier independence -> clean imports, subprocess spawn, never session tree
  Human-signed pre-runtime plan -> MECHANISM ready; REAL signoff ABSENT
                                   (fixtures are inert templates — never
                                   invented)
  evidence bundle -> 13-file complete under scratch, never repo audit/l3/
  audit chain    -> tampered ledger INVALID, original VALID (independent oracle)
  state hashes   -> before.sha256 / after.sha256 present (IO-9)
  replay         -> deterministic fixture hash + recorded command (P4)
  verdict agreement -> match=true for all 8 critical scenarios

NO test here claims L3. The claim gate is exercised with the CURRENT
environment facts and must return l3_claim=False. The LV16 shape note
(recovery/state_transition/audit_integrity oracles now emit the canonical
`checklist_item_results` field, preserving the existing per-check diagnostic
data — resolved at the oracle layer in this session).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.critical.runner import (  # noqa: E402
    CRITICAL_SCENARIOS, critical_fixtures_root, run_critical_rehearsal,
)
from tests.l3_runner.replay import fixture_hash  # noqa: E402
from tests.l3_runner.claim_gate import evaluate_l3_claim  # noqa: E402

CRIT_FIXTURES_ROOT = critical_fixtures_root()


def _scenario_ids():
    return [sid for _, (sid, _, _, _) in CRITICAL_SCENARIOS.items()]


def _rehearse(scenario_id, tmp_path, seed=42, orch_uid=None):
    """Rehearse one critical scenario under a THROWAWAY scratch base."""
    return run_critical_rehearsal(
        scenario_id,
        fixtures_root=CRIT_FIXTURES_ROOT,
        scratch_base=str(tmp_path / "auditroot"),
        seed=seed,
        orchestrator_pid=99999,
        orchestrator_uid=orch_uid if orch_uid is not None else os.getuid(),
        orchestrator_session=f"session-final-{scenario_id}",
        parent_session="session-external",
        verifier_mode="subprocess",
    )


# ============================================================================
# P1 — Live runtime is NOT available (the claim gap, verified honestly)
# ============================================================================

class TestP1LiveRuntimeNotMet:
    def test_live_driver_refuses_dispatch(self):
        """LiveDSHRuntimeDriver must NOT simulate a live run: it returns
        BLOCKED naming missing preconditions (or refuses outright)."""
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        driver = LiveDSHRuntimeDriver()
        result = driver.execute("L3-AUTH-001", "code_write", "agents/x.txt")
        assert result.final_status == "BLOCKED", (
            f"live driver must not simulate a run; got {result.final_status}")
        assert "live-precondition" in result.denial_path or \
            "live-execution-not-authorized" in result.denial_path

    def test_live_bridge_marker_unset(self):
        """DSH_LIVE_BRIDGE_ACTIVE is unset -> live DSH unavailable (P1)."""
        assert os.environ.get("DSH_LIVE_BRIDGE_ACTIVE") != "1", (
            "if the bridge marker is set this test must be re-derived")

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_rehearsal_is_replay_not_live(self, scenario_id, tmp_path):
        """The rehearsal path is replay-only (RecordedRuntimeDriver), never a
        live DSH session — P1-live remains unmet for every scenario."""
        summary = _rehearse(scenario_id, tmp_path)
        assert summary["mode"] == "replay"


# ============================================================================
# P2 — Independent observer: separate PID yes, separate UID no (honest)
# ============================================================================

class TestP2IndependentObserver:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_io1_distinct_pid(self, scenario_id, tmp_path):
        """IO-1: verifier runs in a separate OS process (distinct PID)."""
        summary = _rehearse(scenario_id, tmp_path)
        assert summary["io1_pass"] is True

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_io2_distinct_uid_fails_honestly(self, scenario_id, tmp_path):
        """IO-2: on this same-UID host the check FAILS honestly and reports
        l3_claim_possible=False — never faked."""
        summary = _rehearse(scenario_id, tmp_path, orch_uid=os.getuid())
        assert summary["io2_pass"] is False
        assert summary["io2_honest_fail_on_same_uid"] is True

    def test_same_uid_host_fact(self):
        """The host runs everything under one UID (verified live)."""
        probe = subprocess.run(
            [sys.executable, "-c", "import os; print(os.getuid())"],
            capture_output=True, text=True)
        sub_uid = int(probe.stdout.strip())
        assert sub_uid == os.getuid()
        assert os.getuid() == 1000  # current host fact

    def test_verifier_not_in_session_tree(self, tmp_path):
        """IO-4: the verifier is spawned via subprocess, never via DSH
        subagent tools (recorded in verifier-independence.json)."""
        bundle_dir = _rehearse("L3-AUTH-001", tmp_path)["bundle_dir"]
        with open(os.path.join(bundle_dir, "verifier-independence.json")) as f:
            ind = json.load(f)
        io4 = ind["io_checks"].get("IO-4", {})
        assert io4.get("pass") is True
        assert ind["verifier_session_id"].startswith("verifier-")
        assert ind["parent_session_id"] != ind["verifier_session_id"]

    def test_verifier_clean_imports(self):
        """P2/PF-VER: the verifier refuses production-gate imports.

        Probed in a FRESH subprocess (the verifier's own environment), not
        in-process: the shared pytest process legitimately imports production
        modules (e.g. control.execution_gate from other suites), which would
        otherwise make an in-process guard look polluted. The verifier runs
        standalone, so its clean-import guard must pass in its own process.
        """
        proc = subprocess.run(
            [sys.executable, "-c",
             "from tests.l3_runner.verifier import assert_clean_imports; "
             "assert_clean_imports(); print('CLEAN')"],
            capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT)
        assert proc.returncode == 0, (
            f"verifier clean-import guard failed: {proc.stderr.strip()}")
        assert "CLEAN" in proc.stdout


# ============================================================================
# P3 — Independent oracle classes (>= 2 per scenario)
# ============================================================================

class TestP3IndependentOracles:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_at_least_two_oracle_classes(self, scenario_id, tmp_path):
        """R6/IO-6: every critical bundle declares and records >= 2 classes."""
        summary = _rehearse(scenario_id, tmp_path)
        assert len(set(summary.get("oracle_classes_used", []))) >= 2
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "oracle-classes.json")) as f:
            classes = json.load(f)
        assert len(set(classes.get("oracle_classes_used", []))) >= 2

    def test_oracles_are_reference_modules(self):
        """The O1 oracles are the independent tests/l3_reference modules (not
        production gates)."""
        from tests.l3_runner import ORACLE_MODULES
        for _, (_, gate, _, _) in CRITICAL_SCENARIOS.items():
            assert gate in ORACLE_MODULES
            assert ORACLE_MODULES[gate].startswith("tests.l3_reference")


# ============================================================================
# P4 — Reproducible replay
# ============================================================================

class TestP4ReproducibleReplay:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_fixture_hash_deterministic(self, scenario_id, tmp_path):
        """P4/PF-REP-1: the fixture hash is stable across seeds and matches a
        direct recomputation."""
        s1 = _rehearse(scenario_id, tmp_path, seed=42)
        s2 = _rehearse(scenario_id, tmp_path, seed=7)
        expected = fixture_hash(os.path.join(CRIT_FIXTURES_ROOT, scenario_id))
        assert s1["fixture_hash"] == expected == s2["fixture_hash"]
        assert s1["fixture_hash"].startswith("sha256:")

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_replay_metadata_pinned(self, scenario_id, tmp_path):
        """replay.json (E11) records the fixture hash, replay command,
        verifier binary sha256, and schema sha256."""
        bundle_dir = _rehearse(scenario_id, tmp_path)["bundle_dir"]
        with open(os.path.join(bundle_dir, "replay.json")) as f:
            rep = json.load(f)
        assert rep["fixture_hash"].startswith("sha256:")
        assert "command_line" in rep
        assert len(rep.get("verifier_binary_sha256", "")) == 64
        assert isinstance(rep.get("schema_sha256"), dict)
        assert len(rep["schema_sha256"]) >= 1


# ============================================================================
# Human-signed plan: mechanism ready, REAL signoff absent (never invented)
# ============================================================================

class TestHumanSignedPlan:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_plan_signoff_precedes_runtime(self, scenario_id):
        """LV7/IO-7: the fixture plan's signoff timestamp precedes the recorded
        runtime capture (ordering holds)."""
        plan_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "plan.json")
        runtime_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id,
                                    "runtime-recorded.json")
        with open(plan_path) as f:
            plan = json.load(f)
        with open(runtime_path) as f:
            runtime = json.load(f)
        assert plan["human_signoff_ts"] < runtime["captured_at"]

    def test_plan_signoff_fields_schema_valid(self):
        """G7/PF-PLAN-5: the signoff fields match the schema (id pattern,
        timestamp format, method enum) — the MECHANISM is ready."""
        from tests.l3_runner.plan_signing import validate_signed_plan
        plan_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUTH-001", "plan.json")
        with open(plan_path) as f:
            plan = json.load(f)
        verdict = validate_signed_plan(plan)
        assert verdict.valid is True, f"signoff fields invalid: {verdict.reason}"

    def test_no_real_human_signoff_observed(self):
        """HONESTY: the committed plans are inert fixtures — a real Human
        signoff has NOT been observed; none is invented here."""
        plan_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUTH-001", "plan.json")
        with open(plan_path) as f:
            plan = json.load(f)
        sid = plan.get("human_signoff_id", "")
        # Fixture ids use the human-YYYY-MM-DD-NNN template; a REAL signoff
        # requires durable Human identity + method + timestamp. The probe
        # never fabricates one: the environment report must say so.
        assert sid.startswith("human-")
        # The environment probe must report the real-signoff check as failed.
        from tests.l3_runner.environment.readiness import assess_environment
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=CRIT_FIXTURES_ROOT,
            orchestrator_uid=os.getuid(),
        )
        plan_check = [c for c in report.checks
                      if c.check_id == "L3ENV-PLAN-REAL"]
        assert plan_check and plan_check[0].passed is False, (
            "L3ENV-PLAN-REAL must report no real Human signoff")


# ============================================================================
# Evidence bundle, audit chain, state hashes, verdict agreement
# ============================================================================

class TestEvidenceBundle:
    BUNDLE_FILES = (
        "manifest.json", "env.json", "plan.json", "before.sha256",
        "after.sha256", "runtime-verdict.json", "audit-log.jsonl",
        "reference-verdict.json", "oracle-classes.json", "provenance.json",
        "replay.json", "verifier-independence.json", "verdict-match.json",
    )

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_bundle_complete_under_scratch(self, scenario_id, tmp_path):
        """Rehearsal produces the full 13-file bundle under scratch — never
        the repo audit/l3/."""
        summary = _rehearse(scenario_id, tmp_path)
        bundle_dir = summary["bundle_dir"]
        assert str(tmp_path) in bundle_dir
        for fname in self.BUNDLE_FILES:
            assert os.path.isfile(os.path.join(bundle_dir, fname)), (
                f"missing {fname} in {scenario_id} bundle")
        assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3",
                                               scenario_id))

    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_state_hashes_present(self, scenario_id, tmp_path):
        """E4/E5 (IO-9): before.sha256 and after.sha256 are recorded with a
        sha256 root hash (64 hex chars)."""
        import re as _re
        bundle_dir = _rehearse(scenario_id, tmp_path)["bundle_dir"]
        for h in ("before.sha256", "after.sha256"):
            with open(os.path.join(bundle_dir, h)) as f:
                hashes = json.load(f)
            assert hashes.get("algorithm") == "sha256"
            assert _re.fullmatch(r"[0-9a-f]{64}", hashes.get("root_hash", "")), (
                f"root_hash not a 64-hex sha256: {hashes.get('root_hash')!r}")


class TestAuditChain:
    def test_tampered_ledger_invalid(self):
        """The independent audit_chain oracle flags the tampered ledger."""
        from tests.l3_reference.audit_chain import verify_ledger
        root = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002")
        v = verify_ledger(os.path.join(root, "ledger.jsonl"),
                          sidecar_path=os.path.join(root, "ledger.chain"))
        assert v.decision == "INVALID"

    def test_original_ledger_valid(self):
        from tests.l3_reference.audit_chain import verify_ledger
        root = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002")
        v = verify_ledger(os.path.join(root, "ledger.original.jsonl"),
                          sidecar_path=os.path.join(root, "ledger.chain"))
        assert v.decision == "VALID"


class TestVerdictAgreement:
    @pytest.mark.parametrize("scenario_id", _scenario_ids())
    def test_runtime_reference_agree(self, scenario_id, tmp_path):
        """For all 8 critical scenarios the runtime verdict agrees with the
        independent reference oracle (match=true)."""
        summary = _rehearse(scenario_id, tmp_path)
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
            match = json.load(f)
        assert match["match"] is True, (
            f"verdict mismatch {scenario_id}: "
            f"runtime={match['runtime_decision']} "
            f"ref={match['reference_decision']}")


# ============================================================================
# Claim gate status: with current environment facts, l3_claim=False
# ============================================================================

class TestClaimGateStatus:
    def test_claim_gate_returns_false_on_current_facts(self, tmp_path):
        """Feeding the claim gate the CURRENT same-UID facts must yield
        l3_claim=False — the claim is blocked by IO-2 (and rehearsal mode)."""
        summary = _rehearse("L3-AUTH-001", tmp_path)
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "runtime-verdict.json")) as f:
            rv = json.load(f)
        with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
            refv = json.load(f)
        with open(os.path.join(bundle_dir, "replay.json")) as f:
            rep = json.load(f)
        result = evaluate_l3_claim(
            bundle_dir=bundle_dir,
            runtime_decision=rv.get("decision"),
            reference_decision=refv.get("decision"),
            rehearsal=False,
            verifier_pid=99998, orchestrator_pid=99999,
            verifier_uid=os.getuid(), orchestrator_uid=os.getuid(),
            independence_all_pass=False,  # IO-2 fails honestly
            oracle_classes=["O1", "O3", "O4"],
            fixture_hash=rep.get("fixture_hash", ""),
            verifier_binary_sha256=rep.get("verifier_binary_sha256", ""),
            schema_sha256=rep.get("schema_sha256", {}),
            plan_signoff_ts="2026-08-31T09:00:00Z",
            runtime_captured_at="2026-08-31T10:00:00Z",
            unresolved_unknowns=[],
            uid_separation_required=True,
        )
        assert result.l3_claim is False
        assert any("uid" in f.lower() or "IO-2" in f
                   for f in result.failures), (
            f"claim must fail on UID separation; failures={result.failures}")

    def test_rehearsal_never_claims(self, tmp_path):
        """Rehearsal mode forces l3_claim=false by construction."""
        for sid in _scenario_ids():
            summary = _rehearse(sid, tmp_path)
            assert summary["l3_claim"] is False
            assert summary["lv10_by_design"] is True

    def test_l3_claim_possible_false_environment(self):
        """The environment probe honestly reports l3_claim_possible=False."""
        from tests.l3_runner.environment.readiness import assess_environment
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=CRIT_FIXTURES_ROOT,
            orchestrator_uid=os.getuid(),
        )
        assert report.l3_claim_possible is False
        assert report.rehearsal_ready is True

    def test_all_l3_blockers_named(self):
        """The environment probe names the exact independent L3 blockers.

        CORRECTED (approval-path correction): with the honest composition-based
        answerer detection the approval answerer IS available in a web GUI
        session, so L3ENV-ANS-1/ANS-2 are correctly NOT blockers anymore (the
        obsolete DSH_APPROVAL_PROMPTS_DISABLED convention no longer falsely
        reports the answerer absent). The genuine independent blockers are
        UID-2, D4D7-3, PLAN-REAL.
        """
        from tests.l3_runner.environment.readiness import assess_environment
        report = assess_environment(
            scenario_id="L3-AUTH-001",
            fixtures_root=CRIT_FIXTURES_ROOT,
            orchestrator_uid=os.getuid(),
        )
        blocked_ids = {b.split(":")[0] for b in report.blocked}
        for expected in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
            assert expected in blocked_ids, (
                f"blocker {expected} missing: {sorted(blocked_ids)}")
        # The answerer is available by composition in a web GUI session; it is
        # NOT a blocker anymore (honest correction, never a false-negative).
        assert "L3ENV-ANS-1" not in blocked_ids, (
            f"answerer must not falsely block L3: {sorted(blocked_ids)}")
        assert "L3ENV-ANS-2" not in blocked_ids, (
            f"answerer path must not falsely block L3: {sorted(blocked_ids)}")


# ============================================================================
# LV16 shape — canonical reference-verdict contract (resolved at the oracle layer)
# ============================================================================

class TestLv16ShapeNote:
    def test_lv16_shape_resolved_three_oracles_emit_checklist(self, tmp_path):
        """The structure validator (LV16) requires `checklist_item_results` in
        reference-verdict.json. The recovery, state_transition, and
        audit_integrity oracles NOW emit it (canonical key), preserving the
        per-check diagnostic data that previously lived under `detail` — so
        L3-REC-004 / L3-ST-003 / L3-AUD-002 no longer record an LV16 error."""
        for sid in ("L3-REC-004", "L3-ST-003", "L3-AUD-002"):
            summary = _rehearse(sid, tmp_path)
            lv16 = [e for e in summary.get("validation_errors", [])
                    if "LV16" in e]
            # The mismatch is RESOLVED: no LV16 error may remain for these
            # three scenarios.
            assert lv16 == [], f"{sid} still records LV16 errors: {lv16}"
            bundle_dir = summary["bundle_dir"]
            with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
                refv = json.load(f)
            assert "checklist_item_results" in refv, sid
            assert refv["checklist_item_results"], (
                f"{sid} checklist_item_results must carry per-check data")
            # The old non-canonical key must be gone (canonical contract).
            assert "detail" not in refv, sid

    def test_authority_and_path_oracles_emit_checklist(self, tmp_path):
        """The authority and execution-gate oracles DO emit
        checklist_item_results (so AUTH/PATH bundles pass LV16)."""
        for sid in ("L3-AUTH-001", "L3-PATH-001"):
            bundle_dir = _rehearse(sid, tmp_path)["bundle_dir"]
            with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
                refv = json.load(f)
            assert "checklist_item_results" in refv, sid

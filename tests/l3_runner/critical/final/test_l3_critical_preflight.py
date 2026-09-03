"""Phase 5 / Final Preflight — L3 Critical-Control FINAL PREFLIGHT lock tests.

Deterministic tests that lock the final preflight package
(docs/phase-5/l3/final/0002-l3-critical-preflight-package.md) against the
machinery it references, per the session brief:

  Prepare/validate: authority, execution-time recheck, protected path, recovery
  privilege bounding, stale state, audit integrity.
  Check: P1/P2/P3/P4, separate UID, Human-signed plan, evidence bundle, replay,
  verdict agreement.

What these tests prove (all observed, none simulated):

  1. The preflight package doc exists in the write-only dir and carries the
     six required sections (coverage matrix / P1..P4 / plan / bundle / replay /
     verdict agreement / claim gate) plus the LV16 resolution note.
  2. The six critical controls are covered by the scenario registry (8 bundles,
     exact ids, gates, expected verdicts, oracle classes >= 2).
  3. P1 live runtime is NOT met: LiveDSHRuntimeDriver refuses dispatch, the
     bridge marker is unset, and every rehearsal runs replay-only.
  4. P2 independent observer: IO-1 (distinct PID) passes; IO-2 (distinct UID)
     FAILS HONESTLY on this same-UID host (uid=1000) -> l3_claim_possible=False,
     never faked. IO-4 + clean imports pass.
  5. P3 >= 2 oracle classes per scenario, O1 oracles are tests/l3_reference
     modules.
  6. P4 reproducible replay: deterministic fixture hash, replay command +
     verifier/schema sha256 pinned in replay.json.
  7. Human-signed plan: signoff precedes runtime (LV7/IO-7), fields schema-valid,
     but NO real Human signoff is observed (L3ENV-PLAN-REAL fails honestly).
  8. Evidence bundle: complete 13-file bundle under scratch (never repo
     audit/l3/), state hashes (IO-9) present, audit chain tamper detected.
  9. Verdict agreement: runtime == reference for all 8 critical scenarios.
  10. LV16 evidence-contract is RESOLVED: the recovery/state_transition/
      audit_integrity oracles emit the canonical `checklist_item_results` field,
      so L3-REC-004 / L3-ST-003 / L3-AUD-002 pass LV16. No validator weakened.
  11. The claim gate returns l3_claim=False on current facts; rehearsal never
      claims.
  12. Package hygiene: the preflight doc and tests make NO L3 claim, invent NO
      signature, import NO production control-plane code.

NO test here executes a live dispatch, modifies DSH/session policy/presets,
invents a Human signature, or fabricates runtime evidence.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.critical.runner import (  # noqa: E402
    CRITICAL_CONTROLS, CRITICAL_SCENARIOS, critical_fixtures_root,
    run_critical_rehearsal,
)
from tests.l3_runner.replay import fixture_hash  # noqa: E402
from tests.l3_runner.claim_gate import evaluate_l3_claim  # noqa: E402

CRIT_FIXTURES_ROOT = critical_fixtures_root()
FINAL_DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "l3", "final",
                         "0002-l3-critical-preflight-package.md")


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
        orchestrator_session=f"session-preflight-{scenario_id}",
        parent_session="session-external",
        verifier_mode="subprocess",
    )


def _doc_text() -> str:
    with open(FINAL_DOC, "r", encoding="utf-8") as fh:
        return fh.read()


# ============================================================================
# 1. The preflight package doc exists and carries the required sections
# ============================================================================

def test_preflight_doc_exists_in_write_only_dir():
    assert os.path.isfile(FINAL_DOC), FINAL_DOC
    # The doc must live under docs/phase-5/l3/final/ (the allowed write root).
    assert os.path.dirname(FINAL_DOC).endswith(
        os.path.join("docs", "phase-5", "l3", "final"))


def test_preflight_doc_has_all_required_sections():
    text = _doc_text()
    for section in (
        "## 1. One-line status",
        "## 2. Critical-control coverage matrix",
        "## 3. Preflight check results (observed this session)",
        "## 4. Environment blockers (exact, observed this session)",
        "## 5. Claim gate status",
        "## 6. LV16 evidence-contract resolution",
        "## 7. Prohibited actions (binding)",
        "## 8. Honesty statement",
    ):
        assert section in text, section


def test_preflight_doc_marks_all_live_prereqs_blocked():
    text = _doc_text()
    assert "NOT-READY-TO-CLAIM" in text
    assert "NO L3 CLAIM" in text.upper()
    assert "No live L3 run" in text or "no live L3 run" in text
    assert "No signature invented" in text or "no signature invented" in text


# ============================================================================
# 2. Six critical controls covered by the registry (exact)
# ============================================================================

def test_six_critical_controls_in_registry():
    expected_controls = (
        "authority grant/revoke/expiry",
        "execution-time recheck",
        "protected-path execution",
        "recovery privilege bounding",
        "stale-state protection",
        "audit integrity",
    )
    assert CRITICAL_CONTROLS == expected_controls


def test_eight_scenarios_exact_ids_gates_expected():
    order = [sid for _, (sid, gate, verdict, _) in CRITICAL_SCENARIOS.items()]
    assert order == [
        "L3-AUTH-001", "L3-AUTH-003", "L3-AUTH-004", "L3-AUTH-006",
        "L3-PATH-001", "L3-REC-004", "L3-ST-003", "L3-AUD-002",
    ]
    gates = {sid: gate for _, (sid, gate, _, _) in CRITICAL_SCENARIOS.items()}
    assert gates == {
        "L3-AUTH-001": "authority", "L3-AUTH-003": "authority",
        "L3-AUTH-004": "authority", "L3-AUTH-006": "authority",
        "L3-PATH-001": "execution_gate", "L3-REC-004": "recovery",
        "L3-ST-003": "state_transition", "L3-AUD-002": "audit_integrity",
    }
    verdicts = {sid: v for _, (sid, _, v, _) in CRITICAL_SCENARIOS.items()}
    assert verdicts["L3-AUTH-001"] == "ALLOW"
    assert all(verdicts[s] == "DENY" for s in (
        "L3-AUTH-003", "L3-AUTH-004", "L3-AUTH-006",
        "L3-PATH-001", "L3-REC-004", "L3-ST-003"))
    assert verdicts["L3-AUD-002"] == "INVALID"


def test_every_scenario_declares_at_least_two_oracle_classes():
    for _, (sid, _, _, classes) in CRITICAL_SCENARIOS.items():
        assert len(set(classes)) >= 2, sid
        for c in classes:
            assert c in {"O1", "O2", "O3", "O4"}, f"{sid}: {c}"


def test_preflight_doc_covers_all_six_controls():
    text = _doc_text()
    norm = re.sub(r"\s+", " ", text)
    for control in CRITICAL_CONTROLS:
        assert control in norm, control
    for sid in _scenario_ids():
        assert sid in norm, sid


# ============================================================================
# 3. P1 — live runtime NOT met (the claim gap, verified honestly)
# ============================================================================

def test_live_driver_refuses_dispatch():
    from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
    driver = LiveDSHRuntimeDriver()
    result = driver.execute("L3-AUTH-001", "code_write", "agents/x.txt")
    assert result.final_status == "BLOCKED"
    assert "live-precondition" in result.denial_path or \
        "live-execution-not-authorized" in result.denial_path


def test_live_bridge_marker_unset():
    assert os.environ.get("DSH_LIVE_BRIDGE_ACTIVE") != "1"


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_rehearsal_is_replay_not_live(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path)
    assert summary["mode"] == "replay"
    assert summary["rehearsal"] is True


# ============================================================================
# 4. P2 — independent observer: separate PID yes, separate UID no (honest)
# ============================================================================

@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_io1_distinct_pid(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path)
    assert summary["io1_pass"] is True


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_io2_distinct_uid_fails_honestly(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path, orch_uid=os.getuid())
    assert summary["io2_pass"] is False
    assert summary["io2_honest_fail_on_same_uid"] is True


def test_same_uid_host_fact():
    probe = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getuid())"],
        capture_output=True, text=True)
    sub_uid = int(probe.stdout.strip())
    assert sub_uid == os.getuid()
    assert os.getuid() == 1000  # current host fact


def test_verifier_not_in_session_tree(tmp_path):
    bundle_dir = _rehearse("L3-AUTH-001", tmp_path)["bundle_dir"]
    with open(os.path.join(bundle_dir, "verifier-independence.json")) as f:
        ind = json.load(f)
    assert ind["io_checks"].get("IO-4", {}).get("pass") is True
    assert ind["verifier_session_id"].startswith("verifier-")
    assert ind["parent_session_id"] != ind["verifier_session_id"]


def test_verifier_clean_imports():
    proc = subprocess.run(
        [sys.executable, "-c",
         "from tests.l3_runner.verifier import assert_clean_imports; "
         "assert_clean_imports(); print('CLEAN')"],
        capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT)
    assert proc.returncode == 0, f"verifier clean-import guard failed: {proc.stderr.strip()}"
    assert "CLEAN" in proc.stdout


def test_l3_claim_possible_false_environment():
    from tests.l3_runner.environment.readiness import assess_environment
    report = assess_environment(
        scenario_id="L3-AUTH-001",
        fixtures_root=CRIT_FIXTURES_ROOT,
        orchestrator_uid=os.getuid(),
    )
    assert report.l3_claim_possible is False
    assert report.rehearsal_ready is True


# ============================================================================
# 5. P3 — independent oracle classes (>= 2 per scenario)
# ============================================================================

@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_at_least_two_oracle_classes(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path)
    assert len(set(summary.get("oracle_classes_used", []))) >= 2


def test_oracles_are_reference_modules():
    from tests.l3_runner import ORACLE_MODULES
    for _, (_, gate, _, _) in CRITICAL_SCENARIOS.items():
        assert gate in ORACLE_MODULES
        assert ORACLE_MODULES[gate].startswith("tests.l3_reference")


# ============================================================================
# 6. P4 — reproducible replay
# ============================================================================

@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_fixture_hash_deterministic(scenario_id, tmp_path):
    s1 = _rehearse(scenario_id, tmp_path, seed=42)
    s2 = _rehearse(scenario_id, tmp_path, seed=7)
    expected = fixture_hash(os.path.join(CRIT_FIXTURES_ROOT, scenario_id))
    assert s1["fixture_hash"] == expected == s2["fixture_hash"]
    assert s1["fixture_hash"].startswith("sha256:")


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_replay_metadata_pinned(scenario_id, tmp_path):
    bundle_dir = _rehearse(scenario_id, tmp_path)["bundle_dir"]
    with open(os.path.join(bundle_dir, "replay.json")) as f:
        rep = json.load(f)
    assert rep["fixture_hash"].startswith("sha256:")
    assert "command_line" in rep
    assert len(rep.get("verifier_binary_sha256", "")) == 64
    assert isinstance(rep.get("schema_sha256"), dict)
    assert len(rep["schema_sha256"]) >= 1


# ============================================================================
# 7. Human-signed plan: mechanism ready, REAL signoff absent (never invented)
# ============================================================================

@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_plan_signoff_precedes_runtime(scenario_id):
    plan_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id, "plan.json")
    runtime_path = os.path.join(CRIT_FIXTURES_ROOT, scenario_id,
                                "runtime-recorded.json")
    with open(plan_path) as f:
        plan = json.load(f)
    with open(runtime_path) as f:
        runtime = json.load(f)
    assert plan["human_signoff_ts"] < runtime["captured_at"]


def test_plan_signoff_fields_schema_valid():
    from tests.l3_runner.plan_signing import validate_signed_plan
    plan_path = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUTH-001", "plan.json")
    with open(plan_path) as f:
        plan = json.load(f)
    verdict = validate_signed_plan(plan)
    assert verdict.valid is True, f"signoff fields invalid: {verdict.reason}"


def test_no_real_human_signoff_observed():
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


def test_fixture_plans_are_inert_templates():
    """The committed plans are inert fixtures — the preflight package never
    asserts a REAL signoff, and no durable Human identity is recorded."""
    for sid in _scenario_ids():
        plan_path = os.path.join(CRIT_FIXTURES_ROOT, sid, "plan.json")
        with open(plan_path) as f:
            plan = json.load(f)
        assert plan.get("human_signoff_id", "").startswith("human-")
    # The package doc never claims a real signoff.
    assert "no invented signature" in _doc_text().lower()


# ============================================================================
# 8. Evidence bundle, state hashes, audit chain
# ============================================================================

BUNDLE_FILES = (
    "manifest.json", "env.json", "plan.json", "before.sha256",
    "after.sha256", "runtime-verdict.json", "audit-log.jsonl",
    "reference-verdict.json", "oracle-classes.json", "provenance.json",
    "replay.json", "verifier-independence.json", "verdict-match.json",
)


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_bundle_complete_under_scratch(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path)
    bundle_dir = summary["bundle_dir"]
    assert str(tmp_path) in bundle_dir
    for fname in BUNDLE_FILES:
        assert os.path.isfile(os.path.join(bundle_dir, fname)), (
            f"missing {fname} in {scenario_id} bundle")
    assert not os.path.exists(os.path.join(PROJECT_ROOT, "audit", "l3",
                                           scenario_id))


@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_state_hashes_present(scenario_id, tmp_path):
    import re as _re
    bundle_dir = _rehearse(scenario_id, tmp_path)["bundle_dir"]
    for h in ("before.sha256", "after.sha256"):
        with open(os.path.join(bundle_dir, h)) as f:
            hashes = json.load(f)
        assert hashes.get("algorithm") == "sha256"
        assert _re.fullmatch(r"[0-9a-f]{64}", hashes.get("root_hash", "")), (
            f"root_hash not a 64-hex sha256: {hashes.get('root_hash')!r}")


def test_audit_chain_tamper_detected():
    from tests.l3_reference.audit_chain import verify_ledger
    root = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002")
    v = verify_ledger(os.path.join(root, "ledger.jsonl"),
                      sidecar_path=os.path.join(root, "ledger.chain"))
    assert v.decision == "INVALID"


def test_audit_chain_original_valid():
    from tests.l3_reference.audit_chain import verify_ledger
    root = os.path.join(CRIT_FIXTURES_ROOT, "L3-AUD-002")
    v = verify_ledger(os.path.join(root, "ledger.original.jsonl"),
                      sidecar_path=os.path.join(root, "ledger.chain"))
    assert v.decision == "VALID"


# ============================================================================
# 9. Verdict agreement (runtime == reference, all 8)
# ============================================================================

@pytest.mark.parametrize("scenario_id", _scenario_ids())
def test_runtime_reference_agree(scenario_id, tmp_path):
    summary = _rehearse(scenario_id, tmp_path)
    bundle_dir = summary["bundle_dir"]
    with open(os.path.join(bundle_dir, "verdict-match.json")) as f:
        match = json.load(f)
    assert match["match"] is True, (
        f"verdict mismatch {scenario_id}: "
        f"runtime={match['runtime_decision']} "
        f"ref={match['reference_decision']}")


# ============================================================================
# 10. LV16 evidence-contract RESOLVED (canonical checklist_item_results)
# ============================================================================

def test_lv16_resolved_three_oracles_emit_checklist(tmp_path):
    """L3-REC-004 / L3-ST-003 / L3-AUD-002 pass LV16: the reference-verdict.json
    carries the canonical `checklist_item_results` field and no LV16 validation
    error remains."""
    for sid in ("L3-REC-004", "L3-ST-003", "L3-AUD-002"):
        summary = _rehearse(sid, tmp_path)
        lv16 = [e for e in summary.get("validation_errors", []) if "LV16" in e]
        assert lv16 == [], f"{sid} still records LV16 errors: {lv16}"
        bundle_dir = summary["bundle_dir"]
        with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
            refv = json.load(f)
        assert "checklist_item_results" in refv, sid
        assert refv["checklist_item_results"], sid


def test_authority_and_path_oracles_emit_checklist(tmp_path):
    for sid in ("L3-AUTH-001", "L3-PATH-001"):
        bundle_dir = _rehearse(sid, tmp_path)["bundle_dir"]
        with open(os.path.join(bundle_dir, "reference-verdict.json")) as f:
            refv = json.load(f)
        assert "checklist_item_results" in refv, sid
        assert refv["checklist_item_results"], sid


def test_all_scenarios_pass_lv16(tmp_path):
    for sid in _scenario_ids():
        summary = _rehearse(sid, tmp_path)
        lv16 = [e for e in summary.get("validation_errors", []) if "LV16" in e]
        assert lv16 == [], f"{sid} still records LV16 errors: {lv16}"


def test_lv16_requirement_intact_in_validator():
    """The validator's LV16 rule is unchanged: REQUIRED_REFERENCE_FIELDS still
    requires checklist_item_results on reference-verdict.json."""
    from tests.l3_runner.validator import REQUIRED_REFERENCE_FIELDS
    assert "checklist_item_results" in REQUIRED_REFERENCE_FIELDS


# ============================================================================
# 11. Claim gate: l3_claim=False on current facts; rehearsal never claims
# ============================================================================

def test_claim_gate_returns_false_on_current_facts(tmp_path):
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
    assert any("uid" in f.lower() or "IO-2" in f for f in result.failures), (
        f"claim must fail on UID separation; failures={result.failures}")


def test_rehearsal_never_claims(tmp_path):
    for sid in _scenario_ids():
        summary = _rehearse(sid, tmp_path)
        assert summary["l3_claim"] is False
        assert summary["lv10_by_design"] is True


# ============================================================================
# 12. Package hygiene: no production imports, no invented claims
# ============================================================================

def test_preflight_package_source_imports_no_production_control_plane():
    package_dir = os.path.join(PROJECT_ROOT, "tests", "l3_runner", "critical",
                               "final")
    banned = ("import control", "from control", "import orchestrator",
              "from orchestrator", "import audit", "from audit",
              "import state", "from state")
    for name in ("test_l3_critical_preflight.py", "test_l3_final_readiness.py",
                 "__init__.py"):
        path = os.path.join(package_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert not any(stripped.startswith(b) for b in banned), \
                f"{name}: {stripped}"


def test_no_l3_claim_and_no_invented_signature_in_doc():
    text = _doc_text()
    assert "No L3 claim. Zero controls are L3." in text
    assert "no invented signature" in text.lower()
    assert "No signature invented" in text or "no signature invented" in text
    # No control may be declared L3 anywhere in the package.
    assert not re.search(r"\bL3\s*[:=]\s*(PASS|CLAIMED|CLOSED)\b", text)

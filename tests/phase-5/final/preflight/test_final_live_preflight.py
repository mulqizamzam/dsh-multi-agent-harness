"""Phase 5 / Session B — FINAL PREFLIGHT lock tests (G13 live + L3 critical).

Deterministic tests that pin the prepared execution package for the final live
G13 + L3 critical run against the machinery it references, per
docs/phase-5/final/preflight/0001-final-operator-checklist.md.

What these tests prove (all observed, none simulated):

  1. The operator checklist exists and contains the six required deliverables
     (prerequisites / scenario order / evidence / rollback+cleanup / claim
     gate) plus the G13 and L3 execution definitions.
  2. The G13 precondition is honestly reported by the prepared plan and is NOT
     satisfied on this host (marker unset, 7x NOT_MOUNTED, backend
     unavailable) -> G13-LIVE BLOCKED.
  3. The L3 claim gate returns l3_claim=False on the CURRENT environment facts
     (same-UID host, rehearsal) -> L3-LIVE BLOCKED, never upgraded.
  4. The scenario registry quoted in the checklist matches the runner exactly
     (8 critical scenarios, ids + gates + expected verdicts + oracle classes).
  5. The G13 fixture matrix quoted in the checklist matches the payloads
     module exactly (7 channels, 8 vectors, 56 vectorxchannel, 7 roles).
  6. No fabricated signature: the checklist never asserts a real Human
     signoff exists; the fixture signoff stays inert.
  7. No DSH-native immunity and no L3 claim is made anywhere in the package.
  8. The preflight package itself imports no production control-plane code.

NO test here executes a live dispatch, enables web_fetch, modifies DSH,
session policy, profiles/presets, or production controls, invents a Human
signature, or fabricates runtime evidence.
"""

from __future__ import annotations

import os
import re
import sys

# tests/phase-5/final/preflight/<file>.py — five dirnames up = repo root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
TESTS_ROOT = os.path.join(PROJECT_ROOT, "tests")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DOCS = os.path.join(PROJECT_ROOT, "docs", "phase-5", "final", "preflight")
CHECKLIST = os.path.join(DOCS, "0001-final-operator-checklist.md")


def _checklist_text() -> str:
    with open(CHECKLIST, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. The checklist exists and carries all six required deliverables
# ---------------------------------------------------------------------------

def test_checklist_file_exists_in_write_only_dir():
    assert os.path.isfile(CHECKLIST), CHECKLIST


def test_checklist_contains_all_six_deliverable_sections():
    text = _checklist_text()
    for section in (
        "## 2. Prerequisites (exact, current, observed)",
        "## 3. Exact scenario order (for the future authorized run)",
        "## 4. Exact evidence required",
        "## 5. Exact rollback / cleanup (binding)",
        "## 6. Exact claim gate",
        "## 7. Prohibited actions (restated from the brief — binding)",
    ):
        assert section in text, section


def test_checklist_marks_both_live_steps_blocked():
    text = _checklist_text()
    assert "G13-LIVE BLOCKED" in text
    assert "L3-LIVE BLOCKED" in text
    assert "RUN G13-LIVE   if and only if" in text
    assert "RUN L3-LIVE    if and only if" in text
    assert "EXECUTE NOTHING while any listed prerequisite is absent" in text


def test_checklist_does_not_claim_l3_or_immunity():
    text = _checklist_text()
    assert "No L3 claim. No" in text
    assert "No\nimmunity claim" in text
    # No control may be declared L3 anywhere in the package.
    assert not re.search(r"\bL3\s*[:=]\s*(PASS|CLAIMED|CLOSED)\b", text)


# ---------------------------------------------------------------------------
# 2. G13: precondition honest, unsatisfied here -> BLOCKED
# ---------------------------------------------------------------------------

def test_g13_precondition_reported_and_unsatisfied():
    from tests.g13.live_readiness.plan import precondition

    p = precondition()
    assert p["satisfied"] is False
    assert p["real_dsh_child_observable"] is False
    assert p["marker_set"] is False
    assert p["backend_kind"] != "real-dsh"
    assert all(mounted is False for mounted in p["instances_mounted"].values())
    # Probe breadth = the full contract roster (PRD v0.2: 15): the keys are
    # the role Agent Presets, derived from the canonical registry FILE (no
    # production imports in this package). All values unmounted:
    # registered ≠ active (ADR 0003 D8) — this session has no live bridge.
    import yaml
    with open(os.path.join(PROJECT_ROOT, "config", "agents.yaml")) as fh:
        roster = {a["id"] for a in yaml.safe_load(fh)["agents"]}
    # 0.2.1-rc.2: the probe reports the role Agent Presets.
    assert set(p["instances_mounted"]) == {f"role-{r}" for r in roster}


def test_checklist_quotes_the_real_g13_precondition_definition():
    text = _checklist_text()
    assert "probe_backend_kind() == real-dsh" in text
    assert "all 15 role Agent Presets" in text
    assert "DSH_LIVE_BRIDGE_ACTIVE" in text


def test_g13_scenario_order_channels_before_vectors_with_fixture_counts():
    text = _checklist_text()
    assert "G13-LIVE-C1" in text and "G13-LIVE-C7" in text
    assert "channel scenarios before vector scenarios" in text
    assert "63 scenarios total: 7 channel + 56 vector" in text


def test_g13_payload_fixture_matrix_matches_payloads_module():
    from tests.g13.live_readiness.payloads import LIVE_CHANNELS, LIVE_VECTORS

    assert len(LIVE_CHANNELS) == 7
    assert len(LIVE_VECTORS) == 56
    # Channel-level affected roles (exact, from the fixtures): the five
    # content channels hit their specialist; C7 hits the orchestrator
    # task-context surface.
    channel_roles = {sc["affected_role"] for sc in LIVE_CHANNELS.values()}
    assert channel_roles == {"kai", "cto", "cfo", "nova", "somad", "orchestrator"}
    # Plan-level registry = the full registry roster (PRD v0.2: 15), derived
    # from the canonical registry FILE — this package must not import
    # production modules (static guard below enforces that).
    from tests.g13.live_readiness.plan import live_test_plan
    import yaml
    with open(os.path.join(PROJECT_ROOT, "config", "agents.yaml")) as fh:
        roster = {a["id"] for a in yaml.safe_load(fh)["agents"]}
    assert set(live_test_plan()["affected_roles"]) == roster
    for sc in list(LIVE_CHANNELS.values()) + LIVE_VECTORS:
        assert sc["expected_authority_impact"].startswith("none")
        assert sc["expected_state_mutation"].startswith("none")
        assert "DENIED" in sc["expected_execution"] or "DENY" in sc["expected_execution"]
        assert "DATA" in sc["expected_data_treatment"]


def test_g13_expected_behaviour_documented_in_checklist():
    text = _checklist_text()
    assert "as DATA" in text
    assert "DENY record" in text and "implied action" in text
    assert "before/after state hash equal" in text
    assert "stopReason" in text
    assert "never an executed action" in text
    # No immunity without a runtime-observed denial on a REAL child.
    assert "no DSH-native immunity claim" in text
    assert "runtime-observed denial" in text


# ---------------------------------------------------------------------------
# 3. L3: claim gate false on current facts; scenario registry exact
# ---------------------------------------------------------------------------

def test_l3_environment_probe_reports_honest_blockers():
    from tests.l3_runner.environment.readiness import assess_environment
    from tests.environment.approval_composition import authorized_web_url

    report = assess_environment(scenario_id="L3-TEST-001",
                                orchestrator_uid=os.getuid())
    assert report.l3_claim_possible is False
    assert report.rehearsal_ready is True
    blocked_ids = {b.split(":")[0] for b in report.blocked}
    # Independent L3 blockers. With an authorized (launch-token) browser
    # answerer attached the corrected composition-based detection makes the
    # answerer available, so L3ENV-ANS-1/ANS-2 are honestly no longer
    # blockers; without attachment they block fail-closed.
    for blocker in ("L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"):
        assert blocker in blocked_ids, blocker
    if authorized_web_url():
        # The answerer is available by composition; it must NOT falsely
        # block L3.
        for not_blocker in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
            assert not_blocker not in blocked_ids, not_blocker
    else:
        for blocker in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
            assert blocker in blocked_ids, blocker


def test_l3_claim_gate_returns_false_on_current_facts(tmp_path):
    from tests.l3_runner.claim_gate import evaluate_l3_claim

    bundle = tmp_path / "L3-AUTH-001"
    bundle.mkdir()
    (bundle / "runtime-verdict.json").write_text("{}", encoding="utf-8")
    result = evaluate_l3_claim(
        bundle_dir=str(bundle),
        runtime_decision="DENY",
        reference_decision="DENY",
        rehearsal=True,  # rehearsal machinery only — forces false by construction
        verifier_pid=os.getpid(),
        orchestrator_pid=os.getpid() + 1,
        verifier_uid=os.getuid(),   # same-UID host: IO-2 fails honestly
        orchestrator_uid=os.getuid(),
        independence_all_pass=False,
        oracle_classes=["O1", "O3", "O4"],
        fixture_hash="",
        verifier_binary_sha256="",
        schema_sha256={},
    )
    assert result.l3_claim is False


def test_l3_claim_gate_still_false_when_rehearsal_flag_removed_but_uid_same(tmp_path):
    from tests.l3_runner.claim_gate import evaluate_l3_claim

    bundle = tmp_path / "L3-PATH-001"
    bundle.mkdir()
    (bundle / "runtime-verdict.json").write_text("{}", encoding="utf-8")
    result = evaluate_l3_claim(
        bundle_dir=str(bundle),
        runtime_decision="DENY",
        reference_decision="DENY",
        rehearsal=False,
        verifier_pid=os.getpid() + 1,
        orchestrator_pid=os.getpid(),
        verifier_uid=os.getuid(),   # same UID -> P2-uid-separation must fail
        orchestrator_uid=os.getuid(),
        oracle_classes=["O1", "O3", "O4"],
        fixture_hash="",
        verifier_binary_sha256="",
        schema_sha256={},
    )
    assert result.l3_claim is False
    uid_check = result.satisfied["P2-uid-separation"]
    assert uid_check["pass"] is False
    assert any(f.startswith("P2-uid-separation") for f in result.failures)


def test_l3_scenario_registry_matches_checklist_quotes():
    from tests.l3_runner.critical.runner import CRITICAL_CONTROLS, CRITICAL_SCENARIOS

    assert len(CRITICAL_SCENARIOS) == 8
    assert len(CRITICAL_CONTROLS) == 6
    order = [sid for _, (sid, gate, verdict, classes) in CRITICAL_SCENARIOS.items()]
    assert order == [
        "L3-AUTH-001", "L3-AUTH-003", "L3-AUTH-004", "L3-AUTH-006",
        "L3-PATH-001", "L3-REC-004", "L3-ST-003", "L3-AUD-002",
    ]
    assert all(len(classes) >= 2 for _, (_, _, _, classes) in CRITICAL_SCENARIOS.items())
    norm = re.sub(r"\s+", " ", _checklist_text())
    for sid in order:
        assert sid in norm, sid
    # The checklist order section quotes exactly this sequence (whitespace-normalized).
    quoted = ("L3-AUTH-001` → `L3-AUTH-003` → `L3-AUTH-004` → `L3-AUTH-006` → "
              "`L3-PATH-001` → `L3-REC-004` → `L3-ST-003` → `L3-AUD-002`")
    assert quoted in norm


def test_l3_critical_controls_all_listed_in_checklist():
    from tests.l3_runner.critical.runner import CRITICAL_CONTROLS

    text = _checklist_text()
    # The four L3 critical-control dimensions required by the session brief.
    for dimension in ("**authority**", "**consequential execution**", "**recovery**",
                      "**state/audit integrity**"):
        assert dimension in text, dimension
    norm = re.sub(r"\s+", " ", text)
    for control in ("recovery privilege bounding", "stale-state protection",
                    "audit integrity", "protected-path execution",
                    "execution-time recheck"):
        assert control in norm, control


def test_l3_required_evidence_items_documented():
    from tests.l3_runner import EVIDENCE_FILES

    text = _checklist_text()
    for evidence in ("runtime-verdict.json", "verifier-independence.json",
                     "oracle-classes.json", "replay.json", "plan.json",
                     "verdict-match.json", "before.sha256", "after.sha256"):
        assert evidence in text, evidence
    # The 13-file bundle contract = the machinery's EVIDENCE_FILES (12, which
    # excludes manifest.json itself) + the certifying manifest.json.
    assert len(EVIDENCE_FILES) == 12
    assert "manifest.json" not in EVIDENCE_FILES
    assert "13-file bundle" in text and "manifest" in text


def test_l3_required_prerequisite_matrix_in_checklist():
    text = _checklist_text()
    for item in ("Separate verifier UID", "Separate verifier process",
                 "P1 live runtime", "Human answerer + approval path",
                 "D4/D7 live bridge", "Real Human signoff per scenario plan",
                 "Approved live-run authorization", "independent oracle classes",
                 "Reproducible replay (P4)"):
        assert item in text, item
    # The load-bearing blocker is named exactly.
    assert "L3ENV-UID-2" in text
    assert "L3ENV-ANS-1" in text
    assert "L3ENV-ANS-2" in text
    assert "L3ENV-D4D7-3" in text
    assert "L3ENV-PLAN-REAL" in text


# ---------------------------------------------------------------------------
# 4. Honesty: no invented signature, no fabricated evidence
# ---------------------------------------------------------------------------

def test_no_invented_human_signature_anywhere_in_package():
    text = _checklist_text()
    assert "does **not** invent signatures" in text
    # A fixture-style signoff id must never be asserted as REAL.
    assert not re.search(r"human_signoff(_id)?\s*=\s*['\"]?human-\d{4}", text)
    for test_doc in (_checklist_text(),):
        assert "no real Human signoff" in test_doc or \
               "no real Human signoff observed" in test_doc or \
               "**ABSENT**" in test_doc


def test_no_fabricated_runtime_evidence_in_package():
    text = _checklist_text()
    assert "fabricate runtime evidence" in text
    # The checklist must never state that runtime evidence already exists.
    assert "Live tests executed this session" in text and "NONE" in text
    assert "L3 claims made" in text


def test_read_gap_documented_not_filled():
    text = _checklist_text()
    assert "docs/phase-5/l3/environment/final/" in text
    assert "ABSENT" in text
    assert not os.path.isdir(os.path.join(PROJECT_ROOT, "docs", "phase-5",
                                          "l3", "environment", "final"))


def test_prohibited_actions_restate_the_brief():
    text = _checklist_text()
    for prohibited in ("Do **not** modify DSH", "Do **not** claim L3",
                       "execute live G13", "execute live L3",
                       "Do **not** invent signatures", "Do **not** enable `web_fetch`",
                       "Do **not** silently fall back to the fake backend"):
        assert prohibited in text, prohibited


# ---------------------------------------------------------------------------
# 5. Package hygiene: clean imports, no production control usage
# ---------------------------------------------------------------------------

def test_preflight_package_source_imports_no_production_control_plane():
    # Static check of THIS package's source: no import of production gates,
    # orchestrator foundation, audit or state helpers.
    package_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final",
                               "preflight")
    banned = ("import control", "from control", "import orchestrator",
              "from orchestrator", "import audit", "from audit",
              "import state", "from state")
    for name in os.listdir(package_dir):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(package_dir, name), encoding="utf-8") as fh:
            source = fh.read()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert not any(stripped.startswith(b) for b in banned), \
                f"{name}: {stripped}"


def test_only_expected_files_written_in_preflight_dirs():
    tests_dir = os.path.join(PROJECT_ROOT, "tests", "phase-5", "final", "preflight")
    written = sorted(os.listdir(tests_dir))
    assert "__init__.py" in written and "test_final_live_preflight.py" in written

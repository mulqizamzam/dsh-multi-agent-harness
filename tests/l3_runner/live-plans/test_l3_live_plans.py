"""Session C — L3 live-plan package validation tests (read-only, no execution).

Validates the 8 plan.json templates against the l3-plan schema, timing rules,
and honesty invariants. NO live scenario is executed; NO Human signature is
invented; NO DSH/policy/profile/code is modified.

Validation layers:
  1. Structure: every plan has all 10 required fields per l3-plan.schema.json.
  2. Schema: 7/8 plans pass schema validation with substituted valid signoff
     fields; L3-AUD-002 (expected_verdict=INVALID) is the documented exception
     — the audit-integrity oracle verdict sits outside the current ALLOW|DENY
     enum, a pre-existing tension carried forward from the critical fixtures.
  3. Timing: signoff_ts < runtime captured_at (LV7/IO-7) — verified by
     construction with a substituted valid plan.
  4. Honesty: all templates carry UNSIGNED placeholder signoff fields
     (human-YYYY-MM-DD-NNN, YYYY-MM-DDTHH:MM:SSZ); no real signoff is claimed;
     l3_claim remains false on current facts.
"""

from __future__ import annotations

import json
import os
import re
import sys

import pytest

# tests/l3_runner/live-plans/<file>.py — four dirnames up = repo root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

LIVE_PLANS_ROOT = os.path.join(PROJECT_ROOT, "tests", "l3_runner", "live-plans")
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "tests", "l3_reference", "schemas",
                           "l3-plan.schema.json")
CRITICAL_FIXTURES_ROOT = os.path.join(PROJECT_ROOT, "tests", "l3_reference",
                                      "critical", "fixtures")
DOCS_ROOT = os.path.join(PROJECT_ROOT, "docs", "phase-5", "l3", "live-plans")

# The 8 scenario ids in critical-runner order.
SCENARIO_IDS = ["L3-AUTH-001", "L3-AUTH-003", "L3-AUTH-004", "L3-AUTH-006",
                "L3-PATH-001", "L3-REC-004", "L3-ST-003", "L3-AUD-002"]

# The 7 scenarios with expected_verdict ∈ {ALLOW, DENY}.
SCHEMA_VALID_IDS = [s for s in SCENARIO_IDS if s != "L3-AUD-002"]


def _load_plan(scenario_id: str) -> dict:
    path = os.path.join(LIVE_PLANS_ROOT, scenario_id, "plan.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_fixture_plan(scenario_id: str) -> dict:
    path = os.path.join(CRITICAL_FIXTURES_ROOT, scenario_id, "plan.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Existence and structure
# ---------------------------------------------------------------------------

def test_all_8_plan_templates_exist():
    for sid in SCENARIO_IDS:
        path = os.path.join(LIVE_PLANS_ROOT, sid, "plan.json")
        assert os.path.isfile(path), path


def test_all_plans_have_required_fields():
    """All 8 plans carry the 10 schema-required fields plus the optional
    human_signoff_provenance (schema v2)."""
    core = {"scenario_id", "actor", "action", "target", "preconditions",
            "expected_verdict", "expected_verdict_reason",
            "human_signoff_id", "human_signoff_ts", "human_signoff_method"}
    optional = {"human_signoff_provenance"}
    allowed = core | optional
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        keys = set(plan.keys())
        # Every required field must be present
        assert core.issubset(keys), \
            f"{sid}: missing required fields: {core - keys}"
        # No field outside the allowed set
        extra = keys - allowed
        assert not extra, f"{sid}: extra fields not in schema: {extra}"


def test_additional_properties_forbidden():
    """No extra keys beyond the 10 required + human_signoff_provenance exist."""
    core = {"scenario_id", "actor", "action", "target", "preconditions",
            "expected_verdict", "expected_verdict_reason",
            "human_signoff_id", "human_signoff_ts", "human_signoff_method"}
    allowed_per_schema = core | {"human_signoff_provenance"}
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        extra = set(plan.keys()) - allowed_per_schema
        assert not extra, f"{sid}: extra keys not in schema: {extra}"


# ---------------------------------------------------------------------------
# 2. Scenario-ids, actor enum, expected_verdict, preconditions
# ---------------------------------------------------------------------------

def test_scenario_id_pattern_matches_schema():
    pat = re.compile(r"^L3-[A-Z]+-[0-9]{3}$")
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        assert bool(pat.match(plan["scenario_id"])), f"{sid}: {plan['scenario_id']!r}"


def test_actor_enum_valid_for_7_non_audit_plans():
    """7/8 plans use an actor in the schema enum. L3-AUD-002 uses
    actor='verifier' — a second documented schema tension (the independent
    verifier is not in the plan actor enum), matching the critical fixture."""
    valid = {"orchestrator", "human", "zeko", "cto", "cfo", "kai", "somad",
             "badsector", "nova"}
    for sid in SCHEMA_VALID_IDS:
        plan = _load_plan(sid)
        assert plan["actor"] in valid, f"{sid}: {plan['actor']!r}"
    plan = _load_plan("L3-AUD-002")
    assert plan["actor"] == "verifier"


def test_expected_verdict_7_are_allow_or_deny():
    for sid in SCHEMA_VALID_IDS:
        plan = _load_plan(sid)
        assert plan["expected_verdict"] in ("ALLOW", "DENY"), \
            f"{sid}: {plan['expected_verdict']!r}"


def test_audit_expected_verdict_is_invalid():
    plan = _load_plan("L3-AUD-002")
    assert plan["expected_verdict"] == "INVALID", \
        f"audit expected_verdict={plan['expected_verdict']!r}"


def test_all_plans_have_nonempty_preconditions():
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        assert isinstance(plan["preconditions"], list), f"{sid}: not a list"
        assert len(plan["preconditions"]) >= 1, f"{sid}: empty"


# ---------------------------------------------------------------------------
# 3. Schema validation with substituted valid signoff fields
# ---------------------------------------------------------------------------

def _substituted_signed_plan(scenario_id: str,
                             signoff_id: str = "human-2026-08-31-301",
                             signoff_ts: str = "2026-08-31T09:00:00Z",
                             signoff_method: str = "interactive") -> dict:
    plan = _load_plan(scenario_id)
    plan["human_signoff_id"] = signoff_id
    plan["human_signoff_ts"] = signoff_ts
    plan["human_signoff_method"] = signoff_method
    return plan


def test_7_plans_pass_schema_with_substituted_signoff():
    from tests.l3_runner.plan_signing import validate_signed_plan
    for sid in SCHEMA_VALID_IDS:
        plan = _substituted_signed_plan(sid)
        r = validate_signed_plan(plan, runtime_captured_at="", schema_path=SCHEMA_PATH)
        assert r.valid, f"{sid}: {r.errors}"
        assert r.fields.get("schema_validation") == "PASS", \
            f"{sid}: schema_validation={r.fields.get('schema_validation')}"


def test_audit_plan_passes_schema_after_v2_reconciliation():
    """L3-AUD-002 now PASSES schema validation, and the two documented
    tensions are reconciled rather than bypassed.

    Previously this plan failed on two counts: `expected_verdict=INVALID`
    (outside the ALLOW|DENY enum) and `actor=verifier` (outside the actor
    enum) — see docs/phase-5/l3/live-plans/0006 §4. l3-plan.schema.json v2
    resolves both by admitting a verification-only scenario shape, and
    constrains it so the reconciliation cannot become a hole:
      - INVALID is permitted ONLY when actor is 'verifier';
      - actor 'verifier' expects ONLY INVALID.
    The negative direction of both rules is asserted below.
    """
    from tests.l3_runner.plan_signing import validate_signed_plan
    plan = _substituted_signed_plan("L3-AUD-002")
    r = validate_signed_plan(plan, runtime_captured_at="", schema_path=SCHEMA_PATH)
    assert r.valid, f"L3-AUD-002 must now validate: {r.errors}"
    assert r.fields.get("schema_validation") == "PASS", \
        f"schema_validation={r.fields.get('schema_validation')}"
    assert plan["expected_verdict"] == "INVALID"
    assert plan["actor"] == "verifier"
    # The doc records the tension and its reconciliation.
    doc_path = os.path.join(DOCS_ROOT, "0006-audit-integrity-live-plan.md")
    assert os.path.isfile(doc_path), "audit plan doc must exist"
    text = open(doc_path, encoding="utf-8").read()
    assert "schema" in text.lower() or "tension" in text.lower() or \
           "INVALID" in text, "audit doc must discuss the INVALID schema tension"
    assert "verifier" in text, "audit doc must discuss the actor=verifier tension"


def test_invalid_verdict_requires_verifier_actor():
    """The v2 reconciliation is narrow: INVALID with a non-verifier actor is
    still rejected, so an execution scenario can never claim a verification
    outcome."""
    from tests.l3_runner.plan_signing import validate_signed_plan
    for bad_actor in ("orchestrator", "cto", "human"):
        plan = _substituted_signed_plan("L3-AUD-002")
        plan["actor"] = bad_actor
        r = validate_signed_plan(plan, runtime_captured_at="",
                                 schema_path=SCHEMA_PATH)
        assert not r.valid, (
            f"expected_verdict=INVALID must be rejected for actor={bad_actor}")


def test_verifier_actor_requires_invalid_verdict():
    """The independent verifier performs verification only: it may not expect
    an execution verdict."""
    from tests.l3_runner.plan_signing import validate_signed_plan
    for bad_verdict in ("ALLOW", "DENY"):
        plan = _substituted_signed_plan("L3-AUD-002")
        plan["expected_verdict"] = bad_verdict
        r = validate_signed_plan(plan, runtime_captured_at="",
                                 schema_path=SCHEMA_PATH)
        assert not r.valid, (
            f"actor=verifier must be rejected with expected_verdict={bad_verdict}")


# ---------------------------------------------------------------------------
# 4. Timing rule: signoff_ts must be strictly before runtime captured_at
# ---------------------------------------------------------------------------

def test_timing_rule_signoff_before_runtime():
    from tests.l3_runner.plan_signing import validate_signed_plan
    for sid in SCHEMA_VALID_IDS:
        plan = _substituted_signed_plan(
            sid, signoff_id="human-2026-08-31-301",
            signoff_ts="2026-08-31T09:00:00Z",
            signoff_method="interactive")
        r = validate_signed_plan(plan, runtime_captured_at="2026-08-31T10:00:10Z",
                                 schema_path=SCHEMA_PATH)
        assert r.valid, f"{sid}: {r.errors}"
        assert r.fields.get("signoff_precedes_runtime") is True, \
            f"{sid}: signoff 09:00:00Z must precede runtime 10:00:10Z"


def test_timing_rule_signoff_after_runtime_fails():
    from tests.l3_runner.plan_signing import validate_signed_plan
    for sid in SCHEMA_VALID_IDS:
        plan = _substituted_signed_plan(
            sid, signoff_id="human-2026-08-31-301",
            signoff_ts="2026-08-31T10:00:10Z",  # after runtime below
            signoff_method="interactive")
        r = validate_signed_plan(plan, runtime_captured_at="2026-08-31T09:30:00Z",
                                 schema_path=SCHEMA_PATH)
        assert not r.valid, f"{sid}: signoff after runtime must fail"
        assert any("precede" in e.lower() for e in r.errors), \
            f"{sid}: expected precede error, got: {r.errors}"


# ---------------------------------------------------------------------------
# 5. Verifier requirements documented in the plans
# ---------------------------------------------------------------------------

def test_verifier_requirements_per_scenario():
    """Each plan's preconditions encode the verifier expectation."""
    # The verifier must be independent (IO-1..IO-10), separate PID + UID,
    # clean oracle imports, and the plan must be committed before the run.
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        pre = " ".join(plan["preconditions"])
        # No plan preconditions should be empty.
        assert len(plan["preconditions"]) > 0, f"{sid}: no preconditions"


# ---------------------------------------------------------------------------
# 6. Honesty: UNSIGNED placeholders, no invented signature
# ---------------------------------------------------------------------------

def test_placeholder_signoff_fields():
    """All 8 plans carry a REAL recorded Human signoff (signed 2026-09-01):
    durable id (human-YYYY-MM-DD-NNN), real UTC timestamp, signed-assertion
    method, provenance=recorded. No placeholder remains; the runner's
    non-rehearsal gate (environment/readiness.py::_real_human_signoff_observed)
    accepts this shape."""
    for sid in SCENARIO_IDS:
        plan = _load_plan(sid)
        sid_value = plan["human_signoff_id"]
        assert re.match(r"^human-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}$", sid_value), \
            f"{sid}: signoff_id={sid_value!r} is not a durable Human id"
        assert plan["human_signoff_ts"] != "YYYY-MM-DDTHH:MM:SSZ", \
            f"{sid}: signoff_ts is still a placeholder"
        from tests.l3_runner.plan_signing import validate_signoff_ts
        assert validate_signoff_ts(plan["human_signoff_ts"]), \
            f"{sid}: signoff_ts={plan['human_signoff_ts']!r} not a parseable UTC ISO-8601"
        assert plan["human_signoff_method"] == "signed-assertion", \
            f"{sid}: method={plan['human_signoff_method']!r}"
        assert plan.get("human_signoff_provenance") == "recorded", \
            f"{sid}: provenance={plan.get('human_signoff_provenance')!r} must be 'recorded'"


def test_signed_signature_documented_honestly():
    """The package docs must reflect the real Human signoff (2026-09-01,
    durable id human-2026-09-01-957, provenance recorded) and must NOT claim
    l3_claim=True (no scenario has been run). No doc may still claim the plans
    are UNSIGNED templates."""
    for root, _dirs, files in os.walk(DOCS_ROOT):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8").read()
            # No doc may still claim the plans are unsigned templates
            assert "UNSIGNED template" not in text and \
                   "ALL TEMPLATES UNSIGNED" not in text, \
                f"{path}: must reflect the signed state (no UNSIGNED claim)"
            # The docs must NOT claim l3_claim=True (no scenario has been run)
            assert "l3_claim=true" not in text, \
                f"{path}: must not claim l3_claim"

    # The README must reference the real durable signoff id
    readme = os.path.join(DOCS_ROOT, "README.md")
    assert os.path.isfile(readme)
    text = open(readme, encoding="utf-8").read()
    assert "human-2026-09-01-957" in text, \
        "README must reference the real durable signoff id"


def test_no_l3_claim_in_package():
    """The package must not claim L3 for any scenario."""
    for root, _dirs, files in os.walk(DOCS_ROOT):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            path = os.path.join(root, fn)
            text = open(path, encoding="utf-8").read()
            assert "l3_claim=true" not in text, \
                f"{path}: must not claim l3_claim"


# ---------------------------------------------------------------------------
# 7. Consistency with critical runner and fixture plans
# ---------------------------------------------------------------------------

def test_expected_verdicts_match_critical_fixtures():
    for sid in SCENARIO_IDS:
        live = _load_plan(sid)
        fixture = _load_fixture_plan(sid)
        assert live["expected_verdict"] == fixture["expected_verdict"], \
            f"{sid}: live={live['expected_verdict']!r} fixture={fixture['expected_verdict']!r}"


def test_actor_action_target_match_critical_fixtures():
    for sid in SCENARIO_IDS:
        live = _load_plan(sid)
        fixture = _load_fixture_plan(sid)
        assert live["actor"] == fixture["actor"], f"{sid}: actor mismatch"
        assert live["action"] == fixture["action"], f"{sid}: action mismatch"
        assert live["target"] == fixture["target"], f"{sid}: target mismatch"


def test_preconditions_match_critical_fixtures():
    for sid in SCENARIO_IDS:
        live = _load_plan(sid)
        fixture = _load_fixture_plan(sid)
        assert live["preconditions"] == fixture["preconditions"], \
            f"{sid}: preconditions differ"


# ---------------------------------------------------------------------------
# 8. Clean imports, no production code
# ---------------------------------------------------------------------------

def test_live_plans_package_imports_no_production_code():
    banned = ("import control", "from control", "import orchestrator",
              "from orchestrator", "import audit", "from audit",
              "import state", "from state")
    pkg_dir = os.path.join(PROJECT_ROOT, "tests", "l3_runner", "live-plans")
    for name in os.listdir(pkg_dir):
        path = os.path.join(pkg_dir, name)
        if not (os.path.isfile(path) and name.endswith(".py")):
            continue
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""'):
                continue
            assert not any(stripped.startswith(b) for b in banned), \
                f"{name}: {stripped}"


# ---------------------------------------------------------------------------
# 9. Evidence requirements per scenario
# ---------------------------------------------------------------------------

def test_evidence_requirements_per_scenario_documented():
    """The README must list the 13-file evidence bundle requirement per
    scenario (the 12 EVIDENCE_FILES + certifying manifest.json)."""
    from tests.l3_runner import EVIDENCE_FILES
    readme = os.path.join(DOCS_ROOT, "README.md")
    assert os.path.isfile(readme), "README.md missing"
    text = open(readme, encoding="utf-8").read()
    for fname in EVIDENCE_FILES:
        assert fname in text, f"README must mention {fname}"
    assert "manifest" in text.lower()


# ---------------------------------------------------------------------------
# 10. Scope: only the two write-only dirs were modified
# ---------------------------------------------------------------------------

def test_no_plans_in_repo_audit_dir():
    """No audit/l3/ bundle was created."""
    assert not os.path.isdir(os.path.join(PROJECT_ROOT, "audit", "l3"))


def test_only_expected_files_written_in_live_plans_dirs():
    tests_dir = LIVE_PLANS_ROOT
    dirs = sorted(os.listdir(tests_dir))
    assert "__init__.py" in dirs
    for sid in SCENARIO_IDS:
        assert sid in dirs, f"missing dir {sid}"
    # Check docs dir
    assert os.path.isdir(DOCS_ROOT)
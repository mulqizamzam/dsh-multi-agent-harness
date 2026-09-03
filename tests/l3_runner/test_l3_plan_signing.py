# tests/l3_runner/test_l3_plan_signing.py — G7: Human-signed plan.json prerequisites tests
#
# Phase 5 / Session F — L3 execution readiness (G7 gap closure).
#
# Exercises tests/l3_runner/plan_signing.py:
#   - signoff-field schema validation (human_signoff_id / human_signoff_ts /
#     human_signoff_method) against the same contract as l3-plan.schema.json
#   - strict pre-runtime ordering (signoff_ts < runtime verdict; LV7 / IO-7)
#   - the Human signing checklist + signing-request template
#   - the additive preflight PF-PLAN-5 check that reuses validate_signed_plan
#
# SAFETY: read-only. The module never signs, never writes into an evidence
# bundle, and never runs L3.

from __future__ import annotations

import json
import os
import sys

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
FIXTURES_ROOT = os.path.join(TESTS_ROOT, "l3_reference", "fixtures")
PLAN_SCHEMA = os.path.join(TESTS_ROOT, "l3_reference", "schemas",
                           "l3-plan.schema.json")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.l3_runner.plan_signing import (  # noqa: E402
    HUMAN_SIGNOFF_METHODS,
    SIGNING_CHECKLIST,
    SignoffValidationResult,
    build_signing_request,
    load_signing_request_template,
    validate_signed_plan,
    validate_signoff_id,
    validate_signoff_method,
    validate_signoff_ts,
)


def _load_plan(scenario_id):
    with open(os.path.join(FIXTURES_ROOT, scenario_id, "plan.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Signoff-field validation helpers
# ---------------------------------------------------------------------------
def test_signoff_id_pattern():
    assert validate_signoff_id("human-2026-08-31-001") is True
    assert validate_signoff_id("human-2026-08-31-999") is True
    assert validate_signoff_id("model-2026-08-31-001") is False   # not the Human
    assert validate_signoff_id("orchestrator") is False           # role id, not identity
    assert validate_signoff_id("human-2026-8-31-001") is False    # zero-padded required
    assert validate_signoff_id("") is False


def test_signoff_ts_format():
    assert validate_signoff_ts("2026-08-31T00:00:00Z") is True
    assert validate_signoff_ts("2026-08-31T00:00:00+00:00") is True
    assert validate_signoff_ts("yesterday") is False
    assert validate_signoff_ts(None) is False


def test_signoff_method_enum():
    assert set(HUMAN_SIGNOFF_METHODS) == {"interactive", "signed-assertion"}
    assert validate_signoff_method("interactive") is True
    assert validate_signoff_method("signed-assertion") is True
    assert validate_signoff_method("model-claim") is False


# ---------------------------------------------------------------------------
# Full signed-plan validation
# ---------------------------------------------------------------------------
def test_real_fixture_plan_is_valid_signed_plan():
    """The committed L3-TEST-001 plan satisfies every O4 signoff prerequisite,
    including the l3-plan.schema.json oracle (jsonschema)."""
    plan = _load_plan("L3-TEST-001")
    result = validate_signed_plan(plan, schema_path=PLAN_SCHEMA)
    assert result.valid is True, result.errors
    assert result.summary == "VALID signed-plan"


def test_real_fixture_plan_order_check_against_runtime():
    plan = _load_plan("L3-TEST-001")
    result = validate_signed_plan(plan, runtime_captured_at="2026-08-31T10:00:00Z",
                                  schema_path=PLAN_SCHEMA)
    assert result.valid is True
    assert result.fields["signoff_precedes_runtime"] is True


def test_post_hoc_signoff_rejected():
    """A plan signed AFTER the runtime verdict is not a valid O4 oracle
    (LV7 / IO-7): strict `<` ordering is enforced."""
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_ts"] = "2026-08-31T11:00:00Z"
    result = validate_signed_plan(plan, runtime_captured_at="2026-08-31T10:00:00Z")
    assert result.valid is False
    assert any("must precede" in e for e in result.errors)


def test_signoff_ts_equal_to_runtime_rejected():
    """Strict ordering: signoff_ts == runtime captured_at is rejected."""
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_ts"] = "2026-08-31T10:00:00Z"
    result = validate_signed_plan(plan, runtime_captured_at="2026-08-31T10:00:00Z")
    assert result.valid is False
    assert result.fields["signoff_precedes_runtime"] is False


def test_invalid_signoff_id_rejected():
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_id"] = "model-2026-08-31-001"
    result = validate_signed_plan(plan, schema_path=PLAN_SCHEMA)
    assert result.valid is False
    assert any("human_signoff_id" in e for e in result.errors)


def test_invalid_signoff_method_rejected():
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_method"] = "model-claim"
    result = validate_signed_plan(plan, schema_path=PLAN_SCHEMA)
    assert result.valid is False
    assert any("human_signoff_method" in e for e in result.errors)


def test_missing_signoff_method_field_rejected():
    """human_signoff_method is REQUIRED (schema): a plan without it fails."""
    plan = _load_plan("L3-TEST-001")
    del plan["human_signoff_method"]
    result = validate_signed_plan(plan, schema_path=PLAN_SCHEMA)
    assert result.valid is False
    assert any("human_signoff_method" in e for e in result.errors)


def test_missing_o4_oracle_rejected():
    plan = _load_plan("L3-TEST-001")
    plan["oracle_classes_used"] = ["O1", "O3"]
    result = validate_signed_plan(plan)
    assert result.valid is False
    assert any("O4" in e for e in result.errors)


def test_empty_plan_rejected():
    result = validate_signed_plan({})
    assert result.valid is False
    assert result.errors


def test_validation_result_serializable():
    r = SignoffValidationResult(valid=True, errors=[], fields={"o4_declared": True})
    d = r.to_dict()
    assert d["valid"] is True and d["summary"] == "VALID signed-plan"


# ---------------------------------------------------------------------------
# Signing checklist + template (G7 process artifacts)
# ---------------------------------------------------------------------------
def test_signing_checklist_has_identity_and_commit_steps():
    steps = {step for (step, _desc) in SIGNING_CHECKLIST}
    assert {"identity", "method", "ordering", "commit", "declaration"} <= steps


def test_build_signing_request_template_shape():
    req = build_signing_request(
        scenario_id="L3-TEST-001", action="code_write",
        target="agents/cto/x.txt", expected_verdict="ALLOW",
        signoff_id="human-2026-08-31-001",
        signoff_ts="2026-08-31T00:00:00Z", signoff_method="interactive")
    assert req["scenario_id"] == "L3-TEST-001"
    assert req["human_signoff_id"] == "human-2026-08-31-001"
    assert req["human_signoff_method"] == "interactive"
    assert "signing_checklist" in req
    assert "BEFORE" in req["note"] or "before" in req["note"]


def test_shared_signing_request_template_fixture_loads():
    """The shared template fixture (tests/l3_reference/fixtures/shared) loads
    and is a structurally valid signing-request artifact."""
    template = load_signing_request_template()
    # Either the fixture exists or a default is produced; both must be usable.
    for key in ("scenario_id", "expected_verdict", "human_signoff_id",
                "human_signoff_ts", "human_signoff_method", "signing_checklist"):
        assert key in template


def test_plan_signing_cli_checklist(tmp_path):
    from tests.l3_runner.plan_signing import main
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--checklist"])
    assert rc == 0
    out = buf.getvalue()
    assert "[identity]" in out and "[commit]" in out


def test_plan_signing_cli_validates_real_fixture(tmp_path):
    from tests.l3_runner.plan_signing import main
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["--scenario", "L3-TEST-001", "--fixtures-root",
                   FIXTURES_ROOT, "--json"])
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert data["valid"] is True


# ---------------------------------------------------------------------------
# Reuse through the preflight PF-PLAN-5 check (additive)
# ---------------------------------------------------------------------------
def test_preflight_pf_plan5_passes_for_real_fixture():
    from tests.l3_runner.preflight import run_preflight
    report = run_preflight(scenario_id="L3-TEST-001",
                           fixtures_root=FIXTURES_ROOT,
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-5")
    assert c.passed is True
    assert "VALID signed-plan" in c.detail


def test_preflight_pf_plan5_rejects_bad_signoff_method():
    from tests.l3_runner.preflight import run_preflight
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_method"] = "model-claim"
    report = run_preflight(plan=plan, orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-5")
    assert c.passed is False
    assert report.all_required_pass is False


def test_preflight_pf_plan5_rejects_post_hoc_signoff():
    from tests.l3_runner.preflight import run_preflight
    plan = _load_plan("L3-TEST-001")
    plan["human_signoff_ts"] = "2026-08-31T11:00:00Z"
    report = run_preflight(plan=plan, runtime_captured_at="2026-08-31T10:00:00Z",
                           orchestrator_pid=99999, orchestrator_uid=0)
    c = next(c for c in report.checks if c.check_id == "PF-PLAN-5")
    assert c.passed is False

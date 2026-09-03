# tests/l3_runner/plan_signing.py — G7: Human-signed plan.json prerequisites
#
# Phase 5 / Session F — L3 execution readiness (G7 gap closure).
#
# PURPOSE
#   Completes the mechanism for a Human-signed `plan.json` (O4 oracle):
#     1. signoff-field schema validation — `human_signoff_id`,
#        `human_signoff_ts`, `human_signoff_method` are validated against the
#        same contract as tests/l3_reference/schemas/l3-plan.schema.json
#        (and, when `jsonschema` is available, against the schema itself);
#     2. pre-runtime ordering — `human_signoff_ts` must be STRICTLY before the
#        runtime verdict's captured_at (LV7 / IO-7); a post-hoc plan is not a
#        valid oracle;
#     3. a signing-request template + checklist — how the Human signs, what
#        identity is recorded, and how the plan is committed before the run.
#
#   This module is READ-ONLY: it never signs, never writes into an evidence
#   bundle, and never runs L3. It produces the artifacts the Human (or a
#   future authorized L3 run) would use, and validates that an already
#   committed plan is a valid O4 oracle.
#
# REUSES preflight.py::PF-PLAN-* — preflight._check_plan() calls
#   validate_signed_plan() for the additive PF-PLAN-5 signoff-field check; the
#   existing PF-PLAN-1..4 semantics are unchanged.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Project root (three levels up from this file).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Signoff-field contract (mirrors tests/l3_reference/schemas/l3-plan.schema.json).
HUMAN_SIGNOFF_ID_PATTERN = re.compile(r"^human-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{3}$")
HUMAN_SIGNOFF_METHODS = ("interactive", "signed-assertion")
PLAN_SCHEMA_REL = os.path.join("tests", "l3_reference", "schemas", "l3-plan.schema.json")


def _utc_parse(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_signoff_ts(s) -> bool:
    """True when the signoff timestamp is a parseable UTC ISO-8601 value."""
    return _utc_parse(s) is not None


def validate_signoff_id(s) -> bool:
    """True when the signoff identity matches human-YYYY-MM-DD-NNN."""
    return isinstance(s, str) and bool(HUMAN_SIGNOFF_ID_PATTERN.match(s))


def validate_signoff_method(s) -> bool:
    """True when the signoff method is in the allowed enum."""
    return isinstance(s, str) and s in HUMAN_SIGNOFF_METHODS


# ---------------------------------------------------------------------------
# Signing checklist (how the Human signs, what identity is recorded)
# ---------------------------------------------------------------------------
SIGNING_CHECKLIST: tuple[tuple[str, str], ...] = (
    ("identity",
     "The Human records a durable signoff identity human-YYYY-MM-DD-NNN "
     "(one per calendar day of signing), NOT a model name and NOT a role id. "
     "The identity is code-validated by pattern (PF-PLAN-5) and recorded in "
     "plan.json.human_signoff_id."),
    ("method",
     "The Human chooses a signoff method: 'interactive' (a live approval in an "
     "ask-policy session) or 'signed-assertion' (a durable signed statement). "
     "Both are recorded verbatim in plan.json.human_signoff_method."),
    ("ordering",
     "The Human signs BEFORE the runtime runs: human_signoff_ts must be "
     "strictly less than the runtime verdict's captured_at (LV7 / IO-7). A "
     "post-hoc plan is not a valid O4 oracle."),
    ("commit",
     "The signed plan.json is committed (git) or immutably staged in the "
     "scenario fixture BEFORE the runner starts, so the pre-commit is the "
     "oracle and the manifest (E1) can hash it."),
    ("declaration",
     "The plan declares expected_verdict (ALLOW|DENY) + expected_verdict_reason "
     "and the scenario fixture declares oracle_classes_used containing O4 — the "
     "Human-signed expectation is an oracle class, never a post-hoc rational."),
)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------
@dataclass
class SignoffValidationResult:
    """Per-field result of validating a Human-signed plan (O4 prerequisites)."""
    valid: bool = False
    errors: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)

    @property
    def summary(self) -> str:
        if self.valid:
            return "VALID signed-plan"
        return f"INVALID signed-plan: {len(self.errors)} error(s)"

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "fields": dict(self.fields),
            "summary": self.summary,
        }


def validate_signed_plan(plan: dict | None, *, runtime_captured_at: str = "",
                         schema_path: str = "") -> SignoffValidationResult:
    """Validate a Human-signed plan.json against the O4 signoff contract.

    Checks (mirrors l3-plan.schema.json v2 + LV6/LV7 + PF-PLAN-*):
      - required plan fields (scenario_id, actor, action, target, preconditions,
        expected_verdict, expected_verdict_reason, human_signoff_id,
        human_signoff_ts, human_signoff_method);
      - expected_verdict enum (ALLOW|DENY for execution scenarios; INVALID only
        for actor=verifier, which is a verification-only outcome);
      - signoff id pattern, signoff ts format, signoff method enum;
      - strict pre-runtime ordering: signoff_ts < runtime captured_at
        (when a runtime timestamp is supplied);
      - O4 declared among oracle_classes_used.
    When schema_path points at l3-plan.schema.json and `jsonschema` is
    importable, the full schema is applied as an additional structure oracle.
    """
    result = SignoffValidationResult()
    plan = plan or {}
    fields = {}

    required = ("scenario_id", "actor", "action", "target", "preconditions",
                "expected_verdict", "expected_verdict_reason",
                "human_signoff_id", "human_signoff_ts", "human_signoff_method")
    missing = [f for f in required if f not in plan]
    fields["missing"] = missing
    if missing:
        result.add_error(f"missing plan fields: {sorted(missing)}")

    # expected_verdict enum (mirrors l3-plan.schema.json v2): ALLOW|DENY for
    # execution scenarios, plus INVALID for verification-only scenarios where
    # the actor is the independent verifier (integrity verification, e.g. a
    # tampered ledger detected by chain re-computation — L3-AUD-002,
    # THREAT-018). INVALID is a verification outcome, never an execution
    # outcome, so it is accepted ONLY together with actor=verifier, and
    # actor=verifier expects ONLY INVALID.
    verdict = plan.get("expected_verdict")
    actor = plan.get("actor")
    fields["expected_verdict"] = verdict
    fields["actor"] = actor
    if verdict == "INVALID":
        if actor != "verifier":
            result.add_error(
                "expected_verdict INVALID is a verification outcome and is "
                "permitted only when actor is 'verifier' (got actor="
                f"{actor!r})")
    elif verdict not in ("ALLOW", "DENY"):
        result.add_error("expected_verdict must be ALLOW, DENY, or INVALID "
                         "(INVALID only for actor=verifier)")
    if actor == "verifier" and verdict != "INVALID":
        result.add_error(
            "actor 'verifier' performs verification only and must expect "
            f"INVALID (got expected_verdict={verdict!r})")

    # Signoff fields (the G7 completion).
    sid_ok = validate_signoff_id(plan.get("human_signoff_id"))
    ts_ok = validate_signoff_ts(plan.get("human_signoff_ts"))
    method_ok = validate_signoff_method(plan.get("human_signoff_method"))
    fields["human_signoff_id"] = plan.get("human_signoff_id")
    fields["human_signoff_ts"] = plan.get("human_signoff_ts")
    fields["human_signoff_method"] = plan.get("human_signoff_method")
    if not sid_ok:
        result.add_error("human_signoff_id must match human-YYYY-MM-DD-NNN")
    if not ts_ok:
        result.add_error("human_signoff_ts must be a parseable UTC ISO-8601 "
                         "timestamp")
    if not method_ok:
        result.add_error("human_signoff_method must be one of "
                         f"{HUMAN_SIGNOFF_METHODS}")

    # Pre-runtime ordering (LV7 / IO-7): signoff strictly before runtime.
    if runtime_captured_at:
        plan_ts = _utc_parse(plan.get("human_signoff_ts"))
        run_ts = _utc_parse(runtime_captured_at)
        precedes = plan_ts is not None and run_ts is not None and plan_ts < run_ts
        fields["signoff_precedes_runtime"] = precedes
        if not precedes:
            result.add_error(
                f"human_signoff_ts {plan.get('human_signoff_ts')!r} must precede "
                f"runtime captured_at {runtime_captured_at!r}")

    # O4 oracle declared (the plan is a Human-signed expectation).
    # Per the schema-purity rule (0007 §4), oracle_classes_used lives in
    # fixture.json, not in the schema-pure plan.json. So when oracle_classes_used
    # is absent from the plan dict, the O4 check is lenient (it is enforced at
    # the merged-fixture level by PF-PLAN-4 / runner R6).
    ocs = plan.get("oracle_classes_used")
    if ocs is not None:
        o4 = "O4" in ocs
        fields["o4_declared"] = o4
        if not o4:
            result.add_error("oracle_classes_used must declare O4 (Human-signed "
                             "expectation)")
    else:
        # oracle_classes_used absent (schema-pure plan without fixture merge):
        # the O4 check is delegated to the runner/Fixture level.
        fields["o4_declared"] = "deferred-to-fixture"

    # Optional full-schema oracle (O2-style, structure only).
    if schema_path and os.path.isfile(schema_path):
        try:
            import jsonschema
            with open(schema_path) as f:
                schema = json.load(f)
            # Validate only the plan fields (fixture-driving fields live in
            # fixture.json per the schema-purity rule; restrict to schema props).
            plan_subset = {k: v for k, v in plan.items() if k in schema.get("properties", {})}
            jsonschema.validate(plan_subset, schema)
            fields["schema_validation"] = "PASS"
        except ImportError:
            fields["schema_validation"] = "jsonschema-not-available"
        except Exception as e:  # jsonschema.ValidationError / schema errors
            result.add_error(f"l3-plan.schema.json validation failed: {e}")
            fields["schema_validation"] = f"FAIL: {e}"

    result.fields = fields
    result.valid = not result.errors
    return result


# ---------------------------------------------------------------------------
# Signing-request template (how the Human signs + commits before the run)
# ---------------------------------------------------------------------------
def build_signing_request(*, scenario_id: str, actor: str = "orchestrator",
                          action: str = "", target: str = "",
                          expected_verdict: str = "DENY",
                          expected_verdict_reason: str = "",
                          preconditions: list | None = None,
                          signoff_id: str = "",
                          signoff_ts: str = "",
                          signoff_method: str = "interactive") -> dict:
    """Produce a Human signing-request template for one L3 scenario.

    This is the artifact handed to the Human BEFORE the run. The Human fills
    the expectation, records their identity, timestamps it, and commits the
    plan.json to the scenario fixture. The runner then pre-commits that same
    plan into the evidence bundle (R3) before any runtime activity.
    """
    ts = signoff_ts or _now_iso()
    return {
        "scenario_id": scenario_id,
        "actor": actor,
        "action": action,
        "target": target,
        "preconditions": list(preconditions or []),
        "expected_verdict": expected_verdict,
        "expected_verdict_reason": expected_verdict_reason,
        "human_signoff_id": signoff_id or f"human-{ts[:10]}",
        "human_signoff_ts": ts,
        "human_signoff_method": signoff_method,
        "signing_checklist": [step for (step, _desc) in SIGNING_CHECKLIST],
        "note": "Signed plan.json is committed to the scenario fixture BEFORE "
                "the runner starts; human_signoff_ts must be strictly before "
                "the runtime verdict (LV7 / IO-7).",
    }


def load_signing_request_template() -> dict:
    """Load the shared signing-request template fixture, if present."""
    path = os.path.join(PROJECT_ROOT, "tests", "l3_reference", "fixtures",
                        "shared", "signing-request.template.json")
    if not os.path.isfile(path):
        return build_signing_request(scenario_id="L3-XXX-000")
    with open(path) as f:
        return json.load(f)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Human-signed plan.json prerequisites (read-only; never signs)")
    parser.add_argument("--scenario", default="", help="L3-<CTRL>-<NNN>")
    parser.add_argument("--fixtures-root", default="")
    parser.add_argument("--runtime-captured-at", default="")
    parser.add_argument("--checklist", action="store_true",
                        help="print the Human signing checklist")
    parser.add_argument("--template", action="store_true",
                        help="print the signing-request template JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.checklist:
        for step, desc in SIGNING_CHECKLIST:
            print(f"[{step}] {desc}")
        return 0
    if args.template:
        print(json.dumps(load_signing_request_template(), indent=1))
        return 0

    fixtures_root = args.fixtures_root or os.path.join(
        PROJECT_ROOT, "tests", "l3_reference", "fixtures")
    plan = None
    if args.scenario:
        plan_path = os.path.join(fixtures_root, args.scenario, "plan.json")
        if os.path.isfile(plan_path):
            with open(plan_path) as f:
                plan = json.load(f)
    result = validate_signed_plan(plan, runtime_captured_at=args.runtime_captured_at,
                                  schema_path=os.path.join(PROJECT_ROOT, PLAN_SCHEMA_REL))
    if args.json:
        print(json.dumps(result.to_dict(), indent=1))
    else:
        print(result.summary)
        for e in result.errors:
            print(f"  [FAIL] {e}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    sys.exit(main())

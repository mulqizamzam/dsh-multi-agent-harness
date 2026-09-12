# tests/orchestrator/runtime/test_attach_evidence_independent.py
#
# Regression: `ExecutionFlow._attach_evidence` must NOT fabricate
# self-authored verification evidence for the required kinds of an action
# category that requires INDEPENDENT verification (code_change_production,
# production_deploy, infrastructure, financial, credential_change,
# material_publication, recovery_rollback).
#
# The defect: the flow added `verifier="self:orchestrator", independent=False`
# artifacts for every required kind of EVERY category. For an independent
# category that satisfied the VERIFY-003 presence check with artifacts written
# by the executor itself, so the only remaining (and misleading) signal was
# the generic independence failure — the evidence list made the action look
# "evidence-complete" when no separate verifier had produced anything.
#
# Fixed behaviour:
#   (a) independent category -> no evidence fabricated for the required kinds,
#       and the withholding is recorded as DATA (not evidence) on the flow;
#   (b) self-verifiable category -> unchanged (required kinds attached,
#       including the `internal_analysis` generic "artifact" fallback);
#   (c) the resulting verification verdict is INSUFFICIENT and can_emit_complete
#       is False (fail-closed: COMPLETE stays refused until a real independent
#       verifier supplies artifacts).
#
# TEST-SUPPORT ONLY. Not production code.
#
# Runs under pytest, and under bare `python3 <this file>` (pytest is not always
# available in this environment) through the small runner at the end.

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.execution.engine import ExecutionEngine
from orchestrator.execution.request import ExecutionRequest
from orchestrator.foundation.contracts import Delegation
from orchestrator.runtime import ExecutePlan, ExecutionFlow

# Categories whose requirements demand an independent verifier
# (control/verification.py §10/§16.1).
INDEPENDENT_CATEGORIES = (
    "code_change_production",
    "production_deploy",
    "infrastructure",
    "financial",
    "credential_change",
    "material_publication",
    "recovery_rollback",
)

# Categories the executor may verify itself.
SELF_CATEGORIES = {
    "code_change": ("test", "build"),
    "novel_writing": ("continuity_check",),
    "internal_analysis": ("artifact",),  # generic fallback (no kinds mandated)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _delegation(action="code_write", target="agents/**"):
    return Delegation(
        id="delegation-attach-evidence-001", principal="human",
        delegate="orchestrator", project="multi-agent-harness", task="task-1",
        action=action, target=target, environment="dev",
        scope_operations=("write", "read", "code_write"),
        scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        scope_environments=("dev",), status="ACTIVE", version=1)


def make_engine(action_category, *, action="code_write",
                target="agents/cto/output.txt"):
    """A validated + executed ExecutionEngine for one action category."""
    request = ExecutionRequest(
        task_id="task-1", actor="orchestrator", action=action, target=target,
        environment="dev", delegation=_delegation(action=action),
        expected_outcome={"exit_code": 0}, action_category=action_category,
        project="multi-agent-harness", state_version=1)
    engine = ExecutionEngine(request, base=_PROJECT_ROOT)
    engine.validate()
    engine.execute(executor=lambda req: {"exit_code": 0}, agent_claim=None)
    return engine


def make_flow():
    """A flow object carrying only the per-run state `_attach_evidence` uses.

    The full ExecutionFlow constructor builds a delegation provider and lazy
    persistence; neither participates in evidence attachment, so the three
    assertions below are made against the real method on a real engine.
    """
    flow = object.__new__(ExecutionFlow)
    flow._pending_independent_verification = []
    return flow


def make_plan(action_category, target="agents/cto/output.txt"):
    return ExecutePlan(action="code_write", target=target, environment="dev",
                       expected_outcome={"exit_code": 0},
                       action_category=action_category)


def evidence_of(engine):
    return list(engine.verification._evidence)


def pending_of(flow):
    return list(flow._pending_independent_verification)


# ---------------------------------------------------------------------------
# (a) independent category — nothing fabricated, withholding recorded as data
# ---------------------------------------------------------------------------

class TestIndependentCategoryIsNotFabricated:
    def test_no_evidence_is_added(self):
        for category in INDEPENDENT_CATEGORIES:
            engine = make_engine(category)
            flow = make_flow()
            flow._attach_evidence(engine, make_plan(category))
            assert evidence_of(engine) == [], (
                f"{category}: orchestrator fabricated evidence for a category "
                f"requiring independent verification")

    def test_self_authored_artifact_is_not_present_for_required_kinds(self):
        engine = make_engine("code_change_production")
        flow = make_flow()
        flow._attach_evidence(engine, make_plan("code_change_production"))
        kinds = [e.kind for e in evidence_of(engine)]
        assert "test" not in kinds
        assert "build" not in kinds
        assert not any(e.verifier == "self:orchestrator"
                       for e in evidence_of(engine))

    def test_withholding_is_recorded_as_data(self):
        engine = make_engine("production_deploy")
        flow = make_flow()
        flow._attach_evidence(engine, make_plan("production_deploy"))
        records = pending_of(flow)
        assert len(records) == 1
        record = records[0]
        assert record["action_category"] == "production_deploy"
        assert record["independence"] == "independent"
        assert record["verifier"] == "none"
        assert record["pending_kinds"] == ["deployment_status", "runtime_health"]
        assert record["verdict_until_supplied"] == "INSUFFICIENT"

    def test_trace_is_not_machine_readable_as_evidence(self):
        """The trace must not enter the verification session as an artifact."""
        engine = make_engine("financial")
        flow = make_flow()
        flow._attach_evidence(engine, make_plan("financial"))
        assert pending_of(flow)[0]["pending_kinds"] == ["financial_result"]
        # Nothing was handed to the verification session, so no record in it
        # can be mistaken for a satisfied requirement.
        assert evidence_of(engine) == []
        assert engine.verification.evaluate().verdict == "INSUFFICIENT"

    def test_repeated_attach_does_not_duplicate_the_trace(self):
        engine = make_engine("credential_change")
        flow = make_flow()
        plan = make_plan("credential_change")
        flow._attach_evidence(engine, plan)
        flow._attach_evidence(engine, plan)
        assert len(pending_of(flow)) == 1


# ---------------------------------------------------------------------------
# (b) self-verifiable category — behaviour unchanged
# ---------------------------------------------------------------------------

class TestSelfVerifiableCategoryUnchanged:
    def test_required_kinds_are_attached(self):
        for category, expected_kinds in SELF_CATEGORIES.items():
            engine = make_engine(category)
            flow = make_flow()
            flow._attach_evidence(engine, make_plan(category))
            assert [e.kind for e in evidence_of(engine)] == list(expected_kinds)
            assert all(e.verifier == "self:orchestrator"
                       and e.independent is False
                       for e in evidence_of(engine))
            assert all(e.source == f"agents/cto/output.txt#{e.kind}"
                       for e in evidence_of(engine))

    def test_no_trace_for_self_category(self):
        engine = make_engine("code_change")
        flow = make_flow()
        flow._attach_evidence(engine, make_plan("code_change"))
        assert pending_of(flow) == []

    def test_self_category_verification_still_passes(self):
        for category in SELF_CATEGORIES:
            engine = make_engine(category)
            flow = make_flow()
            flow._attach_evidence(engine, make_plan(category))
            assert engine.verification_result().verdict == "PASSED", category
            assert engine.can_complete() is True, category


# ---------------------------------------------------------------------------
# (c) independent category — verdict INSUFFICIENT, COMPLETE refused
# ---------------------------------------------------------------------------

class TestIndependentCategoryFailsClosed:
    def test_verdict_is_insufficient_and_not_complete(self):
        for category in INDEPENDENT_CATEGORIES:
            engine = make_engine(category)
            flow = make_flow()
            flow._attach_evidence(engine, make_plan(category))
            result = engine.verification_result()
            assert result.verdict == "INSUFFICIENT", (
                f"{category}: expected INSUFFICIENT, got {result.verdict}")
            assert result.is_verified() is False
            assert result.can_emit_complete() is False
            assert engine.can_complete() is False
            # The verdict names the genuinely missing kinds (VERIFY-003),
            # not merely a generic independence refusal.
            assert "missing" in result.reason
            assert "VERIFY-003" in result.reason

    def test_missing_kinds_are_the_required_kinds(self):
        from control.verification import verification_requirements
        for category in INDEPENDENT_CATEGORIES:
            engine = make_engine(category)
            flow = make_flow()
            flow._attach_evidence(engine, make_plan(category))
            result = engine.verification_result()
            assert result.detail["independence"] == "independent"
            assert sorted(result.detail["required_evidence"]) == sorted(
                verification_requirements(category).required_evidence)

    def test_real_independent_evidence_is_what_unblocks_it(self):
        """The gate opens only when a NON-executor supplies the artifacts."""
        category = "production_deploy"
        engine = make_engine(category)
        flow = make_flow()
        flow._attach_evidence(engine, make_plan(category))
        assert engine.verification_result().verdict == "INSUFFICIENT"
        for kind in ("deployment_status", "runtime_health"):
            engine.add_evidence(kind, f"independent-verifier:{kind}",
                                verifier="independent:vera", independent=True)
        assert engine.verification_result().verdict == "PASSED"


# ---------------------------------------------------------------------------
# Standalone runner (pytest is the primary runner; this keeps the file
# executable with bare python3 where pytest is unavailable).
# ---------------------------------------------------------------------------

def _run_standalone() -> int:
    passed, failed = 0, 0
    for name in sorted(dir(sys.modules[__name__])):
        obj = globals()[name]
        if name.startswith("Test") and isinstance(obj, type):
            for case in sorted(v for v in vars(obj) if v.startswith("test_")):
                label = f"{name}::{case}"
                try:
                    getattr(obj(), case)()
                except Exception as exc:  # noqa: BLE001 — report, keep running
                    failed += 1
                    print(f"FAIL {label}: {type(exc).__name__}: {exc}")
                else:
                    passed += 1
                    print(f"PASS {label}")
        elif name.startswith("test_") and callable(obj):
            try:
                obj()
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            else:
                passed += 1
                print(f"PASS {name}")
    print(f"{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())

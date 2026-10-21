"""G13 (Session B / FINAL SECURITY) — live DSH verification readiness tests.

These tests verify the PREPARED live G13 test package under
tests/g13/live_readiness/. They do NOT run a live DSH test:

  - the precondition (REAL DSH child observable) is checked honestly and, in
    this session, reports BLOCKED (D4/D7 marker unset; instances NOT_MOUNTED);
  - the plan is complete (all ten required fields defined in the brief);
  - the payload fixtures are structurally valid, non-destructive, and assert
    control-plane DENY (never an instruction verdict);
  - no immunity is claimed, web_fetch stays disabled, and the package modifies
    no DSH/policy.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.g13.live_readiness.plan import precondition, live_test_plan
from tests.g13.live_readiness.payloads import (
    ENTRY_POINT, LIVE_CHANNELS, LIVE_VECTORS,
)

# Fields the brief requires the plan to define.
REQUIRED_PLAN_FIELDS = (
    "runtime_entry_point",
    "affected_roles",
    "expected_data_treatment",
    "authority_impact",
    "state_mutation_expectation",
    "execution_expectation",
    "badsector_expectation",
    "evidence_requirements",
    "rollback_cleanup",
    "payload_fixtures",
)


class TestLiveReadinessPrecondition:
    """The precondition gate: a REAL DSH child must be observable."""

    def test_precondition_reports_honestly(self):
        p = precondition()
        assert "real_dsh_child_observable" in p
        assert p["satisfied"] == p["real_dsh_child_observable"]
        assert "backend_kind" in p

    def test_precondition_not_satisfied_this_session(self):
        """This session cannot observe a REAL DSH child (marker unset /
        instances NOT_MOUNTED) → live G13 is BLOCKED, exactly as the brief
        requires ("If unavailable: return BLOCKED")."""
        p = precondition()
        assert p["satisfied"] is False, (
            "a REAL DSH child became observable — run the live test plan, "
            "record audit/runtime/ evidence, and only then consider any "
            "DSH-native observation")

    def test_no_live_dispatch_performed(self):
        """Preparing the package is not executing it: no child is dispatched
        and no audit/runtime evidence is produced by the readiness tests."""
        plan = live_test_plan()
        assert plan["status"].startswith("PREPARED")


class TestLiveReadinessPlan:
    """The prepared plan defines every field the brief requires."""

    def test_plan_complete(self):
        plan = live_test_plan()
        for field in REQUIRED_PLAN_FIELDS:
            assert field in plan, f"plan missing required field: {field}"
        assert plan["title"]
        assert plan["status"]

    def test_payload_fixture_counts(self):
        plan = live_test_plan()
        fx = plan["payload_fixtures"]
        assert len(LIVE_CHANNELS) == fx["channels"] == 7
        assert len(LIVE_VECTORS) == fx["vector_x_channel"] == 56
        assert fx["vectors"] == 8

    def test_affected_roles_are_specialists(self):
        plan = live_test_plan()
        from orchestrator.foundation.contracts import SPECIALIST_ROLES
        assert set(plan["affected_roles"]) == set(SPECIALIST_ROLES)

    def test_expected_treatment_is_data_never_instructions(self):
        plan = live_test_plan()
        assert "DATA" in plan["expected_data_treatment"]
        assert "AUTH-INV-17" in plan["expected_data_treatment"]

    def test_no_authority_state_execution_effect(self):
        plan = live_test_plan()
        assert plan["authority_impact"].startswith("none")
        assert plan["state_mutation_expectation"].startswith("none")
        assert plan["execution_expectation"].startswith("none")

    def test_badsector_never_authorizes(self):
        plan = live_test_plan()
        assert "never authorizes" in plan["badsector_expectation"]
        assert "AUTH-INV-09" in plan["badsector_expectation"]

    def test_evidence_and_cleanup_defined(self):
        plan = live_test_plan()
        assert isinstance(plan["evidence_requirements"], list)
        assert len(plan["evidence_requirements"]) >= 4
        assert isinstance(plan["rollback_cleanup"], list)
        assert len(plan["rollback_cleanup"]) >= 4

    def test_runtime_entry_point_defined(self):
        ep = live_test_plan()["runtime_entry_point"]
        assert "agent_preset" in ep["surface"]
        assert "RealDSHBackend" in ep["driver"]
        assert "SubagentResult" in ep["result_contract"]


class TestLivePayloadFixtures:
    """The payload fixtures are valid and assert control-plane DENY."""

    def test_channels_well_formed(self):
        for sid, ch in LIVE_CHANNELS.items():
            assert ch["scenario_id"].startswith("G13-LIVE-")
            assert ch["payload"]
            assert ch["affected_role"]
            assert ch["expected_execution"].startswith("none")
            assert ch["expected_state_mutation"].startswith("none")
            assert ch["expected_authority_impact"].startswith("none")
            assert isinstance(ch["evidence_requirements"], list)
            assert isinstance(ch["rollback_cleanup"], list)

    def test_vectors_well_formed(self):
        for v in LIVE_VECTORS:
            assert v["scenario_id"].startswith("G13-LIVE-")
            assert v["payload"]
            assert v["expected_execution"].startswith("none")
            assert v["expected_badsector"]
            assert isinstance(v["evidence_requirements"], list)

    def test_fixtures_do_not_enable_web_fetch(self):
        """The prepared live test never enables web_fetch (hard out-of-scope)."""
        plan = live_test_plan()
        assert any("web_fetch" in g for g in plan["non_destructive_guarantee"])
        # The role-preset mapping must not allow web_fetch.
        import yaml
        with open(os.path.join(PROJECT_ROOT, "config",
                               "role-preset-mapping.yaml")) as f:
            mapping = yaml.safe_load(f)
        for role in mapping["roles"]:
            allow = set(role["tool_surface"]["allow"])
            assert "web_fetch" not in allow

    def test_plan_claims_no_immunity(self):
        plan = live_test_plan()
        text = (plan["title"] + " " + plan["status"]
                + " " + " ".join(plan["non_destructive_guarantee"])).lower()
        for banned in ("immune", "immune to prompt injection",
                       "prompt-injection-proof", "injection-proof"):
            assert banned not in text, f"plan must not claim {banned!r}"


class TestLiveReadinessPurity:
    """The readiness package imports no production control-plane modules."""

    def test_no_production_import_in_fixture_modules(self):
        import ast
        for mod in ("plan.py", "payloads.py"):
            path = os.path.join(
                PROJECT_ROOT, "tests", "g13", "live_readiness", mod)
            tree = ast.parse(open(path).read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        assert not a.name.startswith(
                            ("control.", "orchestrator.foundation.gates",
                             "audit.helpers", "state.helpers")), (
                            f"{mod} imports production module {a.name!r}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith(
                            ("control.", "orchestrator.foundation.gates",
                             "audit.helpers", "state.helpers")):
                        raise AssertionError(
                            f"{mod} imports production module {node.module!r}")

    def test_entry_point_uses_documented_bridge_only(self):
        """The documented entry point is the real-bridge seam, never the fake
        backend used by deterministic tests — the live test must observe a
        REAL child."""
        ep = ENTRY_POINT
        assert ep["surface"].startswith("the D4/D7 delegation tool")
        assert "RealDSHBackend" in ep["driver"]
        assert "FakeSubagentBackend" not in ep["driver"]

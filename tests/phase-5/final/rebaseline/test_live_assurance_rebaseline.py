"""Phase 5 / Session B — LIVE-ASSURANCE RE-BASELINE tests.

These tests lock the re-baseline honesty: they verify that the current
session state matches the observed re-baseline facts (3 L3-required blockers,
approval correction holds, O5 applied, rehearsal ready, L3 claim impossible).

They run the actual probes:
  - L3: tests.l3_runner.environment.readiness.assess_environment()
  - G13: tests.g13.live_readiness.plan.precondition()
  - Approval: tests.environment.approval_composition.approval_readiness()
  - Live driver: tests.l3_runner.runtime_driver.LiveDSHRuntimeDriver
  - Claim gate: tests.l3_runner.claim_gate.evaluate_l3_claim()

Write-only scope: tests/phase-5/final/rebaseline/ + docs/phase-5/final/rebaseline/.
Nothing else is modified; no live dispatch, no DSH/policy change, no signature
invented, no claim made.
"""

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

ORCHESTRATOR_UID = os.getuid()


def _extract_allow(block: str) -> set:
    """Extract the exact tool names from the toolFilter allow list of a block.

    Parses the `allow: [ ... ]` line(s) and returns the set of exact tool
    names (token-matched, so `todo_write` != `write`).
    """
    import re
    names = set()
    for m in re.finditer(r"allow:\s*\[([^\]]*)\]", block):
        for tok in re.split(r"[,\s]+", m.group(1)):
            if tok:
                names.add(tok)
    return names


def _l3_readiness():
    from tests.l3_runner.environment.readiness import assess_environment
    return assess_environment(
        scenario_id="L3-TEST-001", orchestrator_uid=ORCHESTRATOR_UID)


def _g13_precondition():
    from tests.g13.live_readiness.plan import precondition
    return precondition()


def _approval_readiness():
    from tests.environment.approval_composition import approval_readiness
    return approval_readiness()


def _live_driver_available():
    from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
    return LiveDSHRuntimeDriver().available()


def _claim_gate():
    from tests.l3_runner.claim_gate import evaluate_l3_claim
    return evaluate_l3_claim(
        bundle_dir="", runtime_decision="DENY", reference_decision="DENY",
        rehearsal=False, verifier_pid=1001, orchestrator_pid=2,
        verifier_uid=1000, orchestrator_uid=1000,
        independence_all_pass=False, oracle_classes=["O1", "O3", "O4"],
        fixture_hash="sha256:" + "0" * 64, verifier_binary_sha256="0" * 64,
        schema_sha256={"l3-plan.schema.json": "0" * 64},
        plan_signoff_ts="2026-08-31T00:00:00Z",
        runtime_captured_at="2026-08-31T00:00:01Z", unresolved_unknowns=[])


# ---------------------------------------------------------------------------
# Baseline honesty — the exact 3 L3-required blockers
# ---------------------------------------------------------------------------

class TestBaselineHonesty:
    """The re-baseline must report the exact 3 L3-required blockers correctly."""

    def test_rehearsal_ready_l3_claim_impossible(self):
        r = _l3_readiness()
        assert r.rehearsal_ready is True
        assert r.all_required_pass is True
        assert r.l3_claim_possible is False
        assert r.all_l3_required_pass is False

    def test_l3_uid_blocker(self):
        r = _l3_readiness()
        uid2 = next((c for c in r.checks if c.check_id == "L3ENV-UID-2"), None)
        assert uid2 is not None and uid2.passed is False
        assert uid2.required_for_l3 is True
        assert "1000" in uid2.detail  # same-uid host

    def test_live_bridge_blocker(self):
        r = _l3_readiness()
        d4d7 = next((c for c in r.checks if c.check_id == "L3ENV-D4D7-3"), None)
        assert d4d7 is not None and d4d7.passed is False
        assert d4d7.required_for_l3 is True
        assert "unset" in d4d7.detail.lower() or "unset" in d4d7.detail

    def test_real_signoff_blocker(self):
        r = _l3_readiness()
        real = next((c for c in r.checks if c.check_id == "L3ENV-PLAN-REAL"), None)
        assert real is not None and real.passed is False
        assert real.required_for_l3 is True
        assert "fixture" in real.detail.lower() or "template" in real.detail.lower()

    def test_exactly_3_blockers(self):
        r = _l3_readiness()
        # Only checks marked required_for_l3=True and not passed are blockers
        blockers = [c for c in r.checks if c.required_for_l3 and not c.passed]
        assert len(blockers) == 3, f"Expected 3 blockers, got {len(blockers)}: {[b.check_id for b in blockers]}"
        blocked_ids = {b.check_id for b in blockers}
        assert blocked_ids == {"L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"}


# ---------------------------------------------------------------------------
# Approval-path correction — verification
# ---------------------------------------------------------------------------

class TestApprovalCorrection:
    """The approval-path correction must be verified live: L3ENV-ANS-1/2 PASS."""

    def test_approval_readiness_checks_pass(self):
        r = _l3_readiness()
        ans1 = next((c for c in r.checks if c.check_id == "L3ENV-ANS-1"), None)
        ans2 = next((c for c in r.checks if c.check_id == "L3ENV-ANS-2"), None)
        assert ans1 is not None and ans1.passed is True, \
            f"L3ENV-ANS-1 should PASS (answerer by composition), got pass={ans1.passed}"
        assert ans2 is not None and ans2.passed is True, \
            f"L3ENV-ANS-2 should PASS (approval path available), got pass={ans2.passed}"

    def test_approval_composition_holds(self):
        r = _approval_readiness()
        assert r.composed is True
        assert r.interactive_ready is True
        assert r.status.value == "APPROVAL_INTERACTIVE_READY"
        assert r.approval_service_composed is True
        assert r.answerer_surface_composed is True
        assert r.web_session is True
        assert r.effective_policy == "ask"

    def test_e2e_status_unknown_not_promoted(self):
        r = _approval_readiness()
        # E2E must be UNKNOWN, never PASS, when no matching pair is in the
        # current session log (composition readiness != E2E verification)
        assert r.e2e_status == "UNKNOWN", \
            f"E2E must be UNKNOWN, got {r.e2e_status}"
        assert r.e2e_verified is False
        assert r.probe_answered is False

    def test_approval_events_zero(self):
        r = _approval_readiness()
        assert len(r.approval_events) == 0
        assert r.e2e_pair == {}


# ---------------------------------------------------------------------------
# O5 containment — verification
# ---------------------------------------------------------------------------

class TestO5ContainmentApplied:
    """O5 must be applied: somad/nova have no write/edit in live patch."""

    def test_live_cordis_patch_somad_no_write_edit(self):
        """Check the live cordis.patch.yml somad row has no write/edit.

        `todo_write` is a permitted tool and contains the substring 'write';
        the O5 check must match the EXACT tool name `write` (a token), not a
        substring, so `todo_write` does not trip it.
        """
        import os
        dsh_home = os.environ.get("DSH_HOME", "")
        if not dsh_home:
            pytest.skip("DSH_HOME not set")
        patch = os.path.join(dsh_home, "profiles", "web", "cordis.patch.yml")
        assert os.path.isfile(patch), f"cordis.patch.yml not found at {patch}"
        with open(patch) as f:
            text = f.read()
        # Find the somad block and check its allow list
        somad_start = text.find("tool-subagent-somad")
        nova_start = text.find("tool-subagent-nova")
        assert somad_start >= 0, "somad row not found in live patch"
        assert nova_start >= 0, "nova row not found in live patch"
        # Extract the somad block (from somad_start to nova_start)
        somad_block = text[somad_start:nova_start]
        somad_allow = _extract_allow(somad_block)
        assert "write" not in somad_allow, f"O5 FAIL: somad allow still has write: {somad_allow}"
        assert "edit" not in somad_allow, f"O5 FAIL: somad allow still has edit: {somad_allow}"
        # Extract the nova block (from nova_start to end)
        nova_block = text[nova_start:]
        # Find the end of nova block (next tool-subagent or end of file)
        next_tool = nova_block.find("tool-subagent-", 1)
        if next_tool >= 0:
            nova_block = nova_block[:next_tool]
        nova_allow = _extract_allow(nova_block)
        assert "write" not in nova_allow, f"O5 FAIL: nova allow still has write: {nova_allow}"
        assert "edit" not in nova_allow, f"O5 FAIL: nova allow still has edit: {nova_allow}"


# ---------------------------------------------------------------------------
# G13 precondition — honesty
# ---------------------------------------------------------------------------

class TestG13Precondition:
    """G13 live execution must stay BLOCKED until a real DSH child exists."""

    def test_precondition_is_honest(self):
        p = _g13_precondition()
        assert "marker_set" in p
        assert "instances_mounted" in p
        assert "backend_kind" in p
        assert p["satisfied"] == p["real_dsh_child_observable"]
        assert p["satisfied"] is False
        assert p["marker_set"] is False
        assert p["all_instances_mounted"] is False
        assert p["backend_kind"] == "unavailable"

    def test_no_immunity_claim(self):
        from tests.g13.live_readiness.plan import live_test_plan
        plan = live_test_plan()
        text = (plan["title"] + " " + plan["status"]).lower()
        for banned in ("immune", "prompt-injection-proof", "injection-proof"):
            assert banned not in text


# ---------------------------------------------------------------------------
# Live runtime driver — must refuse
# ---------------------------------------------------------------------------

class TestLiveRuntimeDriver:
    """The live runtime driver must refuse live dispatch."""

    def test_availability_returns_all_false(self):
        avail = _live_driver_available()
        assert avail["all"] is False
        assert avail["d4_d7_mounted"] is False
        # baseline_policy and execution_gate_routes_writes may be True with
        # default config; signoff/approval/marker are False
        assert avail["human_signed_plan"] is False

    def test_execute_returns_blocked(self):
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        driver = LiveDSHRuntimeDriver()
        result = driver.execute("L3-TEST-001", "probe", "probe")
        assert result.final_status == "BLOCKED"
        assert result.decision in ("ERROR", "DENY")
        # Must name a missing precondition, not simulate a pass
        assert result.denial_path.startswith("live-precondition:")
        assert "human_signed_plan" in result.denial_path
        assert "d4_d7_mounted" in result.denial_path


# ---------------------------------------------------------------------------
# Claim gate — must return false
# ---------------------------------------------------------------------------

class TestClaimGate:
    """The L3 claim gate must remain false on current facts."""

    def test_claim_gate_returns_false(self):
        res = _claim_gate()
        assert res.l3_claim is False
        # Same-UID + no bundle + rehearsal (or no live runtime) = no claim
        assert any("P1-runtime" in f for f in res.failures)
        assert any("P2-uid-separation" in f for f in res.failures)


# ---------------------------------------------------------------------------
# Scope — write-scope lock
# ---------------------------------------------------------------------------

class TestScope:
    """Write-scope lock: the re-baseline writes only to its two paths."""

    def test_report_exists(self):
        report = os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "final", "rebaseline",
            "0001-live-assurance-rebaseline-report.md")
        assert os.path.isfile(report), f"Report not found at {report}"
        with open(report) as f:
            text = f.read()
        assert "BLOCKED" in text
        assert "RE-BASELINE" in text.upper() or "RE-BASELINE" in text

    def test_rebaseline_declares_no_claim(self):
        report = os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "final", "rebaseline",
            "0001-live-assurance-rebaseline-report.md")
        with open(report) as f:
            text = f.read()
        assert "l3_claim_possible=False" in text
        assert "NO CLAIM" in text.upper() or "NO L3 CLAIM" in text.upper() or \
               "ZERO CONTROLS L3" in text.upper() or "no claim" in text.lower()

    def test_audit_l3_not_created(self):
        """The re-baseline must never create the repo audit/l3 store."""
        audit_l3 = os.path.join(PROJECT_ROOT, "audit", "l3")
        assert not os.path.exists(audit_l3)

    def test_no_dsh_bridge_marker_set(self):
        """The re-baseline must never set the bridge marker."""
        import os
        marker = os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "")
        assert marker == "" or marker == "0", \
            "DSH_LIVE_BRIDGE_ACTIVE must remain unset"
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

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")
if not os.path.exists(PYTHON):
    PYTHON = sys.executable

ORCHESTRATOR_UID = os.getuid()


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
        # Only checks marked required_for_l3=True and not passed are blockers.
        # With an authorized (launch-token) browser answerer attached the
        # answerer checks PASS, leaving exactly the three independent
        # blockers; without attachment the answerer checks additionally
        # block fail-closed (composed != attached).
        from tests.environment.approval_composition import authorized_web_url
        independent = {"L3ENV-UID-2", "L3ENV-D4D7-3", "L3ENV-PLAN-REAL"}
        if authorized_web_url():
            blockers = [c for c in r.checks if c.required_for_l3 and not c.passed]
            assert len(blockers) == 3, f"Expected 3 blockers, got {len(blockers)}: {[b.check_id for b in blockers]}"
            assert {b.check_id for b in blockers} == independent
        else:
            blockers = [c for c in r.checks if c.required_for_l3 and not c.passed]
            blocked_ids = {b.check_id for b in blockers}
            for cid in independent:
                assert cid in blocked_ids, (
                    f"independent blocker {cid} missing: {sorted(blocked_ids)}")
            for cid in ("L3ENV-ANS-1", "L3ENV-ANS-2"):
                assert cid in blocked_ids, (
                    f"answerer blocker {cid} must block without attachment: "
                    f"{sorted(blocked_ids)}")


# ---------------------------------------------------------------------------
# Approval-path correction — verification
# ---------------------------------------------------------------------------

class TestApprovalCorrection:
    """The approval-path correction must be verified live: with an attached
    authorized browser answerer L3ENV-ANS-1/2 PASS; without one they block
    fail-closed."""

    def test_approval_readiness_checks_pass(self):
        from tests.environment.approval_composition import authorized_web_url
        r = _l3_readiness()
        ans1 = next((c for c in r.checks if c.check_id == "L3ENV-ANS-1"), None)
        ans2 = next((c for c in r.checks if c.check_id == "L3ENV-ANS-2"), None)
        if authorized_web_url():
            assert ans1 is not None and ans1.passed is True, \
                f"L3ENV-ANS-1 should PASS (answerer by composition), got pass={ans1.passed}"
            assert ans2 is not None and ans2.passed is True, \
                f"L3ENV-ANS-2 should PASS (approval path available), got pass={ans2.passed}"
        else:
            assert ans1 is not None and ans1.passed is False, \
                f"L3ENV-ANS-1 must fail closed without an attached answerer, got pass={ans1.passed}"
            assert ans2 is not None and ans2.passed is False, \
                f"L3ENV-ANS-2 must fail closed without an attached answerer, got pass={ans2.passed}"

    def test_approval_composition_holds(self):
        from tests.environment.approval_composition import authorized_web_url
        r = _approval_readiness()
        assert r.composed is True
        assert r.approval_service_composed is True
        assert r.answerer_surface_composed is True
        assert r.web_session is True
        assert r.effective_policy == "ask"
        if authorized_web_url():
            assert r.interactive_ready is True
            # 2026-09-07: a real approval has since flowed through the Web GUI
            # (sanctioned escalation of the zeko live-row edit), so the ladder
            # may legitimately sit at E2E_VERIFIED (strictly above
            # INTERACTIVE_READY; both require full composition).
            assert r.status.value in ("APPROVAL_INTERACTIVE_READY",
                                      "APPROVAL_E2E_VERIFIED")
        else:
            # Fail-closed: composed but unattached — never promoted.
            assert r.interactive_ready is False
            assert r.status.value == "APPROVAL_COMPOSED"

    def test_e2e_status_matches_session_log_not_pinned(self):
        r = _approval_readiness()
        # E2E status is session-log-derived, never pinned: UNKNOWN only while
        # no approval/asked + approval/decided pair is in the CURRENT session
        # log (composition readiness != E2E verification); PASS exactly when
        # a re-derivable pair exists. First observed PASS: 2026-09-07.
        assert r.e2e_status == ("PASS" if r.e2e_pair else "UNKNOWN"), \
            f"e2e_status {r.e2e_status!r} inconsistent with pair presence"
        assert r.e2e_verified is bool(r.e2e_pair)
        assert r.probe_answered is bool(r.e2e_pair)
        if r.e2e_status == "PASS":
            assert r.e2e_pair.get("outcome"), (
                "E2E pair must carry a closed-vocabulary outcome")

    def test_e2e_pair_empty_iff_unknown(self):
        r = _approval_readiness()
        assert (r.e2e_pair == {}) == (r.e2e_status == "UNKNOWN")


# ---------------------------------------------------------------------------
# O5 containment — verification
# ---------------------------------------------------------------------------

class TestO5ContainmentApplied:
    """O5 must be applied: somad/nova have no write/edit in the composed
    delegation rows (orchestrator/agent.cordis.yml)."""

    def test_orchestrator_composition_somad_nova_no_write_edit(self):
        """The composed somad/nova delegation rows carry no write/edit.

        The 15 `tool-subagent-<id>` rows moved out of the live profile patch
        ($DSH_HOME/profiles/web/cordis.patch.yml) into
        `orchestrator/agent.cordis.yml` on 2026-10-11, so the O5 containment
        fact is asserted against the composition that actually carries the
        rows. They are PARSED as YAML, not text-scanned: the old text scan of
        the patch silently matched nothing once the rows moved (an empty
        section trivially "passes"), which is exactly the failure shape this
        rewrite removes.

        `todo_write` is a permitted tool and contains the substring 'write';
        the check reads exact tool names from the parsed allow list, so
        `todo_write` does not trip it. Containment is both-sided: write/edit
        absent from allow AND named in deny (the read-only-roles contract).
        """
        import yaml
        from tests.d4d7_composition import preset_tool_surface
        with open(os.path.join(PROJECT_ROOT, "config",
                               "role-preset-mapping.yaml")) as f:
            mapping = yaml.safe_load(f)
        surfaces = {r["id"]: r["tool_surface"] for r in mapping["roles"]}
        for rid in ("somad", "nova"):
            allow = preset_tool_surface(f"role-{rid}")
            deny = set(surfaces[rid]["deny"] or [])
            assert "write" not in allow, f"O5 FAIL: {rid} allow still has write: {sorted(allow)}"
            assert "edit" not in allow, f"O5 FAIL: {rid} allow still has edit: {sorted(allow)}"
            assert {"write", "edit"} <= deny, (
                f"O5 FAIL: {rid} deny must name write+edit: {sorted(deny)}")


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
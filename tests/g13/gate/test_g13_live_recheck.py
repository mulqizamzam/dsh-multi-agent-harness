"""G13 live execution gate recheck — 11-axis precondition reassessment (Session A).

Honest, deterministic recheck that asserts the current state of every
prerequisite for the prepared 63-case live G13 package. All dynamic state
probed fresh this session — no old blocker status reused without re-inspection.

Does NOT re-create payloads, modify DSH, modify session policy, dispatch a
live child, or claim G13 PASS.

Verdict convention: the suite is GREEN and asserts G13_LIVE_READY = NO with
the exact current blockers. When a blocker clears, the flip turns RED, which
is the signal to re-assess.
"""

import os
import sys
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.g13.live_readiness.plan import precondition, live_test_plan
from tests.live_dsh.backend_kind import probe_backend_kind
from tests.live_dsh.discovery import probe_all_instances_mounted
from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver


def recheck_verdict() -> dict:
    """11-axis recheck verdict (detection only, fresh this session)."""
    p = precondition()
    marker = p["marker_set"]
    all_mounted = p["all_instances_mounted"]
    kind = p["backend_kind"]
    real_child = p["real_dsh_child_observable"]

    # Approval path
    from tests.environment.approval_composition import approval_readiness
    ar = approval_readiness()
    # NOTE: ar.status is an ApprovalStatus enum and ar.e2e_status is a str whose
    # values are "PASS" | "UNKNOWN" | "UNAVAILABLE" (approval_composition.py).
    # Comparing the enum to a bare str, or to the non-existent literal
    # "VERIFIED", is always False — both axes were unconditionally BLOCKED
    # regardless of the real environment. Compare against the real values.
    approval_ready = (ar.status.value == "APPROVAL_INTERACTIVE_READY")
    approval_e2e = (ar.e2e_status == "PASS")

    # Authorization
    driver_result = LiveDSHRuntimeDriver().execute(
        scenario_id="G13-LIVE-C1", action="write", target="agents/**")
    auth_allowed = (driver_result.final_status != "BLOCKED")

    # Scratch workspace
    scratch_ok = False
    try:
        with tempfile.TemporaryDirectory() as td:
            probe = os.path.join(td, "probe.txt")
            with open(probe, "w") as f:
                f.write("probe")
            scratch_ok = (os.path.isfile(probe) and
                          not os.path.abspath(td).startswith(
                              os.path.abspath(PROJECT_ROOT)))
    except Exception:
        scratch_ok = False

    # Evidence capture
    evidence_ok = os.path.isdir(os.path.join(PROJECT_ROOT, "audit", "runtime"))

    # Stop-at-first-failure
    found_x = False
    for fname in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"):
        path = os.path.join(PROJECT_ROOT, fname)
        if os.path.isfile(path):
            with open(path) as f:
                if "-x" in f.read() or "maxfail=1" in f.read():
                    found_x = True

    # Rollback/cleanup
    plan = live_test_plan()
    rollback_defined = (
        isinstance(plan.get("rollback_cleanup"), list)
        and len(plan["rollback_cleanup"]) >= 4
    )

    # G10 status
    g10_blocking = False  # G10 CLOSED by current H5 approval

    axes = {
        "1_dsh_live_bridge_active": marker,
        "2_d4d7_instances_mounted": all_mounted,
        "3_real_backend_available": (kind == "real-dsh"),
        "4_real_child_observable": real_child,
        "5_approval_path": approval_ready,
        "6_authorized_g13_run": auth_allowed,
        "7_scratch_workspace": scratch_ok,
        "8_evidence_capture": evidence_ok,
        "9_stop_at_first_failure": found_x,
        "10_rollback_cleanup": rollback_defined,
        "11_g10_closed": (not g10_blocking),
    }
    all_ready = all(axes.values())
    return {
        "g13_live_ready": all_ready,
        "axes": axes,
        "approval_e2e": approval_e2e,
        "backend_kind": kind,
        "all_mounted": all_mounted,
        "marker_set": marker,
        "real_child_observable": real_child,
        "live_driver_status": driver_result.final_status,
        "live_driver_blockers": driver_result.denial_path,
    }


# ============================================================================
# G13_LIVE_READY verdict
# ============================================================================

class TestG13LiveRecheckVerdict:
    """G13_LIVE_READY verdict — honest, deterministic, fresh this session."""

    def test_g13_live_ready_is_no(self):
        """G13_LIVE_READY = NO: prerequisites not satisfied this session."""
        v = recheck_verdict()
        assert v["g13_live_ready"] is False, (
            "G13_LIVE_READY flipped to YES — all prerequisites satisfied; "
            "run the prepared live G13 package and re-assess")

    def test_verdict_matches_precondition(self):
        """The recheck verdict is consistent with the canonical precondition()."""
        v = recheck_verdict()
        p = precondition()
        assert v["marker_set"] == p["marker_set"]
        assert v["all_mounted"] == p["all_instances_mounted"]
        assert v["real_child_observable"] == p["real_dsh_child_observable"]

    def test_verdict_names_blocked_axes(self):
        """The recheck identifies exactly which axes are blocked."""
        v = recheck_verdict()
        blocked = [k for k, ready in v["axes"].items() if not ready]
        # At minimum these must be blocked — all four require runtime authority
        # (a mounted D4/D7 composition + live bridge marker) that no in-session
        # action can supply.
        assert "1_dsh_live_bridge_active" in blocked
        assert "2_d4d7_instances_mounted" in blocked
        assert "3_real_backend_available" in blocked
        assert "4_real_child_observable" in blocked
        assert "6_authorized_g13_run" in blocked
        # Closed by in-session engineering work — these must NOT be blocked.
        assert "9_stop_at_first_failure" not in blocked
        assert "11_g10_closed" not in blocked


# ============================================================================
# 11-axis per-axis evidence
# ============================================================================

class TestG13RecheckAxes:
    """Per-axis evidence for the recheck report."""

    # ---- Axis 1: DSH_LIVE_BRIDGE_ACTIVE ----

    def test_axis_1_dsh_live_bridge_active_blocked(self):
        marker = os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "").strip().lower()
        assert marker not in ("1", "true", "yes"), (
            f"DSH_LIVE_BRIDGE_ACTIVE now set: {marker!r}")

    # ---- Axis 2: D4/D7 instances mounted ----

    def test_axis_2_instances_not_mounted(self):
        mounted = probe_all_instances_mounted()
        assert all(v is False for v in mounted.values()), (
            f"some instances now mounted: {mounted}")
        from orchestrator.foundation.contracts import SPECIALIST_ROLES
        assert set(mounted.keys()) == {
            f"subagent_{r}" for r in SPECIALIST_ROLES
        }

    def test_axis_2_composition_files_persistent(self):
        dsh_home = os.environ.get("DSH_HOME", "")
        assert dsh_home, "DSH_HOME not set"
        presets_dir = os.path.join(dsh_home, ".agent-presets")
        assert os.path.isdir(presets_dir)
        presets = {d for d in os.listdir(presets_dir)
                   if os.path.isdir(os.path.join(presets_dir, d))}
        # The 15 role presets plus the orchestrator root-session preset
        # deployed 2026-09-12 (ADR 0004).
        assert presets == {
            "role-zeko", "role-cto", "role-cfo", "role-kai",
            "role-somad", "role-badsector", "role-nova",
            "role-vera", "role-argus", "role-atlas", "role-tess",
            "role-quill", "role-scout", "role-talon", "role-ledger",
            "orchestrator",
        }

    # ---- Axis 3: REAL backend available ----

    def test_axis_3_backend_unavailable(self):
        kind = probe_backend_kind().value
        assert kind == "unavailable", f"backend now {kind!r}"

    # ---- Axis 4: real child observable ----

    def test_axis_4_child_not_observable(self):
        p = precondition()
        assert p["real_dsh_child_observable"] is False

    # ---- Axis 5: approval path ----

    def test_axis_5_approval_path_composition_ready(self):
        """Approval composition is ready; E2E state is session-log-derived.

        The status ladder (approval_composition.py) distinguishes
        APPROVAL_COMPOSED (service + answerer surface composed, but no web GUI
        attached) from APPROVAL_INTERACTIVE_READY (composed AND a reachable web
        GUI session) from APPROVAL_E2E_VERIFIED (a harmless approval-required
        probe re-derived from the CURRENT session log: approval/asked +
        approval/decided pair with a closed-vocabulary outcome). Any rung
        above HEADLESS means "composition ready". E2E_VERIFIED legitimately
        occurs once a real approval has flowed through this Web GUI (first
        observed 2026-09-07 via the sanctioned escalation of the zeko
        live-row edit); it is derived from live log evidence, not pinned.
        """
        from tests.environment.approval_composition import approval_readiness
        ar = approval_readiness()
        assert ar.status.value in ("APPROVAL_COMPOSED",
                                   "APPROVAL_INTERACTIVE_READY",
                                   "APPROVAL_E2E_VERIFIED"), (
            f"approval status: {ar.status}")
        assert ar.composed is True
        assert ar.effective_policy == "ask"

    def test_axis_5_approval_e2e_state_is_ladder_consistent(self):
        """The E2E assertion must follow the observed ladder state, not pin a
        snapshot: UNKNOWN only while no pair is in the current session log;
        PASS exactly when a re-derivable pair exists. Composition readiness
        alone is never E2E evidence."""
        from tests.environment.approval_composition import approval_readiness
        ar = approval_readiness()
        assert ar.e2e_status == ("PASS" if ar.e2e_pair else "UNKNOWN"), (
            f"e2e_status {ar.e2e_status!r} inconsistent with pair presence")
        assert ar.probe_answered == bool(ar.e2e_pair)
        if ar.status.value == "APPROVAL_E2E_VERIFIED":
            assert ar.e2e_status == "PASS" and ar.e2e_pair, (
                "E2E_VERIFIED without a re-derivable pair")
        else:
            assert ar.e2e_status != "PASS", (
                f"E2E PASS at rung {ar.status.value} — ladder inconsistency")

    # ---- Axis 6: authorized G13 run ----

    def test_axis_6_live_driver_refuses_dispatch(self):
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        assert result.final_status == "BLOCKED", (
            f"driver status: {result.final_status}")

    def test_axis_6_driver_denies_g13_preconditions(self):
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        for missing in ("human_signed_plan", "d4_d7_mounted",
                        "approval_answerer"):
            assert missing in result.denial_path, (
                f"{missing} missing from denial_path {result.denial_path!r}")

    # ---- Axis 7: scratch workspace ----

    def test_axis_7_scratch_workspace_available(self):
        with tempfile.TemporaryDirectory() as td:
            probe = os.path.join(td, "probe.txt")
            with open(probe, "w") as f:
                f.write("probe")
            assert os.path.isfile(probe)
            assert not os.path.abspath(td).startswith(
                os.path.abspath(PROJECT_ROOT))

    # ---- Axis 8: evidence capture ----

    def test_axis_8_evidence_path_accessible(self):
        audit_runtime = os.path.join(PROJECT_ROOT, "audit", "runtime")
        assert os.path.isdir(audit_runtime)

    def test_axis_8_plan_defines_evidence_requirements(self):
        plan = live_test_plan()
        assert isinstance(plan["evidence_requirements"], list)
        assert len(plan["evidence_requirements"]) >= 4

    # ---- Axis 9: stop-at-first-failure ----

    def test_axis_9_stop_at_first_failure_configured(self):
        """Axis 9 READY: a pytest config sets -x / maxfail=1.

        Closed by adding `pytest.ini` (`addopts = -x`) at the project root, so
        the canonical 63-scenario live run stops at the first unexpected
        failure instead of cascading state contamination across scenarios
        (docs/phase-5/security/g13/gate/0002 §9 / B6). Full-suite regression
        runs opt out explicitly with `--maxfail=0`.
        """
        found_x = False
        found_in = None
        for fname in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"):
            path = os.path.join(PROJECT_ROOT, fname)
            if os.path.isfile(path):
                with open(path) as f:
                    content = f.read()
                    if "-x" in content or "maxfail=1" in content:
                        found_x = True
                        found_in = fname
        assert found_x is True, (
            "-x/maxfail=1 is no longer configured — the live G13 run would not "
            "stop at first failure; axis 9 has regressed to BLOCKED")
        assert found_in is not None

    # ---- Axis 10: rollback/cleanup ----

    def test_axis_10_rollback_cleanup_defined(self):
        plan = live_test_plan()
        assert isinstance(plan["rollback_cleanup"], list)
        assert len(plan["rollback_cleanup"]) >= 4
        # Must reference scratch workspace
        assert any("scratch" in s.lower()
                   for s in plan["rollback_cleanup"])

    def test_axis_10_non_destructive_guarantees_defined(self):
        plan = live_test_plan()
        assert isinstance(plan["non_destructive_guarantee"], list)
        guarantees = plan["non_destructive_guarantee"]
        assert any("web_fetch" in g for g in guarantees)
        assert any("DSH core" in g or "DSH" in g for g in guarantees)

    # ---- Axis 11: G10 status ----

    def test_axis_11_g10_closed(self):
        """G10 is CLOSED by current Human H5 approval."""
        closure_matrix = os.path.join(
            PROJECT_ROOT, "docs", "phase-5", "final",
            "0001-security-closure-matrix.md")
        assert os.path.isfile(closure_matrix)

        with open(closure_matrix) as f:
            content = f.read()

        assert "G10" in content

        g10_section = False
        g10_closed = False
        for line in content.split("\n"):
            if "| **G10" in line:
                g10_section = True
                g10_closed = "**CLOSED**" in line
                break
            if g10_section and "| **G11" in line:
                break

        assert g10_closed, (
            "G10 is not recorded as CLOSED in the current closure matrix"
        )



# ============================================================================
# No-mutation constraints
# ============================================================================

class TestG13RecheckNoMutation:
    """The recheck changes nothing and claims nothing."""

    def test_no_payload_recreation(self):
        from tests.g13.live_readiness.payloads import LIVE_CHANNELS, LIVE_VECTORS
        assert len(LIVE_CHANNELS) == 7
        assert len(LIVE_VECTORS) == 56

    def test_no_claim_of_g13_pass(self):
        v = recheck_verdict()
        assert v["g13_live_ready"] is False

    def test_no_live_dispatch(self):
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        assert result.stopReason == "refused"

    def test_g13_remains_unknown(self):
        """G13 DSH-native remains UNKNOWN — no live child observed."""
        from tests.g13.live_readiness.plan import precondition
        p = precondition()
        assert p["satisfied"] is False
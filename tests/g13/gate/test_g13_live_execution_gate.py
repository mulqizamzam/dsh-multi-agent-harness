"""G13 live execution gate — 8-axis precondition check.

Deterministic gate tests that honestly record the current state of every
prerequisite the prepared 63-case live G13 package requires. They do NOT
re-create payloads, modify DSH, modify session policy, dispatch a live child,
or claim G13 PASS.

Verdict convention (matches tests/g13/live_readiness/test_live_readiness.py):
the suite is GREEN and asserts G13_PRECONDITION = BLOCKED with the exact
blocked axes, exactly as the live_readiness honesty gate asserts the
precondition is not satisfied. When a blocked axis becomes satisfied, its
assertion flips and the gate turns RED — that is the signal to re-assess.
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


def gate_verdict() -> dict:
    """Per-axis status + overall G13_PRECONDITION verdict (detection only)."""
    p = precondition()
    marker = p["marker_set"]
    all_mounted = p["all_instances_mounted"]
    kind = p["backend_kind"]

    # Axis 7: stop-at-first-failure — no pytest config sets -x / maxfail=1.
    found_x = False
    for fname in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"):
        path = os.path.join(PROJECT_ROOT, fname)
        if os.path.isfile(path):
            with open(path) as f:
                if "-x" in f.read() or "maxfail=1" in f.read():
                    found_x = True

    from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
    driver_result = LiveDSHRuntimeDriver().execute(
        scenario_id="G13-LIVE-C1", action="write", target="agents/**")
    auth_allowed = driver_result.final_status != "BLOCKED"

    axes = {
        "1_real_dsh_child_observable": "BLOCKED" if not p["real_dsh_child_observable"] else "READY",
        "2_d4d7_mounted": "BLOCKED" if not all_mounted else "READY",
        "3_dsh_live_bridge_active": "BLOCKED" if not marker else "READY",
        "4_backend_kind": "BLOCKED" if kind != "real-dsh" else "READY",
        "5_scratch_workspace": "READY",      # verified below in its own test
        "6_evidence_capture": "READY",       # verified below in its own test
        "7_stop_at_first_failure": "BLOCKED" if not found_x else "READY",
        "8_authorization": "BLOCKED" if not auth_allowed else "READY",
    }
    verdict = ("READY" if all(v == "READY" for v in axes.values()) else "BLOCKED")
    return {"verdict": verdict, "axes": axes,
            "satisfied": p["satisfied"],
            "marker_set": marker, "all_instances_mounted": all_mounted,
            "backend_kind": kind}


class TestG13LiveExecutionGateVerdict:
    """G13_PRECONDITION verdict — honest, deterministic."""

    def test_g13_precondition_blocked_this_session(self):
        """G13_PRECONDITION = BLOCKED: prerequisites not satisfied now.

        Mirrors test_live_readiness.py::test_precondition_not_satisfied_this_session.
        If a REAL DSH child becomes observable, run the prepared live package
        and re-assess (this assertion flips RED).
        """
        p = precondition()
        assert p["satisfied"] is False, (
            "precondition satisfied — a REAL DSH child is observable; "
            "run the prepared live G13 package and re-assess the gate")

    def test_gate_verdict_blocked(self):
        """The 8-axis gate verdict is BLOCKED this session."""
        v = gate_verdict()
        assert v["verdict"] == "BLOCKED", f"unexpected verdict: {v}"
        blocked = [k for k, s in v["axes"].items() if s == "BLOCKED"]
        # Exactly the 5 remaining blocked axes are named. Axis 7
        # (stop-at-first-failure) was closed by adding pytest.ini
        # (addopts = -x); the rest require runtime/authorization authority
        # that no in-session action can supply.
        assert blocked == [
            "1_real_dsh_child_observable",
            "2_d4d7_mounted",
            "3_dsh_live_bridge_active",
            "4_backend_kind",
            "8_authorization",
        ], f"unexpected blocked axes: {blocked}"


class TestG13LiveExecutionGateAxes:
    """Per-axis evidence for the gate report."""

    # ---- Axis 1: REAL DSH child observable ----

    def test_axis_1_blocked(self):
        p = precondition()
        assert p["real_dsh_child_observable"] is False, (
            "real_dsh_child_observable flipped to True")

    # ---- Axis 2: D4/D7 mounted ----

    def test_axis_2_blocked(self):
        p = precondition()
        assert p["all_instances_mounted"] is False
        from orchestrator.foundation.contracts import SPECIALIST_ROLES
        assert set(p["instances_mounted"].keys()) == {
            f"subagent_{r}" for r in SPECIALIST_ROLES
        }

    def test_axis_2_d4d7_composition_files_persistent(self):
        """The composition files persist; the live bridge does not
        (per-session mount).

        2026-10-10/11 cutover: the 16 presets are registered DIRECTLY from
        this repo by the dsh-multi-agent-harness plugin (the
        `$DSH_HOME/.agent-presets/` deployment copy is retired), and the 15
        `tool-subagent-<id>` delegation rows are composed in
        `orchestrator/agent.cordis.yml` (moved out of the live profile
        patch). "Files persist" is therefore a property of the repo sources
        the live profile links — checked here as source presence plus the
        composed row set, not as a deployed-copy listing.
        """
        from tests.d4d7_composition import (
            ALL_PRESETS,
            orchestrator_subagent_rows,
            preset_source_report,
        )
        from orchestrator.foundation.contracts import SPECIALIST_ROLES
        ok, missing = preset_source_report()
        assert ok, f"missing composition sources: {missing}"
        assert len(ALL_PRESETS) == 16
        rows = orchestrator_subagent_rows()
        expected = {f"subagent_{r}" for r in SPECIALIST_ROLES}
        assert expected <= set(rows), (
            f"rows not composed in orchestrator/agent.cordis.yml: "
            f"{sorted(expected - set(rows))}")

    # ---- Axis 3: DSH_LIVE_BRIDGE_ACTIVE ----

    def test_axis_3_blocked(self):
        marker = os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "").strip().lower()
        assert marker not in ("1", "true", "yes"), (
            f"DSH_LIVE_BRIDGE_ACTIVE now set: {marker!r}")

    # ---- Axis 4: Backend kind ----

    def test_axis_4_blocked(self):
        kind = probe_backend_kind().value
        assert kind != "real-dsh", (
            f"backend kind flipped to {kind!r} — re-assess the gate")

    def test_axis_4_backend_kind_reports_unavailable(self):
        """Backend kind honestly reports `unavailable` this session."""
        kind = probe_backend_kind().value
        assert kind == "unavailable"

    # ---- Axis 5: Scratch workspace ----

    def test_axis_5_scratch_workspace_available(self):
        """Axis 5 READY: a scratch workspace outside the repo tree is usable."""
        with tempfile.TemporaryDirectory() as td:
            probe = os.path.join(td, "probe.txt")
            with open(probe, "w") as f:
                f.write("probe")
            assert os.path.isfile(probe)
            # scratch must not be inside the repo tree
            assert not os.path.abspath(td).startswith(
                os.path.abspath(PROJECT_ROOT))

    def test_axis_5_plan_defines_scratch_workspace(self):
        plan = live_test_plan()
        assert any("scratch" in s.lower() for s in plan["rollback_cleanup"])

    # ---- Axis 6: Evidence capture ----

    def test_axis_6_evidence_path_accessible(self):
        """Axis 6 READY: audit/runtime/ exists for evidence bundles."""
        audit_runtime = os.path.join(PROJECT_ROOT, "audit", "runtime")
        assert os.path.isdir(audit_runtime)

    def test_axis_6_plan_defines_evidence_requirements(self):
        plan = live_test_plan()
        assert isinstance(plan["evidence_requirements"], list)
        assert len(plan["evidence_requirements"]) >= 4

    def test_axis_6_payloads_have_evidence_requirements(self):
        from tests.g13.live_readiness.payloads import LIVE_CHANNELS, LIVE_VECTORS
        for sid, ch in LIVE_CHANNELS.items():
            assert isinstance(ch["evidence_requirements"], list)
            assert len(ch["evidence_requirements"]) >= 3
        for v in LIVE_VECTORS:
            assert isinstance(v["evidence_requirements"], list)
            assert len(v["evidence_requirements"]) >= 2

    # ---- Axis 7: Stop-at-first-failure ----

    def test_axis_7_ready(self):
        """Axis 7 READY: a pytest config sets -x / maxfail=1.

        A live security test must stop at first failure to avoid cascading
        state contamination across scenarios. This axis was BLOCKED until
        `pytest.ini` (`addopts = -x`) was added at the project root, satisfying
        the gate requirement (docs/phase-5/security/g13/gate/0001 §7).
        Full-suite regression runs opt out explicitly with `--maxfail=0`.
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
            "stop at first failure; axis 7 has regressed to BLOCKED")
        assert found_in is not None

    # ---- Axis 8: Authorization ----

    def test_axis_8_live_driver_refuses_dispatch(self):
        """Axis 8 BLOCKED: LiveDSHRuntimeDriver refuses live dispatch."""
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        assert result.final_status == "BLOCKED", (
            "LiveDSHRuntimeDriver no longer BLOCKED — re-assess the gate")

    def test_axis_8_driver_names_missing_preconditions(self):
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        for missing in ("human_signed_plan", "d4_d7_mounted",
                        "approval_answerer"):
            assert missing in result.denial_path, (
                f"{missing} absent from denial_path {result.denial_path!r}")


class TestG13LiveExecutionGateNoMutation:
    """The gate changes nothing and claims nothing."""

    def test_no_payload_recreation(self):
        """The gate does not re-create the 63 payload fixtures."""
        from tests.g13.live_readiness.payloads import LIVE_CHANNELS, LIVE_VECTORS
        assert len(LIVE_CHANNELS) == 7
        assert len(LIVE_VECTORS) == 56  # unchanged, canonical count

    def test_no_claim_of_g13_pass(self):
        """No G13 PASS claim is made by the gate."""
        v = gate_verdict()
        assert v["verdict"] == "BLOCKED"
        assert v["satisfied"] is False

    def test_no_live_dispatch(self):
        """No live child is dispatched by the gate."""
        from tests.l3_runner.runtime_driver import LiveDSHRuntimeDriver
        result = LiveDSHRuntimeDriver().execute(
            scenario_id="G13-LIVE-C1", action="write", target="agents/**")
        assert result.stopReason == "refused"
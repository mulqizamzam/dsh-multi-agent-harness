# tests/orchestrator/entrypoint/test_entry_live_dispatch.py — Front Door live_dispatch
# threading (Phase 5 / Front Door V1).
#
# Proves that the explicit ``live_dispatch`` parameter is correctly threaded
# through the full front-door chain:
#
#   run_from_chat
#   → run_front_door
#   → ProductionRun.run
#   → BoundedExecutor.execute
#   → ExecutionFlow
#   → RealDSHBackend  (REAL)  /  FakeSubagentBackend  (FAKE)
#
# Tests:
#   1. LOCAL MODE — no live_dispatch → FakeSubagentBackend (COMPLETE).
#   2. LIVE MODE   — stub live_dispatch + D4/D7 marker → RealDSHBackend
#      (COMPLETE, real run_id in provenance).
#   3. LIVE UNAVAILABLE — live_dispatch injected but no marker → BLOCKED
#      (BridgeNotAvailable, no silent fallback to fake).
#   4. THREADING via ProductionRun/BoundedExecutor: backend_kind observable.
#
# RULES (unchanged from existing V1 front-door + G1):
#   - explicit live mode only
#   - no silent FAKE fallback when live is requested
#   - live unavailable → BLOCKED
#   - local mode keeps existing FakeSubagentBackend
#   - no authority change, no DSH/core/session-policy change, no role change,
#     no G10/O3 changes

import os

import pytest

from _helpers import make_delegation

from orchestrator.entrypoint import COMPLETE, BLOCKED, run_from_chat
from orchestrator.production import ProductionRun, BoundedExecutor, ProductionDenied
from orchestrator.runtime import MemoryDelegationProvider
from orchestrator.dsh import (
    BackendKind,
    DSHBridgeResponse,
    BRIDGE_MARKER_ENV,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_dispatch(role="kai", run_id="real-run-0001"):
    """Build a stub dispatch function that records calls and returns a
    DSHBridgeResponse with a valid structured TaskResult for the delegated
    role."""
    calls = []
    def dispatch(invocation, instance):
        calls.append({
            "invocation": invocation.to_dict(),
            "instance_role": getattr(instance, "role", ""),
            "instance_tool": getattr(instance, "tool_name", ""),
        })
        inst_role = getattr(instance, "role", role)
        return DSHBridgeResponse(
            run_id=run_id,
            output="task completed",
            structured={
                "task_id": f"task-1:{inst_role}",
                "assigned_role": inst_role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": [f"{inst_role}: stub analysis complete"],
                "evidence": ["artifact:test"],
                "recommendation": "proceed",
                "reported_at": "2026-09-01T00:00:00Z",
            },
        )
    return dispatch, calls


def _provider(delegation):
    return MemoryDelegationProvider(delegation)


# ======================================================================
# Front-door-level tests
# ======================================================================

class TestLocalMode:
    """No live_dispatch → FakeSubagentBackend (local default)."""

    def test_completes_without_live_dispatch(self, ws, delegation):
        """run_from_chat without live_dispatch → COMPLETE via the default
        FakeSubagentBackend (local mode)."""
        result = run_from_chat(
            "research",
            ("docs/notes.md",),
            delegation.id,
            base=ws,
            provider=_provider(delegation),
        )
        assert result.status == COMPLETE
        assert result.run_id is not None
        assert result.state is not None
        assert result.state["outcome"] == "complete"
        assert result.report is not None

    def test_backend_kind_fake_observable(self, ws, delegation):
        """BoundedExecutor.last_flow.probe_backend() shows FAKE when no
        live_dispatch is injected."""
        executor = BoundedExecutor(base=ws)
        run = ProductionRun(base=ws, executor=executor)
        state = run.run(
            objective="research",
            scope=("docs/notes.md",),
            required_authority_context=delegation.id,
            delegation=delegation,
            provider=_provider(delegation),
        )
        assert state.outcome == "complete"
        assert executor.last_flow is not None
        probe = executor.last_flow.probe_backend()
        assert probe["backend_kind"] == BackendKind.FAKE.value
        assert probe["live_dispatch_injected"] is False


class TestLiveMode:
    """Stub live_dispatch + bridge marker → RealDSHBackend (COMPLETE)."""

    def test_completes_with_real_backend(self, ws, delegation):
        """run_from_chat with stub live_dispatch + marker set → COMPLETE via
        RealDSHBackend. Real child run_id captured in provenance."""
        dispatch, calls = _stub_dispatch(role="kai", run_id="real-run-0001")
        os.environ[BRIDGE_MARKER_ENV] = "1"
        try:
            result = run_from_chat(
                "research",
                ("docs/notes.md",),
                delegation.id,
                base=ws,
                provider=_provider(delegation),
                live_dispatch=dispatch,
            )
        finally:
            os.environ.pop(BRIDGE_MARKER_ENV, None)

        assert result.status == COMPLETE, f"errors: {result.errors}"
        assert result.run_id is not None
        assert result.state is not None
        assert result.state["outcome"] == "complete"
        assert result.report is not None

        # The stub dispatch was called exactly once (one role: kai).
        assert len(calls) == 1, f"dispatch was called {len(calls)} times"
        assert calls[0]["instance_role"] == "kai"
        assert calls[0]["instance_tool"] == "subagent_kai"

        # Real child run_id captured in provenance within the flow result.
        flow_result = result.state["flow_result"]
        assert flow_result["outcome"] == "COMPLETE"
        assert len(flow_result["results"]) == 1
        provenance = flow_result["results"][0].get("provenance", {})
        assert provenance.get("run_id") == "real-run-0001", \
            f"expected real-run-0001, got {provenance.get('run_id')!r}"
        assert provenance.get("role") == "kai"
        assert provenance.get("tool_name") == "subagent_kai"

    def test_backend_kind_real_observable(self, ws, delegation):
        """BoundedExecutor.last_flow.probe_backend() shows REAL when
        live_dispatch is injected + marker set."""
        dispatch, _ = _stub_dispatch(role="kai")
        provider = MemoryDelegationProvider(delegation)
        executor = BoundedExecutor(base=ws, live_dispatch=dispatch)
        os.environ[BRIDGE_MARKER_ENV] = "1"
        try:
            run = ProductionRun(base=ws, executor=executor)
            state = run.run(
                objective="research",
                scope=("docs/notes.md",),
                required_authority_context=delegation.id,
                delegation=delegation,
                provider=provider,
            )
            assert state.outcome == "complete", state.errors
            assert executor.last_flow is not None
            probe = executor.last_flow.probe_backend()
            assert probe["backend_kind"] == BackendKind.REAL.value
            assert probe["live_dispatch_injected"] is True
            assert probe["bridge_marker_active"] is True
        finally:
            os.environ.pop(BRIDGE_MARKER_ENV, None)


class TestLiveUnavailable:
    """Live dispatch injected but bridge marker absent → BLOCKED (fail-closed,
    no silent fallback to fake)."""

    def test_blocked_when_marker_absent(self, ws, delegation):
        """run_from_chat with live_dispatch but no marker → BLOCKED with
        BridgeNotAvailable error (no silent fake fallback)."""
        os.environ.pop(BRIDGE_MARKER_ENV, None)

        dispatch, _ = _stub_dispatch(role="kai")
        result = run_from_chat(
            "research",
            ("docs/notes.md",),
            delegation.id,
            base=ws,
            provider=_provider(delegation),
            live_dispatch=dispatch,
        )

        assert result.status == BLOCKED
        # The flow stopped at the backend availability gate.
        assert result.run_id is not None
        assert result.state is not None
        assert result.state["outcome"] == "stopped"
        error_text = " ".join(result.errors).lower()
        assert "bridge" in error_text or "unavailable" in error_text, \
            f"expected BridgeNotAvailable error, got {result.errors}"

    def test_backend_kind_unavailable_observable(self, ws, delegation):
        """A run with live_dispatch injected + marker absent raises
        ProductionDenied (BridgeNotAvailable) — the probe would show
        UNAVAILABLE."""
        os.environ.pop(BRIDGE_MARKER_ENV, None)

        dispatch, _ = _stub_dispatch(role="kai")
        provider = MemoryDelegationProvider(delegation)
        executor = BoundedExecutor(base=ws, live_dispatch=dispatch)
        run = ProductionRun(base=ws, executor=executor)
        with pytest.raises(ProductionDenied) as excinfo:
            run.run(
                objective="research",
                scope=("docs/notes.md",),
                required_authority_context=delegation.id,
                delegation=delegation,
                provider=provider,
            )
        msg = str(excinfo.value).lower()
        assert "bridge" in msg or "unavailable" in msg or "live_bridge" in msg, \
            f"expected BridgeNotAvailable, got: {excinfo.value}"

    def test_no_silent_fallback(self, ws, delegation):
        """When live_dispatch is injected but bridge is unavailable, the flow
        blocks — the stub dispatch is NEVER called (no silent fake fallback,
        no real dispatch either)."""
        os.environ.pop(BRIDGE_MARKER_ENV, None)

        dispatch, calls = _stub_dispatch(role="kai", run_id="no-fallback")

        result = run_from_chat(
            "research",
            ("docs/notes.md",),
            delegation.id,
            base=ws,
            provider=_provider(delegation),
            live_dispatch=dispatch,
        )

        assert result.status == BLOCKED
        error_text = " ".join(result.errors).lower()
        assert "bridge" in error_text or "unavailable" in error_text, \
            f"expected BridgeNotAvailable, got {result.errors}"
        # The stub dispatch was never called (fail-closed).
        assert len(calls) == 0, \
            f"dispatch was called {len(calls)} times but should be 0 " \
            f"(fail-closed, no silent fallback)"


class TestLiveDispatchThreading:
    """Threading verified at the ProductionRun / BoundedExecutor level."""

    def test_live_dispatch_via_constructor(self, ws, delegation):
        """live_dispatch passed to ProductionRun constructor flows to
        ExecutionFlow."""
        dispatch, calls = _stub_dispatch(role="kai", run_id="ctor-flow")
        provider = MemoryDelegationProvider(delegation)
        os.environ[BRIDGE_MARKER_ENV] = "1"
        try:
            run = ProductionRun(base=ws, live_dispatch=dispatch)
            state = run.run(
                objective="research",
                scope=("docs/notes.md",),
                required_authority_context=delegation.id,
                delegation=delegation,
                provider=provider,
            )
        finally:
            os.environ.pop(BRIDGE_MARKER_ENV, None)

        assert state.outcome == "complete", state.errors
        assert len(calls) == 1

    def test_live_dispatch_via_run_param(self, ws, delegation):
        """live_dispatch passed to ProductionRun.run() threads to the flow."""
        dispatch, calls = _stub_dispatch(role="kai")
        provider = MemoryDelegationProvider(delegation)
        os.environ[BRIDGE_MARKER_ENV] = "1"
        try:
            run = ProductionRun(base=ws)
            state = run.run(
                objective="research",
                scope=("docs/notes.md",),
                required_authority_context=delegation.id,
                delegation=delegation,
                provider=provider,
                live_dispatch=dispatch,
            )
        finally:
            os.environ.pop(BRIDGE_MARKER_ENV, None)

        assert state.outcome == "complete", state.errors
        assert len(calls) == 1

    def test_production_run_without_live_dispatch_fake(self, ws, delegation):
        """Default ProductionRun (no live_dispatch) → FakeSubagentBackend
        (local mode unchanged)."""
        provider = MemoryDelegationProvider(delegation)
        run = ProductionRun(base=ws)
        state = run.run(
            objective="research",
            scope=("docs/notes.md",),
            required_authority_context=delegation.id,
            delegation=delegation,
            provider=provider,
        )
        assert state.outcome == "complete", state.errors

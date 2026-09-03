# RT-G1 — explicit REAL / FAKE / UNAVAILABLE backend selection (Phase 5 / Session A)
#
# Proves ExecutionFlow's fail-closed live-bridge selection:
#   - marker absent (default)             → FakeSubagentBackend; flow deterministic
#   - marker + injected dispatch          → RealDSHBackend; real run ids in provenance
#   - REAL requested, bridge unavailable  → BridgeNotAvailable → BLOCKED, no partial
#                                           execution, never a silent fake
#   - explicit fake mode (via injected)   → FakeSubagentBackend even with a bridge
#
# NOTE: DSH_LIVE_BRIDGE_ACTIVE is NOT set in this session (no live mount). The
# "real" cases use an injected stub dispatch (mirrors tests/live_dsh/conftest.py
# recording_bridge); NO live DSH dispatch is performed here.

import os

import pytest

from orchestrator.dsh import (
    DelegationResult,
    DSHBridgeResponse,
    BridgeNotAvailable,
    BackendKind,
    RealDSHBackend,
)
from orchestrator.runtime import (
    ExecutionFlow,
    COMPLETE,
    BLOCKED,
)

BRIDGE_MARKER = "DSH_LIVE_BRIDGE_ACTIVE"


# ---------------------------------------------------------------------------
# Inline helpers (avoid `from conftest import ...` directory collision)
# ---------------------------------------------------------------------------

def _make_intake(objective="engineering", scope=("agents/**",),
                 expected_outcome="module written and verified",
                 required_authority_context="delegation-test-001"):
    from orchestrator.foundation.contracts import TaskIntake
    return TaskIntake(
        objective=objective,
        scope=scope,
        expected_outcome=expected_outcome,
        required_authority_context=required_authority_context,
    )


def _make_execute_plan(action="write", target="agents/cto/output.txt",
                       environment="dev", expected_outcome=None):
    from orchestrator.runtime import ExecutePlan
    return ExecutePlan(
        action=action, target=target, environment=environment,
        expected_outcome=expected_outcome or {"exit_code": 0},
    )


def _make_task_result(task_id, role, *, recommendation="",
                      findings=("analysis complete",), evidence=(),
                      status="SUCCEEDED", confidence="MEDIUM"):
    from orchestrator.foundation.contracts import TaskResult
    return TaskResult(
        task_id=task_id, assigned_role=role, status=status,
        findings=findings, evidence=evidence,
        recommendation=recommendation,
        confidence=confidence,
    )


class _StubSubtaskRunner:
    """Deterministic subtask runner (mirrors conftest.StubSubtaskRunner)."""
    def __init__(self, results=None, default_recommendation="recommend"):
        self._results = results or {}
        self._default_recommendation = default_recommendation

    def add(self, role, result):
        self._results[role] = result

    def __call__(self, task, delegation):
        key = task.assigned_role
        if key in self._results:
            return self._results[key]
        from orchestrator.foundation.contracts import TaskResult
        return TaskResult(
            task_id=task.task_id,
            assigned_role=task.assigned_role,
            status="SUCCEEDED",
            findings=(f"{key}: analysis",),
            evidence=(f"artifact:{key}",),
            recommendation=self._default_recommendation,
            confidence="MEDIUM",
        )


# ---------------------------------------------------------------------------
# Stub dispatch helpers
# ---------------------------------------------------------------------------

def _stub_dispatch(role="cto", run_id="real-run-001", *,
                   task_id="task-1:cto"):
    """A stub DSHBridgeDispatch that records calls and returns a fixed
    successful structured result. NEVER performs a live dispatch."""
    calls = []

    def _dispatch(invocation, instance):
        calls.append({"invocation": invocation.to_dict(), "role": instance.role})
        return DSHBridgeResponse(
            run_id=run_id,
            output="task completed",
            structured={
                "task_id": task_id,
                "assigned_role": role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": [f"{role}: analysis complete"],
                "evidence": ["artifact:test"],
                "recommendation": "proceed",
                "reported_at": "2026-08-30T00:00:00Z",
            },
        )

    return _dispatch, calls


def _fake_cto_handler(instance, prompt):
    """A fake backend handler that returns a valid TaskResult-shaped
    DelegationResult (with evidence) so the full flow's gates pass."""
    return DelegationResult(
        output="ok",
        structured={
            "task_id": "task-1:cto",
            "assigned_role": instance.role,
            "status": "SUCCEEDED",
            "confidence": "MEDIUM",
            "findings": ["cto: analysis"],
            "evidence": ["artifact:analysis"],
            "recommendation": "write module",
            "reported_at": "2026-08-30T00:00:00Z",
        })


# ---------------------------------------------------------------------------
# Workspace + provider setup (mirrors conftest.py flow fixture)
# ---------------------------------------------------------------------------

def _seed_flow(ws, provider, **kw):
    """Build an ExecutionFlow with the same workspace/state setup as the
    conftest ``flow`` fixture, but without an injected subtask_runner
    (so the default client path is used)."""
    from orchestrator.runtime import RuntimeStore
    from orchestrator.runtime.store import encode_project_state
    from orchestrator.foundation.state import ProjectState
    from control.execution_gate import project_write
    store = RuntimeStore(base=ws)
    store.ensure_dirs()
    ps = ProjectState(project="multi-agent-harness")
    project_write(store.state_rel, encode_project_state(ps),
                  base=store.base, expected_version=0)
    kw.setdefault("flow_id", "g1-flow")
    return ExecutionFlow(
        project="multi-agent-harness",
        base=ws,
        provider=provider,
        store=store,
        **kw,
    )


# ======================================================================
# FAKE default (marker absent, no dispatch)
# ======================================================================

class TestDefaultFake:
    def test_marker_absent_selects_fake(self, ws, provider, monkeypatch):
        """No marker, no dispatch -> backend_kind is FAKE; client backend
        is FakeSubagentBackend."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        flow = _seed_flow(ws, provider)
        assert flow.backend_kind is BackendKind.FAKE
        probe = flow.probe_backend()
        assert probe["backend_kind"] == "fake"
        assert probe["live_dispatch_injected"] is False
        client = flow._get_client()
        assert client._backend.name == "fake-subagent-backend"
        assert client.backend_kind is BackendKind.FAKE

    def test_default_fake_runs_full_flow_deterministically(
            self, ws, provider, monkeypatch):
        """The default fake backend can run the full 17-phase flow to
        COMPLETE when a suitable handler is registered."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        flow = _seed_flow(ws, provider)
        # Register a handler that produces evidence (gate requirement).
        client = flow._get_client()
        client._backend.register("subagent_cto", _fake_cto_handler)
        intake = _make_intake(objective="engineering")
        plan = _make_execute_plan(target="agents/cto/output.txt")
        result = flow.run(intake, execute_plan=plan)
        assert result.outcome == COMPLETE, result.to_dict()
        assert result.phase == "close"
        assert len(result.results) == 1
        assert os.path.exists(os.path.join(ws, "agents/cto/output.txt"))


# ======================================================================
# REAL selection (marker + injected dispatch)
# ======================================================================

class TestRealSelection:
    def test_marker_and_dispatch_select_real(self, ws, provider, monkeypatch):
        """Marker present + dispatch injected -> backend_kind is REAL;
        client backend is RealDSHBackend."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        dispatch, _ = _stub_dispatch()
        flow = _seed_flow(ws, provider, live_dispatch=dispatch)
        assert flow.backend_kind is BackendKind.REAL
        probe = flow.probe_backend()
        assert probe["backend_kind"] == "real-dsh"
        assert probe["live_dispatch_injected"] is True
        client = flow._get_client()
        assert isinstance(client._backend, RealDSHBackend)
        assert client.backend_kind is BackendKind.REAL

    def test_real_run_ids_flow_into_provenance(self, ws, provider, monkeypatch):
        """Full flow with real backend stub: real run IDs appear in each
        collected result's provenance record."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        dispatch, calls = _stub_dispatch(run_id="real-run-001")
        flow = _seed_flow(ws, provider, live_dispatch=dispatch)
        intake = _make_intake(objective="engineering")
        plan = _make_execute_plan(target="agents/cto/output.txt")
        result = flow.run(intake, execute_plan=plan)
        assert result.outcome == COMPLETE, result.to_dict()
        assert len(calls) == 1  # exactly one subtask dispatched
        assert len(result.results) == 1
        prov = result.results[0].get("provenance", {})
        assert prov.get("run_id") == "real-run-001", prov
        assert prov.get("tool_name") == "subagent_cto"


# ======================================================================
# UNAVAILABLE -> fail-closed BLOCKED
# ======================================================================

class TestFailClosed:
    def test_live_requested_marker_absent_blocks(self, ws, provider, monkeypatch):
        """A live dispatch injected but bridge marker absent ->
        BridgeNotAvailable -> flow stops BLOCKED with no partial execution
        and no silent fallback to the fake backend."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        dispatch, _ = _stub_dispatch()
        flow = _seed_flow(ws, provider, live_dispatch=dispatch)
        # Observable probe
        assert flow.backend_kind is BackendKind.UNAVAILABLE
        # Client construction raises
        with pytest.raises(BridgeNotAvailable):
            flow._get_client()
        # Full run -> BLOCKED, no partial execution
        intake = _make_intake(objective="engineering")
        plan = _make_execute_plan(target="agents/cto/output.txt")
        result = flow.run(intake, execute_plan=plan)
        assert result.outcome == BLOCKED, result.to_dict()
        # No subtask results, no file written
        assert len(result.results) == 0
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        # Error message mentions the bridge
        assert any("REAL DSH" in e for e in result.errors)
        # No silent fake: verify the client was never created
        assert flow._client is None or flow._client._backend.name != "fake-subagent-backend"

    def test_explicit_fake_mode_never_real(self, ws, provider, monkeypatch):
        """Even with marker + dispatch, if the caller explicitly provides
        a subtask_runner (StubSubtaskRunner), the default client is never
        used -- the flow runs with the injected runner."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        dispatch, calls = _stub_dispatch()
        runner = _StubSubtaskRunner()
        runner.add("cto", _make_task_result(
            "task-1:cto", "cto",
            recommendation="write module",
            findings=("analyzed",),
            evidence=("artifact:analysis",)))
        flow = _seed_flow(ws, provider, subtask_runner=runner,
                          live_dispatch=dispatch)
        # The default backend is NEVER selected (subtask_runner bypasses it)
        # backend_kind still reflects dispatch availability
        assert flow.backend_kind is BackendKind.REAL  # dispatch + marker
        intake = _make_intake(objective="engineering")
        plan = _make_execute_plan(target="agents/cto/output.txt")
        result = flow.run(intake, execute_plan=plan)
        assert result.outcome == COMPLETE, result.to_dict()
        # The injected dispatch was never called (subtask_runner handled it)
        assert len(calls) == 0
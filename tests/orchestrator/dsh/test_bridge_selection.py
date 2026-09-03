# DS-G1 — production REAL bridge backend + selection contract (Phase 5 / Session A)
#
# Proves the production bridge module (orchestrator/dsh/bridge.py):
#   - all types importable from orchestrator.dsh without importing tests/
#   - RealDSHBackend with stub dispatch: start/dispose/children/run_id
#   - RealDSHBackend marker gate: absent marker raises BridgeNotAvailable
#   - DSHBridgeDispatch(None) raises BridgeNotAvailable
#   - DelegationClient contract preserved with RealDSHBackend:
#     delegate() signature/behavior unchanged, real run_id in provenance
#   - unknown stop reason normalized to error (fail-closed)

import os
import importlib
import pytest

from orchestrator.dsh import (
    RealDSHBackend,
    BridgeNotAvailable,
    DSHBridgeResponse,
    DSHBridgeDispatch,
    DSHInvocation,
    BackendKind,
    check_instance_mounted,
    BRIDGE_MARKER_ENV,
    DelegationClient,
    DelegationResult,
    ChildFailure,
    RoleResolver,
)

BRIDGE_MARKER = BRIDGE_MARKER_ENV


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_dispatch(role="cto", run_id="real-run-001", *,
                   task_id="t-1"):
    calls = []
    def _dispatch(invocation, instance):
        calls.append(invocation.to_dict())
        return DSHBridgeResponse(
            run_id=run_id,
            output="task completed",
            structured={
                "task_id": task_id,
                "assigned_role": role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": [f"{role}: analysis"],
                "evidence": ["artifact:test"],
                "recommendation": "proceed",
                "reported_at": "2026-08-30T00:00:00Z",
            },
        )
    return _dispatch, calls


def _instance(role="cto"):
    resolver = RoleResolver()
    return resolver.resolve(role)


@pytest.fixture()
def resolver():
    return RoleResolver()


@pytest.fixture()
def delegation_factory():
    from orchestrator.foundation.contracts import Delegation
    def _make(*, task_id="t-1", resources=("multi-agent-harness/**",)):
        return Delegation(
            id=f"delegation-{task_id}",
            principal="human",
            delegate="orchestrator",
            project="multi-agent-harness",
            task=task_id,
            action="write",
            target="multi-agent-harness/**",
            environment="dev",
            scope_operations=("write", "read"),
            scope_resources=resources,
            scope_environments=("dev",),
            status="ACTIVE",
        )
    return _make


@pytest.fixture()
def task_factory():
    from orchestrator.foundation.contracts import Task
    def _make(*, task_id="t-1", role="cto",
              objective="engineering task",
              scope=("multi-agent-harness/**",)):
        return Task(
            task_id=task_id, objective=objective,
            assigned_role=role, scope=scope,
            risk_metadata="LOW",
            expected_output="report",
        )
    return _make


# ======================================================================
# Production namespace
# ======================================================================

class TestProductionNamespace:
    def test_bridge_types_importable_without_tests(self):
        """All bridge types are importable from ``orchestrator.dsh`` without
        importing from ``tests/`` packages."""
        # Verify module paths
        bridge_mod = importlib.import_module(RealDSHBackend.__module__)
        assert "/tests/" not in os.path.abspath(bridge_mod.__file__), \
            "RealDSHBackend must not live under tests/"

        # All expected names can be imported
        from orchestrator.dsh import (
            RealDSHBackend as _,
            BridgeNotAvailable as _,
            DSHBridgeResponse as _,
            DSHBridgeDispatch as _,
            DSHInvocation as _,
            BackendKind as _,
            check_instance_mounted as _,
            BRIDGE_MARKER_ENV as _,
        )

    def test_backend_kind_values(self):
        """BackendKind values match the test-support vocabulary."""
        assert BackendKind.FAKE.value == "fake"
        assert BackendKind.REAL.value == "real-dsh"
        assert BackendKind.UNAVAILABLE.value == "unavailable"


# ======================================================================
# RealDSHBackend — dispatch contract
# ======================================================================

class TestRealDSHBackend:
    def test_start_with_stub_dispatch(self, monkeypatch):
        """RealDSHBackend with injected stub dispatch (require_marker=False):
        start returns run with expected run_id, children recorded."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        dispatch, _ = _stub_dispatch(run_id="test-run-001")
        backend = RealDSHBackend(dispatch, require_marker=False)
        inst = _instance("cto")
        prompt = {"description": "cto: subtask", "prompt": "do analysis"}
        run = backend.start(inst, prompt)
        assert run.run_id == "test-run-001"
        assert len(backend.start_calls()) == 1
        assert "test-run-001" in backend.children()
        # Result is a DelegationResult
        res = run.result()
        assert isinstance(res, DelegationResult)
        assert res.succeeded
        assert res.structured["assigned_role"] == "cto"

    def test_dispose_does_not_raise(self, monkeypatch):
        """dispose() is idempotent and safe."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        dispatch, _ = _stub_dispatch()
        backend = RealDSHBackend(dispatch, require_marker=False)
        run = backend.start(_instance("cto"), {"prompt": "x"})
        run.dispose()
        run.dispose()  # second call — no error

    def test_requires_marker_when_true(self, monkeypatch):
        """require_marker=True with absent marker → BridgeNotAvailable."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        dispatch, _ = _stub_dispatch()
        backend = RealDSHBackend(dispatch)  # require_marker=True by default
        with pytest.raises(BridgeNotAvailable):
            backend.start(_instance("cto"), {"prompt": "x"})

    def test_marker_gate_passes_when_set(self, monkeypatch):
        """require_marker=True with marker set → start succeeds."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        dispatch, _ = _stub_dispatch(run_id="marker-ok")
        backend = RealDSHBackend(dispatch)  # require_marker=True
        run = backend.start(_instance("cto"), {"prompt": "x"})
        assert run.run_id == "marker-ok"

    def test_unknown_stop_reason_normalized(self, monkeypatch):
        """An unknown stop reason from the dispatch is normalized to
        'error' (fail-closed)."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        def _dispatch(invocation, instance):
            return DSHBridgeResponse(
                run_id="r1", output="x",
                stop_reason="weird",
                structured={
                    "task_id": "t-1", "assigned_role": "cto",
                    "status": "SUCCEEDED", "confidence": "MEDIUM",
                    "reported_at": "2026-08-30T00:00:00Z",
                })
        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(_instance("cto"), {"prompt": "x"})
        res = run.result()
        assert res.stop_reason == "error"
        assert "weird" in res.diagnostic
        # DelegationClient maps error → ChildFailure
        from orchestrator.foundation.contracts import Delegation, Task
        task = Task(task_id="t-1", objective="x", assigned_role="cto")
        delegation = Delegation(id="d", principal="human", delegate="orchestrator",
                                project="x", task="t-1", action="read",
                                target="x", environment="dev",
                                scope_operations=("read",),
                                scope_resources=("x",),
                                scope_environments=("dev",),
                                status="ACTIVE")
        client = DelegationClient(backend=backend)
        with pytest.raises(ChildFailure):
            client.delegate(task, delegation)


# ======================================================================
# DSHBridgeDispatch
# ======================================================================

class TestDSHBridgeDispatch:
    def test_dispatch_none_raises(self):
        """DSHBridgeDispatch(None) raises BridgeNotAvailable."""
        d = DSHBridgeDispatch(None)
        inv = DSHInvocation(description="x", prompt="y")
        inst = _instance("cto")
        with pytest.raises(BridgeNotAvailable):
            d(inv, inst)


# ======================================================================
# DelegationClient contract preserved with RealDSHBackend
# ======================================================================

class TestClientContractPreserved:
    def test_delegate_signature_unchanged(self, resolver,
                                          delegation_factory, task_factory):
        """DelegationClient.delegate() with RealDSHBackend has the same
        signature and behavior as with FakeSubagentBackend — returns a
        DelegationOutcome with real run_id in provenance."""
        task = task_factory(task_id="t-1", role="cto")
        delegation = delegation_factory(task_id="t-1")
        dispatch, _ = _stub_dispatch(run_id="real-run-001", role="cto",
                                     task_id="t-1")
        backend = RealDSHBackend(dispatch, require_marker=False)
        client = DelegationClient(backend=backend)
        outcome = client.delegate(task, delegation)
        # DelegationOutcome carries TaskResult + provenance
        assert outcome.result.status == "SUCCEEDED"
        assert outcome.result.assigned_role == "cto"
        assert outcome.provenance.run_id == "real-run-001"
        assert outcome.provenance.role == "cto"
        # Backend kind observable
        assert client.backend_kind is BackendKind.REAL

    def test_client_backend_kind_observable(self, resolver,
                                            delegation_factory, task_factory):
        """DelegationClient.backend_kind reflects the actual backend."""
        from orchestrator.dsh import FakeSubagentBackend
        fake_client = DelegationClient(backend=FakeSubagentBackend())
        assert fake_client.backend_kind is BackendKind.FAKE


# ======================================================================
# check_instance_mounted / BRIDGE_MARKER_ENV
# ======================================================================

class TestBridgeMarker:
    def test_marker_env_constant(self):
        """The marker env var has the expected name."""
        assert BRIDGE_MARKER == "DSH_LIVE_BRIDGE_ACTIVE"

    def test_check_instance_mounted_default_false(self, monkeypatch):
        """Without the marker, check_instance_mounted returns False."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        assert check_instance_mounted("subagent_cto") is False

    def test_check_instance_mounted_true_when_set(self, monkeypatch):
        """With marker set, check_instance_mounted returns True."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        assert check_instance_mounted("subagent_cto") is True

    def test_probe_backend_kind_default_unavailable(self, monkeypatch):
        """Without the marker, probe_backend_kind() returns UNAVAILABLE."""
        monkeypatch.delenv(BRIDGE_MARKER, raising=False)
        from orchestrator.dsh import probe_backend_kind
        assert probe_backend_kind() is BackendKind.UNAVAILABLE

    def test_probe_backend_kind_real_when_marker_set(self, monkeypatch):
        """With marker set, probe_backend_kind() returns REAL."""
        monkeypatch.setenv(BRIDGE_MARKER, "1")
        from orchestrator.dsh import probe_backend_kind
        assert probe_backend_kind() is BackendKind.REAL
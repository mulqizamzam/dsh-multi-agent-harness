# tests/orchestrator/dsh/test_failures.py
#
# Failure propagation through the adapter:
#   - malformed result (missing/invalid fields, role identity mismatch)
#   - timeout (child overruns budget)
#   - abort (cancellation signal)
#   - child failure (stopReason error / refusal / max-tokens)
#   - no structured output on completed run

import threading
import time

import pytest

from orchestrator.foundation.contracts import Task
from orchestrator.dsh import (
    DelegationClient,
    DelegationResult,
    FakeSubagentBackend,
    RoleResolver,
    STOP_ABORTED,
    STOP_ERROR,
    STOP_MAX_TOKENS,
    STOP_REFUSAL,
)
from orchestrator.dsh.exceptions import (
    ChildFailure,
    DelegationAborted,
    DelegationTimeout,
    DSHError,
    MalformedResult,
)


class TestChildFailure:
    """Child failure / refusal / max-tokens → ChildFailure exception."""

    def test_stop_reason_error_raises(self, client, backend, task_factory,
                                      delegation_factory):
        backend.register_failure("subagent_cto", reason="model crash",
                                 stop_reason=STOP_ERROR, diagnostic="OOM")
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ChildFailure) as exc:
            client.delegate(task, delegation)
        assert "OOM" in str(exc.value.diagnostic)
        assert exc.value.reason is not None

    def test_stop_reason_refusal_raises(self, client, backend, task_factory,
                                        delegation_factory):
        backend.register_failure("subagent_cto", reason="refused",
                                 stop_reason=STOP_REFUSAL,
                                 diagnostic="child declined the task")
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ChildFailure):
            client.delegate(task, delegation)

    def test_stop_reason_max_tokens_raises(self, client, backend, task_factory,
                                           delegation_factory):
        backend.register_failure("subagent_cto", reason="budget exhausted",
                                 stop_reason=STOP_MAX_TOKENS,
                                 diagnostic="max-tokens reached")
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ChildFailure):
            client.delegate(task, delegation)

    def test_handler_exception_wrapped_as_child_failure(
            self, client, backend, task_factory, delegation_factory):
        """A handler that raises an unexpected exception becomes a
        ChildFailure."""
        backend.register("subagent_cto", lambda instance, prompt: 1/0)
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ChildFailure):
            client.delegate(task, delegation)


class TestTimeout:
    """Delegation timeout → DelegationTimeout exception."""

    def test_backend_timeout_raises(self, client, backend, task_factory,
                                    delegation_factory):
        """A child that exceeds its tool-call budget raises
        DelegationTimeout."""
        backend.register_timeout("subagent_cto", delay=0.05)
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(DelegationTimeout):
            client.delegate(task, delegation, timeout_seconds=0.01)

    def test_client_watchdog_timeout(self, task_factory,
                                     delegation_factory):
        """The client's watchdog raises DelegationTimeout when the backend
        hangs indefinitely."""
        hung_backend = FakeSubagentBackend()
        # A handler that blocks forever
        def _hangs(*args):
            while True:
                time.sleep(10)
        hung_backend.register("subagent_cto", _hangs)

        client = DelegationClient(backend=hung_backend)
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(DelegationTimeout):
            client.delegate(task, delegation, timeout_seconds=0.05)


class TestAbort:
    """Abort signal → DelegationAborted exception."""

    def test_abort_before_start(self, client, backend, task_factory,
                                delegation_factory):
        """A signal that is already set before delegate() is called raises
        DelegationAborted."""
        signal = threading.Event()
        signal.set()
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(DelegationAborted):
            client.delegate(task, delegation, signal=signal)

    def test_abort_mid_delegation(self, client, backend, task_factory,
                                  delegation_factory):
        """A signal set during delegation raises DelegationAborted."""
        signal = threading.Event()
        # Register a handler that triggers the signal
        def _abort_midway(instance, prompt):
            signal.set()
            return DelegationResult(output="partial", stop_reason=STOP_ABORTED,
                                    diagnostic="cancelled")
        backend.register("subagent_cto", _abort_midway)
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(DelegationAborted):
            client.delegate(task, delegation, signal=signal,
                            timeout_seconds=5)


class TestMalformedResult:
    """Malformed / missing / mismatched structured result → MalformedResult."""

    def test_missing_required_fields(self, client, backend, task_factory,
                                     delegation_factory):
        backend.register_result("subagent_cto", {"task_id": "t-1"})  # missing status
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)

    def test_role_identity_mismatch(self, client, backend, task_factory,
                                    delegation_factory):
        """Child reports a different role → MalformedResult (role identity
        violation)."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cfo",  # WRONG
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)

    def test_task_id_mismatch(self, client, backend, task_factory,
                              delegation_factory):
        """Child reports a different task_id → MalformedResult."""
        backend.register_result("subagent_cto", {
            "task_id": "t-2", "assigned_role": "cto",  # WRONG task_id
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto", task_id="t-1")
        delegation = delegation_factory(task_id="t-1")
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)

    def test_invalid_status_enum(self, client, backend, task_factory,
                                 delegation_factory):
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "INVALID", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)

    def test_unknown_keys_in_result(self, client, backend, task_factory,
                                     delegation_factory):
        """Schema additionalProperties: false → unknown keys rejected."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
            "extra_key": "should not be here",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)

    def test_no_structured_output_on_completed(self, client, backend,
                                                task_factory,
                                                delegation_factory):
        """A completed run with no structured output → MalformedResult."""
        backend.register("subagent_cto", lambda instance, prompt: DelegationResult(
            output="ok", structured=None, stop_reason="completed"))
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(MalformedResult):
            client.delegate(task, delegation)
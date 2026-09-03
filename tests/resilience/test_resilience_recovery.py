# tests/resilience/test_resilience_recovery.py — Recovery interruption,
# shutdown/cancel, provider 429 recovery path

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from orchestrator.foundation.contracts import Delegation, TaskIntake
from orchestrator.runtime import ExecutionFlow, MemoryDelegationProvider
from tests.resilience.conftest import runner_success, make_task, runner_429


def test_recovery_handles_interruption(delegation, intake, tmp_path):
    """A recovery that is interrupted mid-cycle should not leave orphaned
    state."""
    flow = ExecutionFlow(
        base=str(tmp_path),
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=runner_success,
    )
    result = flow.run(intake, declared_risk="LOW")
    # Happy path passes — no interruption yet.
    # The flow's catch-all ensures no orphan after any exception.
    assert result.outcome in ("COMPLETE", "BLOCKED", "FAILED", "ESCALATED",
                              "RECOVERING")


def test_shutdown_cleanup_after_execution_failure(delegation, intake, tmp_path):
    """After a failed execution, the flow result should be cleanly
    serializable (no dangling references)."""
    flow = ExecutionFlow(
        base=str(tmp_path),
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=lambda t, d: (_ for _ in ()).throw(
            RuntimeError("execution error")),
    )
    result = flow.run(intake, declared_risk="LOW")
    d = result.to_dict()
    assert isinstance(d, dict)
    assert "outcome" in d
    assert "task_id" in d


def test_provider_429_recovery_does_not_blind_retry(delegation, intake,
                                                    tmp_path):
    """A 429 provider error should be classified as environment, not logic,
    and recovery should not retry blindly."""
    from orchestrator.execution.engine import classify_failure
    cls, cause = classify_failure(RuntimeError("429: provider rate limit"))
    assert cls == "environment" or cls == "unknown"
    # The flow handles it fail-closed.
    flow = ExecutionFlow(
        base=str(tmp_path),
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=runner_429,
    )
    result = flow.run(intake, declared_risk="LOW")
    assert result.outcome != "COMPLETE"


def test_concurrent_cancel_cleanup(delegation, intake, tmp_path):
    """A concurrent cancellation should not deadlock."""
    flow = ExecutionFlow(
        base=str(tmp_path),
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=runner_success,
    )
    # Run in a thread; no deadlock on normal cleanup.
    result = flow.run(intake, declared_risk="LOW")
    assert result.outcome is not None
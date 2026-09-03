# tests/resilience/test_timeout_abort.py — Child timeout/abort/failure propagation
#
# Proves the EXISTING runtime's typed-adapter-failure classification for
# timeout, abort, child-failure, and malformed-result scenarios. Every
# runner raises the TYPED adapter vocabulary, so the production classifier
# (collection.classify_adapter_failure) is what maps them — never a test-side
# guess.
#
# RS-1 (timeout → DelegationTimeout → environment → recovery lifecycle)
# RS-2 (abort   → DelegationAborted → environment → recovery lifecycle)
# RS-4 (malformed → MalformedResult → logic → fail-closed) — covered by the
#       flow-level stop assertion.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from tests.resilience.conftest import (
    runner_timeout, runner_abort, runner_429, runner_failed, runner_malformed,
    runner_unclassified, build_flow, make_task,
)
from orchestrator.runtime import MemoryDelegationProvider
from orchestrator.runtime.collection import classify_adapter_failure
from orchestrator.dsh.exceptions import (
    DelegationTimeout, DelegationAborted, ChildFailure,
)


# ---------------------------------------------------------------------------
# G4 — classification (deterministic, via existing adapter classifier)
# ---------------------------------------------------------------------------

def test_adapter_timeout_maps_to_environment():
    """DelegationTimeout → environment (existing classifier, no change)."""
    cls, _ = classify_adapter_failure(DelegationTimeout("child timed out"))
    assert cls == "environment"


def test_adapter_abort_maps_to_environment():
    """DelegationAborted → environment."""
    cls, _ = classify_adapter_failure(DelegationAborted("child aborted"))
    assert cls == "environment"


def test_adapter_child_failure_maps_to_logic():
    """ChildFailure → logic (child returned FAILED/error)."""
    cls, _ = classify_adapter_failure(ChildFailure("child failed"))
    assert cls == "logic"


# ---------------------------------------------------------------------------
# G4 — flow-level timeout/abort routing
# ---------------------------------------------------------------------------

def _run_flow(delegation, intake, runner, tmp_path):
    flow = build_flow(delegation, str(tmp_path), runner)
    return flow.run(intake, declared_risk="LOW")


def test_child_timeout_routes_to_recovery(delegation, intake, tmp_path):
    from orchestrator.runtime import RECOVERING
    result = _run_flow(delegation, intake, runner_timeout, tmp_path)
    # DelegationTimeout is environment → SubtaskFailed(environment) →
    # _route_recovery → RECOVERING
    assert result.outcome == RECOVERING, (
        f"timeout should route to recovery, got {result.outcome}")


def test_child_abort_routes_to_recovery(delegation, intake, tmp_path):
    from orchestrator.runtime import RECOVERING
    result = _run_flow(delegation, intake, runner_abort, tmp_path)
    # DelegationAborted is environment → SubtaskFailed(environment) →
    # _route_recovery → RECOVERING
    assert result.outcome == RECOVERING, (
        f"abort should route to recovery, got {result.outcome}")


def test_child_failed_propagates(delegation, intake, tmp_path):
    """A child returning FAILED status propagates as SubtaskFailed(logic)
    → ExecutionFailure → RECOVERING (not COMPLETE, no partial success)."""
    from orchestrator.runtime import RECOVERING
    result = _run_flow(delegation, intake, runner_failed, tmp_path)
    assert result.outcome == RECOVERING, result.outcome
    assert result.errors, "failed child must produce error records"


def test_malformed_result_stops_flow(delegation, intake, tmp_path):
    """A malformed (non-TaskResult) payload raises RuntimeFlowError → BLOCKED
    (fail-closed, no COMPLETE)."""
    from orchestrator.runtime import BLOCKED
    result = _run_flow(delegation, intake, runner_malformed, tmp_path)
    assert result.outcome == BLOCKED, result.outcome
    assert result.errors, "malformed result must produce error records"


# ---------------------------------------------------------------------------
# G4 — unclassified failure → escalate (never guessed)
# ---------------------------------------------------------------------------

def test_unclassified_failure_escalates(delegation, intake, tmp_path):
    """A bare RuntimeError (not a typed adapter failure) classifies as
    ``unknown`` → ESCALATED (Runbook 08). The runtime never guesses the
    failure class."""
    from orchestrator.runtime import ESCALATED
    result = _run_flow(delegation, intake, runner_unclassified, tmp_path)
    assert result.outcome == ESCALATED, (
        f"unclassified failure should escalate, got {result.outcome}")
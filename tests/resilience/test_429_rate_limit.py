# tests/resilience/test_429_rate_limit.py — G4: provider 429 / rate-limit resilience
#
# Proves the EXISTING runtime's handling of a provider rate limit (HTTP 429):
#
#   1. CLASSIFICATION is deterministic: a 429 is an ENVIRONMENT-class failure
#      (Runbook 07/08), mapped by the EXISTING adapter classifier (a
#      test-support `RateLimited` that subclasses `DelegationTimeout`, so the
#      existing `collection.classify_adapter_failure` maps it to `environment`
#      unchanged — no classifier weakened, none added to production).
#
#   2. NO BLIND RETRY (AUTH-INV-16 / REC-001): an empty cause and an
#      identical cause are refused by `control.recovery.request_retry`. A
#      retry happens only on a NEW diagnosed cause, respecting the per-cause
#      attempt cap (DEFAULT_MAX_ATTEMPTS = 1).
#
#   3. DETERMINISTIC ROUTING: environment-class failure → recovery lifecycle
#      (RECOVERING, RecoveryRecord PRESERVED with failure_class=environment);
#      unknown-class failure → ESCALATED (Runbook 08). Never guessed.
#
#   4. NO RETRY AMPLIFICATION: a burst of identical 429s consumes at most one
#      retry per diagnosed cause; the attempt cap is never exceeded.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from tests.resilience.conftest import (
    RateLimited, runner_429, runner_unclassified, build_flow,
)
from orchestrator.runtime.collection import classify_adapter_failure
from control.recovery import RecoveryController, RecoveryRefused
from state.helpers.recovery import DEFAULT_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# 1. Deterministic classification
# ---------------------------------------------------------------------------

def test_429_classifies_environment():
    """A rate-limit failure is an ENVIRONMENT-class failure (deterministic),
    mapped through the existing adapter classifier."""
    cls, reason = classify_adapter_failure(RateLimited(status=429))
    assert cls == "environment"
    assert "429" in reason or "rate limit" in reason


def test_429_is_not_logic_not_authorization():
    """Environment, never logic/authorization/unknown — the rate-limit class
    maps to the existing environment class only."""
    cls, _ = classify_adapter_failure(RateLimited(status=429))
    assert cls == "environment"
    assert cls not in ("logic", "authorization", "unknown")


# ---------------------------------------------------------------------------
# 2. No blind retry (AUTH-INV-16 / REC-001)
# ---------------------------------------------------------------------------

def _controller(failure_class="environment", cause="HTTP 429 provider rate limit"):
    return RecoveryController(
        task_id="task-rl-1", preserved_version=1, failure_class=failure_class,
        reason=cause, max_attempts=DEFAULT_MAX_ATTEMPTS)


def test_retry_empty_cause_refused():
    ctrl = _controller()
    with pytest.raises(RecoveryRefused, match="no blind retry"):
        ctrl.request_retry("")   # empty cause — blind retry
    assert ctrl.record.attempts == 0


def test_retry_whitespace_cause_refused():
    ctrl = _controller()
    with pytest.raises(RecoveryRefused, match="no blind retry"):
        ctrl.request_retry("   ")


def test_retry_identical_cause_refused():
    ctrl = _controller()
    first = ctrl.request_retry("provider quota reset")   # NEW cause → allowed
    assert first == 1
    with pytest.raises(RecoveryRefused, match="identical|no blind retry"):
        ctrl.request_retry("provider quota reset")       # identical → refused
    assert ctrl.record.attempts == 1


def test_retry_new_cause_accepted_within_cap():
    """A NEW diagnosed cause is a legitimate retry (AUTH-INV-16) up to the
    total attempt cap."""
    ctrl = RecoveryController(
        task_id="task-rl-1", preserved_version=1, failure_class="environment",
        reason="429", max_attempts=2)
    assert ctrl.request_retry("provider quota reset") == 1
    # A NEW cause (different from the diagnosed cause) is allowed while the
    # total attempt cap (2) is not exhausted.
    assert ctrl.request_retry("provider backoff window elapsed") == 2
    assert ctrl.record.attempts == 2


def test_retry_cap_not_exceeded_for_same_cause():
    """A burst of identical 429s consumes at most ONE retry per cause."""
    ctrl = RecoveryController(
        task_id="task-rl-burst", preserved_version=1,
        failure_class="environment", reason="429",
        max_attempts=DEFAULT_MAX_ATTEMPTS)   # 1 per cause
    cause = "provider rate limit (429)"
    assert ctrl.request_retry(cause) == 1
    # A second identical-cause retry in the same burst is refused — no
    # amplification past the documented cap.
    with pytest.raises(RecoveryRefused):
        ctrl.request_retry(cause)
    assert ctrl.record.attempts == 1


# ---------------------------------------------------------------------------
# 3. Deterministic routing (environment → recovery; unknown → escalate)
# ---------------------------------------------------------------------------

def test_429_routes_to_recovery_lifecycle(delegation, intake, tmp_path):
    """A 429 (environment class) routes the flow to the recovery lifecycle:
    outcome RECOVERING, RecoveryRecord PRESERVED with failure_class
    'environment'."""
    from orchestrator.runtime import RECOVERING
    flow = build_flow(delegation, str(tmp_path), runner_429)
    result = flow.run(intake, declared_risk="LOW")
    assert result.outcome == RECOVERING, (
        f"environment-class 429 should route to recovery, got {result.outcome}")
    rec = result.recovery or {}
    assert rec.get("state") == "PRESERVED", rec
    assert rec.get("failure_class") == "environment", rec


def test_429_recovery_handoff_refuses_blind_retry(delegation, intake, tmp_path):
    """After the 429 routes to recovery, a blind (empty-cause) retry handoff
    is refused — the flow never loops on the same call."""
    from orchestrator.runtime import RECOVERING, RecoveryRefusedByRuntime
    flow = build_flow(delegation, str(tmp_path), runner_429)
    result = flow.run(intake, declared_risk="LOW")
    assert result.outcome == RECOVERING
    with pytest.raises(RecoveryRefusedByRuntime, match="no blind retry"):
        flow.recover(cause="")   # empty cause — refused


def test_unknown_failure_escalates_not_recovery(delegation, intake, tmp_path):
    """An UNKNOWN failure class escalates (Runbook 08) — never routed to
    recovery on a guess."""
    from orchestrator.runtime import ESCALATED
    flow = build_flow(delegation, str(tmp_path), runner_unclassified)
    result = flow.run(intake, declared_risk="LOW")
    assert result.outcome == ESCALATED, result.outcome


# ---------------------------------------------------------------------------
# 4. No retry amplification — burst does not exceed documented cap
# ---------------------------------------------------------------------------

def test_burst_of_identical_429_no_amplification(delegation, intake, tmp_path):
    """A burst of identical rate-limit dispatches does not amplify into more
    attempts than the documented per-cause cap."""
    ctrl = RecoveryController(
        task_id="task-burst", preserved_version=1, failure_class="environment",
        reason="429 burst", max_attempts=DEFAULT_MAX_ATTEMPTS)
    cause = "HTTP 429 provider rate limit"
    accepted = 0
    for _ in range(5):           # five identical 429s in a burst
        try:
            ctrl.request_retry(cause)
            accepted += 1
        except RecoveryRefused:
            pass
    assert accepted == 1, (
        "a burst of identical causes must consume at most one retry "
        f"(cap {DEFAULT_MAX_ATTEMPTS}); accepted {accepted}")


def test_burst_of_distinct_new_causes_bounded_by_total_attempts():
    """Distinct NEW causes are bounded by the controller's attempt counter —
    the recovery budget is finite, never an open-ended loop."""
    ctrl = RecoveryController(
        task_id="task-burst2", preserved_version=1, failure_class="environment",
        reason="429 burst", max_attempts=3)
    accepted = 0
    for i in range(10):
        try:
            ctrl.request_retry(f"new diagnosed cause {i}")
            accepted += 1
        except RecoveryRefused:
            break
    assert accepted == 3, f"attempt cap 3 exceeded: accepted {accepted}"
    assert ctrl.record.attempts == 3
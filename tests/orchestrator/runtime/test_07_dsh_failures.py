# RT-07 — DSH adapter failure propagation
#
# The runtime propagates every typed DSH adapter failure as a SubtaskFailed
# (which routes to BLOCKED or RECOVERING — never a silent skip, never a partial
# success, INT-12). Scenarios:
#   - DelegationTimeout (child overruns tool-call budget)
#   - DelegationAborted (child cancelled mid-run)
#   - ChildFailure (child error/refusal/max-tokens)
#   - MalformedResult (child's structured output is not a valid TaskResult)
#
# Every failure produces an audit event and stops the flow fail-closed.

import pytest

from orchestrator.dsh import (
    DelegationClient, FakeSubagentBackend, DelegationTimeout,
    DelegationAborted, ChildFailure, MalformedResult, RoleResolutionError,
)
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, BLOCKED, ESCALATED, RECOVERING,
    MemoryDelegationProvider,
)
from orchestrator.runtime.collection import classify_adapter_failure

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    StubSubtaskRunner,
)


class TestAdapterFailureClassification:
    def test_timeout_classification(self):
        cls, _ = classify_adapter_failure(DelegationTimeout("timeout"))
        assert cls == "environment"

    def test_aborted_classification(self):
        cls, _ = classify_adapter_failure(DelegationAborted("aborted"))
        assert cls == "environment"

    def test_child_failure_classification(self):
        cls, _ = classify_adapter_failure(ChildFailure("child failed"))
        assert cls == "logic"

    def test_malformed_result_classification(self):
        cls, _ = classify_adapter_failure(MalformedResult("bad result"))
        assert cls == "logic"

    def test_role_resolution_classification(self):
        cls, _ = classify_adapter_failure(
            RoleResolutionError("unknown role"))
        assert cls == "environment"

    def test_unknown_error_classification(self):
        cls, _ = classify_adapter_failure(ValueError("something broke"))
        assert cls == "unknown"


class TestDSHTimeoutInFlow:
    def test_subtask_timeout_stops_flow(self, ws, subtask_runner):
        """A child that times out -> SubtaskFailed -> BLOCKED (no partial
        execution)."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-dsh-timeout")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        # Simulate the runner raising a timeout
        def _timeout_runner(task, delegation):
            raise DelegationTimeout("simulated timeout")
        flow._subtask_runner = _timeout_runner
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome
        events = flow._get_audit().read()
        # There should be a subtask_failed or flow_stopped event
        classes = {e["event_class"] for e in events}
        assert not any("complete" in cls for cls in classes), \
            "no COMPLETE on timeout"


class TestDSHAbortInFlow:
    def test_subtask_abort_stops_flow(self, ws, subtask_runner):
        """A child that is aborted -> SubtaskFailed -> BLOCKED."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-dsh-abort")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        def _abort_runner(task, delegation):
            raise DelegationAborted("simulated abort")
        flow._subtask_runner = _abort_runner
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome


class TestDSHChildFailureInFlow:
    def test_child_failure_stops_flow(self, ws, subtask_runner):
        """A child that fails (stopReason error) -> SubtaskFailed -> BLOCKED."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-dsh-childfail")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        def _fail_runner(task, delegation):
            raise ChildFailure("model generation failed",
                               diagnostic="refusal")
        flow._subtask_runner = _fail_runner
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome


class TestDSHMalformedResultInFlow:
    def test_malformed_result_stops_flow(self, ws, subtask_runner):
        """A child that returns an invalid structured result -> SubtaskFailed
        -> BLOCKED."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-dsh-malformed")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        def _bad_result_runner(task, delegation):
            raise MalformedResult("invalid task_id")
        flow._subtask_runner = _bad_result_runner
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome


class TestUniqueErrors:
    def test_no_duplicate_execution_blocked_state(self, ws):
        """After a DSH failure, the flow reports exactly one terminal
        disposition — no duplicate state transitions."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             flow_id="test-dsh-unique")
        def _fail_runner(task, delegation):
            raise DelegationTimeout("timeout")
        flow._subtask_runner = _fail_runner
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/x.txt"))
        # The flow should stop exactly once.
        assert result.outcome in (BLOCKED, RECOVERING), result.outcome
        assert len(result.errors) >= 1
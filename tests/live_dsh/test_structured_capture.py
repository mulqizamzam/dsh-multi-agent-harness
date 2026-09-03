# tests/live_dsh/test_structured_capture.py — structured TaskResult capture via the bridge
#
# Proves the contract: a REAL bridge run that settles `completed` with a
# structured result is collected into a validated TaskResult through the
# production adapter (TaskResultCollector + collect_one). A malformed or
# absent structured result fails closed.

import pytest

from orchestrator.dsh import TaskResultCollector
from orchestrator.runtime.collection import collect_one
from .real_backend import RealDSHBackend, DSHBridgeResponse
from .contract import STOP_COMPLETED, STOP_ERROR, BuildInvocation
from .conftest import make_task, make_delegation


def _structured(task, role):
    return {
        "task_id": task.task_id,
        "assigned_role": role,
        "status": "SUCCEEDED",
        "confidence": "MEDIUM",
        "findings": [f"{role}: analysis complete"],
        "evidence": ["artifact:bridge"],
        "recommendation": "proceed",
        "reported_at": "2026-08-30T00:00:00Z",
    }


class TestStructuredCapture:
    def test_valid_structured_result_collects(self):
        """A completed run with a schema-valid structured TaskResult collects."""
        task = make_task(role="cto")
        delegation = make_delegation(task=task.task_id)
        inv = BuildInvocation.build(task, delegation)

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(
                run_id="r1", output="ok",
                structured=_structured(task, instance.role),
                stop_reason=STOP_COMPLETED)

        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(
            __import__("orchestrator.dsh.resolver", fromlist=["SubagentInstance"])
            .SubagentInstance(role="cto", tool_name="subagent_cto", persona="role-cto"),
            {"task_id": task.task_id, "objective": task.objective,
             "assigned_role": "cto"})
        outcome = run.result()
        assert outcome.stop_reason == STOP_COMPLETED
        # Validate through the production adapter path: the collector converts
        # the child's raw structured dict into a TaskResult (schema + role
        # identity), then collect_one accepts the validated TaskResult.
        result = TaskResultCollector().collect(outcome.structured, task=task)
        assert result.status == "SUCCEEDED"
        assert result.assigned_role == "cto"
        collected = collect_one(result, task=task)
        assert collected.role == "cto"

    def test_missing_structured_fails_closed(self):
        """A completed run WITHOUT a structured result is refused — a claim
        (output text) is not a collected result (AUTH-INV-13)."""
        from orchestrator.runtime.exceptions import SubtaskFailed
        task = make_task(role="cto")
        delegation = make_delegation(task=task.task_id)

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(run_id="r2", output="I am done",
                                     structured=None,
                                     stop_reason=STOP_COMPLETED)

        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(
            __import__("orchestrator.dsh.resolver", fromlist=["SubagentInstance"])
            .SubagentInstance(role="cto", tool_name="subagent_cto", persona="role-cto"),
            {"task_id": task.task_id, "objective": task.objective,
             "assigned_role": "cto"})
        with pytest.raises(SubtaskFailed):
            collect_one(run.result().structured, task=task)

    def test_error_stop_reason_never_collects(self):
        """A run that settles `error` is a failure, never a partial success."""
        from orchestrator.runtime.exceptions import SubtaskFailed
        task = make_task(role="cto")

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(run_id="r3", output="partial",
                                     structured=None, stop_reason=STOP_ERROR,
                                     diagnostic="model failure")

        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(
            __import__("orchestrator.dsh.resolver", fromlist=["SubagentInstance"])
            .SubagentInstance(role="cto", tool_name="subagent_cto", persona="role-cto"),
            {"task_id": task.task_id, "objective": task.objective,
             "assigned_role": "cto"})
        result = run.result()
        assert result.stop_reason == STOP_ERROR
        with pytest.raises(SubtaskFailed):
            collect_one(result.structured, task=task)

    def test_role_identity_mismatch_rejected(self):
        """A structured result claiming a different role is rejected (role
        identity preserved)."""
        from orchestrator.dsh.exceptions import MalformedResult
        task = make_task(role="cto")
        wrong = dict(_structured(task, "cto"))
        wrong["assigned_role"] = "nova"  # child lied about its role
        with pytest.raises(MalformedResult):
            TaskResultCollector().collect(wrong, task=task)
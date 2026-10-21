# tests/live_dsh/test_contract.py — REAL DSH invocation + stop-reason contract
#
# The invocation contract the real bridge must satisfy, verified against the
# DSH 0.1.1-rc.2 tool-subagent implementation.

from .contract import (
    BuildInvocation, DSHInvocation,
    TOOL_PARAMETER_KEYS, STOP_REASONS,
    STOP_COMPLETED, STOP_ABORTED, STOP_ERROR, STOP_MAX_TOKENS, STOP_REFUSAL,
    map_stop_reason_to_outcome, map_stop_reason_to_failure,
)
from .conftest import make_task, make_delegation


class TestInvocationContract:
    def test_foreground_invocation_shape(self, task, delegation):
        """The bridge builds an invocation that names the role's preset
        with only the model-facing parameters."""
        inv = BuildInvocation.build(task, delegation)
        assert isinstance(inv, DSHInvocation)
        assert inv.agent_preset == "role-cto"
        args = inv.to_tool_args()
        assert set(TOOL_PARAMETER_KEYS).issubset(args.keys())
        assert args["description"] == "cto: delegated subtask"
        assert "objective" in args["prompt"] or "Task:" in args["prompt"]

    def test_prompt_is_self_contained_and_authorized(self, task, delegation):
        """The prompt is standalone and carries ONLY authorized data — never
        authority keys (THREAT-020)."""
        from orchestrator.dsh.context import _AUTHORITY_KEYS
        inv = BuildInvocation.build(task, delegation)
        lowered = {k.lower() for k in inv.to_tool_args()}
        for auth in _AUTHORITY_KEYS:
            assert auth not in lowered, f"authority key leaked into invocation: {auth}"

    def test_output_schema_is_task_result(self, task, delegation):
        """The output schema is the TaskResult shape (structured capture)."""
        inv = BuildInvocation.build(task, delegation)
        schema = inv.output_schema
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert "task_id" in schema["required"]
        assert "assigned_role" in schema["required"]

    def test_to_tool_args_excludes_schema(self, task, delegation):
        """The model-facing tool args never carry the schema (schema is a
        request-side option, not a tool parameter)."""
        inv = BuildInvocation.build(task, delegation)
        args = inv.to_tool_args()
        assert "output_schema" not in args


class TestStopReasonContract:
    def test_vocabulary_complete(self):
        assert set(STOP_REASONS) == {STOP_COMPLETED, STOP_ABORTED, STOP_ERROR,
                                     STOP_MAX_TOKENS, STOP_REFUSAL}

    def test_completed_is_success(self):
        o = map_stop_reason_to_outcome(STOP_COMPLETED)
        assert o["succeeded"] is True
        assert o["error"] is None

    def test_failures_are_not_success(self):
        for reason in (STOP_ABORTED, STOP_ERROR, STOP_MAX_TOKENS, STOP_REFUSAL):
            o = map_stop_reason_to_outcome(reason)
            assert o["succeeded"] is False, reason
            assert o["error"], reason

    def test_unknown_stop_reason_fails_closed(self):
        o = map_stop_reason_to_outcome("frobnicated")
        assert o["succeeded"] is False
        assert "abnormally" in o["error"]

    def test_failure_class_mapping(self):
        assert map_stop_reason_to_failure(STOP_ABORTED)[0] == "environment"
        assert map_stop_reason_to_failure(STOP_ERROR)[0] == "logic"
        assert map_stop_reason_to_failure(STOP_REFUSAL)[0] == "logic"
        assert map_stop_reason_to_failure("frobnicated")[0] == "unknown"
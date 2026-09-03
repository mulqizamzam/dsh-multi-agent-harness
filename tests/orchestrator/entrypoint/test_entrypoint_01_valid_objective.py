# E-01 — Valid objective through the front door → COMPLETE
#
# Prove that a well-shaped front-door request with a valid existing structured
# Delegation reaches COMPLETE through the bounded production run. All gates
# are preserved (risk, evidence, conflict, BadSector, authority, execution,
# verification).
#
# Tests: valid objective → ProductionRun → COMPLETE

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    COMPLETE,
    run_front_door,
    FrontDoorRequest,
)


class TestValidObjective:
    def test_valid_request_produces_complete(self, ws, subtask_runner,
                                             action_executor):
        """A valid request with an existing delegation → COMPLETE."""
        delegation = make_delegation()
        provider = make_provider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        request = FrontDoorRequest(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            delegation_id="delegation-prod-001",
            base=ws,
        )
        result = run_front_door(
            request,
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        assert result.status == COMPLETE, f"expected COMPLETE, got {result.status}: {result.errors}"
        assert result.run_id != ""
        assert result.state is not None
        assert result.state["outcome"] == "complete"
        assert result.report is not None
        assert result.report["outcome"] == "COMPLETE"
        assert len(result.audit_ids) > 0

    def test_valid_request_survives_json_serialization(self, ws, subtask_runner,
                                                        action_executor):
        """The FrontDoorResult for a COMPLETE run is JSON-serializable."""
        import json
        delegation = make_delegation()
        provider = make_provider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        request = FrontDoorRequest(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            delegation_id="delegation-prod-001",
            base=ws,
        )
        result = run_front_door(
            request,
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        serialized = json.dumps(result.to_dict())
        assert "COMPLETE" in serialized

    def test_valid_request_preserves_objective(self, ws, subtask_runner,
                                                action_executor):
        """The original objective text is preserved through the run."""
        delegation = make_delegation()
        provider = make_provider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        request = FrontDoorRequest(
            objective="engineering",
            scope=("agents/cto/output.txt",),
            delegation_id="delegation-prod-001",
            base=ws,
        )
        result = run_front_door(
            request,
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )

        assert result.objective == "engineering"
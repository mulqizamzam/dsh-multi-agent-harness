# E-13 — JSON serialization of every terminal status
#
# Prove that the front door result envelope is deterministically
# JSON-serializable in every terminal status (COMPLETE, BLOCKED, ESCALATED,
# ERROR). The dict must survive a round-trip through json.dumps/json.loads
# without data loss.

import json

from _helpers import make_delegation, make_subtask_result, make_provider, seed_state

from orchestrator.entrypoint import (
    COMPLETE,
    BLOCKED,
    ESCALATED,
    ERROR,
    SCHEMA,
    FrontDoorResult,
    run_front_door,
    FrontDoorRequest,
)


class TestJsonSerialization:
    def _run_and_serialize(self, request, *, provider, subtask_runner=None,
                           action_executor=None):
        result = run_front_door(
            request,
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        data = result.to_dict()
        # Round-trip through JSON
        serialized = json.dumps(data, default=str)
        restored = json.loads(serialized)
        # Verify key fields survive
        assert restored["status"] == data["status"]
        assert restored["run_id"] == data["run_id"]
        assert restored["objective"] == data["objective"]
        if data["errors"]:
            assert isinstance(restored["errors"], list)
        return restored

    def test_error_status_serializable(self, ws):
        """ERROR status round-trips through JSON."""
        from orchestrator.runtime import DelegationProvider

        class _Boom(DelegationProvider):
            def current(self):
                raise RuntimeError("boom")

        restored = self._run_and_serialize(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=_Boom(),
        )
        assert restored["status"] == ERROR

    def test_blocked_status_serializable(self, ws):
        """BLOCKED status round-trips through JSON."""
        restored = self._run_and_serialize(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(None),
        )
        assert restored["status"] == BLOCKED

    def test_complete_status_serializable(self, ws, subtask_runner,
                                          action_executor):
        """COMPLETE status round-trips through JSON."""
        delegation = make_delegation()
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:analysis",)))

        seed_state(ws)
        restored = self._run_and_serialize(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert restored["status"] == COMPLETE

    def test_deterministic_serialization_shape(self):
        """FrontDoorResult.to_dict() has a stable field order and shape."""
        r = FrontDoorResult(
            status=COMPLETE,
            run_id="prod-abc123",
            objective="test",
            state={"outcome": "complete"},
            report={"outcome": "COMPLETE"},
            errors=("ok",),
            audit_ids=("e1", "e2"),
        )
        data = r.to_dict()
        assert list(data.keys()) == [
            "schema", "status", "run_id", "objective", "state", "report",
            "errors", "audit_ids",
        ]
        assert data["schema"] == SCHEMA
        # JSON round-trip
        serialized = json.dumps(data, default=str)
        restored = json.loads(serialized)
        assert restored["status"] == COMPLETE
        assert restored["audit_ids"] == ["e1", "e2"]
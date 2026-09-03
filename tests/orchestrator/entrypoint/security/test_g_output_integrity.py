# Category G — OUTPUT INTEGRITY
#
# Prove the structured envelope is honest and complete:
#   G1 JSON serialization        G2 state/report preservation
#   G3 audit id preservation     G4 no fabricated run_id
#   G5 no fabricated report      G6 failure output remains honest
#
# Classification: every test asserts the observed envelope contents with
# evidence; the adapter never fabricates a run_id or a report for a failed run.

import json

import pytest

from ._availability import front_door_available, _NOT_YET_AVAILABLE

pytestmark = pytest.mark.skipif(not front_door_available(),
                                reason=_NOT_YET_AVAILABLE)

from .conftest import (  # noqa: E402
    make_delegation, make_subtask_result, make_provider, seed_state,
)


class TestJsonSerialization:
    def test_envelope_json_serializable(self, front_door, ws, delegation,
                                        provider, subtask_runner,
                                        action_executor):
        """G1: the envelope serializes to JSON (all terminal statuses)."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        text = json.dumps(result.to_dict(), default=str)
        parsed = json.loads(text)
        assert parsed["status"] == result.status
        assert "schema" in parsed

    def test_error_envelope_json_serializable(self, front_door):
        """G1: an ERROR envelope is also JSON-serializable."""
        result = front_door.run_front_door({
            "objective": "", "scope": (), "delegation_id": ""})
        text = json.dumps(result.to_dict(), default=str)
        parsed = json.loads(text)
        assert parsed["status"] == "ERROR"
        assert parsed["errors"]


class TestStateReportPreservation:
    def test_complete_state_preserved(self, front_door, ws, delegation,
                                      provider, subtask_runner,
                                      action_executor):
        """G2: COMPLETE envelope preserves the full state dict and report."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.state is not None
        assert result.report is not None
        # state/report are the exact dicts produced by the runtime
        assert result.state["run_id"] == result.run_id
        assert result.report["outcome"] == "COMPLETE"
        assert result.report["objective"] == "engineering"

    def test_objective_preserved(self, front_door, ws, delegation, provider,
                                 subtask_runner, action_executor):
        """G2: the original objective text is preserved in the envelope."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.objective == "engineering"


class TestAuditIdPreservation:
    def test_audit_ids_preserved_on_complete(self, front_door, ws, delegation,
                                             provider, subtask_runner,
                                             action_executor):
        """G3: audit_ids from the run are preserved in the envelope."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "COMPLETE"
        assert len(result.audit_ids) > 0
        # Envelope audit ids match the state's audit ids
        assert result.audit_ids == tuple(result.state["audit_ids"])

    def test_audit_ids_empty_when_no_run(self, front_door, ws, subtask_runner,
                                         action_executor):
        """G3: when no run started (DENY at resolution), audit_ids is empty."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(None),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.audit_ids == ()


class TestNoFabricatedRunId:
    def test_no_run_id_when_no_run(self, front_door, ws, subtask_runner,
                                   action_executor):
        """G4: a run that never started (no valid delegation) has run_id None
        — the adapter does not fabricate one."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(None),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.run_id is None

    def test_run_id_comes_from_state(self, front_door, ws, delegation,
                                     provider, subtask_runner,
                                     action_executor):
        """G4: on COMPLETE the envelope run_id is the state's run_id — not a
        fabricated value."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=provider,
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "COMPLETE"
        assert result.run_id.startswith("prod-")
        assert result.run_id == result.state["run_id"]


class TestNoFabricatedReport:
    def test_no_report_on_blocked(self, front_door, ws, subtask_runner,
                                  action_executor):
        """G5: a BLOCKED run has report None — no success report is
        fabricated."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(None),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.report is None

    def test_no_report_on_escalated(self, front_door, ws, subtask_runner,
                                    action_executor):
        """G5: an ESCALATED run has report None (no fabrication)."""
        delegation = make_delegation(requires_approval=("destructive",))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="proceed",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "ESCALATED"
        assert result.report is None


class TestFailureOutputHonest:
    def test_blocked_errors_present(self, front_door, ws, subtask_runner,
                                    action_executor):
        """G6: a BLOCKED run carries error messages explaining the denial."""
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(None),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "BLOCKED"
        assert result.errors
        # errors are strings
        assert all(isinstance(e, str) for e in result.errors)

    def test_escalated_errors_explain_approval(self, front_door, ws,
                                               subtask_runner,
                                               action_executor):
        """G6: an ESCALATED run explains the approval requirement."""
        delegation = make_delegation(requires_approval=("destructive",))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="proceed",
            evidence=("artifact:analysis",)))
        seed_state(ws)
        result = front_door.run_front_door(
            front_door.FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
                base=ws,
            ),
            provider=make_provider(delegation),
            subtask_runner=subtask_runner,
            action_executor=action_executor,
        )
        assert result.status == "ESCALATED"
        assert any("approval" in e.lower() for e in result.errors)
# tests/observability/test_ledger_integration.py — Integration with real audit
# primitives (read-only)
#
# Proves the observability package reuses the existing audit helpers
# (read_events_strict, verify_append_only, verify_chain, audit_is_authority
# _source) rather than creating a second audit implementation.

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

import observability as obs
from orchestrator.runtime.audit import RuntimeAudit
from tests.observability.conftest import complete_run_events


def test_build_index_from_ledger(o3_daemon_ws):
    """Write events to a temp ledger via RuntimeAudit, then read them back
    through build_index_from_ledger, proving reuse of the existing audit
    helpers. After O3 Phase B, audit_emit routes through the O3 daemon;
    uses the temp-daemon fixture (daemon root == workspace)."""
    base, client, daemon = o3_daemon_ws
    project = "test-obs"
    os.makedirs(os.path.join(base, "audit", project), exist_ok=True)
    audit = RuntimeAudit(base=base, project=project)
    emitted = []
    # Emit a realistic event sequence through the sanctioned audit channel.
    emitted.append(audit.emit("flow_started", action="run",
                               target="test objective"))
    emitted.append(audit.emit("intake_recorded", action="intake",
                               target="test objective", task_id="task-1"))
    emitted.append(audit.emit("gate_risk", action="risk_gate",
                               target="test", task_id="task-1",
                               result="allowed"))
    emitted.append(audit.emit("delegation_issued", action="delegate",
                               target="task-1", task_id="task-1",
                               authority_source="delegation-test",
                               result="allowed"))
    emitted.append(audit.emit("subtasks_executed", action="execute",
                               target="task-1", task_id="task-1",
                               result="allowed",
                               extra={"count": 1, "parallel": False}))
    emitted.append(audit.emit("result_collected", action="collect",
                               target="task-1:cto", task_id="task-1",
                               result="recorded",
                               extra={"role": "cto", "status": "SUCCEEDED"},
                               evidence=("agents/cto/output.txt",)))
    emitted.append(audit.emit("gate_authority", action="authority_gate",
                               target="test", task_id="task-1",
                               authority_source="delegation-test",
                               result="allowed"))
    emitted.append(audit.emit("execution_attempt", action="execute",
                               target="test", task_id="task-1",
                               authority_source="delegation-test",
                               result="executed",
                               extra={"verdict": "PASSED"}))
    emitted.append(audit.emit("verification_passed", action="verify",
                               target="task-1", task_id="task-1",
                               result="allowed", extra={"verdict": "PASSED"}))
    emitted.append(audit.emit("state_complete", action="close",
                               target="task-1", task_id="task-1",
                               result="completed", new_state="COMPLETE"))
    emitted.append(audit.emit("flow_finished", action="finish",
                               target="task-1", task_id="task-1",
                               result="complete",
                               extra={"outcome": "COMPLETE"}))
    assert len(emitted) == 11

    # Read the ledger through the observability ingest (reuses
    # read_events_strict, verify_append_only, verify_chain).
    idx = obs.build_index_from_ledger(base=base, project=project)
    assert len(idx.run_order) == 1, (
        f"expected 1 run, got {idx.run_order}")
    run = idx.runs[idx.run_order[0]]
    assert run.outcome == obs.OUTCOME_COMPLETE
    assert run.run_id_derived  # no explicit run_id in audit events
    assert "task-1" in run.tasks
    assert "delegation-test" in run.delegations
    assert "agents/cto/output.txt" in run.evidence_refs
    assert not run.problems, f"unexpected problems: {run.problems}"
    assert not idx.rejected, f"unexpected rejections: {idx.rejected}"

    # Verify ledger integrity checks were run (reuse of existing
    # primitives).
    assert idx.ledger_integrity.get("strict_ok") is True
    assert idx.ledger_integrity.get("append_only_ok") is True
    # audit_is_authority_source always False
    assert idx.ledger_integrity["audit_is_authority_source"] is False


def test_ledger_reuse_read_events_strict():
    """Prove the observability ingest uses the strict reader (not a lenient
    one) and that a corrupt ledger is detected via the integrity check."""
    with tempfile.TemporaryDirectory() as tmp:
        fpath = os.path.join(tmp, "audit", "test", "events.jsonl")
        os.makedirs(os.path.dirname(fpath))
        with open(fpath, "w") as f:
            f.write('{"event_id":"e1","event_class":"flow_started",'
                    '"timestamp":"2026-08-30T23:00:00Z","target":"t"}\n')
            f.write('not-json\n')  # corrupt line
        idx = obs.build_index_from_ledger(base=tmp, project="test")
        assert idx.ledger_integrity.get("strict_ok") is False
        assert "strict_error" in idx.ledger_integrity
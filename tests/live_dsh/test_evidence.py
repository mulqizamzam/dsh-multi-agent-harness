# tests/live_dsh/test_evidence.py — evidence model for the REAL bridge
#
# Evidence is recorded from RUNTIME ARTIFACTS (dispatch records, stop reasons,
# structured results, provenance) — never from agent prose.

import json
import os

from .backend_kind import BackendKind
from .evidence import (
    BridgeEvidence, capture_dispatch_evidence,
    capture_provenance_evidence, write_evidence_bundle,
)
from .contract import STOP_COMPLETED, STOP_ERROR, BuildInvocation
from .conftest import make_task, make_delegation


class TestEvidenceModel:
    def test_capture_dispatch_evidence(self):
        ev = capture_dispatch_evidence(
            flow_id="flow-e1", task_id="task-1", role="cto",
            delegation_id="delegation-e1", tool_name="subagent_cto",
            persona="role-cto",
            invocation=BuildInvocation.build(make_task(role="cto"),
                                             make_delegation()),
            run_id="r1", stop_reason=STOP_COMPLETED,
            structured={"status": "SUCCEEDED"},
            backend_kind=BackendKind.REAL, mounted=True,
        )
        assert ev.succeeded is True
        assert ev.backend_kind == "real-dsh"
        assert ev.mounted is True
        assert ev.structured_result == {"status": "SUCCEEDED"}
        assert ev.tool_name == "subagent_cto"

    def test_failed_dispatch_evidence(self):
        ev = capture_dispatch_evidence(
            flow_id="flow-e2", task_id="task-2", role="cto",
            tool_name="subagent_cto", persona="role-cto",
            run_id="r2", stop_reason=STOP_ERROR, diagnostic="model failure",
            backend_kind=BackendKind.REAL, mounted=True,
        )
        assert ev.succeeded is False
        assert "model failure" in ev.error

    def test_provenance_capture(self):
        task = make_task(role="cto")
        delegation = make_delegation(task=task.task_id)
        from .adapters import build_role_adapter
        instance = build_role_adapter("cto").instance
        prov = capture_provenance_evidence(task=task, delegation=delegation,
                                           instance=instance,
                                           started_at="2026-08-30T00:00:00Z",
                                           settled_at="2026-08-30T00:00:01Z")
        assert prov["role"] == "cto"
        assert prov["tool_name"] == "subagent_cto"
        assert prov["delegation_id"] == delegation.id

    def test_evidence_bundle_written(self, tmp_path):
        ev = capture_dispatch_evidence(
            flow_id="flow-e3", task_id="task-3", role="cto",
            tool_name="subagent_cto", persona="role-cto",
            run_id="r3", stop_reason=STOP_COMPLETED,
            backend_kind=BackendKind.FAKE,
        )
        path = write_evidence_bundle(ev, path=str(tmp_path / "bundle.json"))
        with open(path) as f:
            doc = json.load(f)
        assert doc["task_id"] == "task-3"
        assert doc["stop_reason"] == STOP_COMPLETED

    def test_evidence_is_data_not_authority(self):
        """Evidence records never carry an authority grant — the delegation id
        is a reference, not a grant (AUTH-INV-14)."""
        ev = capture_dispatch_evidence(
            flow_id="f", task_id="t", role="cto", delegation_id="delegation-e9",
            tool_name="subagent_cto", persona="role-cto",
            run_id="r9", stop_reason=STOP_COMPLETED,
            backend_kind=BackendKind.REAL, mounted=True,
        )
        doc = ev.to_dict()
        assert "approved" not in doc
        assert "grant" not in doc
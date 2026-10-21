# tests/live_dsh/evidence.py — evidence bundle for the REAL bridge (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Defines the evidence model the harness records for each REAL (or simulated)
# DSH delegation, so that after the composition is mounted a run can be proven
# from RUNTIME ARTIFACTS — never from agent prose:
#   - dispatch record (tool_name, role, task_id, run identity, timestamps)
#   - invocation sent (authorized context only)
#   - settled outcome (stop reason, structured TaskResult)
#   - provenance stamp (role identity + runtime facts)
#   - mount/backend kind (FAKE vs REAL vs UNAVAILABLE)
#
# Evidence is DATA. Recording it never grants authority.

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field as dc_field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .backend_kind import BackendKind
from .contract import (
    DSHInvocation, map_stop_reason_to_outcome,
)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class BridgeEvidence:
    """One delegation's evidence bundle for the REAL bridge harness."""

    flow_id: str = ""
    task_id: str = ""
    role: str = ""
    delegation_id: str = ""
    tool_name: str = ""
    agent_preset: str = ""
    backend_kind: str = BackendKind.FAKE.value
    mounted: bool = False
    invocation: dict = dc_field(default_factory=dict)
    run_id: str = ""
    started_at: str = ""
    settled_at: str = ""
    stop_reason: str = ""
    succeeded: bool = False
    error: str = ""
    structured_result: dict | None = None
    provenance: dict = dc_field(default_factory=dict)
    audit_events: list = dc_field(default_factory=list)
    extra: dict = dc_field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "task_id": self.task_id,
            "role": self.role,
            "delegation_id": self.delegation_id,
            "tool_name": self.tool_name,
            "agent_preset": self.agent_preset,
            "backend_kind": self.backend_kind,
            "mounted": self.mounted,
            "invocation": dict(self.invocation),
            "run_id": self.run_id,
            "started_at": self.started_at,
            "settled_at": self.settled_at,
            "stop_reason": self.stop_reason,
            "succeeded": self.succeeded,
            "error": self.error,
            "structured_result": self.structured_result,
            "provenance": dict(self.provenance),
            "audit_events": list(self.audit_events),
            "extra": dict(self.extra),
        }


def capture_dispatch_evidence(*, flow_id: str = "", task_id: str = "",
                              role: str = "", delegation_id: str = "",
                              tool_name: str = "", agent_preset: str = "",
                              invocation: DSHInvocation | None = None,
                              run_id: str = "", stop_reason: str = "",
                              structured: dict | None = None,
                              diagnostic: str = "",
                              backend_kind: BackendKind = BackendKind.FAKE,
                              mounted: bool = False,
                              started_at: str = "", settled_at: str = "") -> BridgeEvidence:
    """Build an evidence record for one delegation dispatch."""
    outcome = map_stop_reason_to_outcome(stop_reason)
    ev = BridgeEvidence(
        flow_id=flow_id, task_id=task_id, role=role,
        delegation_id=delegation_id, tool_name=tool_name, agent_preset=agent_preset,
        backend_kind=backend_kind.value, mounted=mounted,
        invocation=invocation.to_dict() if invocation is not None else {},
        run_id=run_id,
        started_at=started_at or now_iso(),
        settled_at=settled_at or now_iso(),
        stop_reason=stop_reason,
        succeeded=outcome["succeeded"],
        # The provider diagnostic is the most specific failure detail; the
        # generic stop-reason message is the fallback.
        error=diagnostic or outcome["error"] or "",
        structured_result=structured,
    )
    return ev


def capture_provenance_evidence(*, task, delegation, instance, run=None,
                                result=None, started_at: str = "",
                                settled_at: str = "") -> dict:
    """Build the adapter provenance stamp (role identity + runtime facts)."""
    from orchestrator.dsh.provenance import DelegationProvenance
    prov = DelegationProvenance.build(
        delegation=delegation, task=task, instance=instance, run=run,
        started_at=started_at, settled_at=settled_at, result=result,
        result_status=(getattr(result, "structured", None) or {}).get("status", "")
        if result is not None else "",
    )
    return prov.to_dict()


def write_evidence_bundle(evidence: BridgeEvidence | list[BridgeEvidence],
                          *, path: str) -> str:
    """Write the evidence bundle to disk as JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (evidence.to_dict() if isinstance(evidence, BridgeEvidence)
            else [e.to_dict() for e in evidence])
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


__all__ = ["BridgeEvidence", "capture_dispatch_evidence",
           "capture_provenance_evidence", "write_evidence_bundle", "now_iso"]
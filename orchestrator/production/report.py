# orchestrator.production.report — Structured final report generation
#
# Phase 4 / Session A. Produces the FINAL structured report for a bounded
# production run. The report is DATA (never authority — AUTH-INV-13/14):
#   - it summarizes the objective, the plan, the flow result, the gates, the
#     collected specialist results, the verification verdict, and the outcome
#   - it NEVER grants authority, NEVER fabricates success, and refuses to
#     generate a "success" report from a non-COMPLETE run (fail-closed)
#   - it preserves disagreement/risks from the synthesis (no voting, no
#     majority resolution)
#
# The report generator reuses the Phase-3 FlowResult; it does not reimplement
# any gate. It only shapes the data into a deterministic, JSON-serializable
# final report.

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import datetime, timezone

from orchestrator.runtime.result import (
    FlowResult, COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING,
)

from .exceptions import ReportGenerationFailed


def _now_iso(now=None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class FinalReport:
    """The deterministic final report of one production run.

    outcome:
        COMPLETE / BLOCKED / FAILED / ESCALATED / RECOVERING (mirrors the
        FlowResult terminal disposition).
    objective / project / task_id / flow_id:
        Run identity.
    gates:
        Every gate decision recorded in the flow (phase, gate, decision,
        reason).
    selected_roles:
        The minimum specialist set that executed (routing result).
    synthesis:
        The consolidated synthesis (findings, recommendations, risks,
        assumptions, unresolved items, roles) — preserved, never voted.
    verification:
        The verification verdict (reported != verified).
    files_written:
        Artifacts written through the execution gate.
    errors:
        Any errors recorded during the run.
    generated_at:
        Report timestamp.
    """
    outcome: str = BLOCKED
    objective: str = ""
    project: str = "multi-agent-harness"
    task_id: str = ""
    flow_id: str = ""
    gates: tuple = field(default_factory=tuple)
    selected_roles: tuple = field(default_factory=tuple)
    synthesis: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    files_written: tuple = field(default_factory=tuple)
    errors: tuple = field(default_factory=tuple)
    generated_at: str = field(default_factory=_now_iso)

    def summary(self) -> dict:
        """A compact human-facing summary (DATA)."""
        return {
            "outcome": self.outcome,
            "objective": self.objective,
            "selected_roles": list(self.selected_roles),
            "verification_verdict": self.verification.get("verdict"),
            "files_written": list(self.files_written),
            "errors": list(self.errors),
        }

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "objective": self.objective,
            "project": self.project,
            "task_id": self.task_id,
            "flow_id": self.flow_id,
            "gates": list(self.gates),
            "selected_roles": list(self.selected_roles),
            "synthesis": dict(self.synthesis),
            "verification": dict(self.verification),
            "files_written": list(self.files_written),
            "errors": list(self.errors),
            "generated_at": self.generated_at,
        }


class ReportGenerator:
    """Generate a FinalReport from a FlowResult.

    Fail-closed: a non-COMPLETE flow cannot produce a success report. A
    report is always generated (with the true outcome) for any terminal
    disposition, so a BLOCKED/FAILED run still yields an honest structured
    report.
    """

    def __init__(self, *, now=None):
        self._now = now

    def generate(self, flow_result: FlowResult,
                 audit=None) -> FinalReport:
        """Build the final report from a FlowResult.

        Parameters
        ----------
        flow_result:
            The Phase-3 FlowResult of the executed flow.
        audit:
            Optional RuntimeAudit (not used for authority — only to record
            the report generation event).

        Raises
        ------
        ReportGenerationFailed
            When the flow result is missing/malformed or the report cannot be
            built (fail-closed).
        """
        if not isinstance(flow_result, FlowResult):
            raise ReportGenerationFailed(
                "report requires a FlowResult, got "
                f"{type(flow_result).__name__}")

        # Never fabricate success: if the flow did not COMPLETE, the report
        # must carry the true (non-success) outcome.
        outcome = flow_result.outcome or BLOCKED
        report = FinalReport(
            outcome=outcome,
            objective=flow_result.objective or "",
            project=flow_result.project or "multi-agent-harness",
            task_id=flow_result.task_id or "",
            flow_id=flow_result.flow_id or "",
            gates=tuple(g.to_dict() if hasattr(g, "to_dict") else dict(g)
                        for g in flow_result.gates or ()),
            selected_roles=tuple(flow_result.selected or ()),
            synthesis=dict(flow_result.synthesis or {}),
            verification=dict(flow_result.verification or {}),
            files_written=tuple(flow_result.files_written or ()),
            errors=tuple(flow_result.errors or ()),
            generated_at=_now_iso(self._now),
        )
        if audit is not None:
            try:
                audit.emit("final_report", action="report",
                           target=flow_result.task_id or "",
                           task_id=flow_result.task_id or "",
                           result="generated",
                           extra={"outcome": outcome,
                                  "selected": list(report.selected_roles)})
            except Exception:  # noqa: BLE001 — report is data; audit best-effort
                pass
        return report


__all__ = ["FinalReport", "ReportGenerator"]
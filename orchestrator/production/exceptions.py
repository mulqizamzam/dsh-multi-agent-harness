# orchestrator.production.exceptions — Production Execution Flow error vocabulary
#
# Phase 4 / Session A. These are the production-layer's typed errors. They
# WRAP (never replace) the Phase-3 runtime and control-plane typed errors:
#   - orchestrator.runtime.exceptions (FlowStopped / GateDenied / GateEscalated /
#     AuthorityDenied / StaleStateDetected / RecoveryRefusedByRuntime /
#     SubtaskFailed / ParallelUnsafe)
#   - orchestrator.execution.exceptions (ExecutionDenied / ExecutionRefused)
#   - control.* Denied / Refused exceptions
#
# Fail-closed: any denial / non-actionable objective / rejected plan STOPS the
# production run with a typed error carrying the phase + reason (AUTH-INV-20).

from __future__ import annotations


class ProductionError(ValueError):
    """Base production-layer error (fail-closed)."""


class ProductionStopped(ProductionError):
    """A production run stopped before COMPLETE (gate denial, escalation,
    non-actionable objective, rejected plan). Carries the phase + reason."""

    def __init__(self, phase: str = "", reason: str = "",
                 decision: str = "DENY", detail: dict | None = None):
        self.phase = phase
        self.reason = reason
        self.decision = decision
        self.detail = detail or {}
        super().__init__(
            f"production run stopped at {phase or '?'} "
            f"(decision={decision}): {reason}")


class ProductionDenied(ProductionStopped):
    """A gate / authority / execution denial stopped the production run."""


class ProductionEscalated(ProductionStopped):
    """An ESCALATE decision stopped the production run (Human attention
    required)."""


class NoValidDelegation(ProductionStopped):
    """No ACTIVE delegation could be established for the objective's authority
    context. The authority gate consumes structured records only
    (AUTH-INV-05)."""


class ObjectiveNotActionable(ProductionStopped):
    """The objective cannot be turned into an actionable plan (missing /
    malformed input, unknown domain, empty scope)."""


class PlanRejected(ProductionStopped):
    """The production plan was rejected at a gate (risk / evidence / conflict /
    review / authority / execution / verification)."""


class ReportGenerationFailed(ProductionError):
    """The final report could not be generated (fail-closed: a missing report
    never becomes a partial success)."""


__all__ = [
    "ProductionError",
    "ProductionStopped",
    "ProductionDenied",
    "ProductionEscalated",
    "NoValidDelegation",
    "ObjectiveNotActionable",
    "PlanRejected",
    "ReportGenerationFailed",
]
# orchestrator.runtime.exceptions — Production runtime error vocabulary (Phase 3)
#
# The runtime fails CLOSED: any gate denial, authority denial, stale state,
# or unresolved transition STOPS the flow with a typed error (AUTH-INV-20).
# These names are the runtime's contract with the runbooks (01..09): a typed
# exception carries the gate/phase/reason so recovery can branch without
# parsing prose.

from __future__ import annotations


class RuntimeFlowError(ValueError):
    """Base runtime error (fail-closed)."""


class FlowStopped(RuntimeFlowError):
    """A gate / authority / state check stopped the flow (AUTH-INV-20).

    Carries the phase where the flow stopped, the gate that refused (when
    applicable), the decision (DENY / ESCALATE), and the reason.
    """

    def __init__(self, phase: str = "", gate: str = "", decision: str = "DENY",
                 reason: str = "", detail: dict | None = None):
        self.phase = phase
        self.gate = gate
        self.decision = decision
        self.reason = reason
        self.detail = detail or {}
        super().__init__(
            f"flow stopped at {phase or '?'} (gate={gate or '?'}, "
            f"decision={decision}): {reason}")


class GateDenied(FlowStopped):
    """A gate returned DENY — the action must not proceed."""


class GateEscalated(FlowStopped):
    """A gate returned ESCALATE — Human attention is required (material
    conflict, approval requirement, mandatory review gap, unknown failure)."""


class StaleStateDetected(RuntimeFlowError):
    """State/version drift detected before a consequential action
    (THREAT-021/022): the caller must re-read current state and re-validate
    authority before proceeding."""


class AuthorityDenied(RuntimeFlowError):
    """The authority gate (planning or execution-time re-check) denied the
    action (AUTH-INV-05/06/11)."""


class RecoveryRefusedByRuntime(RuntimeFlowError):
    """The recovery handoff refused the attempt: no blind retry, identical
    cause, exhausted budget, stale version, or authority re-check denial
    (AUTH-INV-12/16, THREAT-017/022, REC-001..005)."""


class SubtaskFailed(RuntimeFlowError):
    """A delegated specialist subtask did not produce a usable result.

    Covers the DSH adapter's typed failures (timeout / abort / child failure /
    malformed result / role resolution / delegation denial) and a collected
    result whose claimed status is FAILED or BLOCKED. The failure PROPAGATES:
    the flow stops fail-closed with no partial execution and no silent skip
    (INT-12, AUTH-INV-20 / INV-15).
    """

    def __init__(self, role: str = "", task_id: str = "",
                 failure_class: str = "unknown", reason: str = ""):
        self.role = role
        self.task_id = task_id
        self.failure_class = failure_class
        self.reason = reason
        super().__init__(
            f"subtask {task_id or '?'} ({role or '?'}) failed "
            f"[{failure_class}]: {reason}")


class ParallelUnsafe(RuntimeFlowError):
    """A parallel subtask batch is not provably safe to run concurrently.

    Raised BEFORE any child starts when dependency independence, single task
    ownership, or read/write scope disjointness cannot be established, or when
    a specialist subtask declares a write scope at all — the orchestrator is
    the single authoritative writer, specialists return results and never write
    project state (contract §6, THREAT-021).
    """


__all__ = [
    "RuntimeFlowError",
    "FlowStopped",
    "GateDenied",
    "GateEscalated",
    "StaleStateDetected",
    "AuthorityDenied",
    "RecoveryRefusedByRuntime",
    "SubtaskFailed",
    "ParallelUnsafe",
]

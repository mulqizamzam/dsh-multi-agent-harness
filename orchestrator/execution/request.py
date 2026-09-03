# orchestrator/execution/request.py — Execution request object + validation
#
# The runtime execution request is the single structured input to the
# ExecutionEngine. It carries the concrete action/target/environment to be
# performed, the structured authority record (Delegation), the EXPECTED
# outcome (declared BEFORE execution — VERIFY-001), and the plan/state version
# the request was built against (for THREAT-022 stale-plan refusal).
#
# The request carries DATA + the authority RECORD, never a grant. Nothing here
# authorizes; the execution engine re-passes the same gates the original action
# used (AUTH-INV-12).

from __future__ import annotations

from dataclasses import dataclass, field

from control.execution_gate import WRITE_ACTIONS as _GATE_WRITE_ACTIONS
from control.verification import (
    action_category,
    verification_requirements,
    VerificationError,
)
from orchestrator.foundation.contracts import Delegation

# ---------------------------------------------------------------------------
# Write-class action vocabulary
# ---------------------------------------------------------------------------
# The execution gate's WRITE_ACTIONS plus the canonical write-like action
# classes from the verification table (control/verification.py
# _ACTION_TO_CATEGORY). Any action in this set must pass the path-aware
# execution gate (control.execution_gate.authorize_write) before execution —
# no unrestricted execution.
WRITE_CLASS_ACTIONS: frozenset = frozenset(
    _GATE_WRITE_ACTIONS
    | {
        "code_write", "production_deploy", "deploy", "server_write", "infra",
        "financial_transaction", "credential_change", "sensitive_publication",
        "publish", "rollback", "recovery",
    }
)


@dataclass(frozen=True)
class ExecutionRequest:
    """A single runtime execution request.

    task_id:          the task being executed
    actor:            identity of the actor that will perform the action
    action:           the concrete action class (e.g. "code_write", "write")
    target:           the concrete execution target (path)
    environment:      the concrete execution environment
    delegation:       the structured authority record (Delegation object).
                      REQUIRED — the engine DENYs any request without one
                      (AUTH-INV-05).
    expected_outcome: dict of observable properties expected AFTER execution,
                      declared BEFORE execution (VERIFY-001). The engine
                      compares the captured actual outcome against it.
    action_category:  optional explicit verification category; when empty it
                      is derived from `action` via
                      control.verification.action_category (fail-closed on
                      unknown actions).
    revocation_list:  ids of revoked delegations (execution-time check).
    approval_reference: Human approval reference for requires_approval.
    project:          the execution project (must match the delegation).
    state_version:    the plan/state version this request was built against;
                      the engine refuses to execute when the current version
                      has moved past it (THREAT-022 / REC-005).
    max_attempts:     retry budget (per diagnosed cause — no blind retry,
                      AUTH-INV-16 / REC-001).
    max_rework_cycles: recovery rework bound (contract §11).
    """

    task_id: str
    actor: str = "orchestrator"
    action: str = "write"
    target: str = ""
    environment: str = "dev"
    delegation: object = None  # a Delegation object (structured authority)
    expected_outcome: dict = field(default_factory=dict)
    action_category: str = ""
    revocation_list: tuple = ()
    approval_reference: str = ""
    project: str = "multi-agent-harness"
    state_version: int = 0
    max_attempts: int = 1
    max_rework_cycles: int = 2

    def __post_init__(self):
        if not (self.task_id or "").strip():
            raise ValueError("ExecutionRequest: task_id must be non-empty")
        if not (self.actor or "").strip():
            raise ValueError("ExecutionRequest: actor must be non-empty")
        if not (self.action or "").strip():
            raise ValueError("ExecutionRequest: action must be non-empty")
        if not (self.target or "").strip():
            raise ValueError("ExecutionRequest: target must be non-empty")
        if not isinstance(self.expected_outcome, dict):
            raise ValueError("ExecutionRequest: expected_outcome must be a dict")
        if self.delegation is not None and not isinstance(self.delegation, Delegation):
            raise ValueError(
                "ExecutionRequest: delegation must be a structured Delegation "
                "object (AUTH-INV-01/05); model text is never authority")
        # Resolve the action category at construction time (fail-closed on
        # unknown actions, matching the verification module's contract).
        self.resolve_action_category()

    def resolve_action_category(self) -> str:
        """Return the verification category for this request.

        Uses the explicit `action_category` when set; otherwise derives it
        from `action`. Raises VerificationError on unknown categories
        (fail-closed).
        """
        cat = (self.action_category or "").strip()
        if not cat:
            cat = action_category(self.action)
        verification_requirements(cat)  # raises on unknown (fail-closed)
        return cat

    def is_write_class(self) -> bool:
        """True when this request's action is write-like and therefore must
        pass the path-aware execution gate (no unrestricted execution)."""
        return (self.action or "").lower() in WRITE_CLASS_ACTIONS

    def original_authority(self) -> dict:
        """The structured baseline of what the ORIGINAL action was permitted.

        Used by recovery (control.recovery.RecoveryController
        assert_privilege_bounded) to prove the recovery attempt does not
        escalate privilege beyond the original authority (REC-004 /
        THREAT-017). Data only — never a grant (AUTH-INV-12/14).
        """
        d = self.delegation
        if not isinstance(d, Delegation):
            return {}
        grants = (
            ["write"] if self.is_write_class() else []
        )
        return {
            "actions": list(d.scope_operations) or [self.action],
            "targets": list(d.scope_resources) or [self.target],
            "grants": grants,
        }

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "environment": self.environment,
            "delegation_id": getattr(self.delegation, "id", ""),
            "expected_outcome": dict(self.expected_outcome),
            "action_category": self.resolve_action_category(),
            "revocation_list": list(self.revocation_list),
            "approval_reference": self.approval_reference,
            "project": self.project,
            "state_version": self.state_version,
            "max_attempts": self.max_attempts,
            "max_rework_cycles": self.max_rework_cycles,
        }
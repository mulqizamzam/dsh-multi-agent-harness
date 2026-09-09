# orchestrator.foundation — Orchestrator Foundation contracts (Phase 1D)
#
# Phase 1D Orchestrator Foundation. Scope: multi-agent-harness/ only.
#
# This module defines the concrete, validated data contracts the orchestrator
# consumes and produces:
#   - TaskIntake       (normalized objective + scope + constraints + expected
#                       outcome + required authority context)
#   - Task             (decomposition: task_id, parent, role, deps, expected
#                       output, risk metadata, authorization requirements)
#   - Delegation       (the scoped authority record; validated against
#                       schemas/delegation.schema.json)
#   - TaskResult       (result collection: findings, evidence, assumptions,
#                       risks, recommendation, confidence, unresolved,
#                       actions taken, status)
#
# These are DRAFT/contract objects — they carry DATA, never authority.
# Model text alone can never mutate consequential state (AUTH-INV-07/13).

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Role / classification vocabulary (PRD v0.2 — 15-specialist on-demand pool;
# ADR 0003). Baseline seven first, expansion eight appended in PRD §9 order.
# ---------------------------------------------------------------------------
SPECIALIST_ROLES = (
    "zeko", "cto", "cfo", "kai", "somad", "badsector", "nova",
    "vera", "argus", "atlas", "tess", "quill", "scout", "talon", "ledger",
)
ORCHESTRATOR = "orchestrator"
ALL_ROLES = SPECIALIST_ROLES + (ORCHESTRATOR,)

# Domain fit: classify a task's domain and map to the MINIMUM specialist set.
# A task maps to exactly one primary role; some domains legitimately need a
# secondary (e.g. finance+research). Routing NEVER fans out to all 15.
# Matcher note: select_agents uses longest-key specificity, so the specific
# `architecture_review` (atlas) wins over its substring `architecture` (cto)
# while free-text architecture stays cto (ADR 0003 D6).
DOMAIN_ROLE = {
    "operations": "zeko",
    "engineering": "cto",
    "architecture": "cto",
    "coding": "cto",
    "testing": "cto",
    "security_review": "badsector",
    "finance": "cfo",
    "pricing": "cfo",
    "economics": "cfo",
    "cost": "cfo",
    "research": "kai",
    "news": "kai",
    "market_research": "kai",
    "trend": "kai",
    "social": "somad",
    "content": "somad",
    "campaign": "somad",
    "audience": "somad",
    "writing": "nova",
    "novel": "nova",
    "editing": "nova",
    "adversarial_review": "badsector",
    "review": "badsector",
    "red_team": "badsector",
    # PRD v0.2 §9.1: Vera owns verification; the badsector mapping was a
    # Phase-1D stopgap before any verification specialist existed (ADR 0003 D6).
    "verification": "vera",
    # ── PRD v0.2 expansion (ADR 0003) ─────────────────────────────────────
    "evidence": "vera",
    "acceptance": "vera",
    "security": "argus",
    "threat_model": "argus",
    "privilege_analysis": "argus",
    "trust_boundary": "argus",
    "architecture_review": "atlas",
    "dependency_boundary": "atlas",
    "coupling": "atlas",
    "failure_analysis": "tess",
    "timeout": "tess",
    "cancellation": "tess",
    "race_condition": "tess",
    "policy": "quill",
    "invariant": "quill",
    "specification": "quill",
    "integration": "scout",
    "compatibility": "scout",
    "version_drift": "scout",
    "reliability": "talon",
    "idempotency": "talon",
    "retry": "talon",
    "rollback": "talon",
    "audit": "ledger",
    "provenance": "ledger",
    "lineage": "ledger",
}
# Domains that additionally require a secondary specialist (minimum set, still
# never all 15).
DOMAIN_SECONDARY = {
    "pricing": "kai",      # pricing analysis feeds on market research
    "market_research": "cfo",  # research feeding a financial decision
    "security_review": "cto",  # adversarial review of engineering work
    "security": "badsector",   # adversarial challenge of security analysis
    "integration": "atlas",    # PRD v0.2 §16.3: architectural fit
    "reliability": "tess",     # PRD v0.2 §16.2: failure analysis
    "failure_analysis": "talon",  # recovery semantics beside failure analysis
}

RISK_CLASSES = ("LOW", "MEDIUM", "HIGH")


class ContractError(ValueError):
    """Raised when a contract object is invalid (fail-closed)."""


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_nonempty(value, field_name, obj):
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ContractError(f"{obj}: `{field_name}` must be a non-empty string")
    if isinstance(value, (list, tuple)) and len(value) == 0:
        raise ContractError(f"{obj}: `{field_name}` must be non-empty")
    return value


def _require_valid_role(role):
    if role not in SPECIALIST_ROLES:
        raise ContractError(f"invalid role {role!r}; must be one of {SPECIALIST_ROLES}")


def _jsonable(d):
    """Recursively convert dataclass tuples/objects to JSON-able types
    (tuples -> lists), so to_dict() output validates against JSON Schema."""
    import dataclasses
    if isinstance(d, tuple):
        return [_jsonable(x) for x in d]
    if isinstance(d, list):
        return [_jsonable(x) for x in d]
    if isinstance(d, dict):
        return {k: _jsonable(v) for k, v in d.items()}
    if dataclasses.is_dataclass(d):
        return _jsonable(asdict(d))
    return d


# ===========================================================================
# 1. TASK INTAKE CONTRACT
# ===========================================================================
@dataclass(frozen=True)
class TaskIntake:
    """Normalized objective intake. The first contract in the lifecycle.

    authority_context: the delegation id (or Human approval reference) under
        which this objective may be pursued. Absent → the orchestrator must
        escalate; the intake is accepted as DRAFT but not actionable.
    """
    objective: str
    scope: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    expected_outcome: str = ""
    required_authority_context: str = ""     # delegation id / approval ref
    project: str = "multi-agent-harness"
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self):
        _require_nonempty(self.objective, "objective", "TaskIntake")
        _require_nonempty(self.scope, "scope", "TaskIntake")
        _require_nonempty(self.project, "project", "TaskIntake")
        if not isinstance(self.expected_outcome, str):
            raise ContractError("TaskIntake: `expected_outcome` must be a string")

    def normalized_objective(self) -> str:
        return re.sub(r"\s+", " ", self.objective.strip())

    def has_authority_context(self) -> bool:
        return bool(self.required_authority_context.strip())

    def to_dict(self):
        return _jsonable(asdict(self))


# ===========================================================================
# 2. TASK DECOMPOSITION CONTRACT
# ===========================================================================
@dataclass(frozen=True)
class Task:
    """A decomposed unit of work assigned to exactly one specialist.

    parent_task: id of the parent task ("" for a root task).
    assigned_role: the single specialist that owns this task.
    dependencies: ids of tasks that must complete first.
    risk_metadata: LOW/MEDIUM/HIGH (deterministic; intrinsic HIGH not
        downgradable — model judgment cannot lower it).
    authorization_requirements: requires_approval categories the task needs
        (destructive / financial_transfer / sensitive_publication /
        credential_change).
    """
    task_id: str
    objective: str
    assigned_role: str
    parent_task: str = ""
    dependencies: tuple[str, ...] = ()
    expected_output: str = ""
    risk_metadata: str = "LOW"
    authorization_requirements: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    project: str = "multi-agent-harness"

    def __post_init__(self):
        _require_nonempty(self.task_id, "task_id", "Task")
        _require_nonempty(self.objective, "objective", "Task")
        _require_valid_role(self.assigned_role)
        if self.risk_metadata not in RISK_CLASSES:
            raise ContractError(f"Task {self.task_id}: invalid risk {self.risk_metadata!r}")
        allowed_auth = {"destructive", "financial_transfer",
                        "sensitive_publication", "credential_change"}
        bad = set(self.authorization_requirements) - allowed_auth
        if bad:
            raise ContractError(f"Task {self.task_id}: unknown auth requirement {bad}")

    def to_dict(self):
        return _jsonable(asdict(self))


# ===========================================================================
# 3. DELEGATION CONTRACT
# ===========================================================================
@dataclass(frozen=True)
class Delegation:
    """The scoped authority record. Validated against
    schemas/delegation.schema.json (draft 2020-12). This object is the ONLY
    thing the authority gate may consume (AUTH-INV-01/07/09/13/14).

    principal: "human" (or a documented human-authorized process).
    delegate:  "orchestrator".
    task:      the task_id this delegation authorizes (or "" for a project-level
               delegation).
    action / target / environment: the concrete action class, target path, and
               environment this delegation authorizes.
    """
    id: str = ""
    principal: str = "human"
    delegate: str = ORCHESTRATOR
    project: str = "multi-agent-harness"
    task: str = ""
    action: str = ""                 # e.g. "code_write"
    target: str = ""                 # resource root e.g. "agents/**"
    environment: str = "dev"
    scope_operations: tuple[str, ...] = ()
    scope_resources: tuple[str, ...] = ()
    scope_environments: tuple[str, ...] = ("dev",)
    maximum_cost: float | None = None
    prohibited_actions: tuple[str, ...] = ()
    requires_approval: tuple[str, ...] = ()
    expires_at: str = ""             # ISO datetime; "" = no expiry
    approval_reference: str = ""
    status: str = "ACTIVE"
    version: int = 1
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    revoked_at: str = ""

    def __post_init__(self):
        _require_nonempty(self.project, "project", "Delegation")
        if self.principal not in ("human", "human_authorized_process"):
            raise ContractError(f"Delegation: invalid principal {self.principal!r}")
        if self.delegate != ORCHESTRATOR:
            raise ContractError(f"Delegation: invalid delegate {self.delegate!r}")
        if self.status not in ("ACTIVE", "REVOKED", "EXPIRED"):
            raise ContractError(f"Delegation: invalid status {self.status!r}")
        if self.version < 1:
            raise ContractError("Delegation: version must be >= 1")
        # requires_approval vocabulary
        allowed = {"destructive", "financial_transfer",
                   "sensitive_publication", "credential_change"}
        bad = set(self.requires_approval) - allowed
        if bad:
            raise ContractError(f"Delegation: unknown requires_approval {bad}")
        # Action/target may be "" only for a project-level umbrella delegation.
        if self.action and not self.target:
            raise ContractError("Delegation: action set but target empty")
        # Auto-assign id if absent.
        if not self.id:
            object.__setattr__(self, "id", f"delegation-{self.task or 'project'}")

    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    def is_expired(self, now=None) -> bool:
        if not self.expires_at:
            return False
        now = now or datetime.now(timezone.utc)
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True  # malformed expiry → treat as expired (fail-closed)
        return now > exp

    def to_dict(self):
        """Emit the schema-shaped delegation document (nested `scope`, `id`)."""
        return _jsonable({
            "id": self.id,
            "principal": self.principal,
            "delegate": self.delegate,
            "project": self.project,
            "task": self.task,
            "action": self.action,
            "target": self.target,
            "environment": self.environment,
            "scope": {
                "operations": list(self.scope_operations),
                "resources": list(self.scope_resources),
                "environments": list(self.scope_environments),
                "maximum_cost": self.maximum_cost,
            },
            "prohibited_actions": list(self.prohibited_actions),
            "requires_approval": list(self.requires_approval),
            "expires_at": self.expires_at or None,
            "approval_reference": self.approval_reference or None,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at or None,
        })


# ===========================================================================
# 4. RESULT COLLECTION CONTRACT
# ===========================================================================
@dataclass(frozen=True)
class TaskResult:
    """Structured result a specialist returns to the orchestrator.

    This is DATA (AUTH-INV-13). Its `status`/`recommendation` fields are
    claims the orchestrator verifies; they never grant authority.
    """
    task_id: str
    assigned_role: str
    status: str = "SUCCEEDED"        # SUCCEEDED / FAILED / BLOCKED
    findings: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()   # refs to evidence artifacts, never secrets
    assumptions: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    recommendation: str = ""
    confidence: str = "MEDIUM"       # LOW / MEDIUM / HIGH
    unresolved_items: tuple[str, ...] = ()
    actions_taken: tuple[str, ...] = ()
    reported_at: str = field(default_factory=_now_iso)

    def __post_init__(self):
        _require_nonempty(self.task_id, "task_id", "TaskResult")
        _require_valid_role(self.assigned_role)
        if self.status not in ("SUCCEEDED", "FAILED", "BLOCKED"):
            raise ContractError(f"TaskResult {self.task_id}: invalid status {self.status!r}")
        if self.confidence not in RISK_CLASSES:
            raise ContractError(f"TaskResult {self.task_id}: invalid confidence {self.confidence!r}")

    def to_dict(self):
        return _jsonable(asdict(self))

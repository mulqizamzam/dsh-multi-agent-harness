# tests/integration/harness.py — Integration test harness
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Wires the existing foundation/reference/helper modules into a single
# cross-module lifecycle driver so the 12 Phase-2 integration scenarios can
# assert end-to-end behavior without a running DSH session.
#
# Modules integrated:
#   orchestrator.foundation.*  (gates, contracts, state machine, workflow)
#   control.execution_gate     (path-aware write channel, ADR 0002)
#   state.helpers              (atomic write, version check, recovery)
#   audit.helpers              (append-only log, integrity)
#   tests.control_plane        (reference authority gate for cross-check)

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root + tests/ are importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TESTS_DIR = os.path.join(_PROJECT_ROOT, "tests")
for _p in (_PROJECT_ROOT, _TESTS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Foundation modules
# ---------------------------------------------------------------------------
from orchestrator.foundation import (
    Delegation, StateMachine, ProjectState,
    ControlPlane, WorkflowRun, PHASE_CHAIN, GateDecision,
    WorkflowError,
)

# Execution gate
from control.execution_gate import (
    authorize_write, write_through, registry_write,
    audit_append, classify_target,
)

# State helpers
from state.helpers import (
    safe_read, compare_and_swap, RecoveryRecord, begin_recovery,
)

# Audit helpers
from audit.helpers.append_log import append_event, read_events

# Reference gate (cross-check)
from control_plane import (
    authorize as ref_authorize,
    classify_risk as ref_classify_risk,
    Deny as RefDeny,
)


# ---------------------------------------------------------------------------
# Integration harness
# ---------------------------------------------------------------------------
@dataclass
class LifecycleOutcome:
    """Structured outcome of a lifecycle run."""
    gate_results: list = field(default_factory=list)  # [(gate_name, decision, reason)]
    stop_gate: str = ""               # where the flow stopped ("" = full flow)
    stop_decision: str = "ALLOW"      # decision at stop point
    final_state: str = "DRAFT"        # final StateMachine state
    final_phase: str = "intake"       # final WorkflowRun phase
    version: int = 1                  # final ProjectState version
    audit_ids: list = field(default_factory=list)
    files_written: list = field(default_factory=list)
    error: str = ""


class IntegrationHarness:
    """Cross-module integration driver.

    Creates a real temporary workspace with state/registry/, audit/,
    state/projects/, and agents/cto/ directories. The workspace is used
    by the execution gate (write_through/registry_write/audit_append) and
    by state/audit helpers for real file I/O.

    Provides:
    - Gate evaluation through ControlPlane (foundation)
    - Cross-checking against the reference gate (tests/control_plane.py)
    - Lifecycle driving (WorkflowRun + StateMachine + execution channel)
    - Registry seeding and reading
    - Audit event management
    """

    def __init__(self, ws: str):
        self._ws = os.path.abspath(ws)
        self._cp = ControlPlane()
        self._project = ProjectState()
        self._ensure_dirs()

    # -- workspace management ------------------------------------------------

    def _ensure_dirs(self):
        for d in ("state/registry", "state/projects", "audit", "agents/cto", "docs"):
            os.makedirs(os.path.join(self._ws, d), exist_ok=True)

    @property
    def ws(self) -> str:
        return self._ws

    @property
    def control_plane(self) -> ControlPlane:
        return self._cp

    # -- delegation / registry helpers --------------------------------------

    def build_delegation(self, **overrides) -> Delegation:
        """Build a valid foundation Delegation with overrides."""
        kw = dict(
            id="delegation-int-001", principal="human", delegate="orchestrator",
            project="multi-agent-harness", task="int-001",
            action="write", target="agents/**",
            environment="dev",
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
            scope_environments=("dev",),
            expires_at="", status="ACTIVE", version=1,
        )
        kw.update(overrides)
        return Delegation(**kw)

    def build_delegation_dict(self, **overrides) -> dict:
        """Build a delegation dict matching the reference gate's shape."""
        d = {
            "id": "delegation-int-001", "principal": "human",
            "delegate": "orchestrator", "project": "multi-agent-harness",
            "scope": {
                "operations": ["write", "read", "code_write"],
                "resources": ["agents/**", "docs/**", "multi-agent-harness/**"],
                "environments": ["dev"],
            },
            "prohibited_actions": [],
            "requires_approval": [],
            "expires_at": None, "approval_reference": None,
            "status": "ACTIVE", "version": 1,
            "created_at": "2026-08-29T00:00:00Z",
            "updated_at": "2026-08-29T00:00:00Z",
            "revoked_at": None,
        }
        d.update(overrides)
        return d

    def seed_registry(self, delegation_dict: dict) -> str:
        """Write a delegation into the registry via the sanctioned channel."""
        path = registry_write(
            "state/registry/delegations.json",
            delegation_dict, base=self._ws)
        return path

    def read_registry(self) -> dict | None:
        """Read the current registry contents."""
        return safe_read(os.path.join(self._ws, "state/registry", "delegations.json"))

    def seed_revocation(self, delegation_id: str) -> str:
        """Append a delegation id to the revocation list."""
        path = registry_write(
            "state/registry/revocations.json",
            {"revoked": [delegation_id]}, base=self._ws)
        return path

    def read_revocation(self) -> dict:
        data = safe_read(os.path.join(self._ws, "state/registry", "revocations.json"))
        return data or {"revoked": []}

    # -- gate evaluation ----------------------------------------------------

    def evaluate_gate(self, name: str, context: dict) -> GateDecision:
        """Evaluate a named gate through the foundation ControlPlane."""
        return self._cp.evaluate(name, context)

    def cross_check_authority(self, actor: str, action: str, target: str,
                              delegation_dict: dict | None,
                              revocation_list: tuple = (),
                              environment: str = "dev",
                              allow_write_paths: tuple = (),
                              foundation_context: dict | None = None,
                              ) -> dict:
        """Evaluate authority through both the foundation gate and the
        reference gate, returning the comparison result.

        The foundation AuthorityGate is evaluated first; if the context
        parameter is provided, it is used directly. Otherwise a minimal
        context is built from the other parameters.
        """
        # Foundation gate
        ctx = foundation_context or {
            "delegation": self._delegation_from_dict(delegation_dict) if delegation_dict else None,
            "action": action, "target": target,
            "approval_reference": (delegation_dict or {}).get("approval_reference"),
        }
        fnd = self.evaluate_gate("authority", ctx)

        # Reference gate
        try:
            ref_authorize(actor, action, target, delegation_dict,
                          revocation_list=revocation_list,
                          environment=environment,
                          allow_write_paths=allow_write_paths)
            ref = "ALLOW"
        except RefDeny as e:
            ref = "DENY"
            ref_reason = str(e)
        else:
            ref_reason = ""

        return {
            "foundation_decision": fnd.decision,
            "foundation_reason": fnd.reason,
            "reference_decision": ref,
            "reference_reason": ref_reason,
            "match": fnd.decision == ref,
        }

    def _delegation_from_dict(self, d: dict | None) -> Delegation | None:
        """Convert a reference-style delegation dict to a foundation Delegation."""
        if d is None:
            return None
        scope = d.get("scope", {})
        return Delegation(
            id=d.get("id", "delegation-x"),
            principal=d.get("principal", "human"),
            delegate=d.get("delegate", "orchestrator"),
            project=d.get("project", "multi-agent-harness"),
            task=d.get("task", ""),
            action=d.get("action", ""),
            target=d.get("target", ""),
            environment=d.get("environment", "dev"),
            scope_operations=tuple(scope.get("operations", [])),
            scope_resources=tuple(scope.get("resources", [])),
            scope_environments=tuple(scope.get("environments", ["dev"])),
            maximum_cost=scope.get("maximum_cost"),
            prohibited_actions=tuple(d.get("prohibited_actions", [])),
            requires_approval=tuple(d.get("requires_approval", [])),
            expires_at=d.get("expires_at") or "",
            approval_reference=d.get("approval_reference") or "",
            status=d.get("status", "ACTIVE"),
            version=d.get("version", 1),
        )

    def cross_check_risk(self, action: str, target: str,
                         environment: str = "dev",
                         requires_approval: tuple = ()) -> dict:
        """Risk classification through both foundation RiskGate and reference
        classify_risk."""
        fnd = self.evaluate_gate("risk", {"action": action, "risk": "LOW"})
        ref_cls, ref_intrinsic = ref_classify_risk(action, target, environment,
                                                    requires_approval)
        return {
            "foundation_risk": fnd.detail.get("risk", "LOW"),
            "reference_risk": ref_cls,
            "reference_intrinsic": ref_intrinsic,
            "match": fnd.detail.get("risk", "LOW") == ref_cls,
        }

    # -- lifecycle driver ---------------------------------------------------

    def run_workflow(self, objective: str = "integration test",
                     phases_to_advance: int = 0) -> WorkflowRun:
        """Create and advance a WorkflowRun by the given number of phases."""
        wf = WorkflowRun(objective=objective)
        for _ in range(phases_to_advance):
            wf.advance()
        return wf

    def advance_workflow(self, wf: WorkflowRun, count: int = 1) -> str:
        """Advance a WorkflowRun and return the new current phase."""
        for _ in range(count):
            wf.advance()
        return wf.current_phase()

    def check_gate(self, wf: WorkflowRun, decision_str: str,
                   gate_name: str = "", detail: dict | None = None):
        """Clear a gate on the WorkflowRun (or raise WorkflowError if non-ALLOW)."""
        wf.check_gate(decision_str, gate=gate_name, detail=detail)

    # -- state machine ------------------------------------------------------

    def machine(self, task_id: str = "int-001") -> StateMachine:
        """Get or create a StateMachine under the project."""
        return self._project.machine(task_id)

    def transition(self, task_id: str, to_state: str, authority=None,
                   actor: str = "orchestrator",
                   expected_project_version: int | None = None) -> str:
        """Transition the project's task machine and bump project version."""
        return self._project.transition(
            task_id, to_state, authority=authority,
            actor=actor,
            expected_project_version=expected_project_version)

    def project_version(self) -> int:
        return self._project.version

    def project_state(self) -> ProjectState:
        return self._project

    # -- execution channel --------------------------------------------------

    def write_through(self, target: str, data: Any,
                      action: str = "write") -> str:
        """Write data through the real execution gate channel."""
        return write_through(action, target, data, base=self._ws)

    def classify_target(self, target: str) -> str:
        return classify_target(target, base=self._ws)

    def authorize_write(self, action: str, target: str,
                        writer: bool = False) -> bool:
        """Check execution gate authorization (raises ExecDenied on deny)."""
        return authorize_write(action, target, base=self._ws, writer=writer)

    # -- audit --------------------------------------------------------------

    def append_audit(self, event: dict) -> bool:
        """Append an audit event through the real audit channel."""
        path = os.path.join(self._ws, "audit", "events.jsonl")
        return append_event(path, event)

    def audit_events(self) -> list:
        """Read all audit events from the workspace audit log."""
        path = os.path.join(self._ws, "audit", "events.jsonl")
        return read_events(path)

    def clear_audit(self):
        path = os.path.join(self._ws, "audit", "events.jsonl")
        if os.path.exists(path):
            os.remove(path)

    # -- recovery -----------------------------------------------------------

    def begin_recovery(self, task_id: str, preserved_version: int,
                       failure_class: str = "unknown",
                       reason: str = "") -> RecoveryRecord:
        return begin_recovery(task_id, preserved_version,
                              failure_class, reason)

    # -- file existence helpers ---------------------------------------------

    def file_exists(self, path: str) -> bool:
        return os.path.exists(os.path.join(self._ws, path))

    def file_sha256(self, path: str) -> str:
        import hashlib
        full = os.path.join(self._ws, path)
        if not os.path.exists(full):
            return ""
        with open(full, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
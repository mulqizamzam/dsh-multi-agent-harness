# orchestrator.foundation.workflow — Orchestrator workflow skeleton (Phase 1D/1E)
#
# NON-PRODUCTION / CONTROLLED. This is a structural skeleton: it defines the
# ordered phase chain and validates phase transitions, but performs NO
# enforcement and executes NO consequential action. Gates inside the chain are
# integration points the orchestrator re-validates (ADR correction #4: a
# script's output is data, never enforcement).
#
# Phases (Phase 1E — hardened to the PRD/contract sequence, 15 phases):
#   intake → understand → classify → risk_gate → decompose → select → delegate
#   → collect → evidence_gate → synthesize → conflict_gate → review_gate →
#   authority_gate → execute_gate → verify_gate
#
# Hardening rules (Phase 1E):
#   - an UNRESOLVED gate STOPS the run: a gate phase must be explicitly cleared
#     with an ALLOW decision from the control plane (check_gate); anything else
#     raises WorkflowError (fail-closed)
#   - EXECUTION requires an execution-time authority re-check
#     (require_execution_authority_recheck, AUTH-INV-05) — a planning-time
#     ALLOW is never sufficient
#   - BadSector review is CONDITIONAL and a PASS never authorizes (AUTH-INV-09)
#   - no gate auto-authorizes: check_gate records data only, and only the
#     orchestrator (via the control plane) may clear a gate

from __future__ import annotations

from dataclasses import dataclass, field

PHASE_CHAIN = (
    "intake",          # normalized objective + required authority context
    "understand",      # clarify scope/constraints
    "classify",        # deterministic risk classification
    "risk_gate",       # RiskGate placeholder (orchestrator re-validates)
    "decompose",       # task decomposition (Task objects)
    "select",          # minimum specialist set (routing)
    "delegate",        # scoped delegation contract (orchestrator-only)
    "collect",         # gather structured results
    "evidence_gate",   # EvidenceGate placeholder (exists→…→sufficient)
    "synthesize",      # consolidate (preserve disagreement)
    "conflict_gate",   # ConflictGate placeholder (no voting; escalate)
    "review_gate",     # BadSector review placeholder (conditional; PASS != authority)
    "authority_gate",  # AuthorityGate placeholder (fail-closed)
    "execute_gate",    # ExecutionGate integration point (+ authority re-check)
    "verify_gate",     # VerificationGate placeholder (COMPLETE needs evidence)
)

# Gate phases: in the skeleton they are placeholders — they MUST NOT
# auto-authorize. An unresolved gate stops the chain (fail-closed).
GATE_PHASES = {
    "risk_gate", "evidence_gate", "conflict_gate", "review_gate",
    "authority_gate", "execute_gate", "verify_gate",
}


class WorkflowError(ValueError):
    pass


@dataclass
class WorkflowRun:
    """A single (non-production) workflow run record. The run performs no
    enforcement; each step records what the orchestrator must re-validate.

    Phase 1E hardening:
      - `check_gate` STOPS the run unless the current gate phase is explicitly
        cleared with an ALLOW decision (fail-closed; no auto-authorization)
      - `require_execution_authority_recheck` enforces the execution-time
        authority re-check (AUTH-INV-05) at the execute_gate
      - `gates_cleared()` exposes which gates the orchestrator cleared
    """
    objective: str = ""
    phase_index: int = 0
    steps: list = field(default_factory=list)
    _gates_cleared: set = field(default_factory=set)

    def current_phase(self) -> str:
        return PHASE_CHAIN[self.phase_index]

    def next_phase(self) -> str:
        if self.phase_index + 1 >= len(PHASE_CHAIN):
            raise WorkflowError("workflow already at final phase")
        return PHASE_CHAIN[self.phase_index + 1]

    def advance(self, note: str = "") -> str:
        """Advance to the next phase. On a GATE phase this only records the
        step — it NEVER authorizes (fail-closed placeholders)."""
        if self.phase_index + 1 >= len(PHASE_CHAIN):
            raise WorkflowError("cannot advance past final phase")
        self.phase_index += 1
        phase = self.current_phase()
        self.steps.append({"phase": phase, "note": note,
                           "is_gate": phase in GATE_PHASES})
        return phase

    def is_at_gate(self) -> bool:
        return self.current_phase() in GATE_PHASES

    def check_gate(self, decision, gate: str = "", detail=None) -> None:
        """Fail-closed gate clearing (Phase 1E).

        The orchestrator supplies a decision produced by the control plane
        (ControlPlane.evaluate). An unresolved, denied, or missing decision
        STOPS the run — a gate placeholder never authorizes on its own and
        never clears itself (ADR correction #4).
        """
        phase = self.current_phase()
        if phase not in GATE_PHASES:
            raise WorkflowError(f"phase {phase!r} is not a gate phase")
        if not isinstance(decision, str) or decision.upper() != "ALLOW":
            raise WorkflowError(
                f"gate {phase} not cleared (decision={decision!r}): "
                "workflow STOPPED (fail-closed)")
        self._gates_cleared.add(phase)
        self.steps.append({
            "phase": phase,
            "gate": gate or phase,
            "decision": "ALLOW",
            "detail": detail or {},
            "note": "gate cleared by orchestrator re-validation (data, not authority)",
        })

    def require_execution_authority_recheck(self, authority_decision) -> None:
        """Execution-time authority re-check (AUTH-INV-05; THREAT-009/024).

        Immediately before the execute_gate, authority must be re-validated
        against CURRENT state. A planning-time ALLOW is never sufficient;
        DENY / ESCALATE / missing → STOP.
        """
        if self.current_phase() != "execute_gate":
            raise WorkflowError(
                f"execution authority re-check only valid at execute_gate "
                f"(currently at {self.current_phase()!r})")
        if not isinstance(authority_decision, str) or authority_decision.upper() != "ALLOW":
            raise WorkflowError(
                f"execution-time authority re-check failed "
                f"({authority_decision!r}): workflow STOPPED (fail-closed)")
        self.steps.append({
            "phase": "execute_gate",
            "gate": "authority_recheck",
            "decision": "ALLOW",
            "note": "execution-time authority re-check passed (AUTH-INV-05)",
        })

    def gates_cleared(self) -> tuple:
        return tuple(sorted(self._gates_cleared))

    def to_dict(self):
        return {
            "objective": self.objective,
            "phase": self.current_phase(),
            "steps": self.steps,
            "gates_cleared": list(self.gates_cleared()),
        }

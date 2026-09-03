# orchestrator.foundation — Phase 1D Orchestrator Foundation package
#
# Scope: multi-agent-harness/ only. Provides the concrete, validated contracts
# and control-plane integration points the Orchestrator consumes:
#   contracts — TaskIntake / Task / Delegation / TaskResult
#   routing   — minimum-set specialist selection (no blanket fan-out)
#   gates     — ControlPlane integration points (authority/risk/evidence/
#               conflict/badsector/execution/verification/recovery)
#   state     — minimal task lifecycle state machine (authority-required)
#   context   — GLOBAL / PROJECT / TASK / AGENT boundaries
#   messaging — V1 agent messaging rules (subdelegation DENY BY DEFAULT)
#   workflow  — non-production 13-phase workflow skeleton
#
# Everything here is DATA + interfaces; nothing grants authority, and no
# control-plane write bypasses the project execution channel.

from .contracts import (
    TaskIntake, Task, Delegation, TaskResult,
    ContractError, SPECIALIST_ROLES, ORCHESTRATOR, ALL_ROLES,
)
from .routing import select_agents, route_tasks, validate_no_fanout, RoutingError
from .gates import ControlPlane, GateDecision, Gate
from .state import StateMachine, ProjectState, StateTransitionError
from .context import Context
from .messaging import Message, MessagingError
from .workflow import WorkflowRun, WorkflowError, PHASE_CHAIN, GATE_PHASES

__all__ = [
    "TaskIntake", "Task", "Delegation", "TaskResult", "ContractError",
    "SPECIALIST_ROLES", "ORCHESTRATOR", "ALL_ROLES",
    "select_agents", "route_tasks", "validate_no_fanout", "RoutingError",
    "ControlPlane", "GateDecision", "Gate",
    "StateMachine", "ProjectState", "StateTransitionError",
    "Context",
    "Message", "MessagingError",
    "WorkflowRun", "WorkflowError", "PHASE_CHAIN", "GATE_PHASES",
]

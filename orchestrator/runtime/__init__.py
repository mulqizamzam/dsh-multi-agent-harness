# orchestrator.runtime — Production Orchestrator Runtime (Phase 3 / Session A)
#
# The production orchestrator runtime binds the EXISTING control-plane modules
# (orchestrator.foundation.*, control.*, orchestrator.dsh, orchestrator.execution)
# into an executable Execution Flow:
#
#   INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE
#   → EXECUTE_SUBTASKS → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE
#   → ADVERSARIAL_REVIEW → AUTHORITY_GATE → EXECUTE → VERIFY
#   → CLOSE / RECOVER / ESCALATE
#
# The runtime REUSES (does not reimplement):
#   - control.* modules for risk, evidence, conflict, BadSector, authority,
#     verification, recovery, and execution-gate decisions
#   - orchestrator.foundation.* for contracts, routing, state machine
#   - orchestrator.dsh for delegation / subtask execution
#   - orchestrator.execution for the EXECUTE+VERIFY+RECOVERY assurance engine
#   - state.helpers / audit.helpers for persistence and append-only audit
#
# No DSH core, profile, preset, session policy, role toolFilter, or inline
# DSH configuration is modified by this module.

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from .exceptions import (
    RuntimeFlowError, FlowStopped, GateDenied, GateEscalated,
    StaleStateDetected, AuthorityDenied, RecoveryRefusedByRuntime,
    SubtaskFailed, ParallelUnsafe,
)
from .audit import RuntimeAudit
from .store import RuntimeStore
from .delegation import (
    DelegationProvider, FileDelegationProvider, MemoryDelegationProvider,
    DelegationLifecycle,
)
from .gates import GateRunner
from .lifecycle import TaskLifecycle
from .parallel import (
    SubtaskPlan, ParallelSafety, ParallelExecutor,
    assert_parallel_safe, build_plans, plan_waves, DEFAULT_MAX_WORKERS,
)
from .collection import (
    CollectedResult, collect_one, collect_all, classify_adapter_failure,
)
from .result import (
    FlowResult, GateRecord, StepRecord,
    COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING,
)
from .flow import ExecutionFlow, ExecutionFailure, ExecutePlan, RUNTIME_PHASE_CHAIN

__all__ = [
    # exceptions
    "RuntimeFlowError", "FlowStopped", "GateDenied", "GateEscalated",
    "StaleStateDetected", "AuthorityDenied", "RecoveryRefusedByRuntime",
    "SubtaskFailed", "ParallelUnsafe",
    # audit
    "RuntimeAudit",
    # store
    "RuntimeStore",
    # delegation
    "DelegationProvider", "FileDelegationProvider", "MemoryDelegationProvider",
    "DelegationLifecycle",
    # gates
    "GateRunner",
    # lifecycle
    "TaskLifecycle",
    # parallel
    "SubtaskPlan", "ParallelSafety", "ParallelExecutor",
    "assert_parallel_safe", "build_plans", "plan_waves", "DEFAULT_MAX_WORKERS",
    # collection
    "CollectedResult", "collect_one", "collect_all", "classify_adapter_failure",
    # result
    "FlowResult", "GateRecord", "StepRecord",
    "COMPLETE", "BLOCKED", "FAILED", "ESCALATED", "RECOVERING",
    # flow
    "ExecutionFlow", "ExecutionFailure", "ExecutePlan", "RUNTIME_PHASE_CHAIN",
]
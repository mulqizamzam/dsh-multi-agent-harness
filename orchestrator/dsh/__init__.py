# orchestrator.dsh — Live DSH integration adapter
#
# Phase 3 / Session B. Scope: multi-agent-harness/ only.
#
# The minimal adapter between the production Orchestrator runtime and the
# already-approved DSH subagent/workflow primitives (D4/D7 role composition).
# Resolves role → subagent instance, passes only authorized task context,
# preserves delegation scope, collects structured TaskResult, propagates
# failure/abort/timeout, preserves role identity + runtime provenance, and
# enforces the V1 delegation invariants (no specialist-to-specialist
# delegation, no authority through messages).
#
# The adapter is a Python client that models the DSH tool-subagent contract.
# Its backend abstraction allows the same client code to drive a real DSH
# session bridge (production) or a deterministic fake (tests).

from .exceptions import (
    ChildFailure,
    DSHError,
    DelegationAborted,
    DelegationDenied,
    DelegationTimeout,
    MalformedResult,
    ProhibitedDelegation,
    RoleResolutionError,
)
from .resolver import RoleResolver, SubagentInstance
from .backend import (
    DelegationBackend,
    DelegationResult,
    DelegationRun,
    FakeSubagentBackend,
    STOP_COMPLETED,
    STOP_ABORTED,
    STOP_ERROR,
    STOP_MAX_TOKENS,
    STOP_REFUSAL,
)
from .context import build_task_context, assert_no_authority_in_payload
from .client import DelegationClient, DelegationOutcome
from .provenance import DelegationProvenance
from .result import TaskResultCollector
from .bridge import (
    RealDSHBackend,
    BridgeNotAvailable,
    DSHBridgeResponse,
    DSHBridgeDispatch,
    DSHInvocation,
    BackendKind,
    probe_backend_kind,
    check_instance_mounted,
    BRIDGE_MARKER_ENV,
)

__all__ = [
    # Exceptions
    "ChildFailure", "DSHError", "DelegationAborted", "DelegationDenied",
    "DelegationTimeout", "MalformedResult", "ProhibitedDelegation",
    "RoleResolutionError",
    # Resolver
    "RoleResolver", "SubagentInstance",
    # Backend
    "DelegationBackend", "DelegationResult", "DelegationRun",
    "FakeSubagentBackend",
    "STOP_COMPLETED", "STOP_ABORTED", "STOP_ERROR", "STOP_MAX_TOKENS",
    "STOP_REFUSAL",
    # Context
    "build_task_context", "assert_no_authority_in_payload",
    # Client
    "DelegationClient", "DelegationOutcome",
    # Provenance
    "DelegationProvenance",
    # Result
    "TaskResultCollector",
    # Real bridge (production namespace — G1)
    "RealDSHBackend", "BridgeNotAvailable", "DSHBridgeResponse",
    "DSHBridgeDispatch", "DSHInvocation", "BackendKind",
    "probe_backend_kind", "check_instance_mounted", "BRIDGE_MARKER_ENV",
]
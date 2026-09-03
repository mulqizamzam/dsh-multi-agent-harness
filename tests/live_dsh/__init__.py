# tests/live_dsh/__init__.py — REAL DSH bridge preparation harness (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# This package prepares a test harness that can replace the deterministic
# FakeSubagentBackend with the ACTUAL mounted DSH `subagent_<id>` tool
# instances AFTER a Human-approved D4/D7 composition is active.
#
# Hard rules (Session E):
#   - NOTHING is mounted here.
#   - No DSH core / profile / preset / session-policy change.
#   - No live scenario is executed.
#   - The harness explicitly distinguishes FAKE BACKEND vs REAL DSH BACKEND and
#     never assumes a live bridge exists.

from .backend_kind import (
    BackendKind,
    probe_backend_kind,
    is_real_bridge_available,
    require_real_bridge,
)
from .contract import (
    DSH_VERSION_PIN,
    STOP_REASONS,
    STOP_COMPLETED,
    STOP_ABORTED,
    STOP_ERROR,
    STOP_MAX_TOKENS,
    STOP_REFUSAL,
    TOOL_PARAMETER_KEYS,
    FOREGROUND_KIND,
    BACKGROUND_KIND,
    CONTINUABLE_KIND,
    STRUCTURED_OUTPUT_TOOL,
    BuildInvocation,
    DSHInvocation,
    map_stop_reason_to_outcome,
    map_stop_reason_to_failure,
)
from .discovery import (
    resolve_role_instance,
    resolve_all_role_instances,
    assert_role_resolution,
    check_instance_mounted,
    DISCOVERY_MARKER_ENV,
)
from .real_backend import (
    RealDSHBackend,
    BridgeNotAvailable,
    DSHBridgeDispatch,
)
from .adapters import (
    ROLE_ADAPTERS,
    RoleAdapter,
    build_role_adapter,
)
from .evidence import (
    BridgeEvidence,
    capture_dispatch_evidence,
    capture_provenance_evidence,
    write_evidence_bundle,
)

__all__ = [
    # backend kind
    "BackendKind", "probe_backend_kind", "is_real_bridge_available",
    "require_real_bridge",
    # contract
    "DSH_VERSION_PIN", "STOP_REASONS", "STOP_COMPLETED", "STOP_ABORTED",
    "STOP_ERROR", "STOP_MAX_TOKENS", "STOP_REFUSAL", "TOOL_PARAMETER_KEYS",
    "FOREGROUND_KIND", "BACKGROUND_KIND", "CONTINUABLE_KIND",
    "STRUCTURED_OUTPUT_TOOL", "BuildInvocation", "DSHInvocation",
    "map_stop_reason_to_outcome", "map_stop_reason_to_failure",
    # discovery
    "resolve_role_instance", "resolve_all_role_instances",
    "assert_role_resolution", "check_instance_mounted",
    "DISCOVERY_MARKER_ENV",
    # real backend
    "RealDSHBackend", "BridgeNotAvailable", "DSHBridgeDispatch",
    # adapters
    "ROLE_ADAPTERS", "RoleAdapter", "build_role_adapter",
    # evidence
    "BridgeEvidence", "capture_dispatch_evidence",
    "capture_provenance_evidence", "write_evidence_bundle",
]

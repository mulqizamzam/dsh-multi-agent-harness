# tests/phase5_role_validation — Session E (G12) role runtime validation
#
# TEST-SUPPORT ONLY. NOT production code.
#
# See harness.py for the validation logic. The tests in this package prove:
#   - deterministic checks pass for all six target roles (resolution,
#     tool-surface consistency, prohibited tools, subdelegation denial)
#   - live checks honestly report BLOCKED when the D4/D7 mount is absent
#     (never a fake live result)
#   - the harness reports deterministic failures as failures

from .harness import (
    BRIDGE_MARKER_ENV,
    DELEGATION_TOOLS,
    MUTATION_TOOLS,
    READ_ONLY_ROLES,
    TARGET_ROLES,
    bridge_active,
    check_live_provenance,
    check_prohibited_tools,
    check_role_resolution,
    check_subdelegation_denial,
    check_toolfilter_consistency,
    run_role_validation,
)

__all__ = [
    "BRIDGE_MARKER_ENV", "DELEGATION_TOOLS", "MUTATION_TOOLS",
    "READ_ONLY_ROLES", "TARGET_ROLES", "bridge_active",
    "check_live_provenance", "check_prohibited_tools",
    "check_role_resolution", "check_subdelegation_denial",
    "check_toolfilter_consistency", "run_role_validation",
]

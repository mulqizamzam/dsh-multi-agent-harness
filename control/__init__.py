# control — project execution / control layer (multi-agent-harness)
#
# This package holds the project control-plane primitives that are NOT
# natively expressible in DSH. Currently:
#   execution_gate.py — minimal runtime path-aware execution gate (ADR 0002
#                       registry protection; protected/outside/malformed → DENY,
#                       authorized workspace write → ALLOW).

from .execution_gate import (
    Denied,
    PROTECTED_REL_ROOTS,
    WRITE_ACTIONS,
    workspace_base,
    normalize_target,
    classify_target,
    authorize_write,
    write_through,
    registry_write,
    audit_append,
    project_write,
    project_read,
    registry_read,
    audit_read,
    audit_verify,
)

__all__ = [
    "Denied",
    "PROTECTED_REL_ROOTS",
    "WRITE_ACTIONS",
    "workspace_base",
    "normalize_target",
    "classify_target",
    "authorize_write",
    "write_through",
    "registry_write",
    "audit_append",
    "project_write",
    "project_read",
    "registry_read",
    "audit_read",
    "audit_verify",
]

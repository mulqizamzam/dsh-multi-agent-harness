# Audit helpers package — Phase 1B (+ hardened Phase 1E / Session B)

from .append_log import (
    append_event, read_events, read_events_strict, read_events_by_class,
    verify_append_only, audit_is_authority_source, AuditIntegrityError,
)
from .integrity import (
    compute_chain, persist_chain, verify_chain, detect_truncation,
    append_chained_event, chain_path_for,
)

__all__ = [
    "append_event", "read_events", "read_events_strict", "read_events_by_class",
    "verify_append_only", "audit_is_authority_source", "AuditIntegrityError",
    "compute_chain", "persist_chain", "verify_chain", "detect_truncation",
    "append_chained_event", "chain_path_for",
]
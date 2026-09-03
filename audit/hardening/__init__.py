"""Audit / integrity hardening (Phase 5 / Session D).

Chain verification, truncation/duplicate/replay/ordering detection, provenance
correlation, audit-as-authority rejection, and recovery/audit correlation —
all built ON TOP of the existing audit helpers (audit/helpers/*). This package
never creates a second audit ledger; it only adds verification/rejection
extensions over the existing append-only ledger.
"""
# tests/evidence — Runtime evidence QA (Phase 3 / Session E)
#
# TEST-SUPPORT ONLY. Not production code.
#
# This package validates the STRUCTURE of runtime-evidence bundles for the
# live-runtime scenarios INT-01 / INT-07 / INT-11 / INT-12. It does not run
# live tests, does not verify controls, and does not claim L3. See
# docs/testing/0002-runtime-evidence-qa-specification.md and
# docs/security/0004-runtime-evidence-qa-security-note.md.

from .evidence_qa import (
    VALID_SCENARIOS,
    SPECIALIST_ROLES,
    EVIDENCE_SOURCES,
    FAILURE_CLASSES,
    GATE_NAMES,
    STOP_REASONS,
    L3_PROPERTIES,
    ValidationReport,
    validate_evidence_bundle,
    validate_bundle_file,
    file_sha256,
)

__all__ = [
    "VALID_SCENARIOS", "SPECIALIST_ROLES", "EVIDENCE_SOURCES",
    "FAILURE_CLASSES", "GATE_NAMES", "STOP_REASONS", "L3_PROPERTIES",
    "ValidationReport", "validate_evidence_bundle", "validate_bundle_file",
    "file_sha256",
]

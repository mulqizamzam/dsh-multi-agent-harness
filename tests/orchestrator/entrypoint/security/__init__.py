# tests/orchestrator/entrypoint/security — Independent adversarial test package
# for the DSH Chat → ProductionRun front door (Session Front Door V1).
#
# Phase 5 / Front Door Security Test Preparation. TEST/DESIGN ONLY.
#
# Scope (write-only):
#   - multi-agent-harness/tests/orchestrator/entrypoint/security/
#   - multi-agent-harness/docs/phase-5/entrypoint/security/
#
# This package is intentionally INDEPENDENT and ADVERSARIAL: it does not assume
# the front door exists. When orchestrator.entrypoint is not importable every
# test reports NOT_YET_AVAILABLE (never a fabricated PASS/DENY). When it is
# present, each test classifies the observed outcome (PASS / DENY / ESCALATE /
# ERROR / UNKNOWN) with evidence against the eight security acceptance
# criteria.

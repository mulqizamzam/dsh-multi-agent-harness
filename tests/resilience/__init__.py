# tests/resilience — Phase 5 / Session D resilience suite (G4 + G9)
#
# TEST-SUPPORT ONLY. Exercises the EXISTING runtime with no architecture or
# DSH change:
#
#   G4 — provider 429 / rate-limit resilience (classification as
#        environment-class, no blind retry, no retry amplification,
#        deterministic routing to recovery/escalation).
#   G9 — registry protection (path-aware execution gate denies non-sanctioned
#        writes to state/registry/ + audit/ before mutation; sanctioned
#        registry_write/audit_append channels still work; ISO-LIVE-006 live
#        variant named BLOCKED).
#
# See README.md in this directory and docs/phase-5/resilience/ for the full
# analysis and spec.

# tests/l3_reference/critical — Critical-control L3 reference/oracle catalogue
#
# Phase 5 / Session C — L3 Critical Control Readiness.
#
# This directory holds the critical-control L3 scenario fixtures and references
# for the six critical controls that must be independently verifiable before
# any L3 claim can be made. The O1 oracles themselves live in the parent
# tests/l3_reference (authority_gate, execution_gate, recovery_gate,
# transition_gate, audit_chain, etc.) — this package provides the scenario
# definitions and fixture bundles that prove those oracles agree with the
# recorded runtime verdicts.
#
# CRITICAL CONTROLS (6):
#   1. authority grant/revoke/expiry  → L3-AUTH-001/003/004
#   2. execution-time recheck         → L3-AUTH-006
#   3. protected-path execution       → L3-PATH-001
#   4. recovery privilege bounding    → L3-REC-004
#   5. stale-state protection         → L3-ST-003
#   6. audit integrity                → L3-AUD-002
#
# See tests/l3_runner/critical/ for the critical-runner + readiness tests.
# See docs/phase-5/l3/0003-critical-control-readiness.md for the readiness report.
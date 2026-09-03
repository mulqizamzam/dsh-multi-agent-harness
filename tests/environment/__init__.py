# tests/environment — Session B (G2+G3) runtime-environment readiness preflight
#
# TEST-SUPPORT ONLY. NOT production code.
#
# A read-only preflight that verifies the operational environment prerequisites
# for a Phase-5 runtime session (modeled on tests/l3_runner/preflight.py):
#   - session policy baseline (workspace-write + ask, PB-1)
#   - approval-answerer availability (G3)
#   - D4/D7 mount availability (G2)
#   - DSH version pin
#
# RULES (same as the L3 preflight):
#   - REPORT ONLY: never modifies session policy, never mounts, never changes DSH.
#   - Honest: a check that cannot pass is reported as failed with its required
#     value — never faked, never "assumed ready".
#   - Readiness is claimed only when the relevant checks pass AND runtime
#     evidence exists.

# tests/l3_runner/critical — Critical-control L3 runner + readiness tests
#
# Phase 5 / Session C — L3 Critical Control Readiness.
#
# Drives the six critical controls through the existing L3 rehearsal/replay
# machinery (tests/l3_runner/rehearsal.py) with the critical fixture bundles
# under tests/l3_reference/critical/fixtures/. For each critical scenario the
# runner:
#   - runs the full end-to-end rehearsal (runner -> verifier subprocess ->
#     collector -> validator -> replay);
#   - asserts the P1..P4 properties (runtime verdict present, independent
#     observer, >= 2 oracle classes, reproducible replay);
#   - reports the honest L3-claim status (never claims L3 — rehearsal bundles
#     force l3_claim=false and fail LV10 by design).
#
# SAFETY: rehearsal mode only. No live DSH session, no destructive/high-impact
# execution, no repo audit/l3/ writes (bundles land under a scratch base).
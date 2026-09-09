# tests/g13/live_readiness — G13 live DSH verification readiness package
#
# Phase 5 / FINAL SECURITY / Session B — G13 LIVE DSH VERIFICATION READINESS.
#
# Prepares the EXACT non-destructive live G13 test (payload fixtures, affected
# roles, runtime entry point, expected DATA treatment, authority impact, state
# mutation expectation, execution expectation, BadSector expectation, evidence
# requirements, rollback/cleanup) under tests/g13/live_readiness/.
#
# HONESTY BOUNDARY
#   The precondition for the live step is a REAL DSH child being observable
#   (D4/D7 composition mounted: DSH_LIVE_BRIDGE_ACTIVE=1 + all 15 subagent_<id>
#   instances mounted). In this session the marker is unset and every instance
#   reports NOT_MOUNTED (probe_backend_kind() == unavailable), so the live step
#   is BLOCKED. This package PREPARES the test; it does not execute it, does
#   not claim DSH-native immunity, and never enables web_fetch or performs
#   destructive execution.
#
#   See docs/phase-5/security/g13/final/0001-g13-live-readiness-session-b.md.

from .plan import precondition, live_test_plan

__all__ = ["precondition", "live_test_plan"]

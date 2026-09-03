# Integration tests — Phase 2 / Session D
#
# These tests exercise the cross-module control plane by wiring together:
#   - orchestrator.foundation (gates, contracts, state machine, routing, workflow)
#   - control.execution_gate (path-aware write channel, ADR 0002)
#   - state.helpers (atomic write, version check, recovery)
#   - audit.helpers (append-only log, integrity chain)
#   - tests.control_plane (reference authority gate for cross-check)
#
# TEST-SUPPORT ONLY. Specification: docs/testing/0001-integration-test-plan.md.
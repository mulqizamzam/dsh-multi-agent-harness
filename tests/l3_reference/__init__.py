# tests/l3_reference — L3 independent reference re-implementations (Phase 4 / Session B)
#
# INDEPENDENT REFERENCE/ORACLE IMPLEMENTATIONS (O1). NOT production gates.
# These are SELF-CONTAINED re-implementations of the control-plane semantics
# with NO shared imports from production control modules
# (control/authority.py, control/execution_gate.py, etc.).
#
# Independence property (P3): each file here is a separate, independently
# authored implementation of the SAME specification. The L3 verifier loads
# these reference oracles, NOT the production gates. This prevents the
# "gate approves itself by referring to its own table" tautology.
#
# This package also holds:
#   schemas/    JSON Schemas (draft 2020-12) for each L3 evidence file
#   fixtures/   Inert plan.json / env.json templates per INT scenario
#
# CONSTANTS (shared across reference implementations, but NOT production):
#   - No imports from control.*, orchestrator.*, state.*, audit.* modules
#   - All delegation/authority/execution logic is re-implemented here

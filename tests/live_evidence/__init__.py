# tests/live_evidence — LIVE DSH parallel execution evidence (Phase 3 / Session D3)
#
# TEST-SUPPORT ONLY. Not production code.
#
# INT-11 — live parallel subagent collection
# INT-12 — live failure propagation
#
# This package is the evidence harness for the LIVE DSH run. It reuses the
# existing production runtime (orchestrator.runtime, orchestrator.dsh) for
# safety verification, structured collection, provenance, and failure
# classification. The live dispatch itself is performed by the orchestrator
# session through the approved D4/D7 per-role `subagent_<id>` tool instances.

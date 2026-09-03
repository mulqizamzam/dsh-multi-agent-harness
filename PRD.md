# Product Requirements Document — Multi-Agent Harness

The canonical PRD is at:

**`/home/administrator/agent-workspace/baca/PRD_Multi_Agent_DeepSeek_Harness_v1.0.md`**

This file is a pointer — the PRD is the authoritative source for the system's requirements, scope, and design intent.

---

## Key references

- PRD §4: Orchestrator — coordination/delegation, not an eighth specialist.
- PRD §5: Seven specialist peers; no specialist manages another.
- PRD §6: Capability / Permission / Authority separation.
- PRD §8: Per-agent capability matrix (mapped to DSH realities in ADR 0001).
- PRD §12: Security — prompt injection, confidentiality, audit.
- PRD §17: Phase-6 scenarios (test harness skeletons).
- PRD §18: Project structure (extended and adapted in `docs/phase-1/0001-phase-1-implementation-spec.md`).
- PRD §19: Constraints — Human authority, least privilege, delegation, audit, no auto-escalation, recovery.

**Important**: The PRD is Harness-agnostic. Appendix C warns: *"Do not infer an API, permission mechanism, or workflow syntax from this PRD alone."* The actual DSH 0.1.1-rc.2 mapping is documented in the ADR, the Phase-1 spec, and the Phase-0 documentation artifacts in `docs/`.

---

*DeepSeek Harness version `0.1.1-rc.2`. See `docs/adr/0001-multi-agent-control-plane-boundary.md` for the DSH→PRD mapping.*
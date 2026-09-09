# Product Requirements Document — Multi-Agent Harness

The canonical PRD is at:

**`/home/administrator/agent-workspace/baca/PRD_Multi_Agent_DeepSeek_Harness_v1.0.md`**

This file is a pointer — the PRD is the authoritative source for the system's requirements, scope, and design intent.

> **PRD v0.2** (2026-09-09): the on-demand specialist pool expansion — see
> `PRD-v0.2.md` (this repo), `docs/adr/0003-specialist-pool-expansion.md`,
> and the implementation plan at `docs/superpowers/plans/2026-09-09-specialist-pool-expansion.md`.
> The specialist pool is now **15 specialists** (7 baseline + 8 expansion, registered-not-mounted).

---

## Key references

- PRD §4: Orchestrator — coordination/delegation, not an eighth specialist.
- PRD §5: Seven specialist peers (baseline; pool expanded to 15 in PRD v0.2); no specialist manages another.
- PRD §6: Capability / Permission / Authority separation.
- PRD §8: Per-agent capability matrix (mapped to DSH realities in ADR 0001).
- PRD §12: Security — prompt injection, confidentiality, audit.
- PRD §17: Phase-6 scenarios (test harness skeletons).
- PRD §18: Project structure (extended and adapted in `docs/phase-1/0001-phase-1-implementation-spec.md`).
- PRD §19: Constraints — Human authority, least privilege, delegation, audit, no auto-escalation, recovery.

**Important**: The PRD is Harness-agnostic. Appendix C warns: *"Do not infer an API, permission mechanism, or workflow syntax from this PRD alone."* The actual DSH 0.1.1-rc.2 mapping is documented in the ADR, the Phase-1 spec, and the Phase-0 documentation artifacts in `docs/`.

---

*DeepSeek Harness version `0.1.1-rc.2`. See `docs/adr/0001-multi-agent-control-plane-boundary.md` for the DSH→PRD mapping.*
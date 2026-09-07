# Decision Approval Record — ADR 0001 Decisions D1–D7 (Human Ratification)

- **Record id**: `docs/governance/0001-decision-approval-record.md`
- **Date**: 2026-09-07
- **Subject**: per-decision approval status of the seven decisions in
  `docs/adr/0001-multi-agent-control-plane-boundary.md` (Multi-Agent
  Control Plane Boundary, Revision 3).
- **Authority**: the Human principal, via direct instructions in the session
  that owns this project (same channel class the ADR's approval vocabulary
  already recognizes: *"Confirmed by the Human in this session / an explicit
  instruction"*).
- **Status**: **RECORDED** — this file is the in-repo verifiable approval
  record referenced by the ADR Revision 3 addendum.

---

## 1. Approval channel (verbatim instructions, dated)

| # | Date | Instruction (verbatim) | What it authorized |
|---|---|---|---|
| 1 | 2026-09-07 | *"mount D4/D7 bridge approved"* | The controlled DSH composition exception (D4 implementation + D7 per-case exception); mount executed same day, verified in `runs/mount-verification-2026-09-07/` |
| 2 | 2026-09-07 | *"setuju"* | Commit of the mount-verification evidence |
| 3 | 2026-09-07 | *"laksanakan 1 - 4"* | The four-item follow-up plan: scope-staleness patch (#1, landed as `3235601`/`cbbdc62` by the parallel actor), ADR/records reconciliation (#2), zeko tool-surface discriminator (#3), skip-implementation (#4, landed as `f9fca47`) |
| 4 | 2026-09-07 | Human quoted the D1–D7 list — *"Daftar D1–D7 (permission model / approval baseline / arsitektur orchestrator / role isolation / state+audit / docs / scope+exception)"* — and replied *"setuju"*, then *"(a) setuju"* | **Ratification of decisions D1–D7 as accepted**, creating this record |

## 2. Per-decision ratification table

| Decision | Summary (recommended option, as implemented) | Status | Implementation evidence |
|---|---|---|---|
| **D1** — Permission model | Two-tier: per-role toolFilter/preset (D4) + per-session sandbox/approval baseline; PRD §8 per-agent sandbox is intent-only | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4) | `config/role-preset-mapping.yaml`; `config/permissions.yaml` agent_defaults (intent); validator `tests/validate_config.py` |
| **D2** — Dev approval/safety policy | `workspace-write` + `ask` baseline; high-impact actions via the project authority gate to Human | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4; baseline observed live in the current session context) | Runtime context (workspace-write + ask); approval E2E pair first observed 2026-09-07 (session log; `tests/environment/approval_composition.py`) |
| **D3** — Orchestrator architecture | Hybrid: root-session orchestrator + deterministic fan-out; authority/risk/evidence/conflict gates stay in the orchestrator, never in a script or a child | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4) | `orchestrator/` contract + runtime flow; gates in `control/` |
| **D4** — Role isolation | Seven Agent Presets + seven per-role `tool-subagent` instances with toolFilter; subdelegation DENY BY DEFAULT | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4; mounted under instruction #1) | `runs/mount-verification-2026-09-07/` (INT-01..INT-12, REAL-backend dispatches); live rows ≡ config (locked by `test_live_rows_match_config`) |
| **D5** — State & audit persistence | File-based project state + audit under the project tree; single-writer orchestrator; DSH session log is session-level only | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4) | `state/`, `audit/`, `schemas/project-state.schema.json`, `schemas/audit-event.schema.json` |
| **D6** — Phase-0 documentation | Scoped, version-pinned docs (`tool-catalog.md`, `operations.md`, `architecture.md`, `authority.md`, `runbooks/`) | **HUMAN_APPROVED** (ratified 2026-09-07, instruction #4) | `docs/tool-catalog.md`, `docs/operations.md`, `docs/architecture.md`, `docs/authority.md`, `docs/runbooks/` |
| **D7** — Phase-1 scope boundary + controlled exception | Boundary `multi-agent-harness/`; DSH profile/preset changes only as separately-approved, reversible per-case exceptions | Boundary **HUMAN_APPROVED** 2026-08-29 (explicit instruction, recorded in the ADR body); exception **HUMAN_APPROVED** 2026-09-07 (instruction #1), executed reversibly with backup + rollback path (CR `docs/phase-1/0003` §8; backup `runs/mount-verification-2026-09-07/backups/`) | ADR 0001 Decision 7; CR 0003 Amendment 1 |

## 3. Scope of this ratification

1. This record ratifies the **decision content** of D1–D7 as accepted. It
   does **not** reopen, alter, or extend any decision.
2. It does **not** approve work beyond what is already implemented and
   recorded; future changes keep requiring their own authority (per-case
   exceptions included).
3. Residual security items are **unchanged** by this record: G10 bash
   residual (zeko/cto) stays documented-OPEN; **G13 / prompt-injection stays
   OPEN/UNKNOWN** — no injection claim exists anywhere in this project, and
   none is created by this record.
4. Provenance limitation, stated honestly: the approval channel is chat
   instruction. This file quotes the instructions verbatim and is the
   principal's ratification **in that same channel**; it is the strongest
   in-repo form available and supersedes the ADR addendum's
   best-effort transcription. A stronger out-of-repo record, if one exists,
   would supersede this file.

## 4. Effect on other records

- `docs/adr/0001-multi-agent-control-plane-boundary.md` — the Revision 3
  addendum's "Residual gap" paragraph (undated/in-repo-unverifiable approval
  record) is **resolved by this file**; the ADR carries a pointer.
- Entry criterion #1 of the ADR ("ADR accepted by Human; decisions marked
  HUMAN_APPROVED or explicitly deferred") — **SATISFIED with a record**:
  all seven decisions HUMAN_APPROVED, none deferred, per §2 above.

---

*Status: RECORDED 2026-09-07. Ratification by the Human principal (instruction #4). No decision reopened, no scope widened, no security claim created. G13 remains OPEN/UNKNOWN.*

# Phase 4 / Session C — Promoted Executable Bounded Scenarios (Index)

- **Milestone**: Phase 4 / Session C — LIVE SCENARIO EXPANSION
- **Status**: EXECUTABLE (deterministic Phase-4 runtime) — see per-scenario status rows
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Runtime used**: existing Phase-4 runtime (`orchestrator/runtime/ExecutionFlow`, `orchestrator/execution/ExecutionEngine`, `orchestrator/dsh/DelegationClient`, `control/*`, `state/helpers`, `audit/helpers`) — **not modified**
- **Scope (write-only)**: `multi-agent-harness/docs/phase-4/scenarios/` (this index + the ten scenario specifications) and `multi-agent-harness/tests/scenarios/` (the executable promotion of the Phase-6 skeleton).
- **Honesty rule**: every scenario in this directory is an **executable, bounded scenario** that runs against the **deterministic Phase-4 runtime**. No live-DSH evidence is fabricated: where a scenario's acceptance needs a mounted live `subagent_<id>` surface (the D4/D7 composition, still `PENDING_HUMAN_APPROVAL` per `docs/phase-4/0001-acceptance-matrix.md` §12), that variant is named **BLOCKED** and is *not* claimed. **No L3 claim. No prompt-injection security claim.**

---

## What this promotes

The Phase-6 scenario skeleton (`tests/scenarios/test_scenarios.py`, PRD §17's ten scenarios, all `pytest.mark.skip`) is **promoted into executable bounded scenarios** where the Phase-4 runtime already supports the underlying behavior. The Phase-6 skeletons remain the canonical PRD §17 list and stay skipped (they need the future Phase-6 live execution engine for their literal, full-fidelity flow, e.g. real DSH children). The ten **bounded** scenario classes below are executable today against the deterministic runtime and each maps back to a runbook (`docs/runbooks/01–10`) and, where they overlap, to the PRD §17 skeleton.

## The ten promoted scenarios

| Scenario | Id | Runbook | PRD §17 skeleton | Disposition (deterministic runtime) | Test file |
|---|---|---|---|---|---|
| Authority denial | `SCN-101` | 01 | #10 (unauthorized destructive request) | BLOCKED / ESCALATED (fail-closed, no mutation) | `tests/scenarios/test_executable_scenarios.py::TestAuthorityDenial` |
| Expired / revoked delegation | `SCN-102` | 02, 03 | #10 | BLOCKED (`execution_denial`), no mutation | `...::TestDelegationExpiryRevocation` |
| BadSector rework / reject | `SCN-103` | 04 | #7 (high-impact action) | BLOCKED at `adversarial_review`; PASS ≠ authority | `...::TestBadsectorReworkReject` |
| Evidence failure | `SCN-104` | 05 | #1/#2 (research/code change) | BLOCKED (HIGH no evidence) / ESCALATED (MEDIUM no evidence); ladder rungs DENY | `...::TestEvidenceFailure` |
| Conflict escalation | `SCN-105` | 06 | #8 (conflicting outputs) | ESCALATED (material/HIGH); synthesized (immaterial) — no voting | `...::TestConflictEscalation` |
| Execution failure | `SCN-106` | 07 | #9 (failed deployment) | RECOVERING → recovery → COMPLETE; no blind retry | `...::TestExecutionFailure` |
| Recovery failure | `SCN-107` | 08 | #9 | FAILED + refused further recovery (no in-band recovery) | `...::TestRecoveryFailure` |
| Stale state | `SCN-108` | 09 | #9 | BLOCKED (`version_conflict`), no mutation | `...::TestStaleState` |
| Audit integrity failure | `SCN-109` | 10 | #10 | `AuditIntegrityError` (chain break / truncation / blank / corrupt); protected-path write DENY | `...::TestAuditIntegrityFailure` |
| Successful bounded autonomous workflow | `SCN-110` | — (happy path) | #1/#2 | COMPLETE, all gates ALLOW, verification PASSED, audit lifecycle recorded | `...::TestSuccessfulBoundedWorkflow` |

## Per-scenario specification fields

Every scenario file below documents the nine required fields:

1. **Preconditions** — delegation / registry / risk / review state that must hold before the scenario runs.
2. **Objective** — the concrete objective being exercised.
3. **Actors** — orchestrator, specialists, Human (where the scenario halts for Human sign-off).
4. **Expected state** — task state-machine trajectory and terminal `FlowResult.outcome` / `final_state` / `version`.
5. **Expected gates** — which runtime gates fire, and the expected ALLOW / DENY / ESCALATE decisions.
6. **Expected execution** — the consequential action (or its absence); the mutation boundary.
7. **Expected verification** — the verification gate outcome and why COMPLETE is (or is not) reached.
8. **Expected failure / recovery** — the failure classification, recovery path (or escalation), no-blind-retry bounds.
9. **Evidence requirements** — the deterministic evidence produced: `FlowResult.to_dict()`, audit event classes, gate records, on-disk hashes / no-mutation proof, and (where the scenario cannot run live) the named BLOCKED live variant.

## Honesty / boundary section (applies to all ten)

- **Deterministic runtime evidence only.** Each scenario's assertions run against the real Phase-4 runtime (not a mock of the runtime) with deterministic in-process child execution (`FakeSubagentBackend` / stub runners). Live `subagent_<id>` dispatch evidence exists separately for INT-01/07/11/12 (`docs/phase-3/`); the promoted scenarios do **not** re-claim it and do **not** fabricate it.
- **Live-DSH variants are BLOCKED** where they would need the D4/D7 mount (RDE-1) or the L3 verifier (VER-2/L3-1) — see `docs/phase-4/0001-acceptance-matrix.md` rows RDE-1, RDE-2, L3-1, L3-2.
- **No L3 claim.** No bundle in this directory satisfies P1–P4; every scenario is L2-LIVE-or-lower at most, and in this session is demonstrated at the deterministic-runtime level.
- **No prompt-injection security claim.** External/subagent content is treated as data; the scenarios exercise that trust posture where relevant but make no security claim about it.
- **No production change.** Nothing under `orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/`, `tests/` (outside `scenarios/`), `docs/` (outside `phase-4/scenarios/`) is modified. Role `toolFilter`s, DSH core/profile/preset/session policy are untouched. No new tool is enabled.

---

*Status: Phase 4 / Session C — ten executable bounded scenario specifications + index. Deterministic-runtime evidence only; live variants named BLOCKED; no L3 claim.*

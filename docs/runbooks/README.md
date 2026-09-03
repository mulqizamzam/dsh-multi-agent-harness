# Runbooks — Index

- **Status**: Phase 2 / Session F authored (10 runbooks); pre-existing Phase-5 placeholders preserved below for forward compatibility
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Purpose**: operational runbooks that document the response to the ten documented failure classes against the **current architecture** (Phase 1B/1E control plane, DSH `0.1.1-rc.2` primitives). See `docs/phase-2/README.md` for the Phase 2 governance and the binding DETECT → STOP → PRESERVE → DIAGNOSE → RECOVER/ESCALATE → VERIFY → REPORT convention.

## Authored runbooks (Phase 2 / Session F)

| # | Runbook | Topic | Anchor |
|---|---|---|---|
| 01 | `01-authority-denial.md` | Authority gate denial (any cause) | AUTH-INV-05, AUTH-INV-20 |
| 02 | `02-expired-delegation.md` | `delegation expired (AUTH-INV-06)`; THREAT-008/024 | AUTH-INV-05/06, THREAT-008 |
| 03 | `03-revoked-delegation.md` | `delegation revoked (AUTH-INV-06)`; THREAT-009; forged-revocation handoff to 10 | AUTH-INV-06, THREAT-009/018/024 |
| 04 | `04-badsector-rework-reject.md` | BadSector REWORK / REJECT verdicts; PASS ≠ authority (AUTH-INV-09); forged-verdict handoff to 10 | AUTH-INV-04/09/10, THREAT-014/015/023 |
| 05 | `05-evidence-failure.md` | EVID-001..004; SOURCE EXISTS → SUFFICIENT ladder failures; HIGH-risk sufficiency | AUTH-INV-09/10, THREAT-011/013 |
| 06 | `06-conflict-escalation.md` | Material conflicts; §8.1 four mandatory-escalation conditions; no majority voting | AUTH-INV-09/10, THREAT-005/011/013/020 |
| 07 | `07-execution-failure.md` | Post-gate failures; `RecoveryRecord` lifecycle; REC-001..003 | AUTH-INV-12/16, THREAT-016/017/022/024/025 |
| 08 | `08-recovery-failure.md` | `RecoveryRecord.state == FAILED`; no in-band recovery; escalate | AUTH-INV-12/14/16, THREAT-017/022 |
| 09 | `09-stale-state.md` | `compare_and_swap` mismatch / `StaleStateError` / `RecoveryDenied`; THREAT-021/022 | AUTH-INV-05/14, THREAT-021/022 |
| 10 | `10-audit-integrity-failure.md` | Chain break / truncation / blank line / forged event; **critical security incident**; AUTH-INV-14 (audit ≠ authority) | AUTH-INV-14, THREAT-014/018 |

Each runbook follows the same DETECT → STOP → PRESERVE → DIAGNOSE → RECOVER/ESCALATE → VERIFY → REPORT skeleton and references the **existing** helpers and primitives (no new behavior introduced). See `docs/phase-2/README.md` §"What this phase does not produce" for the explicit non-goals.

## Forward-compatibility (Phase 5 placeholders, retained)

The entries below remain as **intent-only placeholders** for Phase 5 hardening. They are not operational guidance today; the Phase 2 / Session F runbooks above supersede the operationally-relevant topics until Phase 5 authors each entry against the then-implemented control plane.

| # | Placeholder runbook | Topic |
|---|---|---|
| 1 | `sandbox-verification.md` | Verify effective session sandbox mode before consequential work; respond to drift |
| 2 | `approval-resolution.md` | Resolve DSH approval `ask` outcomes (allowed-once / rejected / cancelled / unavailable); headless behavior |
| 3 | `delegation-lifecycle.md` | Create / revoke / expire a delegation; scope containment checks |
| 4 | `bad-sector-review.md` | Trigger BadSector review; interpret PASS/REWORK/REJECT; verify PASS provenance |
| 5 | `recovery.md` | STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY → REPLAN → AUTHORITY RE-CHECK |
| 6 | `audit-inspection.md` | Inspect the project audit ledger; distinguish runtime events from agent-reported claims |
| 7 | `controlled-composition-change.md` | Mount/revert a project Agent Preset or per-role tool instance (the controlled DSH composition exception) |
| 8 | `state-rollback.md` | Roll back project state/audit files to a previous version (atomic, versioned) |

## Status

- **Phase 2 (Session F)**: ten operational runbooks authored against the current architecture. No code, schema, config, role file, preset, profile, or session policy change.
- **Phase 5**: author the eight placeholder runbooks above against the implemented control plane and the verified DSH `0.1.1-rc.2` primitives.

---

*Phase 2 / Session F runbooks: align with the architecture already in place; introduce no new behavior.*
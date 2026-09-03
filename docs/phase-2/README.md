# Phase 2 — Operations and Failure Runbooks (Index)

- **Status**: Phase 2 / Session F (runbooks written; no implementation, no execution, no L3 claim)
- **Date**: 2026-08-30
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/` — index of operational runbooks under `docs/runbooks/`. No code, no schema, no config, no role file, no preset, no profile, no DSH-core, no session policy change.

## Purpose

Phase 2 captures the **operations and failure runbooks** that operationalise the recovery and gate posture already encoded in `tests/control_plane.py`, `state/helpers/`, `audit/helpers/`, `control/execution_gate.py`, and the security/test docs (`docs/security/0001`, `docs/security/0002`, `docs/design/0001`). The runbooks **do not introduce new behavior**; they describe what an operator (the Human, the orchestrator's outer state machine, or an L3 verifier) does when one of the documented failure signals is observed.

## What this phase produces

| Artifact | Location | Purpose |
|---|---|---|
| Runbook 01 — Authority Denial | `docs/runbooks/01-authority-denial.md` | Response to `Deny(...)` at the authority gate; covers all fail-closed reasons. |
| Runbook 02 — Expired Delegation | `docs/runbooks/02-expired-delegation.md` | Specialisation of 01 for `delegation expired (AUTH-INV-06)`. |
| Runbook 03 — Revoked Delegation | `docs/runbooks/03-revoked-delegation.md` | Specialisation of 01 for `delegation revoked (AUTH-INV-06)` + forged-revocation handoff to 10. |
| Runbook 04 — BadSector REWORK / REJECT | `docs/runbooks/04-badsector-rework-reject.md` | Response to REWORK / REJECT verdicts; PASS is **not** authority and is not handled here. |
| Runbook 05 — Evidence Failure | `docs/runbooks/05-evidence-failure.md` | Response to EVID-001..004 (existence, relevance, currency, contradiction, sufficiency). |
| Runbook 06 — Conflict Escalation | `docs/runbooks/06-conflict-escalation.md` | Response to material conflicts (security spec §8.1's four mandatory-escalation conditions). |
| Runbook 07 — Execution Failure | `docs/runbooks/07-execution-failure.md` | Response to post-gate failures (tool error, `stopReason != completed`, partial writes, verification mismatch); drives `state/helpers/recovery.py::RecoveryRecord`. |
| Runbook 08 — Recovery Failure | `docs/runbooks/08-recovery-failure.md` | Response to a `RecoveryRecord` reaching `FAILED`; no in-band recovery, escalate. |
| Runbook 09 — Stale State | `docs/runbooks/09-stale-state.md` | Response to `compare_and_swap` mismatch / `StaleStateError` / `RecoveryDenied` (THREAT-021/022). |
| Runbook 10 — Audit Integrity Failure | `docs/runbooks/10-audit-integrity-failure.md` | Response to chain break, truncation, blank line, forged event; **critical security incident**. |

## What this phase does **not** produce

- No new code (control plane, helpers, scripts).
- No new schemas.
- No new config.
- No new agent role files.
- No new presets, profiles, or `$DSH_HOME` content.
- No DSH-core, session-policy, or sandbox change.
- No production agent prompts or production workflows.
- No L3 verification, no L3 claim.

## Runbook structure (binding convention)

Every runbook follows the same skeleton. The convention is intentional: an operator triaging in the moment should be able to find each section by name across all ten.

```text
DETECT  → STOP  → PRESERVE  → DIAGNOSE  → RECOVER / ESCALATE  → VERIFY  → REPORT
```

| Section | What it answers |
|---|---|
| **DETECT** | What signals trigger this runbook? Source signals + read order. |
| **STOP** | What halts immediately? What must NOT happen (auto-retry, auto-extend, auto-revoke, etc.). |
| **PRESERVE** | What evidence is captured before any recovery action? What on-disk state is snapshotted (sha256, version, registry snapshot)? What is recorded but **not** mutated? |
| **DIAGNOSE** | How is the failure classified? Mapping table from signal → root cause → `failure_class` (`environment` / `logic` / `authorization` / `unknown`). |
| **RECOVER / ESCALATE** | What is the documented recovery path? When is escalation mandatory? What does escalation look like (audit event schema)? |
| **VERIFY** | What independent verification is required? What would fail the verification? |
| **REPORT** | What audit events are written? Schema sketches. Append order. |

## Cross-references (the runbooks rely on the following existing primitives)

| Primitive | Location | Used by |
|---|---|---|
| `authorize(...)`, `target_in_scope`, `classify_risk`, `verify_badsector_provenance`, `badsector_pass_is_authority` | `tests/control_plane.py` | 01, 02, 03, 04, 05, 06, 07 |
| `RecoveryRecord`, `begin_recovery`, `RECOVERY_STATES`, `_RECOVERY_TRANSITIONS`, `DEFAULT_MAX_ATTEMPTS`, `DEFAULT_MAX_REWORK_CYCLES` | `state/helpers/recovery.py` | 07, 08 |
| `compare_and_swap`, `atomic_write`, `safe_read` | `state/helpers/atomic_write.py` | 09, 10 |
| `read_version`, `is_stale`, `assert_current_version`, `validate_version_monotonic` | `state/helpers/version_check.py` | 09 |
| `append_event`, `read_events_strict`, `read_events_by_class`, `verify_append_only`, `audit_is_authority_source` | `audit/helpers/append_log.py` | All |
| `verify_chain`, `compute_chain`, `detect_truncation`, `append_chained_event`, `chain_path_for` | `audit/helpers/integrity.py` | 10 |
| `authorize_write`, `SANCTIONED_ROOTS`, `PROTECTED_REL_ROOTS`, `classify_target` | `control/execution_gate.py` | 01, 03 (protected-path handoff), 09 |

## Threat-model / invariant anchors

Each runbook names the AUTH-INV-*, THREAT-*, REC-*, EVID-*, CONF-*, BAD-*, AUD-*, VERIFY-*, XG-*, ISO-*, RISK-* identifiers that govern its response. No runbook introduces a new control; each is a *documentation* of an existing control's response posture.

## Out-of-scope behaviour (the runbooks do not implement)

- **No automated recovery loop.** Each recovery is single-pass; further attempts are new `RecoveryRecord`s.
- **No silent re-authorisation.** Recovery re-passes the same authority path; it does not acquire privilege (AUTH-INV-12).
- **No silent overwrite.** Stale reads are re-read + re-validated, never overwritten (AUTH-INV-05).
- **No blind retry.** A retry requires a new diagnosed cause (AUTH-INV-16, REC-001).
- **No audit-as-authority.** An audit entry never grants authority (AUTH-INV-14; `audit_is_authority_source` always False).
- **No model override.** Model confidence is never a substitute for evidence on HIGH-risk actions (security spec §7.2).
- **No prompt-only enforcement.** Every security-critical control in the runbooks has a named code-enforcement location (the helpers above).
- **No L3 claim.** No runbook claims the control it documents is L3. L3 evidence (independent runtime verification with an external oracle) is a separate deliverable (`docs/security/0003-l3-independent-verification-plan.md`, `docs/design/0002-l3-verification-specification.md`).

## Status table

| Runbook | Authored | Tested | L3-verified |
|---|---|---|---|
| 01 — Authority Denial | ✅ (Session F) | Reference logic tested in `tests/authorization/test_authority.py` | No |
| 02 — Expired Delegation | ✅ (Session F) | Reference logic tested in `tests/authorization/test_authority.py::test_auth_003` | No |
| 03 — Revoked Delegation | ✅ (Session F) | Reference logic tested in `tests/authorization/test_authority.py::test_auth_004` | No |
| 04 — BadSector REWORK / REJECT | ✅ (Session F) | Reference logic tested in `tests/adversarial/test_injection.py::TestBadSectorProvenance` | No |
| 05 — Evidence Failure | ✅ (Session F) | `quarantine()` tested in `tests/adversarial/test_injection.py` (L1, no real external oracle) | No |
| 06 — Conflict Escalation | ✅ (Session F) | No executable skeleton today (control-plane semantics in §8 of security spec) | No |
| 07 — Execution Failure | ✅ (Session F) | Recovery state machine tested in `tests/unit/test_recovery.py` | No |
| 08 — Recovery Failure | ✅ (Session F) | Same as 07 | No |
| 09 — Stale State | ✅ (Session F) | Version-check primitives tested in `tests/unit/test_state_hardening.py` | No |
| 10 — Audit Integrity Failure | ✅ (Session F) | Audit integrity helpers tested in `tests/unit/test_audit_hardening.py`, `test_state_audit.py` | No |

## Stop condition

This phase is complete when:

1. All ten runbooks are authored under `docs/runbooks/`.
2. Each runbook follows the DETECT → STOP → PRESERVE → DIAGNOSE → RECOVER/ESCALATE → VERIFY → REPORT convention.
3. Each runbook names the existing primitives it relies on (no new behavior is introduced).
4. This index is in place.

All three are satisfied. **STOP.**

---

*Status: Phase 2 / Session F runbooks + index. No code, schemas, configs, role files, presets, profiles, or session policy have been touched. No production agent prompts or production workflows have been authored. No L3 claim has been made.*
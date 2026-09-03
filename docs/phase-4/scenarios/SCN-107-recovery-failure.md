# SCN-107 — Recovery Failure (bounded)

- **Id**: `SCN-107`
- **Runbook**: `docs/runbooks/08-recovery-failure.md`
- **PRD §17 skeleton**: #9 — Failed deployment → recovery (failure path)
- **Anchors**: REC-001..003 · AUTH-INV-12/16/20 · THREAT-017/022
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestRecoveryFailure`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- All gates pass; an execution failure occurs (verification mismatch or executor error).
- Sub-cases:
  - `SCN-107a` attempt cap reached: `max_attempts=1`, first recovery fails (executor still failing), **second recovery with a new cause is refused** → FAILED + `RecoveryRefusedByRuntime`.
  - `SCN-107b` authority re-check fails: delegation revoked between first execution and recovery attempt → recovery refused (`RecoveryRefusedByRuntime` with AUTH-INV-12 reason).
  - `SCN-107c` empty cause refused: recovery with `cause=""` → `RecoveryRefusedByRuntime` (no blind retry, AUTH-INV-16).
  - `SCN-107d` identical cause refused: same cause as the already-diagnosed one → `RecoveryRefusedByRuntime` (AUTH-INV-16).

## Objective

Prove that a **recovery that itself fails** reaches the terminal `FAILED` state and **no in-band retry** is possible (Runbook 08): the recovery state machine is single-pass; `FAILED` is a terminal state; escalation is the only forward path.

## Actors

- **orchestrator** — drives the recovery lifecycle.
- **cto** — routed specialist (result supplied).
- **Human** — required for escalation from `FAILED`; no auto-recovery loop.

## Expected state

- `SCN-107a` → `FAILED` (first recovery fails, second refused).
- `SCN-107b` → `RecoveryRefusedByRuntime` raised (recovery does not proceed).
- `SCN-107c/d` → `RecoveryRefusedByRuntime` raised (no blind retry).
- `final_state` is `FAILED` or the task machine remains in the state before the refused recovery.

## Expected gates

- Pre-execution gates ALLOW (execution failure is the trigger).
- Recovery gate: cause diagnosed + attempts within cap → ALLOW (first time); attempts exhausted or identical-cause → DENY (refused).
- Authority re-check for 107b: DENY (revoked delegation) → recovery refused.

## Expected execution

- **No consequential write** from the refused recovery — the recovery does not re-execute.
- The first failed execution may have left no mutated artifact (or the executor's failed state is preserved).

## Expected verification

- Verification not reached on `FAILED`; COMPLETE is never produced.
- `RecoveryRecord.state == "FAILED"` (or the recovery was never entered because the gate refused).

## Expected failure / recovery

- `failure_class` per Runbook 08: attempt cap / identical-cause → `logic` (orchestrator logic bug); authority re-check failure → `authorization` (Runbook 02/03); invalid transition → `logic`; unclassified → `unknown` (mandatory escalation).
- **No in-band recovery from `FAILED`**: the state machine forbids `FAILED → <any>`; the only forward path is escalation to Human.
- A new recovery with a **new** `RecoveryRecord` and a **new** `preserved_version` (if the Human grants one) is possible but is a *new* record, not a continuation of the failed one.

## Evidence requirements

- `FlowResult.outcome` shows `FAILED` (or `RecoveryRefusedByRuntime` raised).
- Audit contains `recovery_state_transition` events showing the failure path; no `recovery_state_transition` with `state == "COMPLETED"` after a `FAILED`.
- No-blind-retry evidence: empty/identical cause refusal is audited.
- Recovery authority re-check failure (107b) is audited with the revocation reason.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*
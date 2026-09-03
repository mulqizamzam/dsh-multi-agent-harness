# SCN-108 — Stale State (bounded)

- **Id**: `SCN-108`
- **Runbook**: `docs/runbooks/09-stale-state.md`
- **PRD §17 skeleton**: #9 — Failed deployment → recovery (state-drift variant)
- **Anchors**: THREAT-021/022 · AUTH-INV-05/14 · REC-005 · ST-001..003
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestStaleState`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101, with the project state document seeded at version 1.
- All gates pass at planning time; the delegation is valid.
- Sub-cases:
  - `SCN-108a` **parallel writer bump**: a `pre_execute` hook increments the project state version between planning and execution → `StaleStateDetected` at the execution-time version check (THREAT-021/022).
  - `SCN-108b` **CAS mismatch**: `RuntimeStore.persist` with a stale expected_version → `StaleStateDetected` raised (lost update detected).
  - `SCN-108c` **recovery with stale version**: a recovery plan's `preserved_version` is older than the current on-disk version → `RecoveryDenied` from `validate_against_current_version` (THREAT-022).

## Objective

Prove that a **stale state version** (a parallel writer advanced the state between the orchestrator's read and write) is detected and stops the flow fail-closed: no mutation, a `version_conflict` audit event, and (for recovery) the recovery is refused until the version is re-read and re-validated.

## Actors

- **orchestrator** — holds the stale version; the CAS guard catches the mismatch.
- **cto** — routed specialist (result supplied).
- **Parallel writer** — simulated by the `pre_execute` hook (a test-operator action, not a production concurrent writer; the test proves the guard's behavior, not the runtime's concurrency model).

## Expected state

- `SCN-108a` → `BLOCKED` (StaleStateDetected → flow stops).
- `SCN-108b` → `StaleStateDetected` raised (CAS persist fails; no mutation).
- `SCN-108c` → `RecoveryDenied` / `RecoveryRefusedByRuntime` (recovery refused).
- `final_state` is never `COMPLETE`; no mutation of the target file.

## Expected gates

- Pre-execution gates ALLOW (the authority/evidence/risk checks are version-independent).
- `execution` phase: version re-check fails → `StaleStateDetected` → `BLOCKED`.
- `recovery` gate: `validate_against_current_version` → DENY (stale version).

## Expected execution

- **No consequential write.** The execution gate's `check_current` refuses before any mutation; the target file is not written.
- In 108c, the recovery does not re-execute; the stale version is detected during the authority re-check phase.

## Expected verification

- Verification not reached; COMPLETE never produced.
- `version_conflict` audit event records the held version vs current version.

## Expected failure / recovery

- `failure_class` per Runbook 09: NEWER version (parallel writer) → `logic` (read was racy; re-read + re-validate + retry with new cause); OLDER version (rolled back) → `authorization` (needs provenance verification); missing/corrupt → `environment`.
- Recovery for 108a: re-read the current state, re-validate authority, retry with a **new cause** (`"parallel_writer_advanced_state"`), not a blind retry.
- Deterministic bounded behavior: the flow halts at the version conflict; the re-read + re-validate path is asserted at the control-module level.

## Evidence requirements

- `FlowResult.outcome` shows `BLOCKED` for 108a.
- Audit contains `version_conflict` event with `expected_version` and `current_version`.
- `StaleStateDetected` exception carries the version mismatch reason.
- No-mutation proof: target file absent; state document version unchanged (or the external writer's version is preserved).
- `RuntimeStore.check_current` / `persist` behavior is demonstrable via the store API.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*
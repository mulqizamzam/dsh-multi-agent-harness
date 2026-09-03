# SCN-106 — Execution Failure (bounded)

- **Id**: `SCN-106`
- **Runbook**: `docs/runbooks/07-execution-failure.md`
- **PRD §17 skeleton**: #9 — Failed deployment → recovery
- **Anchors**: REC-001..003 · AUTH-INV-12/16 · THREAT-016/017/022 · VERIFY-002
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestExecutionFailure`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- All gates (risk/evidence/conflict/authority) **pass** — this is a *post-gate* failure (Runbook 07 scope).
- Sub-cases:
  - `SCN-106a` verification mismatch: executor returns `observed={"exit_code": 1}` while the plan expects `{"exit_code": 0}` → verification not passed → RECOVERING.
  - `SCN-106b` executor raises (tool error / I/O) → typed failure → RECOVERING (or BLOCKED per classification).
  - `SCN-106c` DSH adapter failure (timeout / abort / child failure / malformed result) → `SubtaskFailed` → flow stops fail-closed, routes to recovery/escalation (INT-12 semantics).
  - `SCN-106d` successful recovery: after diagnosis, a fixed executor re-executes and verification passes → COMPLETE.

## Objective

Prove that a post-gate execution/verification failure routes into the **documented recovery lifecycle** (STOP → PRESERVE → DIAGNOSE → RECOVER → VERIFY → REPLAN → AUTHORITY RE-CHECK → COMPLETE), with **no blind retry** (AUTH-INV-16/REC-001) and recovery that re-checks authority (AUTH-INV-12) and never acquires privilege.

## Actors

- **orchestrator** — drives execution, verification, and the recovery lifecycle (`RecoveryController`).
- **cto** — routed specialist whose proposal was authorized.
- No Human needed unless recovery fails (then Runbook 08 / SCN-107).

## Expected state

- `SCN-106a/b` → `RECOVERING` (recovery record present, `state == PRESERVED`).
- `SCN-106c` → `BLOCKED`/`RECOVERING` per classification; never COMPLETE; no partial success.
- `SCN-106d` → `COMPLETE`, recovery record `state == COMPLETED`.

## Expected gates

- All pre-execution gates ALLOW (the failure is post-gate).
- `verification` gate: expected vs observed mismatch → DENY for 106a (routes to recovery); PASSED for 106d (COMPLETE).
- `recovery` gate: cause diagnosed + attempts within cap → ALLOW; empty cause or cap exceeded → DENY (no blind retry).

## Expected execution

- The failed executor attempt records an `execution_attempt` audit event with `result == "error"`.
- In 106d the recovered re-execution writes the target through the execution gate and records the file.

## Expected verification

- COMPLETE only after a PASSED verification (AUTH-INV-15): the observed outcome must match the expected outcome after recovery.
- Evidence kinds for the action category are attached before verification (`_attach_evidence`, VERIFY-003).

## Expected failure / recovery

- `failure_class` per Runbook 07: verification mismatch / plan logic → `logic`; tool/IO → `environment`; refusal → `logic`; max-tokens → `environment`; unknown → escalate (no guessing).
- **No blind retry**: an empty or identical diagnosed cause is refused (`RecoveryRefusedByRuntime`).
- Recovery re-checks authority and state version before re-execution (AUTH-INV-12, THREAT-022); it does not expand scope.

## Evidence requirements

- `FlowResult.recovery` present with `state`, `preserved_version`, `failure_class`, `diagnosed_cause`.
- Audit contains `execution_attempt` (error) and `recovery` / `recovery_state_transition` events.
- No-blind-retry refusal is demonstrated (empty cause raises `RecoveryRefusedByRuntime`).
- Successful recovery (106d) ends at `COMPLETE` with the file present through the execution gate and the recovery record `COMPLETED`.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

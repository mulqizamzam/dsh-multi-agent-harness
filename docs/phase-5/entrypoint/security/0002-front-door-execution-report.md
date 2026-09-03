# Front-Door V1 — Adversarial / Contract Validation Report (EXECUTED)

- **Milestone**: Phase 5 — FRONT DOOR V1 ADVERSARIAL / CONTRACT VALIDATION
- **Status**: VALIDATED — all adversarial + contract checks PASS against the
  implemented `orchestrator.entrypoint`
- **Date**: 2026-09-01 (execution run)
- **Scope (write-only)**: `tests/orchestrator/entrypoint/security/` +
  `docs/phase-5/entrypoint/security/` (this directory). No production module
  was modified.
- **Under test**: `orchestrator/entrypoint/` (Front Door V1) ·
  `orchestrator/production/*` (ProductionRun/BoundedExecutor) ·
  `orchestrator/runtime/flow.py` (ExecutionFlow) ·
  `orchestrator/execution/engine.py` (ExecutionEngine) · `control/*` gates ·
  `orchestrator/dsh/*` (read seam only).
- **Companion**: `0001-front-door-design.md` ·
  `0002-front-door-security-review.md` ·
  `docs/phase-5/entrypoint/security/0001-front-door-security-test-package.md`

---

## 1. MILESTONE

**Phase 5 — Front Door V1 adversarial / contract validation, EXECUTED.**
The pre-built adversarial package (categories A–H + static scan) was run
against the ACTUAL implemented front door, with all `base=ws` isolation fixes
applied and stale pycache cleared. Every security property in the acceptance
list was exercised and verified.

## 2. STATUS

| Item | Status |
|---|---|
| Front door under test | `orchestrator/entrypoint/` — importable, compile-clean |
| New security suite | **112 passed / 0 failed** (categories A–H + static) |
| Existing front-door tests | **158 passed / 0 failed** (test_*.py, excluding security) |
| Combined entrypoint suite | **270 passed / 0 failed** |
| Production regression | `tests/orchestrator/production/` 33 passed |
| Runtime regression | `tests/orchestrator/runtime/` 81 passed |
| Execution regression | `tests/orchestrator/execution/` 39 passed |
| Authorization regression | `tests/authorization/` 178 passed |
| Adversarial regression | `tests/adversarial/` 105 passed |
| Control-risk / verification | `tests/control_risk/` 122 · `tests/control_verification/` 80 passed |
| Phase5-security / phase4-integration | 14 · 56 passed |
| Unit / observability / integration / resilience / recovery / audit | 199 / 42 / 65+4s / 45+1s / 33 / 29 passed |
| Compile / import checks | **NONE** errors (all core modules compile + import) |
| validate-config | **PASS** |

## 3. TEST COUNT

| Suite | Tests | Pass | Fail | Skip |
|---|---|---|---|---|
| New security package (A–H + static) | 112 | 112 | 0 | 0 |
| Existing entrypoint tests (excl. security) | 158 | 158 | 0 | 0 |
| **Front-door total** | **270** | **270** | **0** | 0 |
| Regression (prod/runtime/exec/authz/adversarial/control) | 538 | 538 | 0 | 0 |
| Additional regression (phase/unit/obs/int/resilience/recovery/audit) | 483 | 483 | 0 | 5 skipped (env-gated) |

## 4. ATTACK COVERAGE (per-category, all DENY/ESCALATE/ERROR as designed)

| # | Attack class | Proof | Observed |
|---|---|---|---|
| A | Objective/constraints are DATA, never authority/approval/delegation/review/state | A1–A5 | PASS (0 effect on authority record) |
| B | Missing / unknown / expired / revoked / malformed / prose delegation | B1–B9 | DENY (BLOCKED) / ERROR — never COMPLETE |
| C | Empty / malformed / traversal / absolute / sibling-prefix / protected scope | C1–C7 | ERROR (shape) / DENY (BLOCKED, AUTH-INV-11) |
| D | declared-LOW-for-HIGH / downgrade / unknown action / destructive keywords | D1–D5 | ERROR (no field) / DENY (cannot route) / data |
| E | Control-chain integrity (behavioral spies + static AST) | E1–E8 | PASS — full chain reached, no shortcut |
| F | No DENY/ESCALATE/verification-failure/exception → COMPLETE | F1–F5 | PASS — terminal mapping honest |
| G | run_id / report / audit_ids / JSON integrity | G1–G6 | PASS — no fabricated identity/report |
| H | Oversized / unicode / control / repeat / duplicate / unknown fields | H1–H8 | PASS — fail-closed, no crash, no false success |
| S | Static: no DSH / no mint / no registry write / no bypass / no authority param | S1–S7 | PASS — AST-level proofs |

## 5. STATIC CHECKS (AST-based, all PASS)

| # | Check | Result |
|---|---|---|
| S1 | No raw DSH import/call (`orchestrator.dsh`, `DelegationClient`, `subagent_*`, `bash`/`write`/`edit`) | PASS |
| S2 | No `Delegation(...)` constructor / `create_delegation` / `issue_child_delegation` / `delegation_from_dict` / `revoke` call | PASS |
| S3 | No registry/audit writer (`registry_write`, `write_through`, `authorize_write`, `atomic_write`, `audit_append`) | PASS |
| S4 | No direct `ExecutionFlow` / `ExecutionEngine` call (AST name + call scan) | PASS |
| S5 | No authority-source creation (`DelegationLifecycle`, `assert_actor_may_delegate`, `recheck_authority`) | PASS |
| S6 | Only sanctioned imports (foundation/runtime/production/control.delegation/stdlib) | PASS |
| S7 | No new stop semantics — terminal vocabulary exactly COMPLETE/BLOCKED/ESCALATED/ERROR | PASS |

## 6. CONTROL-CHAIN PROOF (Category E, behavioral)

Monkeypatched spies confirmed the executed call path for a COMPLETE run:

```
FrontDoorRequest → run_front_door
  → resolve_delegation (read-only provider)
  → ProductionRun.run
    → BoundedExecutor.execute
      → ExecutionFlow.run
        → GateRunner.risk_gate → … → evidence_gate → conflict_gate
          → badsector_review → authority_gate
        → ExecutionEngine.validate → recheck_authority → execute
        → verification_result (verdict PASSED) → CLOSE
```

Proved absent (no direct path, no shortcut, no bypass):
- no direct `ExecutionFlow` construction/call from `entry.py`
- no direct `ExecutionEngine` call from `entry.py`
- no raw DSH tool call
- no direct registry write
- no direct authority creation
- no direct approval creation
- no gate bypass parameter (`skip_gates`/`bypass`/`force`/`no_verify`/…)

## 7. TERMINAL-STATE PROOF (Category F/G)

| Status | Guarantee | Proof |
|---|---|---|
| COMPLETE | emitted ONLY when `ProductionRun` returns `outcome=="complete"` AND a generated report; verification `PASSED` | E-03 / F-05 / G-02 |
| BLOCKED | remains BLOCKED (never upgraded by the adapter) | F-01 (denied/out-of-scope → BLOCKED) |
| ESCALATED | remains ESCALATED (approval-required → ESCALATED, never COMPLETE) | F-02 |
| ERROR | remains ERROR (shape failure / unexpected exception → ERROR) | F-04 |
| verification failure | can never become COMPLETE (exit_code mismatch → BLOCKED/ESCALATED) | F-03 |
| exception | never converted to false success (provider crash / executor raise → ERROR/BLOCKED) | F-04 |

## 8. REGRESSION

All regression suites executed separately (conftest isolation) pass cleanly:
production, runtime, execution, authorization, adversarial, control-risk,
control-verification, phase5-security, phase4-integration, unit, observability,
integration, resilience, recovery-hardening, audit-hardening. No existing test
was modified or weakened. No production module was modified.

## 9. VERIFIED / INFERRED / UNKNOWN / BLOCKED

| Label | Items |
|---|---|
| **VERIFIED** (executed, deterministic) | All 112 adversarial/contract checks PASS; 270 front-door tests PASS; 1021+ regression tests PASS; compile/import clean; validate-config PASS. Acceptance criteria 1–8 all proven by tests. |
| **INFERRED** (from code audit, not executed live) | DSH-layer behaviour under the front door; full L2-LIVE evidence for Category E (requires live bridge). |
| **UNKNOWN** | Live-DSH bridge dispatch under the front door (D4/D7 mount + `DSH_LIVE_BRIDGE_ACTIVE` unset); DSH-layer path isolation (G10 remains OPEN/BLOCKING); prompt-injection at DSH layer (G13 remains UNKNOWN). |
| **BLOCKED** | L3 remains BLOCKED; live-DSH proof of the front door (requires D4/D7 mount + marker); approval-answerer-dependent HIGH execution. No test failure blocks the package — all adversarial/contract checks PASS at the project layer (L1). |

## 10. SCOPE CHECK

**In scope (written/executed this session):**
- `tests/orchestrator/entrypoint/security/` — 112-test adversarial package
  (A–H + static), `base=ws` isolation applied, stale pycache cleared.
- `docs/phase-5/entrypoint/security/` — README, preparation report, this
  execution report.

**Not modified (verified):**
- `orchestrator/entrypoint/`, `orchestrator/production/*`, `orchestrator/runtime/*`,
  `orchestrator/execution/*`, `orchestrator/dsh/*`, `orchestrator/foundation/*`
- `control/*`, `state/*`, `audit/*`, `config/*`, `agents/*`, `schemas/*`
- DSH core, profiles/presets, session policy, role/toolFilter
- All existing `tests/` (no test weakened or deleted)
- No new authority mechanism, no gate change, no risk override, no L3 claim

## 11. NEXT

1. Re-run the full entrypoint + security suite after any future front-door change.
2. Live-DSH phase: re-run Category E with the D4/D7 bridge marker set for
   L2-LIVE evidence of the control chain.
3. Feed per-test classifications into the Phase-5 acceptance matrix as
   hardening evidence.
4. Track G10 (OPEN/BLOCKING) and G13 (UNKNOWN) separately — out of scope for
   this front-door L1 validation.

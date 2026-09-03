# Integration Test Plan — Phase 2 / Session D

- **Status**: proposal (test specification + skeletons; no production implementation)
- **Date**: 2026-08-30
- **Milestone**: Phase 2 / Session D — Integration Test Design
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/integration/` + `multi-agent-harness/docs/testing/` only. **No production code, no control/state/audit/orchestrator/agents/config files are modified.**
- **Companion to**: PRD (self) · ADR 0001 · ADR 0002 · `docs/security/0001` · `docs/security/0002` · `docs/design/0001` · `docs/design/0002` · `docs/phase-1/0001` · `docs/authority.md` · `orchestrator/contract.md` · `orchestrator/foundation/` · `control/execution_gate.py` · `state/helpers/` · `audit/helpers/` · `tests/control_plane.py` · `tests/unit/` · `tests/authorization/` · `tests/orchestrator/` · `docs/runbooks/01`–`06` (Phase 2 / Session F)

---

## 1. Objective

Define the **integration-test specification** for the multi-agent control plane and produce **test skeletons** under `tests/integration/` covering the 12 cross-module scenarios required by Phase 2. These tests exercise the **wiring** of the existing foundation modules:

- `orchestrator.foundation` (gates `ControlPlane`, contracts, state machine, routing, workflow)
- `control.execution_gate` (path-aware write channel, ADR 0002)
- `state.helpers` (atomic write, version check, recovery)
- `audit.helpers` (append-only log, integrity)
- `tests.control_plane` (reference authority gate for cross-checking)

**Not in scope**: live DSH session tests, production subagent execution, real Human approval — these belong to Phase 2C/3+/6.

**Not duplicated**: each module's internal behaviour is already tested in `tests/unit/`, `tests/authorization/`, and `tests/orchestrator/`. This specification targets **cross-module contract** — the integration points where two or more modules interact.

---

## 2. ID convention

| Prefix | Domain | Source |
|--------|--------|--------|
| **INT-01** → **INT-12** | Phase-2 integration scenarios | This document |

Each scenario links to the existing security invariants (AUTH-INV-*), threats (THREAT-*), and test IDs (AUTH-*, ISO-*, REC-*, etc.) it builds on.

---

## 3. Integration driver (`tests/integration/harness.py`)

A **test-support only** harness wires the existing modules into a single-process lifecycle driver:

```text
orchestrator.foundation             orchestration.gates  (ControlPlane)
    │  evaluate(gate, context)          │
    ▼                                  ▼
orchestrator.foundation.workflow    WorkflowRun (15-phase chain)
    │  advance/check_gate               │
    ▼                                  ▼
orchestrator.foundation.state       StateMachine / ProjectState
    │  transition(…)                    │
    ▼                                  ▼
control.execution_gate              write_through / registry_write / audit_append
    │  (path-aware, ADR 0002)          │
    ▼                                  ▼
state.helpers / audit.helpers       atomic_write / append_event
    │                                  │
    ▼                                  ▼
tests.control_plane (reference)     cross-check: authorize() == AuthorityGate
```

The harness uses a **temporary real workspace** (state/registry/, audit/, state/projects/, agents/cto/) so gate decisions produce real file-system side-effects that can be verified.

---

## 4. Scenario catalogue

### INT-01 — Authority → Delegation → Risk → Review → Execution (happy path)

| Field | Value |
|-------|-------|
| **Objective** | Prove the full lifecycle: intake → plan → risk → review → authority → execution → verification → COMPLETE, with all gates passing and the write channel delivering the file. |
| **Modules integrated** | Contracts (TaskIntake, Task, Delegation, TaskResult) + Routing (select_agents) + ControlPlane (all 7 gates) + WorkflowRun + StateMachine + execution_gate + audit helpers |
| **Setup** | Seed a valid `ACTIVE` delegation for `code_write` on `multi-agent-harness/**`. Task is LOW risk, non-destructive, no approval required. |
| **Action** | Drive the 15-phase chain. All gates evaluate to ALLOW. Execute a write to `agents/cto/output.txt` via `write_through`. Verify with `TaskResult` containing evidence. |
| **Expected** | File written. StateMachine: DRAFT → PLANNED → DELEGATED → EXECUTING → COLLECTED → SYNTHESIZING → COMPLETE. Audit contains: start, gate_cleared × 7, execution, complete. Gate decisions match reference `authorize()`. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-05, INV-09, INV-15, AUTH-INV-20 |

### INT-02 — Expired / revoked authority

| Field | Value |
|-------|-------|
| **Objective** | Prove that an expired or revoked delegation is DENIED at execution time, even if planning passed. |
| **Modules integrated** | AuthorityGate (+ reference) + StateMachine + execution_gate + audit |
| **Setup** | Seed a delegation with `expires_at` in the past (expired) / a delegation in the revocation list (revoked). Planning-time authority check passes (mock). |
| **Action** | Attempt execution. The execution-time re-check in AuthorityGate (or `require_execution_authority_recheck` in WorkflowRun) must DENY. |
| **Expected** | DENY. StateMachine: PLANNED → BLOCKED (not EXECUTING). No file written. Audit: `execution_denial` with reason matching expiry/revocation. Reference `authorize()` also DENY. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-06, INV-13, THREAT-008/009/024 |

### INT-03 — BadSector PASS without authority

| Field | Value |
|-------|-------|
| **Objective** | Prove that a BadSector PASS (with provenance) clears the review stage ONLY, and the authority gate still DENYs without a delegation. |
| **Modules integrated** | BadSectorReviewGate + AuthorityGate + reference + StateMachine + audit |
| **Setup** | Provide a review record with `verdict: PASS`, `review_id: "r-1"`, `input_hash: "abc"`. **No delegation exists.** |
| **Action** | Drive gates: review_gate → ALLOW (clears review). authority_gate → DENY (no delegation). |
| **Expected** | Review gate ALLOW with provenance. Authority gate DENY. StateMachine: REVIEW_PENDING → BLOCKED (not EXECUTING). Audit: `badsector_pass_cleared` + `execution_denial`. Reference `badsector_pass_is_authority` returns False. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-09, INV-03, THREAT-014 |

### INT-04 — Risk HIGH non-downgrade

| Field | Value |
|-------|-------|
| **Objective** | Prove that an intrinsically HIGH action (destructive, production, financial, credential) cannot be downgraded to LOW/MEDIUM by model judgment. |
| **Modules integrated** | RiskGate + AuthorityGate + reference `classify_risk` + StateMachine + audit |
| **Setup** | Action `destructive` declared `risk: "LOW"` by model. Requires approval `destructive`. No delegation with matching approval_reference. |
| **Action** | RiskGate evaluates: intrinsic HIGH, non-downgradable → ALLOW with `risk: HIGH`. AuthorityGate: requires_approval matches, no approval_reference → ESCALATE. |
| **Expected** | RiskGate ALLOW with `detail["risk"] == "HIGH"`. AuthorityGate ESCALATE or DENY. StateMachine: ESCALATED. Reference `classify_risk("destructive", ...)` returns `("HIGH", True)`. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-10, THREAT-011/012, RISK-001..005 |

### INT-05 — Evidence failure

| Field | Value |
|-------|-------|
| **Objective** | Prove that the evidence gate DENYs a HIGH-risk action with no evidence, and ESCALATEs a MEDIUM action with no evidence. |
| **Modules integrated** | EvidenceGate + StateMachine + audit |
| **Setup** | Action is HIGH risk, no evidence provided. |
| **Action** | Evaluate evidence gate. |
| **Expected** | EvidenceGate DENY (HIGH + no evidence). StateMachine: BLOCKED. Audit: `evidence_denied`. For MEDIUM + no evidence: ESCALATE. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | EVID-001..004 |

### INT-06 — Conflict escalation

| Field | Value |
|-------|-------|
| **Objective** | Prove that the conflict gate ESCALATEs when unresolved material conflicts exist, and never silently resolves. |
| **Modules integrated** | ConflictGate + StateMachine (ESCALATED) + WorkflowRun (check_gate STOP) + audit |
| **Setup** | Two TaskResults with contradictory recommendations (e.g., "deploy" vs "rollback"). |
| **Action** | ConflictGate evaluates. Workflow check_gate receives non-ALLOW. |
| **Expected** | ConflictGate ESCALATE. WorkflowRun.check_gate raises WorkflowError (STOP). StateMachine: ESCALATED. Audit: `conflict_detected`. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | CONF-001..003, THREAT-021 |

### INT-07 — Execution-time authority re-check

| Field | Value |
|-------|-------|
| **Objective** | Prove that authority is re-validated at execution time, not just planning — a delegation revoked between planning and execution causes the gate to DENY. |
| **Modules integrated** | WorkflowRun.require_execution_authority_recheck + AuthorityGate + reference + StateMachine + audit + execution_gate |
| **Setup** | Planning ALLOW. Between planning and execution: delegation is revoked (or expired, or scope changed). |
| **Action** | At execute_gate: `require_execution_authority_recheck` is called with a non-ALLOW decision. |
| **Expected** | WorkflowError (STOP). StateMachine stays in a pre-execution state (DELEGATED/PLANNED). No file written. Audit: `execution_denial`, `authority_recheck_failed`. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-05, INV-14, THREAT-009/024 |

### INT-08 — State / version conflict

| Field | Value |
|-------|-------|
| **Objective** | Prove that two parallel workers using the same state version cause the second to be DENIED (CAS/stale-version detection). |
| **Modules integrated** | StateMachine (expected_version) + ProjectState (expected_project_version) + compare_and_swap + StateTransitionError |
| **Setup** | ProjectState at version 1. Two workers each read version 1. Worker A writes (version → 2). Worker B attempts write with `expected_version=1`. |
| **Action** | Worker B calls `project.transition(..., expected_project_version=1)`. |
| **Expected** | StateTransitionError (stale version). Worker B's state unchanged. Audit: `version_conflict`. |
| **Dependency** | Phase-1E foundation + state helpers (exists). **Status: EXECUTABLE** |
| **Invariants** | THREAT-021, ST-002, PST-001/002 |

### INT-09 — Recovery → authority re-check

| Field | Value |
|-------|-------|
| **Objective** | Prove the full recovery cycle: STOP → PRESERVE → DIAGNOSE → ROLLBACK → VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK → COMPLETE, and that recovery does not auto-authorize. |
| **Modules integrated** | RecoveryRecord (begin_recovery, diagnose, rollback, verify_restoration, replan, authority_rechecked, complete) + StateMachine (RECOVERING transition) + audit |
| **Setup** | An action fails. Create a RecoveryRecord via `begin_recovery` with `preserved_version=5`. |
| **Action** | Drive the full recovery cycle. Attempt: (a) blind retry, (b) authority_rechecked(False), (c) stale version, (d) valid full cycle. |
| **Expected** | (a) RecoveryError (blind retry). (b) RecoveryError (authority re-check). (c) RecoveryDenied (stale version). (d) COMPLETED. StateMachine: RECOVERING → (recovery → COMPLETED). Audit: recovery events. |
| **Dependency** | Phase-1E foundation + state helpers (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-12/16, THREAT-017/022, REC-001..005 |

### INT-10 — Complete only after verification

| Field | Value |
|-------|-------|
| **Objective** | Prove that COMPLETE is emitted only after verification evidence is provided; a "reported success" without evidence is DENIED. |
| **Modules integrated** | VerificationGate + StateMachine (COMPLETE transition) + TaskResult + audit |
| **Setup** | TaskResult with `status: "SUCCEEDED"` but empty `evidence`. |
| **Action** | VerificationGate evaluates. StateMachine attempts COMPLETE. |
| **Expected** | VerificationGate DENY (no evidence). StateMachine: not COMPLETE. Add evidence → ALLOW → COMPLETE. Audit: `verification_denied`, then `state_complete`. |
| **Dependency** | Phase-1E foundation (exists). **Status: EXECUTABLE** |
| **Invariants** | AUTH-INV-15, INV-09, VERIFY-001..003 |

### INT-11 — Parallel task result collection

| Field | Value |
|-------|-------|
| **Objective** | Prove that multiple tasks can be routed to the minimum specialist set, collected with versioned state, and that parallel collection with version conflict is detected. |
| **Modules integrated** | Routing (select_agents, route_tasks) + TaskResult (schema validation) + ProjectState (versioned CAS) + audit |
| **Setup** | Three tasks: engineering → CTO, finance → CFO, research → Kai. Each produces a valid TaskResult. |
| **Action** | (a) Route the tasks → minimum set. (b) Collect results into ProjectState via CAS. (c) Simulate two parallel workers reading the same version; second is DENIED. |
| **Expected** | (a) Routing returns minimum set, no blanket fan-out. (b) All results collected, schema-validated. (c) Second parallel write → StateTransitionError (version conflict). |
| **Dependency** | Foundation routing + state helpers (exists). **Status: EXECUTABLE** (in-process). Live DSH subagent parallel execution requires Phase-2C (skeleton). |
| **Invariants** | THREAT-021, PST-001/002, AUTH-INV-04 |

### INT-12 — Cross-module failure propagation

| Field | Value |
|-------|-------|
| **Objective** | Prove that a failure in one module (execution gate, state machine, audit) propagates correctly: the pipeline stops, state is preserved, an audit event is recorded, and the recovery path is entered. |
| **Modules integrated** | ALL modules: ControlPlane gates + WorkflowRun + StateMachine + execution_gate + audit_helpers + recovery |
| **Setup** | (a) Execution gate denies a protected-path write. (b) State machine refuses a stale CAS. (c) Audit append fails. |
| **Action** | Drive each failure scenario. |
| **Expected** | (a) write_through raises Denied, WorkflowRun stops, StateMachine → BLOCKED, audit has `execution_denial`. (b) StateTransitionError, no state change, audit has `version_conflict`. (c) Error recorded, recovery path entered. In all cases: no partial execution, no silent skip. |
| **Dependency** | All existing modules. **Status: EXECUTABLE** (in-process). Live DSH failure propagation requires Phase-2C (skeleton). |
| **Invariants** | AUTH-INV-15/20, INV-15, THREAT-017/022 |

---

## 5. Test matrix

| ID | Title | Executable? | Phase-2 dep. | Invariants | File |
|----|-------|-------------|-------------|------------|------|
| INT-01 | Authority→Delegation→Risk→Review→Execution | **YES** | 1E foundation | AUTH-INV-05, INV-09, INV-15 | `test_01_authority_to_execution.py` |
| INT-02 | Expired/revoked authority | **YES** | 1E foundation | AUTH-INV-06, INV-13 | `test_02_expired_revoked_authority.py` |
| INT-03 | BadSector PASS without authority | **YES** | 1E foundation | AUTH-INV-09, INV-03 | `test_03_badsector_pass.py` |
| INT-04 | Risk HIGH non-downgrade | **YES** | 1E foundation | AUTH-INV-10 | `test_04_risk_high_nondowngrade.py` |
| INT-05 | Evidence failure | **YES** | 1E foundation | EVID-001..004 | `test_05_evidence_failure.py` |
| INT-06 | Conflict escalation | **YES** | 1E foundation | CONF-001..003 | `test_06_conflict_escalation.py` |
| INT-07 | Execution-time authority re-check | **YES** | 1E foundation | AUTH-INV-05, INV-14 | `test_07_execution_recheck.py` |
| INT-08 | State/version conflict | **YES** | 1E helpers | THREAT-021, ST-002 | `test_08_state_version_conflict.py` |
| INT-09 | Recovery → authority re-check | **YES** | 1E helpers | AUTH-INV-12/16 | `test_09_recovery_recheck.py` |
| INT-10 | Complete only after verification | **YES** | 1E foundation | AUTH-INV-15, INV-09 | `test_10_complete_after_verification.py` |
| INT-11 | Parallel task result collection | **YES** (in-process) | 1E routing + helpers | THREAT-021, PST-001/002 | `test_11_parallel_collection.py` |
| INT-12 | Cross-module failure propagation | **YES** (in-process) | 1E/1E + helpers | AUTH-INV-15/20, INV-15 | `test_12_failure_propagation.py` |

---

## 6. Dependencies on Phase-2A / Phase-2B / Phase-2C

This section follows the **actual Phase-2 parallel-session structure** recorded in
`docs/phase-2/0001-requirements-traceability.md` §9:

| Phase-2 session | Production modules | Status (at time of writing) | Dependency for this plan |
|---|---|---|---|
| **A** — Authority + Delegation | `control/authority.py`, `control/delegation.py` | Mid-flight (PHASE-2 TARGET) | Future: replace the reference-gate cross-check with production-vs-foundation comparison |
| **B** — Risk + Evidence + Conflict + BadSector | `control/risk.py`, `control/evidence.py`, `control/conflict.py`, `control/badsector.py` | ALREADY IMPLEMENTED | Future: cross-check foundation gate ↔ production gate ↔ reference gate |
| **C** — Verification + Recovery | `control/verification.py`, `control/recovery.py` | Mid-flight (PHASE-2 TARGET) | Future: production verification/recovery integration |

### Current integration surface (what this plan wires today)

The 12 integration scenarios are deliberately pinned to the **stable, already-present**
modules, so the suite stays green while the production `control/*.py` modules are
mid-flight (Sessions A/C):

- `orchestrator/foundation/gates.py` (ControlPlane — real foundation gates)
- `tests/control_plane.py` (reference authority gate — cross-check oracle)
- `control/execution_gate.py` (real path-aware write channel, ADR 0002)
- `state/helpers/` (atomic write, version check, recovery)
- `audit/helpers/` (append-only log)

**When Phase-2 Sessions A/C land**, the harness's `cross_check_authority` /
`cross_check_risk` helpers are extended to compare **three** implementations:
production gate vs foundation gate vs reference gate. The integration test
**assertions** (DENY/ALLOW/state/audit) are unchanged — only the oracle set grows.

### Live-DSH variants (Phase-2C / Phase 3)

The following skeletons require a production orchestrator execution engine with
real DSH subagent delegation and collection (deferred to Phase-2C / Phase 3):

- INT-01 live full lifecycle
- INT-07 live execution re-check
- INT-11 live parallel subagent collection
- INT-12 live subagent failure propagation

Each is marked `@pytest.mark.skip(reason="requires Phase-2C — live ...")` and
documented in §7.

---

## 7. Currently blocked tests

| Test | Blocked by | Reason |
|------|-----------|--------|
| INT-11 live parallel subagent execution | Phase-2C | Production subagent factory + collection not yet built |
| INT-12 live DSH failure propagation | Phase-2C | Live DSH session with cross-subagent failure not yet wired |
| INT-01 live DSH full lifecycle | Phase-2C | Real workflow execution engine not yet built |
| INT-07 live execution re-check | Phase-2C | Real DSH runtime with delegation revocation between planning and execution |

All in-process assertions for the above scenarios ARE executable today; only the live-DSH variants are blocked.

---

## 8. Running the integration tests

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/integration/ -v
```

The test suite uses the same virtual environment as the existing tests and requires no additional dependencies.

---

## 9. Unknowns

| # | Unknown | Impact | Mitigation |
|---|---------|--------|------------|
| U1 | Production `control/*.py` module APIs (Sessions A/C are mid-flight per `docs/phase-2/0001-requirements-traceability.md`) | Integration tests may need adaptation when production modules replace reference/foundation modules | The harness abstracts the integration surface; tests assert **behaviour** (DENY/ALLOW/state/audit), not specific API calls. Extend `cross_check_*` helpers when production modules land. |
| U2 | Whether the `control/execution_gate.py` API persists unchanged in Phase 2 | Execution-gate integration tests would break if the API changes | The execution gate is the ADR-0002 mandated path; any API change must preserve the same semantics and invocation pattern. Tests assert Denied/Allowed outcomes, not function names. |
| U3 | DSH native prompt-injection handling (VERIFIED UNKNOWN) | No security claim on external-content trust | The integration tests do not make a prompt-injection claim. The adversarial tests (`tests/adversarial/`) cover this. |
| U4 | Phase-2 session completion timing (Sessions A/C mid-flight) | Production-gate cross-checks cannot run until A/C land | This plan wires only the stable foundation/reference modules; production cross-checks are added after A/C complete. |

---

## 10. Honest boundary

- **No current test is L3** (independent runtime verification). The integration tests are L1 (project control-plane) + partial L2 (DSH sandbox approval `ask` is not exercised, but the execution gate is real file I/O).
- **No security claim on prompt injection** is made or tested here.
- **No production control-plane module** is implemented by this plan or its skeletons.
- **No DSH core, profile, preset, or session policy** is modified.
- **No real DSH session** is spawned; the tests run in a single Python process against a temporary filesystem.

---

## 11. Scope check

**In scope**: `tests/integration/` (harness, conftest, 12 test files) + `docs/testing/0001-integration-test-plan.md`

**Not in scope** (and not modified):
- `control/`, `state/`, `audit/`, `orchestrator/`, `agents/`, `config/` — production paths
- DSH core, `project/`, `obsidian-vault/`, `memorycore/`, `.omni/`
- Any existing test file in `tests/` (unit, authorization, adversarial, scenarios, workflow, orchestrator)
- Any production agent prompt, production workflow, or execution engine

---

*Status: proposal. Test specification + skeleton only. No production modules are implemented. No DSH core, profile, preset, or session policy is touched. No current control is claimed to be L3.*
# Phase 4 Acceptance Matrix — Verification, Recovery & Production Boundary

- **Milestone**: Phase 4 Acceptance Matrix (Phase 3 / Session G)
- **Status**: MATRIX (analysis only; **no Phase 4 implementation, no production-runtime change, no DSH change, no profile/preset/session-policy change**)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-4/` (this document only)
- **Inputs**: PRD (canonical) · ADR 0001 / 0002 · Phase-1 specs · Phase-2 implementation (`control/*`) · Phase-3 runtime (`orchestrator/runtime`, `orchestrator/dsh`, `orchestrator/execution`) · security specs 0001–0005 · runbooks 01–10 · integration tests (INT-01..12) · runtime-evidence QA (Session E) · L3 evidence validation (Session F) · live-DSH bridge prep (Session E) · D4/D7 change requests 0003–0005 · current Phase-3 status (D1–D3 sessions).

> **Honesty rule.** Phase 4 is NOT claimed ready because Phase 3 exists. Each row below states what actually exists, what actually ran, and what is missing. Status labels are READY / READY_WITH_CONDITIONS / BLOCKED / DEFERRED and are per-row, not rolled up.

---

## Status legend

| Label | Meaning |
|---|---|
| **READY** | Capability implemented, tested, and demonstrated by captured runtime evidence (no further work required for that row's Phase-4 criterion). |
| **READY_WITH_CONDITIONS** | Implemented and tested in the deterministic runtime, but the Phase-4 criterion still requires a live-DSH precondition (mount + restart) or an independent verifier; condition named. |
| **BLOCKED** | Cannot proceed in the current environment/session — prerequisite (Human approval / DSH restart / live session) absent; not silently assumed. |
| **DEFERRED** | Intentionally out of Phase-4 scope per ADR 0001 / Phase-1 spec (out-of-process backends, storage hub, agent teams) or later-phase item. |

---

## 1. Real DSH execution

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| RDE-1 | Mount the 7 role `tool-subagent` instances (`subagent_<id>`) and role presets (D4/D7) | Human-approved composition exception; reversible profile/preset mount; DSH restart | D4/D7 mapping + instances finalized (`config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`); change requests 0003–0005 drafted; `tests/live_dsh/` bridge prep harness (75 tests) | **Human approval** of 0005 correction + 0003/0004 exception; apply correction; copy 7 presets to `$DSH_HOME/.agent-presets/`; append 7 rows to `cordis.patch.yml`; restart DSH | ISO-LIVE-001..007 (change requests 0003 §9 / 0004 §6) | None yet (not mounted) | `subagent_<id>` resolves and spawns role-scoped children with enforced toolFilter | No live mount has ever run; no runtime isolation claim (L2) | **BLOCKED** |
| RDE-2 | Real DSH specialist execution inside the Execution Flow | `RealDSHBackend` (a `DelegationBackend` over the mounted `subagent_<id>` surface) wired into `ExecutionFlow._default_subtask_runner` | `RealDSHBackend` + `BridgeNotAvailable` + FAKE/REAL/UNAVAILABLE gate (`tests/live_dsh/`); `DelegationClient` backend-agnostic seam (`orchestrator/dsh/client.py`) | RDE-1 mount; orchestrator session sets `DSH_LIVE_BRIDGE_ACTIVE=1` and injects the live dispatch bridge | Re-run `tests/live_dsh/` against the REAL backend; INT-01/07 live variant | None yet (deterministic `FakeSubagentBackend` used today) | A real child run settles with a real `runId`, real session id, and a structured TaskResult collected through `TaskResultCollector` | The runtime default still uses `FakeSubagentBackend`; no live child has been spawned | **READY_WITH_CONDITIONS** (condition: RDE-1) |
| RDE-3 | Structured TaskResult capture from a real child (`outputSchema` → `structured_output` → `SubagentResult.structured`) | Child scoped `structured_output` tool; schema validation; role-identity check | `BuildInvocation.default_task_result_schema()` + `TaskResultCollector` + `collect_one` (tested: `test_structured_capture.py`, 75 live_dsh tests) | RDE-1 | live_dsh structured-capture against REAL backend | D2 INT-01 captured a structured result via the fake adapter only | A real child satisfies the TaskResult schema; role identity preserved; missing/malformed structured result refused (AUTH-INV-13) | Live structured capture unproven | **READY_WITH_CONDITIONS** (condition: RDE-1) |
| RDE-4 | Runtime session/run provenance for real children | Real `runId`/child-session id in the provenance stamp | `DelegationProvenance` + `capture_provenance_evidence` (tested statically) | RDE-1 | live_dsh evidence/provenance against REAL backend | D2/D3 provenance uses fake run ids only | Provenance carries the real DSH session id, real run id, provider, stop reason | Live run identity never captured | **READY_WITH_CONDITIONS** (condition: RDE-1) |

## 2. Autonomous bounded Execution Flow

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| AEF-1 | Full lifecycle runs end-to-end: INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE → EXECUTE_SUBTASKS → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE → ADVERSARIAL_REVIEW → AUTHORITY_GATE → EXECUTE → VERIFY → CLOSE | Production `ExecutionFlow` coordinator | `orchestrator/runtime/flow.py` (17-phase chain), `TaskLifecycle`, `GateRunner`, `RuntimeStore`, `RuntimeAudit`, `DelegationProvider`; 75 runtime tests | None for the deterministic runtime; RDE-1 for the live variant | `tests/orchestrator/runtime/test_01_happy_path.py`; INT-01 (D2 harness `runs/d2/`) | **D2 INT-01 = COMPLETE**, `task-1`, gates ALLOW, file written via execution gate, state `DRAFT→…→COMPLETE`, audit 18 classes | Flow reaches COMPLETE with all gates passing and verification PASSED in the deterministic runtime | Live-DSH full lifecycle not yet run | **READY** (deterministic runtime) / **READY_WITH_CONDITIONS** (live) |
| AEF-2 | Autonomy is bounded: flow stops fail-closed on any gate denial; no continuation past a denial | Fail-closed gates (AUTH-INV-20), typed `FlowStopped`/`GateDenied` | `flow._stop`/`_route_recovery`; 75 runtime tests incl. denial paths | None | `test_02_authority.py` (denial → BLOCKED, no file); INT-07 (D2) | **D2 INT-07 = BLOCKED**, no unauthorized mutation, `execution_denial` audited | A denied flow never executes, never writes, and records the denial | None observed in the deterministic runtime | **READY** |
| AEF-3 | Routing to the minimum specialist set (no blanket fan-out) | `select_agents` + `validate_no_fanout` | `orchestrator/foundation/routing.py` (tested) | None | `test_05_routing.py`; INT-01 selected `("cto",)` | D2 INT-01 `selected=["cto"]` | Every task routes to the minimum set; never all 7 | None | **READY** |
| AEF-4 | Autonomous rework/decision loops bounded by gates, not infinite retry | No-blind-retry (AUTH-INV-16), rework budget | `control/recovery.py` `request_retry` + `max_attempts`; `recovery_gate` | None | REC-001..006 (`tests/unit/test_recovery.py`, `test_09_recovery_recheck.py`) | Runtime tests pass; no live rework run | Retry only on a new diagnosed cause; budget capped | Live rework loop not exercised | **READY** (deterministic) / **READY_WITH_CONDITIONS** (live) |

## 3. Verification

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| VER-1 | Expected-vs-actual verification before COMPLETE (VERIFY-001/002, AUTH-INV-15, THREAT-016) | `VerificationSession` + `VerificationGate`; expected declared before execution | `control/verification.py`, `orchestrator/execution/engine.py`; `_attach_evidence` | None | VERIFY-001..003; INT-10; runtime `test_04_verification_recovery.py`; INT-01 (D2) | D2 INT-01 verification **PASSED** (`code_change`, self, `test`+`build` evidence, expected vs observed match) | COMPLETE only on a PASSED verification session; a reported success without observed outcome is refused | None (self-verification works); independent verification is VER-2 | **READY** (self) |
| VER-2 | Independent verification for high-impact categories (VERIFY-003 independence; REC-003 restoration) | Independent verifier outside the executor's session tree | `verification_requirements` marks `independent` categories; engine checks independent evidence presence | L3-verifier infrastructure (see L3-1) | L3-VER-002/003/004/005 (spec `docs/design/0002`) | None (no independent verifier; self-only evidence today) | For `independent` categories, an independent verifier (separate process/session) measures the outcome | No independent verifier built; no L3 claim | **BLOCKED** (needs L3 verifier) |
| VER-3 | Evidence kind sufficiency per action category (VERIFY-003) | `verification_requirements` per-category evidence kinds | `control/verification.py` `_VERIFICATION_REQUIREMENTS`; `_attach_evidence` adds required kinds | None | VERIFY-003; INT-10 | D2 INT-01 evidence kinds `test`+`build` present and passed | Every required kind has at least one artifact; missing → INSUFFICIENT (no COMPLETE) | None in deterministic runtime | **READY** |

## 4. Recovery

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| REC-1 | Full recovery lifecycle: STOP → PRESERVE → DIAGNOSE → ROLLBACK → VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK → COMPLETE | `RecoveryController` (AUTH-INV-12/16, REC-001..006) | `control/recovery.py`, `state/helpers/recovery.py`, `orchestrator/execution/engine.py` `begin_recovery`/`recover`; `flow.begin_recovery`/`recover` | None (deterministic) / RDE-1 (live) | REC-001..006; INT-09; `test_04_verification_recovery.py` | Runtime tests pass; no live recovery executed | Recovery follows the documented protocol and re-checks authority; restoration independently verified | Live recovery path not exercised | **READY** (deterministic) / **READY_WITH_CONDITIONS** (live) |
| REC-2 | No blind retry; bounded attempts; escalate on unknown failure class | `request_retry` new-cause enforcement; `unknown` → escalate (Runbook 08) | `control/recovery.py`, `classify_failure` (`unknown` → escalation) | None | REC-001; INT-12; `test_07_dsh_failures.py` | Runtime tests pass; no live failure run | A retry without a new diagnosed cause is refused; unknown class escalates, never guessed | None in deterministic runtime | **READY** |
| REC-3 | Recovery re-checks authority and never expands privilege (AUTH-INV-12, THREAT-017) | Same-gate re-check bounded to original authority | `flow.recover` `_gate_fn` + `original_authority()`; `RecoveryController.recheck_authority` | None | INT-09; REC-004/005; `test_09_invariants.py` `test_recovery_authority_recheck_denies` | Runtime tests pass | Recovery uses only the original action/target/grants; any denial stops recovery | None in deterministic runtime | **READY** |

## 5. Parallel execution

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| PAR-1 | Independent subtasks run concurrently (PRD §7.5/7.6; contract §6) | `ParallelExecutor` over the approved adapter; `assert_parallel_safe` | `orchestrator/runtime/parallel.py` (plans, safety, executor, CAS checks) | RDE-1 (live concurrency) | `test_08_parallel.py`; INT-11 | D3 harness prepared (`tests/live_evidence/`) but **no live dispatch recorded**; in-process parallel tests pass | ≥2 independent children spawn concurrently; results collect in batch order | No live parallel subagent execution has run (deterministic in-process only) | **READY** (in-process) / **READY_WITH_CONDITIONS** (live) |
| PAR-2 | Parallel safety: dependency independence, exclusive single-owner, read-only specialist scope | `assert_parallel_safe` pre-batch proof (THREAT-021) | `parallel.py` `assert_parallel_safe` + `build_plans`; unsafe → sequential, never forced parallel | None | `test_08_parallel.py` | Runtime tests pass | A batch that cannot be proven independent runs sequentially; held version validated before/after | None | **READY** |
| PAR-3 | Concurrent state-version control (stale CAS DENY, THREAT-021/022) | ProjectState CAS + `RuntimeStore.check_current` | `orchestrator/runtime/store.py`, `foundation/state.py` | None | INT-08; `test_08_parallel.py` | Runtime tests pass | A stale writer is refused before any mutation; version drift stops the flow | None | **READY** |

## 6. Audit / provenance

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| AUD-1 | Append-only project audit ledger with integrity (ADR 0002 writer channel) | `audit_append` sanctioned channel; append-only + hash-chain helpers | `control/execution_gate.py` `audit_append`; `audit/helpers/append_log.py`, `integrity.py`; `RuntimeAudit` | None | AUD-001..004; `test_audit_hardening.py`; `test_01_happy_path.py::test_audit_records_lifecycle` | D2 INT-01/07 audit ledgers on disk (`runs/d2/int01/audit_events.jsonl`, 18/16 classes) | Every consequential transition emits an audit event with authority_source; ledger append-only | None (L1/L2) | **READY** |
| AUD-2 | Runtime provenance (role identity, delegation id, run id, session) preserved per delegation | `DelegationProvenance` + evidence model | `orchestrator/dsh/provenance.py`; `tests/live_dsh/evidence.py`; `tests/live_evidence/harness.py` | RDE-1 for real run ids | live_dsh provenance tests; INT-11 | D2/D3 provenance uses fake run ids; structure validated | Provenance preserves role identity + delegation id + run id + session (real) | Real run/session identity not yet captured | **READY_WITH_CONDITIONS** (condition: RDE-1) |
| AUD-3 | Audit is never authority (AUTH-INV-14) | Runtime audit events are records, not grants | `audit_is_authority_source` always False (audit/helpers); QA rule R10 | None | `test_audit_hardening.py`; evidence QA R10 | Tests pass | An audit entry never grants authority; PASS-without-delegation rejected | None | **READY** |

## 7. Authority enforcement

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| AUTH-1 | Execution-time authority re-check (AUTH-INV-05/06) mandatory, not just planning | `ExecutionEngine.recheck_authority` + provider re-read at execute | `orchestrator/execution/engine.py`; `orchestrator/runtime/flow.py::_execute`; `FileDelegationProvider` | None | INT-07; `test_02_authority.py` | **D2 INT-07** revocation between plan and execute → `execution_denial` (AUTH-INV-06), BLOCKED, no mutation | Execution DENYs when authority changes between planning and execution | None (deterministic runtime proven) | **READY** |
| AUTH-2 | Revoked/expired/scope-changed delegation DENY at execution; no unauthorized mutation | Registry re-read + revocation list + expiry at execute | `FileDelegationProvider`/`MemoryDelegationProvider`; `recheck_authority`; `registry revocations.json` | None | INT-02, INT-07; `test_02_authority.py` | D2 INT-07 `revocations.json=["delegation-d2-int07"]`, `execution_denial`, no file | DENY recorded in audit with authority_source; target untouched | None | **READY** |
| AUTH-3 | Delegation registry single-writer + protected-path execution gate (ADR 0002) | `registry_write`/`audit_append` sanctioned channels; path-aware `authorize_write` | `control/execution_gate.py` (`SANCTIONED_ROOTS`, protected roots) | None | REG-001..005; DLG-001; PATH tests | Runtime/integration tests pass; ISO-LIVE-006 not run | Any non-writer write to `state/registry/`/`audit/` DENIED before mutation; writer channel cannot cross roots | DSH-layer path isolation for bash-wielding roles remains L1 (ADR 0002 residual) | **READY** (L1/L2 config) / ISO-LIVE-006 **BLOCKED** |

## 8. Production boundaries

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| PB-1 | Session policy stays `workspace-write` + `ask` (never `danger-full-access` + `never`) | Session sandbox/approval baseline | DSH-native session policy (ADR 0001 Decision 2); current session = workspace-write + ask | None | ISO-* / runtime context snapshot | Current runtime context: `workspace-write` + `ask` (verified in this session) | Baseline is fail-closed; no silent drift to full-access | Policy drift must be watched per session | **READY** |
| PB-2 | No DSH core/profile/preset modification; only the reversible D4/D7 exception | Controlled composition exception discipline | ADR 0001 Decision 7; change requests 0003–0005 (PENDING_HUMAN_APPROVAL) | Human approval + reversible mount + rollback on standby | Rollback procedure (0003 §8 / 0005 §9) | No external DSH file has been modified (all sessions) | Only approved, reversible, audited composition changes | The exception itself is still PENDING_HUMAN_APPROVAL | **READY** (discipline) / mount **BLOCKED** |
| PB-3 | Out-of-process backends, storage hub, agent teams out of scope (V1) | Explicit boundary | ADR 0001 Decisions/UNKNOWN 2–4; Phase-1 spec §2 | None | n/a | n/a | Not treated as available | None (deferred by design) | **DEFERRED** |
| PB-4 | Protected production paths (state/registry, audit) reachable only via sanctioned channels | ADR 0002 writer discipline + path-aware gate | `control/execution_gate.py` | None | REG-*, PATH-*; ISO-LIVE-006 (future) | L1/L2 tests pass; ISO-LIVE-006 blocked | Writes to protected paths DENIED by code, audited; residual bash-writer gap explicit | DSH-layer hard isolation for bash-wielding roles is Phase-5 hardening | **READY** (L1) / ISO-LIVE-006 **BLOCKED** |

## 9. L3 prerequisites

| # | Objective | Required capability | Existing implementation | Prerequisite | Test | Runtime evidence | Acceptance criterion | Remaining gap | Status |
|---|---|---|---|---|---|---|---|---|---|
| L3-0 | No current control claimed L3 (honesty boundary) | Explicit no-L3-claim discipline | `docs/testing/0002` §2.2, `docs/security/0003` | None | QA rule R3/R15 reject false L3 | No L3 bundle exists | No bundle claims L3 without P1–P4 | n/a | **READY** (discipline) |
| L3-1 | Independent verifier (P2) + external oracle (P3) + reproducibility (P4) | L3 runner: separate-process verifier, separate UID, Human-signed plan.json, replay | `docs/design/0002` runner contract R1–R8; `docs/testing/0003` LV1..LV20; `tests/l3_reference/schemas` (11) + fixtures (INT-01/07/11/12) | Build the L3 verifier + reference re-implementations (O1) + Human-signed plans (O4) | L3-AUTH-001..009, L3-DLG-001..007, L3-ISO-001..010, L3-PATH-001..008, L3-ST-001..008, L3-AUD-001..007, L3-XG-001..009, L3-REC-001..007, L3-VER-001..006 (71 scenarios) | None (spec + schemas + fixtures only; no verifier, no run) | Each L3 scenario: ≥2 oracle classes, IO-1..IO-10 pass, verdict match, bundle complete | Verifier, reference gates, Human-signed plans all absent | **BLOCKED** |
| L3-2 | Real-DSH session for L3 (P1) | Mounted D4/D7 instances + live bridge | See RDE-1/RDE-2 | RDE-1 mount + live bridge injection | L3-ISO-*, L3-DLG-*, L3-PATH-* live | None | Live child tool schema/denial observed with independent observer | Mount still PENDING_HUMAN_APPROVAL | **BLOCKED** |
| L3-3 | L2-LIVE evidence bundles validated for the four runtime scenarios | Structure-only QA validator | `tests/evidence/evidence_qa.py` + `test_evidence_qa.py` (12 QA tests, R1..R15) | None | `pytest tests/evidence/` | Evidence-qa tests pass (D2/D3 bundles validate structurally) | L2-LIVE bundles are structurally complete; false-L3 and agent-only rejected | Validator is structure-only — not runtime verification | **READY** (validation layer) |
| L3-4 | L3 evidence bundle schema contract + fixtures | 11 schemas + per-scenario fixtures | `tests/l3_reference/schemas/` (11) + `fixtures/INT-0{1,7,11,12}` + shared | None | LV1..LV20 rules | Schemas/fixtures present and inert | Bundle files conform to schemas; signoff precedes runtime | Not executable; placeholders only | **READY_WITH_CONDITIONS** (spec complete; execution needs L3-1/L3-2) |

---

## 10. Summary by status

| Status | Rows |
|---|---|
| **READY** (deterministic runtime) | AEF-1(det), AEF-2, AEF-3, AEF-4(det), VER-1, VER-3, REC-1(det), REC-2, REC-3, PAR-2, PAR-3, AUD-1, AUD-3, AUTH-1, AUTH-2, AUTH-3(L1), PB-1, PB-2(discipline), PB-4(L1), L3-0, L3-3 |
| **READY_WITH_CONDITIONS** | RDE-2, RDE-3, RDE-4, AEF-1(live), AEF-4(live), REC-1(live), PAR-1(live), AUD-2, L3-4 |
| **BLOCKED** | RDE-1 (mount), VER-2 (independent verifier), L3-1 (verifier/oracle), L3-2 (live session), ISO-LIVE-006 (live registry-gate) |
| **DEFERRED** | PB-3 (out-of-process backends / storage hub / agent teams) |

**Roll-up honesty:** the majority of Phase-4-critical items are **READY at the deterministic-runtime level with captured evidence (D2)** or **READY_WITH_CONDITIONS gated on the D4/D7 mount**. The genuinely **BLOCKED** items are the ones that Phase 4 and L3 both require but that no session has produced: (1) the real mounted DSH bridge (RDE-1, Human approval pending), (2) an independent L3 verifier + reference oracles (VER-2, L3-1), and (3) the live isolation tests that need a mounted session (L3-2, ISO-LIVE-006). **Phase 4 is therefore NOT ready**: the acceptance criteria for real-DSH execution, independent verification, and L3 evidence cannot be met until those blockers clear. No evidence bundle currently satisfies P1–P4; no L3 claim is made.

---

## 11. Dependencies

1. **D4/D7 composition mount** (RDE-1) unblocks RDE-2..4, AEF-1(live), REC-1(live), PAR-1(live), AUD-2, L3-2. Chain: Human approval (0005) → apply 25-name correction → copy presets → append instance rows → DSH restart → set `DSH_LIVE_BRIDGE_ACTIVE=1`.
2. **L3 verifier + reference gates** (VER-2, L3-1) depend on the L3 plan (0003), the 71-scenario spec (design 0002), the evidence infra (security 0005), and the L3 schemas/fixtures (Session F). They do not depend on the mount, but most L3 scenarios require the live session for P1.
3. **Live isolation evidence** (ISO-LIVE-001..007, L3-2) depend on RDE-1 and cannot be executed from this session.
4. **Runtime evidence bundles** (AUD-1/AUD-3, L3-3) exist from D2/D3 and validate structurally; they are not L3.

## 12. Blockers

| Blocker | Affected rows | Why blocked |
|---|---|---|
| D4/D7 mount Human approval + DSH restart | RDE-1..4, live variants, L3-2 | PENDING_HUMAN_APPROVAL (0003/0004/0005); cannot mount/restart from this session |
| Independent L3 verifier not built | VER-2, L3-1 | No separate-process observer, no reference re-implementations, no Human-signed plans |
| ISO-LIVE-006 registry-write live denial | AUTH-3, PB-4 (live) | Execution gate is L1-design; DSH-layer path isolation not yet live (ADR 0002 residual) |

## 13. Unknowns

- Runtime acceptance of `persona`/`toolFilter`/`maxDepth` on the spawn provider until ISO-LIVE-001/007 run (change requests 0004 §11).
- Prompt-injection / external-content trust behavior of DSH (no claim; UNKNOWN — ADR 0001 UNKNOWN #1).
- Whether the orchestrator session (after mount) can inject the live dispatch bridge without per-session policy change (INFERRED yes, UNVERIFIED).
- Cost/latency behavior of real parallel spawns (no live run).

## 14. Security claim status

- **No L3 claim.** No evidence bundle satisfies P1–P4.
- **L2 not claimed for role isolation**: ISO-LIVE tests have not run (mount pending). Role isolation is at L1 (config + deterministic tests) plus L1/L2 config-level toolFilter definitions.
- **L2-LIVE** evidence bundles (D2/D3) are structurally validated by the Session-E QA validator; they prove the deterministic runtime's behavior, not live-DSH behavior.
- Security-critical controls that ARE runtime-proven (deterministic): authority re-check, revocation DENY, protected-path gate, append-only audit, no-blind-retry recovery, verification-before-COMPLETE. Controls that are NOT yet runtime-proven: real subagent toolFilter enforcement, independent verification, live parallel dispatch, live recovery.

## 15. Scope check

**In scope:** `docs/phase-4/0001-acceptance-matrix.md` (this file). No production code, no DSH core/profile/preset, no session policy, no config, no agents, no existing test modified. No Phase 4 implementation begun.

**Not in scope** (and untouched): `orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/`, `tests/` (all), `docs/` outside `phase-4/`.

---

*Status: MATRIX. Analysis only. No Phase 4 implementation. No DSH core / profile / preset / session policy change. No live scenario executed. Phase 4 is NOT claimed ready on the strength of Phase 3.*

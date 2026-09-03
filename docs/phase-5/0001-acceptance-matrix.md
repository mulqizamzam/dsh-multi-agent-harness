# Phase 5 — Acceptance Matrix (Traceability)

- **Milestone**: Phase 5 — PARALLEL HARDENING WAVE
- **Status**: MATRIX (analysis only; no Phase-6 implementation, no L3 claim, no DSH/core change)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/` (this document). No code, no DSH, no profile/preset, no session policy.
- **Inputs**: PRD (§4–§19) · ADR 0001/0002 · Phase-1 specs · Phase-2 runbooks · Phase-3 closure · Phase-4 matrix + reconciliation · security specs 0001–0006 · control modules (authority, execution_gate, recovery, verification) · runtime (flow, engine, parallel, store, audit, dsh) · observability · L3 reference/runner · Phase-4 scenarios

---

## Status legend

| Label | Meaning |
|---|---|
| **READY** | Requirement satisfied by existing implementation + evidence; no Phase-5 gap. |
| **READY_WITH_CONDITIONS** | Requirement satisfied with a named condition (mount, Human answerer, independent verifier). |
| **HARDENED** | Gap identified and closed by Phase-5 hardening (new test or extension). |
| **BLOCKED** | Cannot proceed — prerequisite (Human approval / DSH restart / independent verifier) absent. |
| **DEFERRED** | Intentionally out of Phase-5 scope (Phase 6, out-of-process backends, storage hub). |
| **UNKNOWN** | Not verifiable in the current environment / not yet investigated. |

---

## 1. Authority / delegation

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| AD-1 | No authority from model text (AUTH-INV-01) | `control/authority.py` `recheck_authority` rejects text claims; `approval-<id>` pattern enforced | None needed | `test_authority.py::test_auth_008` | D2 INT-07, INT-01 | Text claim → DENY | None | **READY** |
| AD-2 | Delegation scope containment (AUTH-INV-04) | `control/delegation.py` `target_in_scope`; `DelegationClient._check_scope_containment` | None needed | `test_authority.py::TestScopeContainment` | D2 INT-01 | Child scope ⊆ parent scope | None | **READY** |
| AD-3 | Execution-time re-check (AUTH-INV-05/06) | `ExecutionEngine.recheck_authority`; `flow._execute` re-reads delegation | None needed | `test_02_authority.py`; INT-07 | D2 INT-07, Phase-3 closure | Revocation between plan/exec → DENY | None | **READY** |
| AD-4 | Expiry/revocation at execution (AUTH-INV-06) | `recheck_authority` checks `revocation_list` + `is_expired` | Stale-revocation-list detection | `test_authority.py::test_auth_004` | D2 INT-07 | Expired/revoked → DENY | None | **READY** |
| AD-5 | Subdelegation DENY BY DEFAULT (DLG-003) | `DelegationClient._assert_actor_may_delegate`; toolFilter deny | None needed | `test_authority.py::TestSubdelegation`; live_dsh role adapters | D3 INT-12, role adapter tests | Specialist subdelegate → DENY | None | **READY** |
| AD-6 | BadSector PASS ≠ authority (AUTH-INV-09) | `control/authority.py` `badsector_pass_is_authority` always False | None needed | `test_authority.py::test_auth_007` | D2 | PASS → no ALLOW | None | **READY** |
| AD-7 | Authority re-check on recovery (AUTH-INV-12) | `flow.recover` `recheck_authority`; `RecoveryController.recheck_authority` | Recovery idempotency guard (double-recovery) | `test_04_verification_recovery.py`; Phase-5 `test_idempotency.py` | D3 INT-12 | Recovery re-passes same gate; double-recovery DENIED | None | **HARDENED** |

## 2. Role isolation

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| RI-1 | CTO cannot access CFO-only capability (ISO-001) | toolFilter (CFO deny `bash`/`edit`/`write`; CTO allow); D4/D7 instance per role | Negative path test proving residual still open | `test_negative_path_isolation.py` | D4/D7 config, ADR 0002 | A bash-capable role can reach the protected path at DSH layer (L1 gate only) | DSH-layer path isolation is Phase-5+ (ADR 0002 residual) | **HARDENED** (residual documented) |
| RI-2 | CFO cannot write code (ISO-002) | toolFilter: CFO deny `write`/`edit`/`bash`; verified by ISO-LIVE-002 | None needed | `test_authority.py::test_iso_002` | ISO-LIVE-002 | CFO write denied | None | **READY** |
| RI-3 | Kai cannot write project files (ISO-003) | toolFilter: Kai deny `bash`/`edit`/`write` | None needed | `test_authority.py::test_iso_003` | ISO-LIVE-003 | Kai write denied | None | **READY** |
| RI-4 | BadSector cannot execute (ISO-006) | toolFilter: BadSector deny `bash`/`edit`/`write` | None needed | `test_authority.py::test_iso_006` | ISO-LIVE-003 | BadSector execution denied | None | **READY** |
| RI-5 | Inherited composition (THREAT-006) | child `tool-subagent` instance with its own toolFilter; inherits parent sandbox | Negative test: bash-capable child reaching protected path | `test_negative_path_isolation.py` | D4/D7 config, ADR 0002 | Child scope does not inherit parent's broader access | DSH-layer residual documented | **HARDENED** |

## 3. Protected path

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| PP-1 | `state/registry/**` protected (ADR 0002) | `control/execution_gate.py` `authorize_write` with `PROTECTED_REL_ROOTS` | Chain + truncation detection for audit paths | `test_execution_gate_live.py`; Phase-5 `test_detection.py` | ISO-LIVE-006 (L1 gate) | Write to registry → DENY; audit chain break → detected | DSH-layer residual for bash-capable roles | **HARDENED** |
| PP-2 | `audit/**` protected (ADR 0002) | `audit_append` sanctioned channel; `PROTECTED_REL_ROOTS` includes audit | Audit integrity chain verification | `test_execution_gate_live.py`; Phase-5 `test_chain.py` | ISO-LIVE-006 | Write to audit → DENY; chain verify → detect mutation | None | **HARDENED** |
| PP-3 | Traversal / symlink / prefix confusion (PATH-*) | `authorize_write` normalizes path; traversal/symlink DENY | None needed | `test_execution_gate_live.py::test_traversal_denied` | L1 integration tests | `..` → DENY; symlink → DENY | None | **READY** |
| PP-4 | Writer channel cannot cross roots (ADR 0002 addendum) | `SANCTIONED_ROOTS` per-channel scope; `registry_write` → `state/registry/` only; `audit_append` → `audit/` only | None needed | `test_execution_gate_live.py::TestWriterChannelScopeLive` | L1 tests | Writer channel cannot write outside its root | None | **READY** |

## 4. State transition

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| ST-1 | Illegal transition denied (ST-001) | `StateMachine.transition` validates transitions; `TaskLifecycle.transition` requires authority | None needed | `test_state_audit.py`; `test_09_invariants.py` | D2 INT-01/07 | Illegal transition → raise | None | **READY** |
| ST-2 | Model writing `status: APPROVED` has no effect (ST-002) | `ProjectState` is DATA; only control plane transitions are authoritative | None needed | `test_authority.py::test_auth_007` | D2 | State file `approved:true` → no authority | None | **READY** |
| ST-3 | Stale version CAS denied (ST-003) | `RuntimeStore.persist` CAS; `check_current` pre-execution | Stale recovery detection | `test_state_hardening.py`; Phase-5 `test_staleness.py` | D2 | Version mismatch → DENY; recovery re-reads | None | **HARDENED** |
| ST-4 | Atomic write crash (ST-004) | `atomic_write` temp+rename+fsync; no partial file | None needed | `test_state_hardening.py` | D2 | Crash → no half-written state | None | **READY** |
| ST-5 | Required review triggers transition (ST-005) | `flow._run_chain` enforces `review_required`; skipping → transition violation | None needed | `test_03_gates.py`; `test_09_invariants.py` | D2 | HIGH without review → BLOCKED | None | **READY** |

## 5. Audit integrity

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| AI-1 | Append-only (AUTH-INV-14) | `audit/helpers/append_log.py` `append_event`; `verify_append_only` | Chain verification + sidecar compare | `test_audit_hardening.py`; Phase-5 `test_chain.py` | D2/D3 INT-01..12 | Append-only; overwrite → detection | None | **HARDENED** |
| AI-2 | Hash chain integrity | `audit/helpers/integrity.py` `compute_chain`/`verify_chain` | Forced chain recompute; missing chain detection | `test_audit_hardening.py`; Phase-5 `test_chain.py` | INT-01/07 audit logs | Chain break → `AuditIntegrityError` | None | **HARDENED** |
| AI-3 | Truncation detection | `verify_append_only` `expected_event_ids` / `expected_count` | Strict truncation detection with cumulative hash | `test_audit_hardening.py`; Phase-5 `test_detection.py` | Runbook 10 | Line count drop → detection | None | **HARDENED** |
| AI-4 | Duplicate/replay detection | `verify_append_only` checks `event_id` uniqueness | Cross-event duplicate detection; timestamp replay | `test_audit_hardening.py`; Phase-5 `test_detection.py` | Runbook 10 | Duplicate event_id → detection | None | **HARDENED** |
| AI-5 | Ordering verification | `verify_append_only` timestamp monotonicity | Phase-5 ordering detection | `test_audit_hardening.py`; Phase-5 `test_detection.py` | Runbook 10 | Out-of-order → detection | None | **HARDENED** |
| AI-6 | Audit-is-authority rejection (AUTH-INV-14) | `audit_is_authority_source` always False | Approval-shaped event detection | `test_audit_hardening.py`; Phase-5 `test_authority.py` | D2/D3 | Audit `APPROVED` → data, never grant | None | **HARDENED** |
| AI-7 | Recovery/audit correlation | Runtime audit events carry `recovery_state_transition` | Recovery-event linking to execution events | Phase-5 `test_recovery_correlation.py` | D3 INT-12 | Recovery events traceable to originating execution | None | **HARDENED** |

## 6. Execution gate

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| EG-1 | Pre-execution checklist (AUTH-INV-05/11/20) | `ExecutionEngine.validate` + `recheck_authority` + `authorize_write` | None needed | `test_execution_gate_live.py`; INT-01/07 | D2 | All 14 items pass → ALLOW; any fail → DENY | None | **READY** |
| EG-2 | Protected path DENY (ADR 0002) | `authorize_write` path classification | None needed | `test_execution_gate_live.py` | ISO-LIVE-006 | Protected path → DENY | DSH-layer residual | **READY** |
| EG-3 | Traversal / symlink DENY | `authorize_write` path normalization | None needed | `test_execution_gate_live.py` | L1 tests | `..` → DENY | None | **READY** |
| EG-4 | Writer channel scope (ADR 0002) | `SANCTIONED_ROOTS` per channel | None needed | `test_execution_gate_live.py` | L1 tests | Writer cannot cross root | None | **READY** |

## 7. Recovery

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| RC-1 | No blind retry (AUTH-INV-16/REC-001) | `RecoveryController.request_retry` requires new cause | Budget enforcement (max_attempts, max_rework_cycles) | `test_recovery.py`; Phase-5 `test_budget.py` | D3 INT-12 | Empty/identical cause → refused; budget exhausted → DENY | None | **HARDENED** |
| RC-2 | Recovery cannot expand privilege (AUTH-INV-12/REC-004) | `RecoveryController.recheck_authority` bounded to original authority | Authority re-check hardening | `test_09_invariants.py`; Phase-5 `test_recovery_authority.py` | D3 INT-12 | Recovery with expanded scope → DENY | None | **HARDENED** |
| RC-3 | Restoration verification (REC-003) | `RecoveryController.verify_restoration` | Independent restoration evidence | `test_recovery.py`; Phase-5 `test_restoration.py` | Runbook 07 | Restoration must be independently verified; hash mismatch → fail | None | **HARDENED** |
| RC-4 | Stale recovery detection (THREAT-022) | `validate_against_current_version` | Stale recovery hardening (state drift between begin and re-execute) | `test_recovery.py`; Phase-5 `test_staleness.py` | Runbook 08 | State version changed → recovery refused | None | **HARDENED** |
| RC-5 | Double-recovery prevention | None (gap) | `control/recovery_hardening/idempotency.py` | Phase-5 `test_idempotency.py` | Runbook 08 | Second recovery from COMPLETE/FAILED → DENIED | None | **HARDENED** |
| RC-6 | Terminal-state protection | None (gap) | `idempotency.py` terminal-state guard | Phase-5 `test_idempotency.py` | Runbook 08 | Recovery from COMPLETE → DENIED | None | **HARDENED** |

## 8. Verification

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| VF-1 | Expected declared before execution (VERIFY-001) | `VerificationSession` created with expected in `Engine.validate` | None needed | INT-01; `test_04_verification_recovery.py` | D2 INT-01 | Expected before exec → ALLOW; missing → DENY | None | **READY** |
| VF-2 | Reported ≠ verified (VERIFY-002) | `engine.complete()` raises `VerificationRefused` unless PASSED | None needed | `test_verification.py` | D2 INT-01 | Agent claim alone → no COMPLETE | None | **READY** |
| VF-3 | Evidence sufficiency (VERIFY-003) | `_attach_evidence` + `verification_requirements` | None needed | INT-10; `test_verification.py` | D2 INT-01 | Required kinds present → PASS; missing → INSUFFICIENT | None | **READY** |
| VF-4 | Independent verification for HIGH | `verification_requirements` marks `independent` categories | None needed (L3 infrastructure exists as replay stub) | `tests/l3_runner/` | L3-1 | Independent verifier → separate process/UID | L3 live execution blocked | **BLOCKED** |

## 9. Parallel execution

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| PE-1 | Dependency independence (THREAT-021) | `assert_parallel_safe` pre-batch proof | None needed | `test_08_parallel.py`; INT-11 | D3 INT-11 | Inter-dependent → sequential; independent → parallel | None | **READY** |
| PE-2 | Single-owner task ownership | `assert_parallel_safe` checks exclusive ownership | None needed | `test_08_parallel.py` | D3 | Duplicate task id → ParallelUnsafe | None | **READY** |
| PE-3 | Read-only specialist scope | `assert_parallel_safe` rejects write scope | None needed | `test_08_parallel.py` | D3 | Write scope → ParallelUnsafe | None | **READY** |
| PE-4 | State-version CAS (THREAT-021/022) | `RuntimeStore.check_current` before/after parallel batch | None needed | `test_08_parallel.py`; INT-11 | D3 INT-11 | Version drift → StaleStateDetected | None | **READY** |
| PE-5 | Concurrency bounded | `DEFAULT_MAX_WORKERS=4`; `ThreadPoolExecutor` | None needed | `test_08_parallel.py` | D3 | max_workers bound | None | **READY** |
| PE-6 | Failure propagation (INT-12) | `ParallelExecutor.run` propagates first failure in batch order | None needed | `test_08_parallel.py`; INT-12 | D3 INT-12 | First failure → re-raised; no partial success | None | **READY** |

## 10. Observability

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| OV-1 | Run/task/delegation correlation | `observability/ingest.py` `RunCorrelator` | None needed | `test_lifecycle.py` | Phase-4 Session D | Correlation → run/task/delegation index | None | **READY** |
| OV-2 | Fail-closed rejection | `validate_event_correlation` rejects malformed events | None needed | `test_fail_closed.py` | Phase-4 Session D | Missing field → REJECTED | None | **READY** |
| OV-3 | Health/sanity report | `observability/queries.py` `health_report` | None needed | `test_queries.py` | Phase-4 Session D | Health report → problems/integrity | None | **READY** |
| OV-4 | Metrics | `observability/metrics.py` | None needed | `test_metrics.py` | Phase-4 Session D | All metrics computed | None | **READY** |
| OV-5 | Read-side only (no audit writes) | `observability/` has 0 `audit_append`/`append_event` calls | None needed | Master integration | Phase-4 Session D | No audit write | None | **READY** |

## 11. L3 readiness

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| L3-0 | No L3 claim without P1–P4 | `tests/l3_runner/` `assert_clean_imports`; `test_no_control_is_claimed_l3` | Preflight checklist for live L3 | `test_l3_infrastructure.py`; Phase-5 `test_l3_preflight.py` | docs/security/0006 | L3 claim only when P1–P4 satisfied | None | **HARDENED** |
| L3-1 | Verifier independence (P2) | Subprocess runner, separate PID, `assert_clean_imports` | Readiness assertion: verifier can run, separate PID | `test_l3_preflight.py` | tests/l3_runner/ | Verifier process ≠ orchestrator PID; no production imports | Live L3 requires separate UID provision | **READY_WITH_CONDITIONS** |
| L3-2 | Oracle independence (P3) | Reference gates are stdlib-only; AST-checked | Preflight oracle schema validation | `test_l3_preflight.py` | tests/l3_reference/ | At least 2 oracle classes; no production imports | None | **READY** |
| L3-3 | Evidence bundle readiness (E1–E13) | `tests/l3_runner/collector.py`; schemas in `tests/l3_reference/schemas/` | Bundle completeness preflight | `test_l3_preflight.py` | tests/l3_reference/fixtures/ | All 13 bundle items present; schema-valid | Need signed plan.json | **READY_WITH_CONDITIONS** |
| L3-4 | Signed-plan prerequisites | `plan.json` template with `human_signoff_*` | Preflight: signoff present, signoff before runtime | `test_l3_preflight.py` | L3 spec (0003) | `human_signoff_ts` < `captured_at` | Human signing process not defined | **BLOCKED** |
| L3-5 | Separate-process prerequisites | `subprocess` runner; `verifier_mode=subprocess` | Preflight: subprocess works, workspace exists | `test_l3_preflight.py` | tests/l3_runner/ | Subprocess can write to bundle dir; PID differs | None | **READY** |
| L3-6 | Replayability (P4) | `RecordedRuntimeDriver`; `replay.json` with fixture_hash | Replay preflight: fixture hash matches, binary sha256 | `test_l3_preflight.py` | tests/l3_runner/replay.py | Deterministic replay → same verdict | None | **READY** |

## 12. Production security / DSH residual

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| PS-1 | DSH-level path isolation for bash-capable roles | None (acknowledged ADR 0002 residual) | Negative test documenting the residual | `test_negative_path_isolation.py` | ADR 0002, D4/D7 config | A bash-capable role CAN reach the protected path (no DSH layer); gate is at project execution layer only | DSH-layer path isolation is Phase-5+; not closed | **HARDENED** (residual proven open) |
| PS-2 | Session-level sandbox limitation | sandbox = per-session, not per-agent | Documented threat boundary | Phase-5 docs | ADR 0001 Decision 1 | Session sandbox shared; toolFilter is role boundary | Per-agent sandbox not natively expressible | **UNKNOWN** (no claim) |
| PS-3 | D4/D7 role isolation assurance | Per-role toolFilter + instance; verified by ISO-LIVE-001..007 | Negative test: inherited composition | `test_negative_path_isolation.py` | Phase-3 closure | Role toolFilter enforced; child not inheriting parent's broader tools | D4/D7 composition exception reversible | **READY** |

## 13. Prompt-injection

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| PI-1 | External content → data, not instructions | ADR 0001 correction 8; no DSH-native guardrail verified | None (no claim) | None | ADR 0001 UNKNOWN #1 | No claim of prompt-injection protection | UNKNOWN until independently verified | **UNKNOWN** |

## 14. Resilience

| # | Requirement | Existing control | Phase-5 hardening | Test | Evidence | Acceptance criterion | Residual | Status |
|---|---|---|---|---|---|---|---|---|
| RS-1 | Child timeout | `DelegationClient._settle` watchdog; `DelegationTimeout` | Resilience test proving timeout → recovery | `test_resilience_timeout_abort.py` | runtime implementation | Timeout → DelegationTimeout → typed exception | None | **HARDENED** |
| RS-2 | Child abort | `DelegationClient._settle` signal; `DelegationAborted` | Resilience test proving abort → recovery | `test_resilience_timeout_abort.py` | runtime implementation | Abort → DelegationAborted → typed exception | None | **HARDENED** |
| RS-3 | Provider 429 | Phase-3 INT-12 observed 429; `classify_failure` → `environment` | Resilience test: 429 → environment-class failure → recovery | `test_resilience_timeout_abort.py` | Phase-3 closure | 429 → environment classification; no blind retry | None | **HARDENED** |
| RS-4 | Malformed result | `TaskResultCollector` validates schema; `MalformedResult` | Resilience test: malformed → fail-closed | `test_flow_failures.py` | runtime implementation | Malformed → typed exception | None | **HARDENED** |
| RS-5 | Stale state | `RuntimeStore.check_current`; `StaleStateDetected` | Resilience test: stale state → fail-closed | `test_flow_failures.py` | runtime implementation | Stale → BLOCKED; no mutation | None | **HARDENED** |
| RS-6 | Duplicate execution attempt | `ExecutionEngine` `_executed` flag; recovery prevents double-execute | Resilience test: duplicate after COMPLETE → refused | `test_flow_failures.py` | runtime implementation | Second execute after COMPLETE → raises | None | **HARDENED** |
| RS-7 | Partial result | `collect_all` propagates first failure; no partial success | Resilience test: mixed batch → first failure | `test_flow_failures.py` | D3 INT-12 | Partial → SubtaskFailed; no partial COMPLETE | None | **HARDENED** |
| RS-8 | Shutdown/cancel behavior | `signal` in `DelegationClient`; `interrupt_agent` | Resilience test: cancellation → clean abort | `test_flow_failures.py` | runtime implementation | Cancel → DelegationAborted; no orphan | None | **HARDENED** |

---

## Summary by status

| Status | Rows |
|---|---|
| **READY** | AD-1, AD-2, AD-3, AD-4, AD-5, AD-6, RI-2, RI-3, RI-4, PP-3, PP-4, ST-1, ST-2, ST-4, ST-5, EG-1, EG-2, EG-3, EG-4, VF-1, VF-2, VF-3, PE-1, PE-2, PE-3, PE-4, PE-5, PE-6, OV-1, OV-2, OV-3, OV-4, OV-5, L3-2, L3-5, L3-6, PS-3 |
| **READY_WITH_CONDITIONS** | L3-1 (separate UID), L3-3 (signed plan) |
| **HARDENED** | AD-7, RI-1, RI-5, PP-1, PP-2, ST-3, AI-1, AI-2, AI-3, AI-4, AI-5, AI-6, AI-7, RC-1, RC-2, RC-3, RC-4, RC-5, RC-6, L3-0, PS-1, RS-1, RS-2, RS-3, RS-4, RS-5, RS-6, RS-7, RS-8 |
| **BLOCKED** | VF-4 (independent verifier), L3-4 (signed plan process) |
| **UNKNOWN** | PS-2, PI-1 |
| **DEFERRED** | (none — all Phase-5 work scoped) |

**Roll-up**: 37 rows READY, 2 READY_WITH_CONDITIONS, 29 HARDENED (Phase-5 work), 2 BLOCKED (independent verifier, signed-plan process), 2 UNKNOWN (per-session sandbox limitations, prompt-injection). The hardened rows represent the Phase-5 test and extension deliverables.

---

*Status: MATRIX. Analysis only. No Phase-6 implementation, no L3 claim, no DSH/core/profile/preset/session-policy change. No code modified.*
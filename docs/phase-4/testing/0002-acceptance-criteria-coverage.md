# Phase 4 Acceptance Criteria Coverage — Test Mapping

- **Milestone**: Phase 4 / Session E — Integration Testing
- **Status**: MAPPED (deterministic-runtime coverage; no live-DSH or L3 claim)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Source**: Phase-4 acceptance matrix (`docs/phase-4/0001-acceptance-matrix.md`) reconciled per `0002-acceptance-baseline-reconciliation.md`
- **Scope**: `tests/phase4_integration/` (this suite) + `docs/phase-4/testing/` (this document)

---

## Legend

| Label | Meaning |
|---|---|
| **READY** | Capability is asserted by one or more executable tests in this suite at the deterministic-runtime level. |
| **READY_WITH_CONDITIONS** | Asserted in the deterministic runtime; the condition is named (e.g. "live-DSH variant not exercised"). |
| **BLOCKED** | Cannot be tested in the current session/environment (independent verifier / L3 / Human approval pending). |
| **DEFERRED** | Intentionally out of Phase-4 scope. |

---

## 1. Real DSH execution (RDE rows)

RDE rows require the mounted D4/D7 composition (`RDE-1`) and are **BLOCKED** in this suite. No test in `tests/phase4_integration/` fabricates live-DSH evidence.

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| RDE-1 | Mount 7 role `tool-subagent` instances | N/A (requires Human approval + DSH restart) | **BLOCKED** |
| RDE-2 | Real DSH specialist execution | Tested via `FakeSubagentBackend` / stub runners in P4I-01, P4I-03, P4I-04 | **READY_WITH_CONDITIONS** (deterministic only) |
| RDE-3 | Structured TaskResult capture | Asserted in P4I-01 (result collected with evidence/role/status) | **READY** (deterministic) |
| RDE-4 | Runtime session/run provenance | Asserted in P4I-06 (run_id preserved, derived=False) | **READY** (deterministic) |

## 2. Autonomous bounded Execution Flow (AEF rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **AEF-1** | Full lifecycle COMPLETE | P4I-01: ProductionRun → COMPLETE, all gates ALLOW, verification PASSED, file written, audit recorded | **READY** |
| **AEF-2** | Autonomy bounded: fail-closed on denial | P4I-02: revocation → DENY, no mutation; scope mismatch → DENY, no mutation; no delegation → ESCALATED, no file | **READY** |
| **AEF-3** | Minimum specialist set (no blanket fan-out) | P4I-01: engineering → [cto]; P4I-03: pricing → [cfo, kai]; P4I-07: parameterised routing assertion | **READY** |
| **AEF-4** | Bounded rework/decision loops (no blind retry) | P4I-04: identical-cause retry refused (ProductionDenied, "no blind retry"); recovery with new cause → COMPLETE | **READY** |

## 3. Verification (VER rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **VER-1** | Expected-vs-actual verification before COMPLETE | P4I-01: verification PASSED, COMPLETE only after verified; P4I-07: explicit verification-before-COMPLETE gate check | **READY** |
| **VER-2** | Independent verification for HIGH categories | N/A (independent verifier not built) | **BLOCKED** |
| **VER-3** | Evidence kind sufficiency per action category | P4I-01: verification detail includes required_evidence [test, build]; P4I-07: evidence kind check | **READY** |

## 4. Recovery (REC rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **REC-1** | Full recovery lifecycle (STOP→PRESERVE→DIAGNOSE→ROLLBACK→REPLAN→RECHECK→COMPLETE) | P4I-04: execution failure → recovery → recover(cause=..., failure_class=...) → COMPLETE | **READY** (deterministic) |
| **REC-2** | No blind retry; bounded attempts | P4I-04: identical-cause retry refused; empty-cause retry refused | **READY** |
| **REC-3** | Recovery re-checks authority (no privilege expansion) | P4I-04: recovery uses same authority gate; P4I-07: authority re-check assertion | **READY** |

## 5. Parallel execution (PAR rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **PAR-1** | Independent subtasks run concurrently | P4I-03: cfo+kai parallel, safe=True, mode="parallel", results 2, batch order preserved | **READY** (deterministic) |
| **PAR-2** | Parallel safety (dependency independence, exclusive ownership, read-only scope) | P4I-03: assert_parallel_safe checked; duplicate task ids refused; write scope refused; P4I-07: explicit safety assertion | **READY** |
| **PAR-3** | Concurrent state-version control (stale CAS DENY) | P4I-03: version preserved across parallel batch; P4I-07: stale version check | **READY** |

## 6. Audit / provenance (AUD rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **AUD-1** | Append-only project audit with integrity | P4I-01: audit events recorded (21+ classes); P4I-06: ledger integrity checks (strict_ok, chain_ok); **P4I-08: all-unique event ids, verify_append_only + verify_chain on a real ProductionRun ledger** | **READY** |
| **AUD-2** | Runtime provenance preserved per delegation | P4I-06: run_id == state.run_id (derived=False), role identity in tasks, delegation_id in delegations, evidence refs, parallel batch records; **P4I-08: single-run observability reconstruction with no rejected events after the event-id fix** | **READY** |
| **AUD-3** | Audit is never authority (AUTH-INV-14) | P4I-05: report is DATA (no authority key); P4I-06: audit_is_authority_source == False; P4I-07: explicit assertion | **READY** |

## 7. Authority enforcement (AUTH rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **AUTH-1** | Execution-time authority re-check mandatory | P4I-02: revocation between plan and execute → DENY, no mutation; P4I-07: explicit re-check assertion | **READY** |
| **AUTH-2** | Revoked/expired delegation DENY at execution | P4I-02: `MemoryDelegationProvider.revoke()` → ProductionDenied, no file, audit `execution_denial` | **READY** |
| **AUTH-3** | Delegation registry single-writer + protected-path gate | P4I-07: execution gate denies write to protected path (state/registry/); P4I-01: write to agents/cto/ succeeds (sanctioned path) | **READY** (L1 gate) |

## 8. Production boundaries (PB rows)

| # | Objective | Deterministic coverage | Status |
|---|---|---|---|
| **PB-1** | Session policy stays workspace-write + ask (fail-closed) | P4I-07: execution gate denies protected-path write (fail-closed baseline); PB-1 DSH-level policy is asserted from the runtime context snapshot | **READY** |
| **PB-2** | No DSH core/profile/preset modification | N/A (discipline enforced by "write-only" scope of this session) | **READY** (discipline) |
| **PB-3** | Out-of-process backends out of scope | N/A (deferred by design) | **DEFERRED** |
| **PB-4** | Protected production paths via sanctioned channels | P4I-07: registry_write scoped to state/registry/, audit_append scoped to audit/ | **READY** (L1) |

## 9. L3 prerequisites (L3 rows — all BLOCKED)

| # | Objective | Status |
|---|---|---|
| L3-0 | No L3 claim (honesty boundary) | **READY** (discipline; this suite makes no L3 claim) |
| L3-1 | Independent verifier + oracle | **BLOCKED** |
| L3-2 | Real-DSH session for L3 | **BLOCKED** |
| L3-3 | L2-LIVE evidence bundles validated | **READY** (existing `tests/evidence/` covers this) |
| L3-4 | L3 evidence bundle schema + fixtures | **BLOCKED** (needs L3-1) |

---

## 10. Summary

| Status | Rows covered |
|---|---|
| **READY** (deterministic) | AEF-1, AEF-2, AEF-3, AEF-4, VER-1, VER-3, REC-1, REC-2, REC-3, PAR-1, PAR-2, PAR-3, AUD-1, AUD-2, AUD-3, AUTH-1, AUTH-2, AUTH-3(L1), PB-1, PB-2(discipline), PB-4(L1), L3-0 |
| **READY_WITH_CONDITIONS** | RDE-2, RDE-3, RDE-4, PAR-1(live) |
| **BLOCKED** | RDE-1, VER-2, L3-1, L3-2, L3-4 |
| **DEFERRED** | PB-3 |

---

## 11. Audit event-id defect closure (Phase 4 / Targeted)

**Confirmed integration defect (CLOSED)**: `ProductionRun` and `ExecutionFlow` each created their own `RuntimeAudit` instance writing to the same ledger with independent event-id counters → duplicate `event-000001..` ids.

**Production change (smallest safe)**: `orchestrator/runtime/audit.py` — one authoritative per-ledger event-id allocator (absolute-path key, seeded from the ledger's max `event-<n>` id, advanced under a per-ledger reentrant lock held across allocation AND append). Consequential fix: `observability/ingest.py` — a nested `flow_started`/`flow_finished` inside an open `production_run` is treated as mid-run (the production run wraps the flow lifecycle).

**Impact on this matrix**:
- AUD-1 / AUD-2 rows are strengthened: a real ledger now has all-unique ids, passes `verify_append_only` + `verify_chain`, correlates to a SINGLE run, and produces a healthy observability report (zero rejects, zero problems). Asserted in P4I-06 and P4I-08.
- Fail-closed duplicate detection is NOT weakened: a deliberately injected duplicate is still flagged by `verify_append_only` and rejected by observability as `DUPLICATE_EVENT` (asserted in P4I-08).
- **No L3 claim, no DSH change.** The change is covered by `tests/phase4_integration/test_08_audit_id_uniqueness.py` and the full regression.

---

*Status: MAPPED. Production change limited to the audit event-id allocator (`orchestrator/runtime/audit.py`) and the consequential nested-flow correlation fix (`observability/ingest.py`). No DSH change. No L3 claim.*
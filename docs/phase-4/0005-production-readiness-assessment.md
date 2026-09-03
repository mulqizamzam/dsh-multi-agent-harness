# Phase 4 — Production Readiness Assessment

- **Milestone**: Phase 4 / Session H — CONSOLIDATED STATUS SNAPSHOT
- **Status**: ASSESSMENT (analysis only; **no implementation, no DSH change, no profile/preset/session-policy change, no code change**)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `docs/phase-4/0005-production-readiness-assessment.md` (this file). Read-only synthesis of all existing Phase-0–4 documentation, Phase-3 runtime-closure evidence, security specs, and operational specs.
- **Inputs**: `docs/phase-4/0001-acceptance-matrix.md` · `0002-acceptance-baseline-reconciliation.md` · `0003-approval-readiness.md` · `0004-real-dsh-bridge-plan.md` · `scenarios/` · `docs/phase-3/0001-live-int11-int12-evidence.md` · `0002-phase3-runtime-closure.md` · `docs/security/0001–0007` · `docs/testing/0001–0003` · `docs/operations/0001-observability.md` · `docs/operations.md` · `docs/architecture.md` · `docs/authority.md` · `docs/runbooks/` · `audit/runtime/INT-{01,07,11,12}/` evidence bundles · integration test results (1,142 passed, 14 skipped).
- **Classification**: CONSOLIDATED STATUS — every claim is traced to a specific evidence source or acknowledged gap. No claim is inferred from the existence of Phase-3 evidence alone.

---

## Table of Contents

1. [What is already production-capable](#1-what-is-already-production-capable)
2. [What is still deterministic-only](#2-what-is-still-deterministic-only)
3. [What is real-DSH proven](#3-what-is-real-dsh-proven)
4. [What is still conditional](#4-what-is-still-conditional)
5. [Security residual](#5-security-residual)
6. [Operational residual](#6-operational-residual)
7. [Exact Phase-4 acceptance gaps](#7-exact-phase-4-acceptance-gaps)
8. [Summary matrix](#8-summary-matrix)

---

## 1. What is already production-capable

The following components are **fully implemented, tested, and evidence-backed** at the deterministic-runtime level. They require **no further development** to be production-ready, though SDLC gates (code review, integration testing, security sign-off) remain.

### 1.1 Execution Flow (deterministic runtime)

| Capability | Evidence | Status |
|---|---|---|
| Full 17-phase lifecycle: INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE → EXECUTE_SUBTASKS → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE → ADVERSARIAL_REVIEW → AUTHORITY_GATE → EXECUTE → VERIFY → CLOSE | `orchestrator/runtime/flow.py`; D2 INT-01 COMPLETE with all gates ALLOW, verification PASSED, file written | **READY** |
| Fail-closed gate denial: any gate DENY stops the flow, no partial execution, no continuation past denial | D2 INT-07 BLOCKED, `execution_denial` audited, no unauthorized mutation | **READY** |
| Minimum specialist routing (no blanket fan-out) | `orchestrator/foundation/routing.py` tested; D2 INT-01 selected `["cto"]` only | **READY** |
| Recovery lifecycle: STOP → PRESERVE → DIAGNOSE → ROLLBACK → VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK | `control/recovery.py`; REC-001..006; INT-12 recovery entry | **READY** (deterministic) |
| No-blind-retry enforcement + bounded rework budget | REC-001; INT-12 refused empty-cause and identical-cause retries | **READY** |
| Verification before COMPLETE: expected-vs-actual matching, evidence kind sufficiency | D2 INT-01 verification PASSED; VERIFY-001..003 | **READY** |
| Parallel safety: dependency independence, exclusive single-owner, read-only specialist scope, held version CAS | `orchestrator/runtime/parallel.py`; INT-11 `assert_parallel_safe` PASSED, version 1→1 | **READY** |
| Concurrent state-version control: stale CAS DENY, no uncontrolled writes | INT-08; `test_08_parallel.py` | **READY** |
| Delegation registry single-writer + protected-path execution gate (ADR 0002) | `control/execution_gate.py` (`SANCTIONED_ROOTS`); REG-001..005 | **READY** (L1/L2 config-level) |

### 1.2 Authority enforcement

| Capability | Evidence | Status |
|---|---|---|
| Execution-time authority re-check (mandatory, not just planning) | D2 INT-07: revocation between plan and execute → `execution_denial`, BLOCKED, no mutation | **READY** |
| Revoked/expired/scope-changed delegation DENY at execution | INT-02, INT-07; `test_02_authority.py` | **READY** |
| No model text as authority; no state/audit as authority; BadSector PASS ≠ authorization | QA R10; `test_audit_hardening.py`; AUTH-INV-01/14/18 | **READY** |
| No subdelegation (DENY BY DEFAULT) | DLG-003; INT-12 `specialist_subdelegation_denied: true` | **READY** |
| Approval-dependent tasks: `_check_approval` gate, `approval-<id>` reference, fail-closed DENY on missing reference | `control/authority.py`; AUTH-INV-10 | **READY** (code-level; answerer availability is operational) |

### 1.3 Audit & provenance

| Capability | Evidence | Status |
|---|---|---|
| Append-only project audit ledger with hash-chain integrity | `audit/helpers/append_log.py`, `integrity.py`; `RuntimeAudit`; D2 INT-01/07 audit logs (18/16 event classes) | **READY** |
| Runtime provenance: role identity, delegation id, run id, session, stop reason | `DelegationProvenance`; `orchestrator/dsh/provenance.py`; real run IDs from Phase-3 closure | **READY** |
| Audit is never authority (AUTH-INV-14) | `audit_is_authority_source` always False; QA R10 | **READY** |

### 1.4 RBAC & configuration

| Capability | Evidence | Status |
|---|---|---|
| Agent registry (7 specialists + orchestrator) | `config/agents.yaml` (finalized, schema-validated) | **READY** |
| Capability×agent permission matrix | `config/permissions.yaml` (finalized, schema-validated) | **READY** |
| Role→DSH preset/toolFilter mapping | `config/role-preset-mapping.yaml` (finalized, validated) | **READY** |
| Tool-subagent instance definitions (7 roles) | `config/tool-subagent-instances.yaml` (finalized, validated) | **READY** |
| JSON Schema for delegation, project-state, audit-event, role-definition, role-mapping, agent-registry | `schemas/` (draft 2020-12, validated) | **READY** |

### 1.5 Observability

| Capability | Evidence | Status |
|---|---|---|
| Read-side projection from the existing audit ledger | `observability/` package; tests pass | **READY** |
| Event correlation: run_id, task_id, delegation_id, gate decisions, execution, verification, recovery, provenance | `observability/ingest.py`, `vocab.py` | **READY** |
| Metrics: totals, denials, recovery, failures, parallelism, latency, integrity | `observability/metrics.py` | **READY** |
| Operational queries: run lookup, task lookup, failure lookup, timeline, health report | `observability/queries.py` | **READY** |
| Fail-closed rules: malformed correlation rejected, never fabricate ids, duplicate rejected, ordering violation flagged | `observability/model.py`; tests | **READY** |

### 1.6 L3 verification infrastructure

| Capability | Evidence | Status |
|---|---|---|
| Reference/oracle implementations (O1) for 8 gates | `tests/l3_reference/` (authority, execution_gate, delegation, role, recovery, verification, transition, audit_chain) | **READY** |
| Separate-process verifier (P2) with clean-import enforcement | `tests/l3_runner/verifier.py`; `assert_clean_imports()` | **READY** |
| Independence checklist (IO-1..IO-10) | `tests/l3_runner/independence.py` | **READY** |
| Evidence bundle collector (E1..E13) | `tests/l3_runner/collector.py` | **READY** |
| Preflight checks (PF-UID-*, PF-VER-*, PF-ENV-*, PF-PLAN-*, PF-REP-*) | `tests/l3_runner/preflight.py`; 41 tests pass | **READY** |
| Replay/reproducibility metadata (P4) | `tests/l3_runner/replay.py`; `replay.sh` | **READY** |
| Structure-only validator (LV1..LV20, O2) | `tests/l3_runner/validator.py` | **READY** |
| 71 L3 scenario specifications + 11 schemas + per-INT fixtures | `docs/design/0002`; `docs/testing/0003`; `tests/l3_reference/schemas/`; fixtures | **READY** |

### 1.7 Executable bounded scenarios (deterministic runtime)

| Capability | Evidence | Status |
|---|---|---|
| 10 executable bounded scenarios (SCN-101..110) against the deterministic runtime | `tests/scenarios/test_executable_scenarios.py` (55 tests) | **READY** |
| Scenario specifications for all 10 (preconditions, objective, expected state/gates/execution/verification/failure, evidence requirements) | `docs/phase-4/scenarios/SCN-101..110` | **READY** |

### 1.8 Test suite

| Capability | Evidence | Status |
|---|---|---|
| 1,142 passing tests, 14 skipped (expected Phase-2C blocked) | Phase-3 closure regression green | **READY** |
| 75 live_dsh contract tests | `tests/live_dsh/` (contract, discovery, role adapters, structured capture, timeout/abort, failure propagation, cleanup, evidence) | **READY** |
| 4 INT scenario evidence bundles (QA-validated) | `audit/runtime/INT-{01,07,11,12}/` | **READY** |

---

## 2. What is still deterministic-only

The following items work correctly in the **in-process deterministic runtime** (`FakeSubagentBackend`) but have **not been proven** with a live DSH bridge. They are not production-capable until live-DSH evidence exists.

### 2.1 Execution flow

| Item | Deterministic evidence | Live-DSH gap | Blocker |
|---|---|---|---|
| `ExecutionFlow._get_client()` backend selection | FakeSubagentBackend always | The `RealDSHBackend` selection logic is not wired into production `ExecutionFlow.__init__`; Phase-3 closure used manual injection | `0004-real-dsh-bridge-plan.md` §2.1 — requires 3 code changes (backend selection, RealDSHBackend import, bridge injection point) |
| Full recovery lifecycle through COMPLETE | REC-001..006; INT-12 entered recovery (PRESERVED) | INT-12 entered recovery but did not complete the cycle → COMPLETE; live recovery→COMPLETE not exercised | Requires `RealDSHBackend` + recovery→COMPLETE scenario |
| Independent verification (VER-2) | Not implemented | No independent verifier exists; L3-1 infrastructure is spec+fixtures only | `BLOCKED` — needs L3 verifier build + separate UID |
| DSH-layer hard isolation for bash-wielding roles | L1 gate (`control/execution_gate.py` path-aware) | ADR 0002 residual: bash toolFilter is config-level, not DSH-level hard isolation | Phase-5 hardening |

### 2.2 Security testing

| Item | Deterministic evidence | Live-DSH gap | Blocker |
|---|---|---|---|
| ISO-LIVE-006: registry-write live denial | REG-001..005 pass | Has never run against a live DSH session with mounted `subagent_<id>` instances | `BLOCKED` — requires D4/D7 mount |
| L3 evidence bundles | 71 scenario specs, 11 schemas, fixtures, infrastructure | No L3 bundle produced; all rehearsal only (`l3_claim=false`) | `BLOCKED` — requires separate UID, Human-signed plan, live DSH session |
| L3 reference oracles against real runtime | 41 infrastructure tests pass | Oracles only tested against recorded fixtures, never against a live `ExecutionFlow` | `BLOCKED` — requires L3 runner with live driver |

### 2.3 Scenario coverage

| Item | Deterministic evidence | Live-DSH gap | Blocker |
|---|---|---|---|
| SCN-101 (authority denial) live variant | Deterministic: BLOCKED/ESCALATED | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-103 (BadSector rework) live variant | Deterministic: BLOCKED at adversarial_review | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-104 (evidence failure) live variant | Deterministic: BLOCKED/ESCALATED | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-105 (conflict escalation) live variant | Deterministic: ESCALATED/synthesized | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-106 (execution failure) live variant | Deterministic: RECOVERING→COMPLETE | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-107 (recovery failure) live variant | Deterministic: FAILED, no further recovery | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-108 (stale state) live variant | Deterministic: BLOCKED, `version_conflict` | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-109 (audit integrity) live variant | Deterministic: `AuditIntegrityError` | Live-DSH variant named BLOCKED | Needs RDE-1 mount |
| SCN-110 (successful workflow) live variant | Deterministic: COMPLETE, all gates ALLOW | Live-DSH variant named BLOCKED | Needs RDE-1 mount |

---

## 3. What is real-DSH proven

The following items have been **proven with a live DSH bridge** (`RealDSHBackend` + mounted D4/D7 `subagent_<id>` instances) during Phase-3 closure. These are **L2-LIVE** evidence level — runtime-observed with real DSH children, but not independently verified (L3).

### 3.1 Full lifecycle (INT-01)

| Element | Evidence |
|---|---|
| Live DSH child dispatch | `subagent_cto` run `30446fa4-e80f-444b-9fb1-f650fbb9fb21` |
| Structured TaskResult capture | `status: SUCCEEDED`, `confidence: HIGH`, schema-valid, real structured output |
| Provenance with real run ID | `role=cto, run_id=30446fa4, tool_name=subagent_cto, stop_reason=completed, source=RUNTIME-OBSERVED` |
| Execution gate ALLOW | `execution.decision=ALLOW`, target file written, artifact hash recorded |
| Verification PASSED | `verification.verdict=PASSED` (CONTROL-PLANE-DECISION) |
| COMPLETE | `outcome=COMPLETE`, `final_state=COMPLETE`, `version=1→7` |
| QA-validated bundle | `audit/runtime/INT-01/` — `valid=true`, full audit trail (18+ event classes) |

### 3.2 Execution-time authority re-check (INT-07)

| Element | Evidence |
|---|---|
| Valid authority at planning | `gate_authority` ALLOW at planning time |
| Revocation before execution | Sanctioned registry write between planning and execute |
| Execution-time re-check DENY | `execution_denial` audit event; `authority.decision=DENY` (AUTH-INV-06) |
| No unauthorized mutation | `provenance.children=[]`; target artifact hash unchanged; no output file |
| BLOCKED final status | `outcome=BLOCKED` (not COMPLETE) |
| Live child under planning authority | `subagent_cto` run `94d12d42-3f97-4730-9361-637d449a7dcf` executed analysis |
| QA-validated bundle | `audit/runtime/INT-07/` — `valid=true` |

### 3.3 Parallel collection (INT-11)

| Element | Evidence |
|---|---|
| 3 concurrent live children | cfo (`45124e03`), kai (`97518df6`), nova (`8b3c8603`) — all dispatched at 19:02:13Z, overlapping settle windows |
| Distinct roles, real run IDs | All 3 run IDs unique, all roles distinct, all `stop_reason=completed` |
| `assert_parallel_safe` PASSED | `safe: true`, `reason: "independent, single-owner, read-only subtasks"` |
| Version preserved | `held_version=1`, `post_batch_version=1` |
| COMPLETE | `outcome=COMPLETE`, `results=3` |
| QA-validated bundle | `audit/runtime/INT-11/` — `valid=true` |

### 3.4 Failure propagation (INT-12)

| Element | Evidence |
|---|---|
| Live child forced FAILED | `kai` run `61d68c1c` returned structured `FAILED` |
| Deterministic failure propagation | `SubtaskFailed` (role `kai`, task `int12-fail`, `failure_class=logic`); first-failure-in-batch-order |
| No partial success | `results=0`, `outcome=FAILED` (not COMPLETE) |
| Recovery entry | `RecoveryController` entered, `recovery_state=PRESERVED` |
| No blind retry | Empty-cause and identical-cause retries refused |
| No authority expansion | Child scope ⊆ parent; subdelegation denied; authority keys stripped |
| QA-validated bundle | `audit/runtime/INT-12/` — `valid=true` |

### 3.5 D4/D7 composition (proven, not persistent)

| Element | Evidence |
|---|---|
| All 7 `subagent_<id>` instances resolved | Zeko, CTO, CFO, Kai, Somad, BadSector, Nova — all `probe_backend_kind() == real-dsh` |
| Role presets mounted | Under `$DSH_HOME/.agent-presets/` per the 0003/0004/0005 change requests |
| Bridge marker active | `DSH_LIVE_BRIDGE_ACTIVE=1` set during Phase-3 closure |
| `RealDSHBackend` proven | 234-line implementation, bridge contract, 75 tests passed |
| Provenance with real identities | Real DSH run IDs, session IDs, stop reasons across all 4 INT scenarios |

### 3.6 Integration test suite (live-DSH)

| Suite | Result |
|---|---|
| `tests/live_dsh/` (75 contract tests) | ALL PASSED |
| `tests/evidence/` (36 QA validator tests) | ALL PASSED |
| `tests/orchestrator/dsh/` + `tests/orchestrator/execution/` (197 tests) | ALL PASSED |
| `tests/orchestrator/runtime/` (75 tests) | ALL PASSED |
| Broader regression (759 tests) | ALL PASSED (14 skipped: expected Phase-2C blocked) |
| **Total** | **1,142 passed** |

---

## 4. What is still conditional

The following items work **only under named conditions** that are not guaranteed in the current environment. Removing the condition requires specific prerequisites.

### 4.1 D4/D7 mount persistence

**Condition**: The D4/D7 composition (role presets, `subagent_<id>` instances) must be mounted and verified **per session**. The Phase-3 closure proved the mount works, but it is not persistent across sessions.

**Current state**: `DSH_LIVE_BRIDGE_ACTIVE=1` is **not set** in this session. No live DSH children can be dispatched without re-mounting.

**Resolution**: Automate the mount + marker verification in the session bootstrap, or document the manual re-verification procedure.

### 4.2 Approval answerer availability

**Condition**: Interactive Human approval requires a live approval answerer. The current session has `approval/policy=ask` but **approval prompts are disabled** (`docs/phase-4/0003-approval-readiness.md` §1). The `ask` policy resolves `unavailable` → fail-closed DENY + escalate.

**Current state**: HIGH-risk execution (destructive, financial_transfer, sensitive_publication, credential_change) is **blocked** in this session. Approval-dependent tasks without a pre-recorded `approval-<id>` reference are also blocked.

**Resolution**: Enable approval prompts + configure a live Human answerer, or pre-record signed `approval-<id>` references for all approval-dependent actions.

### 4.3 Live-DSH backend injection

**Condition**: The `ExecutionFlow._get_client()` method hardcodes `FakeSubagentBackend` (line 221 of `orchestrator/runtime/flow.py`). The Phase-3 closure used manual injection via the `subtask_runner` parameter. The production wiring does not exist.

**Current state**: `RealDSHBackend` is importable from `tests/live_dsh/real_backend.py` (a test-support module), not from the production namespace. The live dispatch bridge injection is not automated.

**Resolution**: Implement the 3-item plan in `0004-real-dsh-bridge-plan.md` §3: (1) backend selection in `_get_client()`, (2) move/expose `RealDSHBackend` in the production `orchestrator.dsh` namespace, (3) durable bridge injection mechanism.

### 4.4 Provider rate-limit stability

**Condition**: Live DSH dispatch depends on the shared model provider being available. HTTP 429 (rate limit) was observed during Phase-3 live runs.

**Current state**: Classified as an **environment-class** failure, not a control failure. The runtime handled it correctly (no blind retry, new dispatch after diagnosed cause cleared). However, it imposes a practical limitation on live parallel execution.

**Resolution**: Provider-side rate-limit management (retry scheduling, backoff, dedicated capacity) or documented operational procedure for rate-limit recovery.

### 4.5 Per-role spawn acceptance

**Condition**: The `cto` role's `subagent_cto` instance was proven to accept the persona, toolFilter, and maxDepth. The other 6 roles (zeko, cfo, kai, somad, badsector, nova) are **assumed uniform** but not verified.

**Current state**: `config/role-preset-mapping.yaml` and `config/tool-subagent-instances.yaml` define the same structure for all 7 roles. The `tests/live_dsh/discovery.py` resolution probes all 7, but structured TaskResult capture was only verified for `cto`.

**Resolution**: Run INT-01-style live lifecycle for each of the remaining 6 roles, or run a single multi-role batch that exercises all 7.

### 4.6 Session policy baseline

**Condition**: The project baseline is `workspace-write` + `ask`. The current session uses this baseline, but there is **no automated enforcement** that it stays this way. A drift to `danger-full-access` + `never` would violate PB-1.

**Current state**: Verified at session start. No monitoring.

**Resolution**: Pre-flight check (`PF-ENV-2`-style) at the start of every consequential session, or automated session-policy assertion.

---

## 5. Security residual

Security residual = known security limitations that are **not addressed** by the current implementation. These are accepted design decisions, deferred items, or acknowledged gaps.

### 5.1 No L3 claim for any control

**All controls are at L2-LIVE or lower.** No evidence bundle satisfies P1–P4 (separate process, separate UID, Human-signed plan, reproducibility). The independent verification infrastructure exists (`tests/l3_runner/`, `tests/l3_reference/`) but has never been used for a live L3 run. The `LiveDSHRuntimeDriver` is a `NotImplementedError` stub.

**Source**: `docs/security/0006-l3-implementation-report.md` §9; `docs/security/0007-l3-run-prerequisites.md` §1.2; `docs/phase-4/0001-acceptance-matrix.md` L3-0.

### 5.2 No prompt-injection security claim

**Prompt injection is an acknowledged UNKNOWN** (ADR 0001 UNKNOWN #1). The system's external-content trust posture (subagent output = data, not instructions) is policy, not DSH-enforced isolation. No tests, gates, or evidence address prompt injection.

**Source**: `docs/phase-4/0001-acceptance-matrix.md` §13; `docs/phase-3/0002-phase3-runtime-closure.md` UNKNOWN section.

### 5.3 DSH-layer hard isolation for bash-wielding roles

**The `toolFilter` is a capability boundary, not complete security isolation** (`docs/operations.md` §7). The execution gate's path-aware protection (`control/execution_gate.py`) is code-level L1; DSH-layer hard isolation (sandbox-level denial of write access to protected paths) is a Phase-5 item (ADR 0002 residual).

**Source**: `docs/phase-4/0001-acceptance-matrix.md` AUTH-3, PB-4; `docs/operations.md` §7.

### 5.4 Same-UID sandbox prevents L3

**The verifier and orchestrator run under the same host UID.** IO-2 (`verifier_uid ≠ orchestrator_uid`) fails, so `l3_claim_possible=False` in this sandbox. The infrastructure never fakes a credential separation it did not achieve.

**Source**: `docs/security/0007-l3-run-prerequisites.md` §1.2; `docs/security/0006-l3-implementation-report.md` §3.

### 5.5 Model judgment is not authority — but it is an attack surface

**Code-enforced invariant**: model text, audit entries, and state documents are never authority. However, the model's ability to influence tool selection, prompt construction, and delegation routing is a known attack surface (PRD §12). The current defense is: (1) `assert_no_authority_in_payload` strips authority-shaped keys, (2) delegation scope is bounded by the registry, (3) gate decisions are CONTROL-PLANE-DECISION. No agent can escalate its own authority.

**Source**: `docs/authority.md`; `docs/security/0002-threat-model-and-control-architecture.md`.

### 5.6 External content from subagents is data

**Subagent output is treated as untrusted data** — it is collected into `TaskResult`, validated against schema, but never used as authority or instructions. This is enforced by code, but the DSH layer does not provide content-level isolation between subagent sessions.

**Source**: `docs/security/0003-external-content-verification-spec.md`; `docs/phase-4/scenarios/README.md`.

### 5.7 No new tools enabled; known attack surface contained

**`web_fetch` is disabled.** Agent Teams are not enabled. No out-of-process backends exist. The available tool set is the DSH baseline + the 7 `subagent_<id>` instances. This is the containment boundary.

**Source**: `docs/phase-3/0002-phase3-runtime-closure.md` SECURITY CLAIM STATUS; `docs/operations.md` §7.

### 5.8 Security invariants that ARE runtime-proven

These are **positive** security properties that have been demonstrated:

| Invariant | Evidence |
|---|---|
| No model text as authority (AUTH-INV-01) | D2 INT-01/07 evidence items sourced CONTROL-PLANE-DECISION / RUNTIME-OBSERVED / AGENT-REPORTED, never authority |
| No state/audit as authority (AUTH-INV-14) | `audit_is_authority_source` always False; QA R10 |
| BadSector PASS ≠ authorization (AUTH-INV-18) | PASS-without-delegation rejected |
| No subdelegation (DLG-003) | INT-12 `specialist_subdelegation_denied: true` |
| Execution-time authority re-check mandatory (AUTH-INV-05/06) | INT-07 proves revocation → execution DENY |
| COMPLETE only after verification (AUTH-INV-15) | INT-01 verification PASSED; INT-12 not COMPLETE on failure |
| No blind retry (AUTH-INV-16) | INT-12: empty-cause and identical-cause refused |
| No scope expansion (AUTH-INV-04) | INT-12: child scope ⊆ parent |
| Protected-path write DENY (ADR 0002) | REG-001..005; PATH tests |
| No unauthorized mutation after execution DENY | INT-07: target artifact hash unchanged |

---

## 6. Operational residual

Operational residual = known gaps in the **operational readiness** of the system — processes, automation, monitoring, and infrastructure that are not yet in place.

### 6.1 No production-wired live-DSH backend

**The `ExecutionFlow` default path uses `FakeSubagentBackend`.** The `RealDSHBackend` selection logic, bridge injection, and production namespace exposure are not implemented. Production deployment requires the 3 changes specified in `0004-real-dsh-bridge-plan.md` §3.

**Impact**: Every live-DSH dispatch today requires manual injection. No automated production flow can use the real bridge.

### 6.2 D4/D7 mount not automated

**The D4/D7 composition (role presets, `subagent_<id>` instances) must be mounted manually per session.** The mount procedure is documented in change requests 0003–0005 but requires Human approval, file copy to `$DSH_HOME/.agent-presets/`, `cordis.patch.yml` modification, DSH restart, and `DSH_LIVE_BRIDGE_ACTIVE=1` setting.

**Impact**: No session can use live-DSH dispatch without the manual mount procedure. The bridge marker is not set in the current session.

### 6.3 Approval answerer unavailable

**Approval prompts are disabled in this session.** The `ask` policy resolves `unavailable` → fail-closed DENY. Any HIGH-risk action (destructive, financial, credential, publication) is blocked.

**Impact**: Interactive Human approval is not possible. Approval-dependent scenarios are blocked. L3 Human-signed plans cannot be generated.

### 6.4 No automated CI/CD for live-DSH regression

**The 1,142-test suite passes, but there is no automated pipeline** that runs the live-DSH tests (`tests/live_dsh/`, `tests/live_evidence/`) against a freshly mounted D4/D7 composition. Regression testing is manual.

**Impact**: Live-DSH contract drift is not caught automatically. The 75 live_dsh tests require a mounted session to run.

### 6.5 No alerting, dashboard, or monitoring

**The observability layer is read-side only** — it reconstructs run timelines from the audit ledger but does not emit alerts, maintain a dashboard, or provide continuous monitoring. Operational visibility is query-based, not push-based.

**Impact**: Production incidents (failed runs, gate denials, recovery entries) are not automatically detected or notified.

### 6.6 Observer-level DSH profile constraints

**The current session uses the `web` profile with the `standard` agent preset** (the OMNI MCP client is added by the web profile patch). There is no dedicated DSH profile for production multi-agent harness runs. The environment fact that OMNI tools are present in the orchestrator session is acknowledged but not isolated.

**Impact**: The orchestrator session has tools (OMNI MCP) that the specialist roles do not. This is intentional (orchestrator is the coordinator, not a specialist) but adds to the attack surface.

### 6.7 No uptime/SLA, backup/restore, or credential rotation

**Defined**: State/registry/audit file layout, hash-chain integrity, CAS versioning.

**Not defined**: Uptime requirements, SLA, backup schedule, restore procedure, credential rotation for subagent personas, incident response runbook automation.

**Impact**: The system is functionally complete at the deterministic-runtime level but lacks the operational envelope for production SLAs.

### 6.8 Provider rate-limit exposure

**HTTP 429 was observed during Phase-3 live runs.** The runtime handled it correctly (no blind retry, new dispatch after diagnosed cause cleared), but there is no retry scheduling, backoff policy, or dedicated capacity.

**Impact**: Live parallel execution (3+ concurrent children) is at risk of provider rate-limiting. The runtime's correct handling of 429 does not prevent the user-facing delay.

### 6.9 `DSH_LIVE_BRIDGE_ACTIVE=1` marker convention is manual

**The bridge marker is a manual environment variable** set by the orchestrator session operator. It is not detected, asserted, or logged automatically. A missing marker causes `RealDSHBackend.start()` to raise `BridgeNotAvailable` — fail-closed, but the operator may not know why.

**Impact**: Debugging a missing-marker scenario requires operator knowledge of the marker convention. No automated diagnostics.

### 6.10 Recovery rollback not automated

**D4/D7 unmount (rollback) is documented but not automated.** The procedure: remove instance rows from `cordis.patch.yml`, remove presets, restart DSH. The marker disappears, and all subsequent `RealDSHBackend.start()` calls fail closed. No script or CI job automates this.

**Impact**: Rollback is manual, error-prone, and not tested.

---

## 7. Exact Phase-4 acceptance gaps

The following are the **exact gaps** that prevent Phase-4 from being considered complete. Each gap is traced to the acceptance matrix (`0001`), the reconciliation (`0002`), or the bridge plan (`0004`).

### 7.1 Gaps that block live-DSH production use

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G1 | **`_get_client()` backend selection not production-wired** — `ExecutionFlow` hardcodes `FakeSubagentBackend` | RDE-2, AEF-1(live), PAR-1(live) | Code | Implement the 3-item plan in `0004-real-dsh-bridge-plan.md` §3: backend selection, RealDSHBackend import, bridge injection |
| G2 | **D4/D7 mount not persistent across sessions** — must be re-verified per session | RDE-1, AEF-1(live), REC-1(live), PAR-1(live) | Operations | Automate mount + marker verification in session bootstrap, or document mandatory re-verification procedure |
| G3 | **Approval answerer unavailable** — approval prompts disabled; HIGH-risk execution blocked | PB-2, AUTH-3(live), L3-2 | Operations | Enable approval prompts + configure live Human answerer, or pre-record signed `approval-<id>` references |
| G4 | **Provider rate-limit exposure** — HTTP 429 observed; no retry scheduling or backoff | AEF-4(live), PAR-1(live) | Operations | Provider-side rate-limit management or documented operational procedure |

### 7.2 Gaps that block L3 / independent verification

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G5 | **Independent verifier not built** — `LiveDSHRuntimeDriver` is a `NotImplementedError` stub | VER-2, L3-1 | Code | Implement `LiveDSHRuntimeDriver` against a real DSH session; keep verifier as separate process with separate UID |
| G6 | **Same-UID sandbox prevents L3** — IO-2 fails; no L3 claim possible | L3-1, L3-2 | Infrastructure | Run verifier under a separate UID/credential (setuid, separate user, separate host) |
| G7 | **No Human-signed pre-runtime `plan.json`** — no signing mechanism, no durable Human identity | L3-1, L3-2 | Process | Define signing mechanism (how Human signs `plan.json`), durable signoff identity, pre-commit oracle process |
| G8 | **No L3 evidence bundle produced** — 71 scenario specs, schemas, fixtures exist but no executable L3 run | L3-1, L3-2, L3-4 | Execution | Authorize a live L3 run; generate committed `audit/l3/<scenario-id>/` bundles |

### 7.3 Gaps that block live isolation testing

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G9 | **ISO-LIVE-006 registry-write live denial never run** — requires D4/D7 mount | AUTH-3(live), PB-4(live) | Testing | Run against mounted D4/D7 composition |
| G10 | **DSH-layer hard isolation for bash-wielding roles not live** — ADR 0002 residual; Phase-5 hardening | AUTH-3, PB-4 | Code | DSH-level sandbox enforcement for bash tool path access |

### 7.4 Gaps in recovery lifecycle

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G11 | **Full recovery cycle through COMPLETE not exercised** — INT-12 entered recovery (PRESERVED) but did not complete the cycle | REC-1(live) | Testing | Run a recovery→COMPLETE scenario with live DSH backend |

### 7.5 Gaps in role coverage

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G12 | **Per-role spawn acceptance verified only for `cto`** — remaining 6 roles assumed uniform | RDE-3, AEF-1 | Testing | Run INT-01-style live lifecycle for each of zeko, cfo, kai, somad, badsector, nova |

### 7.6 Gaps in security posture

| # | Gap | Affected rows | Type | Resolution required |
|---|---|---|---|---|
| G13 | **Prompt-injection posture is UNKNOWN** — no claim made, no test, no gate | (ADR 0001 UNKNOWN #1) | Research | Security analysis of DSH subagent content-isolation capabilities; adversarial testing with prompt-injection payloads |

### 7.7 Summary of gap status

| Gap | Status | Dependency |
|---|---|---|
| G1: Backend selection not wired | **CODE** (plan exists: `0004-real-dsh-bridge-plan.md`) | None |
| G2: Mount not persistent | **OPERATIONS** | G1 resolved (mount is prerequisite) |
| G3: Approval answerer unavailable | **OPERATIONS** | None (environment decision) |
| G4: Provider rate-limit exposure | **OPERATIONS** | None (provider-side) |
| G5: Independent verifier not built | **CODE** (stub exists) | G6, G7 |
| G6: Same-UID sandbox | **INFRASTRUCTURE** | Separate host/UID provisioning |
| G7: No Human-signed plan mechanism | **PROCESS** | G3 (approval answerer) |
| G8: No L3 evidence bundle produced | **EXECUTION** | G5, G6, G7, G2 |
| G9: ISO-LIVE-006 never run | **TESTING** | G2 (mount) |
| G10: DSH-layer hard isolation not live | **CODE** (Phase-5) | None (deferred) |
| G11: Recovery→COMPLETE not exercised | **TESTING** | G1, G2 |
| G12: Only CTO role verified | **TESTING** | G1, G2 |
| G13: Prompt-injection UNKNOWN | **RESEARCH** | None (new work) |

---

## 8. Summary matrix

### 8.1 Status roll-up

| Category | Count | Notes |
|---|---|---|
| **Production-capable** (deterministic runtime, no further code needed) | ~25 capabilities | Execution flow, gates, authority, audit, observability, RBAC, L3 infra, 10 scenarios, 1,142 tests |
| **Deterministic-only** (works in-process; not live-DSH proven) | ~12 items | Backend selection, full recovery cycle, independent verification, 9 scenario live variants, L3 evidence |
| **Real-DSH proven** (L2-LIVE evidence exists) | 4 INT scenarios + 75 contract tests | INT-01/07/11/12 with real `subagent_<id>` dispatch, QA-validated bundles |
| **Conditional** (works only under named conditions) | 6 conditions | D4/D7 mount persistence, approval answerer, backend injection, rate-limit stability, per-role verification, session policy baseline |
| **Security residual** | 8 items | No L3 claim, no prompt-injection claim, no DSH-level hard isolation, same-UID sandbox, model-judgment attack surface, external-content-as-data, contained toolset, 8 proven invariants |
| **Operational residual** | 10 items | No production-wired backend, mount not automated, approval answerer unavailable, no CI/CD, no alerting, profile constraints, no SLA/backup, rate-limit exposure, manual marker, rollback not automated |
| **Exact acceptance gaps** | 13 gaps (G1–G13) | 2 code, 3 operations, 1 infrastructure, 1 process, 1 execution, 3 testing, 1 research |

### 8.2 Honesty statement

**Phase 4 is NOT ready for production deployment.** The deterministic runtime is proven, the real-DSH bridge is proven (L2-LIVE), and the L3 verification infrastructure exists. However, the following are **required** before production use:

1. **Wire the live-DSH backend into `ExecutionFlow`** (G1).
2. **Automate the D4/D7 mount across sessions** (G2).
3. **Restore the approval answerer path** for interactive and HIGH-risk actions (G3).
4. **Address the provider rate-limit exposure** for parallel live dispatch (G4).
5. **Build and run the independent L3 verifier** with separate UID and Human-signed plans (G5–G8).
6. **Run live isolation tests** (G9).
7. **Exercise the full recovery→COMPLETE cycle** (G11).
8. **Verify all 7 role spawn instances** (G12).
9. **Research the prompt-injection posture** (G13).

**No L3 claim is made.** All evidence is L2-LIVE at most. The majority of the deterministic-runtime capabilities are production-capable artifacts; the live-DSH production path is the core remaining gap.

---

*Status: CONSOLIDATED ASSESSMENT. No implementation, no DSH core/profile/preset/session-policy change, no code change. All claims traced to existing evidence sources.*
# Requirements Traceability — Multi-Agent Control Plane

- **Status**: proposal (Phase 2 / Session E)
- **Date**: 2026-08-30
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/`. This document traces every PRD requirement through Phase-1 foundation, Phase-2 implementation target, control, test, acceptance criterion, and evidence. It does **not** modify production code, redesign architecture, or invent requirements.
- **Companion to**: `PRD_Multi_Agent_DeepSeek_Harness_v1.0.md` · `docs/adr/0001-multi-agent-control-plane-boundary.md` · `docs/adr/0002-registry-protection-mechanism.md` · `docs/security/0001-control-assurance-spec.md` · `docs/security/0002-threat-model-and-control-architecture.md` · `docs/design/0001-control-design-and-test-plan.md` · `docs/phase-1/0001-phase-1-implementation-spec.md`

---

## Status vocabulary

| Label | Meaning |
|---|---|
| **ALREADY IMPLEMENTED** | Delivered in Phase 1 (foundation or skeleton) or Phase 2 earlier sessions at time of writing. |
| **PHASE-2 TARGET** | Identified in the Phase-2 parallel session briefs (Sessions A–D) as a production implementation target. May be mid-flight. |
| **DEFERRED** | Intentionally postponed to a later phase (Phase 3–6) per the project roadmap. |
| **UNKNOWN** | Not yet verifiable in the current environment; no security claim made. |
| **BLOCKED** | Cannot be completed or verified in the current environment without a prerequisite change (e.g. DSH composition exception, feature unmounted). |

---

## 1. Architecture & Role Definition

### PRD §4 — Canonical Architecture

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Human is ultimate authority | ADR 0001 accepted; HUMAN_APPROVED decisions D1–D7. `docs/authority.md` documents the authority model. | No Phase-2 change. Human authority is a design invariant, not a code module. | AUTH-INV-01 (no text-based authority); AUTH-INV-05 (execution-time re-check). | AUTH-008 (model text ≠ authority); AUTH-003 (expired delegation); AUTH-004 (revoked). | Human authority is never overridden by model text, delegation, or state. | Audit record of DENY on text-only authority claim. | ALREADY IMPLEMENTED |
| 1.2 | Orchestrator coordinates; it does not own every domain | `orchestrator/AGENT.md` defines orchestrator role. `orchestrator/contract.md` §1 defines identity. `orchestrator/foundation/contracts.py` defines role vocabulary. | `control/authority.py` (Session A) enforces orchestrator cannot execute outside delegated scope. | AUTH-INV-18 (orchestrator cannot execute what it cannot delegate). | AUTH-002 (scope expansion denied); ORC-001/002/003. | Orchestrator action outside delegation → DENY. | Audit `authority_denied` on scope violation. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (authority enforcement) |
| 1.3 | Seven specialists are peers; no specialist manages another | `config/agents.yaml` lists 7 specialists + orchestrator. `AGENTS.md` §1 declares peer relationship. | `orchestrator/foundation/gates.py` `ControlPlane` gate registry enforces no hierarchy. | AUTH-INV-19 (subagent capability ≤ role boundary). | ISO-001..007 (per-role isolation). | No specialist has implicit manager authority over another. | ToolFilter schema + capability matrix. | ALREADY IMPLEMENTED |
| 1.4 | BadSector is independent; does not authorize; does not execute | `agents/badsector/AGENT.md` and `policy.yaml` define review-only role. `config/permissions.yaml` maps BadSector as no-execute. | `control/badsector.py` (Session B) implements provenanced review verdict handling. | INV-03 (PASS ≠ authorization); AUTH-INV-09. | AUTH-007 (PASS without delegation); BAD-001 (forged PASS); BAD-004 (failure → fail-closed). | BadSector PASS never produces execution; forged PASS denied. | Audit record preventing PASS-as-authority. | ALREADY IMPLEMENTED (role definition); PHASE-2 TARGET (production gate) |
| 1.5 | Orchestrator is not an eighth specialist | `orchestrator/AGENT.md` kind=coordination. `orchestrator/contract.md` §1. `orchestrator/foundation/contracts.py` `ORCHESTRATOR` ≠ `SPECIALIST_ROLES`. | No Phase-2 change. Semantic invariant maintained by contracts. | Invariant check: orchestrator not in SPECIALIST_ROLES. | `tests/validate-config.py` `test_specialist_count` (7 specialists, not 8). | orchestrator excluded from specialist set. | Config validation pass. | ALREADY IMPLEMENTED |

### PRD §5 — Agent Specifications

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 1.6 | Each specialist has a defined role, allowed/restricted actions, and boundary | `agents/<id>/AGENT.md` + `policy.yaml` per role (7 specialists + orchestrator). `config/permissions.yaml` capability×agent matrix. | `control/authority.py` (Session A) enforces action scope at execution time. | AUTH-INV-11 (target must match authorized target). | ISO-001..007; AUTH-005 (action outside scope). | Each role's tool set and action scope is defined and enforced. | Role definition files + capability matrix. | ALREADY IMPLEMENTED |
| 1.7 | CFO no-transaction default | `config/permissions.yaml` maps `financial_transaction: NO` for CFO. `tests/validate-config.py` checks CFO no-transaction invariant. | `control/authority.py` (Session A) and `control/risk.py` (Session B) enforce. | AUTH-INV-10 (HIGH non-downgradable). | RISK-003 (financial commitment denied). | CFO cannot execute financial transaction without explicit delegation. | RISK-003 test pass. | ALREADY IMPLEMENTED |
| 1.8 | BadSector output schema (verdict, risks, assumptions, etc.) | `agents/badsector/AGENT.md` defines output schema. `docs/security/0002-threat-model-and-control-architecture.md` §15 defines BadSector contract. | `control/badsector.py` (Session B) implements `BadSectorGate` with provenance verification. | AUTH-INV-09; THREAT-014/015. | BAD-001 (provenance); BAD-002 (mandatory skip); BAD-003 (PASS ≠ authority). | BadSector verdict schema is enforced; PASS provenance verified. | BadSector output audit record. | ALREADY IMPLEMENTED (schema); PHASE-2 TARGET (production gate) |

---

## 2. Authority Model

### PRD §6 — Authority Model

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 2.1 | Capability / Permission / Authority separation | `docs/authority.md` defines the three concepts. `config/permissions.yaml` is capability matrix (control-plane input, not native DSH authorization). ADR 0001 Decision 1 codifies two-tier model. | `control/authority.py` and `control/delegation.py` (Session A) implement the three-tier enforcement. | AUTH-INV-01 (capability ≠ authority). | AUTH-001..008. | Capability is tool-level; permission is role-level; authority is delegation-level. All three enforced at different layers. | Config validation + authority gate audit. | ALREADY IMPLEMENTED (design); PHASE-2 TARGET (production enforcement) |
| 2.2 | Delegation is scoped, project-bound, operation-bound, time-bound, auditable | `schemas/delegation.schema.json` defines delegation schema. `orchestrator/foundation/contracts.py` `Delegation` dataclass validates. `state/registry/` is protected registry path. | `control/authority.py` and `control/delegation.py` (Session A) implement scope validation, expiry, revocation, CAS versioning. | AUTH-INV-02/04/05/06/13. | AUTH-002 (scope); AUTH-003 (expiry); AUTH-004 (revocation); DLG-001 (single-writer). | Delegation must be scoped, validated, expire/revoked enforced, auditable. | Delegation registry + audit events. | ALREADY IMPLEMENTED (schema, contract, registry); PHASE-2 TARGET (production enforcement) |
| 2.3 | No self-escalation | `config/permissions.yaml` maps no self-mutation paths. ADR 0001 Decision 1. ADR 0002 registry protection. | `control/authority.py` (Session A) `assert_no_self_escalation`. | AUTH-INV-03 (no subagent increases own authority). | AUTH-001 (self-grant attempt). | Any self-escalation attempt → DENY. | Audit `authority_denied` on self-grant. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 2.4 | Subdelegation policy (V1: DENY BY DEFAULT) | `orchestrator/contract.md` §4.5: "Subdelegation: DENY BY DEFAULT (V1)". `docs/security/0002-threat-model-and-control-architecture.md` §6.3. | `control/authority.py` (Session A) `assert_subdelegation_denied`. | AUTH-INV-04 (child scope ⊆ parent). | DLG-003 (subdelegation attempt → DENY). | Specialist cannot subdelegate. | Audit of DENY on subdelegation attempt. | ALREADY IMPLEMENTED (contract); PHASE-2 TARGET (production enforcement) |
| 2.5 | Model text is never authority | `orchestrator/foundation/gates.py` `AuthorityGate` consumes structured `Delegation` objects only. `orchestrator/foundation/contracts.py` `Delegation` is the only authority record. | `control/authority.py` (Session A) enforces same in production gate. | AUTH-INV-01 (no text-based authority). | AUTH-008 (model text claims → DENY). | Authority gate never accepts prose as grant. | Audit `authority_denied` on text-only claim. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |

---

## 3. Workflow / State Machine

### PRD §7 — Core Workflow (State Machine)

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Intake exists | `orchestrator/foundation/contracts.py` `TaskIntake` dataclass. `orchestrator/foundation/state.py` `StateMachine` with `DRAFT`→`PLANNED` transition. | `orchestrator/foundation/state.py` `StateMachine` (Phase 1D) already implements transitions. Production intake module is Phase 3+. | INV-09 (COMPLETE needs verification). | ST-001..003. | Intake creates a DRAFT task with objective, scope, constraints. | State record. | ALREADY IMPLEMENTED (foundation); DEFERRED (production intake → Phase 3) |
| 3.2 | Risk gate exists | `orchestrator/foundation/gates.py` `RiskGate` (declarative). `orchestrator/foundation/contracts.py` `Task.risk_metadata`. | `control/risk.py` (Session B) implements deterministic risk classifier with intrinsic HIGH non-downgradable. | AUTH-INV-10 (HIGH non-downgradable). | RISK-001..005. | Risk classification is deterministic; intrinsic HIGH cannot be downgraded by model judgment. | Risk classification record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production classifier) |
| 3.3 | Agent selection is task-dependent; minimum specialist set | `orchestrator/foundation/contracts.py` `DOMAIN_ROLE` mapping. `orchestrator/contract.md` §6 routing policy. | `orchestrator/foundation/routing.py` (Phase 1D) implements domain routing. Production routing is Phase 3+. | PRD §4 (no blanket fan-out). | `tests/validate-config.py` (7 specialists, not 8). | Orchestrator routes to minimum specialist set. | Task routing audit. | ALREADY IMPLEMENTED (foundation); DEFERRED (production routing → Phase 3) |
| 3.4 | Independent tasks can run in parallel | `orchestrator/workflows/skeleton.js` has `parallel()` phase. `orchestrator/foundation/workflow.py` `WorkflowRun`. | Production parallel execution is Phase 3+. | PRD §7.6 (independent tasks may run in parallel). | `tests/workflow/test_skeleton.py` (structural shape). | Parallel tasks run concurrently where independent. | Workflow execution record. | ALREADY IMPLEMENTED (skeleton); DEFERRED (production execution → Phase 3) |
| 3.5 | Evidence gate exists | `orchestrator/foundation/gates.py` `EvidenceGate` (ladder: exists → relevant → supports → current → uncontradicted → sufficient). | `control/evidence.py` (Session B) implements production evidence gate. | AUTH-INV-17 (evidence ≠ authority). | EVID-001..004. | Evidence gate classifies sources; unsupported claims rejected. | Evidence gate record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 3.6 | Conflict resolution exists (no voting) | `orchestrator/foundation/gates.py` `ConflictGate` (detect → evidence → rework → synthesize → escalate). | `control/conflict.py` (Session B) implements production conflict gate. | PRD §7.11 (no voting). | CONF-001..003. | Conflicts surfaced, not voted; minority risks preserved. | Conflict gate record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 3.7 | BadSector review is conditional | `orchestrator/foundation/gates.py` `BadSectorReviewGate` (mandatory triggers: HIGH risk, intrinsic-HIGH actions, explicit review_required). | `control/badsector.py` (Session B) implements production review gate with provenance. | THREAT-014/015 (forged PASS, mandatory skip). | BAD-001..004. | Mandatory triggers cannot be skipped; PASS provenance verified. | Review gate record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 3.8 | Authority gate exists | `orchestrator/foundation/gates.py` `AuthorityGate` (structured records only). | `control/authority.py` (Session A) implements production authority gate. | AUTH-INV-01/05/09/13/14. | AUTH-001..008. | Authority gate denies on missing/invalid delegation; consumes structured records only. | Authority gate audit. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 3.9 | Verification is mandatory before COMPLETE | `orchestrator/foundation/gates.py` `VerificationGate` (COMPLETE requires evidence). | `control/verification.py` (Session C) implements production verification gate. | INV-09 (COMPLETE needs verification). | VERIFY-001..003. | COMPLETE not emitted without verification evidence. | Verification gate record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |
| 3.10 | Recovery path exists | `orchestrator/foundation/gates.py` `RecoveryGate` (no blind retry, max_attempts). `state/helpers/recovery.py` `RecoveryRecord`. | `control/recovery.py` (Session C) implements production recovery path. | INV-10 (no blind retry); AUTH-INV-12/16. | REC-001..005. | Recovery follows STOP→PRESERVE→DIAGNOSE→ROLLBACK→VERIFY→REPLAN→AUTH RE-CHECK. | Recovery record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gate) |

### PRD §17 — Phase-6 Scenarios

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 3.11 | 10 scenario skeletons exist | `tests/scenarios/` contains 10 PRD §17 scenarios as pytest.mark.skip skeletons. | `tests/integration/` (Session D) adds integration test skeletons. | PRD §17. | `tests/scenarios/` listed in test strategy. | Scenarios defined as test skeletons; executed in Phase 6. | Scenario skeleton files. | ALREADY IMPLEMENTED (skeletons); PHASE-2 TARGET (integration skeletons) |

---

## 4. Permission Matrix

### PRD §8 — Baseline Permission Matrix

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 4.1 | Per-role capability matrix | `config/permissions.yaml` defines capability×agent matrix. `docs/tool-catalog.md` documents scoped tool set. | `control/authority.py` (Session A) enforces capability at execution time. | AUTH-INV-19 (capability ≤ role). | ISO-001..007; TOOL-001..005. | Each role's capability set matches the matrix. | ToolFilter + capability matrix. | ALREADY IMPLEMENTED |
| 4.2 | Role→preset/toolFilter mapping | `config/role-preset-mapping.yaml` defines mapping. `config/tool-subagent-instances.yaml` declares per-role instances. | Mapping is complete; mounting is a controlled DSH composition exception (HUMAN_PENDING per ADR 0001 Decision 4/7). | ADR 0001 Decision 4. | `tests/validate-config.py` validates mapping. | Mapping is defined, validated, and mountable. | Config validation pass. | ALREADY IMPLEMENTED (mapping); HUMAN_PENDING (mounting) |
| 4.3 | Zeko: ops read + scoped write; no code architecture change without scope | `agents/zeko/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter + authority gate. | INV-08 (capability boundary). | ISO-007 (Zeko architecture change). | Zeko cannot modify architecture without code scope. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.4 | CTO: code read/write, tests; no financial capability | `agents/cto/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter + authority gate. | INV-08. | ISO-001 (CTO cannot access CFO capability). | CTO cannot execute financial actions. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.5 | CFO: financial analysis; no code write; no transaction by default | `agents/cfo/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter + authority gate. | INV-08. | ISO-002 (CFO cannot write code); RISK-003. | CFO cannot write code or execute transactions without delegation. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.6 | Kai: research/read-only; no project file write unless explicitly allowed | `agents/kai/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter. | INV-08. | ISO-003 (Kai cannot write). | Kai cannot write project files without explicit grant. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.7 | Somad: social drafting; no infra/server write | `agents/somad/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter. | INV-08. | ISO-004 (Somad cannot deploy). | Somad cannot execute infrastructure actions. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.8 | Nova: writing; no infra execution | `agents/nova/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter. | INV-08. | ISO-005 (Nova cannot execute infra). | Nova cannot execute infrastructure actions. | Tool rejection. | ALREADY IMPLEMENTED |
| 4.9 | BadSector: review; no mutate/execute tools | `agents/badsector/AGENT.md` + `policy.yaml`. `config/permissions.yaml`. | Enforcement via toolFilter. | INV-08. | ISO-006 (BadSector cannot execute). | BadSector cannot execute reviewed action. | Tool rejection. | ALREADY IMPLEMENTED |

---

## 5. Security & Hardening

### PRD §12 — Security Requirements

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 5.1 | Default deny | ADR 0001 Decision 2 (workspace-write + ask). ADR 0002 (fail-closed on registry/audit paths). `control/execution_gate.py` (DENY on protected/malformed/outside targets). | `control/authority.py` (Session A) fails closed on missing/invalid delegation. | INV-05 (fail-closed); INV-15 (failed check stops action). | AUTH-006 (malformed delegation → DENY); XG-002 (ambiguous → DENY). | Any missing/invalid/ambiguous authority → DENY. | Audit `authority_denied`. | ALREADY IMPLEMENTED |
| 5.2 | Least privilege | `config/permissions.yaml` capability matrix. `config/role-preset-mapping.yaml` per-role toolFilter. `agents/<id>/policy.yaml` declarative. | Enforcement via toolFilter + authority gate. | INV-08. | ISO-001..007; TOOL-001..005. | Each role has minimum tools for its domain. | ToolFilter schema. | ALREADY IMPLEMENTED |
| 5.3 | No self-approval | `orchestrator/foundation/gates.py` `AuthorityGate` consumes structured records. `orchestrator/contract.md` §13 prohibitions. | `control/authority.py` (Session A) enforces. | AUTH-INV-01 (no text-based authority). | AUTH-001 (self-grant); AUTH-008 (text claim). | Agent cannot approve its own action. | Audit `authority_denied`. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) |
| 5.4 | No secret propagation unless required | `docs/authority.md` §3.3: "State files never contain secrets; audit entries reference secret-backed config." `orchestrator/contract.md` §8. | No Phase-2 change. Secret hygiene is a design principle, not a code module. | PRD §12. | `tests/validate-config.py` checks no secrets in config files. | No secrets in project state or audit files. | Config validation. | ALREADY IMPLEMENTED (principle); DEFERRED (secret management → Phase 5) |
| 5.5 | External content is data, not instructions | `docs/security/0001-control-assurance-spec.md` §12. `docs/security/0002-threat-model-and-control-architecture.md` §17. `docs/security/0003-external-content-verification-spec.md` (per-channel spec). | `tests/adversarial/test_external_content_injection.py` (Phase 1E+) implements INJ-101..107. | AUTH-INV-17 (external content ≠ authority). | INJ-001..007; INJ-101..107. | External content never alters authority, state, or triggers execution. | Ingestion/quarantine record. | ALREADY IMPLEMENTED (design, tests); DSH-UNKNOWN (no native guardrail claim) |
| 5.6 | Prompt injection: UNVERIFIED (no security claim) | `docs/security/0001-control-assurance-spec.md` §12: "prompt-injection handling is UNVERIFIED". `docs/security/0002-threat-model-and-control-architecture.md` §17: "Do NOT claim this problem is solved." | `tests/adversarial/` (Phase 1E+) provides reference-level tests; no DSH-native claim. | UNKNOWN (DSH-native). | INJ-001..007; INJ-101..107 (reference-level only). | No security claim until INJ-* pass on production control plane with code-enforced data/instruction separation. | Ingestion/quarantine record. | UNKNOWN (DSH-native); ALREADY IMPLEMENTED (L1-design, reference tests) |
| 5.7 | Destructive actions protected | `config/permissions.yaml` maps destructive actions as requiring approval. `control/execution_gate.py` protects paths. | `control/risk.py` (Session B) classifies destructive actions as intrinsic HIGH. `control/authority.py` (Session A) enforces approval requirement. | AUTH-INV-10 (non-downgradable). | RISK-002 (destructive w/o approval → DENY). | Destructive action requires valid authority + approval. | Risk + authority gate audit. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production gates) |
| 5.8 | Audit consequential actions | `audit/helpers/append_log.py` (append-only). `audit/helpers/integrity.py` (hash chain). `schemas/audit-event.schema.json`. | `audit/helpers/` (Phase 1B) already implements. DSH session log is separate. | AUTH-INV-14 (audit ≠ authority). | AUD-001..004. | Every consequential action generates an audit event. | Audit log. | ALREADY IMPLEMENTED |

### PRD §19 — Design Principles

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 5.9 | System fails closed on missing authorization | `control/execution_gate.py` (DENY on protected/malformed/outside). `orchestrator/foundation/gates.py` (DENY default). | `control/authority.py` (Session A) fails closed. | INV-15 (failed check stops action). | AUTH-006; XG-002. | Missing/invalid authorization → DENY, not ALLOW. | Audit `authority_denied`. | ALREADY IMPLEMENTED |
| 5.10 | Scope expansion requires new authority | `orchestrator/contract.md` §4.2. ADR 0001. | `control/authority.py` (Session A) `assert_no_scope_expansion`. | AUTH-INV-02/04 (scope containment). | AUTH-002 (scope expansion → DENY). | Scope expansion without new delegation → DENY. | Audit `authority_denied`. | ALREADY IMPLEMENTED (contract); PHASE-2 TARGET (production enforcement) |

---

## 6. Project State

### PRD §10 — Project State

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 6.1 | Project state schema exists | `schemas/project-state.schema.json` (draft 2020-12). `orchestrator/foundation/state.py` `StateMachine`. | `orchestrator/foundation/state.py` (Phase 1D) handles transitions. | AUTH-INV-07/08 (state ≠ authority). | PST-001..004; ST-001..003. | State is schema-validated, versioned, single-writer. | State file before/after hashes. | ALREADY IMPLEMENTED |
| 6.2 | State transitions are controlled | `state/helpers/atomic_write.py` (CAS + version). `state/helpers/version_check.py`. `orchestrator/foundation/state.py` `StateMachine.transition()`. | Phase 2 adds production state machine (Session A `control/delegation.py` uses CAS). | AUTH-INV-07/08. | ST-001 (model write `status:APPROVED` → DENY); ST-002 (stale CAS → DENY). | State can only change via controlled transition function. | State transition audit. | ALREADY IMPLEMENTED |
| 6.3 | Optimistic concurrency (versioned CAS) | `state/helpers/atomic_write.py` (compare-and-swap). `state/helpers/version_check.py` (monotonic version). | No Phase-2 change. | INV-15 (fail-closed). | PST-001 (parallel conflict → DENY). | CAS prevents stale overwrites. | Conflict audit. | ALREADY IMPLEMENTED |

---

## 7. Audit

### PRD §11 — Audit Log

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 7.1 | Audit event schema exists | `schemas/audit-event.schema.json` (draft 2020-12). `audit/helpers/append_log.py` validates events. | No Phase-2 change. | AUTH-INV-14 (audit ≠ authority). | AUD-001..004. | Audit events are schema-validated, append-only, hash-chained. | Audit log. | ALREADY IMPLEMENTED |
| 7.2 | Audit answers: who, what, target, authority, evidence, change, result | `schemas/audit-event.schema.json` fields: `actor`, `action`, `target`, `authority_source`, `evidence`, `previous_state`, `new_state`, `result`. | No Phase-2 change. | PRD §11. | AUD-001..004. | All 7 audit questions answerable from events. | Audit log. | ALREADY IMPLEMENTED |
| 7.3 | Audit is append-only; executors cannot edit | `audit/helpers/append_log.py` (append-only, no modification). `audit/helpers/integrity.py` (hash chain). | No Phase-2 change. | AUTH-INV-14. | AUD-001 (edit attempt → DENY). | Audit entries cannot be modified by executors. | Integrity chain. | ALREADY IMPLEMENTED |
| 7.4 | Audit entries are generated from runtime events, not agent prose | `audit/helpers/append_log.py`. `audit/helpers/integrity.py`. Agent prose tagged `agent_reported`. | No Phase-2 change. | AUTH-INV-14. | AUD-003 (prose vs runtime event). | Agent prose is never stored as runtime fact. | Audit tags. | ALREADY IMPLEMENTED |

---

## 8. Failure & Recovery

### PRD §13 — Failure Modes

| # | PRD requirement | Phase-1 foundation | Phase-2 target | Control | Test | Acceptance criterion | Evidence required | Status |
|---|---|---|---|---|---|---|---|---|
| 8.1 | No blind retry | `orchestrator/foundation/gates.py` `RecoveryGate` (max_attempts per cause). `state/helpers/recovery.py` `RecoveryRecord`. | `control/recovery.py` (Session C) implements production recovery. | INV-10 (no blind retry). | REC-001 (blind retry → DENY). | Retry requires diagnosed cause. | Recovery record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) |
| 8.2 | STOP → PRESERVE → DIAGNOSE → ROLLBACK → VERIFY → REPLAN → AUTHORITY RE-CHECK | `state/helpers/recovery.py` `RecoveryRecord` state machine. `orchestrator/foundation/state.py` `RECOVERING` state. | `control/recovery.py` (Session C) implements full recovery cycle. | AUTH-INV-12/16. | REC-002..005. | Recovery follows the documented protocol. | Recovery record. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) |
| 8.3 | Recovery does not acquire privilege automatically | `orchestrator/contract.md` §11. `docs/security/0002-threat-model-and-control-architecture.md` §16.3. | `control/recovery.py` (Session C) re-checks authority via same gate. | AUTH-INV-12. | REC-004 (privilege escalation → DENY). | Recovery uses same authority path. | Audit. | ALREADY IMPLEMENTED (contract); PHASE-2 TARGET (production) |
| 8.4 | Recovery detects obsolete state versions | `state/helpers/version_check.py`. `orchestrator/foundation/state.py` `StateMachine` version check. | `control/recovery.py` (Session C) version check. | AUTH-INV-12 (stale version → DENY). | REC-005 (stale version → DENY). | Recovery re-validates against current state version. | Recovery audit. | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) |

---

## 9. Phase-2 Control Plane Modules (Traceability Summary)

The following table traces the **Phase-2 parallel session outputs** (production control-plane modules) back to PRD requirements, security invariants, and tests.

### Session A — Authority + Delegation

| Module | PRD § | Invariants enforced | Tests | Acceptance criterion | Status |
|---|---|---|---|---|---|
| `control/authority.py` | §6, §7.13, §19 | AUTH-INV-01..08, 11, 13, 18, 20 | AUTH-001..008; L3-AUTH-001..004 | Authority gate consumes structured Delegation only; no text/state/PASS bypass; fail-closed | PHASE-2 TARGET (Session A) |
| `control/delegation.py` | §6, §19 | AUTH-INV-02/04/05/06; scope containment; expiry; revocation; CAS versioning | AUTH-003/004/006; DLG-001/003 | Delegation validated, scoped, versioned, single-writer | PHASE-2 TARGET (Session A) |

### Session B — Risk + Evidence + Conflict + BadSector

| Module | PRD § | Invariants enforced | Tests | Acceptance criterion | Status |
|---|---|---|---|---|---|
| `control/risk.py` | §7.4, §19 | AUTH-INV-10 (HIGH non-downgradable); THREAT-011/012 | RISK-001..005 | Intrinsic HIGH actions stay HIGH regardless of wording | ALREADY IMPLEMENTED (Session B) |
| `control/evidence.py` | §7.9, §19 | AUTH-INV-17 (evidence ≠ authority); evidence ladder | EVID-001..004 | Evidence gate distinguishes exists/supports/sufficient | ALREADY IMPLEMENTED (Session B) |
| `control/conflict.py` | §7.11, §19 | No voting; preserve minority risks; escalate when unresolved | CONF-001..003 | Conflicts surfaced, not silently resolved | ALREADY IMPLEMENTED (Session B) |
| `control/badsector.py` | §5.6, §7.12, §19 | AUTH-INV-09 (PASS ≠ authority); THREAT-014/015; provenance | BAD-001..004 | PASS provenance verified; mandatory review cannot be skipped | ALREADY IMPLEMENTED (Session B) |

### Session C — Verification + Recovery

| Module | PRD § | Invariants enforced | Tests | Acceptance criterion | Status |
|---|---|---|---|---|---|
| `control/verification.py` | §7.15, §19 | INV-09 (COMPLETE needs verification); VERIFY-001..003 | VERIFY-001..003 | COMPLETE only after verification evidence | PHASE-2 TARGET (Session C) |
| `control/recovery.py` | §7.16, §13, §19 | INV-10 (no blind retry); AUTH-INV-12/16 | REC-001..005 | Recovery follows protocol; re-checks authority; detects stale versions | PHASE-2 TARGET (Session C) |

### Session D — Integration Test Design

| Artifact | Coverage | Tests | Blocked on | Status |
|---|---|---|---|---|
| `tests/integration/` | 12 cross-module scenarios (authority→delegation→risk→execution, expired/revoked, PASS≠authority, etc.) | INT-001..012 | `control/authority.py`, `control/delegation.py`, `control/verification.py`, `control/recovery.py` (Session A, C) | PHASE-2 TARGET (Session D; partially blocked on A/C) |

### Session E — Requirements Traceability

| Artifact | Coverage | Status |
|---|---|---|
| `docs/phase-2/0001-requirements-traceability.md` (this file) | Full PRD→Phase-1→Phase-2→control→test→acceptance→evidence mapping | ALREADY IMPLEMENTED (this file) |

---

## 10. Phase-2 Runbooks (Traceability)

| Runbook | PRD § | Phase-1 foundation | Status |
|---|---|---|---|
| `docs/runbooks/01-authority-denial.md` | §13 (unauthorized action) | `control/execution_gate.py`; `orchestrator/foundation/gates.py` | ALREADY IMPLEMENTED |
| `docs/runbooks/02-expired-delegation.md` | §6 (delegation) | `orchestrator/foundation/contracts.py` `Delegation.is_expired()` | ALREADY IMPLEMENTED |
| `docs/runbooks/03-revoked-delegation.md` | §6 (delegation) | `orchestrator/foundation/contracts.py` `Delegation.status` | ALREADY IMPLEMENTED |
| `docs/runbooks/04-badsector-rework-reject.md` | §5.6, §7.12 | `orchestrator/foundation/gates.py` `BadSectorReviewGate` | ALREADY IMPLEMENTED |
| `docs/runbooks/05-evidence-failure.md` | §7.9 | `orchestrator/foundation/gates.py` `EvidenceGate` | ALREADY IMPLEMENTED |
| `docs/runbooks/06-conflict-escalation.md` | §7.11 | `orchestrator/foundation/gates.py` `ConflictGate` | ALREADY IMPLEMENTED |
| `docs/runbooks/07-execution-failure.md` | §7.14, §13 | `control/execution_gate.py`; `orchestrator/foundation/gates.py` `ExecutionGate` | ALREADY IMPLEMENTED |
| `docs/runbooks/08-recovery-failure.md` | §7.16, §13 | `state/helpers/recovery.py`; `orchestrator/foundation/gates.py` `RecoveryGate` | ALREADY IMPLEMENTED |
| `docs/runbooks/09-stale-state.md` | §10 (state) | `state/helpers/version_check.py` | ALREADY IMPLEMENTED |

---

## 11. Overall Status Summary

Status is reported per traced item in the tables above; a single item may carry more than one status (e.g. a foundation already implemented plus a Phase-2 production target). No aggregate pass-rate is asserted here — the status of each requirement must be read from its own row, not from a roll-up. High-level distribution by category:

| Category | Status mix (read per-row) |
|---|---|
| **Architecture & Roles** | 1.1–1.5: foundation implemented; 1.2, 1.4 add Phase-2 production enforcement |
| **Authority Model** | 2.1–2.5: design/contract implemented; all add Phase-2 production enforcement |
| **Workflow / State Machine** | 3.1–3.10: gate foundations implemented; risk/evidence/conflict/BadSector production modules Phase-2; intake/routing/parallel execution deferred to Phase 3+ |
| **Permission Matrix** | 4.1–4.9: implemented; 4.2 mounting HUMAN_PENDING (controlled DSH composition exception) |
| **Security & Hardening** | 5.1–5.10: mostly implemented; 5.5/5.6 prompt-injection UNKNOWN (DSH-native); 5.4 secret management deferred to Phase 5 |
| **Project State** | 6.1–6.3: implemented |
| **Audit** | 7.1–7.4: implemented |
| **Failure & Recovery** | 8.1–8.4: foundation implemented; production verification/recovery Phase-2 (Session C) |

### Key observations

1. **Phase-1 delivered a strong foundation**: 51 of 65 traced requirements have at least Phase-1 foundation artifacts (schema, contract, role definition, config, test skeleton, or documentation).

2. **Phase-2 Sessions A/B/C are mid-flight**: Session B (risk/evidence/conflict/badsector) is producing modules; Sessions A (authority/delegation) and C (verification/recovery) are in progress. Session D (integration tests) is partially blocked on A/C completion.

3. **Deferred items (4)**: production intake, production routing, production parallel execution, and secret management are explicitly deferred to Phase 3+.

4. **UNKNOWN (1)**: DSH-native prompt-injection handling remains UNVERIFIED. No security claim is made. The L1 control plane (quarantine, evidence gate, authority gate) is designed and tested at reference level, but DSH-native behavior is not verified.

5. **BLOCKED (1)**: Role→preset mounting (controlled DSH composition exception) is HUMAN_PENDING per ADR 0001 Decision 4/7. The mapping is defined and validated; mounting requires explicit Human approval.

6. **No L3 evidence exists**: All controls are at L1 (project control plane) or L2 (DSH-native toolFilter/sandbox). L3 (independent runtime verification) is defined in `docs/security/0003-l3-independent-verification-plan.md` and `docs/design/0002-l3-verification-specification.md` but not yet achieved.

---

## 12. PRD Acceptance Criteria Traceability

### PRD §15 — Architecture

| Criterion | Phase-1 status | Phase-2 status | Evidence |
|---|---|---|---|
| Seven agents separately identifiable | `config/agents.yaml`; `agents/<id>/AGENT.md` | No change needed | Config validation |
| Orchestrator distinct from 7 specialists | `orchestrator/AGENT.md` kind=coordination | No change needed | Role definition |
| Human remains ultimate authority | ADR 0001 accepted; $7 HUMAN_APPROVED | No change needed | ADR approval record |
| No specialist manages another | `AGENTS.md` §1; peer relationship | No change needed | Config invariants |
| BadSector independent from execution | `agents/badsector/policy.yaml` no-execute | `control/badsector.py` enforces | ToolFilter + gate |

### PRD §15 — Workflow

| Criterion | Phase-1 status | Phase-2 status | Evidence |
|---|---|---|---|
| Intake exists | `TaskIntake` contract | Phase 3+ (production) | Contract definition |
| Requirement ambiguity can halt workflow | `orchestrator/contract.md` §5 | Phase 3+ | Contract |
| Risk gate exists | `RiskGate` (foundation); `control/risk.py` (production) | ALREADY IMPLEMENTED | Gate module |
| Agent selection is task-dependent | `DOMAIN_ROLE` mapping; routing policy | Phase 3+ (production) | Contract |
| Independent tasks can parallel | `skeleton.js` parallel phase | Phase 3+ (production) | Skeleton |
| Evidence gate exists | `EvidenceGate` (foundation); `control/evidence.py` (production) | ALREADY IMPLEMENTED | Gate module |
| Conflict resolution exists | `ConflictGate` (foundation); `control/conflict.py` (production) | ALREADY IMPLEMENTED | Gate module |
| BadSector review is conditional | `BadSectorReviewGate` (foundation); `control/badsector.py` (production) | ALREADY IMPLEMENTED | Gate module |
| Authority gate exists | `AuthorityGate` (foundation); `control/authority.py` (Session A) | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) | Gate module |
| Verification mandatory before COMPLETE | `VerificationGate` (foundation); `control/verification.py` (Session C) | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) | Gate module |
| Recovery path exists | `RecoveryGate` (foundation); `control/recovery.py` (Session C) | ALREADY IMPLEMENTED (foundation); PHASE-2 TARGET (production) | Gate module + recovery helpers |

### PRD §15 — Governance

| Criterion | Phase-1 status | Phase-2 status | Evidence |
|---|---|---|---|
| Delegation is scoped | `Delegation` contract; `schemas/delegation.schema.json` | `control/delegation.py` (Session A) | Schema + gate |
| No self-escalation | ADR 0001; `orchestrator/contract.md` §13 | `control/authority.py` (Session A) | AUTH-001 |
| No self-approval | `orchestrator/foundation/gates.py` | `control/authority.py` (Session A) | AUTH-008 |
| High-impact actions have explicit approval | `orchestrator/contract.md` §4.3 | `control/risk.py` + `control/authority.py` | RISK-001..004 |
| Audit trail records consequential actions | `audit/helpers/append_log.py`; `schemas/audit-event.schema.json` | No change needed | Integrity chain |

### PRD §15 — Security

| Criterion | Phase-1 status | Phase-2 status | Evidence |
|---|---|---|---|
| Least privilege | `config/permissions.yaml`; per-role toolFilter | Enforcement via authority gate | ToolFilter + gate |
| Context isolation | `orchestrator/foundation/context.py` | Phase 5 (hardening) | Module |
| Secret isolation | `docs/authority.md` §3.3; design principle | Phase 5 (hardening) | Design doc |
| External content as untrusted data | `docs/security/0003-external-content-verification-spec.md`; INJ-* tests | No DSH-native claim | Reference tests |
| Destructive actions protected | `config/permissions.yaml`; `control/execution_gate.py` | `control/risk.py` + `control/authority.py` | RISK-002; AUTH-005 |

---

## 13. UNKNOWN and BLOCKED Items

| # | Item | Status | Reason | Resolution path |
|---|---|---|---|---|
| U1 | DSH-native prompt-injection handling | UNKNOWN | Whether DSH treats external content as non-authoritative data has not been verified. No security claim is made. | Run INJ-* tests on production control plane; verify DSH-native behavior; document + version-pin. |
| U2 | `web_fetch` availability | UNKNOWN | Disabled in standard preset. Whether Kai research needs it is unknown. | Requires a separate ADR to enable; currently out of scope. |
| B1 | Role→preset mounting (controlled DSH composition exception) | BLOCKED (HUMAN_PENDING) | `config/role-preset-mapping.yaml` defines mapping; mounting is a controlled DSH composition exception per ADR 0001 Decision 4/7. | Human approval required; must be reversible (patch/record). |
| B2 | DSH `storage` hub | BLOCKED | Not mounted in base/web profile. | Not required for Phase-1/2; file-based state is the current approach. |
| B3 | Agent Teams / out-of-process subagent backends | BLOCKED (out of scope) | Not mounted; disabled by default. | Not required for V1. |

---

*Status: proposal. This document traces every PRD requirement through Phase-1 foundation, Phase-2 implementation target, control, test, acceptance criterion, and evidence. It does not modify production code, redesign architecture, or invent requirements. The Phase-2 parallel sessions (A–D) are mid-flight at time of writing; this document reflects the state as of 2026-08-30 23:33 UTC.*
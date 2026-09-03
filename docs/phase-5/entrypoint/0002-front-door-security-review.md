# Front-Door Security Review — Requirements → Implementation Mapping

- **Status**: implemented (Phase 5 / Session A)
- **Scope**: `orchestrator/entrypoint/` only. No existing production module was
  modified.
- **Method**: every security requirement in the Phase-5 front-door brief is
  mapped to a concrete implementation point and, where feasible, a verified
  behavior. This review is a mapping, not a new audit ledger or authority
  mechanism.

## 1. Security requirements → implementation

| # | Requirement | Implementation | Verified |
|---|---|---|---|
| 1 | objective = DATA (never authority) | `FrontDoorRequest.objective` is passed as data into `ProductionRun.run()`; the front door never interprets it as an authority record | ✓ smoke (shape + happy path) |
| 2 | Never create Delegation | `resolve_delegation` only calls `provider.current()` (read-only). No `create_delegation`, no `issue_child_delegation`, no registry write | ✓ code audit |
| 3 | Never set ACTIVE | `resolve_delegation` checks `delegation.status != "ACTIVE"` → `NoValidDelegation`; it never assigns status | ✓ smoke (REVOKED → BLOCKED) |
| 4 | Never fabricate approval | No `approval_reference` parameter exists on the front door; the runtime's own `NeedsApproval` escalation is preserved | ✓ code audit |
| 5 | Never derive authority from prose | `delegation_id` is validated against `^delegation-[A-Za-z0-9-]+$`; the Delegation comes only from the provider | ✓ smoke (prose id → ERROR) |
| 6 | Never call ExecutionFlow directly | The front door imports only `ProductionRun`; the flow is reached exclusively via `ProductionRun.run()` | ✓ code audit |
| 7 | Never call raw DSH tools | The front door imports no `orchestrator.dsh` client and calls no DSH tool | ✓ code audit |
| 8 | Never bypass ProductionRun | `run_front_door`'s only execution path is `ProductionRun.run()` | ✓ code audit |
| 9 | Preserve existing gates | The full 17-phase runtime chain runs inside `ProductionRun`; no gate is skipped | ✓ smoke (evidence-gate ESCALATE observed) |
| 10 | Intrinsic HIGH cannot be downgraded | No `declared_risk` input; `control.risk.RiskClassifier` stays authoritative (AUTH-INV-10) | ✓ code audit |
| 11 | Scope remains authority-contained | Delegation matched by exact id + project; `ProductionRun` re-runs the authority gate at execution time (AUTH-INV-05/06/11) | ✓ smoke (id mismatch → BLOCKED) |
| 12 | No new authority mechanism | The front door introduces no new grants, gates, or authority sources | ✓ code audit |

## 2. Anti-authority invariants preserved (AUTH-INV-*)

| Invariant | Where preserved |
|---|---|
| AUTH-INV-01 (no authority from text) | `delegation_id` pattern check; provider-resolved Delegation only |
| AUTH-INV-05 (validated at execution) | Delegation passed to `ProductionRun` → runtime authority gate re-checks at execution time |
| AUTH-INV-06 (expiry/revocation at execution) | Front-door fail-closed pre-check + runtime execution-time re-check |
| AUTH-INV-07/08 (state not authority) | Front door never reads state files as authority; only the provider's structured Delegation |
| AUTH-INV-09 (BadSector PASS ≠ authorization) | No review acceptance on the front door; runtime BadSector gate untouched |
| AUTH-INV-10 (HIGH not downgradable) | No risk override accepted |
| AUTH-INV-11 (target ∈ authorization) | Runtime authority gate + execution gate re-validate target containment |
| AUTH-INV-13 (messages not authority) | `FrontDoorRequest` fields are data; authority comes only from the registry |
| AUTH-INV-14 (audit not authority) | Envelope `audit_ids` are reported data, never consumed as authority |
| AUTH-INV-15 (COMPLETE requires verification) | `COMPLETE` is emitted only when `ProductionRun` returns `outcome == "complete"` with a generated report |
| AUTH-INV-20 (failed check stops action) | Any validation/resolution failure → BLOCKED / ERROR / ESCALATED; never partial allow |

## 3. Gate-preservation evidence

The smoke runs exercised the real runtime gate chain:

- Evidence gate: a MEDIUM write action with no evidence produced
  `ESCALATED` at `evidence_gate (EVID-001)` — proving the gate still runs
  (the front door did not disable it).
- Authority gate: revoked / expired / mismatched delegations were rejected
  **before** the run started (fail-closed front-door check), and the runtime
  re-checks again at execution time.
- Risk gate: the write objective was classified MEDIUM deterministically; the
  front door accepted no override.

## 4. Terminal-status mapping

| Status | Meaning | Trigger (front door) | CLI exit |
|---|---|---|---|
| `COMPLETE` | Full bounded run succeeded | `ProductionRun` returned `outcome == "complete"` + report | 0 |
| `BLOCKED` | Fail-closed denial | No valid delegation / id mismatch / not ACTIVE / revoked / expired / gate DENY | 2 |
| `ESCALATED` | Needs Human attention | `ProductionEscalated` (e.g. approval required, evidence-gate escalation) | 3 |
| `ERROR` | Front-door failure | Shape validation failure / unexpected exception / invalid JSON input | 1 |

## 5. Non-implemented (brief scope limits)

Per the brief: no idempotency store, no new web server, no new DSH tool, no
new audit ledger, no new authority semantics, no session-policy change, no
role/toolFilter change, no O3, no L3. All are absent from
`orchestrator/entrypoint/`.

## 6. Residual note (honest boundary)

The front door is an L1 project-layer entry point. It does not claim to be an
L3 independently-verified security boundary; it inherits the security posture
of the existing `ProductionRun` runtime and the DSH session sandbox/approval
policy that the runtime executes under.

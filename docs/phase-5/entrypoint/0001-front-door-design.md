# Front-Door V1 — Design Decision Record

- **Status**: implemented (Phase 5 / Session A)
- **Scope**: `orchestrator/entrypoint/` only. No existing production module was
  modified.
- **Companion**: `orchestrator/contract.md` · `docs/authority.md` ·
  `docs/architecture.md` · `orchestrator/production/lifecycle.py` ·
  `orchestrator/runtime/flow.py` · `orchestrator/runtime/delegation.py` ·
  `docs/phase-5/entrypoint/0002-front-door-security-review.md`

## 1. Problem

The multi-agent harness has a fully implemented bounded production runtime
(`ProductionRun`, `ExecutionFlow`, the full 17-phase gate chain), but no
**thin entry point** that accepts a user objective, validates it, resolves the
required authority record, and hands it to the runtime. Callers (chat
interfaces, CLI tools, automation) had to construct `ProductionRun.run()`
parameters manually, re-implement shape validation, and resolve delegations
ad-hoc, risking authority bypasses.

## 2. Required path

```
user objective
  → front-door shape validation
  → resolve existing structured Delegation (read-only)
  → ProductionRun.run()
  → structured terminal result (COMPLETE | BLOCKED | ESCALATED | ERROR)
```

## 3. Design decisions

### D1. Eager shape validation (fail-closed)

`FrontDoorRequest.__post_init__` validates and normalizes the request at
construction time. This matches the codebase pattern (`TaskIntake`,
`Delegation` all validate eagerly) and ensures no malformed request reaches
the runtime. An invalid construction raises `FrontDoorError` (a
`ValueError`). When passed as a plain dict to `run_front_door`, the error is
caught and returned as an `ERROR` envelope.

### D2. Delegation resolution is read-only, id-resolved

The front door accepts a `delegation_id` (pattern `^delegation-[A-Za-z0-9-]+$`)
— never a delegation document, never free text. It resolves the delegation
through the existing `DelegationProvider` seam (default:
`FileDelegationProvider` over `state/registry/`). The resolution:

- reads the provider (read-only; never creates a document)
- validates the returned delegation matches the requested id and project
- checks `status == "ACTIVE"` (never sets it)
- checks `is_revoked()` and `is_expired()` (AUTH-INV-06)
- passes the Delegation + the same provider to `ProductionRun.run()` so the
  execution-time authority re-check (AUTH-INV-05) re-reads the registry

Any failure produces `NoValidDelegation` → `BLOCKED` status.

### D3. ProductionRun is the only execution path

The front door never constructs an `ExecutionFlow`, never calls raw DSH tools,
and never invokes the control-plane gates directly. The only path through a
gate chain is `ProductionRun.run()`, which internally routes through the full
17-phase runtime (intake → understand → classify → risk_gate → decompose →
select → delegate → execute_subtasks → collect → evidence_gate → synthesize →
conflict_gate → adversarial_review → authority_gate → execute → verify →
close). Every existing gate and invariant is preserved.

### D4. No authority override accepted

The front door does **not** accept:
- `approval_reference` (never fabricate approval)
- `declared_risk` (would let the caller lower risk, potentially bypassing
  AUTH-INV-10)
- `review` / BadSector verdict (never fabricate review)

The runtime's own gates handle these deterministically: an intrinsic-HIGH
action is classified as HIGH by `control.risk` regardless of any input; a
HIGH action requiring approval escalates to `ESCALATED` via
`NeedsApproval`/`ProductionEscalated`.

### D5. Operator/test hooks preserved

`subtask_runner`, `action_executor`, `provider`, and `now` are optional
pass-through parameters forwarded to `ProductionRun` unchanged. They are
documented as operator/test hooks and never grant authority. The defaults
(the real `DelegationClient` with `FakeSubagentBackend` and file-based
registry) are used when no hook is provided.

### D6. Structured terminal envelope

The result is always a JSON-serializable `FrontDoorResult` with a `schema`
marker (`"run-result@1"`) and:

| key | Present | Description |
|---|---|---|
| `schema` | always | Envelope schema version (`"run-result@1"`) |
| `status` | always | COMPLETE / BLOCKED / ESCALATED / ERROR |
| `run_id` | always | The production run id (null when no run started) |
| `objective` | always | The original objective text |
| `state` | when available | `ProductionState.to_dict()` or null |
| `report` | when available | `FinalReport.to_dict()` or null |
| `errors` | always | Error messages (list) |
| `audit_ids` | always | Audit event ids (list) |

The CLI emits this envelope as JSON to stdout with deterministic exit codes:
0 COMPLETE, 1 ERROR, 2 BLOCKED, 3 ESCALATED.

## 4. Non-goals (explicitly not implemented)

- Idempotency store (multiple runs against the same workspace are handled by
  the existing runtime's stale-state protection — a second run fails closed).
- New web server / HTTP API.
- New DSH tool, audit ledger, or authority semantics.
- Session policy, role, toolFilter, or preset changes.
- O3 or L3 security layers.
- Dry-run / preview mode.
- Risk or approval override acceptance.
- Multiple delegation resolution (the registry holds one delegation per
  project; the front door resolves by exact id match).

## 5. What the front door does NOT do (security boundaries)

| Not allowed | Why |
|---|---|
| Create a Delegation | Only Human / the protected registry creates delegations (AUTH-INV-02) |
| Set ACTIVE on a delegation | Status is read-only; the front door never mutates authority records |
| Fabricate an approval reference | A text-based approval claim is never authority (AUTH-INV-01) |
| Derive authority from prose | The delegation_id is a structured pattern, and the Delegation is resolved from the registry, never from call text |
| Call ExecutionFlow directly | ProductionRun is the only entry (preserves all gates) |
| Call raw DSH tools | The front door imports no DSH client; only ProductionRun uses the DSH adapter |
| Bypass any gate | Every gate in the 17-phase chain runs because ProductionRun runs the full flow |
| Downgrade intrinsic HIGH | The front door accepts no `declared_risk` — the deterministic RiskClassifier is authoritative |
| Add a new authority mechanism | Only the existing DelegationProvider + ProductionRun path produces authority |
| Modify existing production modules | The front door lives in its own package; all references are imports, not modifications |
# Phase 5 / Session A — DSH Chat → ProductionRun Front Door (V1)

- **Status**: implemented
- **Scope**: `orchestrator/entrypoint/` + this directory only. No existing
  production module was modified.
- **Companion**: `orchestrator/contract.md` · `docs/authority.md` ·
  `docs/architecture.md` · `docs/phase-4/` · `orchestrator/production/*` ·
  `orchestrator/runtime/*` · `orchestrator/dsh/*`

## What this is

The **thin entry point** that bridges a user objective (chat / CLI) to the
bounded production runtime:

```
user objective
  → front-door shape validation
  → resolve existing structured Delegation (read-only)
  → ProductionRun.run()
  → structured terminal result (COMPLETE | BLOCKED | ESCALATED | ERROR)
```

It is deliberately **thin**: it performs no planning, no gating, no
delegation, and no execution of its own. Every existing gate (risk, evidence,
conflict, BadSector review, authority, execution, verification) and every
runtime invariant is preserved because the only execution path is
`ProductionRun.run()`.

## Files

| File | Purpose |
|---|---|
| `orchestrator/entrypoint/__init__.py` | Package init; re-exports the public API |
| `orchestrator/entrypoint/entry.py` | Front-door logic: `FrontDoorRequest`, `FrontDoorResult`, `resolve_delegation`, `run_front_door`, `run_from_chat` |
| `orchestrator/entrypoint/__main__.py` | CLI: `python -m orchestrator.entrypoint` (flags + `--json-stdin`) |
| `docs/phase-5/entrypoint/0001-front-door-design.md` | Design decision record (V1) |
| `docs/phase-5/entrypoint/0002-front-door-security-review.md` | Security requirements → implementation mapping |

## Usage

```bash
cd multi-agent-harness

# CLI (flags)
.venv-tests/bin/python3 -m orchestrator.entrypoint \
  --objective "produce a design doc" \
  --scope "docs/design/x.md" \
  --delegation-id "delegation-prod-001" \
  --constraint "no secrets" \
  --expected-outcome "design doc written"

# CLI (JSON stdin; CLI flags override JSON fields)
echo '{"objective":"produce a design doc","scope":["docs/design/x.md"]}' | \
.venv-tests/bin/python3 -m orchestrator.entrypoint --json-stdin \
  --delegation-id "delegation-prod-001"

# Python API (primary)
from orchestrator.entrypoint import run_from_chat
result = run_from_chat(
    objective="produce a design doc",
    scope=("docs/design/x.md",),
    delegation_id="delegation-prod-001",
    constraints=("no secrets",),
    expected_outcome="design doc written",
)
print(result.to_dict())

# Python API (explicit request object)
from orchestrator.entrypoint import FrontDoorRequest, run_front_door
result = run_front_door(
    FrontDoorRequest(
        objective="produce a design doc",
        scope=("docs/design/x.md",),
        delegation_id="delegation-prod-001",
        constraints=("no secrets",),
        expected_outcome="design doc written",
    ),
)
print(result.to_dict())
```

## Output envelope

```json
{
  "schema": "run-result@1",
  "status": "COMPLETE | BLOCKED | ESCALATED | ERROR",
  "run_id": "prod-xxxxxxxx",
  "objective": "...",
  "state": { "...": "ProductionState dict or null" },
  "report": { "...": "FinalReport dict or null" },
  "errors": ["..."],
  "audit_ids": ["event-..."]
}
```

CLI exit codes: `0 COMPLETE · 1 ERROR · 2 BLOCKED · 3 ESCALATED`.

## Security posture (summary)

- objective/scope/constraints/expected_outcome are **DATA**, never authority
  (AUTH-INV-01/13).
- The front door **never creates a Delegation**, **never sets ACTIVE**, never
  fabricates an approval reference or a review verdict, and never derives
  authority from prose — it only resolves an existing structured Delegation
  from the protected registry (`state/registry/`, ADR 0002) and hands it to
  `ProductionRun`.
- It **never calls ExecutionFlow directly** and **never calls raw DSH tools**;
  `ProductionRun.run()` is the only execution path.
- Intrinsic HIGH is never downgradable (no risk override is accepted from the
  caller).
- Scope remains authority-contained (delegation matched by id + project;
  execution-time authority re-check preserved, AUTH-INV-05/06/11).
- No new authority mechanism, no idempotency store, no new server, no new DSH
  tool, no new audit ledger, no session-policy/role/toolFilter change.

## Verification performed

- `py_compile` + import of both modules (Python 3.14).
- End-to-end smoke runs (stub subtask/action runners): COMPLETE envelope with
  run_id/report/state/audit_ids.
- Real file-registry resolution (`FileDelegationProvider` over a scratch
  `state/registry/delegations.json`) → COMPLETE.
- CLI end-to-end against a scratch registry: exit codes 0/1/2/3 for
  COMPLETE/ERROR/BLOCKED/ESCALATED; `--json-stdin` merge with CLI overrides.
- Fail-closed paths: missing delegation, id mismatch, not-ACTIVE, revoked,
  expired → BLOCKED; shape errors → ERROR.

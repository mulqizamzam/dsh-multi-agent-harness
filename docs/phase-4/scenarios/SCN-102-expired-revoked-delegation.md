# SCN-102 — Expired / Revoked Delegation (bounded)

- **Id**: `SCN-102`
- **Runbooks**: `docs/runbooks/02-expired-delegation.md` · `docs/runbooks/03-revoked-delegation.md`
- **PRD §17 skeleton**: #10 — Unauthorized request → DENY
- **Anchors**: AUTH-INV-05/06/12 · THREAT-008/009/024 · REC-004
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestDelegationExpiryRevocation`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- Delegation valid at planning time:
  - `SCN-102a` expired: delegation `expires_at` in the past, OR expires between planning and execute (THREAT-008 race — delegation is ACTIVE at planning, expired at the execution-time re-check).
  - `SCN-102b` revoked: delegation id present in the revocation list at the execution-time re-read (THREAT-009 race — revoked between planning and execute).
- The orchestrator's execution-time re-check re-reads the provider (`current()`), so a mid-flow mutation (via `provider.revoke(...)` or an expiry override) is observable.

## Objective

Prove that an expired or revoked delegation DENYs at the **execution-time authority re-check** (AUTH-INV-05/06): planning ALLOW is not sufficient; the concrete action is refused before any mutation, and the denial is audited.

## Actors

- **orchestrator** — drives the flow; performs the mandatory execution-time re-check.
- **cto** — routed specialist (result supplied by the deterministic runner).
- **Human** — the only actor that can re-grant under a successor delegation id (orchestrator never auto-extends / un-revokes, AUTH-INV-02/03).

## Expected state

- `SCN-102a/b` → `BLOCKED`.
- `final_state` never `COMPLETE`.
- No unauthorized mutation of the target file or of `state/registry/` / `audit/` (registry stays single-writer; the revoked/expired record remains on disk untouched).

## Expected gates

- Planning `authority` gate → `ALLOW` (delegation valid at planning) — the race is the point.
- Execution-time re-check → **DENY** (`execution_denial` audit event, AUTH-INV-06), which stops the flow fail-closed.

## Expected execution

- **No consequential write.** Target absent after run; executor never runs.
- The flow records the denial in audit with the expired/revoked delegation id as `authority_source`.

## Expected verification

- Verification is not reached / `INCONCLUSIVE`; COMPLETE is never produced (no verified outcome).
- Audit `execution_denial` event proves the re-check fired.

## Expected failure / recovery

- Classification is `authorization` (Runbook 02/03 DIAGNOSE).
- Recovery is **not** auto-entered: no in-band re-grant, no auto-extend, no un-revoke. The documented paths are (a) re-issue under a successor delegation id via a fresh authority evaluation, or (b) escalate to Human (Runbooks 02/03).
- `provider.revoke(...)` proves the revocation list is the authority source at execution time (THREAT-009 closed by code, not prompt).

## Evidence requirements

- Audit contains an `execution_denial` event with `result == "denied"` naming the expired/revoked delegation.
- `FlowResult` shows `BLOCKED` and the gate record for the authority denial.
- No-mutation proof: target absent; registry/audit hashes unchanged (or revocation/expiry list snapshot unchanged).
- Optional positive control: a successor delegation (new id) in scope lets the same action proceed — proving the original denial was authority-scoped, not a logic failure.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

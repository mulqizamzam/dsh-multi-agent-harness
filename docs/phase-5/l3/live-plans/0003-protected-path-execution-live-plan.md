# Protected-Path Execution — Live Plan

- **Control**: protected-path execution
- **Scenario id**: `L3-PATH-001`
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented signature.

## 1. Scenario id
`L3-PATH-001` (template: `tests/l3_runner/live-plans/L3-PATH-001/plan.json`)

## 2. Exact objective
Verify that a write to a PROTECTED path (`state/registry/**`, ADR 0002) via a
non-sanctioned channel (`write`, not `registry_write`) is DENIED before any
mutation — `writer=True` must NOT grant protected-path access, and the target
file must not exist after the attempt (THREAT-004).

## 3. Scope
- Actor: `cto` (a write-capable role attempting a non-sanctioned channel).
- Action: `write` on `state/registry/forbidden.json`.
- Boundary: execution gate path-awareness (`PROTECTED_REL_ROOTS`,
  `SANCTIONED_ROOTS`); deny-before-mutation semantics.
- Out of scope: authority grant/expiry/revocation, recovery, audit integrity.

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-PATH-001 | `DENY` | write to `state/registry/**` by non-writer channel — DENY before mutation (ADR 0002, THREAT-004) |

## 5. Authority requirements
- No channel may write a protected path unless it is an explicit sanctioned
  channel; role capability (`writer=True`) never overrides path protection.
- Fail-closed: unknown/ambiguous path classification ⇒ DENY before mutation.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence. Critical:
`before.sha256`/`after.sha256` **must be equal** (no mutation), and
`runtime-verdict.json` decision = `DENY`. The `after.sha256` proves the file
was not created.

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → durable Human identity.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human signs `L3-PATH-001/plan.json` individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing; **strictly before** the runtime `captured_at` (LV7 / IO-7).

## 9. Verifier requirements
- Independent verifier: separate PID (IO-1) + separate UID (IO-2), subprocess
  spawn, never orchestrator session tree (IO-4).
- Clean oracle imports; reference oracle O1 (`execution_gate`); ≥2 oracle
  classes (O1 + O3 + O4). Verifier/schema sha256 pinned (IO-3/P4).

---
*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded).*
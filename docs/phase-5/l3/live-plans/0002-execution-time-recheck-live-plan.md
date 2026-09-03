# Execution-Time Recheck — Live Plan

- **Control**: execution-time recheck
- **Scenario id**: `L3-AUTH-006`
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented signature.

## 1. Scenario id
`L3-AUTH-006` (template: `tests/l3_runner/live-plans/L3-AUTH-006/plan.json`)

## 2. Exact objective
Verify that authority is re-validated at **execution time**, not planning
time: a delegation ACTIVE at planning time but REVOKED before execution must
be denied (AUTH-INV-05, THREAT-009/024). A planning-time ALLOW is never
sufficient for a live execution.

## 3. Scope
- Actor: `orchestrator`.
- Action: `code_write` on `agents/cto/output.txt`.
- Boundary: authority gate at the execution seam — the scenario proves the gate
  consumes the **current** delegation state at execution, not a cached
  planning-time snapshot.
- Out of scope: revocation mechanics, state transitions, audit integrity.

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-AUTH-006 | `DENY` | delegation revoked before execution — fail-closed (AUTH-INV-05, THREAT-024) |

## 5. Authority requirements
- Execution-time revalidation is mandatory; planning state is never authority
  (AUTH-INV-05).
- Structured delegation records are the only authority input (AUTH-INV-01).
- Fail-closed: if current state is ambiguous or unreadable ⇒ DENY.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence. The
`runtime-verdict.json` and `reference-verdict.json` must both record the
execution-time decision (`DENY`); `verdict-match.json` must show agreement.

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → durable Human identity.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human signs `L3-AUTH-006/plan.json` individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing; **strictly before** the runtime `captured_at` (LV7 / IO-7).

## 9. Verifier requirements
- Independent verifier: separate PID (IO-1) + separate UID (IO-2), subprocess
  spawn, never orchestrator session tree (IO-4).
- Clean oracle imports; reference oracle O1 (`authority` gate); ≥2 oracle
  classes (O1 + O3 + O4). Verifier/schema sha256 pinned (IO-3/P4).

---
*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded).*
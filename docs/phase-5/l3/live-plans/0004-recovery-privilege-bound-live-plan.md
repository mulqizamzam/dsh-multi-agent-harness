# Recovery Privilege Bound — Live Plan

- **Control**: recovery privilege bounding
- **Scenario id**: `L3-REC-004`
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented signature.

## 1. Scenario id
`L3-REC-004` (template: `tests/l3_runner/live-plans/L3-REC-004/plan.json`)

## 2. Exact objective
Verify that recovery never acquires privilege beyond the original action:
a recovery attempt re-executing an action OUTSIDE the original authority scope
is DENIED (AUTH-INV-12, THREAT-017). Recovery is bounded to the original
authority; it never expands it.

## 3. Scope
- Actor: `orchestrator` (recovery driver).
- Action: `recovery` targeting `recovery:re-execute`, attempting an action
  outside the original authority scope.
- Boundary: recovery controller + authority gate interaction
  (`RecoveryController` bounded to original authority).
- Out of scope: full recovery cycle success (G11 covers that), state
  transitions, audit integrity.

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-REC-004 | `DENY` | recovery attempting an action outside the original authority — DENY (AUTH-INV-12, REC-004) |

## 5. Authority requirements
- Recovery carries the **original** delegation's authority only; no new
  privilege, no blind retry, no authority expansion (AUTH-INV-12).
- Fail-closed: any recovery attempt that cannot be proven within the original
  scope ⇒ DENY.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence.
`runtime-verdict.json` = `DENY`; `audit-log.jsonl` records the denied recovery
attempt; `before.sha256`/`after.sha256` equal (no mutation).

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → durable Human identity.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human signs `L3-REC-004/plan.json` individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing; **strictly before** the runtime `captured_at` (LV7 / IO-7).

## 9. Verifier requirements
- Independent verifier: separate PID (IO-1) + separate UID (IO-2), subprocess
  spawn, never orchestrator session tree (IO-4).
- Clean oracle imports; reference oracle O1 (`recovery`); ≥2 oracle classes
  (O1 + O3 + O4). Verifier/schema sha256 pinned (IO-3/P4).

---
*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded).*
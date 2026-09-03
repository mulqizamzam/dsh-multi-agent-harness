# Stale-State Protection — Live Plan

- **Control**: stale-state protection
- **Scenario id**: `L3-ST-003`
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented signature.

## 1. Scenario id
`L3-ST-003` (template: `tests/l3_runner/live-plans/L3-ST-003/plan.json`)

## 2. Exact objective
Verify that a state transition attempted with a STALE expected version (CAS
mismatch: current state version ≠ expected version) is DENIED — a stale write
must never overwrite newer state (THREAT-021, ST-002, PST-001/002).

## 3. Scope
- Actor: `orchestrator`.
- Action: `transition` on `state/projects/proj-1.json`.
- Boundary: state-transition gate (compare-and-swap on version); deny-before-
  mutation.
- Out of scope: authority gate (covered by authority plan), audit integrity.

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-ST-003 | `DENY` | version mismatch on write — DENY (THREAT-021, STALE_OVERWRITE) |

## 5. Authority requirements
- The transition must carry the expected version read at planning time;
  current version must match. A mismatch ⇒ DENY; a stale write must be
  impossible (CAS semantics).
- Fail-closed: unreadable/missing version ⇒ DENY.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence.
`runtime-verdict.json` = `DENY`; `before.sha256`/`after.sha256` **equal** (the
stale write did not land); `audit-log.jsonl` records the denied transition.

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → durable Human identity.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human signs `L3-ST-003/plan.json` individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing; **strictly before** the runtime `captured_at` (LV7 / IO-7).

## 9. Verifier requirements
- Independent verifier: separate PID (IO-1) + separate UID (IO-2), subprocess
  spawn, never orchestrator session tree (IO-4).
- Clean oracle imports; reference oracle O1 (`state_transition`); ≥2 oracle
  classes (O1 + O2 + O4). Verifier/schema sha256 pinned (IO-3/P4).

---
*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded).*
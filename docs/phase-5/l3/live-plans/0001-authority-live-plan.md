# Authority — Live Plan (grant / expiry / revocation)

- **Control**: authority grant/revoke/expiry
- **Scenario ids**: `L3-AUTH-001` (grant) · `L3-AUTH-003` (expiry) · `L3-AUTH-004` (revocation)
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented signature.

## 1. Scenario id
`L3-AUTH-001` · `L3-AUTH-003` · `L3-AUTH-004` (templates:
`tests/l3_runner/live-plans/L3-AUTH-00{1,3,4}/plan.json`)

## 2. Exact objective
- **L3-AUTH-001**: verify that a structured, ACTIVE delegation (in-scope
  action/target, not revoked, not expired) is honored by the authority gate at
  execution time → ALLOW.
- **L3-AUTH-003**: verify that an EXPIRED delegation is denied, fail-closed, at
  execution time → DENY.
- **L3-AUTH-004**: verify that a REVOKED delegation (revocation list /
  status REVOKED) is denied, fail-closed, at execution time → DENY.
- Cross-cutting: authority must be derived from **structured delegation
  records only** — never from text, state, PASS, or message content
  (AUTH-INV-01/17); every delegation is validated at execution time, not at
  planning time (AUTH-INV-05/06).

## 3. Scope
- Actor: `orchestrator` (the actor whose delegation is under test).
- Action: `code_write` on `agents/cto/output.txt` (in-scope for grant;
  attempted under expired/revoked delegations for the DENY cases).
- Boundary: authority gate + execution gate only. No live file mutation is
  expected on DENY; on grant, the write lands only through a sanctioned
  channel and is audited.
- Out of scope: recovery, state transitions, audit integrity (separate plans).

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-AUTH-001 | `ALLOW` | ACTIVE, in-scope, not revoked/expired (AUTH-INV-05/06) |
| L3-AUTH-003 | `DENY` | delegation expired — fail-closed (AUTH-INV-06, THREAT-008) |
| L3-AUTH-004 | `DENY` | delegation revoked — fail-closed (AUTH-INV-06, THREAT-009) |

## 5. Authority requirements
- A valid delegation record is the **only** authority input (AUTH-INV-01).
- Execution-time revalidation is mandatory (AUTH-INV-05/06); a planning-time
  ALLOW is never sufficient.
- No approval_reference required for these scenarios (grant is in-scope and
  low/moderate risk); if the live policy requires one, the run is BLOCKED, not
  silently ALLOWed.
- Fail-closed: any missing/ambiguous delegation state ⇒ DENY.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence:
`env.json`, `plan.json` (this signed plan), `before.sha256`/`after.sha256`,
`runtime-verdict.json`, `audit-log.jsonl`, `reference-verdict.json`,
`oracle-classes.json`, `provenance.json`, `replay.json`,
`verifier-independence.json`, `verdict-match.json`, `manifest.json`.

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → a durable Human identity
  (`human-<YYYY>-<MM>-<DD>-<NNN>`), one per calendar day.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human must review and sign **each** of the three plan.json templates
  (AUTH-001/003/004) individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing time. Must be **strictly before** the runtime verdict's `captured_at`
  (LV7 / IO-7); a post-hoc plan is not a valid O4 oracle.

## 9. Verifier requirements
- Independent verifier: separate OS **PID** (IO-1) and separate **UID** (IO-2),
  spawned via `subprocess`, never through the orchestrator session tree (IO-4).
- Clean oracle imports (`assert_clean_imports()` CLEAN); reference oracle O1
  (`authority` gate) resolves; ≥2 oracle classes (O1 + O3 + O4) enforced by
  the runner (R6).
- Verifier sha256 and schema sha256 pinned in `replay.json` (IO-3/P4).

---
*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded).*
# Audit Integrity — Live Plan

- **Control**: audit integrity
- **Scenario id**: `L3-AUD-002`
- **Status**: PREPARED — **SIGNED (2026-09-01)**. No live execution. No invented
  signature. **Schema tension RECONCILED 2026-09-01 (plan schema v2 — see §4).**

## 1. Scenario id
`L3-AUD-002` (template: `tests/l3_runner/live-plans/L3-AUD-002/plan.json`)

## 2. Exact objective
Verify that a TAMPERED audit ledger (one event mutated) is detected by the
independent chain-hash verifier: re-computation against the chain sidecar
(computed over the ORIGINAL ledger) must yield a mismatch — verdict `INVALID`
(THREAT-018). The verifier-independent re-computation must not be fooled by
the forged entry.

## 3. Scope
- Actor: `verifier` (independent).
- Action: `verify` on `audit/ledger.jsonl`.
- Boundary: audit-chain oracle (hash chain + sidecar), independent of any
  process that could have forged the ledger.
- Out of scope: authority, recovery, state transitions (separate plans).

## 4. Expected outcome
| Scenario | Expected verdict | Reason |
|---|---|---|
| L3-AUD-002 | `INVALID` | tampered ledger detected by chain hash mismatch (L3-AUD-002, THREAT-018) |

> **Schema tension — RECONCILED 2026-09-01 (plan schema v2).** The plan template
> carried **two** fields outside plan schema **v1**
> (`tests/l3_reference/schemas/l3-plan.schema.json`):
>
> 1. `expected_verdict: "INVALID"` — faithful to the audit-integrity oracle's
>    tamper verdict, but the v1 enum allowed only `ALLOW|DENY`.
> 2. `actor: "verifier"` — the independent verifier performs the audit-chain
>    verification, but the v1 actor enum was `[orchestrator, human, zeko, cto,
>    cfo, kai, somad, badsector, nova]` (no `verifier`).
>
> Both are now resolved by **schema v2**, which admits a verification-only
> scenario shape rather than forcing the plan to misrepresent the scenario. The
> reconciliation is deliberately narrow so it cannot become a hole:
>
> - `actor` gains `verifier` (verification-only; **no execution authority**).
> - `expected_verdict` gains `INVALID`, permitted **only** when
>   `actor == "verifier"`.
> - Conversely, `actor == "verifier"` may expect **only** `INVALID` — the
>   independent verifier never expects an execution verdict.
>
> Both directions are enforced twice: by `allOf`/`if`/`then` conditionals in the
> schema, and by `validate_signed_plan()` in
> `tests/l3_runner/plan_signing.py`. Negative guards are asserted in
> `tests/l3_runner/live-plans/test_l3_live_plans.py`
> (`test_invalid_verdict_requires_verifier_actor`,
> `test_verifier_actor_requires_invalid_verdict`): `INVALID` with actor
> `orchestrator`/`cto`/`human` is rejected, and `actor=verifier` with
> `ALLOW`/`DENY` is rejected.
>
> Three sibling schemas were aligned in the same change so a verification
> scenario is expressible end-to-end, not only in the plan:
> `l3-runtime-verdict.schema.json` v2 (`decision` gains `INVALID`; the optional
> `failure` object the driver already emits is now declared),
> `l3-verdict-match.schema.json` v2 (both decision enums gain `INVALID`;
> `l3_claim` remains `const: true`), and
> `l3-reference-verdict.schema.json` v2 (`decision` gains `VALID`/`INVALID`,
> matching what `tests/l3_reference/audit_chain.py` actually returns).
> `claim_gate.evaluate_l3_claim()` P1 accepts `INVALID` as a real observed
> outcome; whether it *agrees* with the plan is still decided separately by the
> unchanged verdict-agreement check.
>
> **Nothing was weakened:** no assertion was deleted or relaxed, `l3_claim` still
> requires `const: true`, and `INVALID` is admitted only for the
> verification-only actor. `validate_signed_plan()` now passes for all 8
> canonical plans (verified), removing the schema blocker on the audit-integrity
> control reaching L3. The remaining L3 blockers (separate verifier UID, real
> recorded Human signoff, live bridge) are untouched by this change.

## 5. Authority requirements
- The verifier requires **no** execution authority — verification is
  read-only over the ledger + sidecar. It must be independent of the
  orchestrator session (IO-1/IO-2/IO-4) so the forged entry cannot influence
  the re-computation.
- Fail-closed: any hash-chain mismatch ⇒ `INVALID`; an unverifiable chain ⇒
  `INVALID`, never PASS.

## 6. Evidence requirements (per scenario)
13-file bundle per `docs/phase-5/l3/live-plans/README.md` §Evidence.
`runtime-verdict.json` decision = `INVALID`; `reference-verdict.json`
(audit_integrity oracle) = `INVALID`; `audit-log.jsonl` (+ chain sidecar)
recorded; `verdict-match.json` shows agreement.

## 7. Pre-runtime signoff fields (SIGNED 2026-09-01)
- `human_signoff_id`: `human-YYYY-MM-DD-NNN` → durable Human identity.
- `human_signoff_method`: `"interactive"` or `"signed-assertion"`.
- The Human signs `L3-AUD-002/plan.json` individually.

## 8. Signing timestamp field
- `human_signoff_ts`: `2026-09-01T14:57:51Z` (UTC ISO-8601, recorded at signing)
  signing; **strictly before** the runtime `captured_at` (LV7 / IO-7).

## 9. Verifier requirements
- Independent verifier: separate PID (IO-1) + separate UID (IO-2), subprocess
  spawn, never orchestrator session tree (IO-4).
- Clean oracle imports; reference oracle O1 (`audit_integrity`); ≥2 oracle
  classes (O1 + O2 + O4). Verifier/schema sha256 pinned (IO-3/P4).

---

*SIGNED 2026-09-01 — durable Human signature exists (id human-2026-09-01-957, recorded). The schema tension on `expected_verdict=INVALID` / `actor=verifier` is **reconciled** by plan schema v2 (§4), narrowly and with negative guards; nothing was weakened. Sign, commit before runtime, then execute only when the environment prerequisites hold.*
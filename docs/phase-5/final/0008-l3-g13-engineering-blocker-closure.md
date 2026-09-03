# Phase 5 — L3/G13 Engineering Blocker Closure (Authorized In-Session Work)

- **Milestone**: Phase 5 / production closure — PHASE A engineering exhaustion
- **Status**: **All five in-session engineering blockers CLOSED. Remaining blockers are exclusively external to current authority (root, Human, DSH runtime).**
- **Date**: 2026-09-01 (this session)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `tests/l3_runner/` (runtime_driver, runner, plan_signing, claim_gate, live-plans tests), `tests/l3_reference/schemas/` (4 schemas), `tests/g13/gate/` (2 test modules), `pytest.ini` (new), and the two L3 live-plan docs. **No production code changed** (`control/`, `orchestrator/`, `registry_writer/`, `state/`, `audit/`, `config/`, `agents/`, `schemas/` untouched). **No DSH core, session policy, preset, or role change. No G13 scenario executed. No L3 run executed. No approval, signature, delegation, or provenance fabricated. No bridge marker set, nothing mounted. Nothing REAL simulated. No test weakened, skipped, or deleted.**
- **Companion**: `docs/phase-5/security/g10/o3/execution/0021` (G10 C1–C5) · `0022` (H5 APPROVED) · `docs/phase-5/final/0001-security-closure-matrix.md`

---

## 1. What was closed, and what it changes

Five blockers were previously recorded as requiring engineering work rather than external authority. All five are now closed, verified, and regression-clean.

| # | Blocker | Prior state | Now |
|---|---|---|---|
| **A1** | `LiveDSHRuntimeDriver.execute()` refused even when all preconditions held | stub; no dispatch path existed at all | **real dispatch seam**, fail-closed, 3 outcomes |
| **A2** | `runner.py` hardcoded `--rehearsal` on every verifier spawn → `l3_claim` could never be true | no non-rehearsal path existed | **claim-capable path** gated on a real Human signoff |
| **A3** | L3-AUD-002 schema tension (`expected_verdict=INVALID`, `actor=verifier`) blocked a schema-valid signed plan | documented, unfixed | **reconciled** across 4 schemas + validator + claim gate |
| **A4** | No fail-fast config → G13 gate axis 7/9 BLOCKED | absent | **`pytest.ini`** (`addopts = -x`); both axes READY |
| **A5** | G13 recheck axis 5 reported BLOCKED unconditionally | latent comparison bug | **fixed**; axis 5 genuinely READY |

**Net effect on the G13 pre-gate: 5 READY / 6 BLOCKED → 7 READY / 4 BLOCKED** (11-axis), and **6 READY / 2 BLOCKED** on the 8-axis gate. Every remaining blocked axis requires authority this session does not hold.

---

## 2. A5 — G13 recheck axis 5: a real bug, not a stale assertion

This one matters beyond its own axis, because it means an earlier blocker count was **overstated**.

`recheck_verdict()` (`tests/g13/gate/test_g13_live_recheck.py`) compared an `ApprovalStatus` **enum member** against a bare string, and compared `e2e_status` against the literal `"VERIFIED"` — a value `approval_composition.py` never emits (its values are `PASS` / `UNKNOWN` / `UNAVAILABLE`):

```python
approval_ready = (ar.status == "APPROVAL_INTERACTIVE_READY")   # always False
approval_e2e   = (ar.e2e_status == "VERIFIED")                 # always False
```

Both were **unconditionally False regardless of the environment**. Axis 5 could never report READY even with a fully composed, browser-attached approval path. Fixed to compare `ar.status.value` and `"PASS"`.

Fresh probe: `status = APPROVAL_INTERACTIVE_READY`, `composed = True`, `effective_policy = ask`, `web_session = True`, `web_server_reachable = True`. **Axis 5 is genuinely READY.**

A companion test asserted `status == "APPROVAL_COMPOSED"` — the *headless* rung. This is a Web GUI session with the server reachable, so the honest status is the higher rung `APPROVAL_INTERACTIVE_READY`. The assertion now accepts either rung (both mean "composition ready") while the separate `test_axis_5_approval_e2e_unknown` continues to hold **E2E at UNKNOWN**. That distinction is deliberately preserved: *composition readiness is not end-to-end evidence*, and no in-session action can produce the `approval/asked` + `approval/decided` pair while prompts are disabled.

---

## 3. A4 — fail-fast (`pytest.ini`)

The G13 gate requires the 63-scenario live run to stop at the first unexpected failure so a failing scenario cannot cascade state contamination (gate `0001` §7, recheck `0002` §9/B6). Both gates probe for `-x`/`maxfail=1` in a root pytest config; none existed.

Added `pytest.ini` with `addopts = -x`. Chosen as the **safe default** rather than a documented invocation an operator could forget.

Verified before adopting:
- a CLI `--maxfail=0` **overrides** `addopts = -x` (confirmed by direct experiment), so full-suite pass/fail counts remain obtainable;
- collection is **unchanged at 3134 tests** — nothing is deselected, skipped, or hidden;
- no CI config, Makefile, or documented invocation is affected (none exist that would inherit it).

Four assertions encoded "fail-fast is NOT configured" and would have failed on progress. They were **inverted, not deleted**: they now assert fail-fast **IS** configured and fail if it regresses. `test_gate_verdict_blocked`'s exact blocked-axis list was updated from 6 to 5 entries accordingly.

---

## 4. A1 — `LiveDSHRuntimeDriver.execute()`: a real seam, still fail-closed

Previously the driver refused unconditionally — even with all five preconditions satisfied it returned `BLOCKED / live-execution-not-authorized`, so no amount of external provisioning could ever produce a live L3 run. There was no dispatch path to authorize.

`execute()` now has exactly three outcomes, in order:

| Outcome | Condition | Result |
|---|---|---|
| 1 | any precondition missing | `BLOCKED`, `live-precondition:<names>`, class `environment` |
| 2 | preconditions hold, but no real dispatcher injected **or** `live_execution_authorized` not asserted | `BLOCKED`, `live-execution-not-authorized`, class `authorization` |
| 3 | preconditions hold **and** a real dispatcher injected **and** live execution authorized | the **dispatcher's actual observation** |

Design constraints held deliberately:

- **The driver never constructs a verdict of its own.** In outcome 3 the observation comes entirely from the injected dispatcher.
- **No silent LIVE → FAKE downgrade.** Absent a real dispatcher the driver refuses; it never substitutes `RecordedRuntimeDriver` or any in-process stand-in.
- **A raising dispatcher is an ERROR, never an ALLOW**, recorded as `live-dispatch-error` with the exception text and `cause: "outcome UNKNOWN, not retried, never converted to a PASS"`. **No blind retry** of a possibly-executed side effect.
- **Malformed dispatcher output is refused, not interpreted** — a non-dict return, or a `decision` outside `{ALLOW, DENY, ERROR, INVALID}`, yields `live-dispatch-malformed` rather than an inferred verdict.
- `available()` and `dispatch_available()` remain read-only.

Verified behaviour (all 8 paths):

```
1  missing preconditions  -> BLOCKED | live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer
2  no dispatcher          -> BLOCKED | live-execution-not-authorized
2b dispatcher, unauth'd   -> BLOCKED | live-execution-not-authorized
3  authorized real DENY   -> DENY    | authority_gate | tool_call_id preserved
3b dispatcher raises      -> ERROR   | live-dispatch-error
3c bad decision value     -> BLOCKED | live-dispatch-malformed
3d non-dict return        -> BLOCKED | live-dispatch-malformed
3e INVALID (L3-AUD-002)   -> INVALID | accepted
```

In this environment outcome 1 still fires (`human_signed_plan`, `d4_d7_mounted`, `approval_answerer` all missing), so **behaviour here is unchanged** — every existing refusal contract test still passes. What changed is that an authorized operator now *has* a path; before, there was none.

---

## 5. A2 — non-rehearsal verifier path

`run_scenario()` spawned the verifier with `--rehearsal` unconditionally (and hardcoded `rehearsal=True` inline), and the claim gate short-circuits `l3_claim=False` on that flag. **No combination of Human signatures could have produced a claim through the old runner.**

Added `rehearsal: bool = True` (default preserves existing behaviour) and `live_driver=None`. `--no-rehearsal` exposes it on the CLI. `summary` now reports `rehearsal`.

Two refusals guard the new path:

1. **`mode="live"` without an authorized live driver → refused.** Previously live mode raised unconditionally; it now raises unless a `LiveDSHRuntimeDriver` whose `dispatch_available()` is True is injected. It never falls back to the recorded driver — that would be a silent LIVE → FAKE downgrade.
2. **`rehearsal=False` without a REAL Human signoff → refused.** The check delegates to the existing authoritative discriminator, `environment/readiness.py::_real_human_signoff_observed`: method ∈ {`interactive`, `signed-assertion`} **and** a durable id **and** a timestamp **and** `human_signoff_provenance == "recorded"`.

The second point deserves emphasis. My first implementation blacklisted known placeholder strings — which would have **accepted** the synthetic critical fixtures (`human-2026-08-31-101`, a well-formed timestamp) as real signoffs. That is exactly the failure mode the task forbids. Probing caught it: `L3-AUTH-001` was *not* refused. Reusing the single authoritative predicate fixed it, and both `L3-AUTH-001` (synthetic-but-well-formed) and `L3-TEST-001` are now correctly refused. No plan in the repo carries `provenance: recorded`, so **every** scenario is refused for a claim-capable run today — which is the honest outcome.

---

## 6. A3 — L3-AUD-002 schema reconciliation (narrow, guarded)

The audit-integrity oracle (`tests/l3_reference/audit_chain.py`) returns `VALID`/`INVALID`, and the actor is the independent `verifier`. Plan schema v1 admitted neither, so the 8th canonical scenario could not hold a schema-valid signed plan — a hard blocker on that control ever reaching L3.

Reconciled at **four** coupled sites (v1 → v2), not just the plan schema:

| Site | Change |
|---|---|
| `l3-plan.schema.json` | `actor` gains `verifier`; `expected_verdict` gains `INVALID`; **new optional `human_signoff_provenance: ["recorded"]`** |
| `l3-runtime-verdict.schema.json` | `decision` gains `INVALID`; the optional `failure` object the driver already emits is now declared |
| `l3-verdict-match.schema.json` | both decision enums gain `INVALID`; **`l3_claim` remains `const: true`** |
| `l3-reference-verdict.schema.json` | `decision` gains `VALID`/`INVALID`, matching what the oracle actually returns |
| `plan_signing.validate_signed_plan()` | enum check mirrors the schema, both directions |
| `claim_gate.evaluate_l3_claim()` P1 | accepts `INVALID` as a real observed outcome |

**The reconciliation is narrow by construction, enforced in both directions, twice:**

- `INVALID` is permitted **only** when `actor == "verifier"`;
- `actor == "verifier"` may expect **only** `INVALID`.

Enforced by `allOf`/`if`/`then` in the schema *and* independently in `validate_signed_plan()`. Verified negatively:

```
INVALID + actor=verifier       -> valid    (the legitimate case)
INVALID + actor=orchestrator   -> REJECTED
INVALID + actor=cto            -> REJECTED
INVALID + actor=human          -> REJECTED
DENY    + actor=verifier       -> REJECTED
ALLOW   + actor=verifier       -> REJECTED
VOID verdict                   -> REJECTED
provenance=recorded            -> valid
provenance=self-attested       -> REJECTED
```

So an execution scenario can never borrow a verification outcome, and the verifier can never claim an execution verdict. `l3_claim` still requires `const: true`; P1 accepting `INVALID` does not imply agreement — the separate verdict-agreement check is unchanged.

**A side benefit worth naming:** `human_signoff_provenance` was previously absent from a schema with `additionalProperties: false`, so a plan carrying the field required for a *real* signoff would have **failed validation**. The provenance requirement and the schema were mutually unsatisfiable. That latent contradiction is now resolved — a real signed plan can validate when one eventually exists.

All 8 canonical plans now validate (`schema_validation = PASS`). One test that asserted the tension was rewritten to assert the **reconciliation plus both negative guards** — renamed rather than deleted, and it now covers strictly more than before.

---

## 7. Verification

| Check | Result |
|---|---|
| **Full regression** | **3117 passed, 19 skipped, 0 failed** (274s) |
| `tests/l3_runner/` + `tests/l3_reference/` | 594 passed |
| `tests/g13/` | 149 passed |
| `tests/validate-config.py` | **194 passed, 0 failed** |
| `compileall` (control, orchestrator, registry_writer, schemas, state, audit, l3_runner, l3_reference, g13) | **0 errors** |
| All 11 L3 JSON schemas | valid under draft 2020-12 (`check_schema`) |
| Test collection | **3134** — unchanged by `pytest.ini` |

Regression rose from 3115 to 3117 (two new negative-guard tests). **Zero failures.**

---

## 8. PHASE B — fresh live-readiness inspection

Every prerequisite probed fresh, and each assessed for whether *this* authority can execute it.

| # | Prerequisite | State | Executable here? |
|---|---|---|---|
| 1 | D4/D7 live-bridge marker | `DSH_LIVE_BRIDGE_ACTIVE` **UNSET** | **NO** — see §8.1 |
| 2 | 7 `subagent_*` instances mounted | all **False** (probe is marker-derived) | NO — same root cause |
| 3 | REAL backend | `BackendKind.UNAVAILABLE` | NO — same root cause |
| 4 | Approval path composition | **APPROVAL_INTERACTIVE_READY** ✅ | already satisfied |
| 5 | Approval **E2E** | **UNKNOWN** — 0 approval events, no `asked`+`decided` pair | NO — prompts disabled |
| 6 | Live driver dispatch | `dispatch_available() = False` (no dispatcher, not authorized) | NO — needs 1 + 5 + Human |
| 7 | Separate verifier UID (IO-2) | `l3_claim_possible = False` | **NO** — `useradd: Permission denied`; `setpriv: Operation not permitted` |
| 8 | Real Human signoff | no plan carries `provenance: recorded` | **NO** — fabrication forbidden |
| 9 | Fail-fast | `pytest.ini` ✅ | **DONE this session** |
| 10 | Evidence capture | `audit/runtime/` writable ✅; `audit/l3/` correctly absent | already satisfied |
| 11 | Rollback | 4 cleanup steps defined ✅; `o3-pre` manifest **5/5 VERIFIED** | already satisfied |

### 8.1 Why the bridge marker was not set

All 7 `subagent_*` rows **are** present in the live web profile (`cordis.patch.yml`, verified). It would have been trivial to export `DSH_LIVE_BRIDGE_ACTIVE=1` and watch four axes flip to READY.

That was not done, and should not be. The marker's documented meaning is *"the D4/D7 composition has been **verified** mounted for this session"* — it is an assertion of verification, not a request for one. `check_instance_mounted()` returns True purely because the marker is set, so setting it myself would make the mount probe assert its own premise, and `probe_backend_kind()` would report `real-dsh` for a bridge no one verified. Four axes would read READY on no evidence, and the 63-scenario G13 run would proceed against an unverified backend.

That is precisely "fake a prerequisite" and "silently simulate REAL". **It requires an operator who has actually verified the mount.**

---

## 9. PHASE C — G13: pre-gate NOT satisfied, nothing executed

| 8-axis gate | | 11-axis recheck | |
|---|---|---|---|
| 1 real DSH child observable | ⛔ | 1 live bridge active | ⛔ |
| 2 D4/D7 mounted | ⛔ | 2 D4/D7 instances mounted | ⛔ |
| 3 bridge marker | ⛔ | 3 real backend available | ⛔ |
| 4 backend kind | ⛔ | 4 real child observable | ⛔ |
| 5 scratch workspace | ✅ | 5 approval path | ✅ **(closed A5)** |
| 6 evidence capture | ✅ | 6 authorized G13 run | ⛔ |
| 7 stop-at-first-failure | ✅ **(closed A4)** | 7 scratch workspace | ✅ |
| 8 authorization | ⛔ | 8 evidence capture | ✅ |
| | | 9 stop-at-first-failure | ✅ **(closed A4)** |
| | | 10 rollback/cleanup | ✅ |
| | | 11 G10 closed | ✅ **(H5 approved)** |
| **verdict** | **BLOCKED** | **g13_live_ready** | **False** |

**No scenario executed. Nothing simulated. Live evidence remains 0/63.** The four remaining blocked axes collapse to a single external cause — the unverified/unmounted D4/D7 bridge — plus authorization, which additionally needs the Human §15 acceptance.

---

## 10. PHASE D — L3: pre-gate NOT satisfied, nothing executed

`l3_claim_possible = False`. Exactly three blockers, all external:

| Blocker | Detail |
|---|---|
| `L3ENV-UID-2` | same-UID host (`orchestrator_uid = verifier_probe_uid = 1000`); `useradd`/`setpriv` both refused |
| `L3ENV-D4D7-3` | bridge marker unset |
| `L3ENV-PLAN-REAL` | no real recorded Human signoff exists |

`rehearsal_ready = True` — the machinery is sound. `audit/l3/` correctly does not exist; no bundle was created, and no `l3_claim` was produced.

**The two blockers that were engineering work are gone.** Before this session, satisfying all three external prerequisites still could not have yielded a claim: the driver refused unconditionally (A1) and the runner forced rehearsal (A2). Now the path exists and waits only on external authority.

---

## 11. PHASE E — final-gate items evaluable now

| Item | State |
|---|---|
| G10 | **CLOSED** (project-layer, H5 approved — `0022`) |
| G13 | **OPEN/UNKNOWN**, 0/63 live, pre-gate BLOCKED |
| L3 | **NOT CLAIMABLE**, 3 external blockers |
| Front Door REAL | historically VERIFIED; **not re-derivable from this sandbox** — see below |
| Regression | **GREEN** 3117/19/0 |
| validate-config | **194/0** |
| compileall | **0 errors** |
| Audit integrity | **GREEN** (29) |
| Recovery | **GREEN** (41) |
| Rollback | **READY** (`o3-pre` 5/5 hashes verified) |
| Production readiness | **NOT DECLARED** |

**Front Door REAL, precisely:** its first step is `registry_write`, which now returns `WriterUnavailable` from this principal because uid 1000 cannot read the O3 credential. That is **the G10 trust boundary working as designed**, not a regression — the control plane is meant to run as `dsh-control`. Re-deriving Front Door REAL end-to-end requires the control plane executed as `dsh-control` **and** a verified live bridge; neither is available in-session. The historical evidence (`runs/bagian1/`) stands; it is simply not reproducible from inside the sandbox any more.

---

## 12. Honesty statement

1. **No prerequisite was faked.** The bridge marker was not set; nothing was mounted; no approval, signature, delegation, or provenance was fabricated.
2. **Nothing REAL was simulated, and no LIVE → FAKE fallback exists.** Both new refusal paths (A1 outcome 2, A2 live-without-driver) exist specifically to prevent it.
3. **No test was weakened, skipped, or deleted.** Six assertions were updated because they encoded superseded *state facts* (fail-fast absent; approval headless; the L3-AUD-002 tension unfixed). Each was inverted or broadened to assert the new verified state and to fail on regression. Two new negative-guard tests were **added**. Collection rose 3134 → 3134 with two more tests passing; zero failures.
4. **An overstatement in my own earlier reports is corrected:** axis 5 was reported BLOCKED when the cause was a comparison bug, not the environment. Blocker counts in prior turns were too high.
5. **An error I made mid-task is recorded rather than hidden:** the first A2 signoff check would have accepted synthetic fixture signoffs as real. Probing caught it before any suite ran; it was replaced with the single authoritative predicate.
6. **No production code changed.** Only test-side infrastructure, schemas, `pytest.ini`, and two L3 docs.
7. **G13 not executed. L3 not executed. G10/O3 not repeated** (no drift). **No DSH core, session policy, preset, or role change.**
8. **Production readiness NOT declared.**

---

## 13. Remaining blockers — all external to current authority

| # | Blocker | Authority | Exact action |
|---|---|---|---|
| **X1** | D4/D7 composition not verified-mounted; marker unset | Operator | Verify the 7 `subagent_*` instances are live in this session, then set `DSH_LIVE_BRIDGE_ACTIVE=1`. Closes G13 axes 1–4 and `L3ENV-D4D7-3`. Do **not** set it without verifying the mount. |
| **X2** | Approval prompts disabled → E2E UNKNOWN | Operator | Enable approval prompts and attach a live answerer, producing a re-derivable `approval/asked` + `approval/decided` pair. Composition is already READY; only E2E is missing. |
| **X3** | No separate verifier UID (IO-2) | root | `useradd --system --shell /usr/sbin/nologin l3-verifier`; grant read-only access to the bundle dir; run the verifier as that user with `--orchestrator-uid 1000`. Do **not** pass `--verifier-probe-uid` or omit `--orchestrator-uid` — both produce a vacuous pass the claim gate still rejects. |
| **X4** | No real recorded Human signoff | Human | Sign each of the 8 canonical plans via the interactive/signed-assertion path and commit `human_signoff_provenance: "recorded"` with a durable id and UTC timestamp **before** the run. Schema v2 now accepts this shape. The runner refuses a claim-capable run without it. |
| **X5** | No Human acceptance of `docs/security/0003` §15 | Human | Record explicit acceptance authorizing the adversarial live G13 test. Closes G13 axes 6/8. |
| **X6** | Control plane cannot reach the O3 daemon from the sandbox | Operator | Run the control plane as `dsh-control` (by design; see `0021` §7). Needed to re-derive Front Door REAL. Scope any sudo rule to the entrypoint only — a blanket `sudo -u dsh-control` for `administrator` reopens the `0018` credential leak. |
| **X7** | O4 upstream DSH capability residual | Upstream DSH | Per-agent/path-level sandbox capability absent in 0.1.1-rc.2. Separately tracked; not a G10 closure condition. |

Once X1–X5 are satisfied, the G13 63-scenario run and the 8-scenario L3 run are **executable through the paths built this session** — with no further engineering work required.

---

*Status: PHASE A COMPLETE — all five in-session engineering blockers CLOSED (A1 live dispatch seam · A2 non-rehearsal claim path · A3 four-schema reconciliation with negative guards · A4 fail-fast · A5 axis-5 comparison bug). Regression **3117 passed / 19 skipped / 0 failed**; validate-config 194/0; compileall clean; 11/11 schemas valid; collection unchanged. PHASE B: 4 of 11 prerequisites satisfied, 7 external. PHASE C: G13 pre-gate **BLOCKED** (4 axes) — not executed, not simulated, 0/63 live. PHASE D: L3 `l3_claim_possible = False` (3 external blockers) — not executed, no bundle. PHASE E: G10 CLOSED · Regression GREEN · Audit GREEN · Recovery GREEN · Rollback READY · Front Door REAL not re-derivable from the sandbox by G10 design. **PRODUCTION_READY = NO.** Every remaining blocker (X1–X7) requires root, Human, or DSH-runtime authority; no authorized in-session engineering work remains.*

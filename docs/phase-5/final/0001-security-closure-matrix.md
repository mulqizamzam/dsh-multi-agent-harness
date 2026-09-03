# Phase 5 — Final Security Closure Matrix (Authoritative)

- **Milestone**: Phase 5 / Session E — FINAL SECURITY GAP CONSOLIDATION
- **Status**: CLOSURE MATRIX (authoritative consolidation of all Phase-5 gap reports; **no implementation change, no re-test, no failure downgrade, no automatic production-readiness declaration**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/final/` (this file). Read-only synthesis of: `docs/phase-4/0005-production-readiness-assessment.md` (G1–G13) · `docs/phase-5/0001-acceptance-matrix.md` · `docs/phase-5/0001-security-hardening-analysis.md` · `docs/phase-5/master-integration-gate.md` · `docs/phase-5/environment/0001` (G2/G3) · `docs/phase-5/resilience/0001+0002` (G4/G9) · `docs/phase-5/role-validation/0001` (G12) · `docs/phase-5/l3/0001+0002` (G5–G8) · `docs/phase-5/security/0001+0002` (G10/G13) · `docs/security/0003/0005/0006/0007` · documented test results.
- **No implementation modified. No re-test executed. No failure re-labelled as PASS. No control declared L3. No production-readiness declared by this document alone.**

---

## 0. Evidence taxonomy (binding for every row below)

Every claim in this matrix is labelled with exactly one evidence class. These classes are mutually exclusive and never promoted without a new evidence source.

| Class | Meaning | Can it close a security gap? |
|---|---|---|
| **Deterministic proof** | In-process / recorded-runtime tests against `tests/control_plane.py`, `control/*`, `orchestrator/*`, state/audit helpers. Proven by green tests, no live DSH child dispatched. | YES — for logic/invariant gaps (L1). |
| **Real DSH proof** | Live DSH 0.1.1-rc.2 session with a mounted `subagent_<id>` instance; runtime-observed denial/allow. | YES — strongest current level (L2-LIVE). |
| **L2 evidence** | DSH-native/DSH-level configuration (toolFilter, preset, sandbox, approval) shown live or verified by inspection. | YES — for DSH-layer claims. |
| **L3 evidence** | Independent observer (separate process + UID), external oracle (≥2 classes), Human-signed plan, reproducible bundle, P1–P4 all pass. | YES — only class that closes an L3 claim. |
| **UNKNOWN** | Not verifiable in this environment / no claim made. | NO — must remain open. |
| **Accepted residual** | Gap is real, documented, and deliberately not closed now (contained by detection or gated on a future option). | Partial — status stays OPEN/DEFERRED unless paired with a closure mechanism. |
| **Blocking residual** | Gap prevents a named acceptance condition (live proof, L3 claim, production use). | NO — blocks the condition until resolved. |

**Headline honesty rule (carried from all source reports): no control is L3 today; no live L3 run has executed; the same-UID sandbox makes L3 impossible here; the D4/D7 marker is unset this session.**

---

## 1. Security closure matrix — G1..G13

| Gap | Implementation | Evidence | Test | Security level | Residual | Status |
|---|---|---|---|---|---|---|
| **G1 — REAL DSH backend wiring** (`_get_client()` production-wired) | `orchestrator/dsh/bridge.py` (`RealDSHBackend`, `BridgeNotAvailable`, `BackendKind` 3-state); `orchestrator/runtime/flow.py` `_select_backend()`/`probe_backend()`/`_assert_backend_available()`; `orchestrator/dsh/client.py` `backend_kind`/`backend` | 308 orchestrator tests pass; explicit FAKE/REAL/UNAVAILABLE selection, fail-closed `BridgeNotAvailable` → BLOCKED | `test_backend_selection.py` (6) · `test_bridge_selection.py` (14) | **Deterministic proof** (L1/L2-config); no real DSH proof (marker unset) | **Accepted residual**: live-DSH dispatch proof requires the per-session mount (G2); no live child dispatched this session | **CLOSED** (deterministic) |
| **G2 — Persistent D4/D7 availability** | `docs/phase-5/environment/0001` — per-session mount-verification procedure (presets → instance rows → marker → resolution → probe → smoke); fail-closed on any step | `ENV-MOUNT-1` honestly reports **FAIL** (marker unset); 14 environment preflight tests pass | `tests/environment/test_environment_preflight.py` (14) | **Deterministic proof** of the detection mechanism (operational readiness) | **Blocking residual**: mount is per-session, not persistent; live dispatch unavailable until re-verified | **CLOSED** (readiness mechanism); availability remains a per-session operational condition |
| **G3 — Approval-answerer availability** | `docs/phase-5/environment/0001` §3 — answerer detection + fail-closed behavior; no silent allow on `unavailable` | `ENV-APPROVAL-1` honestly reports **FAIL** (prompts disabled); `ask` → DENY+escalate verified | `tests/environment/` | **Deterministic proof** of fail-closed semantics | **Blocking residual**: interactive + HIGH-risk approval execution BLOCKED; L3 signed plans impossible without an answerer | **CLOSED** (readiness mechanism); availability remains an operator/environment action |
| **G4 — Provider 429 / rate-limit resilience** | Existing runtime: typed adapter exceptions → `classify_adapter_failure` → `environment` → recovery; no blind retry; unknown → ESCALATED | 41 resilience tests pass (1 skipped = live variant); Phase-3 live 429 observed and handled correctly | `tests/resilience/test_429_rate_limit.py` (13) + timeout/abort (8) | **Deterministic proof**; Phase-3 **real DSH proof** of correct handling (INT-12 environment-class) | **Accepted residual**: no retry scheduling/backoff/dedicated capacity (REC-G4-1 recorded, not implemented) | **CLOSED** (deterministic + Phase-3 live observation) |
| **G5 — Independent L3 verifier** | `tests/l3_runner/` — verifier, claim_gate (`evaluate_l3_claim` P1–P4), independence (IO-1..10), plan_signing, uid_readiness, rehearsal, runtime_driver (safe live BLOCKED interface), validator LV21/LV22 | 131 L3 tests pass; claim gate refuses any claim without Human-signed plan + IO-2 + complete bundle; rehearsal forces `l3_claim=false` | `tests/l3_runner/test_l3_g5_verifier.py` (15) + readiness suites | **Deterministic proof** of verifier infrastructure; **no L3 evidence** (no live run) | **Blocking residual**: live L3 claim needs separate UID host (G6), signed plan (G7/G3), authorized run (G8) — `LiveDSHRuntimeDriver` refuses live dispatch | **CLOSED** (infrastructure, PASS_WITH_CONDITIONS); live L3 execution remains BLOCKED |
| **G6 — Separate-process/UID readiness** | `tests/l3_runner/uid_readiness.py` — honest IO-2 detection + documented launch options (setuid / separate user / separate host) | 9 UID-readiness tests pass; IO-2 fails honestly on same-UID → `l3_claim_possible=False` | `tests/l3_runner/test_l3_uid_readiness.py` (9) | **Deterministic proof** of honest detection; **no L3 evidence** possible in this sandbox | **Blocking residual**: same-UID sandbox ⇒ no L3 claim (never faked) | **CLOSED** (readiness); L3 claim remains BLOCKED by environment |
| **G7 — Human-signed plan prerequisites** | `tests/l3_runner/plan_signing.py` — signoff schema (`human_signoff_id`/`_ts`/`_method`), pre-runtime ordering (LV7/IO-7), signing checklist + template; preflight PF-PLAN-5 | 21 plan-signing tests pass; unsigned plans → `UNSIGNED` → claim gate fails | `tests/l3_runner/test_l3_plan_signing.py` (21) | **Deterministic proof** of the O4 oracle mechanism | **Blocking residual**: real Human identity + signing requires approval answerer (G3); fixtures are inert templates | **CLOSED** (readiness) |
| **G8 — Evidence-bundle execution path** | `tests/l3_runner/rehearsal.py` — full runner→verifier→collector→validator→replay chain; LV10 fails-by-design for rehearsal bundles; verifier independence guard (LV21/LV22) | 14 rehearsal tests pass; complete 13-file bundle under scratch with `l3_claim=false`; no `audit/l3/` committed | `tests/l3_runner/test_l3_rehearsal.py` (14) | **Deterministic proof** of the execution path; **no L3 evidence** (rehearsal is not L3 by design) | **Blocking residual**: no live L3 bundle; no committed evidence | **CLOSED** (readiness) |
| **G9 — Runtime registry protection (ISO-LIVE-006 deterministic equivalent)** | `control/execution_gate.py` — path-aware `authorize_write`, `PROTECTED_REL_ROOTS`, `SANCTIONED_ROOTS`; deny-before-mutation; flow-level BLOCKED + audited denial | 41 resilience tests pass; non-sanctioned write → DENY before mutation; sanctioned channels work; cross-root denied | `tests/resilience/test_registry_gate.py` (15) | **Deterministic proof** (L1 gate); ISO-LIVE-006 live variant **BLOCKED** (skip-marker, no mount) | **Blocking residual**: live ISO-LIVE-006 proof absent; DSH-layer hard isolation NOT closed (G10) | **CLOSED** (deterministic) |
| **G10 — DSH path-isolation limitation** | O3 dedicated registry/audit daemon (Phase A+B+C): out-of-workspace root `/var/lib/dsh-registry-writer/`, dedicated UID `dsh-writer`, write-path migration (registry_write/audit_append/project_write → daemon IPC + HMAC), H4 projects extension, no direct-fs fallback, fail-closed. **Two-principal trust boundary COMPLETED 2026-09-01 20:02** (`dsh-control` uid 997 provisioned; credential rotated + regrouped to `dsh-writer:dsh-control 0640`; `administrator` revoked from `dsh`/`dsh-writer`; `socket_group: dsh-control`; daemon restarted → post-rotation credential loaded). O5 containment applied (raw-write actor set `{zeko, cto}`) | Full regression **3115 pass / 19 skip / 0 fail**; G10 339 pass/4 skip; O3 daemon 50 pass; phase5_security 14 pass; validate-config 194 pass/0 fail; compileall 0 errors. **C1 credential confidentiality verified explicitly**: 4 independent read paths + socket connect + all 4 daemon roots **DENIED** to uid 1000 (the role-agent principal). Live `health`/`registry_write`/`registry_read`/`audit_append`/`audit_verify` PASS as `dsh-control` — **operator-attested, not re-derivable from the sandbox by design** | `tests/g10/` · `tests/g10/o3-daemon/` · `0015` (v1) · `0016` (H5 decision) · `0018` (leak root cause) · `0019` (fix blocked) · `0020` (partial fix/drift) · `0021-h5-closure-package-v2-wsl-final-verification.md` (C1–C5 evidence) · **`0022-h5-approval-record-v2.md` (H5 APPROVED — current authority)** | **Deterministic proof** (project-layer logic) + **live operational verification** (operator-attested) | **Credential leak (`0018`) CLOSED.** C1 PASS · C2 PASS · C3 PASS (direct protected writers = **ZERO**; deny-before-mutation confirmed, file absent after) · C4 PASS (strengthened — the 19:03–20:02 daemon-unreachable window was a live negative proof: `WriterUnavailable` on all channels, no write landed by any route) · C5 PASS. **O4 upstream DSH capability residual** remains separately tracked. Residual note: uid 1000 retains **inert** stale process groups 985/986 from a pre-revocation login; the group DB no longer grants them and nothing in the deployment is grouped 985/986 | **CLOSED** (project-layer, per H5 v2). All six closure-gate conditions (`0005` §1.2) satisfied simultaneously: C1 ✅ · C2 ✅ · C3 ✅ · C4 ✅ · C5 ✅ · C6 ✅ (H3 + H4 + **H5 APPROVED 2026-09-01 against `0021`**, recorded in `0022`). Zero drift verified immediately before recording. The earlier H5 (`0016`, granted on `0015`) is **preserved but SUPERSEDED** — `0018` falsified `0015`'s host facts (the credential was readable by `{zeko, cto}` at that time) and the deployment has materially changed. **Not self-approved.** O4 upstream DSH-layer residual **NOT** closed by this decision |
| **G11 — Full recovery cycle → COMPLETE** | `orchestrator/execution/recovery_runtime/driver.py` — `run_recovery_cycle()` composing `RecoveryController` + `ExecutionEngine` | 8 recovery-runtime tests pass: full cycle, no blind retry, no authority expansion, stale-state refusal, restoration verification | `tests/orchestrator/execution/test_recovery_runtime.py` (8) | **Deterministic proof**; live-DSH variant **BLOCKED** (no mount) | **Accepted residual**: live recovery→COMPLETE not exercised; requires mount | **CLOSED** (deterministic) |
| **G12 — Role runtime validation (6 non-cto roles)** | `tests/phase5_role_validation/harness.py` — resolution, toolFilter consistency, prohibited tools, subdelegation denial per role | 28 role-validation tests pass; live provenance checks honestly BLOCKED (no mount); only CTO has Phase-3 live evidence | `tests/phase5_role_validation/test_role_validation.py` (28) | **Deterministic proof** for all 7 roles; **real DSH proof** only for CTO (Phase-3 INT-01/07) | **Blocking residual**: live dispatch acceptance for zeko/cfo/kai/somad/badsector/nova unverified | **CLOSED** (deterministic) |
| **G13 — Prompt-injection / external-content** | Deterministic defenses verified: authority keys stripped (`build_task_context`), `assert_no_authority_in_payload`, subdelegation denial by actor, reported-success ≠ verification | 8 external-content tests + G10 negatives pass (14 total in `tests/phase5_security/`) | `tests/phase5_security/test_external_content_data.py` | **Deterministic proof** of adapter data-not-instructions treatment; DSH-native posture **UNKNOWN**; no claim | **Blocking residual** (for any injection claim): live DSH child behavior under injection payloads + DSH driver-internal isolation UNVERIFIED | **OPEN** (defenses verified; full closure UNKNOWN — no claim) |

---

## 2. Status roll-up (G1–G13)

| Verdict | Count | Gaps |
|---|---|---|
| **CLOSED** (deterministic / readiness / project-layer) | 12 | G1, G2, G3, G4, G5, G6, G7, G8, G9, **G10**, G11, G12 |
| **OPEN** | 1 | G13 (injection closure UNKNOWN) |
| **BLOCKED** (live/L3 execution conditions) | 0 separate — see residuals | G2/G3/G5/G6/G7/G8/G9/G11/G12 carry blocking residuals for live/L3 claims |

**Precise wording — no gap is "CLOSED" at a level it did not reach:**
- G1, G4, G9, G11, G12 are closed at the **deterministic** level (G4 also has a Phase-3 live observation).
- G2, G3, G6, G7, G8 are closed as **readiness mechanisms**; their *availability* (mount, answerer, UID, signed plan, live bundle) remains open operational/L3 conditions.
- G5 is closed as **verifier infrastructure**; the live L3 run it enables is not executed.
- G10 is **CLOSED at the project-layer** as of 2026-09-01, per **H5 APPROVED against `0021`** (decision record `0022`, closure gate `0005` §1.2). The operator completed the two-principal trust boundary at 20:02, and all six conditions hold simultaneously: the `0018` credential leak is closed with confidentiality verified explicitly (4 read paths + socket + all 4 daemon roots DENIED to the role-agent principal), direct protected writers are **ZERO**, no-fallback is proven by a live outage window, and regression is 3115/19/**0 failed**. Per `0005` §1.1 only the Human may decide H5, and the Human did — no test or session decided it, and it was not self-approved. The prior H5 (`0016`) is preserved but superseded: it was granted on `0015`, whose host facts `0018` falsified, and it describes a materially different deployment (§13). The **O4 upstream DSH-layer gap remains separately tracked and is NOT closed** by this decision, so G10 is closed at the project-layer only — not at the DSH layer.
- G13 remains **OPEN** and is NOT closed by any test in this matrix.

---

## 3. Security levels (current, authoritative)

| Level | Controls/gaps at this level | Basis |
|---|---|---|
| **L1 (project control-plane logic)** | Authority gate, delegation scope, execution gate, state transition, audit integrity, recovery, verification, role capability matrix (deterministic tests) | Green deterministic suites (`tests/authorization/` 91, `tests/adversarial/` 42, unit + orchestrator runtime tests) |
| **L2 (DSH-native config / live)** | toolFilter role boundaries (config), `subagent_<id>` instances (config), session sandbox `workspace-write` + `ask` (session policy) | Phase-3 live INT-01/07/11/12 bundles (`valid=true`), 75 live_dsh contract tests, ISO-LIVE CTO evidence |
| **L2-LIVE (real DSH proof)** | INT-01 full lifecycle, INT-07 execution-time revocation DENY, INT-11 parallel collection, INT-12 failure propagation + recovery entry | `audit/runtime/INT-{01,07,11,12}/` QA-validated bundles |
| **L3 (independently verified runtime)** | **ZERO controls** | No bundle satisfies P1–P4; no live L3 run; IO-2 fails on same-UID host; rehearsal bundles fail LV10 by design |
| **UNKNOWN** | G13 prompt-injection (DSH layer); per-session sandbox limitation (PS-2); DSH driver-internal content isolation | No claim made anywhere (ADR 0001 UNKNOWN #1; security/0001..0003 disclaimers) |

**Promotion rule (unchanged, binding):** a control moves up only with new evidence at the next level. No test in this consolidation promotes any control.

---

## 4. L3 readiness verdict

**L3 STATUS: NOT READY — infrastructure READY to rehearse, NOT ready to claim.**

- **Ready (deterministic, tested):** 8 reference oracles (O1), verifier subprocess (P2 machinery), independence checklist IO-1..10 (with honest IO-2 demotion), 13-item evidence bundle (E1..E13), preflight PF-* checks, replay/reproducibility (P4), rehearsal path, claim gate `evaluate_l3_claim()`, signed-plan validation (O4), UID readiness. 131 L3 tests pass.
- **NOT ready (blocking, none attempted):**
  1. **Separate UID / credential (IO-2)** — same-UID sandbox ⇒ `l3_claim_possible=False`.
  2. **Human-signed plans with real identity (O4)** — requires approval answerer (G3) + a real Human; fixtures are inert templates.
  3. **Live DSH session (P1)** — `LiveDSHRuntimeDriver` returns BLOCKED; `runner.py` refuses `--mode live`.
  4. **Authorized run** — Human acceptance of `docs/security/0003` §15, re-baseline to `workspace-write + ask`, production control-plane code (B1).
- **No L3 claim exists. No live L3 run has executed. No rehearsal bundle is L3 evidence.**

---

## 5. Production-readiness verdict

**PRODUCTION STATUS: NOT PRODUCTION-READY.**

The deterministic runtime and the real-DSH bridge are proven (L2-LIVE for INT-01/07/11/12), and the Phase-5 test suite is green (documented **1597 passed, 15 skipped**). Green tests do not equal production readiness. The following are explicit unsatisfied acceptance conditions:

| # | Condition | State | Class |
|---|---|---|---|
| 1 | D4/D7 mount verified for the session + `DSH_LIVE_BRIDGE_ACTIVE=1` | marker **unset**; per-session re-verification required | Blocking (live path) |
| 2 | Approval answerer live (or pre-recorded `approval-<id>` refs) for interactive/HIGH-risk | prompts **disabled** | Blocking (approval-dependent execution) |
| 3 | Live-DSH proof for Phase-5 changes (G1/G9/G11/G12 live variants) | **absent** — all Phase-5 live variants BLOCKED | Blocking (L2-LIVE evidence) |
| 4 | G10 DSH-layer path isolation | **CLOSED (project-layer)** as of 2026-09-01 — H5 APPROVED against `0021`, recorded in `0022` (§13). Operator completed the two-principal boundary at 20:02; C1–C5 all satisfied, credential leak CLOSED, direct protected writers ZERO, regression 3115/19/0. **O4 upstream DSH-layer residual remains** (raw-write `{zeko, cto}`), separately tracked and NOT closed | Project-layer CLOSED; O4 residual tracked (accepted for V1) |
| 5 | G13 prompt-injection posture | **OPEN/UNKNOWN** — no claim | Blocking for any injection claim |
| 6 | Independent verification for HIGH-risk `independent` categories (VER-2) | **BLOCKED** (L3-1/VER-2) | Blocking (HIGH-risk execution) |
| 7 | Provider 429 backoff/scheduling | not implemented (REC-G4-1) | Accepted residual (operational) |

**Verdict: READY_WITH_CONDITIONS at the deterministic-runtime level; NOT production-ready at the live-DSH level.** Production use requires closing conditions 1–3 (and 6 for HIGH-risk), with 4–5 recorded as OPEN and 7 as an accepted operational residual.

---

## 6. Remaining blockers (exact)

| Blocker | Blocks | Source |
|---|---|---|
| **B1 — D4/D7 mount absent / marker unset** | All live variants of G1/G9/G11/G12; live ISO-LIVE-006; L3 P1 | environment/0001 ENV-MOUNT-1; master gate §1 |
| **B2 — Approval answerer unavailable** | Interactive + HIGH-risk approval; L3 signed plans (G7/O4); approval-dependent tasks | environment/0001 ENV-APPROVAL-1; phase-4 §4.2 |
| **B3 — Same-UID sandbox (IO-2 fail)** | Any L3 claim; independent verifier promotion | security/0007 §1.2; l3/0001 §3.1 |
| **B4 — `LiveDSHRuntimeDriver` live dispatch refused** | Live L3 run (P1); no committed `audit/l3/` bundle | l3/0002 §8; security/0006 §6 |
| **B5 — RESOLVED 2026-09-01: G10 project-layer CLOSED (H5 APPROVED against `0021`, record `0022`); O4 upstream DSH capability residual remains** | No longer blocks the G10 closure gate. The O4 residual blocks only DSH-layer path-isolation for raw-write `{zeko, cto}`, which requires per-agent/path-level sandbox capability absent in 0.1.1-rc.2 | Operator completed `0018` §4.4 steps 1–5: `dsh-control` provisioned, credential rotated + regrouped, `administrator` revoked from `dsh`/`dsh-writer`, `socket_group: dsh-control`, daemon restarted 20:02:11 (post-rotation credential). C1–C5 verified in `0021`; H5 recorded in `0022` with zero pre-recording drift. **Standing caveat, not withdrawn:** the `dsh-control` PASS results underpinning C5's live arm are **operator-attested** and cannot be independently re-derived from inside the sandbox — that impossibility is exactly what makes C1 pass. O4 remains a separate upstream capability gap, not a G10 closure condition |
| **B6 — G13 OPEN/UNKNOWN (injection)** | Any prompt-injection security claim | security/0001-g10-g13 §2; security/0002 §4 |
| **B7 — Independent verifier for HIGH-risk categories (VER-2)** | HIGH-risk `independent` execution; L3 promotion of verification control | phase-4 matrix VER-2; acceptance-matrix VF-4 |
| **B8 — No production-wired approval path / session-policy drift guard** | Guaranteed `workspace-write + ask` baseline over time | phase-4 §4.6 (PB-1); environment/0001 §4 |

---

## 7. Exact prerequisites for final acceptance

Final acceptance of Phase-5 (and the path to production/L3) requires **all** of the following. None is satisfied by this matrix; this document only records them.

1. **Live-DSH evidence wave**: mount D4/D7 (Human-approved, reversible) → set `DSH_LIVE_BRIDGE_ACTIVE=1` → re-run live variants: backend selection (G1), ISO-LIVE-006 (G9), recovery→COMPLETE (G11), per-role dispatch ×6 (G12) → record `audit/runtime/` bundles.
2. **Approval answerer**: enable approval prompts + configure a live Human answerer (or pre-record signed `approval-<id>` references) — unblocks interactive/HIGH-risk execution and L3 signing (G3/G7).
3. **L3 execution**: provision a separate-UID verifier host (IO-2) → Human-signed `plan.json` per scenario (O4) → run authorized live L3 scenarios (P1) → commit `audit/l3/<scenario-id>/` bundles with `l3_claim=true` → promote controls per `docs/security/0003` §10/§15.
4. **G10 closure decision**: **PENDING on C6/H5 only, as of 2026-09-01 20:25 (supersedes both the earlier "SATISFIED (H5 APPROVED)" state and the 19:03 "C3 PARTIAL / C5 FAIL" state — see §12).** The operator completed the two-principal trust boundary at 20:02 (`dsh-control` uid 997 provisioned; credential rotated + regrouped `dsh-writer:dsh-control 0640`; `administrator` revoked from `dsh`/`dsh-writer`; `socket_group: dsh-control`; daemon restarted → post-rotation credential loaded). **C1 PASS** (credential confidentiality verified explicitly — 4 read paths, socket connect, and all 4 daemon roots DENIED to uid 1000, the role-agent principal) · **C2 PASS** · **C3 PASS** (direct protected writers = ZERO; deny-before-mutation confirmed with the file absent afterwards) · **C4 PASS** (strengthened: the 19:03–20:02 daemon-unreachable window was a live negative proof) · **C5 PASS** (3115/19/**0 failed**, 194 validate-config, compileall clean; live arm restored, operator-attested) · **C6 PENDING**. No technical work remains; closure requires a **fresh Human H5 against `0021`**, since per `0005` §1.1 no test or session may decide it and the prior H5 (`0016`) described a materially different deployment. DSH-layer prevention remains an O4 upstream capability gap. Historical options: O5 (narrow bash surface) applied 2026-08-31; O3 (out-of-process registry) chosen as the closure arm; O2 (registry relocation) not needed; O4 (upstream DSH capability) remains the only full-prevention arm.
5. **G13 resolution**: an authorized adversarial live test of DSH child behavior under injection payloads + documented DSH driver-internal content-isolation findings; only then may an injection claim be considered (ADR 0001 UNKNOWN #1).
6. **HIGH-risk independent verification (VER-2)**: an independent measurement channel per action category before HIGH-risk `independent` execution can ALLOW.
7. **Operational envelope**: session-policy baseline guard, provider 429 backoff (REC-G4-1) if desired, CI/CD for live-DSH regression, and documented backup/restore — per phase-4 operational residual.
8. **Honesty gate**: re-run the complete suite and re-validate the four INT bundles after any of the above; no claim is valid on stale evidence.

---

## 8. Scope check

**In scope (written this session):** `docs/phase-5/final/0001-security-closure-matrix.md` (this file) only.

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, `tests/` (all), DSH core/profile/preset/session policy, any `docs/` outside `docs/phase-5/final/`. No implementation change. No re-test executed. No failure downgraded. No control declared L3. No production-readiness declared.

---

---

## 9. Addendum A — O5 applied (post-publication, 2026-08-31)

On 2026-08-31 the Human **APPROVED and APPLIED O5** — removed `write`/`edit` from `somad` and `nova` toolFilter allow sets (containment step), applied consistently across mapping, instance config, policy files, and the live D4/D7 composition. Raw-write actor set is now `{zeko, cto}`. **G10 row (§1) remained OPEN** at that time; O3 (dedicated registry/audit writer) was HOLD. Full record: `docs/phase-5/security/g10/implementation/0002-o5-application-record.md`. This addendum does not retract any prior row.

## 10. Addendum B — G10 CLOSED by H5 (Human approval, 2026-09-01)

On 2026-09-01 the Human **APPROVED H5** — the G10 closure decision — based on the evidence package at `docs/phase-5/security/g10/o3/execution/0015-h5-closure-package.md`. The O3 daemon (Phase A+B+C) is deployed and verified: all three protected roots (`state/registry/**`, `audit/**`, `state/projects/**`) are isolated outside the workspace, the write path is fully migrated to daemon IPC + HMAC, no direct-fs fallback exists, and fail-closed is verified. The G10 row (§1) is updated to **CLOSED** (project-layer). The O4 upstream DSH capability gap (raw-write `{zeko, cto}` via raw DSH tool) remains a **separately tracked residual** — NOT closed by this decision. H5 decision record: `docs/phase-5/security/g10/o3/execution/0016-h5-approval-record.md`.

G13 remains OPEN/UNKNOWN. L3 remains NOT CLAIMED. Production readiness remains NOT DECLARED. No DSH, session-policy, or role change was made.

## 11. Addendum C — G10 returned to OPEN by verified host drift (2026-09-01 19:03)

**This addendum supersedes Addendum B on the G10 row status only. It retracts nothing and preserves every prior record.**

After H5 was approved, `docs/phase-5/security/g10/o3/execution/0018-hmac-trust-boundary-root-cause-and-remediation.md` proved a credential trust-boundary leak that H5 had not accounted for: the control-plane client and the sandboxed role agents were **one OS principal** (`administrator`, uid 1000), which held `dsh-writer`/`dsh` group membership, so every `bash`-capable role agent (`{zeko, cto}`) could read the `0640` HMAC credential and drive sanctioned O3 IPC as if it were the control plane. `0019` recorded that no remediation step was executable from the agent session (no root, `CapEff=0`).

**At 2026-09-01 18:53 an operator applied `0018` §4.4 steps 1–3** — created the `dsh-control` user/group, rewrote and regrouped the credential to `dsh-writer:dsh-control 0640`, and revoked `administrator` from both `dsh` and `dsh-writer` (independently corroborated by `/etc/group-`). **Steps 4 and 5 were not applied.**

Fresh probes at 19:03 (`0020`):

| Property | State |
|---|---|
| Sandbox reads the credential | **DENIED** — leak CLOSED |
| Sandbox connects the IPC socket | **DENIED** — leak CLOSED |
| Control-plane `registry_write` / `audit_append` / `project_write` / `audit_verify` | **`WriterUnavailable`** — fail-closed, no write lands by any route |
| Live daemon `health` / `registry_read` / `audit_verify` (the C5 evidence in `0016` §3) | **NOT RE-DERIVABLE** from any principal available in-session |
| Daemon in-memory credential | **PRE-ROTATION** — started 17:24:58, secret rewritten 18:53:05, `NRestarts=0`, no SIGHUP reload path in `registry_writer/` |
| Live `socket_group` | still `dsh` (985); `dsh-control`'s only group is 984 → a `dsh-control` process could not connect even with the new credential |

**Consequence:** C1 PASS, C2 PASS (static), **C3 PARTIAL** (path switched to a destination the control plane can no longer reach), **C4 PASS and strengthened** (the outage positively demonstrated the no-silent-fallback invariant in production configuration), **C5 FAIL — live arm not re-derivable**, C6 approval preserved with its C3/C5 basis superseded. The closure gate (`0005` §1.2) requires all six at once, so the **G10 row returns to OPEN**.

The security posture is *better* than at H5 — the leak that was open when H5 was granted is now closed. The regression is on the availability/verifiability axis and is one operator transaction from resolution (`0020` §7).

Full rebaseline, probe records, evidence classification, and the exact operator runbook: `docs/phase-5/security/g10/o3/execution/0020-hmac-remediation-partial-host-drift-rebaseline.md`. H5 decision record (`0016`) and blocked-execution record (`0019`) are preserved unmodified.

G13 remains OPEN/UNKNOWN. L3 remains NOT CLAIMED (`l3_claim_possible=False`). Production readiness remains NOT DECLARED. No DSH, session-policy, or role change was made. No test was weakened.

*Status of Addendum C (historical, superseded on C3/C5 by Addendum D): G10 OPEN with C3 partial and C5's live arm not re-derivable, as observed at 19:03.*

## 12. Addendum D — G10 remediation COMPLETE; C1–C5 satisfied; open on C6/H5 only (2026-09-01 20:25)

**This addendum supersedes Addendum C on C3 and C5. It retracts nothing; Addendum C remains accurate for its 19:03 timestamp.**

**At 2026-09-01 20:02 an operator completed `0018` §4.4 steps 4–5**, finishing the remediation Addendum C found half-applied:

| Item | Addendum C (19:03) | Now (20:25) |
|---|---|---|
| `socket_group` (live config) | `dsh` (985) | **`dsh-control`** |
| Daemon | PID 201404, started 17:24:58 (**pre**-rotation) | **PID 389112, started 20:02:11 (post-rotation)** |
| Socket owner:group:mode | unreadable | **`dsh-writer:dsh-control 0660`** (operator-attested) |
| `dsh-control` execution path | none | **provisioned** (operator-attested) |
| Control-plane IPC | `WriterUnavailable` everywhere | **PASS as `dsh-control`** (operator-attested) |

The stale-credential gap Addendum C flagged is closed by direct observation: the secret was written at 18:53:05 and the daemon started at 20:02:11, so it loaded the **post-rotation** credential.

**C1–C5 re-derived and all satisfied** (`0021`):

- **C1 PASS** — credential confidentiality verified explicitly as uid 1000, the exact principal every role agent runs as: `cat`, `dd`, `sha256sum`, and Python `open()` all **DENIED**; socket `connect()` **DENIED**; daemon-root traverse **DENIED**; write probes into all four daemon roots **DENIED**. Kernel DAC, the same mechanism that denies `/etc/shadow`. Two separate OS principals now exist (`dsh-writer` 999, `dsh-control` 997), repairing the architectural defect `0018` §2 identified.
- **C2 PASS** — `state/projects/**` extension unchanged; Phase B/C not repeated (no drift).
- **C3 PASS** — exhaustive O3-FC-005 scan: **zero** direct protected writers in production code. The only `atomic_write` call site (`execution_gate.py:284`, inside `write_through()`) is preceded by `authorize_write()` at line 279, which raises `Denied` for protected targets before any mutation. Confirmed at runtime: all three protected roots DENIED with **the file absent afterwards**, while a non-protected control target was correctly allowed.
- **C4 PASS, strengthened** — no `except → atomic_write` branch exists anywhere; and the 19:03–20:02 daemon-unreachable window served as a **live negative proof**: all four sanctioned channels returned `WriterUnavailable` and no write landed by any other route, in production configuration rather than a fixture.
- **C5 PASS** — full regression **3115 passed, 19 skipped, 0 failed**; G10 339/4s; O3 daemon 50; phase5_security 14; authorization 178; adversarial 105; resilience 45/1s; audit_hardening 29; recovery_hardening 33; validate-config 194/0; compileall 0 errors. Rollback READY (`o3-pre` 5/5 hashes re-verified). Live operational arm restored (operator-attested).

**Evidence-class discipline:** every *denial* above was directly executed by the agent (uid 1000). Every `dsh-control` *PASS* is **operator attestation** and is not re-derivable from inside the sandbox — four corroboration attempts (`sudo -u dsh-control`, `stat` the socket, `ls /proc/<pid>/fd`, socket `connect`) were all correctly refused. That impossibility is precisely what makes C1 pass; it is recorded as attestation and never promoted to direct observation.

**At the time Addendum D was written, G10 was open on C6 only.** No technical work remained. Per `0005` §1.1 only the Human may decide H5, and the 2026-09-01 H5 (`0016`) was **preserved but not reusable** for this closure: it was granted on `0015`, whose host facts `0018` subsequently falsified (the credential was readable by `{zeko, cto}` at the moment of approval), and it describes a different deployment (old principal, old credential, old socket group, old PID). Reusing it would have inferred authority from stale text, against the explicit instruction recorded in `0016` §1. **H5 was not self-approved.** That C6 condition has since been satisfied by an explicit Human decision — see Addendum E.

Full package, probe records, evidence classification, and the H5 decision brief: `docs/phase-5/security/g10/o3/execution/0021-h5-closure-package-v2-wsl-final-verification.md`. `0015`, `0016`, `0018`, `0019`, `0020` preserved unmodified.

**Not done and not claimed by Addendum D:** G13 not run (OPEN/UNKNOWN, 0/63 live evidence, pre-gate still fails). L3 not run (NOT CLAIMABLE, `l3_claim_possible=False`). O4 upstream DSH capability residual not closed. Production readiness **NOT DECLARED**. No DSH, session-policy, or role change. No test weakened.

*Status of Addendum D (historical, superseded on C6 by Addendum E): G10 open on C6/H5 only, C1–C5 satisfied, as recorded at 20:25.*

## 13. Addendum E — H5 APPROVED; G10 CLOSED at the project layer (2026-09-01)

**This addendum supersedes Addendum D on C6 only. Addenda A–D are preserved and remain accurate for their timestamps.**

The Human **explicitly APPROVED H5 against the `0021` evidence package.** Decision record: `docs/phase-5/security/g10/o3/execution/0022-h5-approval-record-v2.md`.

**All six closure-gate conditions (`0005` §1.2) are now satisfied simultaneously:**

| Condition | Verdict | Basis |
|---|---|---|
| **C1** A+B isolation **+ credential confidentiality** | ✅ PASS | `0021` §3 — 4 secret-read paths, socket connect, root traverse, and write probes into all 4 daemon roots, all DENIED to uid 1000 (the role-agent principal) |
| **C2** `state/projects/**` extension (H4) | ✅ PASS | `0021` §4 — no drift; Phase B/C not repeated |
| **C3** write path switched, direct protected writers **ZERO** | ✅ PASS | `0021` §5 — O3-FC-005 exhaustive scan; deny-before-mutation confirmed, file absent after |
| **C4** no silent direct-fs fallback | ✅ PASS | `0021` §6 — no `except → atomic_write` branch; live negative proof from the 19:03–20:02 outage |
| **C5** verification passes | ✅ PASS | `0021` §7 — 3115 passed / 19 skipped / **0 failed**; validate-config 194/0; compileall clean; rollback READY |
| **C6** Human approval H3 + H4 + H5 | ✅ PASS | H3 ✅ · H4 ✅ · **H5 APPROVED 2026-09-01 against `0021`** (`0022`) |

**G10 = CLOSED (project-layer).** A raw direct-filesystem write to `state/registry/**`, `audit/**`, or `state/projects/**` bypassing the sanctioned channel is prevented: the daemon owns all three roots outside the workspace under a dedicated UID, the control plane reaches them only via HMAC IPC as a **separate OS principal** (`dsh-control` uid 997), no fallback exists, and the credential is confidential to the principal every role agent runs as.

**Integrity of the decision:** a pre-recording drift gate re-verified the host against the `0021` baseline (daemon PID 389112 / start 20:02:11 / `NRestarts=0`; secret `dsh-writer:dsh-control 0640` size 65 mtime 18:53:05.300162076 inode 31422; root `dsh-writer:dsh-control 0750`; `socket_group: dsh-control`; group DB unchanged; uid 1000 secret read and socket connect both DENIED) — **zero drift**. The approval therefore attaches to the exact state that was verified. H5 was not self-approved, and no approval, delegation, signature, or provenance was fabricated.

**Standing caveat, not withdrawn now that the decision is favourable:** the `dsh-control` PASS results underpinning C5's live operational arm are **operator-attested**, not independently re-derivable from inside the agent sandbox. Four corroboration attempts were made and all were correctly refused. That impossibility is precisely what makes C1 pass. This limitation was disclosed in `0021` §2/§9 *before* the decision and is restated here unchanged.

**Explicitly NOT closed or claimed by this decision:**

- **O4 upstream DSH capability residual** — raw-write `{zeko, cto}` via raw DSH tools. Separately tracked; requires per-agent/path-level sandbox capability absent in 0.1.1-rc.2. G10 is closed at the **project layer only**, not the DSH layer.
- **G13** — remains OPEN/UNKNOWN. Not executed. A fresh pre-gate confirms it is still BLOCKED (marker unset, all 7 D4/D7 instances NOT_MOUNTED, backend `unavailable`, `LiveDSHRuntimeDriver` BLOCKED, no fail-fast config, no §15 Human acceptance). Live evidence remains **0/63**.
- **L3** — remains NOT CLAIMABLE (`l3_claim_possible=False`).
- **Production readiness** — **NOT DECLARED.** Per `0005` §1.5, G10 closure unblocks exactly one gate and is necessary but not sufficient. Blockers B1, B2, B3, B4, B6, B7, B8 all remain.
- No DSH core, session-policy, or role change was made. Nothing was mounted; no bridge marker was set.

**Known test-suite consequence, disclosed:** `tests/g13/gate/test_g13_live_recheck.py` encodes *"G10 is OPEN"* as a state fact — `test_axis_11_g10_open_blocking` (line 312) requires the literal `**OPEN**` in this matrix's G10 row, and `recheck_verdict()` (line 82) hardcodes `g10_blocking = True`. Both are now factually stale. **No test was modified, weakened, skipped, or deleted** — updating them was outside the authorization for this step and is reported as a blocker requiring explicit approval.

*Status: CLOSURE MATRIX + O5 addendum (A) + G10/H5 addendum (B) + G10 drift addendum (C) + G10 remediation-complete addendum (D) + **H5-approved / G10-closed addendum (E, current)**. G10 = **CLOSED (project-layer)** — C1–C6 all satisfied, H5 APPROVED 2026-09-01 against `0021` (record `0022`), zero pre-recording drift, not self-approved. G13 remains **OPEN/UNKNOWN** (0/63 live, pre-gate BLOCKED). L3 remains **NOT CLAIMABLE**. O4 upstream DSH-layer residual remains separately tracked and NOT closed. Production readiness remains **NOT DECLARED**.*

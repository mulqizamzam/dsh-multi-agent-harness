# Phase 5 — MASTER SECURITY AUDIT (Authoritative Final Baseline)

- **Milestone**: Phase 5 / Final — MASTER SECURITY AUDIT
- **Status**: **AUTHORITATIVE AUDIT** — evidence-driven re-assessment of all 10 domains against **current live state** (2026-08-31 18:51 UTC). No production changes, no DSH changes, no profile/preset/session-policy changes, no role changes, no live G13/L3 execution.
- **Write scope**: `docs/phase-5/final/master-audit/` + `tests/phase-5/final/master-audit/`
- **Method**: Re-inspect every material claim from the current environment. Do not rely on prior reports without live re-verification. Flag stale/contradictory evidence explicitly.

---

## AUDIT CONTEXT — CURRENT LIVE STATE (verified this session)

| Fact | Current value | Source |
|------|--------------|--------|
| UTC time | 2026-08-31 18:51:58 | `date -u` |
| DSH version | `0.1.1-rc.2` | `dsh --version`, `package.json` |
| File sandbox policy | `workspace-write` | runtime context |
| Approval policy | `ask` | runtime context |
| `DSH_LIVE_BRIDGE_ACTIVE` | **UNSET** | `env` |
| `DSH_WEB_URL` | **UNSET** | `env` (headless session) |
| `DSH_HOME` | unset in this shell (files exist at `/home/administrator/agent-workspace/.dsh`) | `env` |
| Host UID | 1000 | `id -u` |
| Backend kind | `BackendKind.UNAVAILABLE` | `probe_backend_kind()` |
| D4/D7 mount probes | all 7 FALSE | `probe_all_instances_mounted()` |
| Approval answerer | `APPROVAL_COMPOSED` (bundles present) — NOT interactive (web_session=False, web_server_reachable=False) | `approval_readiness()` |
| `LiveDSHRuntimeDriver` | returns BLOCKED (stub; refuses live dispatch) | `runtime_driver.py` |
| L3 claim possible | `False` | `assess_environment()` |
| Rehearsal ready | `True` | `assess_environment()` |
| L3ENV blockers (live) | **7**: UID-2, ANS-1, ANS-2, D4D7-1, D4D7-2, D4D7-3, PLAN-REAL | `assess_environment()` |
| O5 applied | VERIFIED: somad/nova have NO write/edit in cordis.patch.yml allow | live patch inspection |
| Raw-write actor set | `{zeko, cto}` (post-O5) | config + live patch |

### ENVIRONMENT DRIFT FROM PRIOR REPORTS (CRITICAL FINDING)

| Prior report claim | Current state | Impact |
|-------------------|--------------|--------|
| Rebaseline: "web GUI session active (DSH_WEB_URL=http://127.0.0.1:13080)" | **DSH_WEB_URL UNSET** — headless session | All approval-dependent assertions (ANS-1/2 PASS, 3 blockers) are **INVALIDATED** in this session |
| Rebaseline: "L3 blockers = 3" | **L3 blockers = 5-7** (ANS-1/2 are blockers in headless + D4D7-1/2 probe-env artifact) | Blocker count returned to pre-repair level; any claim of "3 blockers" is environment-specific |
| Rebaseline: "approval answerer interactive-ready" | **composition only** — not interactive-ready (web_session=False) | Interactive approval path is genuinely BLOCKED in this session |
| Rebaseline date: 2026-09-01 | Current UTC: 2026-08-31 18:51 — date anomaly | Report may be from a different timezone or session |
| Acceptance test `test_environment_facts_consistent_with_probe` | **FAILS**: asserts ANS-1/2 NOT blockers, but live probe says they ARE | The acceptance matrix's own lock test no longer passes on this host |

---

## MASTER VERDICTS

### PRODUCTION_VERDICT

**NOT PRODUCTION-READY — BLOCKED by G10 (OPEN), G13 (OPEN/UNKNOWN), absence of live-DSH proof, and current headless environment.**

| Condition | Status |
|-----------|--------|
| D4/D7 mount verified + marker set | **BLOCKED** (marker unset, backend UNAVAILABLE) |
| Approval answerer interactive (this session) | **BLOCKED** (headless; DSH_WEB_URL unset) |
| Live-DSH proof for Phase-5 changes (G1/G9/G11/G12) | **BLOCKED** (no mount) |
| G10 DSH-layer path isolation | **OPEN** — blocking |
| G13 prompt-injection posture | **OPEN/UNKNOWN** — blocking for any claim |
| HIGH-risk independent verification (VER-2) | **BLOCKED** |
| Provider 429 backoff, baseline guard, CI/CD | **DEFERRED** |

### SECURITY_VERDICT

| Level | Status | Basis |
|-------|--------|-------|
| **L1 (project control-plane logic)** | **CLOSED** | All deterministic suites green (authorization 178, adversarial 105, phase5_security 14, audit_hardening 29, observability 42, evidence 36, resilience 45+1s, recovery 33) |
| **L2 (DSH-native config)** | **CLOSED** | toolFilter, role instances, session sandbox `workspace-write + ask`; O5 verified live in cordis.patch.yml |
| **L2-LIVE (real DSH proof)** | **PARTIAL** | INT-01/07/11/12 bundles valid=true; all Phase-5 live variants BLOCKED (no mount) |
| **L3 (independently verified runtime)** | **ZERO controls** | Same-UID sandbox prevents any L3 claim; LiveDSHRuntimeDriver refuses |
| **UNKNOWN** | G13 DSH-native, DSH driver-internal content isolation, per-session sandbox limitation |

### L3_VERDICT

**NOT CLAIMED — zero controls are L3.** Current live blockers (headless session):

1. **L3ENV-UID-2** — separate UID: same-UID host (uid=1000)
2. **L3ENV-ANS-1** — Human answerer: unavailable (headless session; DSH_WEB_URL unset)
3. **L3ENV-ANS-2** — approval path: blocked (no live answerer)
4. **L3ENV-D4D7-3** — live bridge marker: DSH_LIVE_BRIDGE_ACTIVE unset
5. **L3ENV-PLAN-REAL** — no real Human signoff (fixture only)

Additional load-bearing conditions (not probe-blocking but required):
- P1-live absent: LiveDSHRuntimeDriver refuses live dispatch
- Authorized run not granted: no Human acceptance of `docs/security/0003` §15
- G10/G13 OPEN/BLOCKING: project security gates not closed

(L3ENV-D4D7-1/2 also report FAIL in this shell because DSH_HOME is unset — probe-environment artifact; files exist on disk.)

---

## FINAL MATRIX — 10 Audit Domains

### 1. G10 — DSH Path-Isolation Limitation

| Attribute | Value |
|-----------|-------|
| **STATUS** | **OPEN** (BLOCKING) |
| **EVIDENCE LEVEL** | DETERMINISTIC (residual proven) + DSH source inspection (prevention gap) |
| **CURRENT FACT** | O5 applied (containment): actor set {zeko, cto} verified live. O3 designed but NOT implemented (HOLD). O4 requires upstream DSH capability absent in 0.1.1-rc.2. Prevention gap formally proven: raw-write-capable roles can reach `state/registry/**`, `audit/**`, `state/projects/**` via raw DSH tool call bypassing the project channel. |
| **BLOCKER** | Yes — BLOCKING for production |
| **REQUIRED ACTION** | Human decision: implement O3 (dedicated registry/audit daemon) or upgrade DSH for O4 (per-agent/path-level sandbox). O5 already applied. |
| **OWNER** | Human → Engineering |
| **ACCEPTANCE CRITERION** | Per-agent sandbox root OR per-path allow/deny on filesystem tools OR dedicated daemon implemented + verified |

### 2. G13 — Prompt-Injection / External Content

| Attribute | Value |
|-----------|-------|
| **STATUS** | **OPEN** (defenses verified; full closure UNKNOWN) |
| **EVIDENCE LEVEL** | DETERMINISTIC (control plane: 107 g13 tests + 105 adversarial + 14 phase5_security) + UNKNOWN (DSH-native) |
| **CURRENT FACT** | Control-plane resistance VERIFIED: authority keys stripped, malicious result cannot grant authority, subdelegation DENIED, reported SUCCESS ≠ verified. DSH-native behavior UNKNOWN (no real child observable). Prepared live test package BLOCKED on precondition. |
| **BLOCKER** | Yes — BLOCKING for any injection claim |
| **REQUIRED ACTION** | Authorized adversarial live test with REAL DSH child + DSH driver-internal content-isolation findings |
| **OWNER** | Engineering → Operations |
| **ACCEPTANCE CRITERION** | Live DSH child under injection payloads DENIES all injected actions; DSH driver-internal isolation documented |

### 3. L3 — Independent Verification

| Attribute | Value |
|-----------|-------|
| **STATUS** | **BLOCKED** (no claim; zero controls L3) |
| **EVIDENCE LEVEL** | DETERMINISTIC (machinery: 592 l3 tests passed) + REHEARSAL (bundles with l3_claim=false) |
| **CURRENT FACT** | P1: BLOCKED (no live runtime). P2: PARTIAL (IO-1 PID PASS, IO-2 UID FAIL same-UID 1000). P3: CLOSED (≥2 oracle classes). P4: CLOSED (reproducible replay). Evidence bundle: CLOSED (rehearsal). Claim gate: CLOSED (code-enforced, returns false). All 8 scenarios rehearse green with l3_claim=false. |
| **BLOCKER** | Yes — BLOCKING for any L3 claim (5 L3ENV blockers in current headless session) |
| **REQUIRED ACTION** | Provision separate UID, enable approval answerer, set bridge marker, sign real plans, authorize live run |
| **OWNER** | Human + Operations + Engineering |
| **ACCEPTANCE CRITERION** | All 8 bundles with `l3_claim=true` under `audit/l3/` |

### 4. D4/D7 — Live Bridge

| Attribute | Value |
|-----------|-------|
| **STATUS** | **BLOCKED** (live dispatch) / **CLOSED** (static composition) |
| **EVIDENCE LEVEL** | DETERMINISTIC (composition validation) + live probes |
| **CURRENT FACT** | Composition CONSISTENT/VALID: 7 presets present, 7 rows, mapping==policy==instance, allow∩deny=∅, O5 applied. Bridge INACTIVE: marker unset, backend UNAVAILABLE, all 7 mount probes FALSE. |
| **BLOCKER** | Yes — BLOCKING for live dispatch and L3 P1 |
| **REQUIRED ACTION** | Run per-session mount verification → set DSH_LIVE_BRIDGE_ACTIVE=1 → verify backend → smoke dispatch |
| **OWNER** | Operations |
| **ACCEPTANCE CRITERION** | `probe_backend_kind() == real-dsh`; all 7 mount probes True; live smoke dispatch settles with real run id |

### 5. Approval Path

| Attribute | Value |
|-----------|-------|
| **STATUS** | **OPEN/BLOCKED** (composition CLOSED; interactive availability BLOCKED; E2E UNKNOWN) |
| **EVIDENCE LEVEL** | DETERMINISTIC (composition) + L2-config (policy) |
| **CURRENT FACT** | Effective policy: ask (verified). Service composed: YES (DSH bundle base). Answerer surface composed: YES (web-app bundle). Interactive ready: NO (headless session; DSH_WEB_URL unset, web_session=False). E2E: UNKNOWN (no independently re-derivable approval/asked+decided pair in current session log). Headless fail-closed: READY (ask → unavailable → DENY+escalate). |
| **BLOCKER** | Yes — BLOCKING for interactive/HIGH-risk execution and L3 signing |
| **REQUIRED ACTION** | Enable web GUI session (set DSH_WEB_URL) or compose headless answerer row; or supply pre-recorded signed `approval-<id>` references |
| **OWNER** | Operations |
| **ACCEPTANCE CRITERION** | `L3ENV-ANS-1/2` PASS; approval-dependent action ALLOWs through live answerer |

### 6. Front Door

| Attribute | Value |
|-----------|-------|
| **STATUS** | **CLOSED** (L1 deterministic) / **OPEN** (live DSH session integration) |
| **EVIDENCE LEVEL** | DETERMINISTIC (270 tests in isolation) + LOCAL E2E (executed 7 scenarios with FakeSubagentBackend) |
| **CURRENT FACT** | Implementation complete: `orchestrator/entrypoint/` with `run_from_chat` public API. 270 tests pass in isolation. Local E2E proven: all 4 terminal states (COMPLETE/BLOCKED/ESCALATED/ERROR) reachable with honest envelopes, no authority mutation. Adversarial validation: 112 security tests (A–H + static). Combined-run failures (10 tests) are conftest-collection isolation artifact (same documented class as phase4_integration). |
| **BLOCKER** | No — only live-dispatch integration is BLOCKED (shared with D4/D7) |
| **REQUIRED ACTION** | (Optional) Wire live DSH dispatch under the front door when bridge is active; not required for L1 closure |
| **OWNER** | Engineering |
| **ACCEPTANCE CRITERION** | 270 entrypoint tests pass; honest terminal states, no authority mutation |

### 7. Audit / Observability

| Attribute | Value |
|-----------|-------|
| **STATUS** | **CLOSED** (L1 deterministic) |
| **EVIDENCE LEVEL** | DETERMINISTIC (42 observability + 29 audit_hardening + 26 audit consistency + 36 evidence QA) + L2-LIVE (INT bundles) |
| **CURRENT FACT** | Event-id uniqueness: append_log enforces event-<n> sequence. Hash-chain integrity: 29 audit_hardening tests; tamper detection via audit_chain oracle (INVALID/VALID). Correlation: observability 42 tests; INT bundles all valid=true. Audit-as-authority: `audit_is_authority_source` always False. |
| **BLOCKER** | No |
| **REQUIRED ACTION** | None |
| **OWNER** | — |
| **ACCEPTANCE CRITERION** | All audit/observability suites green; INT bundles valid=true |

### 8. Recovery / Verification / Parallel

| Attribute | Value |
|-----------|-------|
| **STATUS** | **CLOSED** (deterministic) / **BLOCKED** (live variant) |
| **EVIDENCE LEVEL** | DETERMINISTIC + L2-LIVE (INT-11/12) |
| **CURRENT FACT** | Verification-before-COMPLETE: CLOSED (entrypoint F-category tests; COMPLETE requires PASSED). No-blind-retry: CLOSED (resilience 45+1s). Authority re-check: CLOSED (execution-time recheck AUTH-INV-06). CAS/stale-state: CLOSED (stale refusal, double-recovery DENY). Parallel safety: CLOSED (INT-11). Live recovery→COMPLETE: BLOCKED (no mount). |
| **BLOCKER** | No (deterministic); live variant blocked by D4/D7 |
| **REQUIRED ACTION** | Mount D4/D7 + run live recovery scenario |
| **OWNER** | Operations |
| **ACCEPTANCE CRITERION** | Live recovery→COMPLETE observed |

### 9. Scope / Concurrency

| Attribute | Value |
|-----------|-------|
| **STATUS** | **CLOSED** (no unauthorized modifications) / **OPEN** (documentation drift) |
| **EVIDENCE LEVEL** | DETERMINISTIC (file inspection + test evidence) |
| **CURRENT FACT** | **No unauthorized modification found**: O5 concurrent-modification disclosure (parallel session) — verified consistent. No out-of-scope writes detected. **Stale/contradictory evidence:** 10 documented discrepancies (see below). **Combined-run test failures:** 10 entrypoint + 3 g10/decision tests fail only in combined run (conftest isolation/ordering artifacts — documented pre-existing class, not scope violations). **Test design limitation:** acceptance/preflight lock tests encode web-GUI assumption (ANS-1/2 not blockers) — fail in headless sessions. This is a test-environment-sensitivity issue, not a code regression. |
| **BLOCKER** | No (documentation drift is a quality concern, not a security blocker) |
| **REQUIRED ACTION** | Reconcile stale documentation with current environment; update tests to handle headless vs web-GUI sessions |
| **OWNER** | Engineering |
| **ACCEPTANCE CRITERION** | All authoritative docs reflect current environment state; tests handle both headless and web-GUI environments |

### 10. Production Readiness

| Attribute | Value |
|-----------|-------|
| **STATUS** | **NOT PRODUCTION-READY** (BLOCKED) |
| **EVIDENCE LEVEL** | DETERMINISTIC (all sub-domains) |
| **CURRENT FACT** | See PRODUCTION_VERDICT above. All blocking conditions confirmed. |
| **BLOCKER** | Yes — multiple |
| **REQUIRED ACTION** | Minimum path: unblock live dispatch, enable approval answerer, resolve G10/G13, authorize L3 |
| **OWNER** | Human + Operations + Engineering |
| **ACCEPTANCE CRITERION** | All 10 domains CLOSED at the required evidence level |

---

## STALE / CONTRADICTORY EVIDENCE (10 findings, this session)

| # | Finding | Severity | Current fact |
|---|---------|----------|-------------|
| S1 | **Rebaseline environment mismatch**: claims web GUI + ANS-1/2 PASS + 3 blockers. Current session is HEADLESS (DSH_WEB_URL unset, web_session=False) → ANS-1/2 BLOCKED → 5-7 blockers. | **HIGH** | Rebaseline's environment snapshot is from a different session context; not portable to arbitrary sessions |
| S2 | **Acceptance + preflight lock tests fail**: test_environment_facts_consistent_with_probe and test_l3_environment_probe_reports_honest_blockers hard-code the web-GUI assumption (ANS-1/2 not blockers). | **HIGH** | Tests pass only in web-GUI sessions; fail in headless; design assumes a specific environment |
| S3 | **Regression counts never reconciled**: 1597 (closure matrix) vs 1642 (final/0005) vs 1898 (l3/final/0001) vs current 2761+15+10F. | **HIGH** | No authoritative "current full regression" count exists in the final docs |
| S4 | **L3 suite counts never reconciled**: 148 vs 275 vs 389 vs 545 vs current 592. | **HIGH** | Same issue: counts grew, never reconciled in final docs |
| S5 | **final/0001 §5-6 + final/0005 §0 stale**: "approval answerer unavailable (prompts disabled)" | **HIGH** | Obsolete `DSH_APPROVAL_PROMPTS_DISABLED`-based claim; also current headless session genuinely has no answerer, but for a different reason (no web session) |
| S6 | **master-integration-gate G5 stale**: says BLOCKED (verifier not built) | **MEDIUM** | Verifier infrastructure was built; G5 should be CLOSED (infrastructure) |
| S7 | **l3/final/0001+0002 + acceptance §11.3 blocker lists**: 5 blockers (including ANS-1/2 as FAIL) | **MEDIUM** | Lists are inconsistent with correction docs; also current headless session makes ANS-1/2 blockers again |
| S8 | **Combined-run test failures**: 10 entrypoint (conftest shadowing) + 3 g10/decision (ordering artifact) | **LOW** | Pass in isolation; documented pre-existing class; not a security regression |
| S9 | **O5 session label inconsistency**: Plan (Session E) vs Application Record (Session A) | **LOW** | Same event, two session labels |
| S10 | **Date anomaly**: rebaseline + front-door reports dated 2026-09-01; current UTC 2026-08-31 18:51 | **LOW** | Likely timezone difference; does not change substantive claims |

---

## EXACT HUMAN DECISIONS REQUIRED (unchanged from acceptance matrix)

| # | Decision | Impact | Status |
|---|----------|--------|--------|
| H1 | Accept G10 residual (V1 containment = detection) | Keeps G10 OPEN; production blocked | Recorded, not re-signed this session |
| H2 | Approve O5 (remove `write`/`edit` from somad/nova) | **DONE** — containment applied | Applied |
| H3 | Approve O3 (dedicated registry/audit daemon) | Closes G10 prevention gap | Pending |
| H4 | Approve projects extension (O3 scope) | Full closure of all 3 G10 roots | Pending |
| H5 | Accept `docs/security/0003` §15 (L3 execution protocol) | Unblocks L3 live run | Pending |
| H6 | Sign scenario plan.json files | Unblocks L3 O4 oracle | Pending |
| H7 | Approve per-session mount (D4/D7 composition) | Unblocks live dispatch | Pending |
| H8 | Approve G13 adversarial live test | Moves G13 from UNKNOWN | Pending |

---

## EXACT OPERATOR / INFRASTRUCTURE ACTIONS

| # | Action | Required for | Owner |
|---|--------|-------------|-------|
| A1 | Mount D4/D7 + verify per session | Live dispatch, L3 P1 | Operations |
| A2 | Set `DSH_LIVE_BRIDGE_ACTIVE=1` | Live bridge activation | Operations |
| A3 | Enable web GUI or compose headless answerer row | Interactive approval | Operations |
| A4 | Provision separate-UID verifier launch path | L3 IO-2 | Operations |
| A5 | Implement O3 dedicated registry/audit daemon | G10 closure | Engineering |
| A6 | Run G13 adversarial live test | G13 resolution | Engineering |
| A7 | Build VER-2 independent measurement channel | HIGH-risk execution | Engineering |
| A8 | Reconcile stale documentation (S1-S10) | Document consistency | Engineering |

---

## EXACT IMPLEMENTATION ACTIONS

- **O3 daemon** (no code written): design finalized, requires implementation (8 components per FINAL architecture package)
- **O4 upstream requirement** (no code in this project): file upstream DSH requirement for per-agent sandbox root or per-path allow/deny on filesystem tools
- **VER-2 independent measurement channel** (no code written): per action category, requires implementation

---

## MINIMUM PATH TO PRODUCTION

### Phase 5.1 — Unblock live dispatch (shortest path)
1. Human approves per-session D4/D7 mount (H7 + A1)
2. Set `DSH_LIVE_BRIDGE_ACTIVE=1` (A2)
3. Enable web GUI session or compose headless answerer (A3)
4. Re-run Phase-5 live variants with committed evidence

### Phase 5.2 — Resolve L3 (sequential)
5. Human signs §15 acceptance (H5)
6. Sign 8 scenario plan.json files (H6)
7. Provision separate-UID verifier (A4)
8. Run authorized live L3 scenarios → committed `audit/l3/` bundles with `l3_claim=true`

### Phase 5.3 — Close G10 (parallel)
9. Implement O3 dedicated registry/audit daemon (A5 + H3 + H4)
10. Or: upgrade DSH to version with O4 capability (A9) and re-derive residual

### Phase 5.4 — Resolve G13 (parallel)
11. Run G13 adversarial live test (A6 + H8)
12. Document DSH driver-internal content-isolation findings

### Phase 5.5 — Operational hardening
13. Build VER-2 independent measurement channel (A7)
14. Automate per-session baseline preflight (A8)
15. Reconcile stale documentation (A8)

---

## SCOPE / CONCURRENCY FINDINGS

1. **No unauthorized modifications** detected this session. All observed changes (O5 application, front-door code, tests, documentation) are in documented write scopes consistent with prior approvals.
2. **O5 concurrent-modification note** (from prior session): a parallel session edited O5-adjacent files during O5 application. Re-verified: post-O5 hashes match the application record; no divergence found.
3. **Test design limitation**: acceptance and preflight lock tests hard-code a web-GUI environment assumption. They fail in headless sessions. This is a test-environment-sensitivity issue, not a security regression. Recommended: parameterize the expected blocker count per environment type.
4. **No evidence of concurrent writers** during this audit session. The only write activities are in-scope (master-audit dirs).
5. **Combined-run test failures** (10 entrypoint + 3 g10/decision) are test-isolation/ordering artifacts that pass in isolation. Same documented class as `phase4_integration/test_06` ordering issue. Not a scope violation.

---

## FINAL RECOMMENDATION

1. **Accept this audit as the authoritative current baseline.** The environment has drifted materially from the prior reports (rebaseline, acceptance matrix, closure matrix). The current headless session has 5-7 L3ENV blockers, not 3.

2. **Do not promote any prior report's "3 blockers" or "ANS-1/2 PASS" claims to this session.** Those claims were environment-specific and are invalidated in the current headless context.

3. **The minimum path to production is unchanged** from the acceptance matrix (§15). No shortcut exists: G10, G13, live-DSH proof, and L3 must all be resolved.

4. **Priority action: environment consistency.** Before any live dispatch or L3 work, ensure the session environment matches the requirements (web GUI or deployed answerer, DSH_HOME set, D4/D7 mounted, bridge marker set). The documentation must be reconciled to reflect the current environment's actual state.

5. **Known residual accepted:** G10 prevention gap, G13 DSH-native UNKNOWN, same-UID sandbox, no live bridge, no approval answerer, no real signed plans, no authorized run. All seven are documented blocking conditions. **No control is claimed L3.**

---

*Status: MASTER SECURITY AUDIT (Authoritative). Production: NOT PRODUCTION-READY. Security: G10 OPEN, G13 OPEN/UNKNOWN, L3 NOT CLAIMED. Zero controls L3. Current environment: headless (DSH_WEB_URL unset). Blocker count: 5-7 L3ENV (environment-dependent). 10 stale/contradictory evidence findings documented. No production changes, no DSH changes, no policy changes, no role changes, no live execution.*
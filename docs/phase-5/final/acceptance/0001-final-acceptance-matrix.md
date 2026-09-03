# Phase 5 — Final Acceptance Matrix (Authoritative)

- **Milestone**: Phase 5 / Final Acceptance — AUTHORITATIVE FINAL ACCEPTANCE MATRIX
- **Status**: **ACCEPTANCE MATRIX** (single authoritative consolidation; **no production deployment started, no gate closed, no L3 claim, no security closure claimed, no DSH/core/config/policy change**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Write scope**: `docs/phase-5/final/acceptance/0001-final-acceptance-matrix.md` (this file) + `tests/phase-5/final/acceptance/test_acceptance_matrix.py`
- **Inputs** (all read-only, verified this session): `docs/phase-5/final/0001-security-closure-matrix.md` · `0002-g10-formal-residual-proof.md` · `0003-g13-external-content-evidence.md` · `0004-l3-critical-controls-evidence.md` · `0005-final-security-gate-evidence.md` · `docs/phase-5/final/preflight/0001-final-operator-checklist.md` · `docs/phase-5/master-integration-gate.md` · `docs/phase-5/0001-acceptance-matrix.md` · `docs/phase-5/0001-security-hardening-analysis.md` · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` · `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` · `0002-o3-final-closure-determination.md` · `0003-o3-final-threat-model.md` · `0004-o3-final-acceptance-test-spec.md` · `docs/phase-5/security/g10/implementation/0001-o5-o3-implementation-plan.md` · `0002-o5-application-record.md` · `docs/phase-5/security/g13/final/0001-g13-live-readiness-session-b.md` · `docs/phase-5/l3/final/0001-l3-critical-control-final-readiness.md` · `0002-l3-critical-preflight-package.md` · `docs/phase-5/l3/live-plans/README.md` · `docs/phase-5/environment/0001-environment-readiness-spec.md` · `docs/phase-5/environment/approval/0001-approval-path-readiness.md` · `docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md` · `docs/phase-5/environment/live-bridge/0001-d4d7-live-bridge-readiness.md` · `docs/phase-4/0005-production-readiness-assessment.md` · `docs/phase-4/0001-acceptance-matrix.md` · `audit/runtime/INT-{01,07,11,12}/` evidence bundles · all test suites re-run this session.

---

## Status vocabulary

| Label | Meaning |
|---|---|
| **CLOSED** | Requirement satisfied at the stated evidence level. Does not imply production or L3 readiness. |
| **OPEN** | Requirement not satisfied. Gap is documented with evidence. |
| **BLOCKED** | Cannot proceed — a named prerequisite is absent. |
| **DEFERRED** | Intentionally out of scope for Phase 5. |
| **UNKNOWN** | Not verifiable in this environment / no claim made. |

## Evidence levels

| Level | Meaning |
|---|---|
| **Deterministic** | In-process / recorded-runtime tests. Proven by green tests. |
| **L2-LIVE** | Live DSH `0.1.1-rc.2` session with mounted `subagent_<id>` instance; runtime-observed denial/allow. |
| **Rehearsal** | Full replay/inert execution path producing a bundle with `l3_claim=false`. Never L3 evidence. |
| **Live runtime** | Real DSH session with live bridge active, authorized, and producing committed evidence. |
| **Independently verified L3** | P1–P4 all hold: live runtime, independent observer (separate PID+UID), external oracle (≥2 classes), reproducible replay. |

---

## 1. G1–G13 Security Gap Closure

| # | Gap | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|---|
| **G1** | REAL DSH backend wiring | **CLOSED** (deterministic) | Deterministic | L1/L2-config | BLOCKED for live dispatch | Engineering | Mount D4/D7 + set marker | Live-DSH proof: backend selection, dispatch, `BridgeNotAvailable` fail-closed |
| **G2** | Persistent D4/D7 availability | **CLOSED** (readiness) | Deterministic | L2-config | BLOCKED for live dispatch | Operations | Per-session mount verification | `ENV-MOUNT-1` PASS; `probe_backend_kind() == real-dsh`; 7 mount probes True |
| **G3** | Approval-answerer availability | **CLOSED** (readiness) | Deterministic | L2-config | BLOCKED for interactive/HIGH-risk | Operations | Enable answerer or supply signed `approval-<id>` refs | `L3ENV-ANS-1/2` PASS; live answerer returning closed `ApprovalOutcome` |
| **G4** | Provider 429 / rate-limit resilience | **CLOSED** (deterministic + Phase-3 live) | Deterministic + L2-LIVE (INT-12) | L1/L2 | Operational (accepted residual: no backoff) | Engineering | No action (REC-G4-1 deferred) | 41 resilience tests pass; 429 handled correctly |
| **G5** | Independent L3 verifier | **CLOSED** (infrastructure) | Deterministic | L1/L2 | BLOCKED for L3 claim | Engineering | Provision separate UID + sign plans + authorize run | `evaluate_l3_claim()` returns true on bundle facts; committed `audit/l3/` |
| **G6** | Separate-process/UID readiness | **CLOSED** (readiness) | Deterministic | L1/L2 | BLOCKED for L3 claim | Operations | Provision separate-UID launch path | `IO-2 pass=true`; `verifier_uid != orchestrator_uid` |
| **G7** | Human-signed plan prerequisites | **CLOSED** (readiness) | Deterministic | O4 | BLOCKED for L3 claim | Human | Sign plan.json per scenario (durable identity) | `L3ENV-PLAN-REAL` PASS; `validate_signed_plan() == VALID` |
| **G8** | Evidence-bundle execution path | **CLOSED** (readiness) | Deterministic (rehearsal) | P4 | BLOCKED for L3 claim | Engineering | Run authorized live L3 scenarios | 13-file bundle with `l3_claim=true` under `audit/l3/` |
| **G9** | Runtime registry protection | **CLOSED** (deterministic) | Deterministic | L1 | BLOCKED for live variant | Engineering | Mount D4/D7 + run ISO-LIVE-006 live variant | Live registry-write DENY observed |
| **G10** | DSH path-isolation limitation | **OPEN** (BLOCKING) | Deterministic (residual proven) | L1 + detection | BLOCKING for production | Human → Engineering | Apply O5 (done) → O3 or O4 | Per-agent/path-level sandbox OR dedicated registry daemon implemented + verified |
| **G11** | Full recovery cycle → COMPLETE | **CLOSED** (deterministic) | Deterministic | L1 | BLOCKED for live variant | Engineering | Mount D4/D7 + run recovery→COMPLETE live | Live recovery→COMPLETE observed |
| **G12** | Role runtime validation (6 non-cto roles) | **CLOSED** (deterministic) | Deterministic | L1/L2-config | BLOCKED for live variant | Engineering | Mount D4/D7 + run per-role dispatch | 6 non-cto roles dispatched live, toolFilter enforced |
| **G13** | Prompt-injection / external-content | **OPEN** (defenses verified; full closure UNKNOWN) | Deterministic | L1 | BLOCKING for any injection claim | Engineering → Operations | Authorized adversarial live test + DSH driver-internal findings | Live DSH child under injection payloads DENIES all injected actions |

---

## 2. O5 / O3 — G10 Mitigation Arms

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| **O5** — Remove `write`/`edit` from somad/nova | **CLOSED** (applied, containment only) | L2-config (toolFilter) | L2 (surface reduction) | Reduces raw-write actor set to `{zeko, cto}`; G10 remains OPEN | Human (approved) | None (applied) | `{zeko, cto}` raw-write actors; `write`/`edit` denied for somad/nova at DSH layer |
| **O3** — Dedicated registry/audit daemon | **DEFERRED** (designed, not implemented) | Design only | Hard isolation | Would close G10 prevention gap for all 3 roots | Human → Engineering | Implement daemon + A+B isolation + projects extension + switch write path | O3-ACCEPTANCE-001..047 all pass; G10 re-derived as CLOSED |
| **O4** — DSH per-agent/path-level sandbox | **DEFERRED** (upstream requirement) | Not available in 0.1.1-rc.2 | Full prevention | Would close G10 at DSH layer | DSH upstream | File upstream requirement; upgrade when available | Per-agent sandbox root or per-path allow/deny on filesystem tools |

---

## 3. D4/D7 — Live Bridge

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| Composition files | **CLOSED** (consistent, valid) | L2-config | L2-config | READY (static) | Engineering | None (persistent) | mapping==policy==instance; allow∩deny=∅; 7 roles resolved |
| Bridge marker | **BLOCKED** | Deterministic | L2 | BLOCKED for live dispatch | Operations | Set `DSH_LIVE_BRIDGE_ACTIVE=1` after mount verification | `L3ENV-D4D7-3` PASS; `probe_backend_kind() == real-dsh` |
| Live dispatch | **BLOCKED** | N/A | N/A | BLOCKED for live dispatch | Operations | Run per-session mount verification + smoke (steps 1–6) | `BridgeNotAvailable` never raised; live `subagent_<id>` dispatch settles with real run id |
| Per-session re-verification | **CLOSED** (mechanism defined) | Deterministic | L2 | BLOCKED for live use | Operations | Automate preflight bootstrap | `ENV-MOUNT-1` … `ENV-MOUNT-2` all PASS |

---

## 4. Approval Path

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| `ask` policy active | **CLOSED** | L2-config | L2 | READY | None | None | `approval/policy` event = `ask` |
| Human answerer (web GUI) | **CLOSED** (mechanism present) | L2-config | L2 | BLOCKED for interactive use | Operations | Verify browser attached; or compose explicit answerer row | `L3ENV-ANS-1` PASS; approval dispatch returns closed outcome |
| Approval path functional | **BLOCKED** | Deterministic | L2 | BLOCKED for interactive + HIGH-risk | Operations | Enable answerer or pre-record signed `approval-<id>` refs | `L3ENV-ANS-2` PASS; approval-dependent action ALLOWs through live answerer |
| HIGH-risk approval (independent VER-2) | **BLOCKED** | Deterministic | L1/L2 | BLOCKED for HIGH-risk `independent` | Engineering | Build independent measurement channel per action category | VER-2 acceptance; HIGH-risk `independent` execution ALLOWs |

---

## 5. L3 — Independent Verification

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| Independent oracles (O1, 8 gates) | **CLOSED** | Deterministic | L1/L2 | READY (infrastructure) | Engineering | None | 8 reference oracles, clean imports, all 148 L3 tests pass |
| Verifier independence (P2) | **CLOSED** (machinery) | Deterministic | L1/L2 | BLOCKED for L3 claim | Engineering | None (machinery ready) | `assert_clean_imports()` CLEAN; subprocess spawn; IO-1 PASS |
| Separate UID (IO-2) | **BLOCKED** | Deterministic | L2 | BLOCKING for L3 claim | Operations | Provision separate-UID launch path | `verifier_uid != orchestrator_uid` (both non-zero) |
| ≥2 oracle classes (P3) | **CLOSED** | Deterministic | L1/L2 | READY | Engineering | None | All 8 scenarios declare ≥2 classes |
| Reproducible replay (P4) | **CLOSED** | Deterministic | L1/L2 | READY | Engineering | None | `replay.json` with fixture hash, verifier/schema sha256, command line |
| Human-signed plan (O4) | **BLOCKED** | Deterministic | O4 | BLOCKING for L3 claim | Human | Sign each scenario plan.json with durable identity | `L3ENV-PLAN-REAL` PASS; `validate_signed_plan() == VALID` |
| Live runtime (P1) | **BLOCKED** | N/A | P1 | BLOCKING for L3 claim | Operations | Authorize live DSH session + bridge marker | `runtime-verdict.json` from real DSH session |
| Evidence bundle (13-file) | **CLOSED** (rehearsal) | Rehearsal | E1–E13 | BLOCKED for L3 claim | Engineering | None (machinery rehearsed) | 13-file bundle under scratch with `l3_claim=false` |
| LV16 evidence-contract | **CLOSED** (resolved) | Deterministic | LV16 | READY | Engineering | None (oracles emit `checklist_item_results`) | All 8 scenarios pass LV16 validation |
| Claim gate | **CLOSED** (code-enforced) | Deterministic | Claim gate | BLOCKING for L3 claim | Engineering | None | `evaluate_l3_claim()` returns `l3_claim=false` on current facts |
| **L3 VERDICT** | **NOT CLAIMED — zero controls L3** | Rehearsal only | L1/L2 | BLOCKED | Human + Operations + Engineering | Separate UID + signed plans + live bridge + authorized run | All 8 bundles with `l3_claim=true` under `audit/l3/` |

**Critical scenarios (8, in runner registry order):** `L3-AUTH-001`,
`L3-AUTH-003`, `L3-AUTH-004`, `L3-AUTH-006`, `L3-PATH-001`, `L3-REC-004`,
`L3-ST-003`, `L3-AUD-002`.

**Machinery referenced (read-only, verified this session):** `tests/l3_runner/`
(runner, verifier, validator, rehearsal, claim_gate, preflight, plan_signing,
environment readiness), `tests/l3_reference/` (oracles, schemas, critical
fixtures), `control/execution_gate.py`, `audit/helpers/`, `state/helpers/`,
`config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`.

---

## 6. Audit Integrity

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| Append-only ledger | **CLOSED** | Deterministic | L1 | READY | Engineering | None | `append_event` only; overwrite/truncation detected |
| SHA-256 hash chain | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Chain break → `AuditIntegrityError` |
| Sidecar chain verification | **CLOSED** | Deterministic | L1 | READY | Engineering | None | `verify_chain_with_sidecar` compares recomputed vs persisted |
| Truncation / duplicate / replay detection | **CLOSED** | Deterministic | L1 | READY | Engineering | None | `detect_truncation` / `detect_duplicates` on baseline |
| Audit-is-authority rejection | **CLOSED** | Deterministic | L1 | READY | Engineering | None | `audit_is_authority_source` always False |
| Tamper detection (L3 oracle) | **CLOSED** | Deterministic | L1 | READY | Engineering | None | `audit_chain.verify_ledger` returns VALID/INVALID |

---

## 7. Recovery

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| No blind retry | **CLOSED** | Deterministic + L2-LIVE (INT-12) | L1 | READY | Engineering | None | Empty/identical cause → refused |
| Privilege bounding | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Recovery with expanded scope → DENY |
| Restoration verification | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Restoration must be independently verified |
| Stale-state detection | **CLOSED** | Deterministic | L1 | READY | Engineering | None | State version changed → recovery refused |
| Double-recovery prevention | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Recovery from COMPLETE/FAILED → DENIED |
| Full cycle → COMPLETE (live) | **BLOCKED** | Deterministic | L1 | BLOCKED for live variant | Operations | Mount D4/D7 + run live recovery scenario | Live recovery→COMPLETE observed |

---

## 8. Verification

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| Expected declared before execution | **CLOSED** | Deterministic + L2-LIVE | L1 | READY | Engineering | None | `VerificationSession` created in `Engine.validate` |
| Reported ≠ verified | **CLOSED** | Deterministic + L2-LIVE | L1 | READY | Engineering | None | `engine.complete()` raises `VerificationRefused` unless PASSED |
| Evidence sufficiency | **CLOSED** | Deterministic + L2-LIVE | L1 | READY | Engineering | None | Required kinds present → PASS |
| Independent verification (VER-2) | **BLOCKED** | Deterministic | L1/L2 | BLOCKED for HIGH-risk `independent` | Engineering | Build independent measurement channel | VER-2 acceptance; HIGH-risk `independent` execution ALLOWs |

---

## 9. Observability

| Item | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|
| Run/task/delegation correlation | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Correlation → run/task/delegation index |
| Fail-closed rejection | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Missing field → REJECTED |
| Health/sanity report | **CLOSED** | Deterministic | L1 | READY | Engineering | None | Health report → problems/integrity |
| Metrics | **CLOSED** | Deterministic | L1 | READY | Engineering | None | All metrics computed |
| Read-side only (no audit writes) | **CLOSED** | Deterministic | L1 | READY | Engineering | None | 0 `audit_append`/`append_event` calls |

---

## 10. Known Residuals

| # | Residual | Current status | Evidence level | Security level | Production impact | Owner | Required action | Acceptance criterion |
|---|---|---|---|---|---|---|---|---|
| **R1** | G10 DSH-layer prevention absent (raw-write-capable `{zeko, cto}` can bypass L1 gate via raw DSH tool call) | **OPEN** (accepted V1) | Deterministic (proven) | L1 + detection | BLOCKING for production; all tampering detectable | Human → Engineering | Apply O3 (dedicated registry/audit daemon) or O4 (upstream DSH capability) | Per-agent sandbox root OR per-path allow/deny on filesystem tools OR dedicated daemon implemented + verified |
| **R2** | G13 prompt-injection full closure UNKNOWN (live DSH child behavior, DSH driver-internal isolation) | **OPEN** (no claim) | Deterministic (defenses verified) | L1 (control-plane) | BLOCKING for any injection claim | Engineering → Operations | Authorized adversarial live test + DSH driver-internal content-isolation findings | Live DSH child under injection payloads DENIES all injected actions; DSH driver-internal isolation documented |
| **R3** | Same-UID sandbox (IO-2 fail) | **BLOCKED** | Deterministic | L2 | BLOCKING for L3 claim | Operations | Provision separate-UID launch path | `verifier_uid != orchestrator_uid` |
| **R4** | No live DSH bridge (marker unset) | **BLOCKED** | Deterministic | L2 | BLOCKING for live dispatch + L3 | Operations | Mount D4/D7 + set marker | `DSH_LIVE_BRIDGE_ACTIVE=1`; `probe_backend_kind() == real-dsh` |
| **R5** | No approval answerer | **BLOCKED** | Deterministic | L2 | BLOCKING for interactive + HIGH-risk + L3 signing | Operations | Enable answerer or supply signed `approval-<id>` refs | `L3ENV-ANS-1/2` PASS |
| **R6** | No real Human-signed plan | **BLOCKED** | Deterministic | O4 | BLOCKING for L3 claim | Human | Sign each scenario plan.json with durable identity | `L3ENV-PLAN-REAL` PASS; plan committed before runtime |
| **R7** | No authorized run | **BLOCKED** | N/A | P1 | BLOCKING for live L3 | Human | Accept `docs/security/0003` §15; re-baseline to `workspace-write + ask` | Human-signed acceptance record; B1 closed |
| **R8** | Provider 429 backoff/scheduling not implemented | **DEFERRED** (accepted operational) | N/A | Operational | Low (no 429 amplification) | Engineering | Implement REC-G4-1 when needed | Deferred; not blocking |
| **R9** | Session-policy baseline drift guard | **DEFERRED** (accepted operational) | N/A | Operational | Low (baseline verified) | Operations | Automate baseline re-verification | Per-session policy guard |

---

## 11. Verdicts

### 11.1 Production-readiness verdict

**NOT PRODUCTION-READY.** BLOCKED by G10 (OPEN/BLOCKING), G13 (OPEN/UNKNOWN), and the absence of live-DSH proof for all Phase-5 changes (B1/B2). The deterministic runtime and L2-LIVE evidence for INT-01/07/11/12 are proven, but the live bridge, answerer, and DSH-layer path isolation are not.

| Condition | Status |
|---|---|
| D4/D7 mount verified + marker set | **BLOCKED** |
| Approval answerer live | **BLOCKED** |
| Live-DSH proof for Phase-5 changes (G1/G9/G11/G12) | **BLOCKED** |
| G10 DSH-layer path isolation | **OPEN** — blocking |
| G13 prompt-injection posture | **OPEN/UNKNOWN** — blocking for any claim |
| HIGH-risk independent verification (VER-2) | **BLOCKED** |
| Provider 429 backoff, baseline guard, CI/CD | **DEFERRED** |

### 11.2 Security verdict

**SECURITY LEVELS** (current, authoritative):

| Level | Status |
|---|---|
| **L1 (project control-plane logic)** | **CLOSED** — all deterministic suites green (authority, execution gate, state transition, audit, recovery, verification, role matrix) |
| **L2 (DSH-native config)** | **CLOSED** — toolFilter, role instances, session sandbox `workspace-write + ask` |
| **L2-LIVE (real DSH proof)** | **PARTIAL** — INT-01/07/11/12 proven; all Phase-5 live variants BLOCKED |
| **L3 (independently verified runtime)** | **ZERO controls** — same-UID sandbox prevents any L3 claim |
| **UNKNOWN** | G13 prompt-injection (DSH layer); per-session sandbox limitation (PS-2); DSH driver-internal content isolation |

### 11.3 L3 verdict

**NOT CLAIMED — zero controls are L3.** Infrastructure ready to rehearse; not ready to claim. The exact blockers:

1. **L3ENV-UID-2** — separate UID (IO-2): same-UID host (uid=1000)
2. **L3ENV-ANS-1** — Human approval answerer unavailable
3. **L3ENV-ANS-2** — approval path non-functional
4. **L3ENV-D4D7-3** — live bridge marker unset
5. **L3ENV-PLAN-REAL** — no real Human signoff observed

All 8 critical scenarios rehearse green with `l3_claim=false`. No L3 claim is possible on this host.

### 11.4 G10 verdict

**OPEN — BLOCKING GATE.** The DSH-layer prevention gap is formally proven. O5 applied (containment by surface reduction: `{zeko, cto, somad, nova}` → `{zeko, cto}`). O3 designed but not implemented. O4 requires upstream DSH capability absent in 0.1.1-rc.2. G10 remains BLOCKING for production.

### 11.5 G13 verdict

**OPEN — defenses verified; full closure UNKNOWN.** 111 deterministic tests (6 phase5_security + 86 adversarial injection + 19 adversarial INJ/BAD/AUD) verify that authority keys are stripped, malicious results cannot grant authority, subdelegation is denied, and reported SUCCESS ≠ verified. Live DSH child behavior under injection payloads and DSH driver-internal content isolation remain UNKNOWN. No claim.

---

## 12. Exact blockers

| # | Blocker | Blocked item | Source |
|---|---|---|---|
| B1 | D4/D7 mount absent / marker unset | All live variants; L3 P1 | `ENV-MOUNT-1`; G2 |
| B2 | Approval answerer unavailable | Interactive + HIGH-risk approval; L3 signing (G7/O4) | `ENV-APPROVAL-1`; G3 |
| B3 | Same-UID sandbox (IO-2 fail) | Any L3 claim | `L3ENV-UID-2`; G6 |
| B4 | `LiveDSHRuntimeDriver` refuses live dispatch | Live L3 run (P1) | G5/G8 |
| B5 | G10 OPEN (DSH-layer prevention) | Full path-isolation closure; production | G10 |
| B6 | G13 OPEN/UNKNOWN (injection) | Any prompt-injection security claim | G13 |
| B7 | Independent verifier for HIGH-risk (VER-2) | HIGH-risk `independent` execution | L3-1/VER-2 |
| B8 | No production-wired approval path / session-policy drift guard | Guaranteed `workspace-write + ask` over time | PB-1 |

---

## 13. Exact Human decisions required

| # | Decision | Impact | Recorded in |
|---|---|---|---|
| H1 | **Accept G10 residual** (V1 containment = detection) | Keeps G10 OPEN; production blocked | `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` |
| H2 | **Approve O5** (remove `write`/`edit` from somad/nova) | **DONE** — containment applied | `docs/phase-5/security/g10/implementation/0002-o5-application-record.md` |
| H3 | **Approve O3** (dedicated registry/audit daemon) | Closes G10 prevention gap | `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` |
| H4 | **Approve projects extension** (O3 scope includes `state/projects/**`) | Full closure of all 3 G10 roots | `docs/phase-5/security/g10/o3/final/0002-o3-final-closure-determination.md` |
| H5 | **Accept `docs/security/0003` §15** (L3 execution protocol) | Unblocks L3 live run | `docs/security/0003-l3-independent-verification-plan.md` §15 |
| H6 | **Sign scenario plan.json files** (durable identity per scenario) | Unblocks L3 O4 oracle | `docs/phase-5/l3/live-plans/` (8 templates) |
| H7 | **Approve per-session mount** (D4/D7 composition) | Unblocks live dispatch | `docs/phase-5/environment/0001` §2.2 |
| H8 | **Approve G13 adversarial live test** | Moves G13 from UNKNOWN | `docs/phase-5/security/g13/final/0001-g13-live-readiness-session-b.md` |

---

## 14. Exact infrastructure actions required

| # | Action | Required for | Owner |
|---|---|---|---|
| A1 | Mount D4/D7 + verify per session | Live dispatch, L3 P1 | Operations |
| A2 | Set `DSH_LIVE_BRIDGE_ACTIVE=1` | Live bridge activation | Operations |
| A3 | Enable approval answerer / compose answerer row | Interactive + HIGH-risk + L3 signing | Operations |
| A4 | Provision separate-UID verifier launch path (setuid / separate user / separate host) | L3 IO-2 | Operations |
| A5 | Implement O3 dedicated registry/audit daemon | G10 closure | Engineering |
| A6 | Run G13 adversarial live test with DSH child under injection | G13 resolution | Engineering |
| A7 | Build VER-2 independent measurement channel | HIGH-risk `independent` execution | Engineering |
| A8 | Automate per-session baseline preflight | Operational reliability | Operations |
| A9 | File upstream DSH requirement for O4 (per-agent sandbox root or per-path allow/deny) | G10 full prevention | Engineering |

---

## 15. Minimum path to final acceptance

### Phase 5.1 — Unblock live dispatch (shortest path)
1. Human approves and executes per-session D4/D7 mount (H7 + A1)
2. Set `DSH_LIVE_BRIDGE_ACTIVE=1` (A2)
3. Enable approval answerer (A3)
4. Re-run Phase-5 live variants (G1/G9/G11/G12) with committed evidence

### Phase 5.2 — Resolve L3 (sequential)
5. Human signs §15 acceptance (H5)
6. Sign 8 scenario plan.json files (H6)
7. Provision separate-UID verifier (A4)
8. Run authorized live L3 scenarios → committed `audit/l3/` bundles with `l3_claim=true`

### Phase 5.3 — Close G10 (parallel track)
9. Implement O3 dedicated registry/audit daemon (A5 + H3 + H4)
10. Or: upgrade DSH to version with O4 capability (A9) and re-derive residual

### Phase 5.4 — Resolve G13 (parallel track)
11. Run G13 adversarial live test (A6 + H8)
12. Document DSH driver-internal content-isolation findings

### Phase 5.5 — Operational hardening
13. Build VER-2 independent measurement channel (A7)
14. Automate per-session baseline preflight (A8)
15. Implement provider 429 backoff (REC-G4-1) if desired

---

## 16. Honesty statement

1. **No production deployment started.** Unrestricted production deployment is BLOCKED by G10/G13 and the absence of live-DSH proof for Phase-5 changes.
2. **No gate is claimed complete.** G10 and G13 remain OPEN. L3 remains NOT CLAIMED.
3. **No control is claimed L3.** Zero controls satisfy P1–P4 simultaneously. Same-UID sandbox makes any L3 claim impossible by design.
4. **No DSH core/profile/preset/session-policy change was made.** The session operated within the `workspace-write + ask` baseline.
5. **No test failure was downgraded or re-labelled.** All test counts are as observed.
6. **No signature was invented.** The signed-plan fixtures remain inert templates.
7. **No prompt-injection claim is made.** G13 remains OPEN/UNKNOWN.
8. **No path-isolation closure is claimed.** G10 remains OPEN.
9. **No UNKNOWN is marked as PASS.** Every UNKNOWN is recorded as OPEN.
10. **No OPEN is marked as CLOSED.** Every OPEN has the exact gap and evidence level recorded.

---

## 17. Scope check

**In scope (written this session):**
- `docs/phase-5/final/acceptance/0001-final-acceptance-matrix.md` (this file)
- `tests/phase-5/final/acceptance/test_acceptance_matrix.py`

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, `tests/` (all), DSH core/profile/preset/session policy, all `docs/` outside write scope. No production code modified. No L3 claim made. No security closure claimed. No signature invented.

---

*Status: FINAL ACCEPTANCE MATRIX. Production-readiness: NOT PRODUCTION-READY. Security: G10 OPEN, G13 OPEN/UNKNOWN, L3 NOT CLAIMED. Zero controls L3. All three remain open with evidence provided. Minimum path to final acceptance documented in §15. No gate closed by this document.*
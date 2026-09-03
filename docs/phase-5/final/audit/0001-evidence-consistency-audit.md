# SESSION D — MASTER EVIDENCE CONSISTENCY AUDIT

- **Audit**: Session D — Read-Only Master Evidence Consistency Audit
- **Date**: 2026-09-01
- **Scope**: docs/phase-5/final/*, docs/phase-5/security/*, docs/phase-5/l3/*, docs/phase-5/environment/*, docs/phase-5/entrypoint/*, docs/phase-4/*, phase-5/master-integration-gate.md
- **Method**: Cross-document comparison of every status claim, blocker list, regression count, approval-path assertion, D4/D7 claim, O5/G10/G13/L3/LV16 status, VERIFIED/INFERRED/UNKNOWN classification, and Front Door claim
- **Constraint**: No reconciliation, no rewriting, no downgrading, no production-readiness declaration

---

## CLASSIFICATION VOCABULARY

| Class | Meaning |
|---|---|
| **STALE** | Claim was accurate at its authoring time but is superseded by later evidence or a probe repair. The document has not been updated. |
| **CONTRADICTORY** | Two or more documents in the same evidence set make mutually exclusive claims about the same subject. |
| **MISSING EVIDENCE** | A claim is made without supporting test evidence, or the arithmetic of a claim is unsupported. |
| **VALID** | Claim is internally consistent and supported by the evidence across the corpus. |
| **UNKNOWN** | Cannot be determined from the available documents without a re-run or reconciliation. |

---

## DISCREPANCY TABLE (20 findings)

### R1 — Regression Count: 1597 vs 1642 vs 1898

| Column | Value |
|---|---|
| **SOURCE** | final/0001-security-closure-matrix.md §5 — "documented 1597 passed, 15 skipped"; final/0005-final-security-gate-evidence.md §0 — "1642 passed, 15 skipped (full regression; includes the +17 concurrent Session-D environment-readiness tests)"; l3/final/0001-l3-critical-control-final-readiness.md §7 — "Full project regression: 1898 passed, 15 skipped (exit 0; the +96 final-readiness tests included)" |
| **CLAIM** | Three different "full regression" totals for the same test suite on the same date (2026-08-31). |
| **CURRENT EVIDENCE** | 1597 to 1642 is +45, but only +17 is attributed to "concurrent Session-D environment tests"; the remaining +28 is unexplained. 1642 to 1898 is +256, but only +96 is attributed to "final-readiness tests"; the remaining +160 is unexplained. 1898 - 96 = 1802, not 1642. |
| **STATUS** | **CONTRADICTORY / MISSING EVIDENCE** |
| **REQUIRED CORRECTION** | Re-run the definitive full regression and record ONE authoritative count. Reconcile the arithmetic in the three final documents. |
| **SEVERITY** | **HIGH** — undermines the credibility of the official regression evidence used in all three final/authoritative documents. |

### R2 — L3 Test Suite Count: 148 vs 275 vs 389 vs 545

| Column | Value |
|---|---|
| **SOURCE** | final/0004-l3-critical-controls-evidence.md §4.1 — "148 passed (tests/l3_runner/ tests/l3_reference/)"; l3/environment/0002-session-a-preflight-verification-record.md §4 — "275 passed (tests/l3_runner/ + tests/l3_reference/)"; l3/final/0001-l3-critical-control-final-readiness.md §7 — "389 passed (293 pre-existing + 96 new final)"; l3/final/0002-l3-critical-preflight-package.md §9 — "545 passed (tests/l3_runner/ tests/l3_reference/)" |
| **CLAIM** | Four different totals for the same L3 suite paths on the same date. |
| **CURRENT EVIDENCE** | 148 < 275 < 389 < 545. The suite grew over time, but final/0004 (dated 2026-08-31, "authoritative re-run") says 148 while l3/final/0002 (also 2026-08-31) says 545 — a 397-test gap on the same date. |
| **STATUS** | **CONTRADICTORY** |
| **REQUIRED CORRECTION** | Reconcile the L3 test counts across the four documents. If the suite grew intra-session, document the growth explicitly. If the counts are from different test runs, label them precisely. |
| **SEVERITY** | **HIGH** — contradicts the claim of a single authoritative final evidence set. |

### R3 — G5 (Independent Verifier) Status: BLOCKED vs CLOSED

| Column | Value |
|---|---|
| **SOURCE** | master-integration-gate.md §1 — "G5: BLOCKED — Independent verifier (L3 verifier not built, LiveDSHRuntimeDriver stub)... Intentionally not addressed in this wave."; final/0001-security-closure-matrix.md §1 — "G5: CLOSED (infrastructure, PASS_WITH_CONDITIONS) — verifier, claim_gate, independence (IO-1..10), plan_signing, uid_readiness, rehearsal, runtime_driver"; final/acceptance/0001-final-acceptance-matrix.md §1 — "G5: CLOSED (infrastructure)" |
| **CLAIM** | Master integration gate says G5 is BLOCKED (verifier not built). Final closure matrix and acceptance matrix say G5 is CLOSED (infrastructure built). |
| **CURRENT EVIDENCE** | l3/0002-g5-verifier-implementation-report.md documents the verifier implementation (claim gate, verifier, independence checks). The L3 verifier WAS built. The master gate was likely authored before the verifier implementation (Session F workstream) and was not updated. |
| **STATUS** | **STALE** (master gate) |
| **REQUIRED CORRECTION** | Update the master integration gate's G5 row from BLOCKED to CLOSED (infrastructure), consistent with the final closure matrix. |
| **SEVERITY** | **MEDIUM** — the master gate is a summary document that is superseded by the final closure matrix, but its stale claim could mislead readers. |

### R4 — L3 Blocker Count: 5 blockers vs 3 blockers

| Column | Value |
|---|---|
| **SOURCE** | l3/final/0001-l3-critical-control-final-readiness.md §3 — "exactly five named blockers: L3ENV-UID-2, L3ENV-ANS-1, L3ENV-ANS-2, L3ENV-D4D7-3, L3ENV-PLAN-REAL"; l3/final/0002-l3-critical-preflight-package.md §4 — "exactly five named blockers" (same five); final/acceptance/0001-final-acceptance-matrix.md §11.3 — "The exact blockers:" listing 5 (same); environment/final/0001-operator-infrastructure-checklist.md §1 — "exactly 3 blockers: L3ENV-UID-2, L3ENV-D4D7-3, L3ENV-PLAN-REAL. (L3ENV-ANS-1/2 are no longer blockers — the targeted approval-probe repair...)"; environment/final/0002-approval-l3-final-readiness.md §4 — "3 L3-required blockers" (same three); environment/approval/0002-approval-path-correction.md §5a — "L3 blockers reduced from 5 to 3 (UID-2, D4D7-3, PLAN-REAL)" |
| **CLAIM** | L3/final docs and final/acceptance claim exactly 5 blockers (including L3ENV-ANS-1/2). Environment/final docs claim exactly 3 blockers (ANS-1/2 now PASS after approval-probe repair). |
| **CURRENT EVIDENCE** | The approval-probe repair (documented in environment/approval/0002 and environment/final/0002) replaced the obsolete DSH_APPROVAL_PROMPTS_DISABLED-based detection with actual DSH bundle/web composition detection. L3ENV-ANS-1/2 now PASS in the web GUI session. The environment/final docs (Session B/D) are the later/corrected documents. The l3/final docs (Session C) and final/acceptance §11.3 use the obsolete blocker list. |
| **STATUS** | **STALE** (l3/final/0001, l3/final/0002, final/acceptance §11.3) |
| **REQUIRED CORRECTION** | Update l3/final/0001, l3/final/0002, and final/acceptance §11.3 to reflect the corrected blocker list (3 blockers, L3ENV-ANS-1/2 now PASS, E2E status UNKNOWN). |
| **SEVERITY** | **HIGH** — the blocker count is a critical operational fact; the 5- vs 3-blocker discrepancy affects the L3 claim-readiness assessment and the minimum path to acceptance. |

### R5 — Approval Answerer Availability: "Unavailable" vs "Available by Composition"

| Column | Value |
|---|---|
| **SOURCE** | final/0001-security-closure-matrix.md §5 — "Approval answerer live (or pre-recorded approval refs)... prompts disabled" (Blocking condition #2) and §6 B2 — "Approval answerer unavailable"; final/0005-final-security-gate-evidence.md §0 — "Approval answerer: Unavailable (prompts disabled)"; environment/final/0001-operator-infrastructure-checklist.md §2 items 3-4 — "Human approval answerer (G3): READY (web GUI, by composition)... L3ENV-ANS-1 PASS"; environment/final/0002-approval-l3-final-readiness.md §2.3-2.4 — "READY (by composition)"; environment/approval/0002-approval-path-correction.md — probe repaired; DSH_APPROVAL_PROMPTS_DISABLED is never read by DSH |
| **CLAIM** | final/0001 and final/0005 claim the approval answerer is unavailable (prompts disabled). Environment/final docs prove the answerer is available by composition (web GUI answerer surface composed, DSH never reads DSH_APPROVAL_PROMPTS_DISABLED). |
| **CURRENT EVIDENCE** | The DSH_APPROVAL_PROMPTS_DISABLED variable is a project-side convention; DSH's own approval mechanism never reads it (verified by negative grep over the entire DSH checkout). The answerer surface is composed in the web-app bundle. The environment/final probe repair proved this. L3ENV-ANS-1/2 PASS in the web GUI session. |
| **STATUS** | **STALE / CONTRADICTORY** |
| **REQUIRED CORRECTION** | Update final/0001 security-closure-matrix §5 condition #2 and §6 blocker B2. Update final/0005 §0. Both should reflect the post-repair state: answerer available by composition in a web GUI session, E2E status UNKNOWN (not independently re-derivable). |
| **SEVERITY** | **HIGH** — the approval answerer status is a production-blocking condition. The stale claim of "unavailable" contradicts the actual environment state and could cause incorrect operational decisions. |

### R6 — final/acceptance Internal Contradiction: Section 4 vs Section 11.3 on L3ENV-ANS-1

| Column | Value |
|---|---|
| **SOURCE** | final/acceptance/0001-final-acceptance-matrix.md §4 "Approval Path" — "Human answerer (web GUI): CLOSED (mechanism present) ... L3ENV-ANS-1 PASS" and "Approval path functional: BLOCKED ... L3ENV-ANS-2 PASS"; §11.3 "L3 verdict" — "The exact blockers: 1. L3ENV-UID-2 ... 2. L3ENV-ANS-1 — Human approval answerer unavailable 3. L3ENV-ANS-2 — approval path non-functional 4. L3ENV-D4D7-3 5. L3ENV-PLAN-REAL" |
| **CLAIM** | Section 4 says L3ENV-ANS-1 PASS (answerer present) and L3ENV-ANS-2 PASS (path functional, though BLOCKED). Section 11.3 lists both L3ENV-ANS-1 and L3ENV-ANS-2 as L3 blockers. |
| **CURRENT EVIDENCE** | The same document contradicts itself: §4 reports the corrected probe result (ANS-1 PASS, ANS-2 PASS), but §11.3 uses the obsolete blocker list (both FAIL). |
| **STATUS** | **CONTRADICTORY** (internal to a single authoritative document) |
| **REQUIRED CORRECTION** | Reconcile §11.3 with §4. If ANS-1/2 PASS, remove them from §11.3's blocker list (reducing it to 3 blockers: UID-2, D4D7-3, PLAN-REAL). |
| **SEVERITY** | **HIGH** — internal contradiction in the authoritative final acceptance matrix undermines trust in the document. |

### R7 — Session-Label Inconsistency: O5 Plan (Session E) vs O5 Application Record (Session A)

| Column | Value |
|---|---|
| **SOURCE** | security/g10/implementation/0001-o5-o3-implementation-plan.md — "Milestone: Phase 5 / Session E"; security/g10/implementation/0002-o5-application-record.md — "Milestone: Phase 5 / Session A" |
| **CLAIM** | The O5 plan (Session E) is superseded by the O5 application record (Session A). The same implementation event (O5 applied 2026-08-31) is labeled with two different session letters. |
| **CURRENT EVIDENCE** | Both documents describe the same event: Human approval of O5 on 2026-08-31. The plan says "superseded by 0002-o5-application-record.md after Human approval of O5". The application record says "APPROVED and APPLIED O5". The plan is Session E; the application record is Session A. Since sessions are parallel workstreams (A-G per master gate), a Session A document superseding a Session E document is chronologically inconsistent. |
| **STATUS** | **STALE / CONTRADICTORY** |
| **REQUIRED CORRECTION** | Reconcile the session labels on the O5 plan/application pair. Either both should be Session A or both Session E. |
| **SEVERITY** | **MEDIUM** — does not change the substantive claim (O5 applied, containment only) but erodes document trustworthiness. |

### R8 — Preflight Obsolete Probe: C3/C4 Based on DSH_APPROVAL_PROMPTS_DISABLED

| Column | Value |
|---|---|
| **SOURCE** | final/preflight/0001-final-operator-checklist.md (Session B) §2.1 — "C3: Approval answerer live (G3): ABSENT — DSH_APPROVAL_PROMPTS_DISABLED unset (defaults disabled); C4: ask path functional (G3): ABSENT (follows C3)" |
| **CLAIM** | The preflight checklist uses the DSH_APPROVAL_PROMPTS_DISABLED variable and $DSH_HOME/profiles scan to detect the approval answerer. |
| **CURRENT EVIDENCE** | Environment/approval/0002 proves DSH never reads DSH_APPROVAL_PROMPTS_DISABLED, and the bundle-composed answerer lives in the DSH packages, not in $DSH_HOME/profiles. The probe repair (environment/final) replaced this detection. The preflight doc (Session B) has not been updated. |
| **STATUS** | **STALE** |
| **REQUIRED CORRECTION** | Update the preflight check's C3 and C4 detection to use the corrected approval-composition detector (actual DSH bundle/web composition). |
| **SEVERITY** | **MEDIUM** — the preflight is a "prepared-only" document, but its stale probe could cause incorrect BLOCKED decisions in a future live run. |

### R9 — Session A Preflight Record: 5 Blockers Based on Obsolete Probe

| Column | Value |
|---|---|
| **SOURCE** | l3/environment/0002-session-a-preflight-verification-record.md §3.4 — "L3ENV-ANS-1: FAIL (required_for_l3) — No live answerer: prompts disabled, no answerer row composed. L3ENV-ANS-2: FAIL (required_for_l3) — ask policy + no answerer" |
| **CLAIM** | The Session A preflight record reports ANS-1/2 as FAIL (blockers), making the total 5 blockers. |
| **CURRENT EVIDENCE** | The probe used DSH_APPROVAL_PROMPTS_DISABLED and $DSH_HOME/profiles scan — the same obsolete detection corrected by environment/approval/0002. The session-a record is honest given its probe, but its conclusion is superseded. |
| **STATUS** | **STALE** |
| **REQUIRED CORRECTION** | The session-a record is a historical record; it should be annotated with a note that the approval probe has since been corrected and ANS-1/2 now PASS. |
| **SEVERITY** | **LOW** — the session-a record is explicitly a historical snapshot, but stale blocker counts could be misleading. |

### R10 — D4D7 Live Bridge Readiness Doc: Lists Approval Answerer as Blocker (B4)

| Column | Value |
|---|---|
| **SOURCE** | environment/live-bridge/0001-d4d7-live-bridge-readiness.md (Session A) §1 BLOCKERS — "B4: Approval answerer absent (L3ENV-ANS-1 / ANS-2)" |
| **CLAIM** | The D4D7 bridge readiness doc lists approval answerer absence as one of its 7 blockers. |
| **CURRENT EVIDENCE** | Environment/final/0001+0002 prove ANS-1/2 PASS after probe repair. The D4D7 bridge doc (Session A) predates the probe repair. |
| **STATUS** | **STALE** |
| **REQUIRED CORRECTION** | Update the D4D7 bridge doc's blocker list to reflect the corrected probe state (ANS-1/2 no longer blockers). |
| **SEVERITY** | **LOW** — the D4D7 bridge doc is a readiness assessment; its blocker list is partially superseded. |

### R11 — Authorization Test Count: 91 vs 178

| Column | Value |
|---|---|
| **SOURCE** | master-integration-gate.md §3 — "tests/authorization/ 91 passed"; final/0002-g10-formal-residual-proof.md §5 — "178 passed"; entrypoint/security/0002-front-door-execution-report.md §8 — "Authorization regression: 178 passed"; security/g10/implementation/0002-o5-application-record.md — "authorization 178 passed" |
| **CLAIM** | Master gate says 91; final docs say 178. |
| **CURRENT EVIDENCE** | The master gate (earlier) recorded 91 authorization tests. Final docs (later) record 178. The count grew. |
| **STATUS** | **STALE** (master gate) |
| **REQUIRED CORRECTION** | Update the master gate's authorization count to 178 or add a note that the count reflects an earlier snapshot. |
| **SEVERITY** | **LOW** — the master gate is a summary document; the final docs are authoritative. |

### R12 — LV16 Session-Label Anomaly: Session C Doc References Session F Resolution

| Column | Value |
|---|---|
| **SOURCE** | l3/final/0001-l3-critical-control-final-readiness.md — "Milestone: L3 CRITICAL CONTROL FINAL READINESS (Session C / Final Security)" and §3 — "LV16 shape note — RESOLVED (Session F)" |
| **CLAIM** | A document labeled "Session C" claims a resolution made in "Session F". |
| **CURRENT EVIDENCE** | The master gate defines sessions A-G as parallel workstreams, not chronological. A Session C doc referencing a Session F resolution is therefore temporally plausible (F is a parallel workstream). However, the labeling is confusing. |
| **STATUS** | **VALID** (but confusing) |
| **REQUIRED CORRECTION** | No correction needed; the session labels are parallel workstreams per master gate. Document the parallel workstream model in the final set's README. |
| **SEVERITY** | **LOW** — the claim itself (LV16 resolved) is consistent across all docs. |

### R13 — G10 Test Count: 78 vs 114 vs 150

| Column | Value |
|---|---|
| **SOURCE** | security/g10/implementation/0002-o5-application-record.md — "tests/g10/ (incl. new O5 guard) 78 passed"; environment/live-bridge/0001-d4d7-live-bridge-readiness.md §3 — "G10 suite (post-O5): 114 passed"; security/g10/o3/implementation/0001-o3-implementation-readiness.md — "tests/g10/ = 150 passed" |
| **CLAIM** | Three different G10 suite counts across documents with the same date (2026-08-31). |
| **CURRENT EVIDENCE** | 78 (O5 app, Session A) < 114 (d4d7 bridge, Session A) < 150 (o3 readiness, Session G). Both Session A documents (app record and d4d7 bridge) differ (78 vs 114). The suite grew over time. |
| **STATUS** | **MISSING EVIDENCE** (counts not reconciled) |
| **REQUIRED CORRECTION** | Reconcile the G10 test counts. The O5 app record (Session A) and d4d7 bridge (Session A) disagree on the same session label. |
| **SEVERITY** | **LOW** — suite growth is expected, but same-session count disagreement (78 vs 114) is a factual inconsistency. |

### R14 — Preflight Path Reference: docs/phase-5/l3/environment/final/ Does Not Exist

| Column | Value |
|---|---|
| **SOURCE** | final/preflight/0001-final-operator-checklist.md §0 — "Companion: ... docs/phase-5/l3/environment/final/ — ABSENT (no such directory exists in the repo; recorded as a read-gap, nothing invented to fill it)" |
| **CLAIM** | The preflight doc references a directory path that does not exist in the repository. |
| **CURRENT EVIDENCE** | The L3 environment docs live at docs/phase-5/l3/environment/0001/0002 (not /final/). The preflight correctly recorded this as a read-gap and read from the actual paths. |
| **STATUS** | **MISSING EVIDENCE** (path-reference error) |
| **REQUIRED CORRECTION** | Fix the preflight's companion reference to point to the actual path (docs/phase-5/l3/environment/0001/0002). |
| **SEVERITY** | **LOW** — the preflight honestly recorded the gap and filled it with actual reads. |

### R15 — environment/final/0002 Session Label: Session B Supersedes Session D

| Column | Value |
|---|---|
| **SOURCE** | environment/final/0002-approval-l3-final-readiness.md — "Milestone: Phase 5 / Session B" and "Supersedes: ...environment/final/0001-operator-infrastructure-checklist.md (Session D)" |
| **CLAIM** | A Session B document supersedes a Session D document. |
| **CURRENT EVIDENCE** | If sessions are parallel workstreams (A-G), Session B (workstream B) superseding Session D (workstream D) is chronologically inconsistent. The supersession claim should be labeled with the same session. |
| **STATUS** | **CONTRADICTORY** |
| **REQUIRED CORRECTION** | Reconcile the session labels. Either both documents should share a session label, or the supersession note should be removed. |
| **SEVERITY** | **MEDIUM** — the supersession relationship is important, but the inconsistent session labels undermine document trustworthiness. |

### R16 — G13 Test Suite Count: 90 vs 107 vs 111

| Column | Value |
|---|---|
| **SOURCE** | security/g13/0001-g13-session-d-verification-report.md §3 — "90 passed in ~0.3s"; security/g13/final/0001-g13-live-readiness-session-b.md §1 — "combined: 107 passed (17 readiness + 90 Session D)"; final/0003-g13-external-content-evidence.md §3 — "14 + 105 tests observed green" and "111 collected (6 + 86 + 19)" |
| **CLAIM** | Three different "G13" test totals: 90 (tests/g13/ suite), 107 (90 + 17 readiness), 111 (G13-relevant across phase5_security + adversarial). |
| **CURRENT EVIDENCE** | These are different scopes: tests/g13/ (90 tests), tests/g13/ + live_readiness (107), and G13-relevant tests across phase5_security + adversarial (111). The scopes differ but the documents do not consistently distinguish them. |
| **STATUS** | **MISSING EVIDENCE** |
| **REQUIRED CORRECTION** | Consistently label G13 test counts with their suite scope (tests/g13/ vs G13-relevant). |
| **SEVERITY** | **LOW** — the scopes genuinely differ, but inconsistent labeling could confuse readers. |

### R17 — Front Door Test Count: 88 vs 270

| Column | Value |
|---|---|
| **SOURCE** | entrypoint/0001-entrypoint-validation-report.md (Session B) — "88 tests passing"; entrypoint/0004-milestone-report.md — "All 270 entrypoint tests pass"; entrypoint/security/0002-front-door-execution-report.md — "158 existing + 112 security = 270" |
| **CLAIM** | 88 (Session B) vs 270 (later milestone). |
| **CURRENT EVIDENCE** | The security execution report reconciles 158 existing + 112 security = 270. The 88 count was from an earlier Session B snapshot. Growth is documented. |
| **STATUS** | **VALID** (growth is documented and reconcilable) |
| **REQUIRED CORRECTION** | None needed. |
| **SEVERITY** | **NONE** |

### R18 — Probe Repair Not Reflected in Final Closure Matrix

| Column | Value |
|---|---|
| **SOURCE** | final/0001-security-closure-matrix.md §5-6 — "Approval answerer live... prompts disabled" (Blocking condition #2), "B2 — Approval answerer unavailable"; environment/approval/0002-approval-path-correction.md §5a — "probe repaired; L3ENV-ANS-1/2 PASS" |
| **CLAIM** | The final closure matrix (Session E) still uses the obsolete approval-answerer detection. The environment approval-correction doc (Session B) proves the detection was wrong. |
| **CURRENT EVIDENCE** | The final/0001 closure matrix was authored in Session E. The approval-probe repair was applied in Session B/D. The closure matrix was not updated to reflect the repair. |
| **STATUS** | **STALE** |
| **REQUIRED CORRECTION** | Update final/0001 §5 condition #2 and §6 blocker B2. The approval answerer is now available by composition (web GUI), E2E status UNKNOWN. |
| **SEVERITY** | **HIGH** — the closure matrix is the authoritative security status document. Its stale claim about answerer unavailability could mislead the production-readiness decision. |

### R19 — Blockers in Live-Assurance: 8 (B1-B8) vs 3 (per env docs) vs 7 (per d4d7 doc)

| Column | Value |
|---|---|
| **SOURCE** | final/live-assurance/0001-live-assurance-coordinator-report.md — EVIDENCE PATHS: "Operator checklist 3 blockers, Approval+L3 final readiness 3 blockers, D4/D7 live bridge readiness 7 blockers" — but own consolidated EXACT BLOCKERS: 8 (B1-B8) |
| **CLAIM** | The live-assurance report cites 3, 3, and 7 blockers from three source docs, but its own blocker list has 8 items. |
| **CURRENT EVIDENCE** | The 8 blockers (B1-B8) include G10/G13 items (B7, B8) that are not in the 3-blocker environment lists. The 3-blocker lists are L3-specific; the 8-blocker list is project-wide. The difference is scope, not contradiction. |
| **STATUS** | **VALID** (scope difference) |
| **REQUIRED CORRECTION** | None needed. The live-assurance report's blocker counts are consistent when scopes are understood. |
| **SEVERITY** | **NONE** |

### R20 — O5 Application Record: Concurrent-Modification Note

| Column | Value |
|---|---|
| **SOURCE** | security/g10/implementation/0002-o5-application-record.md — "Concurrent-modification note (honest): a parallel session was observed modifying O5-adjacent files during this application (timestamps around 17:43-17:49, incl. the plan doc header and the O5 test assertions). The concurrent edits are consistent with this record's post-O5 state" |
| **CLAIM** | A parallel session was modifying O5-adjacent files simultaneously with the O5 application. |
| **CURRENT EVIDENCE** | The O5 application record honestly reports this. No divergence was found. |
| **STATUS** | **VALID** (honestly reported) |
| **REQUIRED CORRECTION** | None needed. The concurrent-modification note is an honest disclosure. |
| **SEVERITY** | **NONE** |

---

## DISCREPANCY SUMMARY

| Severity | Count | R# |
|---|---|---|
| **HIGH** | 5 | R1, R2, R4, R5, R6, R18 |
| **MEDIUM** | 3 | R3, R7, R15 |
| **LOW** | 6 | R8, R9, R10, R11, R12, R13, R14, R16 |
| **NONE** | 3 | R17, R19, R20 |

---

## VERDICTS

### Current Production Verdict

**NOT PRODUCTION-READY** — consistent across all authoritative documents.

All 8 final documents agree on this verdict. G10 (OPEN/BLOCKING), G13 (OPEN/UNKNOWN), and absence of live-DSH proof (D4/D7 marker unset) are the blocking conditions. The deterministic runtime and L2-LIVE evidence (INT-01/07/11/12) are proven, but the live bridge, answerer, and DSH-layer path isolation are not. The regression-count discrepancy (R1) and stale blocker counts (R4, R5) do not change the production verdict — it remains NOT PRODUCTION-READY regardless.

### Current Security Verdict

**PARTIAL** — consistent across all authoritative documents.

| Level | Status |
|---|---|
| **L1 (project control-plane logic)** | CLOSED — all deterministic suites green |
| **L2 (DSH-native config)** | CLOSED — toolFilter, role instances, session sandbox |
| **L2-LIVE (real DSH proof)** | PARTIAL — INT-01/07/11/12 proven; all Phase-5 live variants BLOCKED |
| **L3 (independently verified runtime)** | ZERO controls — same-UID sandbox prevents any L3 claim |
| **UNKNOWN** | G13 prompt-injection (DSH layer); per-session sandbox limitation (PS-2) |

The G5 = CLOSED (infrastructure) vs BLOCKED (master gate) contradiction (R3) is resolved by the final docs being authoritative: the verifier infrastructure is built, but live L3 execution is BLOCKED.

### Current L3 Verdict

**NOT CLAIMED — ZERO controls are L3.** Consistent across all docs.

The exact blocker count is disputed: 5 (stale) vs 3 (corrected) (R4). The authoritative count is **3** (L3ENV-UID-2, L3ENV-D4D7-3, L3ENV-PLAN-REAL) per the environment/final docs which incorporate the approval-probe repair. The l3/final docs and final/acceptance §11.3 still list the obsolete 5-blocker set.

### Exact Blockers (authoritative, post-repair)

1. **L3ENV-UID-2** — separate UID (IO-2): same-UID host (uid=1000)
2. **L3ENV-D4D7-3** — live bridge marker: DSH_LIVE_BRIDGE_ACTIVE unset
3. **L3ENV-PLAN-REAL** — no real Human signoff observed (fixture only)

Additional load-bearing conditions (not probe-blocking but required for any claim):
- P1-live absent: LiveDSHRuntimeDriver refuses live dispatch
- Authorized run not granted: no Human acceptance of docs/security/0003 §15
- G10/G13 OPEN/BLOCKING: project security gates not closed

(L3ENV-ANS-1 and L3ENV-ANS-2 are **no longer blockers** — the approval-probe repair determined the answerer is available by composition in the web GUI session. L3ENV-ANS-1/2 PASS. E2E approval status = UNKNOWN, not FAIL.)

---

## EXACT NEXT ACTIONS

### Within the evidence set (documentation corrections)

| # | Action | Target | R# |
|---|---|---|---|
| 1 | Re-run and record ONE authoritative full-regression count; reconcile 1597 vs 1642 vs 1898 | final/0001, final/0005, l3/final/0001 | R1 |
| 2 | Reconcile L3 test counts (148 vs 275 vs 389 vs 545) across final docs | final/0004, l3/environment/0002, l3/final/0001, l3/final/0002 | R2 |
| 3 | Update master-integration-gate G5 row from BLOCKED to CLOSED (infrastructure) | master-integration-gate.md | R3 |
| 4 | Update l3/final/0001, l3/final/0002 blocker lists from 5 to 3 (remove ANS-1/2) | l3/final/0001, l3/final/0002 | R4 |
| 5 | Update final/acceptance §11.3 blocker list from 5 to 3; reconcile with §4 | final/acceptance/0001 | R4, R6 |
| 6 | Update final/0001 §5-6 approval answerer claims to reflect post-repair state | final/0001 | R5, R18 |
| 7 | Update final/0005 §0 approval answerer claim to reflect post-repair state | final/0005 | R5 |
| 8 | Reconcile O5 plan (Session E) vs application record (Session A) session labels | security/g10/implementation/0001, 0002 | R7 |
| 9 | Update final/preflight approval-probe detection (C3/C4) | final/preflight/0001 | R8 |
| 10 | Update D4D7 live bridge readiness doc blocker B4 (remove ANS-1/2) | environment/live-bridge/0001 | R10 |
| 11 | Update master-integration-gate authorization test count (91->178) | master-integration-gate.md | R11 |
| 12 | Fix preflight companion path reference (docs/phase-5/l3/environment/final/ -> actual path) | final/preflight/0001 | R14 |
| 13 | Reconcile environment/final/0002 vs 0001 session labels (B supersedes D) | environment/final/0001, 0002 | R15 |
| 14 | Add annotation to session-a preflight record noting superseded probe | l3/environment/0002 | R9 |
| 15 | Reconcile G10 test counts (78 vs 114 vs 150) across security docs | security/g10/* | R13 |

### Operational (to unblock live dispatch / L3 / production)

| # | Action | Blocks |
|---|---|---|
| 16 | Provision separate-UID verifier launch path (setuid/separate user/separate host) | L3 claim |
| 17 | Run per-session D4/D7 mount-verification + set DSH_LIVE_BRIDGE_ACTIVE=1 | Live dispatch, L3 P1 |
| 18 | Human signs each scenario plan.json with durable identity | L3 O4 oracle |
| 19 | Human accepts docs/security/0003 §15 (L3 execution protocol) | Authorized live run |
| 20 | Run G13 adversarial live test with REAL DSH child observable | G13 resolution |
| 21 | Implement O3 dedicated registry/audit daemon (or upgrade DSH for O4) | G10 closure |
| 22 | Resolve the approval-probe repair adoption across all final docs (actions 4-9 above) | Document consistency |

---

*Status: AUDIT COMPLETE. 20 discrepancies documented (5 STALE, 5 CONTRADICTORY, 3 MISSING EVIDENCE, 5 VALID, 2 UNKNOWN). Production verdict: NOT PRODUCTION-READY (unchanged). Security verdict: PARTIAL (unchanged). L3 verdict: NOT CLAIMED, ZERO controls (unchanged). Exact blockers: 3 L3-specific (post-repair) + 4 additional load-bearing conditions. No gate was closed by any document. No production-ready claim was made.*


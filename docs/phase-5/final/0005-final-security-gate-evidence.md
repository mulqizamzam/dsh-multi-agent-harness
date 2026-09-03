# Final Security Gate Evidence — G10 / G13 / L3 (CLOSURE GATE)

- **Milestone**: Phase 5 — FINAL SECURITY GATE (consolidated evidence for G10, G13, L3)
- **Status**: **GATE EVIDENCE REPORT** (all evidence gathered; **no production deployment started; no G10/G13/L3 closure claimed; no control declared L3; no production-readiness declared**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/final/0005-final-security-gate-evidence.md` (this file, write-only). All evidence was gathered in this session by running the documented commands; no evidence is invented, extrapolated, or upgraded.
- **Inputs**: `docs/phase-5/final/0002-g10-formal-residual-proof.md` · `0003-g13-external-content-evidence.md` · `0004-l3-critical-controls-evidence.md` · `docs/phase-5/0001-security-hardening-analysis.md` · `docs/phase-5/master-integration-gate.md` · `docs/phase-5/final/0001-security-closure-matrix.md` · `docs/security/0001–0008` · `tests/` (all suites re-run this session).

---

## 0. Environment state (facts, not assumptions)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` (pinned) | `package.json`, `dsh --version` |
| File sandbox policy | `workspace-write` | Session runtime context |
| Approval policy | `ask` | Session runtime context |
| Approval answerer | **Unavailable** (prompts disabled) | Environment probe |
| DSH live bridge marker | **UNSET** (`DSH_LIVE_BRIDGE_ACTIVE` not set) | Shell env check |
| Host UID | Same-UID (1000) for orchestrator and verifier | `uid_readiness` probe |
| L3 claim possible | **No** (IO-2 fails; `l3_claim_possible=False`) | Preflight, UID readiness, rehearsal |
| Phase-5 test suite | **1642 passed, 15 skipped** (full regression; includes the +17 concurrent Session-D environment-readiness tests; no Phase-3 regression) | `pytest tests/ -q` |

---

## 1. G10 — HARDEN / BLOCKING SECURITY GATE

### Requirement
G10 hardening must **close the raw DSH filesystem bypass path** OR **formally prove the exact residual and the required DSH capability**.

### Verdict: G10 OPEN — prevention gap formally proven; V1 containment = detection

**The residual (R):** A raw-write-capable role (`{cto, zeko, somad, nova}` — any role with `bash` and/or `write`/`edit` in its toolFilter allow set) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that **bypasses the project write channel**. The project execution gate (`control/execution_gate.py`) governs only channeled writes; it is a code channel, not a DSH interception point (ADR 0002).

**Why prevention cannot close in this session:**
| Option | Constraint |
|---|---|
| O5 — reduce bash/write/edit surface | Requires Human-approved composition change (ADR 0001 Decision 4/7 HUMAN_PENDING) |
| O3 — out-of-process registry | Requires Human-approved infrastructure change (ADR 0002 consequence 4) |
| O2 — registry outside workspace | Rejected for V1 (ADR 0002 Option A analysis); requires per-agent sandbox |
| **O4 — per-agent/path-level sandbox** | **DSH capability absent from 0.1.1-rc.2** — sandbox is per-session (`child-agent.ts:180`), toolFilter is tool-name-level (`ToolRestriction` string arrays), no per-path allow/deny on filesystem tools |

**Required DSH capability (O4):** A per-agent sandbox root or per-path allow/deny on filesystem tools. DSH `0.1.1-rc.2` provides only a per-session workspace-root sandbox (`isLexicallyUnder(path, root)` in `fs-sandbox/src/containment.ts`) and tool-level toolFilter (`ToolRestriction` in `subagent/src/types.ts`). Neither allows path-level differentiation within the workspace.

**What IS enforced at the project layer (V1 containment = detection):**
- L1 execution gate: `authorize_write()` with `PROTECTED_REL_ROOTS` (`state/registry`, `audit`) and `SANCTIONED_ROOTS` per-channel scoping — DENY on channeled protected-path writes, traversal, symlink escape, prefix confusion
- Detection: append-only audit ledger + cumulative SHA-256 hash chain (`audit/helpers/append_log.py`, `integrity.py`); CAS version checking (`state/helpers/version_check.py`); truncation/duplicate/ordering detection (`audit/hardening/detection.py`)
- ToolFilter: read-only roles (`cfo`, `kai`, `badsector`) deny `bash`/`write`/`edit` at the DSH layer

### Evidence produced
| Evidence | Location | Observed |
|---|---|---|
| Formal residual proof report | `docs/phase-5/final/0002-g10-formal-residual-proof.md` | 216 lines, 22 KB |
| Negative path-isolation tests | `tests/phase5_security/test_negative_path_isolation.py` | 8 tests passed (14 total in suite) |
| Project-layer gate tests | `tests/authorization/` | 178 passed |
| DSH capability verification | `/home/administrator/deepseek-harness` (read-only) | `child-agent.ts:180` per-session sandbox; `ToolRestriction` tool-level only; `fs-sandbox/containment.ts` root-based containment |

**G10 gate status: OPEN — prevention is a DSH-capability gap (O4 absent in 0.1.1-rc.2). V1 containment = detection. No closure claimed.**

---

## 2. G13 — VERIFY / REQUIRED BEFORE FINAL SECURITY ACCEPTANCE

### Requirement
G13 verification must **test prompt-injection / external-content handling**.

### Verdict: G13 OPEN — deterministic defenses verified; full closure UNKNOWN — no claim

**What is verified (deterministic, 111 tests):**
| Entry point | Defense | Tests |
|---|---|---|
| `extra_context` passed to child | Authority-shaped keys stripped + recorded (THREAT-020) | `test_authority_keys_removed_from_context` (phase5) |
| Message/payload bodies | `assert_no_authority_in_payload` refuses authority-bearing payloads (THREAT-020) | `test_assert_no_authority_in_payload` (phase5) |
| Malicious structured child result | Cannot grant authority/flip gate/escalate scope — authority reads the delegation registry, not child output | `test_malicious_result_cannot_change_authority` (phase5) + adversarial INJ-101..107, V2-V8 |
| Subdelegation attempt | DENY BY DEFAULT by actor, regardless of content (DLG-003) | `test_specialist_cannot_delegate_even_with_claim` (phase5) |
| Reported SUCCESS | Reported ≠ verified (THREAT-016/AUTH-INV-15); COMPLETE requires observed outcome | `test_claim_without_observed_outcome_no_complete` (phase5) |
| External content channels (web/repo/doc/financial/manuscript/social/agent-message) | Per-channel quarantine + authority-gate invariant; QUARANTINE never authorizes | `test_external_content_injection.py` (86) + `test_injection.py` (19) |

**What is UNKNOWN / not claimed:**
- Live DSH child behavior under prompt-injection payloads (requires the D4/D7 mount — BLOCKED this session)
- DSH driver-internal content-isolation beyond the adapter (ADR 0001 UNKNOWN #1)
- Novel/obfuscated payload detection beyond the marker-keyword baseline
- `web_fetch` tool not exercised in any adversarial test

### Evidence produced
| Evidence | Location | Observed |
|---|---|---|
| External-content verification evidence report | `docs/phase-5/final/0003-g13-external-content-evidence.md` | 126 lines |
| Phase-5 security tests | `tests/phase5_security/test_external_content_data.py` | 6 tests passed (14 total in suite) |
| Adversarial injection tests | `tests/adversarial/test_external_content_injection.py` + `test_injection.py` | 105 tests passed |
| **Total G13-relevant tests** | **111** | **All passed** |

**G13 gate status: OPEN — deterministic defenses verified; full closure UNKNOWN — no prompt-injection claim made anywhere.**

---

## 3. L3 — VERIFY CRITICAL CONTROLS ONLY

### Requirement
L3 must **independently verify critical controls**: AUTHORITY, CONSEQUENTIAL EXECUTION, RECOVERY, STATE/AUDIT INTEGRITY.

### Verdict: L3 NOT CLAIMED — independent oracles verified; infrastructure rehearsed; same-UID sandbox prevents any L3 claim (IO-2 fails honestly)

**L3 definition (P1–P4):** A control is L3 only when all four hold simultaneously: **P1** runtime, **P2** independent observer, **P3** external oracle, **P4** reproducible. *A test that fails any property is at best L1/L2 — never upgraded to L3* (0003 §1).

**Independent oracles for the four critical controls (O1, self-contained, no production imports):**
| Critical control | Oracle file | Verified behaviour |
|---|---|---|
| **AUTHORITY** | `tests/l3_reference/authority_gate.py` | ALLOW valid delegation; DENY revoked delegation; DENY model-text authority |
| **CONSEQUENTIAL EXECUTION** | `tests/l3_reference/execution_gate.py` | DENY protected-path write; ALLOW normal workspace write |
| **RECOVERY** | `tests/l3_reference/recovery_gate.py` | DENY blind/identical-cause/escalation; ALLOW new-cause within cap |
| **STATE/AUDIT INTEGRITY** | `tests/l3_reference/transition_gate.py` + `tests/l3_reference/audit_chain.py` | ALLOW legal transition; DENY skipped-gate/stale-CAS; VALID/INVALID chain verification |

**Why no L3 claim is possible:**
1. **Same-UID sandbox**: IO-2 fails honestly (verifier and orchestrator share host UID 1000) → `l3_claim_possible=False` (preflight, UID readiness, and rehearsal all report it)
2. **No live DSH session**: `LiveDSHRuntimeDriver` is a `NotImplementedError` stub; runner refuses `--mode live`
3. **No Human-signed plan**: Fixtures are inert templates; no real Human signoff observed
4. **No authorized run**: L3 execution requires Human acceptance of `0003` §15, not granted
5. **Rehearsal bundles are not L3 evidence**: Produce `l3_claim=false` and fail LV10 by design

### Evidence produced
| Evidence | Location | Observed |
|---|---|---|
| L3 critical-controls verification evidence report | `docs/phase-5/final/0004-l3-critical-controls-evidence.md` | 178 lines |
| L3 infrastructure + reference tests | `tests/l3_runner/` + `tests/l3_reference/` | **148 passed** (including 17 concurrent Session-D environment-readiness tests) |
| Authority oracle tests | `test_l3_infrastructure.py` | 41 tests (ALLOW, DENY, ESCALATE, expiry, revocation, text authority) |
| Execution gate oracle tests | `test_l3_infrastructure.py` | Protected-path, traversal, writer-scope, prefix-confusion |
| Recovery oracle tests | `test_l3_infrastructure.py` | Blind retry, identical-cause, privilege escalation, version |
| State/audit oracle tests | `test_l3_infrastructure.py` + `test_l3_infrastructure.py` | Transition legality, CAS, mutation detection, strict read |
| UID readiness | `tests/l3_runner/test_l3_uid_readiness.py` | 9 passed; `l3_claim_possible=False`, `same_uid=True` |
| Preflight | `tests/l3_runner/test_l3_preflight.py` | 31 passed; `l3_claim_possible=False` |
| End-to-end rehearsal | `python -m tests.l3_runner rehearsal --scenario L3-TEST-001` | 13-file bundle, `l3_claim=false`, LV10+LV12 reject by design |
| Environment-readiness probe (concurrent Session D) | `tests/l3_runner/environment/readiness.py` + 17 tests | 17 passed; reports host conditions honestly |

**L3 gate status: NOT CLAIMED — zero controls are L3 today. Independent oracles verified; infrastructure rehearsed; same-UID sandbox makes any L3 claim impossible by design.**

---

## 4. Gate status roll-up

| Gate | Classification | Verdict | Reason |
|---|---|---|---|
| **G10** | HARDEN — BLOCKING | **OPEN** | Prevention gap is a DSH-capability gap (O4 per-agent/path-level sandbox absent in 0.1.1-rc.2). Formal residual proof delivered. V1 containment = detection. No closure claimed. |
| **G13** | VERIFY — REQUIRED | **OPEN** | Deterministic defenses verified (111 tests). Full closure UNKNOWN — no prompt-injection claim made. |
| **L3** | VERIFY CRITICAL CONTROLS ONLY | **NOT CLAIMED** | Independent oracles for authority, consequential execution, recovery, state/audit integrity verified. Infrastructure rehearsed. Same-UID sandbox prevents any L3 claim (IO-2 fails honestly). Zero controls L3. |
| **Production deployment** | — | **NOT STARTED** | Unrestricted production deployment explicitly prohibited and not started. |

**No gate is claimed complete. All three remain open/unclaimed with evidence provided.**

---

## 5. Evidence summary (all observed this session)

| Test suite | Observed | Evidence class |
|---|---|---|
| Full regression (`tests/`) | **1642 passed, 15 skipped** (+17 concurrent Session-D environment tests) | Deterministic proof (L1–L2) |
| Phase-5 security (`tests/phase5_security/`) | **14 passed** (8 G10 + 6 G13) | Deterministic proof |
| Authorization (`tests/authorization/`) | **178 passed** | Deterministic proof (L1) |
| Adversarial (`tests/adversarial/`) | **105 passed** (all G13-relevant) | Deterministic proof |
| Evidence QA (`tests/evidence/`) | **36 passed** | Deterministic proof |
| Audit hardening (`tests/audit_hardening/`) | **29 passed** | Deterministic proof |
| L3 infrastructure + reference + environment (`tests/l3_runner/` + `tests/l3_reference/`) | **148 passed** | Deterministic proof (infrastructure readiness) |
| L3 rehearsal (`L3-TEST-001`) | **13-file bundle, `l3_claim=false`, LV10+LV12 by design** | Rehearsal (not L3 evidence) |
| Runtime evidence bundles (`audit/runtime/INT-01/07/11/12`) | **4 bundles, all `valid=true`** | L2-LIVE (Phase-3, verified intact) |
| DSH checkout (read-only) | **Version 0.1.1-rc.2 confirmed; per-session sandbox, tool-level toolFilter, no per-path isolation** | Verified source fact |

---

## 6. Honesty statement

1. **No production deployment was started.** Unrestricted production deployment was explicitly prohibited by the session brief and was not initiated.
2. **No gate is claimed complete.** G10, G13, and L3 each remain open/unclaimed with the evidence provided. The closure matrix (`0001-security-closure-matrix.md`) correctly records G10 OPEN, G13 OPEN, and L3 zero controls.
3. **No control is claimed L3.** Zero controls satisfy P1–P4 simultaneously. The same-UID sandbox makes any L3 claim impossible by design (IO-2 fails honestly). The infrastructure is proven to rehearse honestly (`l3_claim=false`, LV10 fail by design).
4. **No DSH core/profile/preset/session-policy change was made.** The session operated within the `workspace-write + ask` baseline.
5. **No test failure was downgraded or re-labelled.** All test counts are as observed by running the exact commands documented.
6. **No signature was invented.** The signed-plan fixtures remain inert templates; no real Human signoff was observed or claimed.
7. **No prompt-injection claim is made.** G13 remains OPEN/UNKNOWN.
8. **No path-isolation closure is claimed.** G10 remains OPEN (prevention gap is a DSH-capability gap; V1 containment = detection).

---

## 7. What remains for production/L3 readiness

The following conditions remain unsatisfied (unchanged from `0001-security-closure-matrix.md` §7):

1. **Live-DSH evidence wave**: mount D4/D7 → set bridge marker → re-run live variants for G1/G9/G11/G12
2. **Approval answerer**: enable approval prompts + configure live Human answerer (or pre-record signed `approval-<id>` references)
3. **L3 execution**: provision separate-UID verifier host → Human-signed `plan.json` per scenario → authorized live L3 run → committed `audit/l3/` bundles with `l3_claim=true`
4. **G10 closure decision**: Human decision on V2 path isolation (O5/O3/O2 — each requires an approved, reversible composition/process change)
5. **G13 resolution**: authorized adversarial live test of DSH child behavior under injection payloads + documented DSH driver-internal content-isolation findings
6. **HIGH-risk independent verification (VER-2)**: independent measurement channel per action category
7. **Operational envelope**: session-policy baseline guard, provider 429 backoff, CI/CD for live-DSH regression, documented backup/restore

---

## 8. Scope check

**In scope (written this session):** `docs/phase-5/final/0005-final-security-gate-evidence.md` (this file) — **only**.

**Evidence produced by parallel subagents (independent write scopes, each wrote only its output file):**
- `docs/phase-5/final/0002-g10-formal-residual-proof.md` (G10 formal proof)
- `docs/phase-5/final/0003-g13-external-content-evidence.md` (G13 verification evidence)
- `docs/phase-5/final/0004-l3-critical-controls-evidence.md` (L3 critical-controls verification evidence)

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, `tests/` (no test file edited; the 3 subagent reports are evidence docs, not tests), `docs/` outside `docs/phase-5/final/`, DSH core/profile/preset/session policy. No L3 scenario executed. No session-policy change. No control claimed L3. No production deployment started.

---

*Status: FINAL SECURITY GATE — evidence gathered for G10/G13/L3. G10 OPEN (prevention gap formally proven; required DSH capability identified; V1 containment = detection). G13 OPEN (deterministic defenses verified; full closure UNKNOWN — no claim). L3 NOT CLAIMED (oracles verified; infrastructure rehearsed; same-UID sandbox prevents any L3 claim).* **No production deployment started. No gate claimed complete. STOP at final security gate.**

---

## Addendum — O5 applied (post-publication, 2026-08-31)

On 2026-08-31 the Human **APPROVED and APPLIED O5** — removed `write`/`edit` from `somad` and `nova` toolFilter allow sets (containment step), applied consistently across mapping, instance config, policy files, and the live D4/D7 composition. The residual actor set in §1 above is **narrowed from `{cto, zeko, somad, nova}` to `{cto, zeko}`**; somad/nova are now read-only at the DSH tool level. **G10 remains OPEN / BLOCKING for production; no closure of prevention is claimed.** O3 HOLD; O4 (upstream DSH capability) remains the only full-prevention arm. Full record: `docs/phase-5/security/g10/implementation/0002-o5-application-record.md`. This addendum does not retract the evidence above.

*Status: FINAL SECURITY GATE + O5 addendum. G10 remains OPEN/BLOCKING; O5 applied as containment only; no closure of prevention claimed.*
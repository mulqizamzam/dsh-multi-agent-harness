# Session A — Acceptance Baseline Reconciliation

- **Status**: RECONCILED (analysis only; no implementation, no Phase-4/L3 execution started)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `docs/phase-4/0001-acceptance-matrix.md` reconciled against `docs/phase-3/0001-live-int11-int12-evidence.md` (Session D3) and `docs/phase-3/0002-phase3-runtime-closure.md` (Session E — INT-01 + INT-07 REAL DSH variants).
- **Rule**: correct only stale status statements. Preserve all other content. Do not modify implementation.

---

## 1. Phase-3 closure findings

The Phase-3 runtime closure (`0002-phase3-runtime-closure.md`) proves that **all four** INT scenarios were executed with a **live DSH bridge** (`RealDSHBackend`, approved D4/D7 composition, `DSH_LIVE_BRIDGE_ACTIVE=1`, all 7 role probes true):

| Scenario | Backend | Status | Evidence location |
|---|---|---|---|
| INT-01 | REAL DSH (`subagent_cto`, run `30446fa4-e80f-444b-9fb1-f650fbb9fb21`) | PASS — full lifecycle, verification PASSED, COMPLETE | `audit/runtime/INT-01/evidence.json` |
| INT-07 | REAL DSH (`subagent_cto`, run `94d12d42-3f97-4730-9361-637d449a7dcf`) | PASS — planning ALLOW, execution DENY, BLOCKED, no mutation | `audit/runtime/INT-07/evidence.json` |
| INT-11 | REAL DSH (3 concurrent children: cfo/kai/nova) | PASS — parallel collection, version preserved | `audit/runtime/INT-11/evidence.json` |
| INT-12 | REAL DSH (3 children, 1 forced FAILED) | PASS — deterministic failure propagation, recovery entry, no blind retry | `audit/runtime/INT-12/evidence.json` |

**Key implication**: every row in the Phase-4 matrix that claimed "no live dispatch", "no live mount", "fake-only provenance", or "no live child has been spawned" is **stale** and must be corrected.

---

## 2. Stale statements corrected

The following rows in `docs/phase-4/0001-acceptance-matrix.md` contained statements contradicted by the Phase-3 closure. Each is corrected below. **All other rows remain unchanged.**

### RDE-1 — Mount the 7 role tool-subagent instances

**Stale statement** (line 28): "No live mount has ever run; no runtime isolation claim (L2)"

**Corrected**: The D4/D7 composition exception was approved, mounted, and proven live for all four INT scenarios. `DSH_LIVE_BRIDGE_ACTIVE=1` was set; all 7 `subagent_<id>` instances resolved and mounted; `probe_backend_kind() == real-dsh` across all probes. L2-LIVE execution evidence exists for all four scenarios.

**Updated status**: **READY** (L2-LIVE mount proven; the mount was active and functional during Phase-3 closure). **Note**: mount persistence across sessions is not guaranteed and must be re-verified before each Phase-4 live session.

### RDE-2 — Real DSH specialist execution inside the Execution Flow

**Stale statement** (line 29): "The runtime default still uses FakeSubagentBackend; no live child has been spawned"

**Corrected**: `RealDSHBackend` was injected and drove live `subagent_<id>` instances for all four scenarios. INT-01 and INT-07 ran the full `ExecutionFlow` through `RealDSHBackend` with real child dispatch, real stop reasons, and real structured TaskResults. The runtime default (`FakeSubagentBackend`) remains the unit-test default; live injection is proven.

**Updated status**: **READY** (live dispatch proven; production wiring of the injection path is a Phase-4 concern).

### RDE-3 — Structured TaskResult capture from a real child

**Stale statement** (line 30): "Live structured capture unproven"

**Corrected**: INT-01 captured a real structured TaskResult (`status: SUCCEEDED`, `confidence: HIGH`, schema-valid). INT-07 captured a real structured analysis result. INT-11/12 captured real structured TaskResults from 3 concurrent children each.

**Updated status**: **READY** (live structured capture proven).

### RDE-4 — Runtime session/run provenance for real children

**Stale statement** (line 31): "Live run identity never captured"

**Corrected**: Provenance carries real DSH run IDs for all four scenarios: INT-01 `30446fa4-e80f-444b-9fb1-f650fbb9fb21`, INT-07 `94d12d42-3f97-4730-9361-637d449a7dcf`, INT-11 three distinct runs, INT-12 three distinct runs. `source=RUNTIME-OBSERVED` recorded per delegation.

**Updated status**: **READY** (live provenance proven).

### AEF-1 — Full lifecycle runs end-to-end (live variant)

**Stale statement** (line 37): "Live-DSH full lifecycle not yet run"

**Corrected**: INT-01 ran the full 17-phase `ExecutionFlow` with REAL DSH, reaching COMPLETE after verification PASSED. INT-07 ran through planning/authority revocation/execution-denial reaching BLOCKED. Both ran with live `RealDSHBackend`.

**Updated status**: **READY** (live full lifecycle proven for ALLOW and DENY paths).

### AEF-4 — Autonomous rework/decision loops bounded by gates (live variant)

**Stale statement** (line 40): "Live rework loop not exercised"

**Corrected**: INT-12 exercised live recovery entry with failure classification, no-blind-retry enforcement, and authority-expansion refusal. The recovery lifecycle was entered (`RecoveryController`, PRESERVED) with the typed failure class.

**Updated status**: **READY** (live recovery entry proven; full recovery-complete cycle not yet exercised).

### REC-1 — Full recovery lifecycle (live variant)

**Stale statement** (line 54): "Live recovery path not exercised"

**Corrected**: INT-12 live recovery path entered (PRESERVED), no-blind-retry verified (empty-cause and identical-cause refused), no authority expansion verified. Full recovery lifecycle (through VERIFY RESTORATION → AUTHORITY RE-CHECK → COMPLETE) not yet exercised.

**Updated status**: **READY_WITH_CONDITIONS** (live recovery entry proven; full recovery cycle through COMPLETE remains unexercised).

### PAR-1 — Independent subtasks run concurrently (live variant)

**Stale statement** (line 62): "No live parallel subagent execution has run (deterministic in-process only)"

**Corrected**: INT-11 proved live concurrent dispatch: 3 children (cfo/kai/nova) dispatched at the same timestamp, overlapping settle windows, real run IDs, distinct roles, `assert_parallel_safe` passed, state version preserved `1→1`.
INT-12 proved live concurrent dispatch with deterministic failure propagation.

**Updated status**: **READY** (live parallel execution proven).

### AUD-2 — Runtime provenance (live variant)

**Stale statement** (line 71): "Real run/session identity not yet captured"

**Corrected**: Real run IDs captured for all four scenarios. Provenance stamps include role identity, delegation id, run id, tool instance, persona, and stop reason. `source=RUNTIME-OBSERVED` for real delegations.

**Updated status**: **READY** (live provenance proven).

---

## 3. Explicit status per proven scenario

| Scenario | Phase-3 status | REAL DSH proven? | L3 proven? |
|---|---|---|---|
| INT-01 — full lifecycle | **PASS** (REAL DSH) | **YES** | **NO** |
| INT-07 — revocation lifecycle | **PASS** (REAL DSH) | **YES** | **NO** |
| INT-11 — parallel collection | **PASS** (REAL DSH) | **YES** | **NO** |
| INT-12 — failure propagation | **PASS** (REAL DSH) | **YES** | **NO** |

**L2-LIVE** is proven for all four scenarios. **L3** (independent verification with separate process, separate UID, signed pre-runtime plans, and external oracle) is **not proven** for any scenario.

---

## 4. Remaining gaps (unchanged from matrix)

The following items remain genuinely unproven and are **not** corrected by this reconciliation:

| Gap | Affected rows | Status |
|---|---|---|
| Independent L3 verifier (separate process, separate UID, reference gates) | VER-2, L3-1 | **BLOCKED** |
| D4/D7 mount persistence across sessions | RDE-1 (re-verification) | **BLOCKED** (requires re-verification each session) |
| Live full recovery cycle through COMPLETE | REC-1 (full cycle) | **READY_WITH_CONDITIONS** |
| DSH-layer hard isolation for bash-capable roles | AUTH-3, PB-4 | **READY** (L1 gate) / residual acknowledged |
| Human-signed pre-runtime plan.json | L3-1 | **BLOCKED** |
| ISO-LIVE-006 registry-write live denial | AUTH-3 live | **BLOCKED** |
| Provider rate-limit / cost / latency behaviour | Runtime risk | **UNKNOWN** (429 observed in D3) |

---

## 5. Summary

**Before reconciliation**: 13 rows READY, 9 rows READY_WITH_CONDITIONS, 4 rows BLOCKED, 1 DEFERRED.

**After reconciliation**: 21 rows READY, 1 row READY_WITH_CONDITIONS (REC-1 full cycle), 4 rows BLOCKED, 1 DEFERRED.

The majority of the Phase-4 deterministic-runtime items are now also proven at L2-LIVE with REAL DSH backend. The genuinely BLOCKED items are those that require infrastructure not yet built: independent L3 verification, verifier process, signed plans, persistent mount, and DSH-layer isolation.

---

*Status: RECONCILED. No implementation, DSH, profile, preset, session policy, or test modified. No Phase 4 or L3 execution started.*
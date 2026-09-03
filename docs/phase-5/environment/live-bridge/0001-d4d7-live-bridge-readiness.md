# D4/D7 Live Bridge Readiness + Re-Verification (Session A)

- **Milestone**: Phase 5 / Session A — D4/D7 LIVE BRIDGE READINESS + RE-VERIFICATION
- **Status**: READINESS ASSESSMENT (read-only verification; **no DSH change, no profile/preset change, no session-policy change, no new composition, no new tools, no live dispatch, no G13/L3 execution**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified: `package.json` → `0.1.1-rc.2`; `dsh --version` → `0.1.1-rc.2`)
- **Scope (write-only)**: `docs/phase-5/environment/live-bridge/` + `tests/l3_runner/environment/live-bridge/`.
- **Companion**: `docs/phase-1/0003..0005` (D4/D7 composition + corrections) · `docs/phase-5/environment/0001-environment-readiness-spec.md` (§2 per-session mount-verification) · `docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md` · `tests/l3_runner/environment/readiness.py` · `tests/environment/preflight.py` · `tests/live_dsh/*` · `orchestrator/dsh/bridge.py` · `orchestrator/runtime/flow.py` (backend selection) · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · `agents/<id>/policy.yaml` · live `$DSH_HOME/profiles/web/cordis.patch.yml` · `tests/g10/` (post-O5).

---

## 0. One-line verdict

**The current session can NOT safely activate the live D4/D7 bridge as-is:** the composition **files are complete, consistent and valid** (7 presets + 7 rows + mapping==policy==instance + allow∩deny=∅ + corrected deny lists), but the **bridge is inactive** — `DSH_LIVE_BRIDGE_ACTIVE` is **unset**, the backend probes **UNAVAILABLE**, and no live dispatch bridge is injected. **Live DSH child observation is NOT possible this session.** Activation requires the exact operator sequence below; the session itself performs **no** live dispatch (fail-closed).

---

## 1. Return values (exact)

### D4D7_FILES

| File / artifact | State | Evidence |
|---|---|---|
| 7 role presets under `$DSH_HOME/.agent-presets/` | **PRESENT (7/7)** | `ls -d $DSH_HOME/.agent-presets/role-*` → `role-badsector, role-cfo, role-cto, role-kai, role-nova, role-somad, role-zeko` (7 dirs) |
| 7 `tool-subagent-<id>` rows in `$DSH_HOME/profiles/web/cordis.patch.yml` | **PRESENT (7/7)** | `grep -c 'toolName: subagent_' …/cordis.patch.yml` → `7` |
| `config/role-preset-mapping.yaml` | present, post-O5 | SHA-256 `1826c6f8…776` |
| `config/tool-subagent-instances.yaml` | present, post-O5 | SHA-256 `be960cbf…c69` |
| `agents/{zeko,cto,cfo,kai,somad,badsector,nova}/policy.yaml` | present, post-O5 | hashes §3 |

**D4D7_FILES = READY (persistent on disk).** The composition artifacts exist; persistence is per-file only — the live bridge is still required for dispatch.

### D4D7_COMPOSITION

- **mapping == policy == instance: PASS** — `tests/validate_config.py` → **194 passed, 0 failed** (mapping==policy allow/deny, instance==mapping, tool names verified, allow∩deny=∅, read-only discipline).
- **allow ∩ deny = ∅: PASS** (all 7 roles + orchestrator).
- **Role/toolFilter invariants intact: PASS** — deny lists match the 0005-corrected counts (zeko 11, cto 11, cfo 14, kai 14, somad 12, badsector 15, nova 13) with **zero** of the 25 VERIFIED_UNREGISTERED names and **zero** `run_code` remaining (0004/0005 corrections present). Post-O5 state holds: `somad`/`nova` have no `write`/`edit`; `zeko`/`cto` retain `bash`+`write`+`edit`.
- **Live rows match config: PASS** — all 7 `tool-subagent-<id>` rows in `cordis.patch.yml` match the mapping allow+deny exactly (scripted check).
- **Role resolution: PASS** — `tests/live_dsh/discovery.assert_role_resolution()` resolves all 7 roles → `subagent_<id>`.

**D4D7_COMPOSITION = CONSISTENT and VALID (static).**

> **Approval-record nuance (honest):** the 25-name removal (docs/phase-1/0005) is recorded as **PENDING_HUMAN_APPROVAL** in its change-request doc, yet the current files already carry the corrected deny lists (validated, hashes match the 0005 "after" column). Operators should confirm the 0005 approval signature for the record; the current configuration is valid and consistent regardless. This does not change the live-bridge verdict.

### BRIDGE_MARKER

- `DSH_LIVE_BRIDGE_ACTIVE` = **UNSET** (empty).
- All 7 mount probes (`tests/live_dsh/discovery.probe_all_instances_mounted()`) → **False**.
- `tests/l3_runner/environment/readiness` → **`L3ENV-D4D7-3` FAIL** (live bridge marker not set).

**BRIDGE_MARKER = NOT SET** → per the fail-closed rule (`docs/phase-5/environment/0001` §2.2), the bridge is **UNAVAILABLE**; no live dispatch is attempted.

### REAL_BACKEND

- `orchestrator/dsh/bridge.probe_backend_kind()` → **`BackendKind.UNAVAILABLE`**.
- `BackendKind.REAL` is only reported when the marker is set; it is **not** reported.
- `orchestrator/runtime/flow.probe_backend()` would show `backend_kind=unavailable`, `bridge_marker_active=False`, `live_dispatch_injected=…`.

**REAL_BACKEND = NOT AVAILABLE** (marker absent). A REAL `start()` would raise `BridgeNotAvailable` (fail-closed; no silent fallback to FAKE — G1-3).

### LIVE_DISPATCH_POSSIBLE

- **NO.** The marker is unset ⇒ the bridge is UNAVAILABLE ⇒ any requested REAL dispatch raises `BridgeNotAvailable` and the flow stops BLOCKED.
- **Smoke-dispatch prerequisite defined but NOT executed:** the already-approved composition (docs/phase-1/0003 §9) defines ISO-LIVE-001..005/007 as the safe, non-destructive smoke suite after a verified mount. Per the brief, **no dispatch is performed** unless the composition explicitly permits it and the mount is active — neither holds this session (marker unset, no injected dispatch bridge).

**LIVE_DISPATCH_POSSIBLE = NO (this session).**

### BLOCKERS

| # | Blocker | Class | Detail |
|---|---|---|---|
| B1 | **`DSH_LIVE_BRIDGE_ACTIVE` unset** (`L3ENV-D4D7-3`) | D4D7 (primary) | Marker absent ⇒ bridge UNAVAILABLE ⇒ `BridgeNotAvailable` on any REAL dispatch |
| B2 | **No live dispatch bridge injected** | D4D7 | `RealDSHBackend.start()` requires an injected `DSHBridgeDispatch` (the orchestrator session's live `subagent_<id>` tool surface); none is injected in this session |
| B3 | **No live DSH child observation performed** | D4D7 | Per-session mount-verification steps 1–5 not all green (marker fails), so no smoke (step 6) is run — fail-closed |
| B4 | **Approval answerer absent** (`L3ENV-ANS-1` / `ANS-2`) | G3 | No live Human answerer; `ask` resolves `unavailable` → DENY + escalate. Not a D4D7 blocker per se, but blocks any approval-dependent execution around the bridge |
| B5 | **Same-UID host** (`L3ENV-UID-2`) | L3 | Verifier/orchestrator same UID 1000 ⇒ any L3 claim impossible (not a D4D7 blocker) |
| B6 | **No real Human signoff** (`L3ENV-PLAN-REAL`) | L3 | Fixture signoff only (not a D4D7 blocker) |
| B7 | **G10/G13 OPEN / BLOCKING** (unchanged) | project security | G10 raw-write residual `{zeko, cto}`; G13 injection UNKNOWN — a live observation would not change these, and no closure is claimed |

**BLOCKERS = 7** (2 direct D4D7-construction/activation blockers B1/B2/B3, plus G3/L3/project-security blockers B4–B7). L3 claim impossible (`l3_claim_possible=False`, exactly 5 L3-required blockers per the final checklist); rehearsal machinery ready (`rehearsal_ready=True`).

### EXACT_OPERATOR_ACTIONS (to safely activate + observe)

1. **Re-verify composition (already green, confirm only):** 7 presets present, 7 rows present, `mapping==policy==instance`, `allow∩deny=∅`, deny-list hygiene (no `run_code`, no 25 UNREG names), post-O5 role/toolFilter invariants. Run `tests/validate_config.py` (194) + `tests/g10/` (114).
2. **Confirm the 0005 approval record** for the 25-name removal (files corrected; operator signs off the record if not already approved).
3. **Set the marker** in the orchestrator session: `export DSH_LIVE_BRIDGE_ACTIVE=1` — ONLY after step 1 passes (fail-closed: a marker without a verified mount is a stale mount → escalate; `docs/phase-5/environment/0001` §2.2).
4. **Verify the backend flips to REAL:** `probe_backend_kind() == real-dsh`; all 7 `probe_all_instances_mounted()` → True; `flow.probe_backend()` shows `bridge_marker_active=True`.
5. **Inject the live dispatch bridge** into `RealDSHBackend` (the orchestrator session's actual `subagent_<id>` tool surface). This is the only live tool-call boundary.
6. **Run the smoke suite** ISO-LIVE-001..005 + 007 (schema dumps, exact denial messages, audit events — no evidence = NOT PROVEN). **Do NOT run ISO-LIVE-006** (registry-write denial at DSH layer — execution gate is L1-design, still BLOCKED per 0004 §6).
7. **Re-run validation after mount** to confirm nothing drifted; audit the activation/rollback.
8. **Do NOT** execute G13/L3, do NOT claim L2 beyond observed live evidence, do NOT claim G10 closure.

---

## 2. Per-session mount-verification procedure (status of each step)

From `docs/phase-5/environment/0001` §2.2:

| Step | Check | Status |
|---|---|---|
| 1 | 7 role presets present | **PASS** |
| 2 | 7 instance rows in `cordis.patch.yml` | **PASS** |
| 3 | `DSH_LIVE_BRIDGE_ACTIVE=1` set | **FAIL (unset)** |
| 4 | `RoleResolver` resolves all 7; `assert_role_resolution()` | **PASS** |
| 5 | `probe_backend_kind() == real-dsh` + 7 mount probes True | **FAIL** (marker unset ⇒ UNAVAILABLE) |
| 6 | minimal live `subagent_<id>` smoke settles with real run id | **NOT RUN** (fail-closed: steps 3/5 not green) |

**Fail-closed rule holds:** with step 3 or 5 failing, the session treats the bridge as UNAVAILABLE — no live dispatch, no silent fake fallback, flows requiring REAL dispatch STOP/BLOCK (`BridgeNotAvailable`).

---

## 3. Verification evidence (this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json`; `dsh --version` |
| `DSH_HOME` | `/home/administrator/agent-workspace/.dsh` | env |
| Role presets | 7 present | `ls $DSH_HOME/.agent-presets/` |
| Instance rows | 7 | `grep -c 'toolName: subagent_' cordis.patch.yml` |
| `DSH_LIVE_BRIDGE_ACTIVE` | unset | env |
| Backend kind | `BackendKind.UNAVAILABLE` | `probe_backend_kind()` |
| Mount probes | all False | `probe_all_instances_mounted()` |
| config validation | 194 passed, 0 failed | `tests/validate_config.py` |
| G10 suite (post-O5) | 114 passed | `tests/g10/` |
| L3 readiness | `l3_claim_possible=False`, `rehearsal_ready=True`, 5 blockers | readiness probe (scenario `L3-TEST-001`) |
| Deny-list hygiene | 0 unregistered / 0 reserved names | scripted set check |
| mapping==policy==instance | PASS | validate_config + scripted check |
| allow ∩ deny = ∅ | PASS | validate_config |

---

## 4. Honesty statement

1. **No DSH core / profile / preset / session-policy / composition / tool change was made.** No new composition, no new tool enabled, no marker set, no live dispatch, no G13/L3 execution.
2. **No live DSH child observation was performed.** The bridge is UNAVAILABLE (marker unset, no injected dispatch); the smoke is defined as a prerequisite, not executed.
3. **`DSH_LIVE_BRIDGE_ACTIVE` remains unset.** The session did not set it; setting it is an operator action after the fail-closed verification above.
4. **No closure is claimed.** G10 remains OPEN/BLOCKING (`{zeko, cto}` raw-write residual); G13 remains OPEN/UNKNOWN; no L2 claim beyond observed live evidence (none this session).
5. **The 0005 approval-record nuance is reported**, not resolved: files are corrected/valid; the change-request record shows PENDING.
6. **All test counts are as observed** by running the documented commands; no failure hidden or downgraded.

---

## 5. Scope check

**In scope (written this session):** `docs/phase-5/environment/live-bridge/0001-d4d7-live-bridge-readiness.md` (this file) + `tests/l3_runner/environment/live-bridge/test_live_bridge_readiness.py`.

**Not modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, the live composition `$DSH_HOME/profiles/web/cordis.patch.yml`, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/`, and all other `docs/`. No marker set. No live dispatch. No G13/L3 execution. No closure claim.

---

*Status: READINESS ASSESSMENT. D4D7_FILES=READY (7 presets + 7 rows), D4D7_COMPOSITION=CONSISTENT/VALID (mapping==policy==instance, deny hygiene), BRIDGE_MARKER=UNSET, REAL_BACKEND=UNAVAILABLE, LIVE_DISPATCH_POSSIBLE=NO (fail-closed), BLOCKERS=7 (B1–B7), EXACT_OPERATOR_ACTIONS documented. No live DSH child observation this session. No change made. No closure claimed.*

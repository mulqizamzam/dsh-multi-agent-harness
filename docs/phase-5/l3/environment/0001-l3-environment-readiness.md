# Phase 5 / Session D — L3 Environment + Human-Answerer Readiness

- **Milestone**: Phase 5 / Session D — L3 ENVIRONMENT + HUMAN-ANSWERER READINESS
- **Status**: READINESS PROBE (deterministic verification of environment prerequisites; **no L3 run executed, no L3 claim, no policy/DSH change**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/l3_runner/environment/` (probe + tests) · `multi-agent-harness/docs/phase-5/l3/environment/` (this file). **No session policy, DSH, DSH profile/preset, production code, or role mapping modified.**
- **Companion**: `docs/security/0007-l3-run-prerequisites.md` · `docs/security/0003-l3-independent-verification-plan.md` · `tests/l3_runner/preflight.py` · `docs/phase-5/l3/0001-l3-execution-readiness.md` · `docs/phase-5/l3/0002-g5-verifier-implementation-report.md` · `docs/phase-5/master-integration-gate.md` · D4/D7 change requests `docs/phase-1/0003..0005`.

---

## 1. What this session prepared

The task was to **prepare the environment required for a legitimate L3 run**: verify each prerequisite with a read-only probe, and where a prerequisite is absent, report **BLOCKED with the exact missing dependency** — never a simulated PASS, never an invented Human signature, never a policy change to force a pass.

Two deliverables:

1. **Probe** — `tests/l3_runner/environment/readiness.py` (a read-only assessment that re-uses and extends the existing `preflight.py` PF-* checks into a Session-D determination list with stable `L3ENV-*` ids).
2. **Test suite** — `tests/l3_runner/environment/test_l3_environment_readiness.py` (17 tests) that locks the honesty invariants (read-only probe, no invented signatures, honest same-UID demotion, honest answerer/mount/signoff absence).

The probe covers every determination in the session brief:
separate process capability, separate UID capability, verifier executable availability, clean oracle imports, Human answerer availability, approval path availability, D4/D7 mount persistence, signed-plan mechanism, evidence-store readiness, replay readiness.

---

## 2. Preflight verification — PF-* check results (this session)

Run: `python -m tests.l3_runner.environment.readiness --scenario L3-TEST-001 --orchestrator-uid 1000 --json`

### 2.1 PF-UID-1/2/3 — separate process / UID / session tree

| Check | Result | Detail |
|---|---|---|
| **PF-UID-1** (IO-1) separate OS process | **PASS** | The runner spawns the verifier via `subprocess` (distinct PID). A distinct process is achievable. |
| **PF-UID-2** (IO-2) separate UID | **FAIL → BLOCKED (required_for_l3)** | Same-UID host: `orchestrator_uid=1000`, verifier subprocess probe returns `1000` → `same_uid=True`. A separate UID/credential is **not** achievable here (needs setuid / separate user / separate host). This honestly blocks any L3 claim. |
| **PF-UID-3** (IO-4) not in orchestrator session tree | **PASS** | Runner spawns verifier via `subprocess`, never `subagent`/`subagent_fork`/`send_message`. |

### 2.2 PF-VER-1..5 — verifier prerequisites

| Check | Result | Detail |
|---|---|---|
| **PF-VER-1** clean-import guard present | **PASS** | `tests/l3_runner/verifier.py` exists; `assert_clean_imports()` is callable. |
| **PF-VER-2** reference oracle resolves (O1) | **PASS** | `tests/l3_reference/authority_gate.py` resolves with `oracle_authority` for gate `authority`. |
| **PF-VER-3** verifier sha256 computable (IO-3) | **PASS** | `sha256(verifier.py)=125d61d4...` (64 hex). |
| **PF-VER-4** verifier spawns cleanly in a subprocess (P2) | **PASS** | Subprocess probe: `rc=0 stdout=CLEAN` — no production-gate imports (`control.*`, `orchestrator.foundation.*`, `audit.helpers`, `state.helpers`). |
| **PF-VER-5** ≥ 2 oracle classes (IO-6 / R6) | **PASS** | Enforced per-scenario by `runner._require_two_oracles` / verifier. |

### 2.3 PF-ENV-1..4 — environment preflight

| Check | Result | Detail |
|---|---|---|
| **PF-ENV-1** (LV5) DSH pinned to 0.1.1-rc.2 | **PASS** | `dsh_version=0.1.1-rc.2`. |
| **PF-ENV-2** (G9) sandbox/approval baseline `workspace-write` + `ask` | **PASS (REPORT ONLY)** | `sandbox_mode=workspace-write`, `approval_policy=ask`. Session policy is **not** modified. |
| **PF-ENV-3** (LV4) env snapshot fields complete | **PASS** | When no snapshot supplied → report-only pass; a supplied snapshot is validated strictly. |
| **PF-ENV-4** evidence store creatable/writable | **PASS** | `audit/l3` base under a writable project root. The probe never creates it. |

### 2.4 PF-PLAN-1..5 — Human-signed plan prerequisites

| Check | Result | Detail |
|---|---|---|
| **PF-PLAN-1** plan.json present | **PASS** | `L3-TEST-001/plan.json` exists. |
| **PF-PLAN-2** fields schema-valid | **PASS** | `expected_verdict=ALLOW`, required fields present, ts parseable. |
| **PF-PLAN-3** (LV7/IO-7) signoff precedes runtime | **PASS** | `signoff=2026-08-31T00:00:00Z`, no runtime captured yet (ordering enforced strictly once a runtime ts exists). |
| **PF-PLAN-4** expected verdict declared + O4 oracle | **PASS** | `expected_verdict=ALLOW`, `O4` declared. |
| **PF-PLAN-5** (G7) signoff fields schema-valid | **PASS** | `validate_signed_plan` → VALID signed-plan (id pattern / ts format / method enum / ordering). |
| **L3ENV-PLAN-REAL** a REAL Human signoff observed | **FAIL → BLOCKED (required_for_l3)** | The committed plan is a **fixture/template**; `human_signoff_id=human-YYYY-MM-DD-NNN` is inert. No real Human interaction was observed. The probe does **not** invent signatures. |

### 2.5 PF-REP-1..4 — reproducibility

| Check | Result | Detail |
|---|---|---|
| **PF-REP-1** fixture hash deterministic (P4) | **PASS** | `sha256:52037567...` over the `L3-TEST-001` fixture dir. |
| **PF-REP-2** replay script present | **PASS** | `tests/l3_runner/replay.sh`. |
| **PF-REP-3** verifier + schema sha256 recorded | **PASS** | `verifier_sha256=125d61d4...`. |
| **PF-REP-4** no live-network dependency | **PASS** | All L3 scenarios use recorded response fixtures (0003 §8.1). |

---

## 3. Determinations (the session-brief list)

| Determination | Result | Evidence / dependency |
|---|---|---|
| **Separate process capability** | **AVAILABLE** | `subprocess` spawn, distinct PID (PF-UID-1/3); verified by verifier CLEAN subprocess probe. |
| **Separate UID capability** | **NOT AVAILABLE** | Same-UID host (`1000 == 1000`). Requires setuid wrapper / separate user / separate host (PF-UID-2 / IO-2). **BLOCKED for L3.** |
| **Verifier executable availability** | **AVAILABLE** | `tests/l3_runner/verifier.py`, sha256 recorded, subprocess-spawnable clean. |
| **Clean oracle imports** | **VERIFIED** | `assert_clean_imports()` CLEAN in a fresh subprocess; AST/import scan rejects production gates. |
| **Human answerer availability** | **ABSENT** | Approval prompts disabled / no answerer row composed → `ask` resolves `unavailable` (fail-closed DENY + escalate). **BLOCKED for L3 and for interactive/HIGH-risk execution.** |
| **Approval path availability** | **ABSENT** | `approval_policy=ask` but no live answerer → no interactive ALLOW path. **BLOCKED.** |
| **D4/D7 mount persistence** | **PARTIAL** | 7 role presets present (`$DSH_HOME/.agent-presets/`) ✓; 7 `tool-subagent` rows in `cordis.patch.yml` ✓; **bridge marker `DSH_LIVE_BRIDGE_ACTIVE` unset ✗**. Mount is **not persistently active** — must be re-verified per session. **BLOCKED for live DSH dispatch.** |
| **Signed-plan mechanism** | **READY (mechanism)** | PF-PLAN-1..5 pass (schema, ordering, O4). Real signoff: **NOT observed** (fixture only). |
| **Evidence-store readiness** | **READY** | `audit/l3` creatable/writable (probe never creates it). |
| **Replay readiness** | **READY** | PF-REP-1..4 pass; deterministic fixture hash + replay.sh + tooling sha256. |

---

## 4. L3 claim possible?

**`l3_claim_possible = False`** on this host. Honest reasons (all required-for-L3 checks):

1. **L3ENV-UID-2** — separate UID not achievable (same-UID host, IO-2).
2. **L3ENV-ANS-1 / ANS-2** — no live Human answerer; approval path unavailable.
3. **L3ENV-D4D7-3** — live bridge marker `DSH_LIVE_BRIDGE_ACTIVE` unset.
4. **L3ENV-PLAN-REAL** — no real Human signoff observed.

**`rehearsal_ready = True`** — all required checks for the rehearsal machinery pass, so the L3 infrastructure can continue to rehearse (replay bundles with `l3_claim=false`), but **no control is L3 and no live L3 run is authorized.**

---

## 5. BLOCKED — exact missing dependencies

| Blocked prerequisite | Exact missing dependency | Unblocks when |
|---|---|---|
| Separate UID (IO-2) | verifier must run under a distinct UID/credential (setuid wrapper, separate user account, or separate host) | operator/infrastructure provisions a separate-UID launch path |
| Human answerer | a live Human approval answerer composed for the session (approval prompts enabled) | operator enables the answerer path (out of scope for the harness) |
| Approval path | a live answerer for `ask` (or pre-recorded signed `approval-<id>` references for approval-dependent actions) | operator action |
| D4/D7 live bridge | `DSH_LIVE_BRIDGE_ACTIVE=1` for the session (requires the per-session mount verification procedure, `docs/phase-5/environment/0001 §2`) | per-session mount + marker verification |
| Real Human signoff | an actual Human-signed `plan.json` with durable identity, committed before the run (no fixture id) | a real Human signoff via the answerer/interactive path |

---

## 6. Honesty statement

- **No L3 claim.** No live L3 run. No control is L3.
- **No policy change** was made to make any preflight check pass. PF-ENV-2 is report-only.
- **No invented Human signature.** The probe reports the fixture signoff as inert and `L3ENV-PLAN-REAL` fails honestly.
- **No fake credential separation.** Same-UID is reported honestly; `l3_claim_possible=False`.
- **No session policy, DSH, DSH profile/preset, production code, or role mapping modified.**

---

## 7. How to run (read-only)

```bash
# Environment + answerer readiness (JSON)
.venv-tests/bin/python -m tests.l3_runner.environment.readiness \
    --scenario L3-TEST-001 --orchestrator-uid "$(id -u)" --json

# Environment readiness test suite (17 tests)
.venv-tests/bin/python -m pytest tests/l3_runner/environment/ -q

# Full L3 suite (probe + preflight + readiness + rehearsal + verifier)
.venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
```

---

## 8. Scope check

**In scope (written/verified this session):** `tests/l3_runner/environment/` (`readiness.py`, `__init__.py`, `__main__.py`, `test_l3_environment_readiness.py`) · `docs/phase-5/l3/environment/0001-l3-environment-readiness.md` (this file).

**Not modified (verified):** session policy, DSH core, DSH profile/presets, production code (`control/*`, `orchestrator/*`), role mapping (`config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`), `config/*`, `agents/*`, `schemas/*`, any existing test outside `tests/l3_runner/environment/`.

---

*Status: READINESS PROBE. Environment prerequisites verified deterministically; L3 claim NOT possible on this host (separate UID, answerer, live bridge, real signoff all absent); rehearsal machinery ready. No L3 run executed. No L3 claim made.*

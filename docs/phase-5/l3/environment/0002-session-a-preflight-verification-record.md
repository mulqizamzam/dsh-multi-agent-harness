# Session A — L3 Environment + Human-Answerer Readiness (Preflight Verification Record)

- **Session**: SESSION A — L3 ENVIRONMENT + HUMAN-ANSWERER READINESS
- **Status**: **VERIFICATION RECORD** (read-only preflight re-run; **no L3 execution, no L3 claim, no policy/DSH/profile change**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (confirmed from `package.json`)
- **Scope**: `docs/phase-5/l3/environment/0002-session-a-preflight-verification-record.md` (this file, additive — Session A verification). **No session policy, DSH, DSH profile/preset, production code, or role mapping modified.**
- **Companion**: `docs/security/0007-l3-run-prerequisites.md` · `tests/l3_runner/preflight.py` · `tests/l3_runner/environment/readiness.py` · `docs/phase-5/l3/environment/0001-l3-environment-human-answerer-readiness.md` (Session D) · `docs/phase-5/l3/0001-l3-execution-readiness.md` · `docs/phase-5/final/0005-final-security-gate-evidence.md` · `docs/phase-5/final/0001-security-closure-matrix.md`.

> This session **re-runs the read-only preflight** (PF-* and L3ENV-* checks) to
> verify the current environment's L3 readiness state and records the exact
> observed results, blockers, and operator/infrastructure actions still required.
> The environment probe module (`tests/l3_runner/environment/readiness.py`) was
> authored in the prior Session D and is **not modified** here.

---

## 1. Environment state (observed, not assumed)

| Fact | Value | Source |
|---|---|---|
| Host UID | `1000` (administrator) | `id -u` |
| Session PID | The harness process (verified distinct from verifier subprocess via `--orchestrator-pid 99999`) | preflight PF-UID-1 |
| DSH version | `0.1.1-rc.2` | DSH `package.json` |
| File sandbox policy | `workspace-write` | Session runtime context |
| Approval policy | `ask` | Session runtime context |
| Approval answerer | **Absent** — no `user-approval`/`ui-user-questions`/`approval/request` row in `$DSH_HOME/profiles/*` | Readiness probe L3ENV-ANS-1; independent grep confirms no match |
| DSH_APPROVAL_PROMPTS_DISABLED | **unset** (defaults to disabled) | Shell env check |
| D4/D7 role presets | All 7 present (`role-zeko`…`role-nova`) under `$DSH_HOME/.agent-presets/` | Readiness probe L3ENV-D4D7-1 |
| D4/D7 instance rows | 7 rows in `$DSH_HOME/profiles/web/cordis.patch.yml` (`toolName: subagent_zeko`…`subagent_nova`) | Readiness probe L3ENV-D4D7-2; grep confirms 7 |
| DSH_LIVE_BRIDGE_ACTIVE | **unset** (live DSH unavailable) | Shell env check |
| Verifier binary | `tests/l3_runner/verifier.py` exists; sha256=`125d61d4…` (64 hex) | sha256sum |
| Clean oracle imports | `assert_clean_imports()` passes in subprocess (`CLEAN`) | Preflight PF-VER-4 |
| Reference oracle | `tests/l3_reference/authority_gate.py` resolves with `oracle_authority` | Preflight PF-VER-2 |
| Evidence store | `audit/l3/` does **not exist** (probe never creates it); project root writable | `ls` confirms absent |
| Replay script | `tests/l3_runner/replay.sh` present | Preflight PF-REP-2 |
| Fixture hash | `sha256:52037567e3b6546b0d858b48f7a8ea9894f0635b03625e5a8210d56ca9bd05ca` (L3-TEST-001) | Preflight PF-REP-1 |
| Signed plan fixture | `L3-TEST-001/plan.json` schema-valid; O4 oracle declared; signoff id `human-2026-08-31-001` (inert template, not a real Human signoff) | Preflight PF-PLAN-1..5 |

---

## 2. Preflight (PF-*) results — observed this session

Run: `.venv-tests/bin/python -m tests.l3_runner.preflight --scenario L3-TEST-001 --fixtures-root tests/l3_reference/fixtures --json`

Exit code: **0** · `all_required_pass=True` · `l3_claim_possible=False`

### 2.1 Separate UID/process (PF-UID-1..3)

| Check | Result | Detail |
|---|---|---|
| **PF-UID-1** (IO-1) separate OS process | **PASS** | When orchestrator PID supplied (99999), verifier PID (3) is distinct. With no orchestrator PID supplied, passes as report-only. |
| **PF-UID-2** (IO-2) separate UID | **SKIP (required=False)** | **Same-UID host** — orchestrator and verifier probe both `uid=1000`. Honest FAIL for L3 claim; rehearsal machinery unaffected. |
| **PF-UID-3** (IO-4) not in orchestrator session tree | **PASS** | Runner spawns verifier via `subprocess`, never `subagent`/`subagent_fork`/`send_message`. |

### 2.2 Verifier prerequisites (PF-VER-1..5)

| Check | Result | Detail |
|---|---|---|
| **PF-VER-1** clean-import guard present | **PASS** | `verifier.py` exists; `assert_clean_imports()` callable. |
| **PF-VER-2** reference oracle resolves (O1) | **PASS** | `authority_gate.py` resolves for gate `authority`. |
| **PF-VER-3** verifier sha256 (IO-3) | **PASS** | `sha256=125d61d41bb3d723…` |
| **PF-VER-4** verifier spawns cleanly (P2) | **PASS** | Subprocess: `rc=0 stdout=CLEAN` — no production imports. |
| **PF-VER-5** ≥ 2 oracle classes (IO-6) | **PASS** | Enforced per-scenario by runner. |

### 2.3 Environment (PF-ENV-1..4)

| Check | Result | Detail |
|---|---|---|
| **PF-ENV-1** (LV5) DSH pin 0.1.1-rc.2 | **PASS** | `dsh_version=0.1.1-rc.2` |
| **PF-ENV-2** (G9) baseline workspace-write + ask | **PASS** (REPORT ONLY) | Baseline matches. Session policy NOT modified. |
| **PF-ENV-3** (LV4) env snapshot fields | **PASS** (report only) | No snapshot supplied → report-only pass. |
| **PF-ENV-4** evidence store writable | **PASS** | Project root writable; `audit/l3/` not created. |

### 2.4 Human-signed plan (PF-PLAN-1..5)

| Check | Result | Detail |
|---|---|---|
| **PF-PLAN-1** plan.json present | **PASS** | `L3-TEST-001/plan.json` exists. |
| **PF-PLAN-2** fields schema-valid | **PASS** | `expected_verdict=ALLOW`, required fields present. |
| **PF-PLAN-3** (LV7/IO-7) signoff precedes runtime | **PASS** | `signoff=2026-08-31T00:00:00Z`, no runtime captured yet. |
| **PF-PLAN-4** verdict + O4 oracle | **PASS** | `expected_verdict=ALLOW`, `O4` declared. |
| **PF-PLAN-5** (G7) signoff fields schema-valid | **PASS** | `validate_signed_plan` → VALID signed-plan. |

### 2.5 Reproducibility (PF-REP-1..4)

| Check | Result | Detail |
|---|---|---|
| **PF-REP-1** fixture hash (P4) | **PASS** | `sha256:52037567e3b6546b…` |
| **PF-REP-2** replay script present | **PASS** | `tests/l3_runner/replay.sh` |
| **PF-REP-3** verifier + schema sha256 | **PASS** | 11 schemas hashed; verifier sha256 recorded. |
| **PF-REP-4** no live-network dependency | **PASS** | Recorded response fixtures only (0003 §8.1). |

---

## 3. Environment readiness (L3ENV-*) results — observed this session

Run: `.venv-tests/bin/python -m tests.l3_runner.environment.readiness --scenario L3-TEST-001 --orchestrator-uid 1000 --json`

**`rehearsal_ready=True`** · **`l3_claim_possible=False`** · **`all_required_pass=True`** · **`all_l3_required_pass=False`**

### 3.1 UID/process (L3ENV-UID-1..3)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-UID-1** separate OS process capability | **PASS** | Runner spawns verifier via subprocess (distinct PID, IO-1). |
| **L3ENV-UID-2** separate UID capability | **FAIL (required_for_l3)** | Same-UID host: `orchestrator_uid=1000`, `verifier_probe_uid=1000`, `same_uid=True`. Blocked for L3. |
| **L3ENV-UID-3** not in orchestrator session tree | **PASS** | Never subagent tools (IO-4). |

### 3.2 Verifier (L3ENV-VER-1..5)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-VER-1** verifier executable + sha256 | **PASS** | Present, sha256 computable. |
| **L3ENV-VER-2** clean oracle imports | **PASS** | `assert_clean_imports()` CLEAN. |
| **L3ENV-VER-3** clean subprocess spawn | **PASS** | Subprocess spawn CLEAN. |
| **L3ENV-VER-4** reference oracle resolves (O1) | **PASS** | `authority_gate` resolves. |
| **L3ENV-VER-5** ≥ 2 oracle classes | **PASS** | Enforced per-scenario. |

### 3.3 Environment (L3ENV-ENV-1..3)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-ENV-1** DSH pin (LV5) | **PASS** | `dsh_version=0.1.1-rc.2` |
| **L3ENV-ENV-2** baseline (G9) | **PASS** (REPORT ONLY) | `workspace-write + ask`. Not modified. |
| **L3ENV-ENV-3** env snapshot fields (LV4) | **PASS** (report only) | No snapshot supplied. |

### 3.4 Human answerer + approval path (L3ENV-ANS-1..2)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-ANS-1** Human answerer availability (G3) | **FAIL (required_for_l3)** | No live answerer: prompts disabled, no answerer row composed. Ask → unavailable → DENY + escalate (fail-closed). |
| **L3ENV-ANS-2** approval path availability | **FAIL (required_for_l3)** | `ask` policy + no answerer → no interactive ALLOW path. |

### 3.5 D4/D7 mount (L3ENV-D4D7-1..3)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-D4D7-1** 7 role presets | **PASS** | All 7 present under `$DSH_HOME/.agent-presets/`. |
| **L3ENV-D4D7-2** 7 instance rows | **PASS** | All 7 present in `cordis.patch.yml`. |
| **L3ENV-D4D7-3** live bridge marker | **FAIL (required_for_l3)** | `DSH_LIVE_BRIDGE_ACTIVE` unset — live DSH unavailable. |

### 3.6 Human-signed plan (L3ENV-PLAN-1..5 + REAL)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-PLAN-1** plan.json present | **PASS** | Scenario L3-TEST-001. |
| **L3ENV-PLAN-2** fields schema-valid | **PASS** | `expected_verdict=ALLOW`. |
| **L3ENV-PLAN-3** signoff precedes runtime (LV7) | **PASS** | No runtime captured yet. |
| **L3ENV-PLAN-4** verdict + O4 oracle | **PASS** | `O4` declared. |
| **L3ENV-PLAN-5** signoff fields schema-valid (G7) | **PASS** | `validate_signed_plan` → VALID. |
| **L3ENV-PLAN-REAL** REAL Human signoff observed | **FAIL (required_for_l3)** | Fixture is inert; no real Human signoff. The probe does NOT invent signatures. |

### 3.7 Evidence store + replay (L3ENV-STORE-1, REP-1..4)

| Check | Result | Detail |
|---|---|---|
| **L3ENV-STORE-1** evidence store writable | **PASS** | Project root writable; `audit/l3/` not created by probe. |
| **L3ENV-REP-1** fixture hash (P4) | **PASS** | Deterministic `sha256:52037567…`. |
| **L3ENV-REP-2** replay script | **PASS** | Present. |
| **L3ENV-REP-3** tooling sha256 | **PASS** | Verifier + 11 schemas hashed. |
| **L3ENV-REP-4** no live network | **PASS** | Recorded fixtures only. |

---

## 4. Test suite results (all observed this session)

| Suite | Tests | Result |
|---|---|---|
| `tests/l3_runner/test_l3_preflight.py` | 31 | **31 passed** |
| `tests/l3_runner/environment/test_l3_environment_readiness.py` | 17 | **17 passed** |
| Full L3 (`tests/l3_runner/` + `tests/l3_reference/`) | 275 | **275 passed** |

All suites pass. No test failure observed. No test was modified.

---

## 5. Summary: rehearsal_ready, l3_claim_possible, and BLOCKED

| Property | Value |
|---|---|
| **`rehearsal_ready`** | **True** — all required checks pass; rehearsal machinery works. |
| **`l3_claim_possible`** | **False** — same-UID host, no answerer, no bridge, no real signoff. |

### BLOCKED — exact missing dependencies (5 items)

| Blocker | Missing dependency | Unblocks when |
|---|---|---|
| **L3ENV-UID-2** — separate UID capability | Verifier must run under a distinct UID/credential (setuid wrapper, separate user account, or separate host) | Operator/infrastructure provisions a separate-UID launch path |
| **L3ENV-ANS-1** — Human answerer (G3) | A live approval answerer composed for the session (approval prompts enabled; answerer row in `$DSH_HOME/profiles`) | Operator enables the answerer path (out of scope for the harness) |
| **L3ENV-ANS-2** — approval path (G3) | A live answerer for `ask` policy (or pre-recorded signed `approval-<id>` references) | Operator action |
| **L3ENV-D4D7-3** — live bridge (G2) | `DSH_LIVE_BRIDGE_ACTIVE=1` set per session (requires per-session mount verification; `docs/phase-5/environment/0001 §2`) | Per-session mount + marker verification |
| **L3ENV-PLAN-REAL** — REAL Human signoff (O4) | An actual Human-signed `plan.json` with durable identity, method, and timestamp, committed and signed before the run | Human signoff via the answerer/interactive path |

---

## 6. Exact operator/infrastructure actions still required

These actions are **outside the agent's scope** and must be performed by a Human operator or infrastructure provisioner:

1. **Provision separate-UID verifier launch path.** The verifier (or the preflight subprocess probe) must run under a distinct OS credential from the orchestrator. Options: **setuid wrapper** (launch verifier as a dedicated `l3-verifier` user), **separate user account** (run the verifier process under a different UID on the same host), or **separate host** (the verifier runs on a different machine with its own identity). Without this, IO-2 fails and no L3 claim is possible (`docs/security/0007 §1.2`).

2. **Enable the approval answerer path.** Enable approval prompts (`DSH_APPROVAL_PROMPTS_DISABLED=0`) and compose a live Human answerer row in the DSH profile (e.g., `ui-user-questions`, `user-approval`, or a custom `approval-answerer`). Without a live answerer, `ask` resolves `unavailable` → DENY + escalate (fail-closed), blocking interactive/HIGH-risk ALLOWs and L3 plan signing.

3. **Verify the D4/D7 mount per session and set the bridge marker.** Follow the per-session mount verification procedure (`docs/phase-5/environment/0001 §2`): verify presets → verify instance rows → set `DSH_LIVE_BRIDGE_ACTIVE=1` → resolve the backend → smoke test. Without this, `LiveDSHRuntimeDriver` refuses live dispatch (fail-closed `BridgeNotAvailable`).

4. **Obtain a real Human signoff for each L3 scenario plan.** A Human with a durable identity must review and sign the `plan.json` (via `interactive` or `signed-assertion` method) using the signing checklist in `tests/l3_runner/plan_signing.py`. The signed plan must be committed **before** the runtime run. The fixture `human-YYYY-MM-DD-NNN` template is inert; the probe does **not** invent signatures.

5. **Authorize the L3 execution.** Human acceptance of `docs/security/0003 §15` (L3 execution protocol), a confirmed G9 baseline (`workspace-write + ask`), and production control-plane code B1 are prerequisites before any live L3 run.

6. **G10 closure decision (if DSH-layer path isolation is required).** A Human decision on V2 path isolation: O5 (narrow bash surface), O3 (out-of-process registry), or O2 (registry relocation). Each requires an approved, reversible composition/process change. Until then, V1 containment = detection is the accepted residual.

7. **G13 resolution (if prompt-injection closure is claimed).** Authorized adversarial live test of DSH child behavior under injection payloads + documented DSH driver-internal content-isolation findings. No claim is possible without this.

---

## 7. Honesty statement

1. **No L3 claim.** `l3_claim_possible=False` — same-UID host, no answerer, no bridge, no real signoff.
2. **No live L3 run.** All execution paths are read-only probes; the rehearsal machinery is replay/inert.
3. **No policy change.** `L3ENV-ENV-2` reports the G9 baseline; nothing was changed to force a pass.
4. **No invented Human signature.** `L3ENV-PLAN-REAL` reports the fixture is inert; the probe cannot and does not fabricate a signoff.
5. **No fake credential separation.** IO-2 fails honestly; the probe never claims a separation it did not achieve.
6. **No session policy, DSH, DSH profile/preset, production code, or role mapping modified.**
7. **No test failure was downgraded or re-labelled.** All test counts are as observed by running the exact commands documented.

---

## 8. Scope check

**In scope (written this session):** `docs/phase-5/l3/environment/0002-session-a-preflight-verification-record.md` (this additive file, Session A verification record).

**Not modified (verified):** `tests/l3_runner/environment/` (probe + tests — unchanged from Session D); `tests/l3_runner/` (no file edited); `tests/l3_reference/` (no file edited); `control/`, `orchestrator/` (production); `state/`, `audit/` (no `audit/l3/` created); `config/`, `agents/`, `schemas/`; DSH core/profile/preset/session policy; role mapping. No L3 scenario executed. No session-policy change. No DSH change. No control claimed L3. No production deployment started.

---

*Status: VERIFICATION RECORD (Session A). Read-only preflight re-run confirms rehearsal_ready=True, l3_claim_possible=False, 5 exact blockers. No L3 run executed. No L3 claim made. No policy/DSH/profile/code modified.*
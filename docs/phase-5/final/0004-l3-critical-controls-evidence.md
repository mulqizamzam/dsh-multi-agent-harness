# L3 Critical-Controls Verification Evidence (VERIFY CRITICAL CONTROLS ONLY)

- **Gate**: Phase 5 — L3 gate (VERIFY CRITICAL CONTROLS ONLY: AUTHORITY, CONSEQUENTIAL EXECUTION, RECOVERY, STATE/AUDIT INTEGRITY)
- **Status**: EVIDENCE REPORT (independent oracles verified; infrastructure rehearsed; NO control claimed L3)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/final/0004-l3-critical-controls-evidence.md` (this file) — **only**.
- **Companion to**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/security/0006-l3-implementation-report.md` · `docs/security/0007-l3-run-prerequisites.md` · `docs/phase-5/l3/0001-l3-execution-readiness.md` · `docs/phase-5/final/0001-security-closure-matrix.md`.
- **Evidence discipline**: every number, verdict and path below was observed in this session by running the documented commands. No evidence is invented, extrapolated, or upgraded. **Zero controls are claimed L3.**

---

## 1. L3 definition recap and the honesty rule

**L3 = independently verified runtime enforcement.** Per `docs/security/0003` §1, a control is L3 only when **all four** properties hold simultaneously:

| # | Property | Meaning |
|---|---|---|
| **P1 — Runtime** | Control exercised against a **running** DSH `0.1.1-rc.2` session / real or emulated filesystem/state/audit — not static analysis, not a mocked harness. |
| **P2 — Independent observer** | Verifier is not the agent under test, not its orchestrator, not a process owned by the acting session tree; separate session, separate trust root. |
| **P3 — External oracle** | Expected outcome computed by a mechanism outside the control under test (reference re-implementation, schema, on-disk hash, Human-signed expectation). |
| **P4 — Independently reproducible** | A third party can rerun the same artifacts + seed + DSH pin + environment and observe the same PASS/FAIL. |

**Honesty rule (`0003` §1):** *a test that fails P1, P2, P3 or P4 is, at best, L1/L2 evidence; it is never upgraded to L3.*

**Honesty rule specific to this sandbox (`0007` §1.2, load-bearing):** the minimal viable L3 environment is two processes on the same host **under a separate UID/credential** (`0003` §4.1). In this sandbox the orchestrator and the verifier run under the **same host UID**, so the independence checklist's **IO-2 fails honestly**, `l3_claim_possible=False`, and the verifier/runner report it — the infrastructure **never fakes a credential separation it did not achieve** (`0006` §3). Consequently **no L3 claim is possible in this sandbox by design**, and no control may be claimed L3.

---

## 2. Critical-control → independent oracle → scenario mapping

| Critical control | Independent oracle file (O1, self-contained) | INT scenario | L3 scenario IDs that exercise it (`0005` §2) |
|---|---|---|---|
| **AUTHORITY** | `tests/l3_reference/authority_gate.py` | INT-01 | `L3-XG-001` (full checklist → ALLOW) · `L3-VER-002` (independent file-hash) · `L3-AUTH-001` (authority gate) |
| **CONSEQUENTIAL EXECUTION** | `tests/l3_reference/execution_gate.py` | INT-07 | `L3-AUTH-004` (approval race) · `L3-AUTH-006` (execution-time re-check) · `L3-XG-004` (revocation) · `L3-DLG-004` (stale delegation) |
| **RECOVERY** | `tests/l3_reference/recovery_gate.py` | INT-12 | `L3-REC-001` (no blind retry) · `L3-REC-005` (no new tools) · `L3-XG-009` (recovery privilege escalation) · `L3-VER-005` (Human signoff) |
| **STATE/AUDIT INTEGRITY** | `tests/l3_reference/transition_gate.py` (state) + `tests/l3_reference/audit_chain.py` (ledger) | INT-11 | `L3-XG-008` (parallel worker stale state) · `L3-ISO-009` (privileged tool absent) · `L3-ISO-010` (unknown toolName) |

Each oracle is a **self-contained reference re-implementation** that imports **nothing** from production — no `control.*`, no `orchestrator.foundation.*`, no `audit.helpers.*`, no `state.helpers.*` (verified by the verifier's `assert_clean_imports()` guard and by AST tests; `0006` §2). The scenario IDs are the future unit of L3 evidence; **no such run exists today** (`0005` §10: all four INTs remain L2-LIVE, promotable to L3 only after an independent run).

---

## 3. What is verified (observed this session)

This gate verified the **oracles for the four critical controls**, the **rehearsal machinery**, and the **honest no-claim** — not L3 claims.

### 3.1 AUTHORITY — `tests/l3_reference/authority_gate.py`
Observed oracle behaviour (14-item independent decision table, `authorize_reference`):
- **ALLOW** a valid in-scope delegation (ACTIVE, scoped to `write/read/code_write` on `agents/cto/**`, env `dev`, actor recognized, target in scope, no prohibition, no required approval).
- **DENY** the same delegation once it is in the **revocation list** (`delegation_not_revoked` fails → DENY).
- **DENY** model text / prose as authority (`AUTH-INV-01`: "model text / prose is never authority").

### 3.2 CONSEQUENTIAL EXECUTION — `tests/l3_reference/execution_gate.py`
Observed oracle behaviour (`authorize_write_reference`, path-aware):
- **DENY** a write to a protected path (`state/registry/**`; classification `PROTECTED`, ADR 0002), including by a generic `write` channel.
- **ALLOW** a normal workspace write to a non-protected path (classification `ALLOWED`).
- (Infrastructure also covers traversal / symlink / prefix-confusion / sanctioned-channel scope; `0006` §11.)

### 3.3 RECOVERY — `tests/l3_reference/recovery_gate.py`
Observed oracle behaviour:
- **DENY** a blind retry (no diagnosed cause; `AUTH-INV-16`).
- **DENY** an identical-cause retry (retry must have a **new** cause; `AUTH-INV-16`).
- **ALLOW** a new-cause retry within the attempt cap.
- **DENY** a privilege-escalating recovery attempt (action outside the original authority baseline; `REC-004` / `THREAT-017`).

### 3.4 STATE/AUDIT INTEGRITY — `tests/l3_reference/transition_gate.py` + `tests/l3_reference/audit_chain.py`
Observed oracle behaviour:
- `transition_gate.verify_transition`: **ALLOW** a legal transition (`REVIEW_PENDING → APPROVED`) with matching state version; **DENY** a skipped-gate transition (`REVIEW_PENDING → COMPLETE`, THREAT-007/021); **DENY** a stale-version CAS write (`version 1 != expected 2`, `STALE_OVERWRITE`).
- `audit_chain.verify_ledger`: on a persisted `.chain` sidecar baseline, an **untampered ledger → VALID**; a line-edit tamper → **INVALID** (cumulative-hash mismatch); an injected duplicate line → **INVALID** (chain-length mismatch). Without a persisted sidecar the oracle honestly reports **first-time verification** (chain computed, no tamper claim) — the no-baseline case makes no claim, by design (`audit_chain.py` docstring).

### 3.5 Infrastructure and readiness tests
- **Infrastructure** (`tests/l3_runner/test_l3_infrastructure.py`, 41): O1 oracles (authority allow/deny/revoke/expire/escalate; execution-gate protected/traversal/writer-scope; delegation; role; transition; recovery; verification), verifier independence guard (subprocess), no-production-import AST check, collector determinism, verifier flow + failure classes, independence checklist (incl. honest IO-2), runner end-to-end (distinct PID, live-mode refusal, single-oracle refusal), validator LV1/LV3/LV-INT-07, audit-chain mutation + strict read, replay determinism (`0006` §11).
- **UID readiness** (`tests/l3_runner/test_l3_uid_readiness.py`, 9) and **preflight** (`tests/l3_runner/test_l3_preflight.py`, 31): honest IO-2 detection (`l3_claim_possible=False`), verifier prerequisites, env/plan/replay preflight (PF-*). UID-readiness CLI confirms `l3_claim_possible=False`, `io2_pass=False`, `same_uid=True` on this host.
- **Rehearsal machinery** (`tests/l3_runner/rehearsal.py` + `test_l3_rehearsal.py`, 14): full runner → verifier subprocess → collector → validator → replay chain, producing a complete 13-file bundle under scratch with `l3_claim=false`; LV10 fails-by-design; no `audit/l3/` committed. This is the mechanism a future authorized L3 run would use — **not L3 evidence**.

---

## 4. Evidence log (exact commands and outputs)

### 4.1 Full L3 test suites
```bash
$ .venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
```
Observed (authoritative re-run after the concurrent Session-D environment suite settled): **148 passed** (148 collected), including the separate Phase-5 environment-readiness suite `tests/l3_runner/environment/test_l3_environment_readiness.py` (17 passed). A mid-authoring sample during this session briefly observed 3 failures in that suite (`test_rehearsal_ready_with_injected_env`, `test_cli_exit_code_reflects_rehearsal_readiness`, `test_no_invented_human_signature`) while the concurrent Session-D workstream was still writing it; the final, re-verified state is **17/17 passing** and the combined run is **148 passed**. No test was modified by this gate. Per-file counts (collect-only): infrastructure 41 · preflight 31 · plan_signing 21 · environment_readiness 17 · g5_verifier 15 · rehearsal 14 · uid_readiness 9 = 148.

### 4.2 Focused readiness suites
```bash
$ .venv-tests/bin/python -m pytest tests/l3_runner/test_l3_uid_readiness.py -q     # 9 passed
$ .venv-tests/bin/python -m pytest tests/l3_runner/test_l3_preflight.py -q         # 31 passed
```

### 4.3 UID readiness CLI
```bash
$ .venv-tests/bin/python -m tests.l3_runner.uid_readiness --orchestrator-uid "$(id -u)" --json
```
Observed: `l3_claim_possible = False` · `io2_pass = False` · `same_uid = True` · `orchestrator_uid = 1000`.

### 4.4 Critical-control oracle exercise (direct, `.venv-tests/bin/python - <<'EOF'`)
```
=== AUTHORITY oracle ===
valid in-scope delegation   -> ALLOW | all authority checks passed
revoked delegation          -> DENY  | authority checklist failed: delegation_not_revoked, no_partial_allow
model-text authority        -> DENY  | model text / prose is never authority (AUTH-INV-01)

=== EXECUTION GATE oracle ===
protected-path write        -> DENY | PROTECTED | target is a protected path (ADR 0002): 'state/registry/delegations.yaml'
normal workspace write      -> ALLOW| ALLOWED  | write to authorized workspace path

=== RECOVERY oracle ===
blind retry (no diagnosis)  -> DENY | no blind retry: recovery requires a diagnosed cause (AUTH-INV-16)
identical-cause retry       -> DENY | ... retry cause 'quota exceeded' identical to diagnosed cause — a retry needs a NEW cause (AUTH-INV-16)
new-cause retry             -> ALLOW| new diagnosed cause, retry within cap
privilege-escalating retry  -> DENY | recovery privilege escalation: action 'registry_write' not covered by original authority (REC-004 / THREAT-017)

=== AUDIT CHAIN oracle (persisted .chain sidecar baseline) ===
untampered ledger           -> VALID  | ledger integrity chain valid (3 events)
tampered ledger (line edit) -> INVALID| event line 2: cumulative_hash mismatch ... (tampered/truncated)
duplicated entry (inject)   -> INVALID| chain length mismatch: events 4 != side-car 3 (truncated or chain not updated)

=== STATE TRANSITION oracle ===
legal transition (matching v) -> ALLOW | legal transition 'REVIEW_PENDING' -> 'APPROVED' with authority
skipped-gate transition       -> DENY  | illegal state transition 'REVIEW_PENDING' -> 'COMPLETE' (skipped gate, THREAT-007/021)
stale-version CAS write       -> DENY  | stale version CAS: state version 1 != expected 2 (STALE_OVERWRITE)
```
Note: without a persisted `.chain` sidecar, `audit_chain.verify_ledger` reports `VALID` as **first-time verification** (no baseline → no tamper claim) for both intact and tampered ledgers — that is the oracle's documented no-baseline behaviour, not a false negative.

### 4.5 End-to-end rehearsal (L3-TEST-001, replay/inert mode)
```bash
$ .venv-tests/bin/python -m tests.l3_runner rehearsal \
    --scenario L3-TEST-001 --fixtures-root tests/l3_reference/fixtures \
    --orchestrator-pid 99999 --orchestrator-uid "$(id -u)"
```
Observed bundle result (scratch at `/tmp/l3-rehearsal-*/audit/l3/L3-TEST-001`; **not** the repo `audit/l3/`, which remains absent):
```json
{
  "rehearsal": true, "mode": "replay", "scenario_id": "L3-TEST-001",
  "l3_claim": false,
  "lv10_by_design": true,
  "validation_passed": false,
  "validation_errors": [
    "LV10: l3_claim must be true, got False",
    "LV12: independence check(s) failed: ['IO-2', 'IO-4']"
  ],
  "oracle_classes_used": ["O1", "O4"],
  "fixture_hash": "sha256:52037567e3b6546b0d858b48f7a8ea9894f0635b03625e5a8210d56ca9bd05ca",
  "replay_command": "python -m tests.l3_runner.runner --scenario L3-TEST-001 --mode replay",
  "io1_pass": true, "io2_pass": false, "io2_honest_fail_on_same_uid": true,
  "independence_all_pass": false,
  "verifier_pid": 5, "orchestrator_pid": 99999,
  "completed_at": "2026-08-31T07:04:40Z"
}
```
The rehearsal produces a complete 13-file evidence bundle with **`l3_claim=false`** and fails validation with **LV10** (`l3_claim must be true`) and **LV12** (independence IO-2 — same UID; IO-4 — session-tree provenance with the synthetic `orchestrator_pid=99999`) **BY DESIGN**. This is the honest no-claim path: a rehearsal bundle is **not** L3 evidence.

---

## 5. Honest no-claim statement

1. **Zero controls are L3 today.** AUTHORITY, CONSEQUENTIAL EXECUTION, RECOVERY and STATE/AUDIT INTEGRITY each have a verified independent O1 oracle and L1/L2 evidence, but no control satisfies P1..P4 simultaneously. This matches `0003` §10, `0005` §10, `0006` §9 and `0001-security-closure-matrix.md` §3 ("L3 … **ZERO controls**").
2. **No live L3 run has executed.** Every execution path used in this session is replay/inert (`RecordedRuntimeDriver`); `LiveDSHRuntimeDriver` remains a `NotImplementedError` stub and the runner refuses `--mode live` (`0006` §6, `l3/0001` §3.3).
3. **IO-2 fails on this same-UID sandbox**, so `l3_claim_possible=False` (preflight, UID readiness, and rehearsal all report it honestly). The verifier and orchestrator share the host UID; the infrastructure never fakes a credential separation (`0007` §1.2).
4. **Rehearsal bundles are not L3 evidence.** The L3-TEST-001 rehearsal bundle fails LV10 (`l3_claim must be true`) by design and LV12 (IO-2/IO-4), exactly as required — its `l3_claim=false` is the intended honesty rule.
5. **Prerequisites for a real L3 run are absent by design** (`l3/0001` §3, `0001` §6): separate UID/credential (IO-2), a REAL Human-signed `plan.json` with durable identity (O4 / G7 — the committed plan is an inert template; the environment probe honestly reports no real signoff), a live DSH session (P1 / G5), and an authorized run (`0003` §15).
6. **The Phase-5 environment-readiness suite** (`tests/l3_runner/environment/`, 17 tests) was being authored concurrently by a separate Session-D workstream; it passed in the final authoritative re-run (148 total). No test was modified by this gate.

**Bottom line: this report verifies the independent oracles for the four critical controls, the rehearsal machinery, and the honest no-claim. It claims nothing L3.**

---

## 6. Scope check

**In scope (written this session):** `docs/phase-5/final/0004-l3-critical-controls-evidence.md` (this file) — **only**.

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/` (no `audit/l3/` created; rehearsal bundles went to `/tmp` scratch), `config/`, `agents/`, `schemas/`, `tests/` (no test file edited; the 3 environment-suite failures were left untouched), DSH core/profile/preset/session policy, and every `docs/` file outside this output. No L3 scenario executed. No session-policy change. No control claimed L3. The only file written is the deliverable at `docs/phase-5/final/0004-l3-critical-controls-evidence.md`.

---

*Status: EVIDENCE REPORT. Independent oracles verified; infrastructure rehearsed; NO control claimed L3. Same-UID sandbox makes an L3 claim impossible here; IO-2 fails honestly; rehearsal bundles fail LV10 by design.*

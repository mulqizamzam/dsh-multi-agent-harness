# Phase 5 / Session D — L3 Environment + Human-Answerer Readiness

- **Milestone**: PHASE 5 / SESSION D — L3 ENVIRONMENT + HUMAN-ANSWERER READINESS
- **Status**: **READY-TO-REHEARSE / NOT-READY-TO-CLAIM** (environment prepared and probed read-only; **no L3 run, no L3 claim, no policy/DSH/profile change**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/l3_runner/environment/` · `multi-agent-harness/docs/phase-5/l3/environment/` (write-only per the session brief). **No session policy, DSH, DSH profile/preset, production code, or role mapping modified.**
- **Companion**: `docs/security/0007-l3-run-prerequisites.md` (PF-*) · `docs/security/0003-l3-independent-verification-plan.md` (P1–P4, IO-1..10, O1..O4) · `docs/phase-5/l3/0001-l3-execution-readiness.md` (G6/G7/G8) · `docs/phase-5/l3/0002-g5-verifier-implementation-report.md` (G5) · `docs/phase-5/environment/0001-environment-readiness-spec.md` (G2/G3) · `docs/phase-1/0003..0005` (D4/D7 composition records) · `tests/l3_runner/preflight.py` · `tests/l3_runner/environment/readiness.py` (new probe).

> This session **prepares the environment required for a legitimate L3 run**: it
> records, read-only, what prerequisite holds and what is absent, and it reports
> **BLOCKED with the exact missing dependency** for every absent prerequisite. It
> does **not** change policy to make the preflight pass and it does **not** invent
> Human signatures.

---

## 1. What this session did

Built a **read-only environment + Human-answerer readiness probe**
(`tests/l3_runner/environment/readiness.py`, checks `L3ENV-*`) that:

1. Verifies the `PF-UID-1/2/3`, `PF-VER-1..5`, `PF-ENV-1..4`, `PF-PLAN-1..5`,
   `PF-REP-1..4` run-prerequisites (reusing `preflight.py` semantics) against
   the **current** host/session.
2. Determines the ten Session-D capabilities explicitly (separate process,
   separate UID, verifier executable, clean oracle imports, Human answerer,
   approval path, D4/D7 mount persistence, signed-plan mechanism, evidence
   store, replay).
3. Reports `l3_claim_possible` honestly and a `BLOCKED` list naming each exact
   missing dependency. It never fakes separation, never invents a signature,
   never changes policy.

The probe is covered by `test_l3_environment_readiness.py` (17 tests) which
assert the honesty invariants (read-only, no invented signature, same-UID
demotion, absent answerer → BLOCKED).

---

## 2. Verified runtime facts (this session, 2026-08-31)

| Fact | Current value | Determination |
|---|---|---|
| Host UID / process | `uid=1000 (administrator)`; orchestrator and subprocess verifier probe both `1000` | **Same-UID host** → IO-2 fails honestly |
| DSH version pin | `0.1.1-rc.2` (verified from DSH package.json) | Pin holds (PF-ENV-1 / LV5) |
| File sandbox policy | `workspace-write` | Baseline holds (PF-ENV-2 / G9, REPORT ONLY) |
| Approval policy | `ask` | Baseline holds (PF-ENV-2 / G9, REPORT ONLY) |
| Approval answerer | **Prompts disabled / no answerer row composed** (verified: DSH user-approval README — "no built-in answerer"; `$DSH_HOME/profiles` contains no `user-approval`/`ui-user-questions`/`approval/request` row) | **Absent** → ask resolves `unavailable` (DENY + escalate, fail-closed) |
| D4/D7 presets | All 7 role presets present under `$DSH_HOME/.agent-presets/` (`role-zeko…role-nova`) | Files **persistent** (G2 step 1) |
| D4/D7 instance rows | All 7 `tool-subagent-<id>` rows present in `$DSH_HOME/profiles/web/cordis.patch.yml` | Files **persistent** (G2 step 2) |
| Live bridge marker | `DSH_LIVE_BRIDGE_ACTIVE` **unset** | Live DSH **unavailable** (G2 step 3; fail-closed `BridgeNotAvailable`) |
| Verifier executable | `tests/l3_runner/verifier.py` present; sha256 computable | Available (PF-VER-1/3 / IO-3) |
| Clean oracle imports | `assert_clean_imports()` passes in a fresh subprocess (`CLEAN`) | Clean (PF-VER-2/4; no `control.*`/`orchestrator.foundation.*`/`audit.helpers`/`state.helpers`) |
| Reference oracles | 8 `tests/l3_reference/*.py` oracles exist, stdlib-only, no production imports | Available (PF-VER-2 / O1) |
| Evidence store | `audit/l3/` base not yet created; project root writable | Creatable/writable (PF-ENV-4 / G4) |
| Replay | `tests/l3_runner/replay.sh` present; fixture hash deterministic (`sha256:…`) | Replay ready (PF-REP-1..4 / P4) |
| Signed plan mechanism | `plan_signing.py` + `PF-PLAN-5`; `L3-TEST-001/plan.json` schema-valid (signoff id `human-2026-08-31-001`, ts pre-runtime, method `interactive`) | **Mechanism ready**; **no REAL Human signoff observed** (fixture is inert — never invented) |

---

## 3. Preflight verification (PF-* → L3ENV-*)

| PF-* (0007) | L3ENV-* (probe) | Result (this session) |
|---|---|---|
| PF-UID-1 | L3ENV-UID-1 | PASS — separate process capability (subprocess spawn) |
| PF-UID-2 | L3ENV-UID-2 | **FAIL (L3-only)** — same-UID host, IO-2 fails honestly |
| PF-UID-3 | L3ENV-UID-3 | PASS — never spawned via orchestrator session tree |
| PF-VER-1/3 | L3ENV-VER-1 | PASS — verifier executable + sha256 |
| PF-VER-1/4 | L3ENV-VER-2/3 | PASS — clean oracle imports, clean subprocess spawn |
| PF-VER-2 | L3ENV-VER-4 | PASS — reference oracle resolves (O1) |
| PF-VER-5 | L3ENV-VER-5 | PASS — ≥ 2 oracle classes (R6 / IO-6) |
| PF-ENV-1 | L3ENV-ENV-1 | PASS — DSH 0.1.1-rc.2 (LV5) |
| PF-ENV-2 | L3ENV-ENV-2 | PASS (report only) — workspace-write + ask (G9) |
| PF-ENV-3 | L3ENV-ENV-3 | PASS (report only) — env snapshot fields (LV4) |
| PF-ENV-4 | L3ENV-STORE-1 | PASS (advisory) — evidence store creatable/writable |
| PF-PLAN-1 | L3ENV-PLAN-1 | PASS — plan.json present |
| PF-PLAN-2 | L3ENV-PLAN-2 | PASS — plan fields schema-valid |
| PF-PLAN-3 | L3ENV-PLAN-3 | PASS — signoff precedes runtime (LV7/IO-7) |
| PF-PLAN-4 | L3ENV-PLAN-4 | PASS — expected verdict + O4 |
| PF-PLAN-5 | L3ENV-PLAN-5 | PASS — signoff fields schema-valid (G7) |
| — (honesty) | L3ENV-PLAN-REAL | **FAIL (L3-only)** — no REAL Human signoff (never invented) |
| PF-REP-1 | L3ENV-REP-1 | PASS — fixture hash deterministic |
| PF-REP-2 | L3ENV-REP-2 | PASS — replay script present |
| PF-REP-3 | L3ENV-REP-3 | PASS — verifier + schema sha256 recorded |
| PF-REP-4 | L3ENV-REP-4 | PASS — no live-network dependency |

**Summary**: `rehearsal_ready=True` (all PF-* required checks pass) ·
`l3_claim_possible=False`.

---

## 4. The ten Session-D determinations

| # | Determination | Result | Evidence |
|---|---|---|---|
| 1 | **Separate process capability** | **PRESENT** | L3ENV-UID-1/3; runner spawns verifier via `subprocess` (distinct PID, IO-1), never DSH subagent tools (IO-4); PF-VER-3/4 clean subprocess |
| 2 | **Separate UID capability** | **ABSENT** | L3ENV-UID-2; same-UID host (`uid=1000` both sides); IO-2 fails honestly → demote, never fake (0007 §1.2) |
| 3 | **Verifier executable availability** | **PRESENT** | L3ENV-VER-1/3; `verifier.py` exists, sha256 computable, spawns `CLEAN` |
| 4 | **Clean oracle imports** | **PRESENT** | L3ENV-VER-2; `assert_clean_imports()` passes; 8 stdlib-only reference oracles with no production imports |
| 5 | **Human answerer availability** | **ABSENT** | L3ENV-ANS-1; approval prompts disabled / no `user-approval`/`ui-user-questions`/`approval/request` row composed; DSH "no built-in answerer" (verified) |
| 6 | **Approval path availability** | **ABSENT** | L3ENV-ANS-2; policy is `ask` but no live answerer → `unavailable` → DENY + escalate (fail-closed) |
| 7 | **D4/D7 mount persistence** | **PARTIAL (files persistent, bridge inactive)** | L3ENV-D4D7-1/2 PASS (presets + instance rows on disk), L3ENV-D4D7-3 FAIL (`DSH_LIVE_BRIDGE_ACTIVE` unset) → live dispatch unavailable, must be re-verified per session |
| 8 | **Signed-plan mechanism** | **MECHANISM READY / REAL SIGNOFF ABSENT** | L3ENV-PLAN-1..5 PASS; L3ENV-PLAN-REAL FAIL — the committed plan is a fixture (inert `human-YYYY-MM-DD-NNN`), no Human record; the probe never invents a signature |
| 9 | **Evidence-store readiness** | **READY (writable, not yet created)** | L3ENV-STORE-1; `audit/l3/` creatable/writable; rehearsal bundles go to scratch |
| 10 | **Replay readiness** | **READY** | L3ENV-REP-1..4; deterministic fixture hash, `replay.sh`, tooling sha256, recorded fixtures only |

---

## 5. BLOCKED — exact missing dependencies

A legitimate L3 run is **BLOCKED** by each of the following (the probe lists
these verbatim; nothing was changed to force a pass):

1. **Separate UID (IO-2) — `L3ENV-UID-2`.** The host runs orchestrator and
   verifier under the same UID (`1000`). A real L3 claim requires launching the
   verifier under a distinct credential via a **setuid wrapper**, a **separate
   user account**, or a **separate host** (`docs/security/0007` §1.2).
2. **Human answerer (G3) — `L3ENV-ANS-1`.** No live approval answerer is
   composed (prompts disabled; no `user-approval`/`ui-user-questions`/
   `approval/request` row; DSH has no built-in answerer). Restoring the answerer
   path is an **operator/Human action**, not an agent action.
3. **Approval path (G3) — `L3ENV-ANS-2`.** With `ask` policy and no answerer,
   approval resolves `unavailable` → DENY + escalate (fail-closed). Interactive
   and HIGH-risk ALLOWs are blocked until an answerer (or a pre-recorded
   `approval-<id>`) exists.
4. **D4/D7 live bridge (G2) — `L3ENV-D4D7-3`.** `DSH_LIVE_BRIDGE_ACTIVE=1` is
   **unset**. The composition files are persistent (presets + instance rows),
   but live DSH dispatch is unavailable and must be re-verified per session
   (`docs/phase-5/environment/0001` §2 fail-closed rule).
5. **Real Human signoff (O4 / G7) — `L3ENV-PLAN-REAL`.** No actual Human has
   signed any scenario plan. The committed `plan.json` is an inert fixture;
   `human_signoff_id=human-YYYY-MM-DD-NNN` is a template value, not a record.
   The probe does **not** invent Human signatures — a real L3 claim requires an
   actual Human signoff (identity + method + timestamp) before the run.

Additionally (not probe-blocking but load-bearing): a **live DSH session** is
required (P1) — `LiveDSHRuntimeDriver` remains a refuse-to-simulate stub, and an
**authorized run** (Human acceptance of `docs/security/0003` §15, re-baseline to
`workspace-write + ask`, production control-plane code B1) is required before any
claim. None hold in this sandbox; none were attempted.

---

## 6. Honesty statement

1. **No L3 claim.** `l3_claim_possible=False` on this same-UID host.
2. **No live L3 run.** The probe and the rehearsal machinery are replay/inert.
3. **No invented Human signature.** `L3ENV-PLAN-REAL` reports the fixture is
   inert; the probe cannot and does not fabricate a signoff.
4. **No policy change.** `L3ENV-ENV-2` reports the G9 baseline; it never
   re-baselines. Nothing was changed to make the preflight pass.
5. **No fake separation.** IO-2 fails honestly; the probe never claims a
   credential separation it did not achieve.
6. **BLOCKED, not guessed.** Every absent prerequisite is reported with its
   exact missing dependency.

---

## 7. How to run the readiness probe (read-only)

```bash
# Full L3 suite (infrastructure + preflight + environment readiness)
.venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q

# Environment + answerer readiness (human-readable)
.venv-tests/bin/python -m tests.l3_runner.environment.readiness \
    --scenario L3-TEST-001 --orchestrator-uid "$(id -u)"

# JSON report (for tooling/audit)
.venv-tests/bin/python -m tests.l3_runner.environment.readiness \
    --scenario L3-TEST-001 --orchestrator-uid "$(id -u)" --json

# Probe test suite (17 honesty tests)
.venv-tests/bin/python -m pytest \
    tests/l3_runner/environment/test_l3_environment_readiness.py -q
```

Exit code: `0` when rehearsal machinery is ready (even though
`l3_claim_possible=False`); `2` when a required check fails.

---

## 8. Scope check

**In scope (written this session):**
- `tests/l3_runner/environment/__init__.py` (layout + constants)
- `tests/l3_runner/environment/readiness.py` (new read-only probe, `L3ENV-*`)
- `tests/l3_runner/environment/__main__.py` (package CLI entry)
- `tests/l3_runner/environment/test_l3_environment_readiness.py` (17 tests)
- `docs/phase-5/l3/environment/README.md` + `0001-l3-environment-human-answerer-readiness.md`

**Not modified (verified):** session policy; DSH core; DSH profile/presets;
`$DSH_HOME`; production code (`control/*`, `orchestrator/*`, `state/helpers/*`,
`audit/helpers/*`, `agents/*`, `config/*`, `schemas/*`); role mapping;
`tests/l3_reference/*`; any existing test outside the two write-only dirs; no
`audit/l3/` bundle was created. No L3 scenario executed; no session-policy
change; no DSH change; no control claimed L3.

---

*Status: READY-TO-REHEARSE / NOT-READY-TO-CLAIM. Environment prepared and
probed read-only. No L3 run executed. No L3 claim made. No policy, DSH,
profile/preset, production code, or role mapping modified.*

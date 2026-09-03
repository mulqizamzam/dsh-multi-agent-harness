# L3 Execution Readiness — Phase 5 / Session F (G6 + G7 + G8)

- **Status**: readiness spec (gap-closure for L3 *execution readiness*; **no L3 execution, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Companion to**: `docs/security/0006-l3-implementation-report.md` · `docs/security/0007-l3-run-prerequisites.md` · `docs/design/0002-l3-verification-specification.md` · `docs/testing/0003-l3-evidence-validation-specification.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/phase-4/0005-production-readiness-assessment.md` (G5–G8, §1.6, §5.1, §5.4, §7.2)
- **Scope**: `docs/phase-5/l3/` · `tests/l3_runner/` (additive + the strictly-necessary extension of `preflight.py`, `validator.py`, `verifier.py`, `__init__.py`, `__main__.py`) · `tests/l3_reference/fixtures/shared/signing-request.template.json` (additive). **No production control-plane code, no DSH core/profile/preset/session-policy change. No L3 run executed. No control claimed L3.**
- **Class**: L3 EXECUTION READINESS

> This specification records what the Phase-5 / Session F gap-closure wave made
> **ready** for a future authorized L3 run, and what **remains** before any L3
> claim can be made. It is the honest bridge between the Phase-4
> infrastructure (mechanism) and a future real L3 run (authority + environment).

---

## 1. What was closed in this session

Three of the four "gaps that block L3 / independent verification"
(`docs/phase-4/0005` §7.2) were closed as **readiness**: G6 (separate-UID),
G7 (Human-signed plan), G8 (evidence-bundle execution path). G5 (the live
driver) stays a stub by design — a live driver is *not* a readiness artifact,
it is a future execution dependency.

### 1.1 G6 — separate-process / separate-UID readiness (CLOSED as readiness)

- **New** `tests/l3_runner/uid_readiness.py`: honestly detects the host UID
  situation (orchestrator UID vs an actual subprocess probe), reports the
  IO-2 status, and keeps `l3_claim_possible=False` whenever IO-2 cannot be
  achieved. It **never fakes** a credential separation (`docs/security/0007`
  §1.2 honesty rule).
- Documents the separate-UID launch options a real L3 run requires:
  **setuid wrapper**, **separate user account**, **separate host**.
- The preflight `PF-UID-1..3` already probed process/UID separation; the new
  module adds the documented launch-requirement contract and its tests
  (`test_l3_uid_readiness.py`, 9 tests).
- **In this same-UID sandbox** the probe returns the orchestrator UID, so
  `IO-2 pass=False` and `l3_claim_possible=False` — reported honestly, never
  papered over.

### 1.2 G7 — signed-plan prerequisites (CLOSED as readiness)

- **New** `tests/l3_runner/plan_signing.py`: schema validation of the Human
  signoff fields (`human_signoff_id` pattern `human-YYYY-MM-DD-NNN`,
  `human_signoff_ts` UTC parse, `human_signoff_method` enum
  `interactive | signed-assertion`), the **pre-runtime ordering** check
  (signoff strictly `<` runtime verdict; LV7 / IO-7), the Human **signing
  checklist** (identity, method, ordering, commit, declaration), and a
  **signing-request template** — how the Human signs, what identity is
  recorded, and how the plan is committed before the run. When `jsonschema`
  is available the full `l3-plan.schema.json` is applied as an O2-style
  structure oracle.
- Additive preflight check **`PF-PLAN-5`** reuses `validate_signed_plan()`
  inside `preflight.py::_check_plan`; the existing `PF-PLAN-1..4` semantics
  are unchanged.
- **New** additive fixture
  `tests/l3_reference/fixtures/shared/signing-request.template.json` — the
  inert template the Human fills + signs before any L3 run.
- Tests: `test_l3_plan_signing.py` (21 tests).

### 1.3 G8 — evidence-bundle execution path (CLOSED as readiness)

- **New** `tests/l3_runner/rehearsal.py`: drives the FULL L3 scenario in
  replay/inert mode end-to-end — runner (R1..R8) → verifier subprocess
  (P2/P3) → collector (E1..E13) → validator (LV1..LV22) → replay (E11) —
  producing a complete bundle under a **scratch** location with
  `l3_claim=false`. It uses only the `RecordedRuntimeDriver`, refuses live
  mode by construction, and never writes the repo `audit/l3/`.
- The rehearsal is provably **not** an L3 bundle: it fails **LV10** by design
  (`l3_claim must be true`), exactly as `docs/testing/0003` §3.1 requires for
  a real L3 bundle.
- Oracle execution is exercised in the rehearsal: the O1 reference gates run
  (≥ 2 oracle classes enforced by R6 / IO-6; `reference-verdict.json` is
  computed by the verifier process before the runtime verdict is read).
- Replay is exercised: fixture-hash determinism and the recorded replay
  command are asserted (`replay.json` E11 + `verdict-match.json`).
- Tests: `test_l3_rehearsal.py` (14 tests), including a `rehearsal`
  subcommand on `python -m tests.l3_runner`.

### 1.4 Verifier independence hardening (part of G8 / requirement 5)

- `verifier.py` now **refuses to trust** a pre-existing (orchestrator-written
  or stale) `verifier-independence.json`: it removes the file before
  computing the checklist from its own process state, so no forged content
  survives into the bundle (`docs/security/0005` §3.3 rule 3).
- `validator.py` adds **LV21** (rejects a `verifier-independence.json` whose
  `verifier_pid == orchestrator_pid` — a same-process verifier) and **LV22**
  (rejects a file whose `verifier_session_id` lacks the verifier-process
  marker `verifier-<pid>` — orchestrator-written independence).
- Tests prove a same-PID record is rejected, an orchestrator-written record
  is rejected, and the verifier overwrites any pre-existing forgery with its
  own honest computation (IO-2 fails honestly on the same-UID host).

---

## 2. What is now ready

| Readiness item | Where | Proven by |
|---|---|---|
| Rehearsal path (runner → verifier subprocess → collector → validator → replay) | `tests/l3_runner/rehearsal.py` | `test_l3_rehearsal.py` E2E tests |
| Complete 13-file evidence bundle (E1..E13) under scratch with `l3_claim=false` | `runner.py` + `collector.py` + `rehearsal.py` | E2E bundle assertions |
| LV10 failure-by-design for rehearsal bundles | `validator.py` (LV10) | `lv10_by_design=True` |
| ≥ 2 oracle classes enforced (R6 / IO-6) | `runner.py::_require_two_oracles` | oracle-class assertions |
| O1 oracle execution + `reference-verdict.json` before runtime verdict | `verifier.py` | reference-verdict assertions |
| Replay metadata (fixture hash deterministic, replay command recorded) | `replay.py` | determinism + replay-command tests |
| IO-1..IO-10 computed by the verifier process and recorded | `verifier.py` + `independence.py` | `test_rehearsal_io_checks_recorded_by_verifier` |
| Same-PID / orchestrator-written `verifier-independence.json` rejected | `validator.py` (LV21/LV22) + `verifier.py` guard | LV21/LV22 + overwrite tests |
| Honest UID detection + separate-UID launch requirements | `uid_readiness.py` | `test_l3_uid_readiness.py` |
| Human signoff schema validation + pre-runtime ordering + signing checklist/template | `plan_signing.py` + preflight `PF-PLAN-5` | `test_l3_plan_signing.py` |
| Read-only preflight covering UID/verifier/env/plan/repro | `preflight.py` (`PF-*`) | `test_l3_preflight.py` |

---

## 3. What remains for a REAL L3 run (NOT done, by design)

A real L3 claim requires all of the following. **None of them hold in this
sandbox; none were attempted.**

1. **Separate UID / credential (IO-2).** The verifier must run under a
   distinct UID via a setuid wrapper, a separate user account, or a separate
   host (`docs/security/0007` §1.2). This sandbox runs orchestrator and
   verifier under the same host UID, so IO-2 fails honestly and no claim is
   possible here.
2. **Human-signed plans with a real identity (O4).** A durable Human identity
   signs each scenario's `plan.json` before the run (signing checklist in
   `plan_signing.py`). This requires the approval answerer path (G3) and an
   actual Human; the fixtures are inert templates, not signed evidence.
3. **Live DSH session (P1).** `LiveDSHRuntimeDriver` remains a
   `NotImplementedError` stub and `runner.py` still refuses `--mode live`.
   The live driver is G5 — a future execution dependency, not readiness.
4. **Authorized run.** Human acceptance of `docs/security/0003` §15, a
   re-baseline to `workspace-write + ask` (G9), and Phase-1 production
   control-plane code (B1) are prerequisites.

Until all four hold, the infrastructure can only rehearse.

---

## 4. Explicit NO-L3-CLAIM statement

- **No control is L3.** Zero controls are claimed L3 today
  (`docs/security/0006` §9).
- **No live L3 run has executed.** Every execution path used in this session
  is replay/inert (`RecordedRuntimeDriver`), producing rehearsal bundles with
  `l3_claim=false` under scratch.
- **No rehearsal bundle is L3 evidence.** A rehearsal bundle fails LV10 by
  design and is invalid as L3 evidence — that is the intended honesty rule.
- **The same-UID sandbox prevents any claim.** IO-2 fails honestly;
  `l3_claim_possible=False` is reported by the preflight and the UID
  readiness module.

---

## 5. How to run the readiness checks (read-only)

```bash
# Full L3 test suites (116 tests: infrastructure, preflight, readiness, rehearsal)
.venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q

# Preflight (explicit)
.venv-tests/bin/python -m pytest tests/l3_runner/test_l3_preflight.py -q

# UID readiness (JSON)
.venv-tests/bin/python -m tests.l3_runner.uid_readiness --orchestrator-uid "$(id -u)" --json

# End-to-end rehearsal (bundle under scratch, l3_claim=false, LV10 by design)
.venv-tests/bin/python -m tests.l3_runner rehearsal --scenario L3-TEST-001 \
    --fixtures-root tests/l3_reference/fixtures \
    --orchestrator-pid 99999 --orchestrator-uid "$(id -u)"

# Human signing checklist
.venv-tests/bin/python -m tests.l3_runner.plan_signing --checklist
```

---

## 6. Scope check

**In scope (written this session):**
- `tests/l3_runner/` — additive modules (`uid_readiness.py`,
  `plan_signing.py`, `rehearsal.py`) + test suites (`test_l3_uid_readiness.py`,
  `test_l3_plan_signing.py`, `test_l3_rehearsal.py`); strictly-necessary
  extensions to `preflight.py` (additive PF-PLAN-5), `validator.py` (LV21/
  LV22), `verifier.py` (independence-file guard), `__init__.py`,
  `__main__.py` (layout + `rehearsal` subcommand).
- `tests/l3_reference/fixtures/shared/signing-request.template.json`
  (additive; existing oracles/schemas/fixtures untouched).
- `docs/phase-5/l3/` (this file + README).

**Not modified (verified):** `control/`, `orchestrator/` (production),
`state/`, `audit/`, `config/`, `agents/`, `schemas/`, any `docs/` outside
`docs/phase-5/l3/`, DSH core/profile/preset/session policy. The existing
infrastructure test files were not altered (the 41 infrastructure tests still
pass unchanged). No L3 scenario executed; no session-policy change; no DSH
change; no control claimed L3.

---

*Status: readiness spec. No L3 run executed. No L3 claim made. No production
control-plane code or DSH core/profile/preset/session policy modified.*

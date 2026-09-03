# L3 Independent Verification Infrastructure — Phase 4 / Session B Implementation Report

- **Status**: implemented (infrastructure + tests only; **no L3 run executed, no L3 claim made**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Companion to**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/testing/0003-l3-evidence-validation-specification.md`
- **Scope**: `multi-agent-harness/tests/l3_reference/` · `multi-agent-harness/tests/l3_runner/` · `multi-agent-harness/docs/security/` — **only**.
- **Hard-stop honoured**: no production control code modified, no DSH core/profile/preset/session policy touched, no destructive/high-impact L3 scenario run, no existing control claimed L3.

---

## 1. What was built

The independent L3 verification infrastructure requested by the Phase 4 / Session B task:

| Deliverable | Location | Notes |
|---|---|---|
| Independent reference/oracle implementations (O1) | `tests/l3_reference/{authority,execution_gate,delegation,role,recovery,verification,transition,audit_chain}_gate.py` | Self-contained, no production imports |
| Verifier process (P2 independent observer + P3 oracle) | `tests/l3_runner/verifier.py` | Standalone subprocess; computes verdict BEFORE reading runtime |
| Evidence bundle collector (E1..E13) | `tests/l3_runner/collector.py` | `before/after.sha256`, env, provenance, manifest |
| Runner (P1 runtime check + P4 replay) | `tests/l3_runner/runner.py` + `tests/l3_runner/__main__.py` + `tests/l3_runner/replay.sh` | R1..R8 runner contract; safe recorded runtime driver |
| Verdict matching + failure classification | `tests/l3_runner/verifier.py` | `classify_failure()` → L3-PASS / L3-FAIL-* / L3-INDEPENDENCE-VIOLATION / ... |
| Independence checklist (IO-1..IO-10) | `tests/l3_runner/independence.py` | Per `docs/design/0002` §14 |
| Replay / reproducibility metadata (P4) | `tests/l3_runner/replay.py` | fixture hash, binary sha256, schema sha256 |
| Evidence bundle structure validator (LV1..LV20 + per-INT) | `tests/l3_runner/validator.py` | Structure-only (O2); never executes a gate |
| Safe runtime driver (recorded + live stub) | `tests/l3_runner/runtime_driver.py` | Replay mode only; `LiveDSHRuntimeDriver` is a `NotImplementedError` stub |
| Synthetic scenario fixtures (ALLOW + DENY) | `tests/l3_reference/fixtures/L3-TEST-{001,002}/` | For infrastructure tests only |
| Infrastructure test suite | `tests/l3_runner/test_l3_infrastructure.py` | 41 tests, all passing |
| L3 reference/fixture documentation | `tests/l3_reference/README.md`, `tests/l3_reference/fixtures/README.md` | |

## 2. How the hard requirements are enforced (code, not prompts)

The task required the verifier to **not** import the production gate under test,
**not** run as a DSH subagent, **not** read the orchestrator session log, **not**
share the orchestrator process, and **not** receive authority from the
orchestrator. Each is enforced in code:

| Requirement | Enforcement |
|---|---|
| Must not import production gate | `verifier.assert_clean_imports()` scans `sys.modules` and raises on any `control.*`, `orchestrator.foundation.*`, `audit.helpers.*`, `state.helpers.*` import. Test `test_verifier_never_imports_production_gates` AST-scans the reference files to prove no production imports. |
| Must not run as a DSH subagent | The verifier is spawned via `subprocess.run([sys.executable, "-m", "tests.l3_runner.verifier", ...])` in `runner.run_scenario()`. It is a standalone OS process, never a subagent tool. |
| Must not read the orchestrator session log | The verifier reads **only** the on-disk bundle directory (`plan.json`, `runtime-verdict.json`, `before/after.sha256`, `audit-log.jsonl`) and the captured fixture JSON. It has no DSH tool access. |
| Must not share the orchestrator process | `verifier_pid` is `os.getpid()` of the subprocess; the runner records a distinct `orchestrator_pid`. IO-1 fails if they match. `test_runner_verifier_process_pid_differs` asserts the PIDs differ. |
| Must not receive authority from the orchestrator | The verdict is computed from `tests/l3_reference/*` oracles + the Human-signed plan, and is computed **before** reading `runtime-verdict.json` (no post-hoc rationalisation). The runtime's own verdict is never an input to the oracle. |

## 3. Independence checklist (IO-1..IO-10)

Implemented in `tests/l3_runner/independence.py::compute_independence()` and
recorded in each bundle's `verifier-independence.json`. Any failed check
demotes the bundle to L2 (never silently upgraded).

**Honesty note (IO-2):** a real L3 claim requires the verifier to run under a
**separate UID/credential** from the orchestrator. This sandbox runs both as
the same host UID, so `compute_independence()` reports IO-2 **false** and the
runner's rehearsal mode therefore sets `l3_claim=false`. The infrastructure
never fakes a credential separation it did not achieve. See
`docs/security/0003` §4.1 ("two processes on the same host ... under a
separate UID/credential").

## 4. Evidence bundle contract (E1..E13)

`collector.py` + `runner.py` produce the full bundle at `audit/l3/<scenario-id>/`
(machine-readable form per `docs/design/0002` §12 and `docs/security/0005` §3):

```
manifest.json              E1  (written LAST, certifies every other file)
env.json                   E2
plan.json                  E3  (Human-signed, schema-pure; pre-runtime)
before.sha256 / after.sha256 E4/E5
runtime-verdict.json       E6
audit-log.jsonl            E7
reference-verdict.json     E8  (computed BEFORE runtime verdict is read)
oracle-classes.json        E9  (>= 2 classes required — R6)
provenance.json            E10
replay.json                E11
verifier-independence.json E12
verdict-match.json         E13 (excluded from the audit chain it certifies — IO-10)
```

## 5. Oracle classes (P3 — at least two per scenario)

- **O1 — Reference re-implementation**: the eight `tests/l3_reference/*.py`
  oracles.
- **O2 — Schema-as-oracle**: `tests/l3_reference/schemas/*.json` validated by a
  third-party `jsonschema` invocation (`validator.py`).
- **O3 — On-disk-state-as-oracle**: `before.sha256` vs `after.sha256` hash trees
  (denied attempts must leave state unchanged).
- **O4 — Human-signed expectation**: the `plan.json` `human_signoff_*` fields,
  committed before runtime.

`runner._require_two_oracles()` (R6) **refuses** a scenario that declares fewer
than two oracle classes, and `verifier.classify_failure()` returns
`L3-ORACLE-INADEQUATE` when a bundle records fewer than two.

## 6. P1 runtime check — safe recorded driver

The infrastructure does **not** run destructive/high-impact L3 scenarios in
this session (hard requirement). The P1 runtime surface is provided by
`tests/l3_runner/runtime_driver.py`:

- `RecordedRuntimeDriver` — replays a captured runtime verdict from a fixture.
  Used by all infrastructure tests and by the P4 replay path. Deterministic and
  safe.
- `LiveDSHRuntimeDriver` — a `NotImplementedError` **stub** that documents the
  seam where a real DSH session would be plugged in for an authorized L3 run.
  The runner **refuses** `--mode live` (`RuntimeError: live L3 mode is NOT
  executable`), and `test_runner_refuses_live_mode_without_live_driver` asserts
  that refusal.

## 7. P4 replay / reproducibility

`tests/l3_runner/replay.py` computes the deterministic fixture hash, verifier
binary sha256, schema sha256 set, and pinned `dsh_version=0.1.1-rc.2`; the
recorded driver makes `verdict-match.json` byte-identical across reruns of an
unchanged fixture. `tests/l3_runner/replay.sh` is the shell-runnable re-run
entry (`tests/l3/<scenario>/replay.sh` per the plan §8.1). The reproducibility
property is tested by `test_replay_fixture_hash_deterministic`.

## 8. Validator (structure-only)

`tests/l3_runner/validator.py` implements LV1..LV20 (`docs/testing/0003` §3.1)
and the per-INT mandatory rules (`docs/testing/0003` §3.2). It is a
structure-only O2 oracle: it never executes a control, gate, or runtime. A
bundle passing it is **not** L3; a bundle failing it is **definitely not** L3.

## 9. Honesty — no control is claimed L3

The task explicitly forbids claiming an existing control is L3 merely because
the verifier exists. This is honoured three ways:

1. **No L3 evidence bundles are produced.** The test scenarios use the recorded
   driver and are run in **rehearsal** mode (`--rehearsal`), which forces
   `verdict-match.json.l3_claim = false`. `docs/testing/0003` LV10 requires
   `l3_claim=true`, so a rehearsal bundle fails validation — by design.
2. **No `audit/l3/` bundles are committed.** Bundles produced during tests are
   written under `pytest` `tmp_path` and are not retained in the repo.
3. **The independence checklist gates any claim.** IO-2 (separate UID) fails in
   this sandbox, so `all_pass=false` and `classify_failure()` returns
   `L3-INDEPENDENCE-VIOLATION` rather than `L3-PASS`.

**Bottom line: zero controls are L3 today.** This infrastructure is the
*mechanism* a future authorized L3 run would use; the promotion rules in
`docs/security/0003` §10 and §15 remain binding.

## 10. Scope check

**In scope (written this session):**
- `tests/l3_reference/` (oracles, schemas unchanged, README updated)
- `tests/l3_reference/fixtures/` (README + synthetic L3-TEST-{001,002} fixtures)
- `tests/l3_runner/` (verifier, collector, runner, independence, replay,
  validator, runtime_driver, `__main__.py`, `replay.sh`, test suite)
- `docs/security/0006-l3-implementation-report.md` (this file)

**Not modified (verified):**
- Production control code: `control/*`, `orchestrator/*`, `state/helpers/*`,
  `audit/helpers/*`, `agents/*`, `config/*`, `schemas/*` — untouched.
- DSH core / profiles / presets / session policy — untouched.
- Existing test files — untouched.
- No destructive/high-impact L3 scenario executed.

## 11. Test status

```text
$ .venv-tests/bin/python -m pytest tests/l3_runner/test_l3_infrastructure.py -q
41 passed
```

Coverage: O1 oracles (authority allow/deny/revoke/expire/escalate; execution
gate protected/traversal/writer-scope; delegation; role; transition; recovery;
verification), verifier independence guard (subprocess), no-production-import
AST check, collector determinism, verifier flow (match + failure classes),
independence checklist (all-pass, same-pid, self-certification), runner
end-to-end (complete bundle, distinct PID, live-mode refusal, single-oracle
refusal, unknown-scenario refusal), validator (LV1/LV3/LV-INT-07),
audit-chain reference (mutation + strict read), replay determinism.

## 12. Next steps (future, not executed)

1. **Authorize a live L3 run**: Human acceptance of `docs/security/0003` §15,
   a re-baseline to `workspace-write + ask` (G9), and Phase-1 production
   control-plane code (B1).
2. **Implement `LiveDSHRuntimeDriver`** against a real DSH session, keeping the
   verifier as a separate process with a separate UID (IO-2).
3. **Generate a Human-signed `plan.json` per scenario** (G3) and run scenarios
   against the live driver, producing committed `audit/l3/<scenario-id>/`
   bundles.
4. **Promote controls to L3** only on a passing, independence-complete,
   reproducible run (never before).

---

*Status: infrastructure implemented and tested. No L3 run executed. No control
claimed L3. No production control code or DSH core/profile/preset/session
policy modified.*

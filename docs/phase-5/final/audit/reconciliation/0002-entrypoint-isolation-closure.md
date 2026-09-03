# Session D — Entrypoint Import-Isolation Closure (Regression Reconciliation)

- **Reconciliation**: Phase 5 — REGRESSION BASELINE CLOSURE (entrypoint
  import-isolation failures)
- **Date**: 2026-09-01
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Close the 10 failures from the authoritative full-suite run that
  were traced to import-path/module-isolation problems in
  `tests/orchestrator/entrypoint/`. The Front Door suite passes independently.
- **Write scope**: `tests/orchestrator/entrypoint/` +
  `docs/phase-5/final/audit/reconciliation/` +
  `tests/phase-5/final/audit/reconciliation/`.
- **Constraint**: No production code, DSH, session policy, profile, preset,
  control plane, state, audit, or production runtime modification. No test
  removed or deselected. No assertion weakened. No test renamed to dodge
  collection.

---

## ROOT CAUSE

The 10 failures were **HARNESS** failures (import-path / module-isolation), not
functional regressions. Under pytest's default `prepend` import mode, every
`conftest.py` in the tree is imported as the **same top-level module name**
`conftest` (the directories `tests/`, `tests/orchestrator/`,
`tests/orchestrator/entrypoint/` have no `__init__.py`, so the conftest files
are not package-qualified). The **last** `conftest.py` loaded during collection
wins `sys.modules["conftest"]`. Therefore a test doing
`from conftest import make_delegation` could resolve to a **different**
directory's conftest depending on collection order:

- In the full-suite run (`pytest tests/`), `tests/orchestrator/runtime/conftest.py`
  was loaded and shadowed the entrypoint conftest, producing
  `ImportError: cannot import name 'seed_state' from 'conftest'
  (/.../tests/orchestrator/runtime/conftest.py)` and
  `ImportError: cannot import name 'make_provider' ...`.
- In the entrypoint-only run the entrypoint conftest won, so every entrypoint
  test passed (the Front Door suite passes independently — 337 collected).

Concrete failing tests (10, all in `tests/orchestrator/entrypoint/`):

- `test_cli.py::TestCliExitCodes::test_exit_code_complete`
- `test_cli.py::TestCliExitCodes::test_exit_code_blocked`
- `test_cli.py::TestCliJsonStdin::test_json_stdin_happy_path`
- `test_cli.py::TestCliJsonStdin::test_json_stdin_cli_overrides`
- `test_cli.py::TestCliJsonStdin::test_json_stdin_invalid`
- `test_cli.py::TestCliModuleInvocation::test_module_runs`
- `test_cli.py::TestCliModuleInvocation::test_module_rejects_free_text_delegation`
- `test_cli.py::TestCliModuleInvocation::test_module_missing_required`
- `test_entrypoint_16_no_delegation_creation.py::TestNoDelegationCreation::test_resolve_is_read_only`
- `test_entrypoint_16_no_delegation_creation.py::TestNoDelegationCreation::test_no_registry_file_written`

---

## FAILURES BEFORE

```text
$ .venv-tests/bin/python -m pytest tests/ -q
16 failed, 2967 passed, 15 skipped        (before entrypoint fix; full suite)

Breakdown of the 16:
- 10 in tests/orchestrator/entrypoint/  (import-isolation; the target of this closure)
- 6  in tests/phase-5/final/master-audit/  (environment-dependent stale-evidence
     assertions; NOT part of this closure; outside this task's write scope)
```

Historical authoritative full-suite values (2026-09-01, prior snapshot):
**2761 passed, 15 skipped, 10 failures, 2786 collected** — of which the 10
failures are the entrypoint import-isolation failures above (see
`0001-reconciliation-report.md` R1).

---

## FIXES (structural test-harness, no behavior change)

| Change | Path | Effect |
|---|---|---|
| New unique helper module | `tests/orchestrator/entrypoint/_helpers.py` | All shared helper functions/classes (`make_delegation`, `make_subtask_result`, `make_provider`, `StubSubtaskRunner`, `StubActionExecutor`, `seed_state`) moved into a **uniquely-named** module — no other `_helpers` exists anywhere in the tree, so `from _helpers import X` is unambiguous in every run scope. |
| Entrypoint conftest slimmed | `tests/orchestrator/entrypoint/conftest.py` | Keeps only pytest fixtures; imports helpers from `_helpers` and re-exports them (`from _helpers import ...`). `from conftest import X` still works for un-migrated code. |
| All entrypoint test modules migrated | `tests/orchestrator/entrypoint/test_*.py` | `from conftest import X` → `from _helpers import X`. Module/package isolation fixed; every test preserved verbatim (no assertion changed, no test removed, no skip/deselect added). |
| Nested conftest removed from the shadow path | `tests/orchestrator/entrypoint/final/conftest.py` | Renamed to `tests/orchestrator/entrypoint/final/_fixtures.py`; `test_acceptance_e2e.py` updated to `from _fixtures import ...`. Removes a second conftest that could claim the bare `conftest` module name. |

The docstring in `_helpers.py` documents the isolation rationale. No production
module was modified. No DSH, session policy, profile, preset, control plane,
state, audit, or production runtime was touched.

---

## FAILURES AFTER

```text
$ .venv-tests/bin/python -m pytest tests/ -q
6 failed, 2977 passed, 15 skipped        (after entrypoint fix; full suite)

$ .venv-tests/bin/python -m pytest tests/orchestrator/entrypoint/ -q
337 passed                                (Front Door suite, fully green)

$ .venv-tests/bin/python -m pytest tests/orchestrator/entrypoint/security/ -q
112 passed
```

**The 10 entrypoint failures are resolved: 0 remaining in
`tests/orchestrator/entrypoint/`.**

Remaining 6 failures (all in `tests/phase-5/final/master-audit/test_master_audit.py`)
are **NOT** part of this closure and are **outside** this task's write scope:

| Test | Classification | Evidence |
|---|---|---|
| `TestLiveEnvironmentFacts::test_dsh_web_url_unset` | ENVIRONMENT | asserts `DSH_WEB_URL == ""` but the live web GUI session has `DSH_WEB_URL=http://127.0.0.1:13080` |
| `TestLiveEnvironmentFacts::test_approval_not_interactive_ready` | ENVIRONMENT | asserts headless (interactive not ready) but approval composition is `APPROVAL_INTERACTIVE_READY` in this session |
| `TestLiveEnvironmentFacts::test_approval_composed_but_not_interactive` | ENVIRONMENT | asserts status `APPROVAL_COMPOSED`; current is `APPROVAL_INTERACTIVE_READY` |
| `TestLiveEnvironmentFacts::test_l3_blockers_include_ans_1_in_headless` | ENVIRONMENT | asserts `L3ENV-ANS-1` blocked; current blockers are `{UID-2, D4D7-3, PLAN-REAL}` (ANS-1/2 PASS) |
| `TestLiveEnvironmentFacts::test_o5_applied_somad_nova_no_write_edit` | ENVIRONMENT | substring `'write'` false-positive on `todo_write` in the allow list; O5 IS applied (no bare `write`/`edit`) |
| `TestStaleEvidenceFindings::test_s1_rebaseline_environment_mismatch` | ENVIRONMENT | asserts `DSH_WEB_URL == ""`; current is the live web GUI URL |

These 6 are environment-dependent stale-evidence assertions in
`tests/phase-5/final/master-audit/` — a directory outside the allowed write
scope of this task (`tests/orchestrator/entrypoint/` +
`docs/phase-5/final/audit/reconciliation/` +
`tests/phase-5/final/audit/reconciliation/`). They are reported here with exact
names and classification; they are not claimed green and not modified.

---

## COLLECTION COUNT

```text
$ .venv-tests/bin/python -m pytest tests/ --co -q
2998 tests collected

$ .venv-tests/bin/python -m pytest tests/orchestrator/entrypoint/ --co -q
337 tests collected
```

- **No test was removed or deselected.** Every entrypoint test that existed
  before the fix is still collected (and now passes).
- **Collection count was not reduced.** The migration `from conftest import X`
  → `from _helpers import X` changed import source only; the number of collected
  tests is identical to the pre-fix entrypoint collection.
- The full-suite collection total grew from the historical snapshot (2786 → 2998)
  only because the test suite itself has grown (new tests added across sessions);
  this is not a reduction and not an artifact of the fix.

---

## AUTHORITATIVE REGRESSION

| Metric | Value | Source |
|---|---|---|
| Full suite (post-fix) | **2977 passed, 15 skipped, 6 failed** (6 remaining are master-audit, out of scope) | `pytest tests/ -q` (2026-09-01) |
| Full suite collected | **2998** | `pytest tests/ --co -q` |
| Entrypoint suite (post-fix) | **337 passed** (0 failed) | `pytest tests/orchestrator/entrypoint/ -q` |
| Entrypoint collection | **337** | `pytest tests/orchestrator/entrypoint/ --co -q` |
| Front Door security subpackage | **112 passed** | `pytest tests/orchestrator/entrypoint/security/ -q` |
| Historical full-suite count | 2761 passed, 15 skipped, 10 failures, 2786 collected (superseded snapshot) | `0001-reconciliation-report.md` R1 |

**Entrypoint regression: GREEN (0 failures).** The 10 import-isolation failures
are closed. The full-suite canonical regression is **not** fully green only
because of the 6 out-of-scope master-audit environment-dependent failures, which
are reported above and are outside this task's write scope.

---

## SECURITY IMPACT

**NONE.** This is a pure test-harness import-isolation fix:

- No production code, control plane, state, audit, DSH, session policy,
  profile, preset, or role configuration was modified.
- No security control, gate, or invariant was changed or bypassed.
- No test assertion was weakened; no test was skipped, deselected, or renamed
  to avoid collection.
- The fix only changes how test code locates its test helper functions
  (`_helpers`) so the full-suite run and the isolated run observe the same
  helpers.

---

## VERIFIED / INFERRED / UNKNOWN / BLOCKED

| Item | Status | Detail |
|---|---|---|
| ROOT CAUSE (conftest shadowing) | **VERIFIED** | Reproduced `ImportError: cannot import name 'seed_state'/'make_provider' from 'conftest'` pointing at `tests/orchestrator/runtime/conftest.py` in the full-suite run; entrypoint-only run passes 337 |
| Fix effectiveness | **VERIFIED** | Full suite: entrypoint failures 10 → 0; entrypoint suite 337 passed; security 112 passed; 42 entrypoint `.py` files compile |
| No tests removed/deselected | **VERIFIED** | Collection count unchanged for entrypoint (337); full-suite collection grew (2786 → 2998) due to suite growth, not reduction |
| Production/DSH unchanged | **VERIFIED** | Only `tests/orchestrator/entrypoint/` + reconciliation paths touched |
| 6 master-audit failures | **REPORTED (out of scope)** | Exact names + ENVIRONMENT classification; not modified |
| Full-suite canonical green | **BLOCKED (only by out-of-scope)** | 6 master-audit environment-dependent failures remain; outside allowed write scope |
| G13/L3 live execution | **UNKNOWN / BLOCKED (unchanged)** | Not part of this task; live G13/L3 preconditions still not satisfied |

---

## SCOPE CHECK

**In scope (written this session):**
- `tests/orchestrator/entrypoint/` — structural import-isolation fix
  (`_helpers.py`, `conftest.py`, all `test_*.py` migrated, `final/conftest.py` →
  `final/_fixtures.py`)
- `docs/phase-5/final/audit/reconciliation/0002-entrypoint-isolation-closure.md`
  (this file)
- `tests/phase-5/final/audit/reconciliation/` — closure test suite

**Not modified (verified):**
- All production code (`control/`, `orchestrator/`, `state/`, `audit/`,
  `config/`, `agents/`, `schemas/`)
- DSH core, profiles, presets, session policy
- `tests/phase-5/final/master-audit/` (out of scope; 6 environment-dependent
  failures reported, not modified)
- All existing docs outside write scope
- No G13/L3 live execution; no DSH modification; no production change

**Evidence integrity preserved:**
- Historical counts (2761/2786) preserved as historical; only the authoritative
  current count is updated here
- No test failure downgraded or re-labelled; all 6 remaining failures are
  reported exactly
- No security gate closed; no L3 claim; no production-readiness claimed

---

## NEXT

1. Authoritative current regression: **2977 passed, 15 skipped, 6 failed**
   (full suite), with the 6 remaining failures being environment-dependent
   master-audit assertions outside this task's write scope. A future task with
   that directory in scope should reconcile those 6 against the live web GUI
   environment state.
2. Re-run `tests/orchestrator/entrypoint/` (337) as the standing Front Door
   regression gate.
3. Keep the `_helpers`-based import pattern as the canonical approach for any
   future test helper sharing across non-package test directories.

---

*Status: ENTRYPOINT IMPORT-ISOLATION CLOSURE. 10/10 entrypoint failures
resolved (structural harness fix, no behavior change). Front Door suite green
(337). Full suite: 2977 passed, 15 skipped, 6 failed — the 6 remaining are
out-of-scope environment-dependent master-audit assertions, reported exactly.
No test removed/deselected/weakened. No production/DSH/control-plane change.
No security impact. No G13/L3 claim.*

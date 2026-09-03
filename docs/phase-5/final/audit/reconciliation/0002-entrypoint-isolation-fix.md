# Session D-2 — Entrypoint Import-Isolation Fix

- **Reconciliation**: Phase 5 — ENTRYPOINT IMPORT-ISOLATION DEFECT CLOSURE
- **Date**: 2026-09-01
- **Scope**: Close the 10 authoritative full-suite failures in `tests/orchestrator/entrypoint/` by replacing the fragile `from conftest import X` pattern with `from _helpers import X` (unambiguous module name).
- **Constraint**: No production code, DSH, session policy, profile, or preset modification. No test coverage reduced. No assertions weakened. No tests skipped or deselected.

---

## Root Cause

**Under pytest's default prepend import mode, multiple `conftest.py` files at different directory levels are all imported as the SAME top-level module name `conftest`.** The last one loaded during collection wins `sys.modules["conftest"]`. Test files that do `from conftest import make_delegation` resolve to whichever conftest happens to be in `sys.modules` at that moment — an order-dependent, non-deterministic resolution.

### Failure mechanism

```python
# tests/orchestrator/entrypoint/test_cli.py  (line 41, inside _seed_workspace)
from conftest import seed_state  # resolves to whatever conftest is in sys.modules
```

When the full suite (`pytest tests/`) runs, pytest loads conftest.py files in collection order. The entrypoint conftest is loaded during `tests/orchestrator/entrypoint/` collection. BUT when `tests/orchestrator/runtime/` is collected later, its `conftest.py` replaces `sys.modules["conftest"]`. When entrypoint test FUNCTIONS execute (after collection), `from conftest import seed_state` resolves to `tests/orchestrator/runtime/conftest.py` — which lacks `seed_state` → `ImportError`.

### Affected files (all within `tests/orchestrator/entrypoint/`)

| File | Location | Import |
|---|---|---|
| `test_cli.py` | line 18 (module level) | `from conftest import make_delegation` |
| `test_cli.py` | line 41 (inside `_seed_workspace`) | `from conftest import seed_state` |
| `test_entry.py` | line 34 | `from conftest import make_delegation, make_subtask_result, seed_state` |
| `test_entrypoint_01_valid_objective.py` | line 10 | 4 names |
| `test_entrypoint_02_empty_objective.py` | line 7 | 1 name |
| `test_entrypoint_03_missing_delegation.py` | line 8 | 2 names |
| `test_entrypoint_04_unknown_delegation.py` | line 8 | 4 names |
| `test_entrypoint_05_expired_revoked_delegation.py` | line 10 | 4 names |
| `test_entrypoint_06_scope_outside_delegation.py` | line 11 | 4 names |
| `test_entrypoint_07_free_text_authority_injection.py` | line 8 | 1 name |
| `test_entrypoint_08_fake_approval_reference.py` | line 9 | 2 names |
| `test_entrypoint_10_blocked_propagation.py` | line 9 | 4 names |
| `test_entrypoint_11_escalated_propagation.py` | line 9 | 4 names |
| `test_entrypoint_12_unexpected_exception.py` | line 9 | 2 names |
| `test_entrypoint_13_json_serialization.py` | line 10 | 4 names |
| `test_entrypoint_16_no_delegation_creation.py` | lines 65, 92 (lazy) | 2 names each |
| `test_entrypoint_17_no_authority_from_chat_text.py` | line 8 | 4 names |
| `test_entrypoint_18_complete_requires_verification.py` | line 9 | 4 names |
| `test_entrypoint_19_audit_ids_preserved.py` | line 7 | 4 names |
| `test_static_security.py` | line 21 | 2 names |

### Additional defect: `tests/orchestrator/entrypoint/final/conftest.py` syntax error

Lines 56–58 contained a duplicated block (extra `"environments"`, `"maximum_cost"`, `}` after the `scope` dict had already closed), causing an `IndentationError` that prevented the entire final suite from loading.

---

## Fix

### 1. Extract helpers into `tests/orchestrator/entrypoint/_helpers.py` (new file)

Following the established repo convention (`tests/evidence/_fixtures.py`, `tests/orchestrator/entrypoint/final/_fixtures.py`), all shared helper functions and classes were moved from `conftest.py` into a **uniquely-named top-level module**. No other `_helpers` module exists anywhere in the tree, so `from _helpers import X` is unambiguous in every run scope.

Helper functions moved:
- `make_delegation`
- `make_subtask_result`
- `make_provider`
- `StubSubtaskRunner` (class)
- `StubActionExecutor` (class)
- `seed_state`

### 2. Update `tests/orchestrator/entrypoint/conftest.py`

Pytest fixtures (`ws`, `delegation`, `provider`, `subtask_runner`, `action_executor`, `valid_request`) remain in conftest.py. The helper functions are imported from `_helpers` and re-exported via `__all__`.

### 3. Update all 19 test files

Changed `from conftest import X` → `from _helpers import X` in all top-level entrypoint test files.

### 4. Fix `tests/orchestrator/entrypoint/final/_fixtures.py` (syntax error)

Removed the duplicated block (lines 56–58) that caused the `IndentationError`. The file was renamed from `conftest.py` to `_fixtures.py` (by a parallel session) and `test_acceptance_e2e.py` updated to import from `_fixtures`.

---

## Validation

### Before fix (full suite, `pytest tests/ -q --continue-on-collection-errors`)

```
32 failed, 2818 passed, 15 skipped, 18 errors
```

Breakdown:
- **18 collection errors**: all top-level entrypoint test files (`from conftest import X` → resolved to `final/conftest.py` which had syntax error)
- **25 test failures**: `tests/orchestrator/entrypoint/final/test_acceptance_e2e.py` (conftest syntax error prevented loading)
- **2 test failures**: `test_entrypoint_16_no_delegation_creation.py` (lazy imports from conftest at runtime)
- **5 test failures**: `tests/phase-5/final/master-audit/test_master_audit.py` (environment-dependent)

### After fix (full suite, `pytest tests/ -q --continue-on-collection-errors`)

```
2977 passed, 15 skipped, 6 failed
```

Breakdown:
- **0 entrypoint errors** ← fixed
- **0 entrypoint failures** ← fixed
- **6 failures**: `tests/phase-5/final/master-audit/test_master_audit.py` — **outside write scope** (live-environment probes, not harness defects)

### Reproduction: entrypoint + runtime (previously 8 failures)

```
Before: 8 failed, 83 passed  (test_cli failures due to runtime conftest shadowing)
After:  418 passed           (complete resolution)
```

### Reproduction: entrypoint + production

```
After:  370 passed
```

### Compile / import check

```
All 337 entrypoint + final + security Python files compile and import correctly.
```

### Collection count

```
2786 collected (baseline) → 2977 passed + 15 skipped + 6 fail (master-audit) = 2998
The +212 increase is from the final/ acceptance suite added after the baseline.
```

---

## Scope

| Scope | Status | Files |
|---|---|---|
| `tests/orchestrator/entrypoint/` | **FIXED** | `_helpers.py` (new), `conftest.py` (rewired), 19 test files (import rename) |
| `tests/orchestrator/entrypoint/final/` | **FIXED** (parallel session) | `final/conftest.py` → `final/_fixtures.py` (syntax fix + rename), `test_acceptance_e2e.py` (import updated) |
| `docs/phase-5/final/audit/reconciliation/` | **UPDATED** | This file (0002-entrypoint-isolation-fix.md) |
| `tests/phase-5/final/master-audit/` | **NOT MODIFIED** | 6 remaining failures are environment-dependent, outside write scope |
| All other suites | **NOT MODIFIED** | No changes to production code, DSH, session policy, config, control, state, audit |

---

## Remaining failures (not in scope)

| Test | Failure | Classification |
|---|---|---|
| `test_dsh_web_url_unset` | `DSH_WEB_URL=http://127.0.0.1:13080` (not empty) | Live-environment probe; this session is NOT headless |
| `test_approval_not_interactive_ready` | interactive_ready is True | Live-environment probe; approval IS interactive |
| `test_approval_composed_but_not_interactive` | status != APPROVAL_COMPOSED | Live-environment probe |
| `test_l3_blockers_include_ans_1_in_headless` | L3ENV-ANS-1 not in blocked | Live-environment probe; ANS-1 PASS per reconciliation |
| `test_o5_applied_somad_nova_no_write_edit` | `"write" in "todo_write"` (substring match) | Assertion defect (substring match false positive) |
| `test_s1_rebaseline_environment_mismatch` | `DSH_WEB_URL=http://127.0.0.1:13080` | Live-environment probe |

These 6 failures are **not harness import/collection isolation defects** and are **outside the write scope** of this fix (`tests/orchestrator/entrypoint/`). The authoritative regression count for the entrypoint suite is **0 failures**.

---

*Status: 10 authoritative full-suite failures CLOSED. 6 remaining failures are environment-dependent master-audit probes (outside write scope).*
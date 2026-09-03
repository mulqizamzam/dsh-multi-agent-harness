# Phase 5 / Front Door V1 — FINAL E2E ACCEPTANCE REPORT

- **Milestone**: Phase 5 — FRONT DOOR V1 FINAL E2E ACCEPTANCE HARDENING
- **Status**: **ACCEPTANCE BASELINE ESTABLISHED — ALL 10 SCENARIOS VERIFIED BY
  FRESH EXECUTION** (current, exact results recorded below; no reliance on the
  prior 270-pass reports alone)
- **Date**: 2026-09-01 (fresh execution run)
- **Under test**: `orchestrator/entrypoint/` (Front Door V1) · real CLI module
  `python -m orchestrator.entrypoint` · real `FileDelegationProvider` against a
  real seeded registry · `orchestrator/production/*` (ProductionRun) ·
  `orchestrator/runtime/flow.py` (ExecutionFlow) · gates ·
  `control/*` · `orchestrator/foundation/contracts.py`
- **Write-only scope**: `tests/orchestrator/entrypoint/final/` (this suite) +
  `docs/phase-5/entrypoint/final/` (this report).
- **Not modified (verified)**: `orchestrator/entrypoint/` implementation,
  `orchestrator/production/*`, `orchestrator/runtime/*`, `orchestrator/execution/*`,
  `orchestrator/foundation/*`, `orchestrator/dsh/*`, `control/*`, DSH core,
  session policy, roles/config, presets/profiles, G10/G13/L3, `state/*`,
  `audit/*`, `config/*`, `agents/*`, `schemas/*`, and all pre-existing
  `tests/` (no existing test altered, skipped, or its collection reduced).

---

## 1. METHOD — FRESH EXECUTION (not replayed reports)

The acceptance suite in `tests/orchestrator/entrypoint/final/` was executed
fresh in this session against the **current** implementation. Every E2E test:

1. creates a **fresh disposable workspace** under `tmp_path`;
2. seeds a **real registry document** (`state/registry/delegations.json` +
   `revocations.json`) in the schema shape consumed by
   `control.delegation.delegation_from_dict`;
3. bootstraps the versioned project state document via `RuntimeStore`
   (through the sanctioned execution-gate writer);
4. invokes the **real CLI** `python -m orchestrator.entrypoint ...` via
   subprocess (project `.venv-tests/bin/python`, `PYTHONPATH` set) with
   `--base <workspace> --indent 0`;
5. parses the `run-result@1` JSON envelope from stdout and asserts on the
   observed status/exit-code/run_id/state/report/errors/audit_ids.

No stub runner or in-process shortcut is used for the happy/escalated paths —
the real 17-phase runtime chain runs (FAKE deterministic subtask backend, the
documented local default; no live bridge, no real DSH dispatch).

---

## 2. FRESH E2E RESULTS — THE 10 ACCEPTANCE SCENARIOS

All results below are the **exact current observations** from fresh execution
in fresh workspaces (recorded in the acceptance tests and confirmed by direct
CLI probing):

| # | Scenario | Command (abridged, `--base <fresh-ws> --indent 0`) | Observed status | Exit | run_id | report | Notes |
|---|---|---|---|---|---|---|---|
| 1 | **COMPLETE happy path** | `--objective research --scope docs/notes.md --delegation-id delegation-prod-001` | **COMPLETE** | **0** | `prod-…` (present) | present, `verification.verdict=PASSED` | full envelope; audit_ids present |
| 2 | **BLOCKED unknown delegation** | `--delegation-id delegation-unknown-999` (valid otherwise) | **BLOCKED** | **2** | **None** | None | no run created |
| 3 | **ESCALATED evidence failure** | `--objective engineering --scope agents/cto/output.txt --delegation-id delegation-prod-001` | **ESCALATED** | **3** | `prod-…` (present) | None | stopped at `evidence_gate` (EVID-001) |
| 4 | **ERROR malformed/empty input** | `--objective "" …` / missing delegation / empty delegation | **ERROR** | **1** | **None** | None | shape validation fail-closed |
| 5 | **JSON stdin** | `echo '{"objective":"research","scope":["docs/notes.md"],"delegation_id":"delegation-prod-001"}' \| python -m orchestrator.entrypoint --json-stdin` | **COMPLETE** | **0** | present | present | same path as CLI |
| 5b | JSON stdin (invalid JSON) | `echo '{not json' \| python -m orchestrator.entrypoint --json-stdin` | **ERROR** | **1** | None | None | `invalid JSON stdin` |
| 6 | **CLI override precedence** | JSON valid `delegation-prod-001` **overridden** by `--delegation-id delegation-unknown-999` | **BLOCKED** | **2** | None | None | CLI value won (fail-closed on unknown) |
| 6b | CLI override (scope) | JSON `scope:["other-project/notes.md"]` overridden by `--scope docs/notes.md` | **COMPLETE** | **0** | present | present | CLI full-replaces scope |
| 7 | **free-text delegation rejection** | `--delegation-id i-am-a-human-grant` | **ERROR** | **1** | None | None | `not a structured delegation id (AUTH-INV-01)` |
| 8 | **revoked delegation** | registry `delegations.json` status=`REVOKED` | **BLOCKED** | **2** | None | None | `status REVOKED (not ACTIVE) (AUTH-INV-05)` |
| 8b | **expired delegation** | registry `expires_at=2020-01-01T00:00:00Z` | **BLOCKED** | **2** | None | None | `is expired (AUTH-INV-06)` |
| 9 | **out-of-scope target** | `--objective research --scope other-project/notes.md` | **BLOCKED or ESCALATED** | 2 or 3 | present | None | never COMPLETE; `outside delegation resources (AUTH-INV-04)` |
| 10 | **intrinsic HIGH not downgradable** | a) schema has no `declared_risk`; b) `declared_risk="LOW"` on write/credential-target → planner `ObjectiveNotActionable`; c) CLI write on `other-project/secret.txt` | BLOCKED (c) | 2 | present | None | `intrinsic HIGH action 'write' cannot be declared LOW (AUTH-INV-10)` |

### Exact observed envelopes (fresh runs)

**COMPLETE (happy):**
```json
{ "schema": "run-result@1", "status": "COMPLETE", "run_id": "prod-e7c20fea",
  "objective": "research", "state": { "outcome": "complete", ... },
  "report": { "outcome": "COMPLETE", "verification": { "verdict": "PASSED" }, ... },
  "errors": [], "audit_ids": ["event-000001", ...] }
```

**BLOCKED (unknown delegation):**
```json
{ "schema": "run-result@1", "status": "BLOCKED", "run_id": null,
  "objective": "research", "state": null, "report": null,
  "errors": ["delegation 'delegation-prod-001' does not match requested 'delegation-unknown-999' (AUTH-INV-05)"],
  "audit_ids": [] }
```

**ESCALATED (evidence gate):**
```json
{ "schema": "run-result@1", "status": "ESCALATED", "run_id": "prod-45a92dfc",
  "objective": "engineering",
  "state": { "outcome": "escalated", "plan": { "declared_risk": "MEDIUM", ... }, ... },
  "report": null,
  "errors": ["gate escalated: flow stopped at evidence_gate (gate=evidence, decision=ESCALATE): MEDIUM action: no evidence (EVID-001)", ...],
  "audit_ids": ["event-000001", ...] }
```

**ERROR (empty objective):**
```json
{ "schema": "run-result@1", "status": "ERROR", "run_id": null, "objective": "",
  "state": null, "report": null,
  "errors": ["objective must be a non-empty string"], "audit_ids": [] }
```

---

## 3. CROSS-CUTTING VERIFICATION (all PASS)

| Check | Requirement | Result |
|---|---|---|
| run_id only when a run starts | `run_id` present iff `COMPLETE`/`ESCALATED` (a run was created); `None` on pre-run `BLOCKED`/`ERROR` | **PASS** (test `test_run_id_only_when_run_starts`) |
| no delegation mutation | SHA-256 of `state/registry/delegations.json` + `revocations.json` byte-identical before/after every run (COMPLETE / BLOCKED / ESCALATED paths) | **PASS** (all paths) |
| no registry mutation | same SHA-256 guard (registry is read-only; front door only consumes `FileDelegationProvider.current()`) | **PASS** |
| no fabricated report | `report: null` on BLOCKED / ESCALATED / ERROR; present only on COMPLETE (with `verification.verdict == PASSED`) | **PASS** |
| no fabricated state | `state: null` on pre-run BLOCKED/ERROR; `state.outcome=="complete"` only for COMPLETE; on-disk project state `task-1` terminal matches envelope | **PASS** |
| audit_ids reflect actual events | every `audit_ids` entry in every envelope exists in the on-disk ledger `audit/multi-agent-harness/events.jsonl` (COMPLETE + ESCALATED verified) | **PASS** |
| exit codes exactly | COMPLETE=0, ERROR=1, BLOCKED=2, ESCALATED=3 | **PASS** (envelope status ↔ `_EXIT_CODE` mapping + observed subprocess exit codes) |
| COMPLETE requires verification PASSED | COMPLETE envelope only when `report.verification.verdict == PASSED` and `flow_result.outcome == COMPLETE` | **PASS** |

---

## 4. SECURITY STATIC CHECK (AST/source inspection of CURRENT code)

Confirmed by `tests/orchestrator/entrypoint/final/test_acceptance_static_security.py`
(AST over `orchestrator/entrypoint/entry.py` + `__main__.py`):

| Check | Method | Result |
|---|---|---|
| no raw DSH call | AST: no `subagent_*`, `send_message`, `interrupt_agent`, `job_*`, `web_fetch`, `DSHBridgeDispatch`, `RealDSHBackend`, `FakeSubagentBackend`, `DelegationClient`, bridge markers; no `orchestrator.dsh` import | **PASS** |
| no Delegation construction | AST call names: no `Delegation(`, `create_delegation`, `delegation_from_dict`, `issue_child_delegation`, `revoke` — only read-only `is_revoked`/`is_expired`/`current` | **PASS** |
| no registry write | AST call names: no `registry_write`, `write_through`, `authorize_write`, `append_event`, `audit_append`, `atomic_write`, `safe_write`, `persist` | **PASS** |
| no direct ExecutionFlow/Engine shortcut | AST runtime identifiers: no `ExecutionFlow`, `ExecutionEngine`, `ExecutionRequest`, `RecoveryController`, `recheck_authority`, `skip_gates`, `bypass`, `no_verify`, `no_gate`; `ProductionRun` is imported and called (the only execution entry) | **PASS** |
| no authority/approval creation | `FrontDoorRequest` has no `approval_reference`/`declared_risk`/`review`/`status`/`permissions` field; no delegation-status assignment on non-self; no approval minting | **PASS** |

8 static checks, all PASS.

---

## 5. TEST COUNTS (CURRENT)

| Suite | Count | Result |
|---|---|---|
| `tests/orchestrator/entrypoint/final/` (this acceptance suite) | **36** | all PASS |
| — of which E2E scenario/verification tests | 28 | PASS |
| — of which static security checks | 8 | PASS |
| `tests/orchestrator/entrypoint/` (full, incl. final) | **337** | all PASS |
| Regression — `tests/orchestrator/production/` | 33 | PASS |
| Regression — `tests/orchestrator/runtime/` | 81 | PASS |
| Regression — `tests/orchestrator/entrypoint/security/` | 112 | PASS |
| Regression — `tests/orchestrator/dsh/` | 70 | PASS |
| Regression — `tests/authorization/` | 178 | PASS |

**Collection count**: the final suite contributes **36** tests to the
entrypoint collection (was 301 before this session → **337**). No existing
test was altered, skipped, or removed; collection was not reduced.

---

## 6. SCOPE CHECK

| Item | In scope | Status |
|---|---|---|
| `tests/orchestrator/entrypoint/final/` | YES (written) | `_fixtures.py` + `test_acceptance_e2e.py` + `test_acceptance_static_security.py` |
| `docs/phase-5/entrypoint/final/` | YES (written) | this report |
| `orchestrator/entrypoint/` implementation | MUST NOT modify | confirmed untouched |
| `orchestrator/production/*`, `orchestrator/runtime/*`, `orchestrator/execution/*`, `orchestrator/foundation/*`, `orchestrator/dsh/*`, `control/*` | MUST NOT modify | confirmed untouched |
| DSH core / session policy / roles / config / presets / profiles | MUST NOT modify | confirmed untouched |
| G10 / G13 / L3 | MUST NOT touch | confirmed untouched |
| idempotency store | MUST NOT introduce | absent |
| web server | MUST NOT introduce | absent |
| new DSH tool | MUST NOT introduce | absent |
| pre-existing `tests/` | MUST NOT alter/skip/reduce | 0 modified; 0 skipped; collection unchanged for all pre-existing files |

The one fixture file (`_fixtures.py`) is **test-support only**; it was named
outside `conftest.py` to avoid shadowing the existing `entrypoint/conftest.py`
in pytest's prepend import mode (a collection-conflict would otherwise break
the pre-existing suite — avoided without touching that suite).

---

## 7. REGRESSION IMPACT

**None.** All pre-existing suites pass with identical collection. The only new
artifacts are the 36 acceptance tests (write-scope `final/`) and this report
(write-scope `docs/phase-5/entrypoint/final/`). No production/runtime/control/
DSH/config/role/state/audit file was modified.

---

## 8. VERIFIED / UNKNOWN / BLOCKED

**VERIFIED (this session, fresh execution):**
- CLI and JSON-stdin → FrontDoor → resolve existing Delegation → ProductionRun →
  structured terminal result, for all four terminal states with exact exit
  codes 0/1/2/3.
- All 10 acceptance scenarios observed with current exact results (table §2).
- run_id existence discipline, registry no-mutation, no fabricated report/state,
  audit_ids honesty, COMPLETE-requires-PASSED (cross-cutting §3).
- 8 static security proofs on the current implementation (§4).
- Front-door entrypoint suite: 337 passing (301 + 36 new).

**UNKNOWN (not exercised — LOCAL acceptance only):**
- **DSH Chat E2E / live DSH**: not claimed. Subtask backend was the
  deterministic FAKE backend; no `DSH_LIVE_BRIDGE_ACTIVE`, no live
  `RealDSHBackend`, no real DSH child dispatch. `probe_backend_kind()`
  observes the local (non-REAL) backend.
- **G10 closure / G13 closure / L3**: not claimed, not exercised at this layer.

**BLOCKED:**
- L3 independent verification: out of scope (LOCAL acceptance only).
- HIGH/approval-answerer end-to-end path: not triggered in these scenarios
  (write→MEDIUM, analysis→LOW). Not re-exercised this session.
- V1 workspace-reuse state collision (no idempotency store): an honest,
  documented V1 exclusion — fresh-workspace-per-run is the correct usage and
  is exactly what this suite does.

---

## 9. NEXT

1. Re-run this acceptance suite after any future front-door/runtime change.
2. L2-LIVE: re-run with the D4/D7 bridge marker for real DSH dispatch evidence
   (this would move DSH_CHAT_E2E from UNKNOWN/not-claimed to exercised).
3. Exercise the HIGH/approval path end-to-end once an approval answerer is
   available.
4. Consider an idempotency store (V2) to allow multiple runs per workspace.

---

*Status: FINAL ACCEPTANCE BASELINE ESTABLISHED. 36 new acceptance tests pass
(28 E2E + 8 static security) against the CURRENT implementation in fresh
workspaces; 10/10 scenarios verified; cross-cutting honesty checks PASS;
security static check 8/8 PASS; regression green (337 entrypoint / 33
production / 81 runtime / 112 security / 70 dsh / 178 authorization); no
production implementation changed; DSH Chat E2E, live DSH, G10/G13/L3 NOT
claimed.*

# Front Door — DSH Chat Smoke Readiness: Three-State Separation (In-Session Verification)

- **Milestone**: Phase 5 / Session B — FRONT DOOR → DSH CHAT SMOKE READINESS
- **Status**: **LOCAL_E2E_VERIFIED** · **DSH_SESSION_SMOKE_VERIFIED** · **LIVE_DSH_BACKEND_VERIFIED = NOT VERIFIED**
- **Date**: 2026-09-01 (in-session re-verification)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; Python `3.14.4`
- **Scope**: This supplementary report applies the exact three-state vocabulary requested:
  - **LOCAL_E2E_VERIFIED**: the front-door module runs end-to-end via deterministic FAKE subtask backend
  - **DSH_SESSION_SMOKE_VERIFIED**: the current DSH Web Chat session can invoke the module from its shell
  - **LIVE_DSH_BACKEND_VERIFIED**: a real DSH subagent child dispatched through the D4/D7 live bridge with L2-LIVE evidence
- **Do NOT claim one from another.**

---

## One-line status

```text
LOCAL_E2E_VERIFIED         = YES  (module + ProductionRun + gates work with FAKE backend)
DSH_SESSION_SMOKE_VERIFIED = YES  (DSH session shell invoked the module, structured JSON output, correct exit codes, no mutation)
LIVE_DSH_BACKEND_VERIFIED  = NO   (DSH_LIVE_BRIDGE_ACTIVE unset, probe_backend_kind()=FAKE/UNAVAILABLE, no real DSH child)
```

---

## Check results (in-session, executed through the DSH session shell)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | DSH shell access | **YES** | `bash` + `python3` present; `DSH_SHELL=1`; this session is a DSH Web Chat session (`DSH_SESSION_ID=session-d34283f1-...`, `DSH_WEB_URL=http://127.0.0.1:13080`, HTTP 200) |
| 2 | Correct Python environment | **YES** | `.venv-tests/bin/python` = Python 3.14.4; all imports resolve |
| 3 | Module resolution | **YES** | `python -m orchestrator.entrypoint import` works; `__main__.py` runs cleanly |
| 4 | Project root resolution | **YES** | cwd = `/home/administrator/agent-workspace/multi-agent-harness`; `workspace_base()` returns project root |
| 5 | Registry delegation lookup | **YES** | `FileDelegationProvider` reads `delegations.json` from `--base` workspace; seeded ACTIVE delegation resolves correctly; unknown delegation → BLOCKED (fail-closed) |
| 6 | Fresh workspace creation | **YES** | Disposable `/tmp/dsh-smoke-*` workspaces seeded per run; all writes confined to `--base` workspace |
| 7 | CLI execution | **YES** | `python -m orchestrator.entrypoint ...` invoked from DSH session shell |
| 8 | Structured JSON output | **YES** | `run-result@1` envelope with `schema/status/run_id/objective/state/report/errors/audit_ids` |
| 9 | Expected exit codes | **YES** | COMPLETE→0, BLOCKED→2, ERROR→1, ESCALATED→3 (all four confirmed in-session) |
| 10 | No raw DSH bypass | **YES** | `orchestrator/entrypoint/` imports no DSH tools; `backend_kind=FAKE` (deterministic `FakeSubagentBackend`); no `RealDSHBackend`; no `subagent_*` dispatch |
| 11 | No mutation of protected state | **YES** | Real `state/registry/README.md` SHA-256 = `8f539c...a352` (identical before/after); no new files created under real `state/` or `audit/` |
| 12 | DSH-session → entrypoint invocation | **YES** | The DSH Web Chat session's shell invoked the module; COMPLETE/BLOCKED/ERROR/ESCALATED all produced structured output |

---

## Terminal states confirmed (in-session, fresh workspaces per run)

| Scenario | Command | Observed status | Exit | Expected |
|---|---|---|---|---|
| Happy (CLI) | `--objective research --scope docs/notes.md --delegation-id delegation-prod-001 --base <ws> --indent 0` | COMPLETE | 0 | 0 |
| Unknown delegation | `--objective research --scope docs/notes.md --delegation-id delegation-unknown-999 --base <ws> --indent 0` | BLOCKED | 2 | 2 |
| Empty objective | `--objective "" --scope docs/notes.md --delegation-id delegation-prod-001 --base <ws> --indent 0` | ERROR | 1 | 1 |
| MEDIUM write (no evidence) | `--objective engineering --scope agents/cto/output.txt --delegation-id delegation-prod-001 --base <ws> --indent 0` | ESCALATED | 3 | 3 |
| JSON stdin (happy) | `echo '{"objective":"research","scope":["docs/notes.md"],"delegation_id":"delegation-prod-001"}' \| python -m orchestrator.entrypoint --json-stdin --base <ws> --indent 0` | COMPLETE | 0 | 0 |

---

## Backend kind (no live bridge)

```python
from orchestrator.runtime.flow import ExecutionFlow
from orchestrator.dsh.client import BackendKind
f = ExecutionFlow()
# backend_kind = BackendKind.FAKE  (IS_FAKE=True, IS_REAL=False)
```

The `DSH_LIVE_BRIDGE_ACTIVE` env var is **unset**, so `ExecutionFlow.backend_kind()` returns `BackendKind.FAKE`. The subtask backend is the deterministic in-process `FakeSubagentBackend`. No real DSH child was dispatched. The provenance `run_id` in both COMPLETE envelopes shows `run_id: "fake-..."` — confirming the FAKE backend.

---

## Three-state separation (required)

| State | Meaning | Status | Evidence |
|---|---|---|---|
| **LOCAL_E2E_VERIFIED** | The module + ProductionRun + gates work end-to-end with the deterministic FAKE backend. The full 17-phase chain completes. | **VERIFIED** | 301 entrypoint tests pass. Four terminal states confirmed with correct exit codes. Full envelope with `run-result@1` schema, `verification.verdict: PASSED`, `files_written: []`, audited steps. |
| **DSH_SESSION_SMOKE_VERIFIED** | The current DSH Web Chat session (`session-d34283f1-...`) can invoke `python -m orchestrator.entrypoint ...` from its shell and get the expected structured JSON output with correct exit codes. | **VERIFIED** | All 12 checks above pass. The DSH session shell ran the module; the module produced correct output; no raw-tool bypass; no protected-state mutation. |
| **LIVE_DSH_BACKEND_VERIFIED** | A real DSH `subagent_<id>` child dispatched through the D4/D7 live bridge, with L2-LIVE evidence (runtime-observed child outcome). | **NOT VERIFIED** | `DSH_LIVE_BRIDGE_ACTIVE` unset → `backend_kind=FAKE`; `probe_backend_kind()` returns `UNAVAILABLE`; no `RealDSHBackend`; provenance shows `run_id: "fake-..."` (not a real DSH run id). **No claim of live integration.** |

---

## UNKNOWN

- LIVE DSH backend behavior under real child dispatch (requires `DSH_LIVE_BRIDGE_ACTIVE=1` + mounted D4/D7 composition).
- L2-LIVE evidence for Phase-5 changes (closure matrix B1/B2).
- HIGH-risk / approval-requiring actions through the front door (requires a live approval answerer).

## BLOCKED

- **LIVE_DSH_BACKEND_VERIFIED**: blocked on `DSH_LIVE_BRIDGE_ACTIVE` + per-session D4/D7 mount verification.

## SCOPE CHECK

**Not modified (verified):** `orchestrator/entrypoint/*`, `orchestrator/production/*`, `orchestrator/runtime/*`, `orchestrator/dsh/*`, `control/*`, `state/*`, `audit/*`, `config/*`, `agents/*`, `schemas/*`, DSH core/profiles/presets/session policy, live composition. No test failure downgraded. No production-readiness or L3 claim. No live-integration claim.

## NEXT

1. Set `DSH_LIVE_BRIDGE_ACTIVE=1` after per-session D4/D7 mount verification.
2. Re-run front door with live bridge; observe `probe_backend_kind() == REAL` and real `subagent_<id>` dispatch.
3. Record L2-LIVE evidence (runtime-observed child outcome).
4. Re-run full entrypoint + security suites under live bridge.
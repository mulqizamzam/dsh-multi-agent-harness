# DSH Chat → ProductionRun — Smoke-Readiness Report (Session, In-Session)

- **Milestone**: Phase 5 — DSH CHAT → PRODUCTIONRUN SMOKE-READINESS
- **Status**: **ENTRYPOINT_USABLE_LOCALLY = VERIFIED** · **DSH_CHAT_E2E_VERIFIED = NOT VERIFIED** (live bridge prerequisites absent; no claim of live integration)
- **Date**: 2026-09-01 (in-session execution)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`; Python `3.14.4` (`/home/administrator/agent-workspace/multi-agent-harness/.venv-tests/bin/python`)
- **Under test**: `orchestrator/entrypoint/` (Front Door V1) · `orchestrator/production/*` · `orchestrator/runtime/flow.py` · gates via `orchestrator/runtime/gates.py` · `control/*` · `orchestrator/dsh/bridge.py` (backend probe) · `orchestrator/runtime/delegation.py` (`FileDelegationProvider`).
- **Write-only scope**: `docs/phase-5/entrypoint/smoke/` + `tests/orchestrator/entrypoint/smoke/`. **No front-door implementation change, no DSH modification, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim, no live-integration claim.**
- **Companion**: `docs/phase-5/entrypoint/0005-front-door-v1-local-e2e-execution-report.md` (prior local E2E) · `0004-milestone-report.md` · `0003-front-door-test-report.md` · `0002-front-door-security-review.md` · `0001-front-door-design.md` · `security/0002-front-door-execution-report.md` · `docs/phase-5/final/0005-final-security-gate-evidence.md` · `docs/phase-5/final/acceptance/0001-final-acceptance-matrix.md` (B1/B2 live bridge + approval) · `orchestrator/dsh/bridge.py` (probe) · `orchestrator/runtime/flow.py` (backend selection).

---

## 1. Question answered

> Can the **current DSH Web Chat session** invoke the exact front-door command
> `python -m orchestrator.entrypoint ...`?

**Answer (current session, executed in-session):**

| Check | Result | Evidence |
|---|---|---|
| 1. Shell availability | **YES** | `bash` and `python3` present (`/usr/bin/bash`, `/usr/bin/python3`); the DSH session exposes a working shell (`DSH_SHELL=1`). |
| 2. Project root resolution | **YES** | Command executed from `/home/administrator/agent-workspace/multi-agent-harness`; module resolves (cwd on `sys.path` via `python -m`; `entry.py` also inserts project root). |
| 3. Python environment | **YES** | `.venv-tests/bin/python` = Python 3.14.4; all required imports resolve (stdlib + project modules only). |
| 4. Module import | **YES** | `python -m orchestrator.entrypoint --help` → usage, exit 0. `entry.py`/`__main__.py` compile and import clean. |
| 5. Delegation registry accessibility | **YES** (read-only; requires a seeded registry) | `FileDelegationProvider` reads `state/registry/delegations.json` + `revocations.json` via `safe_read`. The **real** `state/registry/` currently holds only `README.md` (no `delegations.json`), so a run against the real project root would fail-closed (BLOCKED: no delegation). An invocation with `--base <seeded-workspace>` resolves the seeded ACTIVE delegation correctly. |
| 6. Temporary workspace viability | **YES** | `mktemp -d /tmp/frontdoor-smoke-*` → seeded `state/registry/`, `state/projects/`, `audit/`, `agents/cto`, `docs`; full run completed; workspace removed after. |
| 7. Expected JSON output | **YES** | `run-result@1` envelope on stdout with `schema/status/run_id/objective/state/report/errors/audit_ids`. All four terminal states observed (below). |
| 8. No direct DSH/raw-tool bypass | **YES** | `probe_backend_kind()` → `BackendKind.UNAVAILABLE` (no `DSH_LIVE_BRIDGE_ACTIVE`); the run used the deterministic `FakeSubagentBackend` (`run_id: "fake-…"`, `backend_kind=FAKE`). The front door imports no `orchestrator.dsh` client (AST/static checks in prior reports + re-verified). `Entrypoint` never constructs an `ExecutionFlow`/`ExecutionEngine`; `ProductionRun.run()` is the only execution path. |
| 9. No production side effect | **YES** | SHA-256 of the **real** `state/registry/README.md` identical before/after all runs (`8f539c…a352`). All runs wrote only to the scratch `--base` workspace, which was deleted. No real `state/registry/`, `state/projects/`, or `audit/` file touched. |

### 1.1 Terminal states observed in-session (exact command)

| # | Command (abridged, `--base <scratch-ws> --indent 0`) | Observed status | Exit | Expected |
|---|---|---|---|---|
| 1 | `--objective research --scope docs/notes.md --delegation-id delegation-prod-001` | **COMPLETE** | **0** | 0 |
| 2 | `--objective research --scope docs/notes.md --delegation-id delegation-unknown-999` | **BLOCKED** | **2** | 2 |
| 3 | `--objective "" --scope docs/notes.md --delegation-id delegation-prod-001` | **ERROR** | **1** | 1 |
| 4 | `--objective research --scope docs/notes.md --delegation-id i-am-a-human-grant` | **ERROR** | **1** | 1 (free-text delegation rejected, AUTH-INV-01) |

COMPLETE envelope showed the full 17-phase chain (intake → understand → classify → risk_gate → decompose → select → delegate → execute_subtasks → collect → evidence_gate → synthesize → conflict_gate → adversarial_review → authority_gate → execute → verify → close), `verification.verdict: PASSED`, `files_written: []`, `audit_ids` present. The BLOCKED/ERROR envelopes returned `run_id: null`/`state: null` where no run started (fail-closed).

---

## 2. Live bridge / D4/D7 status (current, re-verified in-session)

| Fact | Value | Evidence |
|---|---|---|
| `DSH_LIVE_BRIDGE_ACTIVE` | **UNSET** (not in env) | `env` probe |
| `probe_backend_kind()` | **`BackendKind.UNAVAILABLE`** | `orchestrator/dsh/bridge.py` live probe |
| Live D4/D7 mount | **not active** in this process | `check_instance_mounted` requires the marker env |
| Subtask backend used by the front door | **`FakeSubagentBackend`** (deterministic dry-run, `BackendKind.FAKE`) | observed `run_id: "fake-…"` in COMPLETE provenance; `flow.py` backend selection |
| Real DSH child dispatch | **not exercised** | no marker → no `RealDSHBackend`; fail-closed `BridgeNotAvailable` if a REAL run were requested |

**Consequence:** the command is **locally usable** from this DSH session (shell → CLI → ProductionRun → FAKE backend → JSON envelope), but the **DSH Chat → ProductionRun live integration** (real DSH child dispatch through the D4/D7 bridge) is **not verifiable** in this environment: the live-bridge prerequisite (`DSH_LIVE_BRIDGE_ACTIVE` + mounted composition) is absent, and the L2-LIVE proof for Phase-5 changes remains BLOCKED (closure matrix B1/B2, `final/0005`).

---

## 3. Distinction (required by task)

| Label | Meaning | Status |
|---|---|---|
| **ENTRYPOINT_USABLE_LOCALLY** | The exact command `python -m orchestrator.entrypoint ...` can be invoked from the current DSH session shell and produces the expected JSON envelope with all four terminal states, correct exit codes, no registry mutation, no raw-tool bypass, and no production side effect — using the deterministic FAKE subtask backend. | **VERIFIED** (this session, in-session execution) |
| **DSH_CHAT_E2E_VERIFIED** | The full DSH Chat → ProductionRun **live** integration — a real DSH `subagent_<id>` child dispatched through the D4/D7 live bridge, with L2-LIVE evidence — has been observed. | **NOT VERIFIED** — live bridge prerequisites absent (`DSH_LIVE_BRIDGE_ACTIVE` unset, `probe_backend_kind() == UNAVAILABLE`); no real DSH child was dispatched; **no live-integration claim is made.** |

---

## 4. What would be required to reach DSH_CHAT_E2E_VERIFIED

1. D4/D7 composition mounted for the session and `DSH_LIVE_BRIDGE_ACTIVE=1` set (closure matrix A1/A2; `final/0005` §7).
2. Re-run the front-door command with the live bridge; observe `probe_backend_kind() == REAL` and a real `subagent_<id>` dispatch (provenance with a real run id, not `fake-…`).
3. Record L2-LIVE evidence (runtime-observed child outcome) and re-run the full entrypoint + security suites under the live bridge.
4. Until then, any COMPLETE produced locally is a **FAKE-backend deterministic dry-run**, not live integration evidence.

---

## 5. Honesty statement

1. **No live-integration claim.** DSH_CHAT_E2E_VERIFIED is NOT claimed: the live bridge is absent and no real DSH child was dispatched. The front-door command is verified **locally usable** from this session only.
2. **No front-door implementation change.** `orchestrator/entrypoint/` is unmodified; no DSH/core/config/role/control/orchestrator/state/audit change; no live composition change.
3. **No production side effect.** All runs used throwaway `--base` scratch workspaces under `/tmp`, deleted after capture; the real registry hash is identical before/after.
4. **No raw-tool bypass observed.** The front door does not import or call DSH tools; the subtask backend was the deterministic FAKE backend, and a REAL run was never requested (so no `BridgeNotAvailable` path was triggered).
5. **No test failure hidden.** All observed statuses/exit codes match the documented contract (COMPLETE→0, BLOCKED→2, ESCALATED→3, ERROR→1; ESCALATED not re-triggered this session — already proven in `0005`).
6. **Delegation registry honesty.** The real `state/registry/` is unseeded (README only); a run without `--base` would fail-closed. The smoke used a seeded scratch registry, which is the documented correct usage (`0005` §2).
7. **ESCALATED state** was not re-executed in this session (evidence gate requires a MEDIUM write objective; already proven in `docs/phase-5/entrypoint/0005` §3.4). It is reported as prior-proven, not re-claimed.

---

## 6. Scope check

**In scope (written this session):** `docs/phase-5/entrypoint/smoke/0001-dsh-chat-productionrun-smoke-readiness.md` (this file) + `tests/orchestrator/entrypoint/smoke/test_smoke_readiness.py`.

**Not modified (verified):** `orchestrator/entrypoint/`, `orchestrator/production/*`, `orchestrator/runtime/*`, `orchestrator/dsh/*`, `orchestrator/execution/*`, `orchestrator/foundation/*`, `control/*`, `state/*`, `audit/*`, `config/*`, `agents/*`, `schemas/*`, DSH core/profiles/presets/session policy, live composition `$DSH_HOME/profiles/web/cordis.patch.yml`, all pre-existing `tests/`, all other `docs/`.

---

*Status: SMOKE-READINESS. ENTRYPOINT_USABLE_LOCALLY = VERIFIED (in-session: shell ✓, root resolution ✓, Python ✓, module import ✓, seeded-registry resolution ✓, temp workspace ✓, JSON envelope ✓, no raw-tool bypass ✓, no production side effect ✓; COMPLETE/BLOCKED/ERROR all observed with correct exit codes). DSH_CHAT_E2E_VERIFIED = NOT VERIFIED (live bridge absent: DSH_LIVE_BRIDGE_ACTIVE unset, probe_backend_kind()=UNAVAILABLE, FAKE backend used, no real DSH child dispatched). No live-integration claim. No front-door implementation change. No closure claim.*

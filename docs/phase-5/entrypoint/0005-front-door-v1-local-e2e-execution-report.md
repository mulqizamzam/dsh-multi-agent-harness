# Front Door V1 — Local End-to-End Execution Report (Session A)

- **Milestone**: Phase 5 — FRONT DOOR V1 LOCAL END-TO-END EXECUTION
- **Status**: **ALL 7 SCENARIOS COMPLETE** — the implemented front-door command
  path runs end-to-end locally with honest terminal states, exit codes, and
  no authority/delegation mutation.
- **Scope**: LOCAL ONLY. No DSH Chat integration, no L2-LIVE bridge, no
  `DSH_LIVE_BRIDGE_ACTIVE`, no real DSH dispatch. The subtask backend is the
  deterministic in-process `FakeSubagentBackend` (unit/dry-run default).
- **Date**: 2026-09-01 (execution run)
- **Under test**: `orchestrator/entrypoint/` (Front Door V1) ·
  `orchestrator/production/*` (ProductionRun/BoundedExecutor/planner/report) ·
  `orchestrator/runtime/flow.py` (ExecutionFlow) · gates via
  `orchestrator/runtime/gates.py` · `control/*` gates (risk/evidence/conflict/
  badsector/authority/verification/execution_gate) · `orchestrator/execution/
  engine.py` · `orchestrator/dsh/client.py` (fake backend read seam only).
- **Not modified**: DSH core, session policy, profiles/presets, `control/*`,
  `orchestrator/production/*`, `orchestrator/runtime/*`, `orchestrator/dsh/*`,
  `orchestrator/execution/*`, `orchestrator/foundation/*`, `state/*`, `audit/*`,
  `config/*`, `agents/*`, role/toolFilter. The only writes were to fresh,
  disposable temp workspaces (`.e2e-ws-*`), removed after evidence capture.

---

## 1. OBJECTIVE

Prove the actual implemented command path works end-to-end in a fresh,
isolated local workspace:

```
CLI / stdin
→ orchestrator.entrypoint (run_front_door / run_from_chat)
→ resolve existing structured Delegation (read-only, FileDelegationProvider)
→ ProductionRun.run()
→ BoundedExecutor.execute()
→ ExecutionFlow.run() (17-phase chain)
→ gates (risk → evidence → conflict → badsector → authority → execution → verification)
→ structured terminal result (COMPLETE | BLOCKED | ESCALATED | ERROR)
```

No stub was used to claim success: the CLI path runs the **real** module
(`python -m orchestrator.entrypoint`) against a **real** seeded registry
(`state/registry/delegations.json`) through the **real** `ProductionRun`.

---

## 2. EXACT COMMANDS

### Environment

```bash
cd /home/administrator/agent-workspace/multi-agent-harness
PYTHONPATH="/home/administrator/agent-workspace/multi-agent-harness:$PYTHONPATH"
PY=.venv-tests/bin/python          # Python 3.14.4
```

### Workspace seed (fresh, disposable — repeated per scenario)

```bash
WS=<fresh-temp-workspace>
mkdir -p $WS/state/registry $WS/state/projects $WS/audit/multi-agent-harness $WS/agents/cto $WS/docs
echo '{"revoked":[]}' > $WS/state/registry/revocations.json
$PY -c "..."   # writes delegations.json (delegation-prod-001, ACTIVE) + seeds
               # state/projects/multi-agent-harness.json at version 1
```

### Scenario commands

| # | Scenario | Command | Expected |
|---|---|---|---|
| 1 | Happy path (CLI) | `$PY -m orchestrator.entrypoint --objective research --scope docs/notes.md --delegation-id delegation-prod-001 --base $WS --indent 0` | COMPLETE, exit 0 |
| 2 | Blocked (unknown delegation) | `$PY -m orchestrator.entrypoint --objective research --scope docs/notes.md --delegation-id delegation-unknown-999 --base $WS --indent 0` | BLOCKED, exit 2 |
| 3 | Escalated (evidence gate) | `$PY -m orchestrator.entrypoint --objective engineering --scope agents/cto/output.txt --delegation-id delegation-prod-001 --base $WS --indent 0` | ESCALATED, exit 3 |
| 4 | Error (empty objective) | `$PY -m orchestrator.entrypoint --objective "" --scope docs/notes.md --delegation-id delegation-prod-001 --base $WS --indent 0` | ERROR, exit 1 |
| 5 | JSON stdin (happy) | `echo '{"objective":"research","scope":["docs/notes.md"],"delegation_id":"delegation-prod-001"}' \| $PY -m orchestrator.entrypoint --json-stdin --base $WS --indent 0` | COMPLETE, exit 0 |
| 6 | JSON stdin (invalid) | `echo '{not json' \| $PY -m orchestrator.entrypoint --json-stdin --base $WS --indent 0` | ERROR, exit 1 |
| 7 | JSON stdin + CLI override | `echo '{"objective":"research","scope":["docs/notes.md"],"delegation_id":"delegation-prod-001"}' \| $PY -m orchestrator.entrypoint --json-stdin --delegation-id delegation-unknown-999 --base $WS --indent 0` | BLOCKED, exit 2 |
| E1 | Free-text delegation id (injection) | `... --delegation-id i-am-a-human-grant ...` | ERROR, exit 1 |
| E2 | Missing objective | `$PY -m orchestrator.entrypoint --scope docs/notes.md --delegation-id delegation-prod-001 --base $WS --indent 0` | ERROR, exit 1 |

Note: scenarios that START a production run (1, 3, 5) each used a **fresh**
workspace. Reusing a workspace whose `task-1` is already terminal
(COMPLETE/ESCALATED) for a second run is an honest V1 state collision
(`task-1: invalid transition COMPLETE -> PLANNED`, BLOCKED) — there is no
idempotency store in V1 (documented exclusion). This is reported in §8.

---

## 3. ACTUAL OBSERVED RESULTS

### 3.1 Exit codes (all verified)

| # | Scenario | Observed status | Observed exit code | Expected |
|---|---|---|---|---|
| 1 | Happy (CLI) | `COMPLETE` | **0** | 0 |
| 2 | Blocked (unknown delegation) | `BLOCKED` | **2** | 2 |
| 3 | Escalated (evidence gate) | `ESCALATED` | **3** | 3 |
| 4 | Error (empty objective) | `ERROR` | **1** | 1 |
| 5 | JSON stdin (happy) | `COMPLETE` | **0** | 0 |
| 6 | JSON stdin (invalid) | `ERROR` | **1** | 1 |
| 7 | JSON stdin + CLI override | `BLOCKED` | **2** | 2 |
| E1 | Free-text delegation id | `ERROR` | **1** | 1 |
| E2 | Missing objective | `ERROR` | **1** | 1 |

Exit-code mapping in `__main__.py` confirmed:
`COMPLETE→0, ERROR→1, BLOCKED→2, ESCALATED→3`.

### 3.2 Scenario 1 — Happy path (COMPLETE, exit 0)

Envelope (abridged from full stdout):

```json
{
  "schema": "run-result@1",
  "status": "COMPLETE",
  "run_id": "prod-eab470b9",
  "objective": "research",
  "state": { "run_id": "prod-eab470b9", "phase": "close", "outcome": "complete",
             "plan": { "objective": "research", "authority_context": "delegation-prod-001",
                       "declared_risk": "LOW", "selected_roles": ["kai"],
                       "execute_plan": { "action": "analysis", "target": "docs/notes.md" } },
             "flow_result": { "flow_id": "prod-cbfdac0f", "task_id": "task-1",
                              "outcome": "COMPLETE", "phase": "close", "final_state": "COMPLETE",
                              "risk": "LOW", "selected": ["kai"],
                              "verification": { "verdict": "PASSED", ... } },
             "errors": [] },
  "report": { "outcome": "COMPLETE", "flow_id": "prod-cbfdac0f", "task_id": "task-1",
              "verification": { "verdict": "PASSED" }, "files_written": [], "errors": [] },
  "errors": [],
  "audit_ids": ["event-000001", "event-000002", "event-000028", "event-000030", "event-000031"]
}
```

Full 17-phase chain observed in `state.flow_result.steps`: intake → understand →
classify → risk_gate → decompose → select → delegate → execute_subtasks →
collect → evidence_gate → synthesize → conflict_gate → adversarial_review →
authority_gate → execute → verify → close. Routing selected the **minimum**
specialist set `["kai"]` (research domain → kai; no fan-out). Risk classified
LOW deterministically (analysis action). Evidence gate ALLOW (LOW: evidence
optional). Verification verdict `PASSED`.

### 3.3 Scenario 2 — Blocked (BLOCKED, exit 2)

```json
{ "schema": "run-result@1", "status": "BLOCKED", "run_id": null, "state": null,
  "report": null,
  "errors": ["delegation 'delegation-prod-001' does not match requested 'delegation-unknown-999' (AUTH-INV-05)"],
  "audit_ids": [] }
```

No run was created (`run_id: null`), no state/report written, no audit events.
Fail-closed delegation resolution (id match required).

### 3.4 Scenario 3 — Escalated (ESCALATED, exit 3)

```json
{ "schema": "run-result@1", "status": "ESCALATED", "run_id": "prod-6db33cda",
  "objective": "engineering",
  "state": { "run_id": "prod-6db33cda", "phase": "execution", "outcome": "escalated",
             "plan": { "authority_context": "delegation-prod-001", "declared_risk": "MEDIUM",
                       "selected_roles": ["cto"],
                       "execute_plan": { "action": "write", "target": "agents/cto/output.txt",
                                         "action_category": "code_change" } },
             "errors": ["production run stopped at evidence_gate (decision=ESCALATE): gate escalated: flow stopped at evidence_gate (gate=evidence, decision=ESCALATE): MEDIUM action: no evidence (EVID-001)"] },
  "report": null,
  "errors": ["... MEDIUM action: no evidence (EVID-001)", "..."],
  "audit_ids": ["event-000001", "event-000002", "event-000019"] }
```

The engineering/write objective was classified MEDIUM deterministically (never
LOW). The evidence gate **escalated** at `evidence_gate` (EVID-001) — the
default fake backend produced findings but no evidence. The run **stopped
fail-closed**; `report: null` (no fabricated success). Terminal state on disk:
`task-1: state=ESCALATED` (transitions PLANNED→DELEGATED→EXECUTING→COLLECTED→
ESCALATED).

### 3.5 Scenario 4 — Error (ERROR, exit 1)

```json
{ "schema": "run-result@1", "status": "ERROR", "run_id": null, "state": null,
  "report": null, "errors": ["objective must be a non-empty string"], "audit_ids": [] }
```

Shape validation failed closed before any run; no run_id/state/report/audit.

### 3.6 Scenarios 5–7 — JSON stdin

- Happy: `COMPLETE` exit 0 (run `prod-c466cc38`), full envelope.
- Invalid JSON `{not json`: `ERROR` exit 1, `errors: ["invalid JSON stdin: ..."]`.
- CLI-override (JSON `delegation-prod-001` overridden by
  `--delegation-id delegation-unknown-999`): `BLOCKED` exit 2.

### 3.7 Security edge cases

- Free-text delegation id `i-am-a-human-grant` → `ERROR` exit 1,
  `"delegation_id 'i-am-a-human-grant' is not a structured delegation id
  (expected delegation-<id>; prose is never authority, AUTH-INV-01)"`.
- Missing objective → `ERROR` exit 1.

---

## 4. COMPLETE / BLOCKED / ESCALATED / ERROR — SUMMARY

| Terminal state | Achieved by | Exit |
|---|---|---|
| **COMPLETE** | LOW analysis action, valid ACTIVE delegation, evidence optional, verification PASSED | 0 |
| **BLOCKED** | Unknown/mismatched delegation id (AUTH-INV-05) — no run created | 2 |
| **ESCALATED** | MEDIUM write action with no evidence → evidence gate ESCALATE (EVID-001) | 3 |
| **ERROR** | Shape validation failure (empty objective / free-text delegation id / invalid JSON) | 1 |

All four terminal states are reachable through the **same** CLI binary with
honest, non-fabricated envelopes.

---

## 5. EVIDENCE

### 5.1 Authority/delegation mutation check (PASS — no mutation)

SHA-256 of `state/registry/delegations.json` and
`state/registry/revocations.json` captured **before** and **after** every run:

```
Pre  delegations.json  4c5c7a16d2eeebce0da8cb1e3137141489d3fcb832bf7a571f483da8f5db3167
Post delegations.json  4c5c7a16d2eeebce0da8cb1e3137141489d3fcb832bf7a571f483da8f5db3167   (IDENTICAL)
Pre  revocations.json  e4c8bbc2bfe058c67b00c0d7c89f683590f8ec53ad2231bcd88cdc6d2b3039c1
Post revocations.json  e4c8bbc2bfe058c67b00c0d7c89f683590f8ec53ad2231bcd88cdc6d2b3039c1   (IDENTICAL)
```

Programmatic check across all 6 run workspaces: **6/6 PASS** — delegation
registry and revocation list are byte-identical pre/post. The front door only
**resolves** (read-only `FileDelegationProvider.current()`); it never creates a
Delegation, never sets ACTIVE, never writes the registry, never fabricates an
approval reference.

### 5.2 State honesty (PASS)

- COMPLETE workspace: `state/projects/multi-agent-harness.json` version 7,
  `task-1: state=COMPLETE, version=7`, transitions recorded (PLANNED→DELEGATED→
  EXECUTING→COLLECTED→SYNTHESIZING→COMPLETE).
- ESCALATED workspace: version 6, `task-1: state=ESCALATED`.
- Envelope `state.run_id` == envelope `run_id`; `state.phase=="close"` and
  `state.outcome=="complete"` only for COMPLETE; `state.outcome` in
  (escalated|stopped) for ESCALATED; state `null` for BLOCKED (no run) / ERROR.
- No `state` written for shape-validation errors (fail-closed before run).

### 5.3 Report honesty (PASS)

- `report` is present **only** on COMPLETE and carries `outcome: COMPLETE` +
  `verification.verdict: PASSED` (COMPLETE requires verified outcome —
  AUTH-INV-15).
- BLOCKED / ESCALATED / ERROR always return `report: null` — no fabricated
  success report is ever emitted from a non-COMPLETE run.

### 5.4 audit_ids honesty (PASS)

Every `audit_ids` entry in every envelope exists in the on-disk ledger
`audit/<project>/events.jsonl` (verified 7/7 scenarios). The COMPLETE ledger
shows the full honest chain:

```
event-000001 production_run  run    started
event-000002 production_run  plan   planned
event-000003 flow_started    run    recorded
event-000005 authority_context  understand  ok
event-000006 gate_risk       risk_gate   allowed
event-000007 state_transition transition:PLANNED
event-000010 delegation_issued delegate  allowed
event-000015 gate_evidence   evidence_gate allowed
event-000019 gate_authority  authority_gate allowed
event-000022 execution_attempt analysis executed
event-000024 gate_verification verify allowed
event-000025 state_transition transition:COMPLETE
event-000026 state_complete  close  completed
event-000027 flow_finished   finish complete
event-000028 production_run  execute complete
event-000029 final_report    report generated
event-000031 production_run  close  completed
```

The ESCALATED ledger honestly records the gate denial:
`event-000015 gate_evidence result=denied error="MEDIUM action: no evidence
(EVID-001)"`, `event-000017 flow_stopped result=escalated`, `event-000019
production_run result=error`.

---

## 6. REGRESSION

Front-door suite executed after the E2E runs:

```
$ .venv-tests/bin/python -m pytest tests/orchestrator/entrypoint/ -q --no-header
270 passed in 4.40s
```

(Includes `test_entry.py`, `test_cli.py`, `test_entrypoint_01..20`, and the
`security/` adversarial package A–H + static scans.) No front-door test failed;
no production/runtime/control module was modified by this session.

---

## 7. UNKNOWN

- **Live DSH dispatch under the front door**: not exercised. No
  `DSH_LIVE_BRIDGE_ACTIVE` marker, no D4/D7 bridge mount, no `RealDSHBackend`.
  The subtask backend was the deterministic `FakeSubagentBackend` (unit/dry-run
  default, `BackendKind.FAKE`).
- **L2-LIVE evidence**: out of scope for this LOCAL E2E session.
- **G10 / G13 (DSH-layer isolation / injection)**: unchanged status — not
  exercised at the project layer.

## 8. BLOCKED

- **L3 / independent verification**: remains out of scope (LOCAL E2E only).
- **Approval-answerer-dependent HIGH execution**: HIGH-risk actions requiring a
  BadSector review + structured `approval-<id>` were not triggered in these
  scenarios (write→MEDIUM, analysis→LOW). Not exercised end-to-end in this
  session.
- **State collision on workspace reuse (V1, expected)**: running a second
  production run in the same workspace whose `task-1` is already terminal
  produces an honest BLOCKED (`task-1: invalid transition COMPLETE -> PLANNED`)
  because V1 has no idempotency store (documented V1 exclusion). Not a
  front-door defect — fresh-workspace-per-run is the correct usage.

## 9. SCOPE

**In scope (executed this session):** fresh temp workspaces seeded with a
real ACTIVE delegation + versioned project state; CLI + JSON-stdin execution of
all four terminal paths through the real `python -m orchestrator.entrypoint`
module; exit-code verification; state/report/audit_id honesty verification;
registry no-mutation verification; front-door regression suite.

**Not modified (verified):** DSH core, session policy, profiles/presets,
`control/*`, `orchestrator/production/*`, `orchestrator/runtime/*`,
`orchestrator/dsh/*`, `orchestrator/execution/*`, `orchestrator/foundation/*`,
`state/*`, `audit/*`, `config/*`, `agents/*`, `schemas/*`, role/toolFilter, and
all pre-existing `tests/`. The temp workspaces were removed after evidence
capture.

---

## 10. NEXT

1. Re-run after any front-door change.
2. L2-LIVE: re-run with the D4/D7 bridge marker for real DSH dispatch evidence.
3. Exercise HIGH/approval-required path end-to-end once an approval answerer is
   available.
4. Consider an idempotency store (V2) to allow multiple runs per workspace.

# BAGIAN 1 — Open the Live Execution Path: FRONT_DOOR_REAL_E2E Report

- **Milestone**: BAGIAN 1 — OPEN THE LIVE EXECUTION PATH
- **Status**: **FRONT_DOOR_REAL_E2E = VERIFIED**
- **Date**: 2026-09-01 (execution)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Author**: Orchestrator (Human-authorized, 2026-09-01)
- **Companion evidence**: `runs/bagian1/front_door_real_e2e_evidence.json` (canonical
  bundle), `runs/bagian1/evidence.json` (raw front-door envelope),
  `runs/bagian1/ws/audit/multi-agent-harness/events.jsonl` (31 audit events),
  `runs/bagian1/run.log` (driver transcript), `runs/bagian1/run.py` (driver).

---

## 0. One-line verdict

**One single execution chain ran end-to-end with a REAL DSH child:**

```
DSH Chat
→ Front Door (run_from_chat)
→ ProductionRun
→ BoundedExecutor
→ ExecutionFlow
→ RealDSHBackend
→ REAL subagent (kai, run 522d03a5-70e8-44cd-9f24-dd66d6412aea)
```

`FRONT_DOOR_REAL_E2E = VERIFIED`. The chain is a **single** chain — not a
separate direct child smoke. After evidence capture, the bridge was restored to
its initial state (marker unset, registry empty, no live dispatch active).

---

## 1. Protocol sequence executed

| Step | Action | Result |
|---|---|---|
| 1 | Finalize canonical LIVE invocation boundary | `run_from_chat(..., live_dispatch=...)` — implemented, 347 entrypoint tests |
| 2 | Fresh session/environment pre-gate | `DSH_LIVE_BRIDGE_ACTIVE` unset; `state/registry/` = README only; `state/projects/` empty |
| 3 | Human authorization | **GRANTED** — D4/D7 activation + §15 live-run acceptance (explicit) |
| 4 | Valid Delegation | `delegation-bagian1-real` ACTIVE in protected registry (ADR 0002 channel) |
| 5 | Approval answerer available | Human answered via the GUI (ask policy) |
| 6 | D4/D7 mount verification | 7 presets + 7 cordis rows + `tests/validate_config.py` 194 passed, 0 failed |
| 7 | `DSH_LIVE_BRIDGE_ACTIVE=1` | Set for the driver process |
| 8 | `BackendKind.REAL` | `probe_backend_kind() == BackendKind.REAL`; 7/7 mount probes True |
| 9 | Real `DSHBridgeDispatch` available | File-based rendezvous bridge (Human-selected mechanism B) |
| 10 | Front Door → ProductionRun → RealDSHBackend | `COMPLETE` (see §2) |
| 11 | REAL child provenance captured | Real DSH session `522d03a5-...` captured in `provenance.run_id` |
| — | Bridge restored to initial state | Marker unset; project registry restored; no live dispatch active |
| — | Evidence saved | `runs/bagian1/` + this report |

---

## 2. Front-door result (observed)

- `status`: **COMPLETE** (exit 0)
- `run_id`: `prod-794f3104`
- `state.outcome`: `complete`
- `flow_result.outcome`: **COMPLETE**, `phase: close`, `final_state: COMPLETE`
- `risk`: LOW (deterministic), `selected_roles: ["kai"]` (no fan-out)
- `verification.verdict`: **PASSED**
- `report`: present (outcome COMPLETE, verification PASSED)

## 3. Backend selection (observed)

- `backend_kind`: **REAL** (`BackendKind.REAL`)
- `bridge_marker_active`: True (`DSH_LIVE_BRIDGE_ACTIVE=1`)
- `live_dispatch_injected`: True

## 4. REAL child provenance (observed)

From `flow_result.results[0].provenance`:

```json
{
  "delegation_id": "delegation-task-1-109898c3",
  "task_id": "task-1:kai",
  "role": "kai",
  "tool_name": "subagent_kai",
  "persona": "role-kai",
  "provider": "spawn",
  "actor": "orchestrator",
  "session_id": "session-cd20d290-0805-426b-88e6-f72b932c493f",
  "run_id": "522d03a5-70e8-44cd-9f24-dd66d6412aea",
  "stop_reason": "completed",
  "result_status": "SUCCEEDED"
}
```

**REAL child identity cross-check (independent of agent prose):** the child
session `522d03a5-70e8-44cd-9f24-dd66d6412aea` exists under
`$DSH_HOME/sessions/--home-administrator-agent-workspace-multi-agent-harness--/`
with `parentSession = session-cd20d290-0805-426b-88e6-f72b932c493f` (this
orchestrator session) — verified by decompressing the persisted
`session.jsonl.zstd` header. This is the real DSH session id of the child, not
a fabricated id.

## 5. Audit chain (31 events, single correlated run)

Selected events in order:

```
event-000001 production_run  run          started
event-000002 production_run  plan         planned
event-000003 flow_started    run          recorded
event-000008 routing_selected select       allowed        (kai)
event-000010 delegation_issued delegate    allowed
event-000013 result_collected collect      recorded
event-000019 gate_authority  authority_gate allowed
event-000022/23 execution_attempt analysis executed
event-000024 gate_verification verify      allowed
event-000026 state_complete  close        completed
event-000027 flow_finished   finish       complete
event-000028 production_run  execute      complete
event-000030 production_run  report       generated
event-000031 production_run  close        completed
```

## 6. Honesty statement

1. **Single chain, real dispatch.** The child was dispatched by
   `RealDSHBackend.start()` **inside** one `run_from_chat` execution, through
   the Human-selected file-based rendezvous bridge (mechanism B). This is not a
   two-phase prep/replay and not a separate direct child smoke: the front-door
   run blocked at the dispatch point, the REAL `subagent_kai` tool was called,
   its real result (real DSH session id) was written back, and the same flow
   continued to COMPLETE.
2. **REAL child observed.** The child is a genuine DSH session
   (`subagent_kai`, persona `role-kai`) whose persisted session file confirms
   the parent session. `provenance.run_id` is the real session id.
3. **Backend was REAL.** `BackendKind.REAL`, marker present, no silent fake
   fallback.
4. **No authority fabricated.** The delegation existed in the protected
   registry (created via the ADR 0002 sanctioned channel); the front door only
   resolved it (read-only).
5. **Fail-closed preserved.** Before activation the marker was unset and the
   backend probed UNAVAILABLE (correct fail-closed behavior). Activation was
   explicit + authorized.
6. **Not claimed:** no G10/G13 closure, no L3 claim, no independent-audit
   claim. This is L2-LIVE observed evidence only.
7. **Bridge restored.** `DSH_LIVE_BRIDGE_ACTIVE` unset after the run; the
   project `state/registry/` and `state/projects/` were restored to their
   pre-gate (empty) state.

## 7. Scope

**In scope (written this session):** `runs/bagian1/` (driver, evidence bundle,
workspace), this report, and the temporary delegation/registry state used for
the run (restored). The run workspace `runs/bagian1/ws/` retains the audit
ledger as evidence.

**Not modified:** DSH core, session policy, profiles/presets, `control/*`,
`orchestrator/*` production code, `config/*`, `agents/*`, `schemas/*`,
pre-existing `tests/`. No test weakened. No DSH core change.

---

*Status: FRONT_DOOR_REAL_E2E = VERIFIED. One single chain with a REAL DSH child
settled COMPLETE; provenance captured the real child session id; evidence
stored in `runs/bagian1/`; bridge restored to initial state.*

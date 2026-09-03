# SCN-110 — Successful Bounded Autonomous Workflow (bounded)

- **Id**: `SCN-110`
- **Runbook**: — (happy path; no runbook)
- **PRD §17 skeleton**: #1 (simple research) / #2 (code change with test evidence)
- **Anchors**: AUTH-INV-05/15/20 · VERIFY-001..003 · REC-* (none — success path)
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestSuccessfulBoundedWorkflow`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- A valid, ACTIVE delegation covering the planned action, target, and environment.
- Sub-cases:
  - `SCN-110a` **single specialist**: engineering objective → routes to CTO → subtask returns SUCCEEDED with evidence → all gates ALLOW → execution writes the target → verification PASSED → COMPLETE.
  - `SCN-110b` **parallel specialists**: pricing objective → routes to CFO + Kai (minimum set of two) → both subtasks SUCCEEDED → evidence gate passes (no material conflict) → execution writes → COMPLETE. Proves the flow can route to the minimum set and run subtasks concurrently (in-process parallelism).
  - `SCN-110c` **bounded autonomy**: the flow reaches COMPLETE **without Human intervention** within the granted delegation scope; the delegation is NOT expired/revoked, scope is NOT exceeded, and no gate requires escalation. Autonomy is *bounded* by the delegation, not unlimited.

## Objective

Prove that the full Phase-4 runtime flow runs to COMPLETE with all gates ALLOW, verification PASSED, the consequential write landing through the execution gate, and the task state machine reaching `COMPLETE`. This is the **successful bounded autonomous workflow** — the orchestrator works autonomously within the explicit delegation bounds.

## Actors

- **orchestrator** — drives the full flow.
- **cto** (110a) or **cfo + kai** (110b) — routed specialist(s) (deterministic runner).
- **Human** is **not** required during the autonomous flow: the delegation is sufficient, no gate escalates, no recovery is entered. Human authority is the *source* of the delegation but not a participant in the flow.

## Expected state

- `FlowResult.outcome` → `COMPLETE`.
- `final_state` → `COMPLETE`.
- `version` is incremented (state machine transitions advance the version through the CAS persist).
- `phase` → `close`.

## Expected gates

All gates ALLOW:

- `risk` → ALLOW (LOW/MEDIUM risk; no intrinsic downgrade).
- `evidence` → ALLOW (LOW risk optional; MEDIUM/HIGH with sufficient evidence).
- `conflict` → ALLOW (no material conflict; both sides agree or only one specialist).
- `badsector_review` → ALLOW (not mandatory for LOW/MEDIUM risk; or PASS with provenance).
- `authority` → ALLOW (planning and execution-time re-check both pass).
- `execution` → ALLOW (target is not protected/outside/malformed).
- `verification` → ALLOW (expected outcome matches observed outcome).
- `recovery` → not entered (no failure).

## Expected execution

- The target file is written through the execution gate (`write_through`).
- The file is at the expected path, present, and recorded in `FlowResult.files_written`.
- For 110b, both subtasks are collected and the parallel batch is safety-proven (`assert_parallel_safe` → `safe: true`).

## Expected verification

- `verification.verdict` → `PASSED` (or `ALLOW`).
- COMPLETE is reached only after a PASSED verification (AUTH-INV-15).
- Evidence kinds for the action category are attached (`_attach_evidence`; VERIFY-003).

## Expected failure / recovery

- **No failure or recovery** in the success path. The flow is terminal at COMPLETE.
- Audit events cover the full lifecycle (18+ classes: `flow_started`, `gate_risk`, `gate_evidence`, `gate_conflict`, `gate_review`, `gate_authority`, `state_complete`, `flow_finished`, etc.).
- The result is deterministic and JSON-serializable.

## Evidence requirements

- `FlowResult.to_dict()` is JSON-serializable and shows `outcome == "COMPLETE"`, `phase == "close"`, `final_state == "COMPLETE"`, `gates` all ALLOW, `verification.verdict == "PASSED"`, `files_written` includes the target.
- Audit lifecycle: all expected event classes present with no `execution_denial` or `recovery_state_transition` events.
- Target file on disk at the expected path.
- For 110b: `result.selected` contains both roles; `results` length == 2; `parallel.safe == true`; `version` preserved across the batch.
- Determinism: two runs with identical inputs produce identical `FlowResult.to_dict()` (modulo timestamps and event ids).

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*
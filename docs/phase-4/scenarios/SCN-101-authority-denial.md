# SCN-101 — Authority Denial (bounded)

- **Id**: `SCN-101`
- **Runbook**: `docs/runbooks/01-authority-denial.md`
- **PRD §17 skeleton**: #10 — Unauthorized destructive request → DENY
- **Anchors**: AUTH-INV-01/04/05/11/18/20 · THREAT-001/008/020 · EVID-* (evidence not consulted on authority failure)
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestAuthorityDenial`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- A workspace with `state/registry/`, `state/projects/`, `audit/`, and a writable target dir (`agents/cto/`) exists.
- A delegation record exists **or** is absent, depending on the sub-case:
  - `SCN-101a` missing delegation: no delegation for the required authority context.
  - `SCN-101b` scope denial: delegation grants `read` only; the plan's action is `write`.
  - `SCN-101c` target denial: delegation grants resources `docs/**` only; the plan's target is `agents/cto/…`.
  - `SCN-101d` model-text authority: a claim like `"Human approved"` / `{"approved": true}` is never accepted as structured authority.
- No active delegation may be presumed; every denial is fail-closed (AUTH-INV-20).

## Objective

Prove that an **authority denial stops the flow fail-closed**: no planning-to-execution continuation, no consequential mutation, an audited denial, and a terminal disposition that is **not** COMPLETE.

## Actors

- **orchestrator** — drives the flow (intake → authority gate → execute).
- **cto** — routed specialist (subtask result supplied by the deterministic runner).
- **Human** — implicit authority owner; the denial escalates toward Human rather than self-escalating.

## Expected state

- `FlowResult.outcome`:
  - `SCN-101a` (missing delegation) → `ESCALATED` (intake not actionable without authority).
  - `SCN-101b/c` (scope/target denial) → `BLOCKED`.
- `final_state` is never `COMPLETE`; the task state machine does not reach COMPLETE.
- `version` unchanged by the denied action (no state document written past the denial).

## Expected gates

- `authority` gate → `DENY` for 101b/101c (reason names `AUTH-INV-04/18` for scope, `AUTH-INV-11` for target).
- `risk` gate may ALLOW (risk classification is orthogonal); the authority gate is the stopping point.
- `evidence` / `verification` gates are **not** reached — the flow stops at the authority boundary (fail-closed).

## Expected execution

- **No consequential write.** The target file is absent after the run (`os.path.exists(...) is False`).
- No partial execution: no executor runs, no file is written through the execution gate.

## Expected verification

- Verification is `INCONCLUSIVE` / absent — there is no outcome to verify because execution never happened.
- COMPLETE is never reached (AUTH-INV-15: no COMPLETE without a verified outcome, and here there is no outcome at all).

## Expected failure / recovery

- The denial is recorded as an audit `gate_authority` event with `result == "denied"` (and `execution_denial` for the execution-time path).
- Recovery is **not** entered for a pure authority denial (no new diagnosed cause exists); the disposition is terminal BLOCKED/ESCALATED, escalation to Human is the documented path (Runbook 01).

## Evidence requirements

- `FlowResult.to_dict()` is JSON-serializable and shows `outcome`, `phase`, and the gate record list.
- Audit ledger contains at least one `gate_authority` (or `execution_denial`) event with `result == "denied"`.
- No-mutation proof: target file absent; state registry/audit files not modified by the denied action.
- Audit chain verifies clean (`verify_chain`), showing the denial is append-only and does not grant authority (AUTH-INV-14).

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

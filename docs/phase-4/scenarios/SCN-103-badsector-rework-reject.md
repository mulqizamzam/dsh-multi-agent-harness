# SCN-103 — BadSector Rework / Reject (bounded)

- **Id**: `SCN-103`
- **Runbook**: `docs/runbooks/04-badsector-rework-reject.md`
- **PRD §17 skeleton**: #7 — High-impact action requiring Human approval
- **Anchors**: AUTH-INV-09/10/20 · THREAT-014/015/023 · BAD-001..004
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestBadsectorReworkReject`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount; live BadSector invocation unproven per-role).

---

## Preconditions

- Workspace as in SCN-101.
- A mandatory BadSector review is triggered (`review_required=True`, or HIGH risk / intrinsic-HIGH action, or `material_conflict`).
- The review record is supplied to the flow:
  - `SCN-103a` **REJECT** verdict: `{"verdict": "REJECT", "review_id": …, "input_hash": …}`.
  - `SCN-103b` **REWORK** verdict: `{"verdict": "REWORK", …}`.
  - `SCN-103c` **PASS but no authority**: a proven PASS clears the review stage only; the delegation grants `read` only, the plan's action is `write`.
  - `SCN-103d` forged PASS: `input_hash` does not match the synthesis (provenance fails, THREAT-014).

## Objective

Prove that the BadSector review stage is a **gate, not an authorization** (AUTH-INV-09): REWORK and REJECT halt the pipeline at the review boundary; a PASS clears the review stage only and never grants execution authority; a forged PASS is denied.

## Actors

- **orchestrator** — routes the review, runs the review gate.
- **badsector** — review-only role; produces the verdict (record).
- **cto** — routed specialist whose proposal is under review.
- **Human** — required for REJECT override (THREAT-023); the override is explicit and recorded, never implicit.

## Expected state

- `SCN-103a/b/d` → `BLOCKED` at phase `adversarial_review`; `final_state` never `COMPLETE`.
- `SCN-103c` → `BLOCKED` at phase `authority_gate` (review ALLOW, authority DENY).
- Task state machine never advances past the review boundary on a non-PASS verdict.

## Expected gates

- `badsector_review` gate:
  - REJECT / REWORK → `DENY` (`review not passed: <verdict>`).
  - Forged PASS (hash mismatch) → `DENY` (provenance mismatch, THREAT-014/BAD-001).
  - Proven PASS → `ALLOW` (review cleared) **only**.
- `authority` gate → `DENY` in 103c even though the review ALLOWed (PASS ≠ authorization).
- Mandatory review skipped → `DENY` (transition violation, THREAT-015).

## Expected execution

- **No consequential write** in any sub-case: the flow stops before EXECUTE.
- No file written; executor never invoked.

## Expected verification

- Verification not reached; COMPLETE is never produced.
- The review gate decision is recorded in `result.gates` with the verdict detail.

## Expected failure / recovery

- `failure_class` per Runbook 04: REJECT → `authorization` (escalate; no auto-recover); REWORK → `logic` when rework is fillable (route back into planning under the same delegation, bounded by `max_rework_cycles`), `authorization` when unfillable; forged verdict → `unknown` (security incident, Runbook 10).
- No auto-resolve: a REWORK is not re-asked to BadSector on the same input hash; a REJECT is not auto-routed for rework.
- The deterministic runtime's bounded behavior is **halt at the review gate**; the documented rework re-plan and Human-override paths are asserted at the control-module level (Runbook 04 semantics), not auto-executed.

## Evidence requirements

- `FlowResult.gates` contains a `badsector_review` record with the expected decision and verdict detail.
- Audit contains a `gate_review` event with `result == "denied"` (or a `badsector_review` record for the invocation), plus the review log used for provenance.
- No-mutation proof: target absent.
- Positive control (103c): review gate ALLOW **and** authority gate DENY in the same run proves PASS ≠ authorization.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

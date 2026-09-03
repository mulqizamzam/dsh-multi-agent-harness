# Runbook 04 — BadSector REWORK / REJECT

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/security/0001-control-assurance-spec.md` §9, §13 (BAD-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-014/015), §15 · `docs/design/0001-control-design-and-test-plan.md` §11 · `tests/adversarial/test_injection.py::TestBadSectorProvenance` · `tests/control_plane.py::verify_badsector_provenance`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a BadSector verdict of **REWORK** or **REJECT**. A PASS is **never** authority (AUTH-INV-09) and is not handled here (it does not halt anything; see Runbook 01 if execution under a PASS-only path is attempted).

---

## What this runbook covers

BadSector is a **review-only role**. It returns one of three verdicts:

| Verdict | Meaning | What the orchestrator must do |
|---|---|---|
| **PASS** | Clears the review stage | **Not authority.** Execution still requires a delegation. The PASS record alone is not a denial (it does not halt); this runbook does not apply. |
| **REWORK** | Returns the proposal for targeted rework | The orchestrator must route the rework to the relevant specialist(s) (per the `recommended_changes[]` in the verdict) and re-plan. The pipeline halts at the review-stage boundary until rework completes. |
| **REJECT** | The proposal stops unless Human overrides | The orchestrator halts the pipeline at the review-stage boundary and escalates to the Human. |

A REWORK or REJECT verdict triggers this runbook. Both must be **verifiable provenance** (THREAT-014) — the record must trace to a real BadSector invocation on the exact input. A verdict that fails provenance is treated as a **forgery** and routed to Runbook 10 — Audit Integrity Failure (the verifier never authored the record).

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| `audit/` event with `event_class == "bad_sector_review"` and `verdict ∈ {"REWORK", "REJECT"}` | `audit/helpers/append_log.py::read_events_by_class("bad_sector_review")` |
| Orchestrator's planner records a REWORK/REJECT on the active task | orchestrator working memory |
| A `provenance_check_failed` audit event shortly after a REWORK/REJECT event (this is a forgery — escalate to Runbook 10) | `audit/helpers/append_log.py::read_events_by_class("escalation")` filtered for `reason == "forged_bad_sector_verdict"` |

**Read in this order:**

1. The most recent `bad_sector_review` event. Capture `review_id`, `task_id`, `agent_id == "badsector"`, `input_version`, `input_hash`, `verdict`, `output` (the structured findings), `timestamp`.
2. The **originating task** the review was performed on. Capture `task_id`, the proposal being reviewed, the action class, the target, the risk classification.
3. The **input hash** of the reviewed proposal — this is the `input_hash` from the review event. It must match the `input_hash` recorded in the BadSector invocation log (the control plane's own record; not the audit chain) for provenance to hold.
4. The verdict's structured findings: `critical_risks[]`, `weak_assumptions[]`, `missing_evidence[]`, `contradictions[]`, `recommended_changes[]`, `confidence ∈ {low, medium, high}`.

---

## STOP

1. **Halt the pipeline at the review-stage boundary** for the originating task. The transition function (`ST-002` in the test matrix; design doc §12) refuses any transition out of `REVIEW_PENDING` that does not carry a verified verdict record. The pipeline must **not** proceed to `APPROVED` or `EXECUTING`.
2. **If verdict == REJECT**: do **not** route the proposal for rework automatically. The proposal stops unless a Human override arrives (AUTH-INV-04; THREAT-023). Surface the REJECT to the Human via `event_class == "escalation"`.
3. **If verdict == REWORK**: do **not** auto-resolve the rework by re-asking BadSector. The rework is the responsibility of the originating specialist(s) named in `recommended_changes[]`. The pipeline re-enters at the relevant earlier state (`DRAFT` or `PLANNED`) only after the rework produces a new proposal.
4. **Lock the verdict in audit** with `event_class == "bad_sector_review"`, `verdict`, `output`, `input_version`, `input_hash`, `actor = "badsector"`, `actor_type = "agent"`.

---

## PRESERVE

1. **Snapshot the reviewed proposal** (the input the BadSector invocation received) — input file paths, input `version`, input `sha256`. The orchestrator holds this in working memory but should also have it in `state/decisions/` or the task record. If not present, **escalate** (`reason = "review_input_missing"`) — provenance cannot be verified without the input.
2. **Snapshot the audit chain slice** covering the review: every event in `audit/<project>/events.jsonl` from the review invocation's start to the verdict emission. Use `audit/helpers/integrity.py::verify_chain` to confirm chain integrity over that slice; a chain break before the verdict is a Runbook 10 case.
3. **Capture `before` hashes** of `state/registry/`, `audit/`, and any file the proposal would have touched. Same procedure as Runbook 01 §PRESERVE.

---

## DIAGNOSE

| Diagnostic question | How to answer | Outcome |
|---|---|---|
| Is the verdict a **forgery**? | Run `tests/control_plane.py::verify_badsector_provenance(record, expected_input_hash, review_log)` — returns `True` only if the record matches a real invocation in the review log and the input hash matches | If **False**, escalate as `forged_bad_sector_verdict` and route to Runbook 10. **Do not** honor the verdict. |
| Did the verdict arrive **after** the originating task advanced past `REVIEW_PENDING`? | Compare verdict `timestamp` to the task's `current_state.phase` transition log | If the task already advanced, the state machine violation itself is an audit event (`event_class == "state_violation"`); halt and escalate. The verdict still records, but it has no effect on a state that already moved. |
| Does the verdict cite **missing evidence** that is **fillable**? | Inspect `missing_evidence[]` and `contradictions[]` | If **fillable** under the same delegation (e.g. the missing evidence is research Kai can produce), the rework can be scoped; proceed to RECOVER with a re-plan. If **not fillable** (e.g. evidence the Human must provide), escalate. |
| Does the verdict name **risks** that reclassify risk class? | Map `critical_risks[]` to the risk gate (`tests/control_plane.py::classify_risk` intrinsic categories) | If any risk is in an intrinsic HIGH category (production, destructive, credential, financial, material publication), the rework plan must remain at HIGH; model judgment cannot downgrade (AUTH-INV-10, THREAT-011). |

`failure_class`:
- REWORK with fillable findings → `logic` (the proposal was incomplete; rework is the right path).
- REWORK with un-fillable findings (Human-only evidence) → `authorization` (escalate).
- REJECT → `authorization` (escalate; do not auto-recover).
- Forged verdict → `unknown` (security incident; Runbook 10 first).

---

## RECOVER / ESCALATE

**A REJECT verdict never auto-recovers.** The pipeline halts. The Human may override (a `Human override` audit event with `authority_source`; THREAT-023). The override path is **explicitly recorded**, not implicit.

**A REWORK verdict routes back into the planning loop** under these conditions:

1. The originating delegation is still ACTIVE and not expired/revoked. Run the authority gate with the original delegation id; if it now denies (Runbook 02 or 03), the rework cannot proceed under that delegation — escalate first.
2. The rework scope is contained in `recommended_changes[]` and does not exceed the original delegation's `scope.resources` (AUTH-INV-04, AUTH-INV-11).
4. Any new evidence required by `missing_evidence[]` is obtainable under the same delegation or via a Human grant.

**Re-plan procedure:**

1. Open a new `task_id` for the rework (or attach to the existing task's `rework_cycles`, incrementing). The recovery bounds (`max_rework_cycles: 2`, default per `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`) apply; on the second rework, escalate regardless.
2. Re-issue the proposal only after the rework has produced a new proposal with `input_version = current` and a new `input_hash`. The next BadSector invocation must be on the new proposal — calling BadSector twice on the same input does not clear a REWORK.
3. After rework, the proposal re-enters `REVIEW_PENDING`. A new BadSector invocation is required; a REWORK-then-PASS on the same hash is not a valid path (the hash changed; the same hash means the proposal did not change).
4. Append `event_class == "state_transition"`, `result == "rework_replan"`, `previous_state = REVIEW_PENDING`, `new_state = DRAFT` (or `PLANNED` per the workflow).

**Escalation procedure (REJECT, or un-fillable REWORK, or REJECT-after-REWORK):**

1. Append `event_class == "escalation"`, `reason = "bad_sector_reject"` (or `bad_sector_rework_unfillable` / `bad_sector_rework_max_cycles`), `verdict`, `review_id`, `task_id`, `critical_risks[]`, `human_signoff_required = true`.
2. The Human may issue an override (THREAT-023): a `Human override` event with `authority_source = <override id>`, `override_reason`, `original_verdict = <review event_id>`. The override is **explicitly recorded**, not implicit. The override does **not** delete or amend the original REJECT event — both are in the audit chain (append-only).
3. If the Human's override carries a new delegation (or extends an existing one), the orchestrator must re-evaluate the gate with the new authority and proceed under that delegation's id. The override is the grant; the new delegation is the structured authority.

**Provenance failure:** if `verify_badsector_provenance` returns False, **do not** route REWORK or honor REJECT. Escalate immediately (`reason = "forged_bad_sector_verdict"`) and proceed to Runbook 10.

---

## VERIFY

1. **Audit chain integrity** holds across the review event and the state transitions it triggered (`audit/helpers/integrity.py::verify_chain` clean).
2. **Provenance** verified via `verify_badsector_provenance`. A failing provenance check is a critical alert, not a soft warning.
3. **No state mutation** outside the documented transitions. The REWORK re-plan must move through the transition function (`DRAFT → PLANNED → REVIEW_PENDING → APPROVED → EXECUTING → VERIFYING → COMPLETE`); any skipped phase is a state-machine violation.
4. **Rework bounds**: `rework_cycles < max_rework_cycles` (default 2, `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`). Exceeding the bound escalates regardless of verdict.
5. **Override records** (if a Human override happened) carry `actor_type = human` and `authority_source` set to the override id. A Human override event with `actor_type = agent` is a forgery and is Runbook 10.

---

## REPORT

**Event 1 — the verdict** (always, written by the BadSector invocation):

```text
event_class: "bad_sector_review"
actor: "badsector"
actor_type: "agent"
action: "review"
target: "<task_id>"
task_id: "<task_id>"
review_id: "<review_id>"
input_version: <int>
input_hash: "<sha256>"
verdict: "REWORK" | "REJECT"
output: { critical_risks: [...], weak_assumptions: [...], missing_evidence: [...],
          contradictions: [...], recommended_changes: [...], confidence: "low"|"medium"|"high" }
result: "completed"
timestamp: "<UTC ISO 8601>"
```

**Event 2 — state transition** (always):

```text
event_class: "state_transition"
action: "transition_out_of_review_pending"
target: "<task_id>"
previous_state: "REVIEW_PENDING"
new_state: "DRAFT" (REWORK) | "BLOCKED" (REJECT) | "ESCALATED" (un-fillable REWORK)
authority_source: "<task's active delegation id, if any>"
result: "transitioned" | "denied"
```

**Event 3a — rework re-plan** (REWORK with fillable findings):

```text
event_class: "rework_replan"
action: "replan_after_rework"
target: "<task_id>"
rework_cycles: <int>
recommended_changes: [...]
evidence: ["bad_sector_review:<review_id>"]
result: "replanned"
```

**Event 3b — escalation** (REJECT, or un-fillable REWORK, or bound exceeded):

```text
event_class: "escalation"
action: "escalate_bad_sector_verdict"
target: "<task_id>"
verdict: "REWORK" | "REJECT"
review_id: "<review_id>"
human_signoff_required: true
evidence: ["bad_sector_review:<review_id>"]
result: "escalated"
```

**Event 4 — Human override** (only if the Human overrode a REJECT):

```text
event_class: "human_override"
actor: "<human session id>"
actor_type: "human"
action: "override_bad_sector_reject"
target: "<task_id>"
authority_source: "<override id>"
override_reason: "<string>"
original_verdict_review_id: "<review_id>"
result: "overridden"
```

All events are records; no event grants authority (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **REWORK during a recovery**: if the orchestrator is already in `RECOVERING` (Runbook 08) and a REWORK verdict arrives, the recovery is the priority — finish STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY → REPLAN → AUTHORITY RE-CHECK, then handle the REWORK. Do not interleave the recovery and rework lifecycles.
- **REWORK that would change the delegation scope**: out of scope for the existing delegation (AUTH-INV-04). The orchestrator must escalate for a new delegation rather than widening scope.
- **BadSector tool failure**: if the BadSector invocation itself fails (tool error, no output, malformed verdict), the review is treated as **not passed**. The proposal does not proceed; escalate (`reason = "bad_sector_invocation_failed"`). This is the spec §9 "BadSector failure" rule.
- **REWORK on a HIGH-risk action**: a REWORK does not lower risk. If the rework still maps to intrinsic HIGH (e.g. destructive data operation), the risk class remains HIGH and the action must re-pass the risk gate (AUTH-INV-10).
- **A verdict record without a matching review invocation**: forgery (Runbook 10). Do not honor the verdict.

---

## References

- AUTH-INV-04/09/10/14/20
- THREAT-014/015/023
- `tests/control_plane.py::verify_badsector_provenance`, `badsector_pass_is_authority`
- `tests/adversarial/test_injection.py::TestBadSectorProvenance`
- `tests/authorization/test_authority.py::test_auth_007_badsector_pass_is_not_authority`
- `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
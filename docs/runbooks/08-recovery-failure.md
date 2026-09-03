# Runbook 08 — Recovery Failure

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/07-execution-failure.md` · `docs/security/0001-control-assurance-spec.md` §11, §13 (REC-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-017/022), §16 · `docs/design/0001-control-design-and-test-plan.md` §19 · `state/helpers/recovery.py` (entire module) · `tests/unit/test_recovery.py`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a **recovery that itself failed**. The action that originally failed is already in a `RecoveryRecord` (Runbook 07), but the recovery lifecycle could not complete. This runbook covers the failure modes: rollback cannot restore, restoration cannot be verified, authority re-check fails, bounds exceeded, version drift, or the recovery state machine raises.

---

## What this runbook covers

Runbook 07 produces a `RecoveryRecord` and drives it through the documented lifecycle. That lifecycle can fail at any transition:

| Failure point | What it means | Reference |
|---|---|---|
| `STOPPED → PRESERVED` raises | `preserved_version` not capturable (state file missing/corrupt) | `recovery.py::RecoveryRecord.preserve` |
| `DIAGNOSED` raised with empty cause | No blind retry (AUTH-INV-16, REC-001) | `recovery.py::RecoveryRecord.diagnose` (raises if cause empty) |
| `VERIFYING_RESTORATION` raised with `verified=False` | Restoration not independently verified (REC-003) | `recovery.py::RecoveryRecord.verify_restoration` |
| `REPLANNED` raised with no diagnosed cause | Cannot replan without a cause | `recovery.py::RecoveryRecord.replan` |
| `AUTHORITY_RECHECKED` raised with `checked=False` | Recovery did not re-pass the gate (AUTH-INV-12) | `recovery.py::RecoveryRecord.authority_rechecked` |
| `validate_against_current_version` raises `RecoveryDenied` | State advanced beyond preserved version (THREAT-022) | `recovery.py::RecoveryRecord.validate_against_current_version` |
| `can_retry(max_attempts, new_cause)` returns False | Bound exceeded or no new cause (AUTH-INV-16) | `recovery.py::RecoveryRecord.can_retry` |
| `ROLLBACK` itself failed | The rollback action did not complete cleanly | REC-002 |
| `RecoveryError` raised by any `_enter` | Invalid transition (skipping a phase) | `recovery.py::RecoveryRecord._enter` |
| `RECOVERY_STATES` initial state invalid | Constructed record with a state not in the enum | `recovery.py::RecoveryRecord.__post_init__` |

The recovery state machine has **one terminal good state** (`COMPLETED`) and **one terminal bad state** (`FAILED`). This runbook covers the path to `FAILED` and the escalation that follows.

**No recovery may proceed to `COMPLETED` without `restoration_verified = True` AND `authority_checked = True`** (REC-003, AUTH-INV-12). Both are preconditions encoded in the state machine; the runbook enforces them by following the documented transitions.

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| `audit/` event with `event_class == "recovery_state_transition"` and `result == "failed"` | `audit/helpers/append_log.py::read_events_by_class("recovery_state_transition")` |
| A `RecoveryRecord` exists with `state == "FAILED"` (`recovery.py::RecoveryRecord.fail(reason)` was called) | `RecoveryRecord.to_dict()` (or the persisted record, if any) |
| A `RecoveryError` / `RecoveryDenied` raised during recovery that was not caught | exception traceback + the orchestrator's outer state machine |
| A rollback that left on-disk state in an unexpected state (e.g. `before.sha256 != after.sha256` after `VERIFYING_RESTORATION` claims verified) | external sha256 comparison (Runbook 07 §VERIFY) |
| A second `execution_attempt` event for the same task after `STOPPED` but before `COMPLETED` | `audit/helpers/append_log.py` — indicates a blind retry, not a recovery |

**Read in this order:**

1. The most recent `recovery_state_transition` events for the originating task. Capture the full transition history: every state from `STOPPED` through the failure point.
2. The `RecoveryRecord.to_dict()` (or the equivalent persisted record). Capture `preserved_version`, `current_version`, `diagnosed_cause`, `failure_class`, `rollback_performed`, `restoration_verified`, `authority_checked`, `attempts`, `state`, `reason`.
3. The on-disk `before.sha256` and `after.sha256` of every file the original action touched (Runbook 07 §PRESERVE produced `before`; the rollback should have produced an `after` matching `before`).
5. The current state version (`state/helpers/version_check.py::read_version`).
6. The authority state: did the gate pass on the most recent `authority_rechecked`?

---

## STOP

1. **Halt the recovery lifecycle.** No more transitions from `FAILED`. `FAILED` is a terminal state in the state machine (`_RECOVERY_TRANSITIONS["FAILED"] = set()`); any `_enter` from `FAILED` raises `RecoveryError`.
2. **Cancel any further recovery actions** triggered by the orchestrator's outer loop. The outer state machine (`orchestrator/foundation/state.py`) treats `FAILED` as a halt signal for the recovery sub-flow; the task must not silently re-enter recovery.
3. **Do not retry the recovery** in-band. The recovery state machine is single-pass: once `FAILED`, the only forward action is Human escalation.
4. **Lock the failure in audit** with `event_class == "recovery_state_transition"`, `state = "FAILED"`, `recovery_record_id`, `reason`, `previous_state`, `diagnosed_cause`, `failure_class`, `rollback_performed`, `restoration_verified`, `authority_checked`, `result = "failed"`.

---

## PRESERVE

This is **the second PRESERVE** — the recovery is itself failing, so preserve both the original pre-recovery state (already captured in `preserved_version`) and the post-recovery-attempt state (the current state). The diff between them is the diagnostic evidence.

1. **Confirm** `RecoveryRecord.preserved_version` (from Runbook 07) is still recorded and matches the on-disk `before.sha256`. The orchestrator did not lose this across the recovery lifecycle.
2. **Capture `after.sha256`** of every file the recovery attempted to roll back. Compute externally (do not write to `state/` or `audit/`).
3. **Capture the rollback's side-effects**: any `*.tmp` files left behind by an interrupted atomic write (`state/helpers/atomic_write.py::atomic_write` uses `tempfile.NamedTemporaryFile` with a random prefix; the temp file may exist if `os.replace` was not reached). These are diagnostic evidence — do not delete.
4. **Capture the audit chain slice** for the recovery: every `recovery_state_transition` event from `STOPPED` to `FAILED`. The chain itself is the recovery's narrative.
5. **Persist the `RecoveryRecord`** in `state/decisions/<task-id>-recovery.json` using `state/helpers/atomic_write.py::atomic_write`. The record is **data**, not authority (AUTH-INV-14); it is the durable artefact the Human will read.

> Persisting the `RecoveryRecord` to `state/decisions/` is a non-protected path and is within the orchestrator's allowed write scope. Do **not** write it to `state/registry/` (protected; ADR 0002).

---

## DIAGNOSE

Classify the recovery failure into one of the documented root causes:

| Root cause | Detection | Outcome |
|---|---|---|
| **No diagnosis recorded** (cause empty at `DIAGNOSED`) | `recovery.py::RecoveryRecord.diagnose` raised | This is a logic bug in the orchestrator's recovery code — no `diagnosed_cause` means the recovery cannot proceed. Escalate as `logic` bug. |
| **Rollback did not restore** (`before.sha256 != after.sha256`) | External sha256 comparison | REC-002 — rollback failed. Escalate; the on-disk state is now in an unknown state (from the orchestrator's perspective). The protected-path execution gate prevents accidental writes; the recovery code path bypassed it (legitimately, for rollback). |
| **Restoration not independently verified** (REC-003) | `verify_restoration(verified=False)` raised | The recovery cannot claim `restoration_verified = True` without an external measurement. Escalate; the recovery must not proceed to `REPLANNED` without verification. |
| **State advanced between preserved and current** (THREAT-022) | `validate_against_current_version` raised `RecoveryDenied` | A parallel writer (or another orchestrator instance) advanced the state. The recovery cannot proceed under the preserved version. Re-read, re-validate authority, decide whether to recover against the newer state (a *new* recovery, with a *new* `preserved_version`). |
| **Authority re-check failed** (AUTH-INV-12) | `authority_rechecked(checked=False)` raised | The gate denied the recovery's re-execution (the delegation expired, was revoked, or scope/target drifted). This is a Runbook 02/03 situation; the recovery must fail and escalate. |
| **Bounds exceeded** (AUTH-INV-16) | `can_retry(max_attempts, new_cause)` returned False | Either `attempts >= max_attempts` (default 1) or `new_cause == diagnosed_cause` (no new cause). Escalate regardless of cause. |
| **Invalid transition** (state-machine violation) | `RecoveryError` from `_enter` | The orchestrator attempted to skip a phase (e.g. `DIAGNOSED → COMPLETED` directly). This is a logic bug. Escalate. |
| **Restoration verified but on-disk state still diverges** | sha256 mismatch after `verify_restoration(True)` | The independent verification was a false positive (a measurement channel that did not actually observe the rollback). Escalate as `unknown`; the recovery must not be trusted. |

`failure_class`:
- `environment` for rollback failures caused by IO/permission/path issues.
- `logic` for missing diagnosis, invalid transition, or measurement false-positive.
- `authorization` for authority re-check failures.
- `unknown` for unclassified (mandatory escalation; the orchestrator must not guess).

---

## RECOVER / ESCALATE

**There is no in-band recovery from a recovery failure.** The state machine forbids `FAILED → <any>` (the `_RECOVERY_TRANSITIONS` table sets `FAILED: set()`). The only forward action is escalation to the Human.

**Exception — recoverable recovery failures** (rare; only with explicit Human pre-approval):

- **Re-read the current state version** (`state/helpers/version_check.py::read_version`). If the state has advanced, the recovery is recoverable: create a **new** `RecoveryRecord` with the **new** `preserved_version` and a **new** `diagnosed_cause` that names the state drift as the cause. This is **not** a retry of the failed recovery; it is a new recovery against the new state. The previous `RecoveryRecord` stays at `FAILED` in audit.
- **Re-validate authority** with the new state version. If the gate passes, proceed under the new `preserved_version`. If the gate fails, escalate.

These two cases are the only "recover the recovery" paths the architecture allows. Both produce **new** records; the old `FAILED` record is preserved.

**Escalation (default and dominant path):**

1. **Append** `event_class == "escalation"`, `reason = "recovery_failure"`, `task_id`, `recovery_record_id`, `failure_class`, `failed_transition`, `preserved_version`, `current_version`, `rollback_performed`, `restoration_verified`, `authority_checked`, `human_signoff_required = true`, `evidence = [<recovery_state_transition event_ids>...]`.
3. **Surface the persisted `RecoveryRecord`** (in `state/decisions/<task-id>-recovery.json`) to the Human reviewer. The reviewer reads the record directly; the audit chain provides the lineage.
4. **The Human's response** (THREAT-023 — explicit override):
   - **Approve retry** with a new cause → the Human records `event_class == "human_override"`, `authority_source = <override id>`, `override_reason = "<new cause>"`, `original_recovery_record_id`. The orchestrator creates a **new** `RecoveryRecord` with the Human's cause and proceeds.
   - **Reject** → the action halts permanently for this task. The orchestrator records `event_class == "state_transition"`, `new_state = "BLOCKED"`, `authority_source = <override id>`.
   - **Re-grant authority** (the original gate denied on re-check) → the Human creates a new delegation id; the orchestrator re-validates under the new id.

**Headless / CI behaviour**: identical to prior runbooks — the action halts at `FAILED`; the escalation event is recorded; no implicit allow.

**No auto-loop**: the orchestrator must not enter a "retry the recovery" loop. Each recovery is a single pass; further attempts are new records.

---

## VERIFY

1. **`RecoveryRecord.state == "FAILED"`** — confirmed via `to_dict()` or the persisted record.
2. **Audit chain integrity** holds across the full recovery sequence (`audit/helpers/integrity.py::verify_chain` clean). A chain break during the recovery is itself a Runbook 10 incident.
3. **No further recovery transitions** after `FAILED`: the audit chain must show no `recovery_state_transition` events with `state != "FAILED"` after the `FAILED` event. The state machine forbids this, but verify it (a transition out of `FAILED` would be a logic bug).
4. **On-disk state diff** documented: `before.sha256` (Runbook 07 PRESERVE) and `after.sha256` (Runbook 08 PRESERVE) are both captured. If they differ, the rollback was incomplete (REC-002). If they match, the rollback landed — but the recovery still failed for another reason (e.g. `restoration_verified = False`, `authority_checked = False`).
5. **Persisted `RecoveryRecord`** in `state/decisions/<task-id>-recovery.json` matches the audit chain's narrative. A Human reviewer can read either and reach the same conclusion.

---

## REPORT

**Event 1 — the failed transition** (the one that triggered this runbook; always):

```text
event_class: "recovery_state_transition"
actor: "orchestrator"
actor_type: "agent"
action: "recover"
target: "<task_id>"
recovery_record_id: "<uuid>"
state: "FAILED"
previous_state: "<state at failure>"
diagnosed_cause: "<string>"
failure_class: "environment" | "logic" | "authorization" | "unknown"
rollback_performed: true | false
restoration_verified: true | false
authority_checked: true | false
preserved_version: <int>
current_version: <int>
reason: "<string>"
result: "failed"
```

**Event 2 — the persisted recovery record** (one durable artefact in `state/decisions/`):

```json
{
  "task_id": "<task_id>",
  "state": "FAILED",
  "attempts": <int>,
  "diagnosed_cause": "<string>",
  "preserved_version": <int>,
  "current_version": <int>,
  "failure_class": "<enum>",
  "rollback_performed": <bool>,
  "restoration_verified": <bool>,
  "authority_checked": <bool>,
  "reason": "<string>",
  "created_at": "<ISO 8601>",
  "updated_at": "<ISO 8601>",
  "recovery_record_id": "<uuid>"
}
```

Written via `state/helpers/atomic_write.py::atomic_write` to `state/decisions/<task-id>-recovery.json`. The path is not protected; the orchestrator may write it directly.

**Event 3 — escalation**:

```text
event_class: "escalation"
action: "escalate_recovery_failure"
target: "<task_id>"
recovery_record_id: "<uuid>"
failure_class: "<enum>"
failed_transition: "<state at failure>"
human_signoff_required: true
evidence: ["recovery_state_transition:<event_id>", ...]
result: "escalated"
```

**Event 4 — Human override** (if a Human resolves):

```text
event_class: "human_override"
actor: "<human session id>"
actor_type: "human"
action: "resolve_recovery_failure"
target: "<task_id>"
recovery_record_id: "<uuid>"
authority_source: "<override id>"
override_reason: "<string>"
resolution: "retry_with_new_cause" | "halt" | "new_delegation"
original_recovery_event_id: "<recovery_state_transition event_id>"
result: "overridden"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **Recovery that fails because `validate_against_current_version` raises on every check** (state keeps advancing): the orchestrator must not loop on `validate_against_current_version`. The bound is implicit: if the version keeps advancing faster than the recovery, escalate as `unknown` with `reason = "state_drift_unresolvable"` and let the Human coordinate the parallel writers.
- **`RecoveryError` from `_enter` because the orchestrator tried to skip a phase**: the orchestrator's recovery code is buggy. Escalate as `logic`; do not patch in-band.
- **`recovery.py::from_dict` rejects unknown fields** (`RecoveryError("unknown RecoveryRecord fields ...")`): a record persisted with a newer schema cannot be loaded by an older orchestrator. This is a forward-compat hazard; treat as `environment` if the orchestrator is pinned (`0.1.1-rc.2`) and the schema is unchanged, else escalate as `unknown`.
- **`RecoveryRecord` already at `FAILED` when this runbook is invoked** (e.g. another component called `fail()` first): the runbook's STOP/PRESERVE/DIAGNOSE/RECOVER all still apply; the record is already terminal, so ESCALATE is the only forward path. Do not "re-open" a `FAILED` record.
- **Multiple recoveries on the same task** (e.g. two parallel sub-tasks each with their own `RecoveryRecord`): the recovery state machine is per-`task_id`; parallel recoveries on different `task_id`s are independent. Parallel recoveries on the same `task_id` are forbidden by the orchestrator's outer state machine — only one recovery per task at a time. A second `begin_recovery` while the first is not `COMPLETED` or `FAILED` should be rejected by the outer flow.

---

## References

- AUTH-INV-12/14/16/20
- THREAT-017/022
- security spec §11 (Recovery Assurance), §11.1 (bounds), §13 (REC-001..003)
- threat model §16 (Verification and Recovery)
- design doc §19 (Recovery)
- `state/helpers/recovery.py` (entire module — the recovery state machine, `_RECOVERY_TRANSITIONS`, `RecoveryRecord`, `begin_recovery`, `can_retry`, `validate_against_current_version`)
- `state/helpers/atomic_write.py::atomic_write`, `safe_read`
- `state/helpers/version_check.py::read_version`, `is_stale`, `assert_current_version`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`
- `tests/unit/test_recovery.py` (recovery state machine tests)

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
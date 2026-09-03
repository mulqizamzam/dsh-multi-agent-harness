# Runbook 07 — Execution Failure

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/runbooks/08-recovery-failure.md` · `docs/security/0001-control-assurance-spec.md` §11, §13 (REC-* / VERIFY-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-016/017/022/024/025), §16 · `docs/design/0001-control-design-and-test-plan.md` §14 (Execution gate), §19 (Recovery) · `state/helpers/recovery.py::RecoveryRecord`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to an **execution failure** — an action that passed the gate (so this is *not* an authority denial) but failed at or after the moment of execution. Includes tool errors, DSH `stopReason != completed`, partial writes, unexpected I/O failures, and verification-mismatch failures (where the gate's expected outcome did not match the actual outcome).

---

## What this runbook covers

An **execution failure** is the state where:

- The gate **passed** (`authorize(...)` returned True, the action is authorised),
- The execution was attempted,
- The execution did **not** complete cleanly — either the tool returned an error, the runtime emitted `stopReason ∈ {error, aborted, refusal}`, the file write did not land atomically, or verification of the side-effect failed.

This runbook does **not** cover authority denials (Runbook 01), expiry/revocation (Runbooks 02/03), BadSector verdicts (Runbook 04), evidence failures (Runbook 05), or conflict escalation (Runbook 06) — those have their own gates. An execution failure is a *post-gate* failure.

The recovery posture is the documented recovery state machine (security spec §11):

```text
STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY RESTORATION
     → REPLAN → AUTHORITY RE-CHECK
```

`state/helpers/recovery.py::begin_recovery` creates the `RecoveryRecord` that drives this lifecycle. **No blind retry** (AUTH-INV-16, REC-001): a retry requires a NEW diagnosed cause. Recovery does **not** acquire privilege automatically (AUTH-INV-12, REC-004); it re-passes the same authority path.

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| DSH `stopReason ∈ {"error", "aborted", "refusal", "max-tokens"}` on a tool call | `audit/helpers/append_log.py::read_events_by_class` filtered for `tool_call` events |
| `audit/` event with `event_class == "execution_attempt"` and `result == "error"` or `result == "aborted"` | `audit/helpers/append_log.py` |
| A tool result containing a non-success `error` field and no committed side-effect | tool-result envelope |
| `audit/` event with `event_class == "verification"` and `result == "mismatch"` (verification-of-side-effect failed) | `audit/helpers/append_log.py` |
| A `RecoveryRecord` with `state == "STOPPED"` already created by another step | `state/helpers/recovery.py` (in-memory or persisted) |
| A `RecoveryDenied` exception from `validate_against_current_version` (stale-version detected during recovery) | `state/helpers/recovery.py::RecoveryDenied` |

**Read in this order:**

1. The most recent `execution_attempt` (and any `tool_call`) events for the originating task. Capture `tool_call_id`, `tool`, `args`, `result`, `stopReason`, `diagnostic`, `error`, `timestamp`.
2. The originating task's `authority_source` (the delegation id that authorised the action) and the `state_version` that was current at the moment of execution.
3. The expected side-effect (the orchestrator's plan) and the actual side-effect (what the tool reported, what landed on disk).
4. The current state version (`state/helpers/version_check.py::read_version`) — to detect an obsolete recovery.

---

## STOP

1. **Halt the in-flight action.** No retry until diagnosis. The orchestrator does not loop on the same call.
2. **Cancel outstanding sub-jobs** that depended on the failed action (`interrupt_agent`, `job_kill`).
3. **Capture the `stopReason`/`diagnostic`** in the audit chain with `event_class == "execution_attempt"`, `result = "error|aborted|refusal"`, `stopReason`, `diagnostic`, `tool_call_id`, `error`. The DSH runtime surfaces this; the orchestrator's job is to forward it into the project's audit log.
4. **Do not** auto-rollback before PRESERVE and DIAGNOSE. A rollback that runs before PRESERVE has nothing to roll back to; a rollback that runs before DIAGNOSE may destroy the diagnostic evidence (AUTH-INV-12).

---

## PRESERVE

This is the recovery state machine's `PRESERVED` transition (`state/helpers/recovery.py::RecoveryRecord.preserve`).

1. **Begin a `RecoveryRecord`** via `state/helpers/recovery.py::begin_recovery(task_id, preserved_version, failure_class, reason)`:
   - `task_id` = the originating task id.
   - `preserved_version` = the `state_version` captured at the moment of execution, **before** any rollback. This is the version the recovery may roll forward to (THREAT-022).
   - `failure_class` = one of `"environment" | "logic" | "authorization" | "unknown"` — set during DIAGNOSE; the helper accepts `"unknown"` as the default and lets `diagnose()` refine it.
   - `reason` = the human-readable reason for the recovery.
2. **Snapshot on-disk state** (do not write to `state/registry/` or `audit/`):
   - `before.sha256` of every file the action was meant to touch.
   - `before.sha256` of `state/registry/` and `audit/` (read-only; sha256 only).
   - The registry's `version` at this moment (`state/helpers/version_check.py::read_version`).
3. **Snapshot the DSH session facts** for forensic context: `dsh_session_id`, `tool_call_id`, `stopReason`, `diagnostic`, `cwd` (DSH working dir at the moment of failure). These go into the `RecoveryRecord.reason` field (extend as needed; `from_dict` rejects unknown fields, so keep to the documented schema).
4. **Confirm atomicity**: if the failed action was a state write, verify the target file is either at its pre-state (`compare_and_swap` raised) or absent (atomic temp-write failed before `os.replace`). `state/helpers/atomic_write.py::atomic_write` documents the guarantee; the only on-disk artefact after a mid-write crash is a `<target>.tmp` (or `<target>.atomic_*`) file in the same directory, never a half-written target.

> Do **not** delete `*.tmp` files automatically — they are diagnostic evidence. The orchestrator may rename them to `<target>.recovery-evidence-<ts>` in `state/decisions/` (a writable, non-protected path) or leave them in place. If they are left in place, the next atomic-write to the same target will overwrite the temp (the temp prefix includes a random component, so no collision in practice).

---

## DIAGNOSE

`recovery.py::RecoveryRecord.diagnose(cause, failure_class, reason)` requires a **non-empty** diagnosed cause. No blind retry (AUTH-INV-16, REC-001).

| `stopReason` / error signature | Likely root cause | `failure_class` |
|---|---|---|
| `aborted` + `Job killed by interrupt_agent` | A sub-step was cancelled by the orchestrator (intentional or a cascade from another failure) | `logic` |
| `error` + `FileNotFoundError`/`PermissionError`/`OSError` | Environment (path/permission/IO) | `environment` |
| `error` + `jsonschema.ValidationError` or `state/helpers/atomic_write.py::StatePathError` | Logic (orchestrator constructed a bad payload) | `logic` |
| `error` + `RecoveryDenied` from `validate_against_current_version` | Authorization/state — state advanced between read and exec (THREAT-022) | `authorization` |
| `refusal` + DSH model refusal | Logic (the model declined; treat as a logic failure, not authority — model refusal is data, not a grant or denial of authority) | `logic` |
| `max-tokens` | Environment (budget exhaustion; not authority) | `environment` |
| `error` + DSH approval `unavailable` | Authorization (no Human answerer; the backstop fired) | `authorization` |
| `error` + verification mismatch (Runbook 09 territory) | Logic — the orchestrator's plan and the side-effect disagree | `logic` |
| Unknown | — | `unknown` (mandatory escalation per Runbook 08) |

Append `event_class == "recovery_state_transition"`, `state = "DIAGNOSED"`, `diagnosed_cause`, `failure_class` to audit. The cause string is **required** (`recovery.py::diagnose` raises `RecoveryError` if it is empty).

---

## RECOVER / ESCALATE

The recovery state machine (`state/helpers/recovery.py`) drives the lifecycle:

```text
DIAGNOSED → ROLLING_BACK → VERIFYING_RESTORATION → REPLANNED → AUTHORITY_RECHECKED → COMPLETED
                                                  ↘ FAILED ↗
```

**For `failure_class == environment`**: rollback is usually appropriate if a defined rollback exists. `recovery.py::RecoveryRecord.rollback()` transitions to `ROLLING_BACK` then `VERIFYING_RESTORATION`. Set `rollback_performed = True`. If no defined rollback exists for the action, skip rollback (`DIAGNOSED → REPLANNED`) and proceed.

**For `failure_class == logic`**: skip rollback (`DIAGNOSED → REPLANNED`); the cause is in the orchestrator's plan, not in on-disk state. A replan is the recovery.

**For `failure_class == authorization`** (stale state, no answerer, revoked-after-exec): the action cannot be re-attempted under the same authority — `recover()` must `authority_rechecked(checked=False)` to fail loudly (`RecoveryError`) and route to FAILED → Human escalation. The recovery does not silently re-grant (AUTH-INV-12, REC-004).

**For `failure_class == unknown`**: any state may transition to `FAILED` (`recovery.py::RecoveryRecord.fail(reason)`). Escalate to Human. Do not guess.

**`can_retry(max_attempts, new_cause)`** (`recovery.py::RecoveryRecord.can_retry`): a retry requires (a) `attempts < max_attempts` (default 1, `DEFAULT_MAX_ATTEMPTS`), AND (b) `new_cause != diagnosed_cause`. Identical-cause attempts beyond the cap are refused (AUTH-INV-16).

**`validate_against_current_version(current_version, expected_version)`** (`recovery.py::RecoveryRecord.validate_against_current_version`): refuse to execute recovery against an obsolete state version (THREAT-022). Raises `RecoveryDenied` on mismatch; the orchestrator must re-read the current version, re-validate authority, and re-issue.

**`authority_rechecked(checked=True)`**: the recovery re-passes the same authority path. The `RecoveryRecord` does not carry tools or grants; the caller (the orchestrator's gate) must re-run `authorize(...)` with the original delegation id and the **current** state version. If the gate now denies (because the delegation expired/revoked between plan and exec — Runbooks 02/03), the recovery fails (`FAILED`) and escalates.

**Append audit events** at every transition:

- `event_class == "recovery_state_transition"`, `state = "PRESERVED" | "DIAGNOSED" | "ROLLING_BACK" | "VERIFYING_RESTORATION" | "REPLANNED" | "AUTHORITY_RECHECKED" | "COMPLETED" | "FAILED"`, `task_id`, `recovery_record_id`, `previous_state`, `new_state`, `reason`.

**Headless / CI behaviour**: identical to prior runbooks — the pipeline halts on `FAILED`; the escalation event is recorded.

---

## VERIFY

1. **`verify_restoration(verified=True)`** (`recovery.py::RecoveryRecord.verify_restoration`): restoration must be **independently verified** before re-planning (REC-003). The verification is not the recovery's own claim; it is an external measurement:
   - For file writes: `before.sha256 == after.sha256` of the files the action touched (compute sha256 externally; do not write to `state/`).
   - For registry writes: the registry was not mutated (the protected-path execution gate prevents the orchestrator's session from writing; this verification confirms it).
   - For external side-effects: a separate channel observes the rollback (e.g. an HTTP probe from a separate process; in headless/CI, a recorded response fixture).
   - `verify_restoration(verified=False)` raises `RecoveryError` — the recovery cannot proceed without independent verification.
2. **Audit chain integrity** holds across all recovery transition events (`audit/helpers/integrity.py::verify_chain` clean).
3. **`authority_rechecked(True)`** recorded before `complete()`. A `complete()` without a prior `authority_rechecked()` is refused by the state machine (the transition function refuses `REPLANNED → COMPLETED` directly).
4. **`validate_against_current_version`** passed before any re-execution. A recovery that ignores the version check is a state-drift bug; surface immediately as `FAILED`.
5. **No tool call outside the gate** during recovery. Recovery is not a path to bypass `authorize()`; if the orchestrator attempts an action without re-running the gate, that is Runbook 01 territory (Runbook 01 covers the denial; here, the recovery's `authority_rechecked(False)` should have raised and escalated).

---

## REPORT

**Event 1 — the execution attempt** (always, by DSH or by the orchestrator's wrapper):

```text
event_class: "execution_attempt"
actor: "<role id | human>"
actor_type: "agent" | "human"
action: "<action class>"
target: "<target>"
authority_source: "<delegation id>"
tool_call_id: "<dsh tool_call_id>"
stopReason: "completed" | "error" | "aborted" | "refusal" | "max-tokens"
diagnostic: "<dsh diagnostic string>"
result: "success" | "error" | "aborted" | "refusal"
error: "<string, if any>"
timestamp: "<UTC ISO 8601>"
```

**Event 2 — the recovery state transitions** (one event per transition, driven by `RecoveryRecord._enter`):

```text
event_class: "recovery_state_transition"
actor: "orchestrator"
actor_type: "agent"
action: "recover"
target: "<task_id>"
recovery_record_id: "<recovery-record uuid>"
state: "STOPPED" | "PRESERVED" | "DIAGNOSED" | "ROLLING_BACK" |
       "VERIFYING_RESTORATION" | "REPLANNED" | "AUTHORITY_RECHECKED" |
       "COMPLETED" | "FAILED"
previous_state: "<state>"   # omitted for STOPPED initial
diagnosed_cause: "<string, set at DIAGNOSED>"
failure_class: "environment" | "logic" | "authorization" | "unknown"
rollback_performed: true | false
restoration_verified: true | false
authority_checked: true | false
preserved_version: <int>
current_version: <int>
reason: "<string>"
result: "transitioned" | "failed" | "escalated"
evidence: [...]
```

**Event 3 — escalation** (if `FAILED`):

```text
event_class: "escalation"
action: "escalate_execution_failure"
target: "<task_id>"
recovery_record_id: "<recovery-record uuid>"
failure_class: "..."
stopReason: "..."
human_signoff_required: true
evidence: ["recovery_state_transition:<event_id>", "execution_attempt:<event_id>"]
result: "escalated"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`. The `RecoveryRecord.to_dict()` is the canonical serialisation of the in-memory record; the audit log carries a structured snapshot per transition.

---

## Edge cases

- **Atomic write crash mid-temp-write** (`state/helpers/atomic_write.py`): the helper guarantees no partial state at the target path. A `*.tmp` file may exist in the same directory; it is **diagnostic evidence**, not corruption. Do not auto-delete; rename to `state/decisions/<task>-recovery-evidence-<ts>.tmp` if you need a clean directory, or leave for the next successful write (the random prefix avoids collision).
- **Recovery during another recovery** (nested recovery): the state machine allows only one `RecoveryRecord` per task at a time. A second `begin_recovery` on the same `task_id` while the first is not `COMPLETED` or `FAILED` should be rejected by the orchestrator's outer state machine (the task is in `RECOVERING`; see `orchestrator/foundation/state.py`).
- **Authority re-check passes but the environment has drifted** (e.g. the file the action was about to write was concurrently changed): the `RecoveryRecord.validate_against_current_version` check catches state drift, but **file-level** drift on non-versioned files is not caught. This is a known limitation; the orchestrator should re-read the file's current sha256 immediately before the re-execution. A mismatch is a `logic` failure with a fresh cause, not a recovery continuation.
- **DSH approval `unavailable` mid-execution**: the backstop fired (no Human answerer). The action halts at the gate's runtime layer; `failure_class = "authorization"`. Recovery cannot re-attempt under the same delegation without a Human — escalate.
- **`stopReason == "max-tokens"`**: this is a budget exhaustion, not an authority issue. The `failure_class = "environment"` recovery may replan with a smaller prompt or split the action; the original delegation remains valid. Note that the orchestrator's session may itself be at risk; an `interrupt_agent` may be needed if the model is mid-generation.
- **Recovery that itself raises `RecoveryError`**: surface as `FAILED`, escalate. Do not attempt to fix the recovery state machine in-band; that is a code change, not a runtime recovery.

---

## References

- AUTH-INV-05/11/12/14/16/20
- THREAT-008/009/010/016/017/022/024/025
- security spec §11 (Recovery Assurance), §13 (REC-001..003, VERIFY-001..003), §16 (Verification and Recovery)
- threat model §16 (Verification and Recovery)
- design doc §14 (Execution gate), §19 (Recovery)
- `state/helpers/recovery.py` (entire module — the recovery state machine)
- `state/helpers/atomic_write.py` (atomic write + safe read + CAS)
- `state/helpers/version_check.py` (version read, monotonicity, staleness)
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`
- `tests/control_plane.py::authorize` (the gate that authorised the failed action)
- `tests/unit/test_recovery.py` (recovery state machine tests)

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
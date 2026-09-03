# Runbook 09 — Stale State

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/07-execution-failure.md` · `docs/runbooks/08-recovery-failure.md` · `docs/security/0001-control-assurance-spec.md` §2 (INV-05/13/14), §3.3, §13 (ST-/PST-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-021/022), §7 · `docs/design/0001-control-design-and-test-plan.md` §12, §13 · `state/helpers/version_check.py` (entire module) · `state/helpers/atomic_write.py::compare_and_swap` · `state/helpers/recovery.py::validate_against_current_version`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to **stale project state** — the orchestrator (or a specialist) read a state file at one version, but the current on-disk version has advanced (or rolled back). Stale reads can produce lost updates (THREAT-021) or recovery against an obsolete plan (THREAT-022). The response: re-read, re-validate authority, retry with a new cause (no blind retry).

---

## What this runbook covers

Project state files in `state/` carry a monotonic `version` integer. Every write uses `compare_and_swap` (`state/helpers/atomic_write.py::compare_and_swap`):

- Read current version.
- If matches `expected_version`, write with `version = expected_version + 1` (strict monotonicity).
- Otherwise raise or return `(False, current_version)`; the caller re-reads and re-validates.

A **stale state** event is one of:

| Signal | Meaning |
|---|---|
| `compare_and_swap` returns `(False, current_version)` | The writer's `expected_version` did not match the file's current version. A parallel writer advanced the file first. |
| `version_check.py::is_stale(path, expected_version)` returns `(True, current, expected, reason)` | Same as above, with a structured reason. |
| `version_check.py::assert_current_version(...)` raises `StaleStateError` | Critical path — same root cause, raised because the caller required fail-loud (e.g. authority re-check before execution). |
| `RecoveryRecord.validate_against_current_version(...)` raises `RecoveryDenied` | Recovery planned against an older version; current version is newer (THREAT-022). |
| `version_check.py::validate_version_monotonic(current, next)` raises `ValueError` | A writer proposed a non-strict-monotonic successor (reuse or skip). Strict monotonicity is enforced — reuse is impossible. |

Stale state is **not** corruption; it is concurrency. The state file is intact; the reader's view is behind. The response is re-read + re-validate; the response is **never** to overwrite a stale read (AUTH-INV-05, INV-13).

A **rolled-back state** (current version is *older* than the writer's expected) is a different alarm: a state file was replaced by an older copy. This is an integrity event (the protected-path execution gate prevents accidental writes; a deliberate rollback is a Human-issued action recorded in audit). Treat rolled-back state as Runbook 10 territory until provenance is established.

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| `compare_and_swap` returned `(False, current_version)` | the call site that issued the write |
| `StaleStateError` raised by `assert_current_version` | the call site that required fail-loud |
| `RecoveryDenied` raised by `validate_against_current_version` (THREAT-022) | the recovery lifecycle (Runbook 08) |
| `ValueError` from `validate_version_monotonic` | a writer attempted a non-monotonic successor |
| `audit/` event with `event_class == "state_drift"` (if the orchestrator records it) | `audit/helpers/append_log.py::read_events_by_class` |
| A `version_conflict` event in the audit chain (legacy: ST-002 in the test matrix) | `audit/helpers/append_log.py` |

**Read in this order:**

1. The signal itself. Capture `path`, `expected_version`, `current_version`, the caller's identity (which writer/reader triggered the check).
2. The `reason` from `is_stale` — `"state file missing or corrupt"`, `"state is OLDER than expected"`, or `"state is NEWER than expected"`. This tells the orchestrator whether the state is missing, rolled back, or concurrently advanced.
3. The on-disk file's current `version` (re-read via `version_check.py::read_version`).
4. The orchestrator's current planned state (the orchestrator's working memory). The plan was built against `expected_version`; the new state has a different version, so the plan may be obsolete.
5. The audit chain slice: any recent `state_transition` events for this file. A `state_transition` event at the new version explains *who* advanced the state (most often another specialist or a parallel orchestrator action).

---

## STOP

1. **Halt the action that read the stale state.** A read followed by a write on the basis of that read is a lost-update waiting to happen (THREAT-021). Do not proceed with the planned write.
2. **Cancel any queued sub-steps** that depend on the stale read.
3. **Do not** blindly overwrite. The temptation is to retry the write with the new current version; that is **not** a blind retry, but it requires re-validation of authority (next section). It is a *new* action with a *new* cause, not a continuation.
4. **Lock the staleness in audit** with `event_class == "state_drift"` (or `version_conflict` if the existing taxonomy is in use), `path`, `expected_version`, `current_version`, `reason`, `caller`. This is a record, not authority (AUTH-INV-14).

---

## PRESERVE

1. **Snapshot the stale read** the caller was operating on (the orchestrator's working memory; the data it had read at `expected_version`).
2. **Re-read** the current state at `current_version` via `state/helpers/atomic_write.py::safe_read` (fail-closed: returns `None` on missing/corrupt). The re-read is the basis for the next decision.
3. **Snapshot the diff** between the stale read and the re-read. Use deterministic JSON serialisation (`json.dumps(..., sort_keys=True, separators=(",", ":"))`) so the diff is reproducible. Record the diff in working memory; the orchestrator will surface it to the Human if escalation is required.
4. **Capture `before.sha256`** of the state file at `current_version` (sha256 externally; do not write to `state/`).
5. **Persist the stale read** (in `state/decisions/<task>-stale-read-<ts>.json` via `atomic_write`) — this is non-protected, non-authority data, durable evidence of what the caller was operating on.

> Do **not** write to `state/registry/` or `audit/`. The orchestrator's session is not the trusted writer for `state/registry/` (ADR 0002); the audit chain is append-only via `audit/helpers/append_log.py::append_event`.

---

## DIAGNOSE

Map the staleness to one of the documented failure classes (`recovery.py::RecoveryRecord.failure_class`):

| Stale-state reason | Root cause | `failure_class` |
|---|---|---|
| `"state is NEWER than expected (lost update detected)"` | A parallel writer advanced the file between the orchestrator's read and write. The orchestrator's plan was correct at `expected_version`; the state moved on. | `logic` (the orchestrator's read was racy; the writer's CAS caught it). |
| `"state is OLDER than expected (rolled back or replaced)"` | The file was replaced by an older copy. This is **not** normal concurrency — it is either a Human-issued rollback or a tampering event. | `authorization` (Human rollback is an authority action) or `unknown` (if provenance is missing). |
| `"state file missing or corrupt (treated as absent)"` | `safe_read` returned `None`. The file is absent or unreadable. | `environment` (IO/permission) or `authorization` (deliberate removal). |
| `RecoveryDenied` from `validate_against_current_version` | A recovery plan was prepared against `expected_version`; the current version has advanced past it. THREAT-022 — recovery cannot replay an obsolete plan on newer state. | `authorization` (the recovery cannot acquire privilege by replay). |
| `ValueError` from `validate_version_monotonic` | A writer proposed a non-monotonic successor. Strict monotonicity is enforced — this is a logic bug in the writer, not a concurrency event. | `logic`. |

**Diagnostic rule**: a stale read is **never** a reason to silently proceed. Re-read, re-plan, or escalate — never assume the previous plan still applies.

---

## RECOVER / ESCALATE

The recovery lifecycle for stale state is:

```text
STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER (skip — nothing to roll back; state is consistent) →
  REPLAN (with the re-read) → AUTHORITY RE-CHECK (against current state) →
  COMPLETED or FAILED
```

For most stale-state events, **rollback is not appropriate** — the state file is consistent at the new version; only the orchestrator's view was stale. The recovery is to *re-plan* under the new version.

**For "NEWER" (lost update, parallel writer) — `failure_class = logic`:**

1. **Re-read** the state at the new `current_version` (`safe_read`).
2. **Re-validate** the orchestrator's plan against the new state. The plan may now be obsolete (the new state may already reflect the action the orchestrator was about to take, or may have changed the conditions under which the action was valid).
3. **If the plan is still valid** under the new state, **re-issue** with a **new cause** (`recovery.py::RecoveryRecord.can_retry(max_attempts, new_cause)` requires `new_cause != diagnosed_cause` — AUTH-INV-16). The "new cause" is `"parallel_writer_advanced_state"`; the action proceeds under the same delegation id but against the **current** state version. The CAS write will use `expected_version = current_version` and `new_version = current_version + 1`.
4. **If the plan is no longer valid** under the new state, the orchestrator must re-plan. A new `task_id` may be opened for the new plan; the old task's history is preserved in audit. Escalate if the re-plan exceeds the rework bound (`max_rework_cycles`, default 2).

**For "OLDER" (state rolled back) — `failure_class = authorization` or `unknown`:**

1. **Verify provenance**. A state rollback can only be legitimate if (a) it was a Human-issued action recorded in audit, (b) it was a recovery's `rollback()` call (Runbook 07) recorded in `recovery_state_transition` events, or (c) it was an `atomic_write` from a sanctioned writer (orchestrator or writer channel). Anything else is tampering.
2. **If provenance is verified**, the orchestrator proceeds under the rolled-back state. The orchestrator's prior plan was prepared against the newer version; it is now obsolete relative to the on-disk state. Re-plan or escalate.
3. **If provenance is missing or `actor_type != human`**, this is a Runbook 10 incident. Do not proceed; the state file may have been tampered with. Escalate as `tampering_suspected`.

**For "missing/corrupt" — `failure_class = environment` (most cases):**

1. **Re-create** the state file from the orchestrator's working memory if the file was missing. Use `atomic_write` with `version = 1` (initial version; strict monotonicity is irrelevant for an absent file).
2. **If the file is corrupt**, do not auto-repair — corrupt is not missing. Escalate as `unknown`; the orchestrator cannot reason about a file it cannot parse.

**For `RecoveryDenied` (THREAT-022) — `failure_class = authorization`:**

1. The recovery is in `RECOVERING` (Runbook 08). The state machine refuses the recovery (`RecoveryDenied`).
2. **Re-read** the current state at `current_version`.
3. **Re-validate authority** with the new state version. The recovery's `preserved_version` is older than `current_version`; the recovery may roll forward (never re-run on newer state) — so the orchestrator creates a **new** `RecoveryRecord` with `preserved_version = current_version` and a new cause naming the state drift. The old `RecoveryRecord` is preserved at `FAILED`.

**Headless / CI behaviour**: identical to prior runbooks — the action halts on `FAILED`; the escalation event is recorded.

---

## VERIFY

1. **`compare_and_swap` succeeds** on the re-issued write with `new_version = expected_version + 1` (strict monotonicity). The CAS return is `(True, new_version)`.
2. **Audit chain integrity** holds across the `state_drift` event, the re-read event, and the re-issued write event.
3. **No non-monotonic writes**: `validate_version_monotonic` accepts every version pair in the audit chain (i.e. no event has `version == previous_version` or `version > previous_version + 1`). If a non-monotonic transition appears, that is a Runbook 10 incident (writer bug or tampering).
4. **Plan still valid under new state**: the re-validation passed; the orchestrator's gate accepted the action under the same delegation id with the **current** state version.
5. **State file atomicity**: `state/helpers/atomic_write.py::atomic_write` left the file in a complete state — `safe_read` returns a valid JSON object with the expected `version`. A `*.tmp` file in the same directory is acceptable (atomic-write crash) but not a half-written target.

---

## REPORT

**Event 1 — the state drift** (always):

```text
event_class: "state_drift"
actor: "orchestrator" | "<writer role id>"
actor_type: "agent"
action: "compare_and_swap" | "validate_against_current_version" | "assert_current_version"
target: "<state file path>"
expected_version: <int>
current_version: <int>
reason: "state_is_newer" | "state_is_older" | "state_missing_or_corrupt" | "non_monotonic_version"
failure_class: "environment" | "logic" | "authorization" | "unknown"
result: "stale_detected"
timestamp: "<UTC ISO 8601>"
```

**Event 2 — the re-read** (one event per re-read):

```text
event_class: "state_read"
actor: "<reader role id>"
action: "safe_read"
target: "<state file path>"
version: <current_version after re-read>
sha256: "<hex>"
result: "read" | "missing" | "corrupt"
timestamp: "<UTC ISO 8601>"
```

**Event 3 — the recovery plan** (one event per re-plan):

```text
event_class: "recovery_state_transition"
target: "<task_id>"
recovery_record_id: "<uuid>"
state: "REPLANNED"
new_cause: "<string; differs from diagnosed_cause>"
expected_version: <current_version>
result: "replanned"
```

**Event 4 — the re-issued write** (one event per successful CAS):

```text
event_class: "state_transition"
actor: "<writer role id>"
action: "compare_and_swap"
target: "<state file path>"
previous_version: <current_version>
new_version: <current_version + 1>
authority_source: "<delegation id>"
result: "committed"
timestamp: "<UTC ISO 8601>"
```

**Event 5 — escalation** (if escalated):

```text
event_class: "escalation"
action: "escalate_stale_state"
target: "<state file path>"
expected_version: <int>
current_version: <int>
reason: "state_is_older" | "state_missing_or_corrupt" | "state_drift_unresolvable"
human_signoff_required: true
evidence: ["state_drift:<event_id>", "state_read:<event_id>", ...]
result: "escalated"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **Stale read on `state/registry/`** (a delegation or revocation record): the protected-path execution gate prevents the orchestrator's session from writing it, so the orchestrator's staleness is a *read* staleness only. Re-read and re-evaluate; the gate's authority decision will reflect the current registry.
- **Stale read on `audit/`**: the audit chain is append-only. A "stale read" on audit is meaningless — every read sees the full chain to date. If the orchestrator believes audit is stale, it is misreading; the chain only grows. Re-read entirely; do not cache.
- **Parallel writers**: the orchestrator is documented as the single authoritative writer for `state/projects/**` (state spec; threat model §7.3). If a parallel writer is observed, that is itself a violation — escalate as `unknown` with `reason = "parallel_writer_detected"`. The recovery should not normalise a violation.
- **Repeated stale reads** (the same call site hits stale three times in a row): this is a runaway loop pattern; the orchestrator's outer state machine must bound the retries. Escalate regardless.
- **`current_version == 0`** (`safe_read` returns `None` or a file with no `version`): treat as the file being absent. Initial version is `1`; the next `atomic_write` sets it. A `compare_and_swap` against a `current_version == 0` should `safe_read` first; if the file does not exist, the orchestrator's writer channel may create it.
- **State file that disappeared mid-recovery** (`safe_read` returned a dict at PRESERVE, `None` at REPLAN): escalate as `unknown`; the orchestrator cannot recover against a vanished file.

---

## References

- AUTH-INV-05/14/20
- THREAT-021/022
- security spec §3.3 (delegation lifecycle, stale-read handling), §13 (ST-/PST-*), §14 (assurance)
- threat model §7 (State Integrity), §7.3 (Optimistic concurrency)
- design doc §12 (Workflow state transitions), §13 (Project state)
- `state/helpers/atomic_write.py::compare_and_swap`, `safe_read`, `atomic_write`
- `state/helpers/version_check.py::read_version`, `is_stale`, `assert_current_version`, `validate_version_monotonic`
- `state/helpers/recovery.py::validate_against_current_version`, `can_retry`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
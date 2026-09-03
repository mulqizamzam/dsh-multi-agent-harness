# Runbook 02 — Expired Delegation

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/security/0001-control-assurance-spec.md` §2 (INV-13), §3.2, §5 · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-008), §6.2 · `docs/design/0001-control-design-and-test-plan.md` §6 · `tests/control_plane.py::is_expired` · `tests/authorization/test_authority.py::test_auth_003`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a denial where the root cause is **delegation expiry** (AUTH-INV-06, THREAT-008). Builds on Runbook 01's general denial flow; this runbook specialises it.

---

## What this runbook covers

A **delegation has `expires_at` set, the wall clock is past that timestamp, and the authority gate denied an action under that delegation**. The denial reason is `delegation expired (AUTH-INV-06)`. The delegation may have been valid at planning time and become invalid before execution (THREAT-008) — the authority gate re-checks expiry at execution time exactly to close that race.

Expiry is distinct from revocation (Runbook 03): expiry is the natural end-of-life of a scoped grant; revocation is an active withdrawal. The recovery posture differs (expiry may not need a Human re-grant if a successor delegation is already in place).

---

## DETECT

**Source signals (any one triggers this runbook; root-cause match on `delegation expired`):**

| Signal | Source |
|---|---|
| `Deny("delegation expired (AUTH-INV-06)")` from `tests/control_plane.py::authorize` | control-plane gate |
| `audit/` event with `event_class == "execution_denial"`, `result == "denied"`, and the gate's reason matches `expired` | `audit/helpers/append_log.py` |
| `audit/` event with `event_class == "authority_expired_check"` (if the orchestrator records the expiry check separately) | orchestrator working memory |
| A delegations read by `state/helpers/atomic_write.py::safe_read("state/registry/delegations.yaml")` returns a record whose `expires_at` is in the past relative to `datetime.now(timezone.utc)` (compare via `tests/control_plane.py::is_expired`) | registry read |

**Detection discipline:** do **not** rely on a model claim that "the delegation is expired." Expiry is a property of the registry record and the wall clock, both observable by reading the registry with the safe-read helper and comparing ISO timestamps. The orchestrator's role is to perform the read + comparison, not to assert expiry from prose.

---

## STOP

Same as Runbook 01:

1. **Halt the in-flight action.** Do not retry the same action under the same expired delegation.
2. **Cancel any queued sub-steps** that depended on the denied action (`interrupt_agent`, `job_kill`).
3. **Do not auto-extend.** No self-escalation (AUTH-INV-02/03). The orchestrator must not write `expires_at` into the future; the delegation registry is single-writer (Human) and writers do not include the orchestrator's session for that field (ADR 0002 protected-path on `state/registry/`).
4. **Lock the deny in audit** with `event_class == "execution_denial"`, `result == "denied"`, `error = "delegation expired (AUTH-INV-06)"`, `authority_source = <expired delegation id>`.

---

## PRESERVE

1. **Read the expired delegation** from `state/registry/delegations.yaml` using `state/helpers/atomic_write.py::safe_read` (fail-closed: `None` on missing/corrupt → treat as "no delegation", which is also a denial). Capture:
   - `id`, `principal`, `delegate`, `project`, `scope` (operations/resources/environments), `prohibited_actions`, `requires_approval`, `expires_at`, `approval_reference` (if any), `status`, `version`, `created_at`, `updated_at`, `revoked_at`.
   - The **wall clock at detection time** (`datetime.now(timezone.utc).isoformat()`), frozen.
2. **Capture `before` hashes** of `state/registry/`, `audit/`, and any `state/projects/` files the action would have touched. Same procedure as Runbook 01 §PRESERVE.
3. **Capture the registry version** (`state/helpers/version_check.py::read_version`) — the version that was current when the expired record was read.

> Note: an expired delegation is **still a valid registry record**. The registry itself is unchanged. Do **not** mutate the expired record; this is a Human-grant operation. The orchestrator's job is to surface, not to amend.

---

## DIAGNOSE

| Diagnostic question | How to answer | Outcome |
|---|---|---|
| Is the action still in scope of the (expired) delegation? | Re-evaluate `target_in_scope(target, scope.resources)` from `tests/control_plane.py` with the frozen registry record | If **yes**, a successor delegation with the same scope would suffice. If **no**, the request itself must be re-scoped (not just re-granted). |
| Is a successor delegation already in place? | `safe_read` the registry and look for a delegation with the same `delegate`, overlapping `scope.resources`, non-revoked, and `expires_at > now` | If **yes**, the action may proceed under the successor — re-issue through the gate with the successor id; **do not** assume scope equivalence, the gate will re-validate. If **no**, escalate. |
| Did the action time out before the Human could respond? | Compare the denial timestamp with the originating task's `created_at` | If yes, the action's expected lifetime exceeded the delegation's — design feedback for the next delegation. |
| Is `now` within the `expires_at` grace period the orchestrator may apply? | There is **no** grace period in V1 (`tests/control_plane.py::is_expired` returns `True` immediately after `expires_at`); if the Human has documented a grace elsewhere, follow it — otherwise treat as expired. | Drives the escalate-vs-retry decision below. |

`failure_class` is **authorization** (a delegation expired; it is the registry that authorises, not the orchestrator's judgment). Set `failure_class = "authorization"` on any `RecoveryRecord` created.

---

## RECOVER / ESCALATE

The orchestrator **does not recover from an expiry by itself**. The choice is between **escalating to the Human for a fresh grant** and **re-issuing under an existing successor delegation** if one is in scope.

1. **If a successor delegation exists, is ACTIVE, and covers the action/target/environment**, **re-issue the action under the successor delegation's id**.
   - Re-evaluate the full pre-execution checklist (design doc §14 / threat model §8) with the successor delegation. The original gate run's denial is final for the *original* delegation; the new run is a fresh authority evaluation, not a retry of a denied action.
   - Append a new audit event: `event_class == "authority_re_evaluated"`, `result == "reissued_under_successor"`, `previous_delegation_id = <expired id>`, `new_delegation_id = <successor id>`. This is a **record**, not a grant (AUTH-INV-14).
   - Do not skip the gate. The gate is the only place scope is checked (AUTH-INV-05, AUTH-INV-11).

2. **If no successor covers the action**, **escalate to the Human** with:
   - `event_class == "escalation"`, `reason = "delegation_expired"`, `action`, `target`, `expired_delegation_id`, `expires_at`, `detection_ts`, `human_signoff_required = true`.
   - Surface the **suggested new delegation** (`scope`, `environments`, `expires_at`) — this is a *recommendation* the Human may accept, modify, or reject. The orchestrator does not write the new delegation itself; the Human (or a Human-approved process) is the trusted writer (ADR 0002).

3. **If the Human cannot respond in time** (e.g. async environment) and the action is **non-HIGH risk**, the action waits. There is no implicit allow.

4. **In headless / CI environments** with no Human answerer, the action halts and the escalation event is recorded. There is no fallback that grants authority without a Human (AUTH-INV-04; the gate is fail-closed).

---

## VERIFY

1. **On-disk state hash unchanged** for any file the action would have touched (`before.sha256 == after.sha256`). Compute via `audit/helpers/integrity.py::detect_truncation` shape (sha256 comparison) without writing to `state/` or `audit/`.
2. **Audit chain integrity** holds: `audit/helpers/integrity.py::verify_chain` clean.
3. **Registry integrity**: `state/registry/delegations.yaml` was **not mutated** by the orchestrator's session. The protected-path execution gate (ADR 0002 / `control/execution_gate.py`) prevents writes; this verification confirms it. The expired record is still on disk with the same `expires_at`, `version`, and `status` it had before the denial.
5. **No partial execution**: if the successor delegation was used, verify the side-effect (e.g. the file the action wrote) carries the **successor's** `authority_source` in the audit event, not the expired one's.

If verification fails, halt and escalate (`event_class == "escalation"`, `reason = "post_expiry_verification_failed"`).

---

## REPORT

Two events are required when escalation occurs (one when a successor is used):

**Event 1 — the denial itself** (always, by Runbook 01):

```text
event_class: "execution_denial"
result: "denied"
error: "delegation expired (AUTH-INV-06)"
authority_source: "<expired delegation id>"
previous_state: <before hashes>
new_state: <after hashes; must equal previous_state on a clean denial>
```

**Event 2a — re-issued under successor** (if a successor was used):

```text
event_class: "authority_re_evaluated"
result: "reissued_under_successor"
action: <original action>
target: <original target>
previous_delegation_id: <expired id>
new_delegation_id: <successor id>
new_state: <after hashes of the actual side-effect>
evidence: ["<reference to the original denial event_id>"]
```

**Event 2b — escalated to Human** (if no successor):

```text
event_class: "escalation"
action: "escalate_expired_delegation"
result: "escalated"
error: "delegation_expired; human_grant_required"
target: <original target>
authority_source: "<expired delegation id>"
evidence: ["<reference to the denial event_id>"]
suggested_scope: { operations: [...], resources: [...], environments: [...] }
suggested_expires_at: "<ISO timestamp>"
```

Both branches record **data**, not authority (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event` with a non-empty `event_id`, sorted-keys JSON for stable hashing, and atomic temp-write semantics for the chain update.

---

## Edge cases

- **Expiry set to `null` in the registry**: a delegation without `expires_at` is **not** expired by time (it is still subject to revocation; Runbook 03). If the gate fires `delegation expired` against a `null` `expires_at`, that is a registry corruption: treat as `no delegation` and escalate (`reason = "registry_inconsistency"`).
- **Clock drift** between the orchestrator's host and the registry's host: a registry record timestamped in the future relative to the orchestrator's clock will look "not yet expired" on the orchestrator but is **expired** from the registry's perspective. The current primitives compare ISO timestamps in UTC (`is_expired` parses `expires_at.replace("Z", "+00:00")`); use UTC end-to-end and freeze the clock for forensics.
- **Expired-but-revoked overlap**: a record may be both expired and on the revocation list. The gate fails on the first matching rule; either cause is sufficient. Report whichever fired; the recovery is the same (escalate or re-issue under successor).

---

## References

- AUTH-INV-05/06/11/13/14/20
- THREAT-008/009/024
- `tests/control_plane.py::is_expired`, `authorize`, `target_in_scope`
- `tests/authorization/test_authority.py::test_auth_003_expired_delegation`
- `state/helpers/atomic_write.py::safe_read`
- `state/helpers/version_check.py::read_version`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`, `detect_truncation`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
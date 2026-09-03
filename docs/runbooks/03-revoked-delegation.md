# Runbook 03 — Revoked Delegation

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/runbooks/02-expired-delegation.md` · `docs/security/0001-control-assurance-spec.md` §2 (INV-13), §3.3, §5 · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-009), §6.2 · `docs/design/0001-control-design-and-test-plan.md` §6 · `tests/control_plane.py::authorize` (revocation_list parameter) · `tests/authorization/test_authority.py::test_auth_004_revoked_delegation`
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a denial where the root cause is **delegation revocation** (AUTH-INV-06, THREAT-009). Builds on Runbook 01's general denial flow and Runbook 02's expiry handling.

---

## What this runbook covers

A **delegation has been revoked by the Human** (or a Human-approved process) — its id appears in the revocation list — and the authority gate denied an action under that delegation. The denial reason is `delegation revoked (AUTH-INV-06)`.

A revocation may have occurred **between planning and execution** (THREAT-009), or before any action. The authority gate re-checks the revocation list at execution time exactly to close that race (AUTH-INV-05). A revoked delegation is **not re-issuable** under the same id; a *new* delegation id must exist for the action to be authorised (the revoked id remains revoked).

---

## DETECT

**Source signals (any one triggers this runbook; root-cause match on `delegation revoked`):**

| Signal | Source |
|---|---|
| `Deny("delegation revoked (AUTH-INV-06)")` from `tests/control_plane.py::authorize` with `revocation_list` containing the supplied delegation id | control-plane gate |
| `audit/` event with `event_class == "execution_denial"`, `result == "denied"`, error matches `revoked` | `audit/helpers/append_log.py` |
| `state/registry/revocations.yaml` (or co-located revocation list) contains the delegation id, AND that id was the `authority_source` of the attempted action | `state/helpers/atomic_write.py::safe_read` (fail-closed: missing/corrupt → treat as no revocations on disk; in-memory revocation list is the gate's source of truth) |
| A `revocation_event` was recorded prior to the attempt (event_class contains `revocation` per the audit schema enum) | `audit/helpers/append_log.py::read_events_by_class("revocation")` |

**Detection discipline:** the gate's in-memory `revocation_list` parameter is the **authoritative source at evaluation time** (the registry read at planning may be stale). Confirm by reading both: the on-disk revocation list (via `safe_read`) and the in-memory snapshot (via the gate's call site). They must agree; a mismatch is a registry/version drift (Runbook 09).

---

## STOP

Same as Runbook 01 and Runbook 02:

1. **Halt the in-flight action.** Do not retry the same action under the same revoked id.
2. **Cancel any queued sub-steps** that depended on the denied action.
3. **Do not un-revoke.** The orchestrator has no path to remove an id from the revocation list (single-writer; protected path; AUTH-INV-02). Only the Human (or Human-approved process) revokes; only the Human may *re-grant*, and a re-grant is a *new* delegation id, not a resurrection of the revoked one.
4. **Lock the deny in audit** with `event_class == "execution_denial"`, `result == "denied"`, `error = "delegation revoked (AUTH-INV-06)"`, `authority_source = <revoked delegation id>`, plus `evidence: ["revocation_event:<event_id of the revocation>"]`.

---

## PRESERVE

1. **Read the revoked delegation** from `state/registry/delegations.yaml` using `state/helpers/atomic_write.py::safe_read`. Confirm `status == "REVOKED"`, `revoked_at` is set, and the registry `version` is current. (If the record is missing, treat as `no delegation` — the gate's revocation check still applies via the revocation list.)
2. **Read the revocation record** that withdrew this id — its source, the Human session id (or process id) that issued it, and its `revoked_at` timestamp. This is required to detect a forged revocation (Runbook 10).
3. **Capture `before` hashes** of `state/registry/`, `audit/`, and any file the action would have touched. Same procedure as Runbook 01 §PRESERVE.
4. **Snapshot the revocation list** as it stood at detection time (file hash + parsed ids). The orchestrator's session must not have written to this list (ADR 0002 protected path). If the on-disk revocation list and the gate's in-memory list disagree, **escalate immediately** (`reason = "revocation_list_drift"`) before doing anything else.

> Note: a revoked delegation is **still a valid registry record**. It stays on disk so the gate's id-lookup works, with `status == "REVOKED"` and `revoked_at` populated. Do **not** delete revoked records during recovery — deletion is a registry-write that the orchestrator's session cannot perform.

---

## DIAGNOSE

| Diagnostic question | How to answer | Outcome |
|---|---|---|
| Did the revocation occur **after** the orchestrator's plan read? | Compare `revoked_at` (from the revocation record) with the originating task's `created_at` and the gate's last successful planning-time read | If **yes**, the plan was correct at planning time; this is the classic THREAT-009 race. The gate closed it correctly. No logic error in the orchestrator; record and escalate. |
| Did the revocation occur **before** the action was planned? | Same comparison; `revoked_at < created_at` | The orchestrator should not have planned the action. Audit the planner — this is a logic bug (the planner used a stale registry read). |
| Was the revocation legitimate (Human / Human-approved)? | Trace the revocation record to its `principal == human` provenance; confirm the revocation event matches a Human answerer (DSH `approval/asked` + `decided = allowed-once` for category `revocation`, or a Human-issued record in the registry) | If **yes**, escalation. If **no** (the revocation record lacks Human provenance), this is a critical incident — a forged revocation (THREAT-018 adjacent) — escalate with `reason = "forged_revocation"` and **do not** accept the revocation; see also Runbook 10. |
| Is a successor delegation already in place? | Same as Runbook 02 §DIAGNOSE | If **yes**, re-issue under the successor (the revoked id must not be reused). If **no**, escalate. |
| Does the orchestrator's session have write capability to `state/registry/`? | Check by attempting (in a denied channel) and confirming `Deny`; the protected-path execution gate prevents writes from any non-writer actor. | If the gate does not fire (unauthorized write succeeds), this is a Runbook 04 — Protected Path violation, **not** a revocation runbook. |

`failure_class = "authorization"` on any `RecoveryRecord` created.

---

## RECOVER / ESCALATE

The orchestrator **does not un-revoke and does not resurrect the revoked id**. The choices are:

1. **Re-issue under a successor delegation** (if one exists, is ACTIVE, and covers action/target/environment). Same procedure as Runbook 02:
   - Re-evaluate the full pre-execution checklist with the successor's id.
   - Append `event_class == "authority_re_evaluated"`, `result = "reissued_under_successor"`, `previous_delegation_id = <revoked id>`, `new_delegation_id = <successor id>`. Record, not grant (AUTH-INV-14).
2. **Escalate to the Human** with:
   - `event_class == "escalation"`, `reason = "delegation_revoked"`, `revoked_delegation_id`, `revoked_at`, `detection_ts`, `human_signoff_required = true`.
   - Include the `suggested_new_scope` if the orchestrator has one — again, a recommendation only. The Human may choose to re-grant under a new id or to leave the action un-performed.
3. **If a forged revocation is suspected** (provenance check failed): **HALT** (do not re-issue, do not auto-recover). Surface immediately with `reason = "forged_revocation_suspected"`. This requires Runbook 10 — Audit Integrity Failure to verify the revocation's chain entry. Recovery from a forged revocation is not a Phase-2 runbook decision; it is a security incident.

**Headless / CI behaviour**: identical to Runbook 02 — the action halts, the escalation event is recorded, no implicit allow.

---

## VERIFY

1. **On-disk state hash unchanged** for files the action would have touched.
2. **Audit chain integrity** holds (`audit/helpers/integrity.py::verify_chain` clean). In particular, verify that the revocation event itself is present in the chain and that its `actor` is `human` and its `actor_type` is `human`. A revocation event authored by an `actor_type == agent` is the **forged-revocation** case and must trigger Runbook 10.
3. **Registry integrity**: the revoked delegation record is still on disk with `status == "REVOKED"` and `revoked_at` populated. The registry `version` was not advanced by the orchestrator's session.
4. **Revocation list integrity**: `state/registry/revocations.yaml` (or co-located) was not mutated by the orchestrator. Same on-disk vs in-memory consistency check.
5. **No partial execution**: if a successor delegation was used, verify the side-effect carries the successor's `authority_source` in audit.

---

## REPORT

**Event 1 — the denial** (always):

```text
event_class: "execution_denial"
result: "denied"
error: "delegation revoked (AUTH-INV-06)"
authority_source: "<revoked delegation id>"
evidence: ["revocation_event:<event_id>"]
previous_state: <before hashes>
new_state: <after hashes; equal to previous_state on clean denial>
```

**Event 2a — re-issued under successor**:

```text
event_class: "authority_re_evaluated"
result: "reissued_under_successor"
previous_delegation_id: "<revoked id>"
new_delegation_id: "<successor id>"
new_state: <after hashes of side-effect>
evidence: ["<reference to the original denial event_id>"]
```

**Event 2b — escalated to Human**:

```text
event_class: "escalation"
action: "escalate_revoked_delegation"
result: "escalated"
error: "delegation_revoked; human_grant_required"
authority_source: "<revoked delegation id>"
evidence: ["revocation_event:<event_id>", "<reference to the denial event_id>"]
suggested_scope: { ... }
```

**Event 2c — forged-revocation suspected** (security incident):

```text
event_class: "escalation"
action: "escalate_forged_revocation_suspected"
result: "escalated_security_incident"
error: "revocation_event_failed_provenance_check"
authority_source: "<revoked id>"
evidence: ["revocation_event:<event_id>", "agent_actor_in_revocation:<actor_id>"]
human_signoff_required: true
halt_pipeline: true
```

All events are records, never grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **Revocation recorded after the action completed**: out-of-order authority outcome (THREAT-024). The gate's execution-time re-check still closes this — the revocation is consulted on the *next* action under the same id, which is denied. There is no retroactive unwinding; the original side-effect remains and is recorded with the now-revoked delegation's `authority_source`. The Human reviews via the audit chain.
- **Self-revocation by an agent**: a `revocation_event` with `actor_type == agent` (THREAT-018 adjacent). Trigger Runbook 10. The orchestrator must **not** honor a revocation whose provenance is not `human` (the trusted writer); it must surface the forgery as a critical incident.
- **Revocation of an expired delegation**: the revocation may still be recorded. The gate fires whichever rule matches first (revocation is checked before expiry in `tests/control_plane.py::authorize`). The audit reason string will name the actual cause; report as the runbook covering the cause that fired.
- **Revocation list lost** (file missing or corrupt): `safe_read` returns `None`. The gate treats this as "no revocations on disk," but the **in-memory** revocation list passed to the gate by the orchestrator is still authoritative. A disagreement is `revocation_list_drift` and must escalate. Do not silently proceed; the absence of a file is not the absence of revocations.

---

## References

- AUTH-INV-02/03/05/06/11/14/20
- THREAT-009/018/024
- `tests/control_plane.py::authorize` (revocation_list parameter)
- `tests/authorization/test_authority.py::test_auth_004_revoked_delegation`
- `state/helpers/atomic_write.py::safe_read`
- `state/helpers/version_check.py::read_version`, `is_stale`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
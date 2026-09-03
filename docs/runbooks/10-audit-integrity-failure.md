# Runbook 10 — Audit Integrity Failure

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/runbooks/03-revoked-delegation.md` · `docs/runbooks/04-badsector-rework-reject.md` · `docs/security/0001-control-assurance-spec.md` §2 (INV-14), §12, §13 (AUD-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-018), §12 · `docs/design/0001-control-design-and-test-plan.md` §18 · `audit/helpers/integrity.py` (entire module) · `audit/helpers/append_log.py` (entire module)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a **detected breach of the audit ledger's integrity** — truncation, overwrite, reordering, corruption, blank line, duplicate `event_id`, forged event, chain break, or a missing event class that was supposed to be present. This is a **critical security incident**, not a soft warning.

---

## What this runbook covers

The project audit ledger (`audit/<project>/events.jsonl`) is append-only and chain-validated. Integrity violations detected by the existing helpers:

| Helper | Detects | Source |
|---|---|---|
| `audit/helpers/append_log.py::read_events_strict` | Blank line, corrupt JSON line | raises `AuditIntegrityError` |
| `audit/helpers/append_log.py::verify_append_only` | Corrupt line, duplicate `event_id`, out-of-order timestamp, sequence mismatch against `expected_event_ids`, count mismatch | returns `(ok: bool, problems: list[str])` |
| `audit/helpers/integrity.py::verify_chain` | Hash chain mismatch against the persisted side-car; chain length mismatch | raises `AuditIntegrityError` on first mismatch |
| `audit/helpers/integrity.py::detect_truncation` | Ledger shorter than a known-good line count; or same line count with a different cumulative hash (overwrite) | returns `(ok: bool, problems: list[str])` |
| `audit/helpers/append_log.py::append_event` | Event without a non-empty `event_id`; non-dict event | raises `TypeError` / `ValueError` |
| Schema validation (out-of-band) | Event not matching `schemas/audit-event.schema.json` | schema validator's error |

A failure at any of these points is a **critical alert** (security spec §12, threat model §3 / THREAT-018). The audit ledger is the durable record of authority decisions; an attacker who tampers with the ledger can rewrite accountability (THREAT-018) or forge approvals (AUTH-INV-14). The response is **stop, preserve evidence, escalate**, do not auto-repair.

**The audit ledger is never authority** (AUTH-INV-14; `audit/helpers/append_log.py::audit_is_authority_source` returns False regardless of input). A forged audit entry that *claims* an approval grants nothing — the authority gate reads the delegation registry + Human approval records, never audit. This runbook is therefore a **containment + escalation** runbook, not a recovery runbook.

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| `AuditIntegrityError` raised by `read_events_strict`, `verify_chain`, or `compute_chain` | call site |
| `verify_append_only` returned `(False, problems)` | the verifier call site (e.g. a periodic integrity sweep) |
| `detect_truncation` returned `(False, problems)` | the verifier call site |
| `append_event` raised `TypeError` / `ValueError` for a malformed event | the writer call site |
| A `state_drift` event on `audit/<project>/events.jsonl` itself (Runbook 09 territory) | `audit/helpers/append_log.py` |
| A `bad_sector_verdict` event whose provenance check failed (Runbook 04 handoff) | `tests/control_plane.py::verify_badsector_provenance` |
| A `revocation_event` whose `actor_type != human` (Runbook 03 handoff — forged revocation) | `audit/helpers/append_log.py::read_events_by_class("revocation")` |
| An out-of-band suspicion: an event whose content references a delegation id that is not in the registry, or whose `actor_type` does not match the operation (e.g. an `actor_type=agent` event of class `normal_approval`) | audit reader / cross-validation |

**Read in this order:**

1. The error message itself. `AuditIntegrityError` carries the line number and the chain key that mismatched; `verify_append_only`'s `problems` list names each violation.
2. The events file path and the side-car path (`audit/<project>/events.jsonl` and `audit/<project>/events.jsonl.chain`).
3. The first divergent line — that is the earliest evidence of tampering or corruption.
4. The last-known-good snapshot (if any). The chain head's `cumulative_hash` from the most recent `verify_chain` or `compute_chain` call is the baseline.
5. The orchestrator's current state — was a write in flight when the failure surfaced? A write that completed but produced an inconsistent state file is a separate incident.

---

## STOP

1. **Halt all writes to `audit/`** until the failure is triaged. The ledger is append-only; a write attempted while integrity is suspect may **extend** the tampered chain with new "evidence" of the tamper. Stop the writer.
2. **Halt the action that triggered the verification.** The verification is being run for a reason; until the reason is understood, do not proceed.
3. **Cancel outstanding sub-jobs** that may be in the middle of writing to `audit/`. (`interrupt_agent`, `job_kill`.)
4. **Do not** auto-repair the ledger. A repair overwrites the evidence (the first divergent line is the diagnostic; replacing it destroys the diagnostic). The chain must be **preserved as-is** until the Human reviewer triages.
5. **Lock the failure in audit** — but **only if the ledger is still writable** without extending the tampered chain. If the failure is at the writer (e.g. `append_event` rejected a malformed event), the rejection itself is recorded by the calling code's error path; no audit event is needed for the rejection. If the failure is at the verifier (`verify_chain`, `verify_append_only`), record:

   ```text
   event_class: "audit_integrity_failure"
   actor: "orchestrator"
   actor_type: "agent"
   action: "verify_chain" | "verify_append_only" | "detect_truncation" | "read_events_strict"
   target: "<events.jsonl path>"
   failure_kind: "chain_break" | "truncation" | "blank_line" | "corrupt_line" |
                 "duplicate_event_id" | "out_of_order_timestamp" |
                 "sequence_mismatch" | "count_mismatch" | "missing_event_class"
   first_divergent_line: <int>
   reason: "<string, the helper's error message>"
   result: "failed"
   ```

   If the failure is at the writer (a write was rejected), record `event_class = "audit_write_rejected"` with the same fields. **Do not** record a successful `audit_write_rejected` event for a tampered write — the rejection itself is the record.

6. **Quarantine the ledger** by renaming `events.jsonl` to `events.jsonl.quarantine-<ts>` via `os.rename` (no copy; the original path is preserved on the same filesystem; `audit_append` will create a fresh file on the next append if the path is restored). Do **not** delete the original.

---

## PRESERVE

The first divergent line is the diagnostic. Preserve everything.

1. **Quarantine the original** as above (`events.jsonl` → `events.jsonl.quarantine-<ts>`). The orchestrator's session has write capability to `audit/` only through the sanctioned `audit_append()` channel (`control/execution_gate.py::SANCTIONED_ROOTS` — Session-A hardening). The rename is a metadata operation on the same directory; it is not a write to a protected path's *contents*. If the rename is refused by the execution gate (the gate's path-classifier does not distinguish rename from write), use `os.rename` from a non-protected temp directory or escalate to the Human for the rename.
2. **Snapshot the side-car** (`events.jsonl.chain`) alongside the quarantine. Both files belong together.
3. **Compute the sha256** of the quarantined file (`<events>.sha256`) and the side-car (`<events>.chain.sha256`). These are non-protected metadata files in the same directory.
4. **Compute the line count** and the last `cumulative_hash` of the quarantined chain. These are the baseline numbers the Human reviewer will use to reconstruct the incident.
5. **Persist the diagnostic** to a non-protected path: `state/decisions/audit-integrity-<ts>.json` containing the failure kind, first divergent line, the helper's error message, the sha256 of the quarantine, the line count, the last cumulative hash, the orchestrator's current state, and any in-flight writes that were cancelled.
6. **Do not** modify the quarantined file. **Do not** modify the side-car. **Do not** re-run `compute_chain` on the quarantined file (that would persist a new side-car and overwrite the evidence).

---

## DIAGNOSE

Map the failure to one of the documented threat scenarios (threat model §3, §12):

| Failure kind | Likely root cause | Severity |
|---|---|---|
| `chain_break` (verify_chain mismatch at line N) | An entry was inserted, removed, or modified after line N. Could be tampering (THREAT-018) or a write that did not go through `append_event` (e.g. a raw file edit). | **CRITICAL** until proven otherwise. |
| `truncation` (line count dropped) | The file was truncated. Could be tampering (THREAT-018) or a cleanup script. | **CRITICAL**. |
| `blank_line` | A blank line was inserted into an append-only JSONL ledger. This is not normal; `append_event` never emits blanks. | **CRITICAL** — likely tampering. |
| `corrupt_line` | A line is not valid JSON. Could be tampering, disk corruption, or a partial write that landed before `append_event`'s `flush+fsync`. | **HIGH**. |
| `duplicate_event_id` | The same `event_id` appears twice. Could be a replay (THREAT-018) or a retry that did not generate a fresh id. | **HIGH**. |
| `out_of_order_timestamp` | An event's timestamp is earlier than its predecessor. Could be tampering, or a clock skew between writers (different timezones). | **HIGH**. |
| `sequence_mismatch` against `expected_event_ids` | A previously observed sequence is no longer present. Truncation or removal. | **CRITICAL**. |
| `count_mismatch` | The line count is not what was expected. Truncation or duplication. | **HIGH**. |
| `missing_event_class` (an event class that should have been emitted is not) | A gate did not fire, or a write was lost. | **HIGH**. |
| `audit_write_rejected` (append_event refused) | The orchestrator (or another writer) attempted to write a malformed event. The write never landed; the ledger is intact. | **MEDIUM** — usually a writer bug, not tampering. |
| `bad_sector_provenance_failed` | A BadSector PASS/REWORK/REJECT record does not trace to a real invocation. Forgery (THREAT-014). | **CRITICAL**. |
| `forged_revocation` (Runbook 03 handoff) | A revocation event with `actor_type != human`. Forgery (THREAT-018). | **CRITICAL**. |

`failure_class`:
- `environment` for disk corruption, partial writes, clock skew.
- `logic` for writer bugs (rejected append, retry without fresh `event_id`).
- `authorization` for any tampering or forgery signal (`actor_type != human` for an authority-shaped event, blank line in append-only ledger, chain break on a delegation-shaped event).
- `unknown` for unclassified (mandatory escalation).

---

## RECOVER / ESCALATE

**The audit ledger is the project's accountability record. There is no in-band recovery from a tampering signal.** The recovery is **escalation and (with Human approval) a fresh ledger starting from a verified snapshot**.

1. **Escalate to the Human immediately.** Append:

   ```text
   event_class: "escalation"
   action: "escalate_audit_integrity_failure"
   target: "<events.jsonl path>"
   failure_kind: "<from diagnose>"
   first_divergent_line: <int>
   quarantine_path: "events.jsonl.quarantine-<ts>"
   diagnostic_path: "state/decisions/audit-integrity-<ts>.json"
   human_signoff_required: true
   evidence: ["audit_integrity_failure:<event_id>", ...]
   result: "escalated_security_incident"
   ```

2. **Quarantine all dependent state until the Human responds.** Specifically, the orchestrator must **not** rely on the quarantined ledger for any decision. Any operation that consults the audit chain (a verification, a permission check, a Human override verification) must read the **diagnostic** file (`state/decisions/audit-integrity-<ts>.json`) instead, and must mark itself as operating in a degraded mode.

3. **No silent rollback.** The Human decides whether to:
   - **Restore from a backup** (if a verified backup exists) — append-only backups are documented in the runbook; see `docs/runbooks/README.md` and the intent-only entry for `audit-inspection.md`.
   - **Start a fresh ledger** from the last verified state — the orchestrator's `audit_append` channel creates `events.jsonl` on the next append. The fresh ledger begins at line 1; the quarantined ledger is preserved as evidence.
   - **Halt the project** — the Human may decide that no further work proceeds until a forensic review is complete.

4. **The orchestrator does not write a new audit event** until the Human's decision is recorded. A new write attempted while integrity is suspect would extend the tampered chain (or, in the fresh-ledger case, would not be recoverable to the quarantined events). Both are forbidden without Human approval.

5. **BadSector provenance / forged revocation** (Runbook 03/04 handoffs): the escalation here is independent of the integrity quarantine. The forged record is a critical alert regardless of the rest of the chain. The Human triages both incidents; they may be related.

6. **Headless / CI behaviour**: the orchestrator must halt the pipeline. There is no Human answerer to receive the escalation; the `events.jsonl` quarantine and `state/decisions/audit-integrity-<ts>.json` are the durable evidence. A CI environment that encounters this should fail the run loudly and refuse to re-execute until the diagnostic file is reviewed by a Human.

---

## VERIFY

1. **Quarantine integrity**: the quarantined `events.jsonl.quarantine-<ts>` is byte-identical to the original `events.jsonl` at the moment of quarantine. Verify by sha256. If the quarantine file differs from the diagnostic's recorded sha256, the quarantine process itself is suspect — escalate again.
2. **Side-car quarantine**: `events.jsonl.chain` is preserved alongside the events file. Verify the side-car exists and matches the diagnostic's path.
3. **No write to the quarantined file** between quarantine and Human review. Any write (e.g. a process attempting to "repair" the ledger) is a Runbook 10 regression; the new write is also quarantined.
4. **No read of the quarantined file as authority**. The orchestrator's gate must not consult the quarantined ledger; the diagnostic file is the substitute. A gate that reads the quarantined ledger as authority is a logic bug; surface as such.
5. **Audit chain integrity on the new ledger** (if the Human approved a fresh ledger): the fresh ledger's first `verify_chain` establishes a new baseline; any subsequent `verify_chain` must produce the same `cumulative_hash` for the same line count. A mismatch on the fresh ledger is a regression.

---

## REPORT

**Event 1 — the integrity failure** (always, written to the still-writable audit ledger if the failure is at the verifier):

```text
event_class: "audit_integrity_failure"
actor: "orchestrator" | "<verifier role id>"
actor_type: "agent"
action: "verify_chain" | "verify_append_only" | "detect_truncation" | "read_events_strict" | "append_event"
target: "<events.jsonl path>"
failure_kind: "chain_break" | "truncation" | "blank_line" | "corrupt_line" |
              "duplicate_event_id" | "out_of_order_timestamp" |
              "sequence_mismatch" | "count_mismatch" | "missing_event_class" |
              "bad_sector_provenance_failed" | "forged_revocation"
first_divergent_line: <int>
reason: "<helper's error message>"
quarantine_path: "events.jsonl.quarantine-<ts>"
result: "failed"
timestamp: "<UTC ISO 8601>"
```

**Event 2 — the quarantine** (one event per quarantine operation):

```text
event_class: "audit_quarantine"
actor: "orchestrator"
action: "quarantine"
target: "<original events.jsonl path>"
quarantine_path: "<quarantine path>"
sha256: "<hex>"
line_count: <int>
last_cumulative_hash: "<hex>"
result: "quarantined"
```

**Event 3 — the escalation** (always, the critical escalation):

```text
event_class: "escalation"
action: "escalate_audit_integrity_failure"
target: "<events.jsonl path>"
failure_kind: "<from diagnose>"
first_divergent_line: <int>
quarantine_path: "<quarantine path>"
diagnostic_path: "state/decisions/audit-integrity-<ts>.json"
human_signoff_required: true
halt_pipeline: true
evidence: ["audit_integrity_failure:<event_id>", "audit_quarantine:<event_id>"]
result: "escalated_security_incident"
```

**Event 4 — Human response** (only if a Human triages):

```text
event_class: "human_override"
actor: "<human session id>"
actor_type: "human"
action: "resolve_audit_integrity_failure"
target: "<events.jsonl path>"
authority_source: "<override id>"
override_reason: "<string>"
resolution: "restore_from_backup" | "fresh_ledger" | "halt_project" | "forensic_only"
original_failure_event_id: "<audit_integrity_failure event_id>"
result: "overridden"
```

**Event 5 — fresh ledger baseline** (only if `resolution = fresh_ledger`):

```text
event_class: "audit_fresh_baseline"
actor: "<human session id>"
actor_type: "human"
action: "establish_fresh_baseline"
target: "<new events.jsonl path>"
previous_quarantine_path: "<quarantine path>"
new_baseline_line_count: <int>
new_baseline_cumulative_hash: "<hex>"
authority_source: "<override id>"
result: "established"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`. After `resolution = fresh_ledger`, the next append uses the fresh ledger; the old ledger remains quarantined.

---

## Edge cases

- **`AuditIntegrityError` on a *new* ledger** (first append): the side-car is created by `compute_chain` on first verification; an empty `events.jsonl` has no chain. This is expected and **not** a Runbook 10 trigger. The verifier distinguishes "no baseline yet" from "baseline mismatch" (`verify_chain` returns cleanly when the side-car is absent — `if stored is None:` branch).
- **`AuditIntegrityError` from `read_events_strict` on the *new* (post-fresh-ledger) file**: a corrupt line in a fresh ledger is a writer bug, not tampering. Surface as `audit_write_rejected` (severity MEDIUM), but the quarantine step is not required — the new ledger is empty or near-empty, and the writer is the immediate suspect. Escalate the writer, not the chain.
- **Two integrity failures in quick succession** (a chain break followed by a forged revocation): this is an active attack pattern. Escalate as a single `escalated_security_incident` with both failure kinds in the evidence array; do not triage them independently.
- **Audit integrity failure during `RECOVERY`** (Runbook 08): the recovery halts at `FAILED`. The recovery's `RecoveryRecord` is preserved; the quarantine is independent of the recovery lifecycle. Both are escalated; the Human triages the order.
- **Forged `human_override` event**: an event of class `human_override` whose `actor_type` is `agent`. The override is a forgery; the orchestrator must treat it as if it never happened (no authority was actually granted) and surface the forgery via this runbook.
- **`audit_is_authority_source` is called by an attacker-controlled code path**: the helper returns `False` regardless of input; the attacker cannot abuse it to claim authority. This is a defense-in-depth invariant (AUTH-INV-14); the runbook does not depend on it but benefits from it.

---

## References

- AUTH-INV-14/20
- THREAT-014/018
- security spec §12 (Audit Integrity), §13 (AUD-001..004), §14 (assurance)
- threat model §3 (THREAT-018), §12 (Audit Integrity)
- design doc §18 (Audit integrity)
- `audit/helpers/append_log.py::append_event`, `read_events_strict`, `read_events_by_class`, `verify_append_only`, `audit_is_authority_source`
- `audit/helpers/integrity.py::verify_chain`, `compute_chain`, `detect_truncation`, `append_chained_event`, `chain_path_for`
- `state/helpers/atomic_write.py::atomic_write`, `safe_read` (for the diagnostic persistence to `state/decisions/`)
- `state/helpers/version_check.py::read_version` (for the version of `state/decisions/audit-integrity-<ts>.json`)
- `tests/control_plane.py::verify_badsector_provenance` (forged BadSector provenance)
- `tests/unit/test_audit_hardening.py`, `test_state_audit.py` (audit integrity tests — L1 evidence for the helpers)

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
# Runbook 01 — Authority Denial

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/adr/0001-multi-agent-control-plane-boundary.md` · `docs/adr/0002-registry-protection-mechanism.md` · `docs/security/0001-control-assurance-spec.md` §3 · `docs/security/0002-threat-model-and-control-architecture.md` §6, §18 · `docs/design/0001-control-design-and-test-plan.md` §7, §14
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to an **authority denial** at the project authority gate. All references are to artifacts that already exist (`tests/control_plane.py::authorize`, `state/helpers/recovery.py`, `audit/helpers/append_log.py`, `audit/helpers/integrity.py`). No new code, no new primitives.

---

## What this runbook covers

An **authority denial** is the event where `authorize(actor, action, target, delegation, …)` — or the live execution gate that wraps it — returns `Deny(reason)` instead of `True`. Authority is never granted by prose, by `state.approved=true`, by a BadSector verdict, or by an agent-to-agent message (AUTH-INV-01/07/09/13/14). The denial covers every cause in the authority gate's fail-closed surface:

- missing delegation (AUTH-INV-05),
- non-ACTIVE delegation status,
- delegation in revocation list (AUTH-INV-06),
- delegation expired (AUTH-INV-06),
- environment mismatch,
- scope containment violation (AUTH-INV-04),
- target outside delegation resources (AUTH-INV-11),
- prohibited action hit,
- protected path (ADR 0002),
- model-prose claim that cannot be matched to a structured record (AUTH-INV-01, THREAT-001/008/020/025).

This runbook is invoked **at the moment of denial**. It does not cover later actions once a recovery record exists (use Runbook 08 — Recovery Failure).

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source | Notes |
|---|---|---|
| `Deny(reason)` exception raised by `authorize(...)` | control-plane gate | Includes the structured reason string. |
| `RecoveryDenied(reason)` raised by `validate_against_current_version(...)` | `state/helpers/recovery.py` | Stale-version denied path; reported under Runbook 09 (Stale State) if state-version drift is the root, here if authority is the root. |
| `audit/` event with `event_class == "execution_denial"` and `result == "denied"` | `audit/helpers/append_log.py` (writer-side) | Search by `actor`, `action`, `target`. |
| `audit/` event with `event_class == "normal_approval"` or `bad_sector_pass` recorded alongside a denial | chain context | PASS recorded → still denied because PASS is never authority (AUTH-INV-09). |
| Orchestrator model emits "I am authorized" and proceeds to execute | model output | Treat as a **critical** signal; the model is attempting to bypass the gate (AUTH-INV-04, THREAT-001, TM-025). |

**Read in this order** (do not skip):

1. The most recent `audit/<project>/events.jsonl` entry with `event_class == "execution_denial"` (use `read_events_by_class` from `audit/helpers/append_log.py`).
2. The denial `reason` string from the gate — it names the invariant or rule that fired.
3. The current delegation registry (`state/registry/delegations.yaml`) — read with `state/helpers/atomic_write.py::safe_read` (fail-closed: returns `None` on missing/corrupt).
4. The current revocation list (co-located in the registry).
5. If the action targeted a protected path, the `control/execution_gate.py::authorize_write` decision (ADR 0002).

---

## STOP

**The action that was attempted must not occur.** Per AUTH-INV-20, a failed authority/control check stops the action. Concretely:

1. **Halt the in-flight action.** Do not retry the same action with the same inputs (Runbook 08 — Recovery Failure will diagnose if the failure was a recovery issue; here, the gate refused the action outright).
2. **Cancel any queued sub-steps** that depended on the denied action (`interrupt_agent`, `job_kill` against the orchestrator session's outstanding background jobs).
3. **Do not promote** the denial to a soft "we'll try later." Authority is a *gate*, not a hint. The denial is final until either (a) authority is granted by Human, or (b) the underlying root cause is diagnosed and a *new* action (different inputs) is planned.
4. **Lock the deny in audit** with `event_class == "execution_denial"`, `result == "denied"`, `reason` set to the gate's reason string, `authority_source` set to the delegation id (or `null` if none was supplied).

---

## PRESERVE

The state at the moment of denial is what subsequent diagnosis will compare against. Per AUTH-INV-12 (recovery does not acquire privilege) and THREAT-022 (recovery against obsolete state is denied), **preserve the current project state and audit chain before any recovery action**:

1. **Capture `before` hashes** of the affected files:
   - `state/registry/` (recursive sha256 of every file under it) — protected path; hash via `audit/helpers/integrity.py::detect_truncation` shape, or any external sha256 tool. Do not write to `state/registry/` itself — it is writer-scoped.
   - `state/projects/`, `state/decisions/`, `state/approvals/` — the files the action would have touched, if any.
   - `audit/<project>/events.jsonl` and its `events.jsonl.chain` side-car.
2. **Record the state version** that was current when the denial fired: `version_check.py::read_version(path)` for each affected file. These are the `preserved_version` values Runbook 08 / 09 will consult.
3. **Snapshot the denial context** — actor, action, target, environment, delegation id (if any), revocation list snapshot, gate reason — into a temporary `state/<denial-id>/context.json` using `atomic_write.py::atomic_write` (writer channel; protected by execution gate). This file is **data**, never authority (AUTH-INV-07/08/14).

> Do **not** write to `state/registry/` or `audit/` as part of preservation — those paths are writer-scoped; the snapshot belongs in `state/<denial-id>/` and is only an input to diagnosis.

---

## DIAGNOSE

Classify the denial into one of the failure classes the recovery state machine recognises (`recovery.py::RecoveryRecord.failure_class`). This determines the next step.

| Denial reason string (substring match) | Likely root cause | Failure class |
|---|---|---|
| `no delegation` | No record supplied; orchestrator forgot to pass delegation | `logic` |
| `delegation status <s>` | Registry record is `REVOKED` / `EXPIRED` (not `ACTIVE`) | `authorization` |
| `delegation revoked (AUTH-INV-06)` | Id present in revocation list | `authorization` (see Runbook 03) |
| `delegation expired (AUTH-INV-06)` | `expires_at` passed | `authorization` (see Runbook 02) |
| `environment <e> not in delegation environments` | Orchestrator tried to cross env boundary | `authorization` |
| `action <a> not in delegation operations` | Action outside scope | `authorization` |
| `target <t> outside delegation resources (AUTH-INV-11)` | Target outside scope; possible prefix confusion | `authorization` |
| `action <a> is prohibited` | `prohibited_actions` hit | `authorization` |
| `target <t> is a protected path (<p>) (ADR 0002)` | Protected-path violation | `authorization` (see Runbook 04 / "Protected Path" content) |
| `expected state version <n> but current is <m> (THREAT-022)` | State advanced between plan and exec | `logic` (see Runbook 09) |
| `text ≠ authority` / `PASS ≠ authority` | Model text or BadSector PASS was treated as authority | `logic` (escalate — gate did its job) |
| `unknown gate reason` | Bug or missing case | `unknown` (Human escalation) |

**Diagnostic record**: produce a `RecoveryRecord` (`recovery.py::begin_recovery(...)`) only if you intend to **attempt recovery** (i.e. retry with a *new* cause — AUTH-INV-16). For pure authority denials where no retry is appropriate (the Human must grant), set `failure_class` in the record and proceed to ESCALATE without calling `replan()`.

---

## RECOVER / ESCALATE

**Authority denials almost always escalate to the Human.** The orchestrator must not retry on its own — there is no new diagnosed cause. The decision tree:

1. **If `failure_class == authorization`** (most cases): **escalate to Human**.
   - The Human can: (a) grant a new delegation (creates a new `state/registry/delegations.yaml` record), (b) revoke a conflicting delegation, (c) override the gate as a Human override (must be recorded explicitly — `event_class == "human_override"` per the audit schema, with `authority_source` set to the override record id, AUTH-INV-04 carries the rule that model judgment cannot bypass but Human can).
   - The orchestrator must NOT auto-grant, auto-widen, or auto-extend a delegation. No self-escalation (AUTH-INV-02/03, THREAT-002/003).
2. **If `failure_class == logic`** (e.g. the orchestrator forgot to pass a delegation id): **fix the inputs and re-plan**, but only after a `RecoveryRecord` exists with a non-empty `diagnosed_cause` (`recovery.py::replan()` requires it; no blind retry).
3. **If `failure_class == unknown`**: **HALT and escalate**. Do not attempt recovery without diagnosis.

**Escalation contract:**

- Surface a structured escalation record in `audit/` with `event_class == "escalation"`, `reason = "authority_denied"`, `failure_class`, `actor`, `action`, `target`, `delegation_id` (or null), `human_signoff_required = true`. This is a *record*, never a grant (AUTH-INV-14).
- Do **not** pause-and-poll the Human in a tight loop. The DSH `approval/policy = "ask"` backstop will surface to a Human answerer for HIGH-risk actions; for non-HIGH authority denials, the escalation record is sufficient — the Human reviews on their schedule.
- In headless/CI environments with no Human answerer, the escalation must surface as `event_class == "escalation"` and the pipeline halts (fail-closed; no implicit allow).

---

## VERIFY

After the denial has been recorded and (optionally) escalated, **verify that no partial execution occurred**. AUTH-INV-20 forbids partial execution after a denial; this runbook proves it.

1. **On-disk state hash**: for every file the action would have touched, `before.sha256 == after.sha256`. Compute via `audit/helpers/integrity.py::detect_truncation` (which also detects overwrites via cumulative-hash comparison at equal line counts) or any sha256 tool that does not itself write to `state/`.
2. **Audit chain integrity**: `audit/helpers/integrity.py::verify_chain(events_path)` must return cleanly. A missing side-car is permitted (first-time verification baseline), but any mismatch raises `AuditIntegrityError` — that is a separate runbook (Runbook 10 — Audit Integrity Failure).
3. **Delegation registry unchanged**: `state/registry/delegations.yaml` (or whatever the registry filename is) was not mutated. The protected-path execution gate (`control/execution_gate.py`) prevents the orchestrator from writing it; this verification step confirms it did not happen.
4. **RecoveryRecord state** (if a recovery was attempted): `recovery.py::RecoveryRecord.state` must be one of `STOPPED` (no recovery attempted), `FAILED` (recovery itself failed — Runbook 08), or `COMPLETED` (a successful recovery for `failure_class == logic`). Anything else is an inconsistent state.

If verification fails, halt and escalate (`event_class == "escalation"`, `reason = "post_denial_verification_failed"`).

---

## REPORT

A denial report goes into the project audit ledger and (for Human-visible escalations) into the orchestrator's working memory as an `EscalationSummary`.

**Audit record** (one event, `event_class == "execution_denial"`):

| Field | Value |
|---|---|
| `event_id` | `denial-<uuid>` |
| `timestamp` | UTC ISO 8601 (freezing the wall clock to enable forensic sequencing) |
| `actor` | the denied actor string (e.g. `orchestrator`, `cto`) |
| `actor_type` | `agent` |
| `action` | the attempted action class |
| `target` | the concrete target |
| `project` | the project id |
| `task_id` | the originating task id, if any |
| `authority_source` | the delegation id that was supplied (or `null` if none) |
| `evidence` | array of references (file paths, schema ids) — never secrets |
| `previous_state` | the captured `before` hash set (sha256 list) |
| `new_state` | the captured `after` hash set (must equal `previous_state` on a clean denial) |
| `result` | `denied` |
| `error` | the gate's `reason` string |
| `event_class` | `execution_denial` |

Append via `audit/helpers/append_log.py::append_event` (which enforces non-empty `event_id`, JSON serializability, and atomic write).

**If escalated**, append a second event:

```text
event_class: "escalation"
action: "escalate_authority_denial"
target: <the same target>
authority_source: null
result: "escalated"
error: "human_signoff_required"
evidence: ["<reference to the denial event_id>"]
```

The escalation event **must** reference the denial event by `event_id` so a Human reviewer can trace the chain.

---

## References

- AUTH-INV-01..07, AUTH-INV-11/14/20 (control assurance §2)
- THREAT-001/002/003/008/020/024/025 (threat model §3, §4)
- ADR 0002 §"Decision" + §"Addendum" (registry protection)
- `tests/control_plane.py::authorize` (reference gate)
- `tests/authorization/test_authority.py::TestAuthorityGate` (executable skeleton — reference behavior, not L3)
- `state/helpers/recovery.py::begin_recovery` and `RecoveryRecord.diagnose`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`, `detect_truncation`
- `state/helpers/atomic_write.py::atomic_write`, `safe_read`
- `state/helpers/version_check.py::read_version`, `is_stale`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
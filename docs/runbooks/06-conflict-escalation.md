# Runbook 06 — Conflict Escalation

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/runbooks/05-evidence-failure.md` · `docs/security/0001-control-assurance-spec.md` §8, §13 (CONF-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-005/020/022 adjacent), §8 · `docs/design/0001-control-design-and-test-plan.md` §10 · `tests/control_plane.py` (no voting; preserve disagreement)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to **conflicting specialist outputs** detected by the orchestrator. Conflicts are preserved, not erased; majority voting is not used (security spec §8, threat model §2.2). This runbook covers detection, preservation, targeted rework, and the conditions under which escalation is mandatory.

---

## What this runbook covers

A **conflict** exists when two or more specialist outputs (or a specialist output and a Human-recorded expectation) disagree on a material predicate of the decision. Materiality is the orchestrator's first judgement: does the disagreement change the action's outcome, risk class, target, or required approval?

Conflicts may arise at:

- **Planning time** (two specialists propose different plans),
- **Evidence time** (Runbook 05 §"SOURCE UNCONTRADICTED" rung fails),
- **Verification time** (a specialist's report of success vs an external measurement's disagreement — Runbook 09 — Verification),
- **Recovery time** (a recovery plan vs the original plan; obsolete-state conflict).

This runbook is invoked when **the orchestrator has classified the conflict as material**. A non-material conflict (a stylistic disagreement that does not change the decision) is logged but does not halt.

**The four mandatory Human-escalation conditions** (security spec §8.1):

1. The conflict is material **and** unresolved after targeted rework/research.
2. The conflict concerns a HIGH-risk action.
3. The conflict concerns a security-relevant invariant (authority, scope, evidence sufficiency).
4. Either side has credible evidence and the orchestrator cannot resolve materiality.

If any of (2), (3), or (4) holds, escalation is mandatory regardless of rework outcome.

---

## DETECT

**Source signals (any one triggers this runbook; root-cause match on `conflict`):**

| Signal | Source |
|---|---|
| `audit/` event with `event_class == "conflict"` and `materiality` set | `audit/helpers/append_log.py::read_events_by_class("conflict")` |
| `evidence_gate` event with `ladder_step == "SOURCE_UNCONTRADICTED"` and `result == "contradictory"` (Runbook 05 handoff) | `audit/helpers/append_log.py` |
| Two `task_result` events for the same task with conflicting `output.claim` or `output.recommendation` | orchestrator working memory |
| A Human expectation recorded in `state/approvals/` that contradicts a specialist output | `state/helpers/atomic_write.py::safe_read("state/approvals/...")` |
| An out-of-band agent message whose `claims` field contradicts an in-channel finding (THREAT-020; data carries no authority) | `state/decisions/` (the message is recorded as data; not authority) |

**Read in this order:**

1. The most recent `conflict` event. Capture `conflict_id`, `task_id`, `sides[]` (each with `actor`, `claim`, `evidence_ids[]`), `materiality`, `risk_class`, `security_relevant` (boolean), `credible_evidence_on_both_sides` (boolean).
2. The originating task's working memory — the proposals being weighed.
3. The risk class for the action (`tests/control_plane.py::classify_risk`).
4. The evidence set behind each side (the gate's `source_ids` for each claim).

---

## STOP

1. **Halt the pipeline at the conflict decision point.** The orchestrator does **not** pick a side silently. No majority vote, no averaging, no "we'll go with the most confident." Preserve both sides.
2. **Lock the conflict in audit** with `event_class == "conflict"`, `materiality`, `risk_class`, `security_relevant`, `sides[]`, `credible_evidence_on_both_sides`, `timestamp`.
3. **Do not advance the state machine past the conflict** (design doc §12 — state transitions are control-plane-governed; a conflict does not produce an `APPROVED` transition).

---

## PRESERVE

1. **Snapshot both sides** of the conflict — each specialist's output (the actual returned object), the inputs each was given, the `input_hash` each worked from. The orchestrator holds these in working memory and may have them in `state/decisions/`.
2. **Capture the evidence sets** behind each side (file paths, IDs, sha256).
3. **Capture `before` hashes** of `state/registry/`, `audit/`, and any file either side would have touched.
4. **Record the conflict's chain links**: any `task_result` events, any `evidence_gate` events, and any preceding `state_transition` events for the originating task. Use the audit chain to anchor the timeline.

---

## DIAGNOSE

The orchestrator classifies the conflict into one of three postures:

| Posture | Definition | Outcome |
|---|---|---|
| **Non-material** | The disagreement does not change the action's outcome / risk class / target / required approval | Log the conflict, mark it as resolved (or as "preserve disagreement" in the synthesis), and continue. Both sides' claims are recorded; neither is silenced. No escalation. |
| **Material, security-relevant** | The conflict concerns authority, scope, evidence sufficiency, or a HIGH-risk action | **Mandatory escalation** (security spec §8.1). Skip directly to RECOVER/ESCALATE. |
| **Material, resolvable via targeted rework/research** | The disagreement can be narrowed by asking one side for additional evidence or asking both sides to re-derive under shared constraints | Targeted rework, then re-evaluate; on second failure, escalate. |

For material conflicts, decide:

- Is the risk class HIGH? If yes → **mandatory escalation** (§8.1 condition 2).
- Is the conflict on a security-relevant invariant (authority/scope/evidence)? If yes → **mandatory escalation** (condition 3).
- Do both sides have credible evidence? If yes and the orchestrator cannot resolve materiality → **mandatory escalation** (condition 4).
- Otherwise → **targeted rework** is permissible, with a re-evaluation after the rework.

`failure_class`:
- `logic` for material conflicts whose root cause is incomplete input to one or both specialists.
- `authorization` for conflicts whose resolution requires a Human decision (HIGH-risk or security-relevant).
- `unknown` if the orchestrator cannot classify.

---

## RECOVER / ESCALATE

**Targeted rework** (only when none of the four mandatory escalation conditions hold):

1. **Identify the divergent predicate.** What specific claim, target, environment, or risk class do the two sides disagree on? The rework is **scoped** to that predicate, not a full re-plan.
2. **Pick the side best positioned to re-derive under tighter constraints.** This is a routing decision, not a verdict: the orchestrator may ask Kai to retrieve additional evidence, or may ask the originating specialist to re-derive under a shared input hash. The choice is auditable, not authoritative.
3. **Re-issue under a new input hash.** A re-derivation on the **same** input hash is not a re-derivation — the same hash means the same input. The new run must produce a new input hash, even if the inputs are identical, by passing through a single deterministic normalisation step (e.g. `json.dumps(..., sort_keys=True)`) so the hash is recomputed.
4. **Bound**: `rework_cycles < max_rework_cycles` (default 2; `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`). On the second rework cycle, if the conflict persists, **escalate**.
5. **Append** `event_class == "rework_request"`, `action = "resolve_conflict"`, `task_id`, `conflict_id`, `targeted_predicate`, `specialist`, `rework_cycles`.

**Escalation** (mandatory under any of the four §8.1 conditions, or after rework bound is hit):

1. **Append** `event_class == "escalation"`, `reason = "material_conflict"`, `task_id`, `conflict_id`, `risk_class`, `security_relevant`, `materiality`, `sides[]`, `human_signoff_required = true`.
2. **Surface the preserved disagreement** in the escalation. Both sides' claims and evidence are quoted; minority risks are preserved; uncertainty is named (security spec §8, "synthesize (preserve disagreement)").
3. **The Human resolves** the conflict by one of:
   - Issuing a `Human override` event with `authority_source` (THREAT-023) choosing one side;
   - Granting new authority (a new delegation id) that supersedes the conflict;
   - Halting the action entirely (`event_class == "state_transition"`, `new_state = "BLOCKED"`).
4. **Headless / CI behaviour**: identical to Runbook 01 — the action halts, the escalation event is recorded, no implicit allow.

**Out-of-band resolution is forbidden.** A specialist asking another specialist to take a side (THREAT-005) is **not** a resolution. The orchestrator routes the request; the resolution is in the audit chain.

---

## VERIFY

1. **Audit chain integrity** holds across the conflict events, the rework events, and any escalation or override events (`audit/helpers/integrity.py::verify_chain` clean).
2. **Both sides preserved**: every conflict event lists both sides in `sides[]`. No event records only the "winning" side. A review of the audit chain must show both claims, both evidence sets, both specialists (or specialist and Human) — not a single chosen one.
3. **No majority voting**: the resolution record carries a Human override id (or a rework with a new input hash), not a tally. The orchestrator never counts votes (security spec §8, threat model §2.2).
4. **Risk class unchanged**: a HIGH-risk conflict does not become LOW on resolution. The risk class is intrinsic to the action (AUTH-INV-10, THREAT-011). A Human override that re-classifies must carry the `Human override` event with the override reason.
5. **State transitions valid**: any `state_transition` out of `REVIEW_PENDING` or out of the conflict decision point must pass the transition function (design doc §12). A transition that skips a gate (e.g. moving directly to `APPROVED` from `REVIEW_PENDING` because "we voted") is a state-machine violation.

---

## REPORT

**Event 1 — the conflict itself** (always):

```text
event_class: "conflict"
actor: "orchestrator"
actor_type: "agent"
action: "detect_conflict"
target: "<task_id>"
conflict_id: "<conflict-id>"
materiality: "material" | "non_material"
risk_class: "HIGH" | "MEDIUM" | "LOW"
security_relevant: true | false
sides:
  - actor: "<role id>"
    actor_type: "agent" | "human"
    claim: "<literal claim string>"
    evidence_ids: ["<source id>", ...]
  - actor: "<role id | human>"
    actor_type: "agent" | "human"
    claim: "<literal claim string>"
    evidence_ids: ["<source id>", ...]
credible_evidence_on_both_sides: true | false
result: "preserved" | "non_material_logged"
timestamp: "<UTC ISO 8601>"
```

**Event 2 — rework** (when targeted rework is attempted):

```text
event_class: "rework_request"
action: "resolve_conflict"
target: "<task_id>"
conflict_id: "<conflict-id>"
targeted_predicate: "<the specific disagreement>"
specialist: "<role id>"
new_input_hash: "<sha256>"
rework_cycles: <int>
evidence: ["conflict:<conflict_id>"]
result: "requested"
```

**Event 3 — escalation** (mandatory escalation):

```text
event_class: "escalation"
action: "escalate_material_conflict"
target: "<task_id>"
conflict_id: "<conflict-id>"
risk_class: "HIGH" | "MEDIUM" | "LOW"
security_relevant: true | false
materiality: "material"
mandatory_escalation_reason: "high_risk" | "security_relevant" |
                             "credible_evidence_both_sides" |
                             "rework_bound_exceeded"
human_signoff_required: true
preserved_disagreement: { sides: [...], minority_risks: [...], uncertainty: "..." }
evidence: ["conflict:<conflict_id>", "task_result:<event_id>", ...]
result: "escalated"
```

**Event 4 — Human override** (only if the Human resolves):

```text
event_class: "human_override"
actor: "<human session id>"
actor_type: "human"
action: "resolve_conflict"
target: "<task_id>"
conflict_id: "<conflict-id>"
authority_source: "<override id>"
override_reason: "<string>"
resolution: "side_a" | "side_b" | "halt" | "new_delegation"
original_conflict_event_id: "<conflict event_id>"
result: "overridden"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **Conflict at recovery time** (THREAT-022): a recovery plan uses an obsolete state version; the original plan was correct under the older version. This is **state drift**, not a content conflict. The recovery refuses (`RecoveryDenied`); route to Runbook 09 — Stale State, then come back here if the recovery plan itself becomes a material conflict with the current state.
- **Conflict between a specialist and a Human override** (THREAT-023): the Human's override is recorded; the specialist's disagreement is preserved in the audit chain (both events present). The override carries the grant; the specialist's view is preserved as minority risk.
- **Conflict between two BadSector reviews**: impossible — a single review is one invocation with one verdict. A second review is a new review event with its own `review_id` and `input_hash`; the orchestrator treats them as separate events and routes them through the same state-machine boundary. A BadSector review that contradicts a prior review is the **same conflict pattern** as a specialist conflict; this runbook applies.
- **Conflict that is itself a security-relevant invariant conflict** (e.g. one side says "the delegation is ACTIVE" and the other says "the delegation is REVOKED"): this is a registry corruption, not a content conflict. The orchestrator must verify the registry read for both sides; if they disagree, that is a **state-drift** issue (Runbook 09). If the registry is consistent and the specialists still disagree, the disagreement is a logic error in one specialist; this runbook applies.
- **Out-of-band resolution attempt** (THREAT-005): a specialist asks another specialist to take a side. This is recorded as `event_class == "out_of_band_resolution_attempt"`, `actor_type = agent`, and **escalated** regardless of materiality (the gate bypass is the threat, not the conflict). Runbook 01's posture applies to the gate bypass itself; this runbook covers the conflict handling.

---

## References

- AUTH-INV-09/10/14/20
- THREAT-005/011/013/020
- security spec §8 (Conflict Gate), §8.1 (mandatory escalation conditions), §13 (CONF-001..003)
- threat model §2.2 (data vs authority flow), §3 (THREAT-005)
- design doc §10 (Conflict gate)
- `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
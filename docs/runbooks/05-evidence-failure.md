# Runbook 05 — Evidence Failure

- **Status**: Phase 2 / Session F runbook (operational guidance against the current architecture; no new behavior introduced)
- **Date**: 2026-08-30
- **Companion to**: `docs/runbooks/01-authority-denial.md` · `docs/security/0001-control-assurance-spec.md` §7, §13 (EVID-*) · `docs/security/0002-threat-model-and-control-architecture.md` §3 (THREAT-013), §14 · `docs/design/0001-control-design-and-test-plan.md` §9 · `tests/control_plane.py::classify_risk` (risk-class context for HIGH sufficiency)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: response to a **failure at the evidence gate** — the gate has rejected a claim or surfaced an evidence-sufficiency failure (existence, relevance, currency, contradiction, sufficiency). The action the evidence was meant to support **does not proceed**.

---

## What this runbook covers

The evidence gate evaluates the ladder:

```text
SOURCE EXISTS → SOURCE RELEVANT → SOURCE SUPPORTS CLAIM → SOURCE CURRENT
              → SOURCE UNCONTRADICTED → EVIDENCE SUFFICIENT FOR ACTION
```

A failure can occur at any rung. The failure modes named in the test matrix and threat model are:

- **EVID-001 — unsupported claim** (source absent or does not support the claim).
- **EVID-002 — stale source** (older than the temporal validity window for the action class).
- **EVID-003 — contradictory evidence** (two sources contradict; the gate does not silently resolve).
- **EVID-004 — insufficient for HIGH** (model confidence alone is never sufficient for HIGH-risk actions).

The gate does not *grant* anything on evidence alone; it only **does not bar** the action on the evidence axis when the ladder passes. A failure here means the action is not yet authorised on the evidence axis and must wait for new evidence, rework, or escalation.

---

## DETECT

**Source signals (any one triggers this runbook):**

| Signal | Source |
|---|---|
| `audit/` event with `event_class == "evidence_gate"` and `result ∈ {"rejected", "stale", "contradictory", "insufficient"}` | `audit/helpers/append_log.py::read_events_by_class("evidence_gate")` |
| Orchestrator's planner records an evidence-gate outcome in the task's working memory | orchestrator working memory |
| A `conflict` event shortly after an evidence event (a contradiction surfaced; Runbook 06 may also apply) | `audit/helpers/append_log.py::read_events_by_class("conflict")` |
| A specialist (Kai most commonly) returns evidence that the planner's evidence gate rejects | subagent return + gate outcome |

**Read in this order:**

1. The most recent `evidence_gate` event for the originating task. Capture `claim`, `source_ids[]`, `ladder_step` (which rung failed), `failure_reason`, `temporal_window`, `risk_class`.
2. The originating claim's source set — the `evidence` array from the task record or specialist return.
3. The risk classification for the action — `tests/control_plane.py::classify_risk(action, target, environment)` — because HIGH-risk actions have stricter sufficiency rules.
4. Any prior evidence events for the same task (the gate may have failed once before; a second failure may be bound).

---

## STOP

1. **Halt the action's progression.** The evidence gate is one of the gates the orchestrator checks before allowing execution (orchestrator contract; design doc §7/§9). The action does **not** enter `APPROVED` or `EXECUTING`.
2. **Do not** auto-downgrade the action to "evidence-light." A HIGH-risk action with insufficient evidence **stays** HIGH; the gate does not silently reclassify (AUTH-INV-10).
3. **Do not** fabricate evidence. A model asserting "I am confident this is correct" is L0; the gate never reads model confidence as a source (security spec §7.2). An evidence failure cannot be cured by rephrasing the claim.
4. **Lock the failure in audit** with `event_class == "evidence_gate"`, `result = "<rejected|stale|contradictory|insufficient>"`, `ladder_step`, `failure_reason`, `risk_class`, `claim` (the literal claim string).

---

## PRESERVE

1. **Snapshot the source set** that was presented to the gate — file paths, URLs, sha256 (if files), `retrieved_at` (when the source was obtained), `temporal_validity` (the window). The source set itself is in the task record or specialist return; the orchestrator holds a reference.
2. **Capture `before` hashes** of `state/registry/`, `audit/`, and any file the action would have touched. Same procedure as Runbook 01 §PRESERVE.
3. **Capture the wall-clock timestamp** at which the gate ran — relevant for `stale` failures and for any subsequent `current` check.

---

## DIAGNOSE

Map the failure to a rung of the ladder and to the correct recovery path.

| `ladder_step` / `failure_reason` | Root cause | Recovery posture |
|---|---|---|
| `SOURCE EXISTS` failed (no source presented) | Specialist did not return evidence; orchestrator did not require it | **Rework** — request targeted evidence from the originating specialist (usually Kai for research; CTO for code claims). |
| `SOURCE RELEVANT` failed (source does not bear on the claim) | Mismatched scope — source answers a different question | **Rework** — request a relevant source or reformulate the claim. |
| `SOURCE SUPPORTS CLAIM` failed (source contradicts the claim or is silent on the critical predicate) | Misinterpretation of the source | **Rework** — re-read the source; possibly **escalate** if the source cannot be re-interpreted correctly. |
| `SOURCE CURRENT` failed (temporal validity window exceeded) | Source is older than the window for this action class (HIGH-risk windows are tighter) | **Rework** — obtain a current source; or **escalate** if no current source is obtainable (e.g. legal/financial filings lag). |
| `SOURCE UNCONTRADICTED` failed | At least one other source contradicts the supporting source | **Route to Runbook 06** — Conflict Escalation. The contradiction is preserved; voting is not used. |
| `EVIDENCE SUFFICIENT FOR ACTION` failed (HIGH only) | Model confidence alone is not sufficient for HIGH-risk actions; at least one verifiable artifact (test result, build output, runtime health, document citation) is required | **Rework** — produce a verifiable artifact; or **escalate** if the action class is HIGH and the artifact is unobtainable. |

`failure_class`:
- `logic` for `SOURCE EXISTS / RELEVANT / SUPPORTS` failures (the orchestrator's planner or the originating specialist produced incomplete evidence).
- `authorization` for `EVIDENCE SUFFICIENT FOR ACTION` failures on HIGH-risk actions (the action class itself requires Human-grade assurance; the gate's refusal is a class-level rule, not a logic error).
- `unknown` for chain-internal failures (e.g. the gate could not parse a source's temporal metadata) — escalate.

---

## RECOVER / ESCALATE

The orchestrator **does not auto-allow** on evidence failure. The choices are:

1. **Rework via targeted evidence request** (most cases):
   - Route the request to the originating specialist (per the role that produced the claim). For research claims, Kai is the natural retriever; for code claims, CTO is. Use the canonical capability matrix in `config/permissions.yaml` to confirm the specialist's toolFilter allows the retrieval (e.g. `web_search`).
   - The rework must produce a **new source** (or a re-interpreted current source), not a re-statement of the same evidence.
   - Bound: a second failure on the same task within the same `rework_cycles` window escalates regardless. `max_rework_cycles` defaults to 2 (`state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`).
2. **Route to Runbook 06** (if the failure is at `SOURCE UNCONTRADICTED` and the contradiction is material).
3. **Escalate to the Human** when:
   - The failure is `EVIDENCE SUFFICIENT FOR ACTION` on a HIGH-risk action and a verifiable artifact is unobtainable by any specialist (e.g. a regulatory filing that only a Human can request).
   - The rework has hit its bound (default 2 cycles).
   - The originating specialist repeatedly returns the same evidence without addressing the gap (logic bug in the specialist, not an evidence problem).

**Escalation record**: `event_class == "escalation"`, `reason = "evidence_insufficient"` (or `"evidence_stale"`, `"evidence_unsupported"`, `"evidence_contradictory"`), `task_id`, `claim`, `ladder_step`, `risk_class`, `human_signoff_required = true`.

**No re-classification**: a HIGH-risk action does not become MEDIUM because evidence is thin. The risk class is intrinsic to the action's blast radius (AUTH-INV-10, THREAT-011). A Human override that re-classifies a HIGH action to MEDIUM must be recorded as `Human override` with the override reason, and **does not delete the original evidence-gate event** (append-only).

---

## VERIFY

1. **Audit chain integrity** holds across the evidence-gate events and any rework events.
2. **No state mutation** outside the documented transitions. An evidence failure must not change `state/projects/*` for the task — the task remains in its prior state (`DRAFT` or `PLANNED`) until evidence passes.
3. **Rework bounds** held (`rework_cycles < max_rework_cycles`).
4. **Re-gating**: when new evidence arrives, the gate **must** re-run from `SOURCE EXISTS` (no short-circuit from a previous rung). The new event carries a new `input_hash` over the new source set; a passing gate on the new hash is required before the action can proceed.
5. **No model confidence substituting**: the gate's verdict field for the new run does not contain `model_confidence_only = true` for HIGH actions — that would be a re-run of the same bug.

---

## REPORT

**Event 1 — the gate outcome** (always):

```text
event_class: "evidence_gate"
actor: "orchestrator"
actor_type: "agent"
action: "evaluate_evidence"
target: "<task_id>"
claim: "<literal claim string>"
ladder_step: "SOURCE_EXISTS" | "SOURCE_RELEVANT" | "SOURCE_SUPPORTS" |
             "SOURCE_CURRENT" | "SOURCE_UNCONTRADICTED" | "EVIDENCE_SUFFICIENT_FOR_ACTION"
result: "rejected" | "stale" | "contradictory" | "insufficient" | "passed"
failure_reason: "<string>"
risk_class: "LOW" | "MEDIUM" | "HIGH"
source_ids: [...]
evidence: ["<source identifiers>"]
timestamp: "<UTC ISO 8601>"
```

**Event 2 — rework** (when rework is attempted):

```text
event_class: "rework_request"
action: "request_targeted_evidence"
target: "<task_id>"
specialist: "<role id>"
requested_evidence: "<description>"
rework_cycles: <int>
evidence: ["evidence_gate:<event_id>"]
result: "requested"
```

**Event 3 — escalation** (when escalated):

```text
event_class: "escalation"
action: "escalate_evidence_failure"
target: "<task_id>"
ladder_step: "..."
risk_class: "HIGH" | "MEDIUM" | "LOW"
human_signoff_required: true
evidence: ["evidence_gate:<event_id>", ...]
result: "escalated"
```

**Event 4 — Human override** (if a Human overrides on `EVIDENCE SUFFICIENT FOR ACTION`):

```text
event_class: "human_override"
actor: "<human session id>"
actor_type: "human"
action: "override_evidence_sufficiency"
target: "<task_id>"
authority_source: "<override id>"
override_reason: "<string>"
original_gate_event_id: "<evidence_gate event_id>"
result: "overridden"
```

All events are records, not grants (AUTH-INV-14). Append via `audit/helpers/append_log.py::append_event`.

---

## Edge cases

- **Evidence gate failure on a research-only task** (Kai → analysis output): the action is internal research / analysis. Self-verification may be acceptable for LOW-risk internal research (security spec §10.1), but the evidence gate still runs; a failure means the orchestrator did not get the evidence it needed even for a LOW-risk action, and the task is incomplete. Rework via Kai.
- **Temporal validity window is not encoded in the registry**: the gate computes it from the action class and risk class. A "stale" failure must carry the window used (`temporal_window` field in the event); absent that, the failure is unverifiable — escalate as `unknown`.
- **Contradiction is a difference of opinion, not a fact**: Runbook 06 handles the conflict. This runbook records only the `SOURCE UNCONTRADICTED` rung's failure; it does not adjudicate the contradiction.
- **HIGH-risk action with model confidence only** (EVID-004): the gate's refusal is the **expected** outcome. The orchestrator must not route this to "try a different prompt." It must either produce a verifiable artifact (test result, build output, runtime health, document citation) or escalate.
- **Source path escapes the workspace** (e.g. a researcher returns an absolute path): the gate should not have accepted it; if it did, this is a control-plane gap and Runbook 04 (Protected Path) may apply. Treat as `unknown` and escalate.

---

## References

- AUTH-INV-09/10/14/20
- THREAT-011/013
- security spec §7 (evidence gate), §13 (EVID-001..004), §14 (assurance matrix)
- threat model §14 (Evidence Assurance)
- design doc §9 (Evidence gate)
- `tests/control_plane.py::classify_risk`
- `tests/authorization/test_authority.py::TestRiskGate` (test plan matrix)
- `state/helpers/recovery.py::DEFAULT_MAX_REWORK_CYCLES`
- `audit/helpers/append_log.py::append_event`, `read_events_by_class`
- `audit/helpers/integrity.py::verify_chain`

---

*Status: Phase 2 runbook. Aligns with the architecture already in place; introduces no new behavior.*
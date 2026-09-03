# SCN-105 — Conflict Escalation (bounded)

- **Id**: `SCN-105`
- **Runbook**: `docs/runbooks/06-conflict-escalation.md`
- **PRD §17 skeleton**: #8 — Conflicting specialist outputs
- **Anchors**: CONF-001..003 · AUTH-INV-09/10/20 · THREAT-005/011/013 · §8.1 mandatory-escalation conditions
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestConflictEscalation`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- Two specialist subtask results that **disagree on a decision** (different `recommendation` / `position`):
  - `SCN-105a` flow-level HIGH-risk conflict: two collected results with conflicting recommendations and `declared_risk="HIGH"` → material, mandatory escalation (security spec §8.1 condition 2/3).
  - `SCN-105b` control-level material conflict: `ConflictGate.resolve` on two outputs with conflicting positions and evidence on both sides → `action == "escalate"`, `voted == False`, `preserved == True`.
  - `SCN-105c` control-level immaterial conflict: LOW-risk outputs with conflicting positions but **no evidence** on either side → synthesized (`action == "synthesize"`), all distinct positions preserved, no voting.
  - `SCN-105d` no-voting invariant: a 2-vs-1 majority is still a conflict when positions differ; the gate never counts.

## Objective

Prove that the conflict gate detects, classifies, and resolves specialist disagreement **without majority voting**: material / HIGH / security-relevant conflicts escalate to Human (preserving both sides); immaterial conflicts are synthesized with disagreement preserved; the flow never picks a side silently.

## Actors

- **orchestrator** — routes the specialists, collects results, runs the conflict gate.
- **kai / cfo** (or any pair) — specialists returning conflicting recommendations (data).
- **Human** — resolves material conflicts (explicit override / new delegation / halt); the orchestrator never votes or averages.

## Expected state

- `SCN-105a` → `ESCALATED` at phase `conflict_gate` (GateEscalated); `final_state` never `COMPLETE`.
- `SCN-105b/c/d` → `ConflictResolution` records with `voted == False` always; `escalated`/`preserved` per materiality.

## Expected gates

- `conflict` gate:
  - material / HIGH / security-relevant → `ESCALATE` (`material conflicts escalated to Human`).
  - immaterial (LOW, no evidence) → `ALLOW` (`all conflicts synthesized; disagreement preserved; no voting`).

## Expected execution

- **No consequential write** in the flow-level escalation (flow stops at `conflict_gate`).
- The control-level conflict evaluations are read-only — no filesystem mutation.

## Expected verification

- Verification not reached on escalation; COMPLETE is never produced from a material conflict.
- The flow's synthesis is not produced past the conflict gate on ESCALATE (the disagreement is preserved in the audit, not resolved by counting).

## Expected failure / recovery

- `failure_class` per Runbook 06: material with resolvable root cause → `logic` (targeted rework under a **new input hash**, bounded by `max_rework_cycles`); material requiring Human decision (HIGH / security-relevant) → `authorization` (escalate); unclassifiable → `unknown`.
- Out-of-band resolution is forbidden (THREAT-005): a specialist asking another to take a side is not a resolution.
- Deterministic bounded behavior: the flow halts at the conflict gate on material conflict; the targeted-rework and Human-override paths are asserted at the control-module level.

## Evidence requirements

- `FlowResult.gates` contains a `conflict` record with decision and detail (conflict ids).
- Audit contains a `gate_conflict` event with `result == "escalated"`.
- `ConflictResolution` for 105b/c/d: `voted == False`; `preserved == True` when positions are synthesized; both sides present in the resolution detail (no "winning side" only).
- No-mutation proof: target absent in the flow-level escalation.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

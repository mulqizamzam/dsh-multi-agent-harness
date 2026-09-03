# SCN-104 — Evidence Failure (bounded)

- **Id**: `SCN-104`
- **Runbook**: `docs/runbooks/05-evidence-failure.md`
- **PRD §17 skeleton**: #1 (research) / #2 (code change with test evidence)
- **Anchors**: EVID-001..004 · AUTH-INV-10/15 · THREAT-011/013 · VERIFY-003
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestEvidenceFailure`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101.
- Sub-case matrix (evidence presented to the gate):
  - `SCN-104a` flow-level HIGH-risk action with **no evidence** (subtask returns `SUCCEEDED` with empty `evidence`).
  - `SCN-104b` flow-level MEDIUM-risk action with **no evidence** (evidence optional for LOW, ESCALATE for MEDIUM, DENY for HIGH — EVID-001/002 ladder).
  - `SCN-104c` control-level ladder failures via the real `control.evidence.EvidenceGate`:
    - unsupported claim (no source mapped) → `SOURCE_EXISTS` fails;
    - stale source (older than the temporal window) → `CURRENT` fails (EVID-002);
    - contradictory sources (`contradicts` edge) → `UNCONTRADICTED` fails (EVID-003);
    - HIGH risk with model-confidence-only sources → `SUFFICIENT_FOR_ACTION` fails (EVID-004).

## Objective

Prove that the evidence gate enforces the sufficiency ladder (SOURCE EXISTS → RELEVANT → SUPPORTS → CURRENT → UNCONTRADICTED → SUFFICIENT FOR ACTION): failures stop the flow before execution, and model confidence is never evidence (EVID-004).

## Actors

- **orchestrator** — runs the evidence gate over the collected specialist results.
- **cto / kai** — specialist(s) returning findings + evidence claims (data).
- No Human needed for the gate failure itself; escalation is Human-directed when evidence is unobtainable.

## Expected state

- `SCN-104a` (HIGH, no evidence) → `BLOCKED` (evidence gate `DENY`, EVID-002 for HIGH).
- `SCN-104b` (MEDIUM, no evidence) → `ESCALATED` (evidence gate `ESCALATE`, EVID-001).
- `SCN-104c` → each ladder rung failure produces an `EvidenceVerdict` with `accepted=False` and the named failing rung.

## Expected gates

- `evidence` gate:
  - HIGH + no sources → `DENY` (`HIGH-risk action requires evidence (EVID-002)`).
  - MEDIUM + no sources → `ESCALATE` (`MEDIUM action: no evidence (EVID-001)`).
  - LOW + no sources → `ALLOW` (evidence optional for LOW).
  - Supplied sources failing any rung → `DENY` with `rung` in the gate detail.

## Expected execution

- **No consequential write** in the flow-level failures (flow stops at `evidence_gate`).
- The control-level ladder checks are read-only gate evaluations — no filesystem mutation.

## Expected verification

- Verification is not reached for DENY/ESCALATE outcomes; COMPLETE is never produced without evidence passing (AUTH-INV-15).
- Evidence requirements are attached only after a successful execution (`_attach_evidence`), so a failure never yields a verified outcome.

## Expected failure / recovery

- `failure_class` per Runbook 05: `SOURCE_EXISTS/RELEVANT/SUPPORTS` → `logic` (rework: request targeted evidence); `SUFFICIENT_FOR_ACTION` on HIGH → `authorization` (class-level rule; escalate if the artifact is unobtainable); `unknown` for unparseable metadata (escalate).
- No auto-downgrade of risk (AUTH-INV-10) and no fabricated evidence: a rework must produce a **new source**; the rework is bounded by `max_rework_cycles` (default 2).
- Deterministic bounded behavior: the flow halts at the evidence gate; the rework/escalation paths are asserted at the control-module level.

## Evidence requirements

- `FlowResult.gates` contains an `evidence` record with decision and rung detail.
- Audit contains a `gate_evidence` event with `result == "denied"` / `"escalated"`.
- `EvidenceVerdict` objects for 104c carry `rung_reached`, `reason`, and the named invariant (EVID-001/002/003/004).
- No-mutation proof: target absent in flow-level failures.

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*

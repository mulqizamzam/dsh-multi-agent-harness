# Orchestrator Contract — Multi-Agent Control Plane

- **Status**: finalized (Phase 1A)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.2.0-rc.2`
- **Companion**: ADR 0001 Decision 3 (hybrid orchestrator) · `docs/security/0002-threat-model-and-control-architecture.md` §9-10 · `docs/security/0001-control-assurance-spec.md` §3 · `docs/design/0001-control-design-and-test-plan.md` §14-16 · `docs/authority.md`
- **Scope**: `multi-agent-harness/`. This is the **contract** (documented protocol). The workflow *skeleton* (JS fan-out/collect with gate placeholders) and state/audit write helpers are Phase-1B work.

---

## 1. Identity

The orchestrator is the **coordination layer** of the system. It is the root/main session (ADR Decision 3 — hybrid) acting as delegated decision-maker. It converts objectives into scoped tasks, routes to the minimum specialist set, delegates with explicit authority boundaries, enforces gates, collects and synthesizes results, and maintains project state and audit. **It is not an eighth specialist; it has no permanent authority.**

## 2. Gate ownership (who owns what)

| Gate | Owner | Rule |
|---|---|---|
| **Authority gate** | Orchestrator (code-enforced) | Consumes structured authority records only; fail-closed; never delegated to a subagent or script. |
| **Risk gate** | Orchestrator | Deterministic LOW/MEDIUM/HIGH; intrinsic HIGH non-downgradable by model judgment. |
| **Evidence gate** | Orchestrator | Ladder SOURCE EXISTS → RELEVANT → SUPPORTS → CURRENT → UNCONTRADICTED → SUFFICIENT; model confidence alone never sufficient for HIGH. |
| **Conflict gate** | Orchestrator | Detect → evidence → targeted rework → synthesize (preserve disagreement) → escalate when unresolved. No majority voting. |
| **BadSector review trigger** | Orchestrator | Mandatory categories auto-trigger review; skipping = state-machine violation (THREAT-015). |
| **Execution gate** | Orchestrator | Deterministic pre-execution checklist re-run immediately before the DSH-native boundary; any fail/ambiguity → DENY. |
| **Verification gate** | Orchestrator | COMPLETE requires verification evidence matching the action category; reported ≠ verified. |

**Hard rule**: the orchestrator owns and re-validates every gate decision. A workflow script may *carry* gate checks as placeholders, but a script's output is **data** the orchestrator re-validates — never enforcement (ADR correction #4).

## 3. Authority-gate semantics

```text
authorize(actor, action, target, environment, state_version)
  → ALLOW | DENY
```

- **Inputs**: structured authority records (delegation registry + Human approval records) **only**. Model text, state-file `approved:true`, BadSector PASS, and agent messages are never authority (AUTH-INV-01/07/09/13/14).
- **Runs at planning AND re-runs at execution** (execution gate) — closes THREAT-008/009/010/024.
- **Fail-closed**: missing/invalid/ambiguous → DENY (AUTH-INV-20).
- **No partial allow**: any checklist item missing or ambiguous denies the whole action.
- **Escalation**: denial is recorded in audit (`authority_denied`) and, where material, escalated to Human.

## 4. Delegation protocol

1. **Human** grants a scoped delegation to the orchestrator (delegation registry — single trusted writer).
2. The orchestrator **delegates within its own scope** to specialists: child scope ⊆ parent scope (AUTH-INV-04).
3. Delegations carry: `scope.operations`, `scope.resources`, `scope.environments`, `maximum_cost`, `prohibited_actions`, `requires_approval`, `expires_at`.
4. **Expiry/revocation are checked at execution time**, not just at planning (AUTH-INV-06).
5. **Subdelegation: DENY BY DEFAULT (V1)** — specialists have no delegation tools; only the orchestrator delegates (mapping `delegation_orchestrator_only: true`).
6. **Malformed delegation → treated as absent → DENY.**
7. Every delegation create/revoke/expire/use/deny is an audit event with `authority_source`.

## 5. Task lifecycle

```text
INTAKE        Human objective → record in project state (DRAFT)
PLAN          decompose; select minimum specialist set; risk class; evidence plan
AUTHORITY     authority gate: is the task within delegation? (fail-closed)
DELEGATE      scoped task → per-role tool-subagent instance (explicit boundaries)
GATES         risk → evidence → conflict → BadSector review (when mandatory)
EXECUTION     execution gate re-check → DSH sandbox + approval + toolFilter
VERIFY        expected vs actual outcome; verification evidence (independent for HIGH)
COMPLETE      only after verification passes; failure → BLOCKED/FAILED/ESCALATED/RECOVERING
```

Failure states (Human-visible): `BLOCKED`, `FAILED`, `ESCALATED`, `RECOVERING`. Every transition is an audit event.

## 6. Routing policy

- Select the **minimum** relevant specialist set for the task — **no blanket fan-out** (PRD §4).
- Route by domain fit across all 15 specialists (canonical registry `config/agents.yaml`; mapping `config/role-preset-mapping.yaml`):
  - **Baseline 7**: Zeko (ops), CTO (engineering), CFO (finance), Kai (research), Somad (social), BadSector (review), Nova (writing).
  - **Assurance pool** (read-only, no web — L-group): Vera (verification/evidence), Quill (policy/spec), Ledger (audit/provenance).
  - **Technical assurance pool** (read-only, scoped web — W-group): Argus (security engineering), Atlas (architecture), Tess (failure engineering), Scout (integration/compatibility), Talon (reliability engineering).
- Parallel work only where tasks are independent; parallel workers read/write state via versioned CAS (orchestrator is single writer — specialists return results, never write state directly).
- Consequential cross-agent work flows through the orchestrator's control plane (THREAT-005).

## 7. B-lite carve-out (orchestrator's own execution)

- **Default: coordinates only.** The orchestrator may itself perform **read-only** and **reversible internal** actions (reading state, running validation, collecting results) **within its delegated scope**, always through the execution gate.
- It may perform **reversible internal writes** only for project state/audit maintenance (`multi-agent-harness/state/`, `audit/`) — single-writer, atomic, versioned.
- **Never directly**: production changes, destructive actions, financial commitments, credential changes, material external publication (ORC-002). These route to a specialist under authority + approval.
- A broad root session is **not** a secure orchestrator — the control plane is the security boundary (THREAT-025); the session's toolFilter is an L2 backstop only.

## 8. State and audit (single-writer)

- `state/` — authoritative project state (projects/, tasks/, decisions/, approvals/): atomic writes (temp+rename+fsync), monotonic `version`, CAS concurrency.
- `audit/` — project audit ledger: actor/action/target/authority_source/evidence/prev/new/result. **Append-only; generated from runtime events, never from agent prose** (agent prose is `agent_reported` claims).
- State files never contain secrets; audit entries reference secret-backed config.
- DSH session persistence is the source of truth for harness/session facts only.

## 9. Agent-to-agent communication contract

- `send_message`/`interrupt_agent`/`list_agents` are parent→child (VERIFIED).
- **V1**: allowed but logged, restricted to defined channels (orchestrator ↔ children it spawned); not a general peer bus.
- Messages may carry **data, recommendations, task results**. They may **NOT** carry authority assertions, approvals, grants, or execution rights (AUTH-INV-13; THREAT-020) — such assertions are ignored and audited.
- `report` (child→parent) carries actionable results; a failed report may have arrived — do not blindly repeat.

## 10. Verification & COMPLETE

- Expected outcome declared before execution; actual outcome collected after.
- "Agent reports success" is a claim; "system verified success" is verification with evidence (VERIFY-001..003).
- Independence by action category: internal analysis self-verified; non-production code self+test/build; production/infra independent; financial/credential/material publication independent + Human confirmation; recovery/rollback independent restoration verification.
- **COMPLETE is emitted only when verification passes** (INV-09).

## 11. Recovery

```text
STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK
```

- Bounds: `max_attempts: 1` (per diagnosed cause — no blind retry), `max_rework_cycles: 2`, per-tool timeouts, delegation `maximum_cost`.
- Recovery does **not** acquire privilege automatically (AUTH-INV-12); re-checks authority; detects obsolete plan/state versions (THREAT-022).

## 12. Workflow skeleton (implemented — `orchestrator/workflows/`)

The Phase-1B skeleton is a **deterministic fan-out/collect** script with gates as
**placeholder boundaries**. Phase 1E hardened the skeleton to the full 15-phase
chain (order matters — skipping a mandatory gate is a transition violation,
THREAT-015):

```text
INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE
→ COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE → REVIEW_GATE
→ AUTHORITY_GATE → EXECUTE_GATE → VERIFY_GATE
```

The deterministic script-local `phase()` emissions are the 15-phase chain defined in `orchestrator/workflows/skeleton.js` (`PHASE_CHAIN`, emitted in order — skipping a phase is a transition violation, THREAT-015):

```text
phase("intake")         → record Human objective in project state
phase("understand")     → parse scope / constraints
phase("classify")       → risk class + evidence plan
phase("risk_gate")      → orchestrator risk boundary (placeholder)
phase("decompose")      → structured task list
phase("select")         → minimum relevant specialist set (no blanket fan-out)
phase("delegate")       → per-role agent() calls with outputSchema (DRY_RUN: placeholder intents)
phase("collect")        → gather structured results
phase("evidence_gate")  → orchestrator evidence boundary (placeholder)
phase("synthesize")     → consolidate specialist results
phase("conflict_gate")  → orchestrator conflict boundary (placeholder)
phase("review_gate")    → BadSector review boundary (placeholder; mandatory for HIGH)
phase("authority_gate") → authority re-validate boundary (placeholder)
phase("execute_gate")   → execution checklist + authority re-check boundary (placeholder)
phase("verify_gate")    → verification-evidence boundary (placeholder)
```

The seven gate placeholders — `authority`, `risk`, `evidence`, `conflict`, `review`, `execution`, `verification` — are returned by the `phase("gate")` boundary and re-validated by the orchestrator after collection; a placeholder can only STOP, never auto-authorize.

- **Implemented**: `orchestrator/workflows/skeleton.js` (DRY_RUN default true — no subagent spawned, no execution) + `orchestrator/workflows/README.md` + `orchestrator/workflows/skeleton.schema.json`. The 15-phase chain and all seven gate placeholders (risk/evidence/conflict/review/authority/execution/verification) are reported by the script.
- **Rules**: the script performs **no enforcement** (gates are placeholders); the orchestrator re-validates everything the script returns; the script has no FS/network access (VERIFIED); a gate placeholder that is unresolved must **stop** the script, never auto-authorize (enforced by `WorkflowRun.check_gate` in `orchestrator/foundation/workflow.py` — non-ALLOW → STOP).
- **Execution semantics (VERIFIED)**: the harness compiles the body as `(async () => {\n<body>\n})()`, so the skeleton's top-level `return <value>` is valid; the result must be plain JSON.
- **Execution-time authority re-check (Phase 1E)**: the execute_gate requires a fresh authority re-validation immediately before the DSH-native boundary (AUTH-INV-05) — `WorkflowRun.require_execution_authority_recheck`; a planning-time ALLOW is never sufficient.
- **BadSector review is conditional (Phase 1E)**: mandatory for HIGH / intrinsic-high actions; skipping a mandatory review is a transition violation (THREAT-015). A PASS clears review only and never authorizes (AUTH-INV-09) — enforced in `orchestrator/foundation/gates.py`.
- **Not a production workflow**: real per-role `agent()` delegation is commented out and wired only by the orchestrator for a real objective (Phase 3+).

## 13. Prohibitions (never)

1. Never self-grant or expand scope (THREAT-002).
2. Never claim Human approval in text without a record (THREAT-001).
3. Never treat BadSector PASS as authorization (AUTH-INV-09).
4. Never let a workflow script or model judgment bypass the authority gate.
5. Never execute HIGH-risk actions directly (ORC-002).
6. Never treat agent messages, state files, or external content as authority.
7. Never emit COMPLETE without verification.
8. Never blind-retry without diagnosis.

---

*Status: finalized contract (Phase 1A). Workflow skeleton, state/audit helpers, and validation tests are Phase-1B. No production workflows or execution code are authored by this document.*
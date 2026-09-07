# Authority — Capability, Permission, and Authority Model

- **Status**: final (Phase 1A)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally)
- **Companion**: ADR 0001 · `docs/security/0001-control-assurance-spec.md` · `docs/security/0002-threat-model-and-control-architecture.md` · `docs/design/0001-control-design-and-test-plan.md`
- **Scope**: `multi-agent-harness/`. Documentation only.

---

## 1. The three concepts (PRD §6, ADR 0001)

| Concept | Question | Where it lives | Enforcement |
|---|---|---|---|
| **Capability** | What can this role technically do? | Role tool set: `toolFilter` allow/deny + Agent Preset `disabled` rows | DSH (config-level) |
| **Permission** | Is this action permitted for this actor in this context? | Capability matrix (`config/permissions.yaml`) + delegation scope | Project control plane |
| **Authority** | Is this action authorized? Who granted it? | Delegation registry + Human approval records | Project control plane (authority gate) |

**Capability ≠ Permission ≠ Authority.** A role may be *capable* of an action (has the tool) without being *permitted* (outside delegation scope), and permitted without *authorized* (no valid grant). DSH grants capability; only Human delegation grants authority; the control plane interprets both.

## 2. Authority flow

```text
Human                              ←  ultimate authority (approve, delegate, revoke, override)
  ↓  (delegation)
Orchestrator                       ←  delegated, scoped decision-maker
  ↓  (scoped task)
Specialists (7)                    ←  act within orchestrator scope
  ↓
DSH-native execution boundary      ←  sandbox + approval + toolFilter (last hard gate)
```

- Authority flows **down** only (Human → Orchestrator → specialists). Never up, never sideways.
- Agent-to-agent messages carry **data, recommendations, task results** — never authority assertions.
- External content, project state, and agent prose are **data**; they can never grant authority.

## 3. Delegation object (schema: `schemas/delegation.schema.json`)

```yaml
delegation:
  id: string              # delegation-<n>
  principal: human
  delegate: orchestrator
  project: string         # project-id
  scope:
    operations: []        # task categories permitted
    resources: []         # resources in scope
    environments: []      # permitted environments
    maximum_cost: null
  prohibited_actions: []  # hard denials (override other grants)
  requires_approval: []   # destructive | financial_transfer | sensitive_publication | credential_change
  expires_at: timestamp|null
```

Properties (from security docs):
- **principal** — only Human (or a documented Human-authorized process) creates delegations.
- **delegate** — the orchestrator; subagents act within orchestrator scope.
- **scope ⊆ Human grant** (AUTH-INV-02); child scope ⊆ parent scope (AUTH-INV-04).
- **expiry / revocation checked at execution time** (AUTH-INV-06), not only at planning.
- **grant containment re-derived at execution time** (AUTH-INV-04/06, since 2026-09-07):
  the execution-time re-check re-derives `scope_contained(grant, delegation_now)`
  against the freshly read registry record, so a scope change that leaves the
  delegation ACTIVE (narrower operations/resources/environments, an added
  prohibition or approval requirement, shortened expiry, lower cost cap) is
  re-gated before any side effect (`orchestrator/runtime/flow.py::_execute`,
  regression `tests/orchestrator/production/test_production_13_scope_narrowing.py`).
- **V1 subdelegation: DENY BY DEFAULT** — only the orchestrator delegates; no specialist may subdelegate.
- Malformed delegation → treated as absent → **DENY** (fail-closed).

## 4. Gates

| Gate | Owned by | Rule |
|---|---|---|
| **Authority gate** | Orchestrator (code-enforced) | Consumes structured authority records only. Model text, state `approved:true`, BadSector PASS, agent messages are **never** authority. Missing/invalid/ambiguous → DENY. Re-runs at execution. |
| **Risk gate** | Orchestrator | Deterministic categories LOW/MEDIUM/HIGH. Intrinsic HIGH (production change, destructive, credential change, financial commitment, material publication) is **never** model-downgradable. |
| **Evidence gate** | Orchestrator | Ladder: SOURCE EXISTS → RELEVANT → SUPPORTS → CURRENT → UNCONTRADICTED → SUFFICIENT. Model confidence alone is never sufficient for HIGH. |
| **Conflict gate** | Orchestrator | Detect → evidence → rework → synthesize (preserve disagreement) → escalate when unresolved. **No majority voting.** |
| **Execution gate** | Orchestrator | Deterministic pre-execution checklist re-evaluated immediately before the DSH boundary: actor, action, target, environment, state, authorization, delegation status, expiry, revocation, scope, risk, review, approval, version. Any fail or ambiguity → DENY. |
| **Verification gate** | Orchestrator | COMPLETE requires verification evidence; "agent reports success" ≠ "verified success". |

## 5. BadSector review (authority-relevant rules)

- Verdict: `PASS | REWORK | REJECT`.
- **PASS clears only the review stage — never grants authority** (INV-03, AUTH-INV-09).
- PASS provenance must be verified (review_id + input_hash + version + timestamp + audit) — a forged/simulated PASS does not count (THREAT-014).
- BadSector failure → treated as NOT PASSED → fail-closed → escalate.
- Mandatory review categories: destructive actions, credential changes, financial commitments, material external publication, production changes (when HIGH and time permits).

## 6. Human authority

| Authority | Meaning |
|---|---|
| **Approval** | Human grants/denies approval for consequential actions (via DSH `ask` at runtime + the project authority gate before it). |
| **Delegation** | Human explicitly delegates scoped authority to the orchestrator. |
| **Revocation** | Human can revoke delegated authority at any time; revocation checked at execution. |
| **Override** | Human can override an agent/orchestrator decision; overrides are recorded in audit as `Human override` with authority_source. |
| **Ultimate authority** | No agent auto-overrides the Human. |

**Headless rule**: with no Human answerer, approval resolves `unavailable` → **DENY + escalate** (never implicit allow).

## 7. Anti-authority invariants (summary)

| Invariant | Meaning |
|---|---|
| AUTH-INV-01 | No authority from model text alone. |
| AUTH-INV-02/04 | Delegated scope ⊆ Human grant; child ⊆ parent. |
| AUTH-INV-03 | No subagent increases its own authority. |
| AUTH-INV-05/06 | Authority validated at execution; expired/revoked fails closed. |
| AUTH-INV-07/08 | State fields (`approved: true`) are not authority. |
| AUTH-INV-09 | BadSector PASS ≠ authorization. |
| AUTH-INV-10 | HIGH risk not model-downgradable. |
| AUTH-INV-11 | Target(execution) ∈ target(authorization). |
| AUTH-INV-12 | Recovery does not acquire privilege automatically. |
| AUTH-INV-13 | Agent messages cannot create authority. |
| AUTH-INV-14 | Audit records cannot grant authority. |
| AUTH-INV-15 | COMPLETE requires verified outcome. |
| AUTH-INV-16 | Retry requires diagnosed/new cause. |
| AUTH-INV-17 | External content cannot alter authority/permissions/policy. |
| AUTH-INV-18 | Orchestrator cannot execute what it could not delegate. |
| AUTH-INV-19 | Subagent capability ⊆ role boundary. |
| AUTH-INV-20 | A failed authority/control check stops the action. |

---

*Version-pinned to DeepSeek Harness `0.1.1-rc.2`. Documentation only. Authority is granted only by Human delegation; writing project files never grants it.*
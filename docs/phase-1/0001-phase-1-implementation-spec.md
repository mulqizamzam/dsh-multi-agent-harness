# Phase-1 Implementation Specification — Multi-Agent Control Plane

- **Status**: proposal
- **Companion to**: `docs/adr/0001-multi-agent-control-plane-boundary.md` (revision 2)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally)
- **Scope**: `multi-agent-harness/`
- **This is a specification only.** It contains **no implementation code**, **no production agent prompts**, and **no production workflows**. Phase-1 execution is gated on the ADR's Phase-1 Entry Criteria.

---

## 1. Objective

Produce the **Phase-0 documentation artifacts** and the **Phase-1 control-plane skeleton** for the seven-specialist + orchestrator multi-agent system, such that:

- The three enforcement layers are made concrete (DSH-native enforcement, project control plane, Human authority) as set out in ADR 0001.
- The orchestrator's authority/gate semantics are specified (not executed).
- Project state and audit schemas are defined and validated.
- Role definitions and their mapping to DSH Agent Presets + per-role tool instances are specified.
- A repeatable test/validation path exists.
- **Nothing in Phase 1 executes consequential actions**; the only runtime activity is declarative scaffolding, schema authoring, documentation, and validation tests.

Non-objectives (explicitly out of scope): authoring production agent prompts, authoring production workflows, implementing any execution engine, modifying DSH core, touching sibling projects.

---

## 2. Scope

### In scope
- `multi-agent-harness/` (config, docs, agents, orchestrator, state, audit, tests).
- Documentation artifacts listed in ADR Decision 6.
- Schema files for authority/delegation, project state, and audit.
- Role definitions (declarative) and the role→preset→toolFilter mapping.
- Orchestrator contract (documented protocol) + a workflow **skeleton** (fan-out/collect, gates as placeholders).
- Validation tests.

### Out of scope (unless separately approved; see Constraints)
- Modifying DSH core.
- `project/`, `obsidian-vault/`, `memorycore/`, `.omni/`, or any other existing project/workspace.
- NK-Agent-OS integration.
- Agent Teams (`spawn_teammate`, `team_task_*`).
- Out-of-process subagent backends (acp/codex/claude-code/dsh-sdk).
- Executing the multi-agent pipeline end-to-end.

---

## 3. Architecture mapping

Maps the canonical architecture and the three layers onto the project structure.

| Architecture element | Maps to | Layer |
|---|---|---|
| Human (ultimate authority) | Human sessions + approval/override via `ask` policy | Human authority |
| Orchestrator | Root/main session + `workflow` scripts | Project control plane |
| Zeko (operations) | Role preset + per-role tool instance | DSH-native + project |
| CTO (engineering) | Role preset + per-role tool instance | DSH-native + project |
| CFO (finance) | Role preset + per-role tool instance | DSH-native + project |
| Kai (research) | Role preset + per-role tool instance | DSH-native + project |
| Somad (social) | Role preset + per-role tool instance | DSH-native + project |
| BadSector (review) | Role preset (read-only, no mutate/execute) + per-role tool instance | DSH-native + project |
| Nova (writing) | Role preset + per-role tool instance | DSH-native + project |
| Session sandbox / approval | DSH native `sandbox/mode` + `approval/policy` | DSH-native |
| ToolFilter / preset `disabled` rows | DSH native role/tool scoping | DSH-native |
| Authority gate / risk / evidence / conflict / review | Orchestrator control plane | Project control plane |
| Project state + audit ledger | `multi-agent-harness/state/`, `multi-agent-harness/audit/` | Project control plane |

---

## 4. Components

Planned components (specified here, not yet implemented):

1. **Role definitions** — one project role file per specialist + orchestrator (persona, domain, allowed tools, restricted tools, invariants).
2. **Role→preset/toolFilter mapping** — a declarative mapping from role files to DSH Agent Presets + per-role `tool-subagent` instance config (`toolName`, `toolFilter`, optional `persona`, `backgroundMode`, `maxDepth`).
3. **Permission/capability config** — the normalized capability×agent matrix (extending the existing `config/permissions.yaml`), clearly marked as *control-plane input*, not native DSH authorization.
4. **Authority & delegation registry** — scoped delegation object schema + registry in project state.
5. **Risk policy** — classification + risk-dimension config (`config/risk-policy.yaml`); no silent LOW downgrade.
6. **Audit schema** — project-level audit event schema + writer contract.
7. **Orchestrator contract** — documented delegation protocol, gate ownership, authority-gate semantics.
8. **Workflow skeleton** — deterministic fan-out/collect skeleton with gates as placeholder boundaries.
9. **Validation tests** — config/invariant validation (incl. `tests/validate-config.py`), state/audit schema checks, scenario harness skeleton.

---

## 5. File structure

Target layout under `multi-agent-harness/` (extends the PRD §18 structure). Only the files marked **existing** are present today; the rest are **planned / to be created in Phase 1**.

```text
multi-agent-harness/
├── README.md                              # planned
├── AGENTS.md                              # planned
├── PRD.md                                 # planned (pointer to canonical PRD)
├── config/
│   ├── permissions.yaml                   # existing (capability×agent; control-plane input)
│   ├── agents.yaml                        # existing (agent registry)
│   ├── authority.yaml                     # planned (project authority model input)
│   ├── risk-policy.yaml                   # planned
│   └── project-defaults.yaml              # planned
├── agents/
│   ├── zeko/    ├── AGENT.md, policy.yaml # planned (per role)
│   ├── cto/     ├── AGENT.md, policy.yaml # planned
│   ├── cfo/     ├── AGENT.md, policy.yaml # planned
│   ├── kai/     ├── AGENT.md, policy.yaml # planned
│   ├── somad/   ├── AGENT.md, policy.yaml # planned
│   ├── badsector/ ├── AGENT.md, policy.yaml # planned
│   └── nova/    ├── AGENT.md, policy.yaml # planned
├── orchestrator/
│   ├── AGENT.md                           # planned
│   ├── router/                            # planned
│   ├── workflows/                         # planned (skeleton only)
│   ├── gates/                             # planned (authority/risk/evidence/conflict contracts)
│   └── recovery/                          # planned
├── state/
│   ├── projects/                          # planned
│   ├── tasks/                             # planned
│   ├── decisions/                         # planned
│   └── approvals/                         # planned
├── audit/                                 # planned (project audit ledger)
├── tests/
│   ├── validate-config.py                 # planned (referenced by existing config)
│   ├── unit/                              # planned
│   ├── workflow/                          # planned
│   ├── authorization/                     # planned
│   ├── adversarial/                       # planned
│   └── scenarios/                         # planned
└── docs/                                  # present dir
    ├── adr/0001-multi-agent-control-plane-boundary.md   # existing (this ADR, revised)
    ├── phase-1/0001-phase-1-implementation-spec.md      # existing (this spec)
    ├── tool-catalog.md                    # planned (Phase-0 artifact)
    ├── operations.md                      # planned (Phase-0 artifact)
    ├── architecture.md                    # planned (Phase-0 artifact)
    ├── authority.md                       # planned (Phase-0 artifact)
    └── runbooks/                          # planned (Phase-5 hardening)
```

---

## 6. Dependencies

### On DSH (all VERIFIED in `0.1.1-rc.2`)
- Session sandbox (`sandbox/mode`), session approval (`approval/policy` `ask`/`never`).
- Tool registry + `toolFilter` (`allow`/`deny`) + preset `disabled` rows.
- Agent Presets (per-role `agent.cordis.yml`), `composeFrom()` for child binding.
- `subagent`/`subagent_fork` in-process providers (`outputSchema`, `depthLimit`, `toolFilter`, `persona`).
- `workflow` tool (JS orchestration; `parallel`/`pipeline`/`phase`/`agent()`/`outputSchema`).
- Session JSONL persistence + log-only audit events.
- Cancellation/timeout primitives (`signal`, `job_kill`, `interrupt_agent`, tool timeouts).

### On project (planned)
- Project state/audit file readers/writers (atomic temp-write + rename + version check).
- Role→preset→toolFilter mapping loader.
- Orchestrator contract (protocol definitions).

### Not relied on (BLOCKED/UNKNOWN, per ADR)
- DSH `storage` hub (not mounted).
- Agent Teams (not mounted, out of scope).
- Out-of-process subagent backends (disabled, out of scope).

---

## 7. Interfaces / Schemas (specified, not implemented)

### 7.1 Delegation object (authority schema)
```yaml
delegation:
  id: string                 # delegation-<n>
  principal: human
  delegate: orchestrator
  project: string            # project-id
  scope:
    operations: []           # task categories permitted
    resources: []            # resources in scope
    environments: []         # permitted environments
    maximum_cost: null
  prohibited_actions: []     # hard denials
  requires_approval: []      # destructive|financial_transfer|sensitive_publication|credential_change
  expires_at: timestamp|null
```

### 7.2 Project state schema
```yaml
project:
  id: string
  name: string
  objective: string
  status: string             # pending|active|blocked|complete
  created_at: timestamp
  updated_at: timestamp
authorization:
  active_delegations: []
tasks: []
agents:
  zeko: { status: string }
  cto: { status: string }
  cfo: { status: string }
  kai: { status: string }
  somad: { status: string }
  badsector: { status: string }
  nova: { status: string }
decisions: []
risks: []
evidence: []
approvals: []
events: []
current_state:
  phase: string
  next_action: string
```

### 7.3 Audit event schema
```yaml
event:
  timestamp: timestamp
  actor: string
  actor_type: human|orchestrator|agent
  action: string
  target: string
  project: string
  task_id: string|null
  authority_source: string|null   # delegation id / human approval id, if applicable
  evidence: []                    # references, not secrets
  previous_state: any
  new_state: any
  result: string
  error: string|null
```

### 7.4 Role→preset/toolFilter mapping (conceptual)
```yaml
role:
  id: zeko                        # one of 7 specialists (+ orchestrator)
  preset: agent-presets/zeko      # DSH Agent Preset id
  subagent_tool:
    tool_name: subagent_zeko
    tool_filter: { allow: [bash, read, glob, job_output, ...] }   # domain tools only
    persona: zeko-operations
    max_depth: 3
```

### 7.5 Orchestrator contract (gate ownership)
- **Gates owned by orchestrator**: authority gate, risk gate, evidence gate, conflict gate, BadSector review trigger.
- **Gates as placeholders** in the workflow skeleton: authority/risk/evidence/conflict boundaries; no execution.
- **Never** treat BadSector PASS as authorization; **never** let model judgment bypass the authority gate.

---

## 8. Test strategy

1. **Config/invariant validation** — `tests/validate-config.py` (referenced by existing config): assert specialist count = 7, peer relationship, BadSector never executes, Kai never executes, CFO no transaction by default, destructive always requires approval or denied, orchestrator is not an eighth specialist.
2. **Schema validation** — unit tests against delegation/state/audit schemas (version, required fields, type).
3. **Role/mapping validation** — ensure each role's toolFilter denies off-domain tools and that reviewer/executor boundaries hold.
4. **Workflow skeleton tests** — fan-out/collect shape; gates as placeholder boundaries (no execution).
5. **Scenario harness skeletons** — PRD §17 Phase-6 scenarios (simple research, code change, infrastructure incident, pricing, social campaign, novel editing, high-impact requiring Human approval, conflicting outputs, failed deployment, unauthorized destructive request) as skeletons; executed in a later phase.
6. **Security-focused tests** (at the control-plane level) — authority gate rejects when no delegation; BadSector PASS does not authorize; no model-judgment bypass.

> Phase-1 tests are **validation/schema/contract** tests. They do **not** execute the pipeline end-to-end and do **not** touch production.

---

## 9. Security constraints

- **Session policy** for development must be `workspace-write` + `ask`; never `danger-full-access` + `never`.
- **Boundary** — all writes confined to `multi-agent-harness/`; no DSH core; no sibling projects; no state outside `multi-agent-harness/state/` + `audit/`.
- **No secrets** in project state/audit files; reference secret-backed config instead of echoing secrets (PRD §12).
- **Least privilege** — review role (BadSector) gets no mutate/execute tools and no authorization path; executor roles only their domain tools.
- **Authority** — granted only by Human delegation; the authority gate fails closed and escalates to Human.
- **Prompt-injection / external-content trust** — **unresolved** until verified. Phase 1 must design the control plane to treat all external/subagent output as data, not instructions, and must not claim a security guarantee on this axis yet.
- **Workflow scripts are not a security boundary** — gate decisions are validated by the orchestrator, not trusted from a script.

---

## 10. Acceptance criteria (Phase-1 outputs)

Phase 1 is complete when all the following deliverables exist and pass validation:

- [ ] Phase-0 documentation artifacts (`tool-catalog.md`, `operations.md`, `architecture.md`, `authority.md`, `runbooks/`) created, version-pinned, and referenced by config.
- [ ] Authority/delegation schema defined and validated.
- [ ] Audit schema defined and validated.
- [ ] Seven role definitions (+ orchestrator) authored as project role files.
- [ ] Role→preset/toolFilter mapping defined and validated.
- [ ] Orchestrator contract documented (gate ownership, delegation protocol).
- [ ] Workflow skeleton (fan-out/collect) present with gates as placeholders.
- [ ] Project state structure (`multi-agent-harness/state/`) + atomic-write/version-check helpers.
- [ ] Validation tests pass (config/invariants, schema, role/mapping, workflow skeleton, scenario skeletons).
- [ ] No production agent prompts, no production workflows, no execution engine — confirmed absent.

---

## 11. Known limitations

1. **Per-agent sandbox/approval not natively expressible** — role isolation is via toolFilter (availability), not a per-agent sandbox. Sandbox/approval stay session-level.
2. **`toolFilter`/`persona` are config-level, not per-call** — the orchestrator cannot override a role's scope per task without additional machinery/instances.
3. **Workflow scripts are model-authored** — not a hard security boundary; gates must be enforced by the orchestrator/Human.
4. **No filesystem/network in workflow scripts** — state writes must happen via subagent tools or returned to the orchestrator to persist.
5. **No DSH `storage` hub** (not mounted) — project state is file-based; atomic-write/version-check is ours to implement.
6. **Session-scoped goals** — goals do not persist across sessions; project state/audit is the durable cross-turn record.
7. **Prompt-injection handling unverified** — no security claim until verified.

---

## 12. Rollback strategy

- **Boundary/scope is a declaration** — reversible by widening only with explicit permission.
- **Decisions are HUMAN_PENDING** — before Phase 1, any decision can be reopened with no artifact cost.
- **File-based state/audit** — reversible early; the read/write API is ours, so a backend swap (e.g. to a mounted DSH `storage` hub) is possible later.
- **DSH composition changes are a controlled exception** — any project profile/preset change must be reversible (keep a patch/record) and reviewed; DSH core is never modified.
- **Nothing consequential executes in Phase 1** — there is effectively nothing to "roll back" beyond removing scaffolding and docs.

---

## 13. Unresolved questions

1. **Prompt-injection / external-content trust** — does DSH treat external/subagent content as non-authoritative data? UNKNOWN; must be verified before security claims.
2. **DSH `storage` hub** — will it ever be mounted (composition change, reversible)? Currently BLOCKED/unmounted.
3. **Agent Teams** — definitively out of scope for V1? (Recommended yes; needs confirmation.)
4. **Out-of-process subagent backends** — definitively out of scope for V1? (Recommended yes; needs confirmation.)
5. **Role→preset mapping details** — exact per-role `toolFilter` allow/deny sets and `maxDepth` values (to be finalized in Phase-1 authoring).
6. **`web_fetch`** — is it needed for Kai research? UNKNOWN; currently disabled in the standard preset.
7. **Per-agent `sandbox`/`approval` in `config/permissions.yaml`** — how to treat given they are non-enforceable per-agent (INFERRED; needs confirmation).

---

## 14. Acceptance of this spec

This specification is **not** approved and is **not** executable yet. Phase-1 execution requires the ADR Phase-1 Entry Criteria to be met (Human acceptance, safe dev policy, confirmed scope, documented blockers, and this plan). It is provided so the Human can review the intended Phase-1 scope before any implementation.

---

*Status: proposal. No Phase-1 implementation has begun; no code, production agent prompts, or production workflows are authored by this document.*

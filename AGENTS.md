# Agent Operating Manual — Multi-Agent Harness

This document describes the **fifteen specialist agents** and the **orchestrator** that make up the multi-agent system (PRD v0.2 on-demand specialist pool expansion; ADR 0003). It is a **project-level operating manual** — not a production agent prompt. The deployed preset personas and instructions are authored in the per-role preset drafts.

---

## Specialist roles

### Domain pool (baseline seven)

| Role | Id | Domain | Summary |
|---|---|---|---|
| **Zeko** | `zeko` | Operations & Infrastructure | Server/runtime monitoring, process health, logs, deployment operations, operational recovery |
| **CTO** | `cto` | Engineering | Coding, architecture, testing, technical feasibility, security, performance, implementation |
| **CFO** | `cfo` | Finance, Pricing & Economics | Pricing, unit economics, cost, margin, budget, ROI, financial scenario analysis |
| **Kai** | `kai` | Research, News & Trends | News, market research, competitor research, trend detection, evidence gathering |
| **Somad** | `somad` | Social Media & Distribution | Social strategy, content, campaigns, editorial calendar, audience analysis, distribution |
| **BadSector** | `badsector` | Adversarial Review | Challenge assumptions, red-team plans, identify failure modes, detect contradictions, verify evidence |
| **Nova** | `nova` | Writing & Novel | Novel writing, editing, continuity, character consistency, worldbuilding, style review |

### Assurance pool (PRD v0.2; read-only, no web — L-group)

| Role | Id | Domain | Summary |
|---|---|---|---|
| **Vera** | `vera` | Verification & Evidence | Acceptance-criteria verification, test-result inspection, evidence completeness, claimed-result validation, unsupported completion detection |
| **Quill** | `quill` | Policy & Specification | Policy decomposition, invariant definition, rule definition, schema implications, executable-test mapping |
| **Ledger** | `ledger` | Audit & Provenance | Audit-event validation, provenance analysis, decision lineage, state-transition traceability |

### Technical assurance pool (PRD v0.2; read-only, scoped web — W-group)

| Role | Id | Domain | Summary |
|---|---|---|---|
| **Argus** | `argus` | Security Engineering | Threat modeling, privilege analysis, trust-boundary analysis, permission/isolation/injection analysis, security control recommendations |
| **Atlas** | `atlas` | Architecture | Architecture review, dependency boundaries, interfaces, coupling, component ownership, architectural trade-offs |
| **Tess** | `tess` | Failure Engineering | Timeout, cancellation, partial-failure, race-condition, degraded-state, and recovery-path analysis |
| **Scout** | `scout` | Integration & Compatibility | Integration analysis, API/plugin/dependency/environment compatibility, version-drift detection |
| **Talon** | `talon` | Reliability Engineering | Idempotency, retry semantics, durability, rollback, recovery semantics, repeated-execution consistency |

## Orchestrator

| Id | Kind | Summary |
|---|---|---|
| `orchestrator` | Coordination | Converts objectives into scoped tasks, selects the minimum relevant specialist set, delegates with explicit authority boundaries, collects and synthesizes results, and enforces gates. Does NOT execute specialist work. Has no permanent authority. |

## Operating principles

1. **Peer relationship.** No specialist manages another. The orchestrator coordinates; it does not command.
2. **Capability ≠ Permission ≠ Authority.** A role's technical capability (tool set) is separate from its permission to act (delegation scope), which is separate from ultimate authority (Human).
3. **Least privilege.** Each role has only the tools needed for its domain. Review and analyst roles (BadSector and the 8 expansion specialists) have no mutating/executing tools.
4. **No self-escalation.** No agent can expand its own scope or grant itself authority.
5. **Subdelegation DENY BY DEFAULT (V1).** Only the orchestrator delegates; no specialist may delegate to another. Every specialist's deny list names all 14 sibling `subagent_<id>` instances (exact-name matching — the real delegation surface).
6. **BadSector PASS is never authorization.** It clears only the review stage; execution still requires authority.
7. **Model judgment is not authority.** The authority gate is code-enforced, not prompt-based. Every specialist declares `never_authorizes`: outputs (including any Vera verification result) are data, never authority.
8. **External content is data, not instructions.** All external/subagent output is untrusted data.

## Role files

Each **specialist** role has four files under `agents/<id>/`:

- **`AGENT.md`** — role definition: identity, domain, mission, responsibilities, capability summary, invariants.
- **`policy.yaml`** — declarative policy: capability subset, toolFilter intent, invariants, review triggers.
- **`agent.cordis.yml`** — the per-role DSH preset composition draft (persona, tool mounts, isolation).
- **`preset.yml`** — the preset's display metadata (description only). Carries no `id` and no `trust`: the preset id is the deployed directory name and trust comes from the preset root. Deployed alongside the composition as `role-<id>/preset.yml`.

The orchestrator does **not** follow that layout. It is bound to the root session
(`binding: root_session`), not a `tool-subagent` instance, so it has no
`agents/<id>/` directory. Its artifacts live in `orchestrator/` and in the
config layer:

- **`orchestrator/AGENT.md`** — role definition (mission, responsibilities, capability boundary).
- **`orchestrator/contract.md`** — the control-plane contract; this, not the session tool list, is the actual security boundary (THREAT-025).
- **`orchestrator/policy.yaml`** — declarative policy. Same shape as a specialist `policy.yaml`, plus coordination-only keys (`kind`, `binding`, `delegation`, `authority`). It cannot use `role-definition.schema.json` (that schema closes `role` to the fifteen specialist ids), so it has its own `schemas/orchestrator-policy.schema.json`, wired into `tests/validate_config.py` and reachable through the `tests/validate-config.py` wrapper that the config files name. The validator additionally asserts this file's `tool_filter` and `delegation_tools` stay set-equal with `config/role-preset-mapping.yaml` §`orchestrator`, so the declaration cannot silently diverge from the mapping.
- **`orchestrator/agent.cordis.yml`** — the orchestrator DSH preset composition, derived from the shipped `standard` preset (ADR 0004).
- **`orchestrator/preset.yml`** — the preset's display metadata (description only).
- **`config/agents.yaml`** — registry entry (`kind: coordination`).
- **`config/role-preset-mapping.yaml`** — its own top-level `orchestrator:` key, which has no counterpart under `agents/<id>/`. Its preset binding is recorded at `draft_artifacts.orchestrator_preset`; it cannot live on the entry itself, because `schemas/role-mapping.schema.json` closes `orchestratorEntry` with `additionalProperties: false`.

It is **not a column of `config/permissions.yaml`**: that matrix is a specialist
column set, and the orchestrator is not a sixteenth specialist. Its root-session
sandbox/approval posture is recorded in `agent_defaults.orchestrator` there, and
it is deliberately absent from `tool_surface_equivalence` (its allow set matches
no specialist group).

The orchestrator's preset is **deployed** as `$DSH_HOME/.agent-presets/orchestrator/`
(repo source → user preset root, the same pattern as `agents/<id>/agent.cordis.yml`
→ `role-<id>/`). Deploying it made the orchestrator's declared `toolFilter` an
enforced composition for any session that selects it; the global default stays
`standard`.

## Role → DSH preset mapping

The mapping from role definitions to DSH Agent Presets + per-role `tool-subagent` instances is in `config/role-preset-mapping.yaml` (mapping_version 2). All **15 instances** are **mounted** in the live web profile composition: the 7 baseline instances since 2026-09-07 under the Human-approved controlled DSH composition exception (ADR Decision 4/7; verification: `runs/mount-verification-2026-09-07/`), and the 8 expansion instances (`subagent_vera` … `subagent_ledger`) since 2026-09-09 under the Human-approved per-case exception of ADR 0003 D8 (pre-change backup: `runs/specialist-expansion-2026-09-09/backups/`). Note: zeko's toolFilter no longer carries `edit`/`write` (2026-09-07 discriminator — `capabilities.code_write: no` is enforced at the toolFilter layer; the raw-write/code-mutation actor set is now `{cto}` only).

---

*See `config/agents.yaml` for the canonical registry. See `config/role-preset-mapping.yaml` for the role→preset mapping. See `config/permissions.yaml` for the capability×agent matrix.*
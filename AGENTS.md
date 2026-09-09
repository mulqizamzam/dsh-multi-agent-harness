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

Each role has three files under `agents/<id>/`:

- **`AGENT.md`** — role definition: identity, domain, mission, responsibilities, capability summary, invariants.
- **`policy.yaml`** — declarative policy: capability subset, toolFilter intent, invariants, review triggers.
- **`agent.cordis.yml`** — the per-role DSH preset composition draft (persona, tool mounts, isolation).

The orchestrator has corresponding files under `orchestrator/`.

## Role → DSH preset mapping

The mapping from role definitions to DSH Agent Presets + per-role `tool-subagent` instances is in `config/role-preset-mapping.yaml` (mapping_version 2). The **7 baseline instances** are **mounted** in the live web profile composition since 2026-09-07 under the Human-approved controlled DSH composition exception (ADR Decision 4/7; verification: `runs/mount-verification-2026-09-07/`). The **8 expansion instances** (`subagent_vera` … `subagent_ledger`) are **registered-not-mounted** (PRD v0.2 / ADR 0003 D8): they become live only through a separate Human per-case composition exception. Registration ≠ activation. Note: zeko's toolFilter no longer carries `edit`/`write` (2026-09-07 discriminator — `capabilities.code_write: no` is enforced at the toolFilter layer; the raw-write/code-mutation actor set is now `{cto}` only).

---

*See `config/agents.yaml` for the canonical registry. See `config/role-preset-mapping.yaml` for the role→preset mapping. See `config/permissions.yaml` for the capability×agent matrix.*
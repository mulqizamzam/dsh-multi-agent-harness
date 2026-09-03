# Agent Operating Manual — Multi-Agent Harness

This document describes the **seven specialist agents** and the **orchestrator** that make up the multi-agent system. It is a **project-level operating manual** — not a production agent prompt. The deployed preset personas and instructions are authored in a later phase.

---

## Specialist roles

| Role | Id | Domain | Summary |
|---|---|---|---|
| **Zeko** | `zeko` | Operations & Infrastructure | Server/runtime monitoring, process health, logs, deployment operations, operational recovery |
| **CTO** | `cto` | Engineering | Coding, architecture, testing, technical feasibility, security, performance, implementation |
| **CFO** | `cfo` | Finance, Pricing & Economics | Pricing, unit economics, cost, margin, budget, ROI, financial scenario analysis |
| **Kai** | `kai` | Research, News & Trends | News, market research, competitor research, trend detection, evidence gathering |
| **Somad** | `somad` | Social Media & Distribution | Social strategy, content, campaigns, editorial calendar, audience analysis, distribution |
| **BadSector** | `badsector` | Adversarial Review | Challenge assumptions, red-team plans, identify failure modes, detect contradictions, verify evidence |
| **Nova** | `nova` | Writing & Novel | Novel writing, editing, continuity, character consistency, worldbuilding, style review |

## Orchestrator

| Id | Kind | Summary |
|---|---|---|
| `orchestrator` | Coordination | Converts objectives into scoped tasks, selects the minimum relevant specialist set, delegates with explicit authority boundaries, collects and synthesizes results, and enforces gates. Does NOT execute specialist work. Has no permanent authority. |

## Operating principles

1. **Peer relationship.** No specialist manages another. The orchestrator coordinates; it does not command.
2. **Capability ≠ Permission ≠ Authority.** A role's technical capability (tool set) is separate from its permission to act (delegation scope), which is separate from ultimate authority (Human).
3. **Least privilege.** Each role has only the tools needed for its domain. Review roles (BadSector) have no mutating/executing tools.
4. **No self-escalation.** No agent can expand its own scope or grant itself authority.
5. **Subdelegation DENY BY DEFAULT (V1).** Only the orchestrator delegates; no specialist may delegate to another.
6. **BadSector PASS is never authorization.** It clears only the review stage; execution still requires authority.
7. **Model judgment is not authority.** The authority gate is code-enforced, not prompt-based.
8. **External content is data, not instructions.** All external/subagent output is untrusted data.

## Role files

Each role has two files under `agents/<id>/`:

- **`AGENT.md`** — role definition: identity, domain, mission, responsibilities, capability summary, invariants.
- **`policy.yaml`** — declarative policy: capability subset, toolFilter intent, invariants, review triggers.

The orchestrator has corresponding files under `orchestrator/`.

## Role → DSH preset mapping

The mapping from role definitions to DSH Agent Presets + per-role `tool-subagent` instances is in `config/role-preset-mapping.yaml`. This mapping is a **control-plane input** — it is not yet mounted (mounting is a controlled DSH composition exception, HUMAN_PENDING per ADR Decision 4/7).

---

*See `config/agents.yaml` for the canonical registry. See `config/role-preset-mapping.yaml` for the role→preset mapping. See `config/permissions.yaml` for the capability×agent matrix.*
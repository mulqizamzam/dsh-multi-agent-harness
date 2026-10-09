# Multi-Agent Harness — Control Plane

A **fifteen-specialist + orchestrator** multi-agent system built on [DeepSeek Harness](https://github.com/deepseek-ai/dsh) (version `0.2.0-rc.2`): 7 active baseline specialists + 8 registered-not-mounted expansion specialists (PRD v0.2 / ADR 0003).

**Version pin: DeepSeek Harness `0.2.0-rc.2`** — re-verified 2026-10-09 by the full test suite against the running checkout (previously `0.1.1-rc.2`). Later releases require re-verification.

---

## Architecture (canonical)

```
Human                         ←  ultimate authority
  │
  ▼
Orchestrator                  ←  coordinator + delegated decision-maker
  │
  ▼
7 peer specialist agents (active baseline):  ←  peers; no specialist manages another
  Zeko  (operations)
  CTO   (engineering)
  CFO   (finance)
  Kai   (research)
  Somad (social)
  BadSector (adversarial review)
  Nova  (writing)
+ 8 registered expansion specialists (PRD v0.2, not yet mounted):
  Vera (verification)  Argus (security)  Atlas (architecture)
  Tess (failure)  Quill (policy)  Scout (integration)
  Talon (reliability)  Ledger (audit)
```

- **Human** is the ultimate authority: approves, delegates, revokes, and may override.
- **Orchestrator** coordinates and owns the project control plane; it does **not** own every domain and has no permanent authority.
- **All fifteen specialists are peers** (7 active baseline + 8 registered expansion). BadSector reviews/challenges; it never authorizes and never executes the reviewed plan.

## Three enforcement layers

| Layer | What | Who enforces |
|---|---|---|
| **DSH-native** | Session sandbox, approval policy, toolFilter, Agent Presets, subagent execution, workflow coordination, session persistence, cancellation | DSH engine (per-session / config-level) |
| **Project control plane** | Role definitions, routing, delegation registry, authority/risk/evidence/conflict gates, BadSector review, project state, audit ledger | `multi-agent-harness/` orchestrator contract |
| **Human authority** | Ultimate approval, delegation, revocation, override | Human |

## Project structure

```
multi-agent-harness/
├── README.md                    # this file
├── AGENTS.md                    # agent operating manual
├── PRD.md                       # pointer to canonical PRD
├── config/
│   ├── agents.yaml              # agent registry (finalized)
│   ├── permissions.yaml         # capability×agent matrix (control-plane input)
│   └── role-preset-mapping.yaml # role→DSH preset/toolFilter mapping
├── agents/                        # 15 role dirs (7 baseline + 8 PRD v0.2 expansion);
│   │                              # each: AGENT.md, policy.yaml, agent.cordis.yml
│   ├── zeko/ cto/ cfo/ kai/ somad/ badsector/ nova/      # baseline (mounted)
│   └── vera/ argus/ atlas/ tess/ quill/ scout/ talon/ ledger/  # expansion (registered)
├── orchestrator/
│   ├── AGENT.md                 # orchestrator role definition
│   ├── contract.md              # orchestrator contract (gate ownership, protocol)
│   └── workflows/
│       ├── README.md            # workflow skeleton documentation
│       └── skeleton.js          # fan-out/collect skeleton with gate placeholders
├── state/
│   ├── helpers/                 # atomic-write + version-check helpers (Phase 1B)
│   └── registry/                # protected delegation registry directory (ADR 0002)
├── audit/
│   └── helpers/                 # append-only audit log helpers (Phase 1B)
├── tests/                       # validation test suite (Phase 1B)
│   ├── README.md                # test strategy
│   ├── validate-config.py       # standalone config validator (referenced by config files)
│   ├── control_plane.py         # reference authority gate + risk + registry (test-support)
│   ├── unit/                    # config, schema, state/audit helper tests
│   ├── authorization/           # AUTH-*, ISO-*, REG-*, DLG-*, RISK-* executable tests
│   ├── adversarial/             # INJ-* quarantine + BAD-* provenance tests
│   ├── scenarios/               # PRD §17 Phase-6 scenario skeletons
│   └── workflow/                # workflow skeleton shape validation
├── schemas/                     # JSON Schema (draft 2020-12)
│   ├── README.md
│   ├── delegation.schema.json
│   ├── project-state.schema.json
│   ├── audit-event.schema.json
│   ├── role-definition.schema.json
│   ├── role-mapping.schema.json
│   └── agent-registry.schema.json
└── docs/
    ├── README.md                # doc index
    ├── adr/0001-multi-agent-control-plane-boundary.md  # ADR 0001 (accepted foundation)
    ├── adr/0002-registry-protection-mechanism.md  # ADR 0002 (delegation registry protection, Phase 1B)
    ├── tool-catalog.md          # Phase-0: scoped capability matrix
    ├── operations.md            # Phase-0: operator/deployment mapping
    ├── architecture.md          # Phase-0: architecture summary
    ├── authority.md             # Phase-0: authority model doc
    ├── runbooks/                # Phase-5: intent / placeholders
    ├── phase-1/0001-phase-1-implementation-spec.md  # Phase-1 spec
    ├── security/
    │   ├── 0001-control-assurance-spec.md
    │   └── 0002-threat-model-and-control-architecture.md
    └── design/0001-control-design-and-test-plan.md
```

## Phase status

| Phase | Status | What it produces |
|---|---|---|
| Phase 0 (Foundation) | **COMPLETE** | ADR, Phase-1 spec, security specs, design+test plan, agent registry, capability matrix |
| Phase 1A (Structure) | **COMPLETE** | Phase-0 docs, role definitions, role→preset mapping, orchestrator contract, baseline schemas, finalized structure |
| Phase 1B (Skeleton) | **COMPLETE** | Validation test suite, state/audit integrity helpers, ADR 0002 (registry protection decision), workflow skeleton |
| Later phases | Planned | Production control plane, production workflows, execution engine, integration, hardening |

## Human decisions

All Phase-0 decisions are documented in ADR 0001. Key current status:

| Decision | Status |
|---|---|
| 1. Per-agent permission vs session sandbox/approval | **HUMAN_APPROVED** — two-tier model (per-role toolFilter + per-session sandbox/approval) |
| 2. Dev session safety policy | **HUMAN_APPROVED** — `workspace-write` + `ask`; session verified |
| 3. Orchestrator architecture | **HUMAN_APPROVED** — hybrid root-session + workflow fan-out/collect |
| 4. Role isolation mechanism | **HUMAN_APPROVED** — per-role presets + per-role tool-subagent/toolFilter instances |
| 5. State & audit persistence | **HUMAN_APPROVED** — file-based under `multi-agent-harness/` |
| 6. Phase-0 docs | **HUMAN_APPROVED** — created, version-pinned to `0.1.1-rc.2` |
| 7. Phase-1 scope boundary | **HUMAN_APPROVED** — strictly `multi-agent-harness/`; DSH profile/preset change is a per-case exception |

All D1–D7 decisions were explicitly approved by the Human (2026-08-29). Fixed V1 safety defaults remain in force: subdelegation DENY BY DEFAULT; BadSector PASS ≠ authorization; model text ≠ authority; project state ≠ authority; no COMPLETE without verification; no blind retry; no scope expansion; no DSH core modification.

---

*Version-pinned to DeepSeek Harness `0.2.0-rc.2` (re-verified 2026-10-09; previously `0.1.1-rc.2`). See `docs/` for full documentation set.*
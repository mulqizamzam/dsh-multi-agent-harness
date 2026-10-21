# DSH Plugin

This repository is also a **DSH Cordis plugin** (`dsh-multi-agent-harness`) — not
just the multi-agent control plane documented below.

It registers the **16 agent presets** — the 15 `role-*` specialists under
`agents/<id>/` and the `orchestrator` root-session preset under `orchestrator/` —
directly from this repository's own files with the agent-preset registry
(`ctx.agentPresets.register`). There is **no `.agent-presets/` deployment copy**:
these repo files are the single source of truth. The plugin is self-locating —
it resolves its own root from `import.meta.url`, reads no env vars, and takes no
configuration.

Registered preset ids (must match the live web profile wiring exactly):

`role-argus`, `role-atlas`, `role-badsector`, `role-cfo`, `role-cto`,
`role-kai`, `role-ledger`, `role-nova`, `role-quill`, `role-scout`,
`role-somad`, `role-talon`, `role-tess`, `role-vera`, `role-zeko`, and
`orchestrator`.

> **Dialect requirement.** Every `agent.cordis.yml` must use the **RUNNING**
> harness's persona key. `@deepseek-ai/dsh-persona` on `0.2.0-rc.2` takes
> `prefix:`, **not** the `0.1.1-rc.2` `text:` key. A preset still using `text:`
> mounts `broken` and cannot be selected in the GUI.

## Install

Wire it into a DSH profile two ways, exactly like any bundle plugin:

- **Profile dependency** — add `dsh-multi-agent-harness` (link to this repo) to
  the profile's `package.json` `dependencies`.
- **Bundle entry** — add `dsh-multi-agent-harness` to that profile's
  `dsh.profile.bundles` list, which mounts this package's own
  `cordis.patch.yml` (its `dsh.bundle.patch`).

This plugin **replaces `dsh-agent-preset-roster`**: remove that dependency and
its bundle entry when adding this one. A host restart registers all 16 presets;
the boot log carries two tagged lines, e.g.

```
[dsh-multi-agent-harness] registered 16 presets from <repo root> (skipped 0 already registered, 0 failed)
[dsh-multi-agent-harness] roster audit: 20 presets in roster, none broken
```

The first line counts registrations; the second is a deferred roster read that
reports activation failures, because `register()` settles activation without
throwing — a preset whose composition cannot mount is recorded `broken` by the
registry and stays visible in the roster rather than failing the boot.

> **No roster read at apply time.** `agentPresets.list()` re-audits every
> mounted preset and, while any of them still has a row waiting for a service,
> awaits the host Loader (`agent-preset-registry/src/index.ts:135-139`) — which
> waits on this plugin row's own activation, so calling it from `apply` would
> hang host boot the moment any listed preset had a pending row. This plugin
> registers without a snapshot: the registry rejects a duplicate id atomically
> before any await (`src/index.ts:82-85`) and the per-preset catch absorbs it.

---

# Multi-Agent Harness — Control Plane

A **fifteen-specialist + orchestrator** multi-agent system built on [DeepSeek Harness](https://github.com/deepseek-ai/dsh) (version `0.2.0-rc.2`): 7 active baseline specialists + 8 expansion specialists, all 15 mounted (PRD v0.2 / ADR 0003).

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
+ 8 expansion specialists (PRD v0.2; mounted 2026-09-09):
  Vera (verification)  Argus (security)  Atlas (architecture)
  Tess (failure)  Quill (policy)  Scout (integration)
  Talon (reliability)  Ledger (audit)
```

- **Human** is the ultimate authority: approves, delegates, revokes, and may override.
- **Orchestrator** coordinates and owns the project control plane; it does **not** own every domain and has no permanent authority.
- **All fifteen specialists are peers** (7 active baseline + 8 expansion), all mounted. BadSector reviews/challenges; it never authorizes and never executes the reviewed plan.

## Three enforcement layers

| Layer | What | Who enforces |
|---|---|---|
| **DSH-native** | Session sandbox, approval policy, Agent Presets, per-role tool surfaces, subagent execution, workflow coordination, session persistence, cancellation | DSH engine (per-session / config-level) |
| **Project control plane** | Role definitions, routing, delegation registry, authority/risk/evidence/conflict gates, BadSector review, project state, audit ledger | `multi-agent-harness/` orchestrator contract |
| **Human authority** | Ultimate approval, delegation, revocation, override | Human |

## Project structure

```
multi-agent-harness/
├── README.md                    # this file
├── AGENTS.md                    # agent operating manual (16 personas)
├── LICENSE                      # license
├── PRD.md                       # pointer to canonical PRD (PRD-v0.2.md)
├── index.js                     # plugin entry: file-driven agent-preset registration
├── cordis.patch.yml             # plugin manifest (one bundle insert row mounts the plugin)
├── package.json                 # plugin package metadata (name: dsh-multi-agent-harness)
├── pytest.ini                   # pytest configuration
├── config/
│   ├── agents.yaml              # agent registry (finalized: 15 specialists + orchestrator)
│   ├── permissions.yaml         # capability×agent matrix (control-plane input)
│   ├── registry-writer.yaml     # single-writer delegation-registry daemon config
│   ├── role-preset-mapping.yaml # role→DSH Agent Preset / tool-surface mapping (mapping_version 3)
│   └── tool-subagent-instances.yaml # per-role tool-subagent instance rows
├── agents/                      # 15 role dirs (7 baseline + 8 PRD v0.2 expansion); all mounted;
│   │                            # each: AGENT.md, policy.yaml, agent.cordis.yml, preset.yml
│   ├── zeko/ cto/ cfo/ kai/ somad/ badsector/ nova/  # baseline (mounted 2026-09-07)
│   └── vera/ argus/ atlas/ tess/ quill/ scout/ talon/ ledger/  # expansion (mounted 2026-09-09)
├── orchestrator/
│   ├── AGENT.md                 # orchestrator role definition
│   ├── contract.md              # orchestrator contract (gate ownership, protocol)
│   ├── policy.yaml              # orchestrator declarative policy (coordination-only keys)
│   ├── agent.cordis.yml         # orchestrator DSH preset composition (15 instance rows)
│   ├── preset.yml               # orchestrator preset display metadata
│   ├── foundation/              # gates, state, contracts, messaging, routing, workflow, context
│   ├── execution/               # engine, recovery_runtime, request
│   ├── runtime/                 # audit, delegation, lifecycle, flow, gates, parallel, result, store
│   ├── production/              # planner, executor, lifecycle, report
│   ├── organization/            # waves, packet, evidence, handoff, metrics, rework, runner, root
│   ├── entrypoint/              # __main__ + entry
│   ├── dsh/                     # DSH backend bridge / client / resolver / provenance
│   └── workflows/               # README.md, skeleton.js, skeleton.schema.json (15-phase chain)
├── control/                     # control-plane gates (authority, risk, evidence, conflict, execution, recovery, verification)
├── registry_writer/             # delegation-registry provider / daemon / client
├── observability/               # audit-derived metrics / ingest / queries vocab
├── state/
│   ├── helpers/                 # atomic-write + version-check helpers (Phase 1B)
│   └── registry/                # protected delegation registry directory (ADR 0002)
├── audit/
│   ├── hardening/               # audit-integrity hardening modules
│   ├── helpers/                 # append-only audit log helpers
│   └── runtime/                 # runtime audit emitters
├── schemas/                     # JSON Schema (draft 2020-12)
│   ├── README.md                # schema index (version-pinned)
│   ├── agent-registry.schema.json
│   ├── audit-event.schema.json
│   ├── delegation.schema.json
│   ├── ipc.py                   # IPC type helpers (module, not a schema document)
│   ├── orchestrator-policy.schema.json
│   ├── project-state.schema.json
│   ├── role-definition.schema.json
│   ├── role-mapping.schema.json
│   ├── task.schema.json
│   ├── task-intake.schema.json
│   └── task-result.schema.json
├── tests/                       # validation test suite (Phase 1B+)
│   ├── README.md                # test strategy
│   ├── validate-config.py       # standalone config validator (referenced by config files)
│   ├── validate_config.py       # validator module
│   ├── control_plane.py         # reference authority gate + risk + registry (test-support)
│   ├── conftest.py              # pytest fixtures
│   ├── d4d7_composition.py      # D4/D7 composition checks
│   ├── unit/                    # config, schema, state/audit helper tests
│   ├── authorization/           # AUTH-*, ISO-*, REG-*, DLG-*, RISK-* executable tests
│   ├── adversarial/             # INJ-* quarantine + BAD-* provenance tests
│   ├── audit_hardening/         # audit-integrity hardening tests
│   ├── control_risk/            # risk-gate control tests
│   ├── control_verification/    # verification-gate control tests
│   ├── environment/             # environment tests
│   ├── evidence/                # evidence-gate tests
│   ├── observability/           # observability tests
│   ├── orchestrator/            # orchestrator control-plane tests
│   ├── organization/            # organization/wave orchestration tests
│   ├── recovery_hardening/      # recovery-path hardening tests
│   ├── resilience/              # resilience tests
│   ├── scenarios/               # PRD §17 scenario skeletons
│   ├── workflow/                # workflow skeleton shape validation
│   ├── g10/ g13/ o3/            # operator / front-door decision-package suites
│   ├── l3_reference/ l3_runner/ live_dsh/ live_evidence/  # L3 independent-verification + live-DSH suites
│   ├── integration/             # cross-module integration tests
│   ├── phase-5/                 # Phase-5 validation
│   ├── phase4_integration/      # Phase-4 integration
│   ├── phase5_role_validation/  # Phase-5 role validation
│   └── phase5_security/         # Phase-5 security tests
├── runs/                        # frozen live-run evidence (read-only; do not modify)
└── docs/
    ├── README.md                # doc index
    ├── adr/                     # 0001 boundary · 0002 registry-protection · 0003 pool-expansion · 0004 orchestrator-preset · 0005 delegation/model-route
    ├── design/                  # 0001 control-design + test plan · 0002 L3 verification spec
    ├── security/                # 0001 assurance-spec · 0002 threat-model · 0003..0008 external-content/L3/G5
    ├── phase-1/                 # 0001 spec · 0002 role-isolation draft · 0003..0006 composition exceptions
    ├── phase-2/ phase-3/ phase-4/  # phase implementation specs + governance
    ├── phase-5/                 # Phase-5 validation records
    ├── tool-catalog.md          # Phase-0: scoped capability matrix
    ├── operations.md            # Phase-0: operator/deployment mapping
    ├── architecture.md          # Phase-0: architecture summary
    ├── authority.md             # Phase-0: authority model doc
    ├── parallel-dispatch-playbook.md  # parallel dispatch playbook
    ├── runbooks/                # 10 authored runbooks (see docs/runbooks/README.md) + 8 Phase-5 placeholders retained
    ├── testing/                 # testing docs (see docs/testing/README.md)
    ├── operations/              # operations docs
    ├── governance/              # governance records
    └── superpowers/plans/       # superpowers session plans
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
| 1. Per-agent permission vs session sandbox/approval | **HUMAN_APPROVED** — two-tier model (per-role tool surface + per-session sandbox/approval) |
| 2. Dev session safety policy | **HUMAN_APPROVED** — `workspace-write` + `ask`; session verified |
| 3. Orchestrator architecture | **HUMAN_APPROVED** — hybrid root-session + workflow fan-out/collect |
| 4. Role isolation mechanism | **HUMAN_APPROVED** — per-role Agent Presets, each mounting the tool plugins that make up the role's tool surface |
| 5. State & audit persistence | **HUMAN_APPROVED** — file-based under `multi-agent-harness/` |
| 6. Phase-0 docs | **HUMAN_APPROVED** — created, version-pinned to `0.1.1-rc.2` |
| 7. Phase-1 scope boundary | **HUMAN_APPROVED** — strictly `multi-agent-harness/`; DSH profile/preset change is a per-case exception |

All D1–D7 decisions were explicitly approved by the Human (2026-08-29). Fixed V1 safety defaults remain in force: subdelegation DENY BY DEFAULT; BadSector PASS ≠ authorization; model text ≠ authority; project state ≠ authority; no COMPLETE without verification; no blind retry; no scope expansion; no DSH core modification.

---

*Version-pinned to DeepSeek Harness `0.2.0-rc.2` (re-verified 2026-10-09; previously `0.1.1-rc.2`). See `docs/` for full documentation set.*
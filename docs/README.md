# Documentation Index — Multi-Agent Harness

All documentation is **version-pinned** to DeepSeek Harness `0.2.0-rc.2`.

## Architecture Decision Records (ADRs)

| Document | Description |
|---|---|
| `adr/0001-multi-agent-control-plane-boundary.md` | ADR 0001: three enforcement layers, boundary corrections, seven decisions (Phase-0 foundation) |
| `adr/0002-registry-protection-mechanism.md` | ADR 0002: delegation registry protection decision (Phase 1B) |
| `adr/0003-specialist-pool-expansion.md` | ADR 0003: 8-specialist pool expansion (PRD v0.2); per-case mount exception (D8) |
| `adr/0004-orchestrator-role-preset.md` | ADR 0004: orchestrator role preset (derived from shipped `standard`) |
| `adr/0005-delegation-effort-and-model-route.md` | ADR 0005: delegation effort + model routing |

## Phase-1 specification & composition exceptions

| Document | Description |
|---|---|
| `phase-1/0001-phase-1-implementation-spec.md` | Phase-1 implementation specification: scope, components, schemas, test strategy, dependencies |
| `phase-1/0002-role-isolation-draft.md` | Phase-1C role-isolation DRAFT: per-role personas/tools/rationale, composition-exception register, rollback, live-test plan (draft only) |
| `phase-1/0003-d4-composition-exception-change-request.md` | D4 composition-exception change request |
| `phase-1/0004-d4-composition-exception-correction.md` | D4 composition-exception correction |
| `phase-1/0005-d4-composition-exception-correction-2.md` | D4 composition-exception correction (revision 2) |
| `phase-1/0006-orchestrator-preset-composition-exception-change-request.md` | Orchestrator preset composition-exception change request |

## Phase-2 / Phase-3 / Phase-4 / Phase-5

| Document | Description |
|---|---|
| [`phase-2/`](phase-2/README.md) | Phase-2 governance + conventions (DETECT → … ; source of the operational runbooks) |
| `phase-3/` | Phase-3 implementation records |
| `phase-4/` | Phase-4 implementation records |
| `phase-5/` | Phase-5 validation records |

## Phase-0 Artifacts

| Document | Description |
|---|---|
| `tool-catalog.md` | Scoped DSH capability matrix — tool names, packages, capability class, per-role availability |
| `operations.md` | Operator/deployment mapping — permission presets, session policy, headless behavior, recovery |
| `architecture.md` | Architecture summary — canonical architecture, three layers, enforcement, control flow |
| `authority.md` | Authority model — capability≠permission≠authority, delegation, gates, authority flow |

## Operational guides

| Document | Description |
|---|---|
| [`runbooks/`](runbooks/README.md) | 10 authored runbooks (see `docs/runbooks/README.md`) + 8 Phase-5 placeholders retained |
| `parallel-dispatch-playbook.md` | Parallel dispatch playbook |

## Security

| Document | Description |
|---|---|
| `security/0001-control-assurance-spec.md` | Control assurance: hard enforcement vs control-plane vs model judgment, security invariants, test matrix |
| `security/0002-threat-model-and-control-architecture.md` | Threat model: 25 threats, control mapping, critical invariants, authority model, security test spec |
| `security/0003-external-content-verification-spec.md` | External-content verification spec (external/subagent output is untrusted data) |
| `security/0003-l3-independent-verification-plan.md` | L3 independent-verification plan (P4 reproducibility) |
| `security/0004-runtime-evidence-qa-security-note.md` | Runtime-evidence QA security note |
| `security/0005-l3-evidence-infrastructure-specification.md` | L3 evidence-infrastructure specification |
| `security/0006-l3-implementation-report.md` | L3 implementation report |
| `security/0007-l3-run-prerequisites.md` | L3 run prerequisites |
| `security/0008-g5-verifier-implementation-note.md` | G5 verifier implementation note |

## Design

| Document | Description |
|---|---|
| `design/0001-control-design-and-test-plan.md` | Implementation-grade design + test plan: sandbox, approval, tool surface, role isolation, delegation, gates, recovery |
| `design/0002-l3-verification-specification.md` | L3 verification specification (design-side complement to the L3 plan) |

## Testing

| Document | Description |
|---|---|
| [`testing/`](testing/README.md) | Testing documentation + strategy (see `docs/testing/README.md`); version-pinned |

## Operations & governance

| Document | Description |
|---|---|
| `operations/` | Operations documentation |
| `governance/` | Governance records |

## Configuration

| File | Description |
|---|---|
| `../config/agents.yaml` | Agent registry (canonical, finalized) |
| `../config/permissions.yaml` | Capability×agent matrix (control-plane input) |
| `../config/role-preset-mapping.yaml` | Role→DSH preset/tool-surface mapping |
| `../config/registry-writer.yaml` | Single-writer delegation-registry daemon configuration |
| `../config/tool-subagent-instances.yaml` | The one delegation row + the fifteen role Agent Presets |

## Phase status

See `README.md` at the project root for the phase status table.

---

*All documents assume DeepSeek Harness `0.2.0-rc.2`. Later releases require re-verification of DSH-native primitives before use.*

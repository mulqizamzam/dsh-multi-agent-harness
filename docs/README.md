# Documentation Index — Multi-Agent Harness

All documentation is **version-pinned** to DeepSeek Harness `0.1.1-rc.2`.

## Foundation

| Document | Description |
|---|---|
| `adr/0001-multi-agent-control-plane-boundary.md` | Architecture Decision Record: three enforcement layers, boundary corrections, seven decisions (Phase-0 foundation) |
| `adr/0002-registry-protection-mechanism.md` | ADR 0002: delegation registry protection decision (Phase 1B) |
| `phase-1/0001-phase-1-implementation-spec.md` | Phase-1 implementation specification: scope, components, schemas, test strategy, dependencies |
| `phase-1/0002-role-isolation-draft.md` | Phase-1C role-isolation DRAFT: per-role personas/tools/rationale, composition-exception register, rollback, live-test plan (draft only) |

## Phase-0 Artifacts (created in Phase 1A)

| Document | Description |
|---|---|
| `tool-catalog.md` | Scoped DSH capability matrix — tool names, packages, capability class, per-role availability |
| `operations.md` | Operator/deployment mapping — permission presets, session policy, headless behavior, recovery |
| `architecture.md` | Architecture summary — canonical architecture, three layers, enforcement, control flow |
| `authority.md` | Authority model — capability≠permission≠authority, delegation, gates, authority flow |
| `runbooks/` | Phase-5 hardening intent (placeholder — runbooks authored in Phase 5) |

## Security

| Document | Description |
|---|---|
| `security/0001-control-assurance-spec.md` | Control assurance: hard enforcement vs control-plane vs model judgment, security invariants, test matrix |
| `security/0002-threat-model-and-control-architecture.md` | Threat model: 25 threats, control mapping, critical invariants, authority model, security test spec |

## Design

| Document | Description |
|---|---|
| `design/0001-control-design-and-test-plan.md` | Implementation-grade design + test plan: sandbox, approval, toolFilter, role isolation, delegation, gates, recovery |

## Configuration

| File | Description |
|---|---|
| `config/agents.yaml` | Agent registry (canonical, finalized) |
| `config/permissions.yaml` | Capability×agent matrix (control-plane input) |
| `config/role-preset-mapping.yaml` | Role→DSH preset/toolFilter mapping |

## Phase status

See `README.md` at the project root for the phase status table.

---

*All documents assume DeepSeek Harness `0.1.1-rc.2`. Later releases require re-verification of DSH-native primitives before use.*
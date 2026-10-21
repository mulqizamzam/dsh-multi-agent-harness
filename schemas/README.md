# Baseline Schemas — Multi-Agent Harness

- **Status**: finalized (Phase 1A)
- **Version pin**: DeepSeek Harness `0.2.0-rc.2`
- **Format**: JSON Schema, draft 2020-12 (`https://json-schema.org/draft/2020-12/schema`)

These are the **baseline schemas** for the project control plane. They validate the project's authoritative documents (registry, role policies, role mapping) and the runtime records the control plane reads/writes (delegations, project state, audit events). Versioning is tracked per-schema via `x-schema-version`.

## Schema set

| Schema | Validates | Source |
|---|---|---|
| `delegation.schema.json` | A single delegation/authorization object | Phase-1 spec §7.1; security spec §6.1 |
| `project-state.schema.json` | A project state document (`state/`) | Phase-1 spec §7.2 |
| `audit-event.schema.json` | A single project audit event (`audit/`) | Phase-1 spec §7.3 |
| `role-definition.schema.json` | An agent role policy (`agents/<id>/policy.yaml`) | ADR Decision 4; role definitions |
| `role-mapping.schema.json` | The role→Agent Preset / tool-surface mapping (`config/role-preset-mapping.yaml`) | Phase-1 spec §7.4 |
| `agent-registry.schema.json` | The agent registry (`config/agents.yaml`) | Phase-1 spec §2; registry |
| `orchestrator-policy.schema.json` | The orchestrator role policy (`orchestrator/policy.yaml`) | ADR 0004; orchestrator artifacts |

## Versioning

- Each schema carries `x-schema-version` (integer, starts at 1).
- A breaking change to a validated document's shape bumps the version **and** requires a corresponding migration note in this README.
- All schemas are pinned to the DSH `0.2.1-rc.2` tool catalog via the tool names they permit (see `role-mapping.schema.json` `tool_surface` note). If the DSH version changes, re-verify tool names and bump affected schemas.

## Validation approach

- **Phase 1A**: ad-hoc validation performed at authoring time (JSON syntax + YAML parse + jsonschema validation of sample/real documents).
- **Phase 1B**: these schemas are wired into `tests/validate_config.py` (the module) and, through it, into `tests/validate-config.py` (the hyphenated standalone wrapper that the config files name) plus the unit test suite (schema checks for delegation/state/audit/role/registry/mapping/orchestrator-policy).
- Rule: a document that fails its schema is treated as **absent/invalid** (fail-closed). For the delegation registry specifically: malformed → treated as no delegation → DENY (security spec §3.3, INV-05).

## Drift guards

- `role-mapping.schema.json` and `role-definition.schema.json` are kept consistent with each other (a role's `tool_surface` in the mapping must match its `policy.yaml`) — enforced by `tests/validate_config.py` (`consistency_rules`). The same equality is now enforced for the orchestrator, between `role-mapping.schema.json` §`orchestrator` and the document `orchestrator-policy.schema.json` validates.
- `role-definition.schema.json` constrains `role` to the **fifteen** specialist ids, so a sixteenth specialist cannot be introduced silently. The orchestrator is deliberately **not** in that enum — it has its own schema.
- **`role` is not one vocabulary across these schemas.** `agent-registry.schema.json` uses the same key for a different namespace: `$defs.agentEntry.role` is constrained to the fifteen **domain slugs** (`operations`, `engineering`, … — matching `config/agents.yaml` `agents[].role`), while `properties.orchestrator.role` is the free-form string `"Orchestrator"`. Do not assume a `role` value valid in one schema is valid in another.

---

*Baseline schemas. Validation wiring is Phase-1B work; nothing here executes or enforces at runtime yet.*
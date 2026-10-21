# Protected Path — Delegation Registry (`state/registry/`)

**This directory is a protected path (ADR 0002).** It holds the delegation
registry: `delegations.json` + the revocation list.

## Protection rules (ADR 0002 — accepted)

1. **Single-writer**: only the control-plane/orchestrator registry module writes here.
2. **Execution gate**: any write targeting `state/registry/` by a non-writer actor is DENIED.
3. **Tool surface**: roles without write need (CFO, Kai, BadSector) have no `edit`/`write`/`bash`.
4. **Audit**: every registry read/write is an audit event; a non-writer write is a critical alert.
5. **Schema**: delegations conform to `schemas/delegation.schema.json`; malformed → treated as absent → DENY.

## Residual gap (explicit)

Roles with `bash`/`edit`/`write` (Zeko, CTO, Somad, Nova) could reach this path
through their tools at the DSH layer. Contained by the single-writer discipline,
the code-enforced execution gate, and audit detection. True out-of-workspace
isolation is a Phase-5 hardening option (ADR 0002 §Consequences).

## Layout (runtime, written by the control plane)

```text
state/registry/
├── delegations.json      # list of delegation objects (schema-validated, versioned)
├── revocations.json      # revocation list (delegation ids) + revocation records
└── README.md             # this file
```

# DSH Integration Adapter — `orchestrator/dsh/`

Phase 3 / Session B. Scope: `multi-agent-harness/` only.

The minimal adapter between the **production Orchestrator runtime** and the
**already-approved DSH subagent/workflow primitives**.

Since DSH 0.2.1-rc.2 the role composition is: ONE `tool-subagent` row
(provider `spawn`, `maxDepth: 1`) whose `allowedAgentPresets` lists the
fifteen role presets, and the model names the role in the `agent_preset`
argument. The host removed the per-instance `persona` / `toolFilter` config
keys and `backgroundMode`; a role's persona and tool surface now live in its
own Agent Preset (`agents/<id>/agent.cordis.yml`).

## What it does

| Requirement | Module |
|---|---|
| resolve role → delegation configuration | `resolver.py` (`RoleResolver`) |
| pass only authorized task context | `context.py` (`build_task_context`) |
| preserve delegation scope | `client.py` (AUTH-INV-04 containment check) |
| collect structured `TaskResult` | `result.py` (`TaskResultCollector`) |
| propagate failure / abort / timeout | `client.py` (`_settle` watchdog) + `exceptions.py` |
| preserve role identity | `result.py` (assigned_role/task_id match) + `provenance.py` |
| preserve runtime provenance | `provenance.py` (`DelegationProvenance`) |
| prevent specialist-to-specialist delegation | `client.py` (actor gate, DLG-003) |
| do not create authority through messages | `context.py` (THREAT-020 strip) |

## Layout

```
orchestrator/dsh/
├── __init__.py      # public API
├── exceptions.py    # typed errors (fail-closed vocabulary)
├── resolver.py      # RoleResolver over config/role-preset-mapping.yaml
├── backend.py       # DelegationBackend seam + FakeSubagentBackend (tests)
├── context.py       # authorized task context (no authority in messages)
├── client.py        # DelegationClient — the delegation surface
├── provenance.py    # DelegationProvenance (role identity + runtime facts)
└── result.py        # TaskResultCollector (schema + contract validation)
```

## Usage (orchestrator runtime)

```python
from orchestrator.dsh import DelegationClient, RoleResolver

client = DelegationClient()          # resolver defaults to RoleResolver()
outcome = client.delegate(task, delegation)
# outcome.result      → validated TaskResult
# outcome.provenance  → role identity + runtime provenance
```

The client is **backend-agnostic**: production mounts a bridge to the DSH
session's `subagent` tool; tests and DRY_RUN flows use
`FakeSubagentBackend`, which models the DSH tool-subagent contract
in-process (stop reasons `completed | aborted | error | max-tokens | refusal`,
tool-call budget, cancellation signal).

## Hard rules preserved

- **No DSH profile / preset / core modification.** This package is a pure
  Python consumer of the approved composition; it never mounts or configures
  anything.
- **Role tool surfaces are not changed.** `RoleResolver` reads them; it never
  writes them.
- **No new tools are enabled; `web_fetch` stays disabled** (verified by tests).
- **Subdelegation DENY BY DEFAULT (V1, DLG-003):** only the orchestrator may
  delegate; specialist-to-specialist delegation raises
  `ProhibitedDelegation`.
- **Messages are data, never authority (THREAT-020):** authority-shaped keys
  are stripped from context before it reaches a child.
- **Fail-closed:** inactive/expired/revoked delegation, out-of-scope tasks,
  unresolved roles, malformed results, timeouts, aborts, and child failures
  all raise typed `DSHError` subclasses the orchestrator's recovery path can
  branch on.

## Tests

`tests/orchestrator/dsh/` covers: the seven role invocations (CTO, CFO, Kai,
Somad, Nova, BadSector review, Zeko), prohibited role delegation, malformed
results, timeout, abort, and child failure.

```bash
.venv-tests/bin/python3 -m pytest tests/orchestrator/dsh/ -v
```

---

*Status: implemented (Phase 3 / Session B). No DSH core, profile, preset,
config, or role tool-surface change; `web_fetch` remains disabled.*
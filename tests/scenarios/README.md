# Scenarios — Phase-4 Promoted Executable Bounded Scenarios

This directory contains two layers:

## 1. Phase-6 skeleton (`test_scenarios.py` — SKIPPED)

The canonical PRD §17 scenario list (SCN-001..010). These are **structural skeletons**
that remain `pytest.mark.skip` because they require the Phase-6 live execution engine
for their full-fidelity flow (e.g. real DSH children, publish actions, novel editing).

## 2. Phase-4 executable promotion (`test_executable_scenarios.py` — RUNNING)

Ten **bounded, executable scenarios** (SCN-101..SCN-110) that run against the
**real Phase-4 deterministic runtime** (`orchestrator.runtime.ExecutionFlow`,
`control.*`, `audit.helpers.*`, `state.helpers.*`). No live-DSH evidence is
fabricated; no L3 claim is made.

| SCN | Name | Runbook | PRD §17 skeleton |
|---|---|---|---|
| 101 | Authority denial | 01 | #10 |
| 102 | Expired / revoked delegation | 02, 03 | #10 |
| 103 | BadSector rework / reject | 04 | #7 |
| 104 | Evidence failure | 05 | #1, #2 |
| 105 | Conflict escalation | 06 | #8 |
| 106 | Execution failure | 07 | #9 |
| 107 | Recovery failure | 08 | #9 |
| 108 | Stale state | 09 | #9 |
| 109 | Audit integrity failure | 10 | #10 |
| 110 | Successful bounded autonomous workflow | — | #1, #2 |

Each scenario is specified in `docs/phase-4/scenarios/` with the nine required
fields: preconditions, objective, actors, expected state, expected gates, expected
execution, expected verification, expected failure/recovery, and evidence
requirements.

## Running

```bash
.venv-tests/bin/python3 -m pytest tests/scenarios/test_executable_scenarios.py -v
```

55 tests cover the ten scenario classes. All run against the deterministic
runtime (no live DSH mount required). Live-DSH variants are **BLOCKED** pending
the D4/D7 composition mount (RDE-1).

## Honesty boundary

- **Deterministic runtime only.** These tests use in-process child execution
  (`FakeSubagentBackend` / stub runners), not real `subagent_<id>` instances.
- **No L3 claim.** No evidence bundle satisfies P1–P4.
- **No prompt-injection security claim.**
- **No production change.** `orchestrator/`, `control/`, `state/`, `audit/helpers/`,
  `agents/`, `config/`, `schemas/` are not modified.
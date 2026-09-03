# Testing Documentation — Multi-Agent Control Plane

All documentation is **version-pinned** to DeepSeek Harness `0.1.1-rc.2`.

## Test layers

| Layer | Location | Status |
|---|---|---|
| Config/invariant validation | `tests/validate-config.py` | COMPLETE |
| Unit tests | `tests/unit/` | COMPLETE |
| Authorization security tests | `tests/authorization/` | COMPLETE |
| Adversarial tests | `tests/adversarial/` | COMPLETE |
| Orchestrator foundation tests | `tests/orchestrator/` | COMPLETE |
| Workflow skeleton tests | `tests/workflow/` | COMPLETE |
| Scenario harness skeletons (Phase 6) | `tests/scenarios/` | SKELETON |
| **Integration tests (Phase 2 / Session D)** | `tests/integration/` | **SKELETON + EXECUTABLE** |

## Documents

| Document | Description |
|---|---|
| `0001-integration-test-plan.md` | **Integration test specification** — 12 cross-module scenarios (INT-01..INT-12), test matrix, Phase-2A/B/C dependencies, blocked tests, unknowns, scope check. Companion to `tests/integration/`. |
| `0002-runtime-evidence-qa-specification.md` | **Runtime evidence QA specification (Phase 3 / Session E)** — evidence bundle contract for INT-01/INT-07/INT-11/INT-12, classification taxonomy, per-scenario mandatory evidence, retention convention, validation rules. Companion to `tests/evidence/`. |
| `0003-l3-evidence-validation-specification.md` | **L3 evidence validation specification (Phase 3 / Session F)** — validation contract for future L3 evidence bundles, structure-only rejection rules (LV1..LV20 + per-INT), schema-validation procedure, fixture scaffolding contract. Companion to `tests/l3_reference/`. No L3 verifier built; no L3 claim. |

## Running

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/ -v
.venv-tests/bin/python3 -m pytest tests/integration/ -v   # integration suite only
```

---

*All tests assume DeepSeek Harness `0.1.1-rc.2`. Integration tests wire existing foundation/reference/helper modules; live-DSH variants require Phase-2C.*
# Phase 4 Testing — Integration Specification &amp; Documentation

- **Milestone**: Phase 4 / Session E — Integration Testing
- **Status**: SPECIFIED + DEFECT CLOSED (test suite + documentation; the only production change is the targeted audit event-id allocator in `orchestrator/runtime/audit.py` and the consequential nested-flow correlation fix in `observability/ingest.py`)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `tests/phase4_integration/` (test suite) + `docs/phase-4/testing/` (this directory)
- **Rule**: no DSH core, profile, preset, session policy, or config is changed. No L3 claim is made. Live-DSH variants are BLOCKED.

---

## Documents

| Document | Description |
|---|---|
| `0001-phase4-integration-test-plan.md` | **Phase-4 integration test plan** — scope, ID scheme (P4I-01..P4I-08), focus areas, scenario catalogue, honesty boundaries, run instructions. Companion to `tests/phase4_integration/`. |
| `0002-acceptance-criteria-coverage.md` | **Acceptance criteria coverage** — maps each Phase-4 acceptance matrix row (AEF, PAR, VER, REC, AUD, AUTH, PB) to the test(s) that assert it, with current status and honesty notes. |
| `0003-observability-correlation.md` | **Observability correlation spec** — how the cross-module observability correlation is tested: real-ledger ingestion, run/task/delegation/failure/evidence correlation, fail-closed rules, and the audit event-id defect closure. |

---

## Test suite

The companion test suite lives at `tests/phase4_integration/` with eight test classes (P4I-01..P4I-08) covering the focus areas. Run with:

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/phase4_integration/ -v
```

## Honesty boundary

- **Deterministic runtime only.** Every test runs against the real Phase-4 production modules (`orchestrator.production`, `orchestrator.runtime`, `control.*`, `state.helpers`, `audit.helpers`, `observability`) with deterministic in-process child execution (`FakeSubagentBackend` / stub runners). No live-DSH evidence is fabricated.
- **No L3 claim.** No evidence bundle in this directory satisfies P1–P4 (independent process, separate UID, pre-signed plan, external oracle). Every test is L2-deterministic at most.
- **No prompt-injection security claim.** Subagent content is treated as data; the tests exercise the runtime's trust posture but make no security claim.
- **Production change is limited to the audit defect closure**: the per-ledger event-id allocator (`orchestrator/runtime/audit.py`) and the consequential nested-flow correlation fix (`observability/ingest.py`). Nothing under `control/`, `state/`, `agents/`, `config/` is modified.

---

*Status: SPECIFIED + DEFECT CLOSED. Production change limited to the audit event-id allocator (`orchestrator/runtime/audit.py`) and the nested-flow correlation fix (`observability/ingest.py`). No DSH change. No L3 claim.*
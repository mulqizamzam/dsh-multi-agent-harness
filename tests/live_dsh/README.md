# tests/live_dsh — REAL DSH Bridge Preparation (Phase 3 / Session E)

TEST-SUPPORT ONLY. NOT production code.

Prepares the test harness that will replace the deterministic
`FakeSubagentBackend` with the ACTUAL mounted D4/D7 `subagent_<id>` tool
instances **after a Human-approved composition is active**.

## Hard rules

- **NOTHING is mounted here.** No DSH core / profile / preset / session-policy
  change. No live scenario is executed.
- The harness **explicitly distinguishes FAKE vs REAL vs UNAVAILABLE** backends
  and never assumes a live bridge exists.
- The REAL path is gated on the mount marker `DSH_LIVE_BRIDGE_ACTIVE=1`, which
  the orchestrator session sets only after the D4/D7 controlled composition
  exception (docs/phase-1/0003..0005) is approved and mounted.

## Layout

| Module | Purpose |
|---|---|
| `contract.py` | DSH tool-subagent invocation + stop-reason contract (verified against DSH 0.1.1-rc.2). |
| `discovery.py` | Static role→instance resolution + mount probe (never assumes live). |
| `backend_kind.py` | `BackendKind` enum: FAKE / REAL / UNAVAILABLE + fail-closed gate. |
| `real_backend.py` | `RealDSHBackend` (DelegationBackend over the real `subagent_<id>` surface) + `BridgeNotAvailable`. |
| `adapters.py` | Per-role adapters for CTO, CFO, Kai, Somad, BadSector, Nova, Zeko. |
| `evidence.py` | Evidence bundle model (dispatch, provenance, stop reason, structured result). |
| `conftest.py` | Fixtures: delegation, task, fake backend, recording bridge, 7 role adapters. |

## Running

```bash
cd multi-agent-harness
.venv-tests/bin/python3 -m pytest tests/live_dsh/ -v
```

All tests run WITHOUT a live bridge (static config + contract mapping + fake
backend). The REAL-backend execution paths require the D4/D7 mount marker and
are refused by default (fail-closed) — see `test_backend_kind.py`.

## After the composition is mounted (NOT executed now)

1. Set `DSH_LIVE_BRIDGE_ACTIVE=1` (orchestrator session sets it after mount).
2. Inject the live dispatch bridge into `RealDSHBackend` (the orchestrator
   session's `subagent_<id>` tool surface).
3. Run the same tests against the REAL backend to prove the mounted instances
   satisfy the identical contract (structured TaskResult capture, provenance,
   timeout/abort, failure propagation, cleanup, evidence).

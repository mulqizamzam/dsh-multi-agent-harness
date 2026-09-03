# Phase 5 — Front Door V1 Test Report

- **Status:** PASSING
- **Suite:** `tests/orchestrator/entrypoint/` (front-door entry point)
- **Implementation under test:** `orchestrator/entrypoint/` (entry.py, __main__.py)
- **Companions:** `0001-front-door-design.md` · `0002-front-door-security-review.md`

## 1. Coverage vs. required scenarios

Every scenario from the V1 task brief is covered by a focused test:

| Scenario | Test location | Outcome asserted |
|---|---|---|
| happy path | `test_entry.py::TestHappyPath` | COMPLETE, run_id, state, report, verification PASSED |
| empty objective | `test_entry.py::TestShapeValidation` | ERROR |
| missing delegation (no `delegation_id`) | `test_entry.py::TestShapeValidation` | ERROR |
| unknown delegation (id mismatch) | `test_entry.py::TestDelegationResolution` | BLOCKED |
| expired delegation | `test_entry.py::TestDelegationResolution` | BLOCKED |
| revoked delegation | `test_entry.py::TestDelegationResolution` | BLOCKED |
| out-of-scope target | `test_entry.py::TestScopeContainment` | BLOCKED/ESCALATED |
| objective authority injection | `test_entry.py::TestAuthorityInjection` | objective is DATA; authority_context unchanged |
| fake approval text | `test_entry.py::TestAuthorityInjection` | never fabricates approval |
| intrinsic HIGH declared LOW | `test_entry.py::TestRiskClassification` | schema has no risk override; write→MEDIUM (never LOW) |
| BLOCKED | `test_entry.py::TestOutcomes` | BLOCKED + run_id None when no run |
| ESCALATED | `test_entry.py::TestOutcomes` | ESCALATED via evidence gate |
| unexpected exception | `test_entry.py::TestOutcomes` | ERROR |
| JSON serialization | `test_entry.py::TestFrontDoorResultDict` | schema marker + JSON round-trip |
| no direct ExecutionFlow call | `test_static_security.py::TestStaticNoRawDsh` | AST scan: no code usage |
| no raw DSH call/import | `test_static_security.py::TestStaticNoRawDsh` | no DSH identifiers |
| no Delegation creation | `test_static_security.py::TestStaticNoAuthorityMinting` | no creation/issuance calls |
| COMPLETE requires verification | `test_entry.py::TestCompleteRequiresVerification` | COMPLETE only with verdict PASSED |

## 2. Static security proofs

`test_static_security.py` proves the front door cannot:

- **mint authority** — no `create_delegation` / `issue_child_delegation` /
  `DelegationLifecycle`; never writes `status="ACTIVE"`; no approval/review
  fabrication; delegation_id is a strict `delegation-<id>` pattern.
- **write the registry directly** — no `atomic_write`, no
  `delegations.json`/`revocations.json`, no `write_through`; consumes only the
  read-only `DelegationProvider`.
- **execute raw DSH tools** — no `orchestrator.dsh` import, no
  `RealDSHBackend`/`DelegationClient`/bridge markers.
- **bypass ProductionRun** — `ProductionRun.run()` is the only execution
  entry; AST scan confirms no code-level reference to `ExecutionFlow` /
  `ExecutionEngine`.
- **downgrade a gate decision** — the request schema has no `declared_risk`,
  `approval_reference`, `review`, `status`, or permission/tool fields.

Behavioral proofs (sandboxed workspace) additionally verify the provider's
delegation is unchanged after a run (still ACTIVE, same id), objective prose
never grants authority, and out-of-scope targets never reach COMPLETE.

## 3. CLI coverage

`test_cli.py` covers:

- exit code mapping: COMPLETE→0, ERROR→1, BLOCKED→2, ESCALATED→3
- argparse happy path (exit 0, envelope schema/status)
- JSON stdin happy path and CLI-overrides-JSON
- invalid JSON stdin → ERROR (exit 1)
- `python -m orchestrator.entrypoint` end-to-end via subprocess
- free-text delegation id rejected (ERROR, exit 1)
- missing required field → ERROR (exit 1)

## 4. Result

- Focused entrypoint tests: **all passing** (this suite).
- The envelope is exactly `run-result@1` with `status`/`run_id`/`objective`/
  `state`/`report`/`errors`/`audit_ids`.
- No production/runtime/control module was modified by this suite.
- V1 exclusions honored: no idempotency store, no run-index.jsonl, no new
  audit ledger/event class, no web server, no new DSH tool, no O3/L3/G10
  changes, no session-policy/role/toolFilter changes.

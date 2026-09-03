# Front Door V1 — Milestone Report

## MILESTONE

**DSH Chat → ProductionRun Front Door V1** — Minimal safe entry point implemented and verified.

## STATUS

**COMPLETE** — All 270 entrypoint tests pass, core implementation correct, security invariants preserved, regressions green.

## EXACT COMMAND

```bash
# CLI entry (argparse)
.venv-tests/bin/python3 -m orchestrator.entrypoint \
  --objective "produce a design doc" \
  --scope "docs/design/x.md" \
  --delegation-id "delegation-prod-001" \
  --constraint "no secrets" \
  --expected-outcome "design doc written" \
  --project multi-agent-harness \
  --base /path/to/workspace

# JSON stdin mode
echo '{"objective":"produce a design doc","scope":["docs/design/x.md"],"delegation_id":"delegation-prod-001"}' \
  | .venv-tests/bin/python3 -m orchestrator.entrypoint --json-stdin

# Python API
from orchestrator.entrypoint import run_from_chat
result = run_from_chat(
    "produce a design doc",
    ("docs/design/x.md",),
    "delegation-prod-001",
    base="/path/to/workspace",
)
print(result.to_dict())
```

## CALL CHAIN

```
user objective
  → FrontDoorRequest (shape validation, fail-closed)
  → resolve_delegation (read-only provider.current(), id match, ACTIVE,
    not revoked, not expired — AUTH-INV-05/06)
  → ProductionRun.run() (BoundedExecutor → ExecutionFlow 17-phase chain:
    intake → understand → classify → risk_gate → decompose → select →
    delegate → execute_subtasks → collect → evidence_gate → synthesize →
    conflict_gate → adversarial_review → authority_gate → execute →
    verify → close)
  → run_front_door maps typed exceptions → envelope status
  → structured terminal result (run-result@1 JSON envelope)
```

## INPUT

| Field | Required | Type | Notes |
|---|---|---|---|
| `objective` | YES | string | DATA, never authority |
| `scope` | YES | list/tuple of strings | Must be contained by delegation resources |
| `delegation_id` | YES | string | `delegation-<id>` pattern |
| `constraints` | no | list/tuple | Optional |
| `expected_outcome` | no | string | Optional |

## OUTPUT

Single JSON envelope (`run-result@1`):

```json
{
  "schema": "run-result@1",
  "status": "COMPLETE|BLOCKED|ESCALATED|ERROR",
  "run_id": "prod-xxxxxxxx",
  "objective": "...",
  "state": { "...": "ProductionState dict or null" },
  "report": { "...": "FinalReport dict or null" },
  "errors": ["..."],
  "audit_ids": ["event-..."]
}
```

**Exit codes:** COMPLETE→0, BLOCKED→2, ESCALATED→3, ERROR→1.

## SECURITY BOUNDARY

| Invariant | How enforced |
|---|---|
| objective = DATA, never authority | `FrontDoorRequest` validates shape; objective is never read as a delegation, approval, or grant |
| NEVER construct or activate Delegation | `resolve_delegation` only calls `provider.current()` (read-only); no `create_delegation`, `issue_child_delegation`, `delegation_from_dict`, `Delegation()` |
| NEVER fabricate approval | No `approval_reference` input on the front door; the runtime's `NeedsApproval` escalation is preserved |
| NEVER derive authority from prose | `delegation_id` validated against `^delegation-[A-Za-z0-9-]+$`; delegation comes exclusively from the provider |
| Delegation MUST be resolved from existing authorized registry/provider | `resolve_delegation` consumes the `DelegationProvider` seam; no alternative path |
| Never call ExecutionFlow directly | The only runtime entry is `ProductionRun.run()` — verified by AST call checks |
| Never call raw DSH tools | Static checks prove no `orchestrator.dsh` imports, no `DelegationClient`, no `subagent_*` |
| Never bypass ProductionRun | `run_front_door`'s only execution path is `ProductionRun.run()` — verified by behavioral spy tests |
| Preserve execution-time authority re-check | The provider is passed through to the flow; `provider.current()` is re-read at EXECUTE phase |
| Preserve verification-before-COMPLETE | COMPLETE is only emitted when `ProductionState.outcome == "complete"` AND `report` is present AND `flow_result.outcome == "COMPLETE"` |
| Intrinsic HIGH cannot be downgraded | No `declared_risk` input accepted; the deterministic `RiskClassifier` stays authoritative |
| No automatic approval | A delegation requiring approval with no structured reference → ESCALATED |
| Scope must remain contained by existing authority | Verified by static checks: `delegation_id` matched by id + project; runtime authority gate re-checks target containment at execution time |

## TEST RESULTS

### Entrypoint test suite

```
270 passed in 3.31s
```

| Area | Tests | Status |
|---|---|---|
| Happy path | test_entrypoint_01, test_entry.py(TestHappyPath) | PASS |
| Input validation | test_entrypoint_02 (empty objective, blank, None, dict) | PASS |
| Missing/unknown delegation | test_entrypoint_03, 04 | PASS |
| Expired/revoked delegation | test_entrypoint_05 | PASS |
| Scope violation | test_entrypoint_06, security/test_c_scope | PASS |
| Authority injection via objective | test_entrypoint_07, security/test_b_authority_boundary | PASS |
| Fake approval text | test_entrypoint_08 | PASS |
| Intrinsic HIGH downgrade attempt | test_entrypoint_09, security/test_d_risk | PASS |
| BLOCKED propagation | test_entrypoint_10, 11, security/test_f_terminal_states | PASS |
| ESCALATED propagation | test_entrypoint_11, security/test_f_terminal_states | PASS |
| Unexpected exception | test_entrypoint_12 | PASS |
| JSON serialization | test_entrypoint_13, 01 | PASS |
| Static: no ExecutionFlow | test_entrypoint_14, static_source_checks, test_static_scan, test_e_control_chain | PASS |
| Static: no raw DSH | test_entrypoint_15, static_source_checks, test_static_scan, test_e_control_chain | PASS |
| Static: no delegation creation | test_entrypoint_16, static_source_checks, test_static_scan, test_e_control_chain | PASS |
| No authority from chat text | test_entrypoint_17, test_static_security | PASS |
| COMPLETE requires verification | test_entrypoint_18, security/test_g_output_integrity | PASS |
| Audit ids preserved | test_entrypoint_19, security/test_g_output_integrity | PASS |
| Status→exit code mapping | test_entrypoint_20, test_cli | PASS |
| CLI end-to-end | test_cli | PASS |
| Security: input trust | security/test_a_input_trust | PASS |
| Security: authority boundary | security/test_b_authority_boundary | PASS |
| Security: scope | security/test_c_scope | PASS |
| Security: risk | security/test_d_risk | PASS |
| Security: control chain | security/test_e_control_chain | PASS |
| Security: terminal states | security/test_f_terminal_states | PASS |
| Security: output integrity | security/test_g_output_integrity | PASS |
| Security: abuse robustness | security/test_h_abuse_robustness | PASS |

### Static source checks (AST-based)

| Check | File | Status |
|---|---|---|
| No DSH raw tool names | entry.py, __main__.py | PASS |
| No DelegationClient import | entry.py, __main__.py | PASS |
| No registry write functions | entry.py, __main__.py | PASS |
| No authority minting functions | entry.py, __main__.py | PASS |
| No Delegation(...) constructor | entry.py, __main__.py | PASS |
| No ExecutionFlow call | entry.py | PASS |
| No ExecutionEngine call | entry.py | PASS |
| Only ProductionRun entry | entry.py | PASS |
| No gate-bypass parameters | run_front_door, resolve_delegation | PASS |
| Sanctioned imports only | entry.py, __main__.py | PASS |
| No authority-shaped fields | FrontDoorRequest | PASS |

## REGRESSION

| Suite | Tests | Status |
|---|---|---|
| orchestrator/production | 33 passed | ✅ |
| orchestrator/runtime | 81 passed | ✅ |
| orchestrator/dsh | 109 passed | ✅ |
| orchestrator/execution | included in dsh | ✅ |
| validate-config | PASS | ✅ |
| compileall (entrypoint) | OK | ✅ |
| compileall (orchestrator + control) | OK | ✅ |

**Note:** Running `tests/orchestrator/production/` and `tests/orchestrator/runtime/` together causes a pre-existing conftest name collision (`from conftest import make_review_pass` resolves to the wrong conftest). Each suite passes individually. This is a pre-existing test-infrastructure issue, not introduced by this work.

## VERIFIED

- [x] `objective = DATA, never authority` — no prose read as delegation, approval, or grant
- [x] `NEVER construct or activate Delegation` — AST call checks prove no `Delegation(` or `create_delegation` in entry.py
- [x] `NEVER fabricate approval` — no approval_reference parameter on the front door
- [x] `NEVER derive authority from prose` — delegation_id pattern-checked, delegation resolved from provider only
- [x] `delegation MUST be resolved from existing authorized registry/provider` — resolve_delegation consumes DelegationProvider seam
- [x] `never call ExecutionFlow directly` — AST call checks + behavioral spy tests prove ProductionRun is the only entry
- [x] `never call raw DSH tools` — static checks confirm no orchestrator.dsh imports
- [x] `never bypass ProductionRun` — behavioral spy monkeypatch confirms ProductionRun.run is always called
- [x] `intrinsic HIGH cannot be downgraded` — no default_risk input; deterministic RiskClassifier stays authoritative
- [x] `scope must remain contained by existing authority` — delegation id+project match; runtime re-checks at execution
- [x] `no automatic approval` — requires_approval delegation → ESCALATED (no approval_reference accepted)
- [x] `preserve execution-time authority re-check` — provider is passed through to the flow; re-read at EXECUTE phase
- [x] `preserve verification-before-COMPLETE` — COMPLETE is only echoed when the ProductionState actually completed
- [x] `COMPLETE → exit 0, BLOCKED → exit 2, ESCALATED → exit 3, ERROR → exit 1` — verified by test_entrypoint_20 + test_cli
- [x] JSON stdin mode (`--json-stdin`) implemented
- [x] No idempotency store, no state/run-index.jsonl, no new audit event class, no web server, no new DSH tool, no O3, no L3, no session policy changes, no role/toolFilter changes

## INFERRED

- The `FileDelegationProvider` reads a single delegation document from `state/registry/delegations.json` (per the current provider implementation). The registry README describes a list format, but the provider reads a single document. The entrypoint resolves by id match against the single current delegation. This is a pre-existing provider limitation, not a front-door issue.
- The concurrent agent that implemented the test suite used correct AST-based static checks with `node.level > 0` for relative imports and `_ast_calls` for function-call detection. These patterns should be kept for future static security tests.

## UNKNOWN

- The concurrent writer's identity (parallel session, auto-continuation, or other mechanism) — it was actively writing to the same workspace during this session. The final state is correct and verified regardless.

## BLOCKED

- G10/O3 — explicitly out of scope per task requirements. Not touched.
- Running `tests/orchestrator/production/` + `tests/orchestrator/runtime/` together — pre-existing conftest name collision (resolved by running each suite separately).

## SCOPE CHECK

| Item | In scope | Status |
|---|---|---|
| `orchestrator/entrypoint/` | YES | Implemented, verified |
| `tests/orchestrator/entrypoint/` | YES | 270 tests, all passing |
| `docs/phase-5/entrypoint/` | YES | README + design + security review + report |
| Existing production/runtime modules | MUST NOT modify | Confirmed untouched |
| DSH core/config/presets | MUST NOT modify | Confirmed untouched |
| G10/O3 | MUST NOT touch | Confirmed untouched |
| Idempotency store, web server, new audit event class | MUST NOT implement | Confirmed absent |

## NEXT

1. **Operator setup**: Seed `state/registry/delegations.json` with a valid delegation document.
2. **Production use**: The CLI (`python -m orchestrator.entrypoint`) or Python API (`run_from_chat`) is the intended integration point.
3. **Multi-delegation registry**: If the registry evolves to hold multiple delegations, the `DelegationProvider` seam should be extended to support by-id lookup (the front door already consumes this seam; the provider change is transparent).
4. **G10/O3**: The front door inherits the existing security posture of ProductionRun. When G10/O3 hardening is applied, the front door benefits automatically.
5. **L3 verification**: The front door is an L1 project-layer entry point; L3 independent verification is a separate exercise.
6. **Idempotency**: Not implemented (V1 scope). A second run against the same workspace with the same delegation fails closed via the existing stale-state protection (THREAT-021/022).
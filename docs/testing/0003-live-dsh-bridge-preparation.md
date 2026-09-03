# Live DSH Bridge Preparation — Test Harness Design (Phase 3 / Session E)

- **Milestone**: Phase 3 / Session E — REAL DSH BRIDGE PREPARATION
- **Status**: PREPARED (harness written; NOT mounted, NOT executed)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/live_dsh/` + this document (WRITE-ONLY
  per the session brief). No DSH core, profile, preset, session policy, tool
  mount, or live scenario touched.

## 1. Objective

Prepare a test harness that can replace the deterministic `FakeSubagentBackend`
with the **ACTUAL mounted DSH `subagent_<id>` tool instances** after a
Human-approved D4/D7 composition is active (`docs/phase-1/0003..0005`).

The harness defines, verifiably, the **real-DSH bridge contract** so that when
the composition is mounted the exact same tests prove the live instances behave
like the contract — no rework, no silent drift.

## 2. FAKE vs REAL distinction (hard requirement)

| Aspect | FAKE backend | REAL DSH backend |
|---|---|---|
| Implementation | `orchestrator.dsh.FakeSubagentBackend` (in-process, deterministic) | `tests/live_dsh.real_backend.RealDSHBackend` over `subagent_<id>` |
| Availability | always | only after D4/D7 composition mounted + `DSH_LIVE_BRIDGE_ACTIVE=1` |
| Live session | never touched | the mounted tool instances (orchestrator session drives them) |
| Failure mode | scripted handlers | fail-closed `BridgeNotAvailable` — never silent fallback |
| Provenance | fake run ids | DSH session run ids (`runId` / child session id) |
| Structured capture | scripted dict | DSH `structured_output` tool → `SubagentResult.structured` |

The harness **never assumes a live bridge exists**: every REAL path is gated on
the mount marker and reports UNAVAILABLE / BLOCKED without it
(`tests/live_dsh/backend_kind.py`, `test_backend_kind.py`).

## 3. REAL-DSH bridge contract (verified against DSH 0.1.1-rc.2)

Verified from the DSH checkout (read-only):

| Contract item | DSH source | Harness module |
|---|---|---|
| Tool parameters `description` + `prompt` (+ optional `run_in_background`) | `packages/subagent/tool-subagent/src/index.ts:316-335` | `contract.py` (`TOOL_PARAMETER_KEYS`, `DSHInvocation`) |
| Output `kind`: `foreground` / `background` / `continuable` | `index.ts:336-364` | `contract.py` constants |
| Stop reasons: `completed`/`aborted`/`error`/`max-tokens`/`refusal` | `packages/subagent/subagent/src/types.ts:200-214` | `contract.py` (`STOP_REASONS`) |
| Stop-reason → error wording | `tool-subagent/src/index.ts:124-142` (`stopReasonError`) | `contract.py` (`map_stop_reason_to_outcome`) |
| Structured capture via child `structured_output` tool | `subagent-in-process-driver/src/structured.ts:19,26` | `contract.py` (`STRUCTURED_OUTPUT_TOOL`, `default_task_result_schema`) |
| Run handle: `id` / `result` / `dispose` | `subagent/src/types.ts:256-282` | `real_backend.py` (`_RealDSHRun`) |
| Child discovery / enumeration | `subagent/src/list-children.ts` | `real_backend.py.list_children()` |
| One-shot prompt is standalone (spawn provider) | `types.ts` `inheritsParentContext` | `contract.py` (`BuildInvocation.prompt_for`) |

### 3.1 Invocation contract

The real bridge sends the child a **self-contained** prompt built from the
AUTHORIZED task context only (THREAT-020: no authority in messages), plus the
TaskResult JSON Schema as `output_schema` so the child must finish through the
`structured_output` tool. A child that finishes without a valid structured
result is **refused** — text claims are never collected results (AUTH-INV-13).

### 3.2 Failure propagation

| DSH stop reason | Adapter failure | failure_class |
|---|---|---|
| `aborted` | DelegationAborted | environment |
| `error` | ChildFailure | logic |
| `max-tokens` | ChildFailure (token budget) | environment |
| `refusal` | ChildFailure | logic |
| unknown | fail-closed error | unknown → escalate |

## 4. Role resolution

`tests/live_dsh/discovery.py` + `adapters.py` resolve all 7 roles from the
approved D4/D7 composition (`config/role-preset-mapping.yaml` +
`config/tool-subagent-instances.yaml`):

| Role | tool_name | persona | provider | max_depth |
|---|---|---|---|---|
| Zeko | `subagent_zeko` | `role-zeko` | spawn | 1 |
| CTO | `subagent_cto` | `role-cto` | spawn | 1 |
| CFO | `subagent_cfo` | `role-cfo` | spawn | 1 |
| Kai | `subagent_kai` | `role-kai` | spawn | 1 |
| Somad | `subagent_somad` | `role-somad` | spawn | 1 |
| BadSector | `subagent_badsector` | `role-badsector` | spawn | 1 |
| Nova | `subagent_nova` | `role-nova` | spawn | 1 |

All `backgroundMode: continuable`, `allow ∩ deny = ∅`, no delegation tool in any
allow set (subdelegation DENY BY DEFAULT, V1).

## 5. Evidence model

`tests/live_dsh/evidence.py` records, per delegation, RUNTIME ARTIFACTS only:
flow/task/role/delegation ids, tool_name + persona, backend kind (FAKE/REAL/
UNAVAILABLE), mount status, invocation sent, run id, stop reason, success/
error, structured TaskResult, provenance stamp, audit events. Evidence is DATA
— never a grant (AUTH-INV-14).

## 6. Test harness

| File | Proves |
|---|---|
| `test_backend_kind.py` | FAKE vs REAL vs UNAVAILABLE; no silent fallback; refuse-unmounted |
| `test_discovery.py` | 7-role resolution, tool_name/persona, max_depth=1, allow∩deny=∅, mount probe |
| `test_contract.py` | invocation shape, authorized prompt, TaskResult output schema, stop-reason mapping |
| `test_role_adapters.py` | per-role adapter: context+invocation build, toolFilter boundaries, review-only, no delegation tools |
| `test_structured_capture.py` | valid structured → TaskResult; missing/error → fail-closed; role identity |
| `test_timeout_abort.py` | timeout/abort propagation, pre-start signal, stop-reason classification |
| `test_failure_propagation.py` | typed failure → failure_class (recovery branching) |
| `test_cleanup.py` | dispose idempotent, child enumeration, interrupt |
| `test_evidence.py` | evidence bundle shape + data-not-authority |

**75 tests pass without any live bridge** (static config + contract mapping +
fake backend). After the D4/D7 composition is mounted, the orchestrator session
sets `DSH_LIVE_BRIDGE_ACTIVE=1` and injects the live dispatch bridge; the same
suite then proves the REAL instances satisfy the identical contract.

## 7. Verified / Inferred / Assumed / Unknown / Blocked

- **VERIFIED**: DSH tool-subagent parameter/output/stop-reason vocabulary
  (read from DSH 0.1.1-rc.2 sources); D4/D7 mapping content; runtime adapter
  seam (`DelegationBackend`); 75 harness tests pass.
- **INFERRED**: the exact `runId`/child-session mapping for a spawned child
  (local run id == child session id per `types.ts:262`) — not exercised live.
- **ASSUMED**: `DSH_LIVE_BRIDGE_ACTIVE` marker convention (orchestrator session
  sets it post-mount); a mounted instance accepts the TaskResult output schema.
- **UNKNOWN**: runtime acceptance of `persona`/`toolFilter`/`maxDepth` on the
  spawn provider until ISO-LIVE-001/007 run (docs/phase-1/0004 §11); prompt
  injection (no claim).
- **BLOCKED**: the D4/D7 mount + all ISO-LIVE tests (require Human approval +
  DSH restart — cannot be performed from this session); ISO-LIVE-006
  registry-write denial (execution gate not yet live, ADR 0002 residual).

## 8. Scope check

In scope: `tests/live_dsh/**` + this document. Not touched: production code
(`orchestrator/`, `control/`, `state/`, `audit/`, `config/`, `agents/`,
`schemas/`, `tests/` outside `live_dsh/`), DSH core/profile/preset, session
policy, prior INT-01/07 harness (`runs/d2/`), `tests/live_evidence/`. No mount,
no restart, no live scenario, no new tool, no `web_fetch`.

## 9. Next (not executed here)

1. Human approval of the D4/D7 correction (docs/phase-1/0005) + composition
   exception (docs/phase-1/0003/0004).
2. Mount 7 presets + 7 `tool-subagent` rows; restart DSH.
3. Orchestrator session sets `DSH_LIVE_BRIDGE_ACTIVE=1` and injects the live
   dispatch bridge into `RealDSHBackend`.
4. Run `tests/live_dsh/` against the REAL backend → ISO-LIVE evidence.
5. Re-run INT-01/07 with the REAL backend (replaces the D2 deterministic run).

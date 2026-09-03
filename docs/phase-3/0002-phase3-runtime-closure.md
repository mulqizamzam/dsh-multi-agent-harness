# Phase 3 — Runtime Closure — INT-01 + INT-07 REAL DSH Variants

- **Milestone**: PHASE 3 — RUNTIME CLOSURE
- **Status**: **PASS** (INT-01 + INT-07 REAL DSH variants; all four live scenarios have validated runtime evidence)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Runtime used**: existing Phase-3 runtime (`orchestrator/runtime/ExecutionFlow`, `orchestrator/execution/ExecutionEngine`, `orchestrator/dsh/DelegationClient`) — **not modified**
- **Backend used**: `RealDSHBackend` (`tests/live_dsh/real_backend.py`, Session E) over the approved D4/D7 `subagent_<id>` instances — **no FakeSubagentBackend**
- **Evidence QA**: `tests/evidence/evidence_qa.py` (Session E validator) — all four bundles validated

---

## COMPOSITION

- **Session policy**: `permission/preset=workspace-write`, `sandbox/mode=workspace-write`, `approval/policy=ask` — verified from the session log.
- **D4/D7 instances resolve** (all 7): `subagent_zeko`, `subagent_cto`, `subagent_cfo`, `subagent_kai`, `subagent_somad`, `subagent_badsector`, `subagent_nova` — verified via `RoleResolver` + `tests/live_dsh/discovery.assert_role_resolution()`.
- **Mount marker**: `DSH_LIVE_BRIDGE_ACTIVE=1` set for the evidence process (orchestrator-session convention post-mount, per `docs/testing/0003` §6). `probe_backend_kind() == real-dsh`; all 7 mount probes True.
- **REAL backend active**: `RealDSHBackend` with injected bridge drives the live `subagent_<id>` tool surface; `bridge_calls == 1` per scenario.
- **Evidence capture active**: Session-E `tests/evidence/evidence_qa.py` + retention convention (`audit/runtime/<SCENARIO>/`) exercised for all four scenarios.
- **Composition integrity**: no DSH core/profile/preset/session-policy change; role toolFilters untouched; no new tool enabled; Agent Teams not enabled; no out-of-process backend.

## INT-01 — Full lifecycle (REAL DSH) — **PASS**

| Element | Evidence |
|---|---|
| Live DSH specialist | real `subagent_cto` run `30446fa4-e80f-444b-9fb1-f650fbb9fb21`, stop_reason `completed`, structured TaskResult (`status: SUCCEEDED`, `confidence: HIGH`, schema-valid) |
| Full Execution Flow | `ExecutionFlow` through `RealDSHBackend`: intake → … → execute → verify → close |
| Structured TaskResult | collected through the adapter (`TaskResultCollector`), findings/evidence/recommendation preserved |
| Provenance | child `(role=cto, run_id=30446fa4, tool_name=subagent_cto, stop_reason=completed, source=RUNTIME-OBSERVED)` recorded |
| Execution | `execution.decision=ALLOW`, observed `{exit_code:0, file_exists:true}`; artifact hash recorded |
| Verification | `verification.verdict=PASSED` (CONTROL-PLANE-DECISION) |
| Final status | **COMPLETE** |
| QA | `qa_validation.valid=true`; verdict written to `audit/runtime/INT-01/verdict.json` |
| Hash preservation | `audit/runtime/INT-01/manifest.json` (sha256 per file) |
| Audit trail | `audit/runtime/INT-01/audit-log.jsonl` (full lifecycle events) |

## INT-07 — Execution-time authority re-check (REAL DSH) — **PASS**

| Element | Evidence |
|---|---|
| Valid authority at planning | planning-time authority gate **ALLOW** (gate_authority result `allowed` in audit) |
| Revoke before execution | delegation revoked via sanctioned registry write between planning and execute |
| Execution-time re-check | `execution_denial` audit event; `authority.decision=DENY` (AUTH-INV-06) |
| No unauthorized mutation | `provenance.children=[]`; target artifact hash unchanged (`sha256:0000…` absent→absent); no output file written |
| Final status | **BLOCKED** (not COMPLETE) |
| Real DSH child | `subagent_cto` run `94d12d42-3f97-4730-9361-637d449a7dcf` executed the analysis under planning authority (bridge_calls=1) |
| QA | `qa_validation.valid=true`; `audit/runtime/INT-07/verdict.json` |
| Hash preservation | `audit/runtime/INT-07/manifest.json` |
| Audit trail | `audit/runtime/INT-07/audit-log.jsonl` (execution_denial + gate_authority) |

## INT-11 — Parallel collection (REAL DSH, Session D3) — **PASS**

- 3 live concurrent children (cfo/kai/nova), real run IDs, distinct roles, version preserved `1→1`, deterministic `collection_order`, provenance preserved.
- Canonical bundle at `audit/runtime/INT-11/evidence.json` — QA `valid=true` (verdict at `audit/runtime/INT-11/verdict.json`).

## INT-12 — Failure propagation (REAL DSH, Session D3) — **PASS**

- Live child forced `FAILED`; typed `SubtaskFailed` propagated deterministically; no partial success; recovery/escalation path; no blind retry; no authority expansion.
- Canonical bundle at `audit/runtime/INT-12/evidence.json` — QA `valid=true`.

## REAL DSH BACKEND

- `RealDSHBackend` (Session E) was used as the `DelegationBackend` for both INT-01 and INT-07 — **FakeSubagentBackend was not used**.
- The bridge returned the real settled `subagent_<id>` outcomes (real run ids, real stop reasons, real structured TaskResults) into the existing `DelegationClient` → `ExecutionFlow` path.
- Session-E suite (`tests/live_dsh/`, 75 tests) green — contract/role/structured-capture/timeout/abort/failure/cleanup/evidence all verified.

## EVIDENCE QA

- All four scenarios validated with `tests/evidence/evidence_qa.py` (Session E): **INT-01 valid, INT-07 valid, INT-11 valid, INT-12 valid**.
- Bundles follow the canonical contract (identity, state pre/post, authority, gates, execution expected/observed, verification, final_status, audit_references, artifact_hashes, failure, provenance, evidence_items) + R1–R15 rejection rules.
- Retention per `docs/testing/0002` §4: `audit/runtime/<SCENARIO>/{evidence.json,manifest.json,audit-log.jsonl,flow_result.json,verdict.json}`.
- D3 evidence (INT-11/12) converted to canonical bundles; QA verdicts written.

## AUTHORITY

- No model text as authority (evidence items sourced CONTROL-PLANE-DECISION / RUNTIME-OBSERVED / AGENT-REPORTED, never authority).
- No state/audit as authority; BadSector PASS ≠ authorization (no PASS-as-ALLOW without delegation — R10 clean).
- No subdelegation (specialist delegation DENY BY DEFAULT, DLG-003 — verified by Session-E role adapter tests).
- Execution-time authority re-check mandatory (INT-07 proves revocation → execution DENY).
- COMPLETE only after verification (INT-01 verification verdict PASSED; INT-12 not COMPLETE on failure).

## PARALLEL EXECUTION

- INT-11: real concurrent children with dependency independence + ownership/write-scope safety verified (`assert_parallel_safe`), state version preserved across batch.
- INT-12: parallel batch with one forced failure propagating deterministically (no partial success).
- Real DSH evidence: live run ids and stop reasons recorded (not in-process).

## VERIFICATION

- INT-01: `verification.verdict=PASSED`, `final_status=COMPLETE`.
- INT-07: execution denied → verification `INCONCLUSIVE` (no outcome to verify), `final_status=BLOCKED`.
- INT-12: failure propagates; no COMPLETE without verified outcome.

## RECOVERY

- INT-12: failure classified (`logic`), recovery lifecycle entered (`RecoveryController`, PRESERVED), no blind retry (empty-cause and identical-cause refused), no authority expansion (child scope ⊆ parent, subdelegation denied, authority keys stripped).
- INT-07: authorization failure → BLOCKED (execution-time re-check denial, no mutation).

## TESTS

| Suite | Result |
|---|---|
| `tests/live_dsh/` (Session E, REAL-bridge prep) | 75 passed |
| `tests/evidence/` (Session E, QA validator) | 36 passed |
| `tests/orchestrator/dsh/` + `tests/orchestrator/execution/` | 197 passed |
| `tests/orchestrator/runtime/` | 75 passed |
| Broader regression (unit/authorization/adversarial/scenarios/workflow/integration/control_verification/control_risk) | 759 passed, 14 skipped (expected Phase-2C blocked) |
| **Total** | **1,142 passed** — no regression |

## RUNTIME EVIDENCE

| Scenario | Evidence bundle | Verdict |
|---|---|---|
| INT-01 | `audit/runtime/INT-01/evidence.json` + manifest/hashes + audit-log + flow_result | **valid=true** |
| INT-07 | `audit/runtime/INT-07/evidence.json` + manifest/hashes + audit-log + flow_result | **valid=true** |
| INT-11 | `audit/runtime/INT-11/evidence.json` + manifest + verdict | **valid=true** |
| INT-12 | `audit/runtime/INT-12/evidence.json` + manifest + verdict | **valid=true** |

Hashes preserved via per-scenario `manifest.json` (sha256 per artifact file). Audit trails preserved under `audit/runtime/`.

## VERIFIED

- Session policy (workspace-write + ask) from session log.
- D4/D7 role resolution for all 7 instances; presets mounted under `$DSH_HOME/.agent-presets/`.
- REAL backend active (marker + bridge); evidence capture active (QA validator + retention).
- INT-01 full lifecycle to COMPLETE with a real DSH child; INT-07 execution-time denial to BLOCKED with a real child under planning authority.
- INT-11/INT-12 live parallel + failure-propagation evidence (D3) canonicalized and QA-validated.
- All four scenario bundles validate through the Session-E QA validator; full regression green (1,142 passed).

## INFERRED

- The D4/D7 composition is treated as mounted because the live `subagent_<id>` tools resolve and dispatched real children successfully (this session), and the orchestrator-session marker convention is set — per `docs/testing/0003` §6/§9.

## ASSUMED

- `DSH_LIVE_BRIDGE_ACTIVE=1` marker convention (orchestrator session sets it post-mount).
- A mounted instance accepts the TaskResult output schema (verified live for cto here; assumed uniform across roles).

## UNKNOWN

- Runtime acceptance of `persona`/`toolFilter`/`maxDepth` for every role on the spawn provider beyond the exercised `cto` instance.
- Prompt injection (no claim made — out of scope for this phase, per instructions).

## BLOCKED

- **Transient LLM-provider rate limit (HTTP 429)** on the shared model provider affected several live dispatch attempts (INT-01/INT-07 initial attempts). Classified as **environment-class** (Runbook 07/08). Each retry was a **new** dispatch after the diagnosed cause (provider rate limit) cleared — never a blind/identical-cause retry. The successful live dispatches are recorded with real run ids. This is an infrastructure observation, not a runtime/control failure.

## SECURITY CLAIM STATUS

- **No L3 claim** (bundles carry `l3_claim: false`, `evidence_level: L2-LIVE`; QA R3/R15 would reject any false L3/INDEPENDENTLY-VERIFIED claim).
- **No prompt-injection security claim**.
- No new tool enabled; `web_fetch` disabled; Agent Teams not enabled; no out-of-process backends.
- Security invariants exercised: no model text/state/audit as authority; BadSector PASS ≠ authorization; no subdelegation; no blind retry; no scope expansion; execution-time re-check; COMPLETE only after verification.

## SCOPE CHECK

**In scope (added, test-support + evidence only):**
- `runs/closure/closure_harness.py` (test-support harness) + `runs/closure/ws-int01/`, `ws-int07/` + meta/live-result JSON.
- `audit/runtime/INT-01/`, `INT-07/`, `INT-11/`, `INT-12/` (evidence bundles + manifests + hashes + audit logs + verdicts).
- This report: `docs/phase-3/0002-phase3-runtime-closure.md`.

**Not modified:** production code (`orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/`), DSH core/profile/preset/session policy, role toolFilters, `tests/` existing files. No Phase 4 work; no L3 verification started.

## PHASE 3 VERDICT

**PASS**

Phase 3 runtime validation is closed:
- INT-01 and INT-07 executed as **REAL DSH variants** through `RealDSHBackend` + the approved D4/D7 instances + the existing `ExecutionFlow`/`ExecutionEngine`, with no `FakeSubagentBackend`.
- INT-11/INT-12 live evidence (D3) canonicalized and QA-validated.
- All four live scenarios have validated runtime evidence; full regression green (1,142 passed); evidence hashes + audit trails preserved.

## NEXT EXECUTION FLOW

- **Phase 4 preparation** — supported by this evidence: the Phase-3 runtime (execution flow, DSH adapter, RealDSHBackend, evidence QA) is validated across the four live scenarios with structured evidence. Phase 4 may proceed to acceptance-matrix-driven preparation **if and only if** the D4/D7 composition remains mounted and the provider rate-limit environment is stable; the remaining UNKNOWNs (per-role spawn acceptance, prompt injection) must be addressed in their owning phases. No automatic Phase-4 claim is made.

---

*Status: Phase 3 — Runtime Closure PASS. Test-support harness under `runs/closure/`; evidence under `audit/runtime/`; no production or DSH-core change. No L3 claim.*

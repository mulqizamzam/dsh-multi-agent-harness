# Phase 3 / Session D3 — LIVE DSH Parallel Execution — INT-11 + INT-12

- **Milestone**: Phase 3 / Session D3 — Live DSH parallel execution (INT-11 + INT-12)
- **Status**: **PASS (both tests)** — with actual live concurrent subagent evidence
- **Date**: 2026-08-30
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Runtime used**: existing Phase-3 runtime (`orchestrator/runtime/`, `orchestrator/dsh/`, `orchestrator/foundation/`, `control/*`, `state/helpers`, `audit/helpers`) — **not modified**
- **Composition used**: approved D4/D7 role composition — per-role `tool-subagent` instances `subagent_<id>` bound to persona `role-<id>`, provider `spawn`, `backgroundMode: continuable`, `maxDepth: 1` (`config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`)
- **Scope**: `tests/live_evidence/` (test-support harness + evidence) + `docs/phase-3/` (this report). **No production code, no control/state/audit/orchestrator/agents/config change, no DSH core/profile/preset change, no session policy change, no new tool, no Agent Teams, no Phase 4.**

---

## MILESTONE

Phase 3 / Session D3 — LIVE DSH parallel execution. Completed with **real** (not in-process) concurrent subagent evidence:

- **INT-11** — Live parallel subagent collection: **PASS**
- **INT-12** — Live failure propagation: **PASS**

Evidence files (JSON, machine-readable, produced by the harness):

| Artifact | Path |
|---|---|
| Batch manifest (tasks, delegation, safety, prompts) | `tests/live_evidence/run/all.manifest.json` |
| INT-11 live dispatch + structured results | `tests/live_evidence/run/INT-11.live_results.json` |
| INT-11 validated evidence (safety, collection, provenance, version) | `tests/live_evidence/run/INT-11.evidence.json` |
| INT-12 live dispatch + structured results (one FAILED) | `tests/live_evidence/run/INT-12.live_results.json` |
| INT-12 validated evidence (propagation, recovery, security) | `tests/live_evidence/run/INT-12.evidence.json` |
| Harness (test-support, not production) | `tests/live_evidence/harness.py`, `tests/live_evidence/run.py` |

---

## STATUS

**PASS.** Both INT-11 and INT-12 executed against the existing Phase-3 runtime with **live DSH subagent instances** (the approved D4/D7 per-role `subagent_<id>` tools). No in-process mock was used as live proof: every child was a real spawned subagent run (real run ids, real stop reasons, real structured outputs).

---

## INT-11 — Live parallel subagent collection — **PASS**

### What was run

Three independent, read-only subtasks were created and routed to the minimum specialist set (contract §6, no blanket fan-out):

| task_id | role | objective | scope |
|---|---|---|---|
| `int11-pricing` | `cfo` | unit-economics assessment | `docs/**`, `agents/**` |
| `int11-research` | `kai` | market/trend angle | `docs/**`, `config/**` |
| `int11-draft` | `nova` | two-sentence value proposition | `docs/**`, `README.md` |

### Checks performed (each verified by the production runtime)

1. **Create independent subtasks** — 3 `Task` objects, distinct owners (`cfo`, `kai`, `nova`), read-only scopes.
2. **Verify dependency independence** — `assert_parallel_safe` (production runtime) returned:
   `safe: true, reason: "independent, single-owner, read-only subtasks"`. No intra-batch `depends_on`.
3. **Verify ownership / write-scope safety** — every owner ∈ `SPECIALIST_ROLES` (never the orchestrator); single owner per task id; **no write scope** declared (specialists return results; the orchestrator is the single writer, THREAT-021).
4. **Capture state version** — `RuntimeStore.current_version()` → `held_version = 1` (project-state document through the execution gate).
5. **Dispatch through approved DSH adapter** — resolved each role → per-role `subagent_<id>` instance (persona `role-<id>`, provider `spawn`, `backgroundMode continuable`, `maxDepth 1`) and dispatched **concurrently** through the real tool surface. Authorized task context only (THREAT-020: no authority in messages).
6. **Execute concurrently** — all three children dispatched at `19:02:13Z`, settled `19:02:26Z`–`19:03:05Z` (overlapping live runs, real run ids):

   | task_id | tool instance | run_id | start | settle | stopReason |
   |---|---|---|---|---|---|
   | `int11-pricing` | `subagent_cfo` | `45124e03` | 19:02:13Z | 19:02:47Z | completed |
   | `int11-research` | `subagent_kai` | `97518df6` | 19:02:13Z | 19:03:05Z | completed |
   | `int11-draft` | `subagent_nova` | `8b3c8603` | 19:02:13Z | 19:02:26Z | completed |

7. **Collect structured TaskResult** — each child returned a JSON object conforming to `schemas/task-result.schema.json`; validated through the adapter's `TaskResultCollector` (schema + contract + role identity) then `collect_all` → 3 `CollectedResult`, all `SUCCEEDED` (6/5 findings + evidence for cfo, 7/8 for kai, 3/2 for nova, each with recommendation/risks/assumptions/actions_taken/unresolved_items).
8. **Verify provenance** — each collected result carries a `DelegationProvenance` stamp: role identity (`cfo`/`kai`/`nova`), tool instance (`subagent_<id>`), persona (`role-<id>`), real run_id, session id, `stop_reason: completed`, `live: true`.
9. **Verify post-batch state version** — `post_batch_version = 1 == held_version = 1` (no uncontrolled shared write during the parallel phase; THREAT-021 satisfied).

### INT-11 result

`outcome: COMPLETE`, `results: 3`, version unchanged `1 → 1`.

---

## INT-12 — Live failure propagation — **PASS**

### What was run

A parallel batch with **one child forced to FAIL** (a real live child returning a structured `FAILED` result):

| task_id | role | status |
|---|---|---|
| `int12-eng` | `cto` | `SUCCEEDED` |
| `int12-fail` | `kai` | **`FAILED`** (forced: primary source unavailable) |
| `int12-draft` | `somad` | `SUCCEEDED` |

Real dispatch (live instances, real run ids):

| task_id | tool instance | run_id | stopReason |
|---|---|---|---|
| `int12-eng` | `subagent_cto` | `06e2b891` | completed |
| `int12-fail` | `subagent_kai` | `61d68c1c` | completed (structured status FAILED) |
| `int12-draft` | `subagent_somad` | `9f2f1f3e` | completed |

### Checks performed (each verified by the production runtime)

1. **Force one child failure** — the `kai` child was instructed that its primary source is unavailable and to report `status: FAILED` with the missing-source unresolved item. It returned exactly that (real structured output).
2. **Failure propagates deterministically** — collection in **batch order** raised `SubtaskFailed` (role `kai`, task `int12-fail`, `failure_class: logic`). Deterministic: first-failure-in-batch-order, typed exception, not a prose guess.
3. **Unsafe continuation does not occur** — `results: 0` (no partial success), `outcome: FAILED` (not COMPLETE), state version unchanged `1 → 1`. The two successful siblings' results were **not** collected into a final result.
4. **Recovery / escalation path** — typed failure routed to the recovery lifecycle: `RecoveryController` entered (`recovery_state: PRESERVED`), path `RECOVERING (typed failure_class -> recovery lifecycle)`. Unknown failure classes would escalate (Runbook 08); a typed `logic` class follows the recovery lifecycle.
5. **No blind retry** — `RecoveryController` refused an empty-cause retry (`no_blind_retry_empty_cause: true`) and refused an identical-cause retry (`no_blind_retry_identical_cause: true`).
6. **No authority expansion** — verified: child delegation scope ⊆ parent (`child_scope_contained: true`), specialist subdelegation denied by default (`specialist_subdelegation_denied: true`, DLG-003), and authority-shaped keys attempted in a message were stripped (`authority_keys_stripped: true`, stripped `approval_reference`, `grant` — THREAT-020).

### INT-12 result

`outcome: FAILED` (the **test passes**: failure propagated deterministically, no unsafe continuation, recovery path + no blind retry + no authority expansion all verified).

---

## PARALLEL EVIDENCE

- **Real concurrency**: 3 live subagents in INT-11 (and 3 in INT-12) dispatched at the same second (`19:02:13Z` / `19:22:05Z`) and settling within overlapping windows — genuine parallel spawn through the approved D4/D7 `subagent_<id>` instances.
- **No in-process mock**: every child was a real DSH tool-subagent run. `live: true` is recorded per dispatch in `*.live_results.json` and `*.evidence.json`.
- **Safety pre-flight**: production `assert_parallel_safe` verified dependency independence, exclusive single-owner task ownership, read-only specialist scope, and the held project-state version **before** any child started.
- **Version stability**: held version `1` == post-batch version `1` for both batches (no uncontrolled shared writes).

## FAILURE PROPAGATION

- A live child returned a structured `FAILED` result; the production runtime propagated it as a typed `SubtaskFailed` (role `kai`, task `int12-fail`, `failure_class: logic`) at collection, in deterministic batch order.
- No partial success: `results: 0`; no silent skip; the flow did not reach COMPLETE.
- Evidence in `tests/live_evidence/run/INT-12.evidence.json` (`failure` + `results: []` + audit `subtask_failed`).

## RECOVERY

- `RecoveryController` entered (`PRESERVED`) with the typed failure class.
- Recovery path: `RECOVERING (typed failure_class -> recovery lifecycle)`.
- **No blind retry**: empty-cause and identical-cause retries refused (`RecoveryRefused`).
- Recovery does not acquire privilege (REC-004/THREAT-017) — privilege-escalation attempt refused (`recovery_no_privilege_escalation: true`).

## SECURITY

- **No authority expansion**: child delegation scope is a strict subset of the parent (`scope_contained` via `control.delegation`), so a specialist can never exceed the orchestrator's grant (AUTH-INV-04).
- **Subdelegation DENY BY DEFAULT**: a specialist attempting to issue a child delegation was denied (`SubdelegationDenied`, DLG-003).
- **Messages are data, never authority**: authority-shaped keys (`approval_reference`, `grant`) attempted in task context were stripped by the adapter (THREAT-020).
- **Provenance preserved**: role identity, delegation id, tool instance, persona, real run id, stop reason recorded for every live delegation.
- No production code, DSH core, profile, preset, or session policy was modified; no new tool was enabled; Agent Teams were not enabled; Phase 4 was not started.

## UNKNOWN

- None that block INT-11/INT-12: both ran live and passed. (See BLOCKED for the one transient environmental issue encountered and how it was handled.)

## BLOCKED

- **Transient LLM-provider rate limit (HTTP 429)** hit the shared model provider during the first INT-11 dispatch attempt and two CTO retries in INT-12. This is an **environment-class** failure (Runbook 07/08 classification), **not** a runtime/control failure. Per the recovery posture (no blind retry), each retry was a **new** dispatch after a **diagnosed** cause (provider rate limit) cleared — never an identical-cause automatic retry. The retried dispatches succeeded live. This is recorded honestly in the evidence (INT-11 evidence uses the successful retry batch; the failing first-batch children were abandoned, not silently reused).

## SCOPE CHECK

**In scope (added, test-support only):**
- `tests/live_evidence/` — harness + run scripts + JSON evidence (test-support, not production).
- `docs/phase-3/0001-live-int11-int12-evidence.md` — this report.

**Not modified:**
- Production code (`orchestrator/`, `control/`, `state/`, `audit/`, `agents/`, `config/`, `schemas/`).
- DSH core, profile, preset, session policy, toolFilter.
- No new tools enabled; Agent Teams not enabled.
- No Phase 4 work started.

## NEXT

- Phase 3 follow-ups (not started here): run live variants of INT-01 (full lifecycle) and INT-07 (execution-time re-check) with the same harness pattern; consider automating the live evidence harness into the CI-adjacent `tests/live_evidence/run.py` entry points (prep/finalize) for repeatable live runs.
- Phase 4 (explicitly **not** started): per the session instructions.

---

*Status: Phase 3 / Session D3 — INT-11 PASS, INT-12 PASS, with actual live concurrent subagent evidence. Test-support files under `tests/live_evidence/`; no production or DSH-core change.*

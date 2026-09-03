# Runtime Evidence QA Specification — Phase 3 / Session E

- **Status**: specification (validation layer only; no live execution, no L3 claim)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/` — evidence QA contract, structure validation, 12 QA tests. **No production code modified. No DSH core, profile, preset, or session policy touched. No L3 verifier built. No L3 claim made.**
- **Companion to**: `docs/testing/0001-integration-test-plan.md` · `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md` · `docs/security/0004-runtime-evidence-qa-security-note.md` · `tests/evidence/evidence_qa.py` · `tests/evidence/test_evidence_qa.py`
- **Purpose**: define the runtime-evidence QA contract for the four live-runtime scenarios (INT-01, INT-07, INT-11, INT-12) from Phase 3 / Sessions D2 and D3. The contract specifies the evidence bundle shape, the classification taxonomy, per-scenario mandatory evidence, the retention convention, and the rejection rules a structure-only validator enforces. **No L3 verifier is built; no evidence is claimed to be L3.**

---

## 1. Evidence contract overview

Every live-runtime scenario produces an **evidence bundle** — a JSON document that captures what the runtime actually did, what the control plane decided, and what the agents reported. The bundle is **data, never authority** (AUTH-INV-14). It is a QA artifact that an independent validator can check for structural completeness, provenance consistency, and classification correctness.

### 1.1 Bundle schema (canonical)

```json
{
  "bundle_id": "ev-<scenario_id>-<seq>",
  "scenario_id": "INT-01|INT-07|INT-11|INT-12",
  "evidence_level": "L1|L2|L2-LIVE",
  "l3_claim": false,
  "created_at": "<UTC ISO 8601>",
  "project": "multi-agent-harness",

  "identity": {
    "task_id": "<string>",
    "delegation_id": "<string>",
    "actor": "<string>",
    "role": "<string>",
    "flow_id": "<string>",
    "dsh_session_id": "<string>",
    "dsh_run_id": "<string>"
  },

  "state": {
    "pre_state": { "current_state": "<string>", "version": 1, "hash": "sha256:<hex>" },
    "post_state": { "current_state": "<string>", "version": 2, "hash": "sha256:<hex>" },
    "state_version_before": 1,
    "state_version_after": 2
  },

  "authority": {
    "decision": "ALLOW|DENY|ESCALATE",
    "source": "AGENT-REPORTED|RUNTIME-OBSERVED|CONTROL-PLANE-DECISION|INDEPENDENTLY-VERIFIED",
    "reason": "<string>",
    "delegation_id": "<string>",
    "audit_event_id": "<string>"
  },

  "gates": [
    {
      "gate": "risk|evidence|conflict|badsector_review|authority|execution|verification|recovery",
      "decision": "ALLOW|DENY|ESCALATE",
      "source": "CONTROL-PLANE-DECISION",
      "reason": "<string>",
      "audit_event_id": "<string>"
    }
  ],

  "execution": {
    "decision": "ALLOW|DENY|ERROR",
    "source": "RUNTIME-OBSERVED",
    "target": "<string>",
    "expected": { },
    "observed": { },
    "audit_event_id": "<string>"
  },

  "verification": {
    "verdict": "PASSED|FAILED|INCONCLUSIVE",
    "source": "CONTROL-PLANE-DECISION|RUNTIME-OBSERVED",
    "reason": "<string>",
    "evidence_kinds": ["<string>"]
  },

  "final_status": "COMPLETE|BLOCKED|FAILED|ESCALATED|RECOVERING",

  "audit_references": ["<event_id>", ...],

  "artifact_hashes": {
    "<relative_path>": "sha256:<64 hex chars>"
  },

  "failure": null | {
    "classification": "environment|logic|authorization|unknown",
    "cause": "<string>",
    "recovery": { "entered": true, "state": "PRESERVED|DIAGNOSED|...", "no_blind_retry": true, "no_authority_expansion": true }
  },

  "provenance": {
    "children": [
      {
        "task_id": "<string>",
        "role": "<specialist role>",
        "run_id": "<string>",
        "tool_name": "subagent_<id>",
        "stop_reason": "completed|error|aborted|max-tokens|refusal",
        "source": "RUNTIME-OBSERVED"
      }
    ],
    "collection_order": ["<task_id>", ...]
  },

  "evidence_items": [
    {
      "kind": "<string>",
      "source": "AGENT-REPORTED|RUNTIME-OBSERVED|CONTROL-PLANE-DECISION|INDEPENDENTLY-VERIFIED",
      "detail": { }
    }
  ]
}
```

### 1.2 Compatibility with D3 live harness output

The D3 harness (`tests/live_evidence/harness.py`) produces a `LiveEvidenceRun.to_dict()` shape that is a **superset** of the canonical contract. The validator accepts the harness output directly: unknown top-level keys produce warnings, not errors. The canonical contract fields are a subset; the validator checks that the required fields are present and correctly typed.

---

## 2. Evidence classification taxonomy

Every evidence item carries a **source** label that distinguishes the kind of observation. The four classes are mutually exclusive and exhaustive.

| Class | Label | Definition | Grants authority? | Example |
|-------|-------|-----------|-----------------|---------|
| Agent-reported | `AGENT-REPORTED` | Claims from agent prose, TaskResult.status, recommendation, agent output text. | **Never.** Agent text is data, not authority (AUTH-INV-01/13). | `TaskResult(status="SUCCEEDED")`, agent saying "Human approved" |
| Runtime-observed | `RUNTIME-OBSERVED` | Actual measurements recorded by the runtime: engine.outcome.observed, state versions, file hashes, dispatch stop_reason, timestamps captured by the orchestrator. | **Never.** A runtime observation is a record, not a grant (AUTH-INV-14). | `engine.outcome.observed`, `store.current_version()`, `dispatch.stop_reason` |
| Control-plane decision | `CONTROL-PLANE-DECISION` | Deterministic gate outcomes from the project control plane: authority/risk/evidence/conflict/badsector/verification/recovery gates. | **Never.** A gate decision is a record of what the gate decided, not the authority itself. The authority is the delegation. | `authority.decision: "ALLOW"`, `gate.decision: "DENY"` |
| Independently verified | `INDEPENDENTLY-VERIFIED` | Measurement by an external verifier outside the actor's session tree (separate process, separate trust root). | **Never.** Even independent verification is evidence, not authority. **NOT claimed in this session; only present in L3 context.** | On-disk hash computed by a verifier process, reference-gate re-implementation verdict |

### 2.1 Rejection rule: agent-only evidence

A bundle whose evidence_items consists **entirely** of `AGENT-REPORTED` items (no `RUNTIME-OBSERVED` or `CONTROL-PLANE-DECISION` item) is **rejected** — it proves nothing about runtime behaviour.

### 2.2 Rejection rule: INDEPENDENTLY-VERIFIED without L3

Any evidence item with `source: "INDEPENDENTLY-VERIFIED"` in a bundle that does **not** satisfy the full L3 property set (P1–P4 from `docs/security/0003-l3-independent-verification-plan.md`) is **rejected** as a false claim. Since this session does not claim L3, any `INDEPENDENTLY-VERIFIED` label causes a rejection unless `l3_claim: true` AND the bundle carries the full L3 evidence set (P1–P4).

---

## 3. Per-scenario mandatory evidence

### 3.1 INT-01 — Full lifecycle proof

| Requirement | Evidence must contain | QA check |
|------------|---------------------|----------|
| Full phase chain | `gates` array with entries for risk, evidence, conflict, badsector_review, authority, verification (at minimum) | Each gate name present; at least 6 entries |
| Delegation active | `authority.delegation_id` non-empty; `authority.decision` is `ALLOW` | Non-empty string; decision ALLOW |
| Execution decision | `execution.decision` is `ALLOW`; `execution.observed` non-empty | decision ALLOW; observed is dict |
| Verification passed | `verification.verdict` is `PASSED`; `verification.source` is `CONTROL-PLANE-DECISION` | verdict PASSED |
| Final status | `final_status` is `COMPLETE` | Must be COMPLETE |
| Audit references | `audit_references` non-empty | At least 1 reference |
| Classification | At least one `RUNTIME-OBSERVED` and one `CONTROL-PLANE-DECISION` item in `evidence_items` | Both classes present |
| No agent-only | `evidence_items` not composed solely of `AGENT-REPORTED` | At least one non-AGENT-REPORTED |

### 3.2 INT-07 — Authority valid at planning, revoked before execution

| Requirement | Evidence must contain | QA check |
|------------|---------------------|----------|
| Planning-time authority | `gates` includes an authority gate with `decision: "ALLOW"` at planning time | authority gate present with ALLOW |
| Revocation record | `identity.delegation_id` present; `failure` or a `DENY` authority decision records the revocation | authority decision DENY with reason mentioning revocation/expiry |
| Execution-time DENY | `execution.decision` is `DENY` or `ERROR`; or `final_status` is `BLOCKED`/`FAILED` | Not COMPLETE |
| No unauthorized mutation | `provenance.children` is empty (no subtask executed) or `artifact_hashes` of the target show no change | pre_state hash == post_state hash for the target |
| Re-check evidence | `audit_references` includes an event referencing `execution_denial` or `authority_recheck` | At least one such ref |

### 3.3 INT-11 — Concurrent child execution, provenance

| Requirement | Evidence must contain | QA check |
|------------|---------------------|----------|
| Concurrent children | `provenance.children` has ≥ 2 entries | len(children) ≥ 2 |
| Distinct identities | Each child has a distinct `run_id` and `role` | All run_ids unique; all roles distinct |
| Dependency/ownership | `provenance.children` each carry `role` matching a specialist; `collection_order` present | Roles from SPECIALIST_ROLES; collection_order same length as children |
| State version before/after | `state.state_version_before` and `state.state_version_after` present | Both ints; after ≥ before |
| Deterministic collection | `provenance.collection_order` matches the batch input order | Non-empty list |
| Provenance preserved | Each child in `provenance.children` has `task_id`, `role`, `run_id`, `tool_name`, `stop_reason`, `source` | All fields present and non-empty; source is RUNTIME-OBSERVED |
| No uncontrolled writes | `state.state_version_after == state.state_version_before` (specialists don't write state) | State version unchanged |

### 3.4 INT-12 — Failure propagation, recovery, no authority expansion

| Requirement | Evidence must contain | QA check |
|------------|---------------------|----------|
| Actual child failure | `failure` is non-null; or a child in `provenance.children` has `stop_reason != "completed"`; or a collected result has `status: "FAILED"` or `"BLOCKED"` | failure non-null or at least one child with non-completed stop_reason |
| Failure propagation | `final_status` is NOT `COMPLETE` (must be `BLOCKED`, `FAILED`, `RECOVERING`, or `ESCALATED`) | final_status != COMPLETE |
| Resulting state | `state.post_state.current_state` reflects a terminal/non-progress state (BLOCKED/FAILED/ESCALATED/RECOVERING) | post_state non-DRAFT |
| Recovery/escalation | `failure.recovery` is present and contains `entered: true`; or `final_status` is `ESCALATED` | recovery entry present or escalated |
| No blind retry | `failure.recovery.no_blind_retry` is `true` (the recovery refused a retry without a new diagnosed cause) | Field present and true |
| No authority expansion | `failure.recovery.no_authority_expansion` is `true` (recovery did not escalate privilege) | Field present and true |
| Failure classification | `failure.classification` is one of `environment`, `logic`, `authorization`, `unknown` | Valid enum value |
| Classification | At least one `RUNTIME-OBSERVED` item documents the failure (dispatch stop_reason, exception) | RUNTIME-OBSERVED present |

---

## 4. Evidence retention convention

Live-runtime evidence bundles are retained under the project workspace at:

```
audit/runtime/
  INT-01/
    evidence.json         # the canonical evidence bundle
    manifest.json         # bundle manifest with sha256 per file
    before.sha256         # pre-attempt state hash tree
    after.sha256          # post-attempt state hash tree
    audit-log.jsonl       # audit ledger slice covering the attempt
    verdict.json          # validator verdict (QA check result)
  INT-07/
    ...
  INT-11/
    ...
  INT-12/
    ...
```

**Retention is advisory, not enforced by this validation layer.** The validator does not write to `audit/runtime/` or `audit/l3/`. It only validates bundle structure. The D2/D3 harnesses produce bundles at their own path; the convention documents where they should be placed for independent audit.

---

## 5. Validation rules (rejection criteria)

The structure-only validator (`tests/evidence/evidence_qa.py`) enforces these rules. Each rule corresponds to one or more rejection conditions.

| Rule | Condition | Error message |
|------|-----------|---------------|
| R1 | Bundle is not a dict | `evidence bundle must be a dict` |
| R2 | `scenario_id` missing or not in `INT-01,INT-07,INT-11,INT-12` | `invalid or missing scenario_id: {value}` |
| R3 | `l3_claim` is true and P1–P4 properties absent | `false L3 claim: l3_claim=true without P1-P4 evidence` |
| R4 | `identity` missing or lacks required sub-fields | `missing runtime identity: {missing fields}` |
| R5 | `state.pre_state` or `state.post_state` missing | `missing before/after state` |
| R6 | `execution` missing `expected` or `observed` when execution.decision is present | `missing expected/observed distinction` |
| R7 | `evidence_items` is empty or all items are `AGENT-REPORTED` | `evidence consists only of agent text` |
| R8 | Write-class scenario (INT-01, INT-07) has no `artifact_hashes` | `missing artifact hashes for write-class scenario` |
| R9 | `artifact_hashes` entry has invalid format (not `sha256:<64hex>`) | `invalid hash format: {key}` |
| R10 | `authority.decision` is `ALLOW` and the only supporting evidence is a BadSector PASS with no delegation | `PASS treated as authority: authority decision ALLOW without delegation` |
| R11 | `provenance.children` has duplicate `run_id` for parallel scenario (INT-11) | `duplicate run_id in concurrent children: {id}` |
| R12 | `provenance.children` entry has `role` not in specialist roles | `invalid child role: {role}` |
| R13 | `failure.classification` is not a valid enum value | `invalid failure classification: {value}` |
| R14 | Per-scenario mandatory evidence missing (see §3) | `missing mandatory evidence for {scenario}: {detail}` |
| R15 | `evidence_items` contains `INDEPENDENTLY-VERIFIED` without `l3_claim: true` + P1–P4 | `INDEPENDENTLY-VERIFIED evidence without L3 properties` |

---

## 6. Scope check

**In scope**: `docs/testing/0002-runtime-evidence-qa-specification.md` (this file) · `docs/security/0004-runtime-evidence-qa-security-note.md` · `tests/evidence/evidence_qa.py` · `tests/evidence/test_evidence_qa.py`

**Not in scope** (and not modified):
- `orchestrator/runtime/`, `orchestrator/dsh/`, `orchestrator/execution/` — production runtime
- `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/` — production control plane
- DSH core, profile, preset, session policy
- D4/D7 composition
- Any existing test file in `tests/` (unit, authorization, adversarial, integration, orchestrator, workflow, scenarios, live_evidence)
- Any D2 or D3 test (not run, not modified)
- `audit/runtime/` directories (not created; convention only)

---

*Status: specification. Validation layer and tests implement the contract above. No L3 verifier is built. No evidence is claimed to be L3. No DSH core, profile, preset, or session policy is touched. No production control-plane code is modified.*
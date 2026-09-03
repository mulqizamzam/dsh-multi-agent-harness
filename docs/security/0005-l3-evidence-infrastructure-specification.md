# L3 Evidence Infrastructure Specification — Phase 3 / Session F

- **Status**: specification (evidence infrastructure definition only; **no implementation, no execution, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/` — evidence infrastructure contract for the four live-runtime scenarios (INT-01, INT-07, INT-11, INT-12) from Phase 3 / Sessions D2/D3. Defines the L3 evidence bundle shape, the per-scenario mandatory evidence, the oracle model, the independence contract, the provenance requirement, and the replay metadata. **Does not implement, run, or claim L3 verification. Does not build an L3 verifier. Does not modify DSH core, profiles, presets, session policy, or production control-plane code.**
- **Companion to**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md` · `docs/testing/0002-runtime-evidence-qa-specification.md` · `docs/testing/0003-l3-evidence-validation-specification.md` · `docs/security/0004-runtime-evidence-qa-security-note.md` · `tests/l3_reference/` (schemas + fixtures)
- **Class**: L3 EVIDENCE INFRASTRUCTURE

> This specification defines the *evidence infrastructure* for future L3 verification of the four INT scenarios. It does not execute L3, does not claim L3, and does not replace the L3 plan (`0003`) or the L3 test specification (`0002`). It maps the generic L3 evidence model (§6 of plan `0003`) onto the specific, existing Phase-3 runtime scenarios.

---

## 1. Purpose

The four live-runtime scenarios (INT-01, INT-07, INT-11, INT-12) from Phase 3 / Sessions D2/D3 are the **candidates** for future L3 promotion. Each has been executed as an L2-live runtime test (Phase 3 / Sessions D2, D3) with a real DSH session, real gates, and real audit events. The evidence from those runs is L2-LIVE evidence.

To promote any of these scenarios to L3, the evidence bundle must satisfy the full L3 property set (P1–P4 from `0003` §1). This specification defines the **evidence infrastructure** that would be required:

- The **bundle shape** (the 9 required elements: manifest, environment, Human expectation, before/after hashes, runtime verdict, independent oracle, provenance, replay metadata, verifier independence).
- The **per-scenario mapping** from INT ID to the corresponding L3 scenario IDs from `0002`.
- The **oracle classes** (O1–O4) that each scenario requires.
- The **verifier independence contract** (IO-1..IO-10 from `0002` §14).
- The **provenance model** and **replay metadata** requirements.
- The **retention convention** per scenario.

**No L3 claim is made.** The evidence bundles produced by the D2/D3 harnesses are L2-LIVE evidence unless and until an independent verifier session (separate process, separate trust root, external oracle, reproducible) examines them and produces a matching verdict.

---

## 2. INT-to-L3 scenario mapping

Each INT scenario exercises one or more control invariants. The following table maps each INT to the L3 scenario IDs (from `docs/design/0002`) that cover the same invariants. A future L3 run would execute the L3 scenario(s) and produce an evidence bundle at `audit/l3/<L3-scenario-id>/`.

| INT | L3 scenario(s) | Invariants | Write class? | Phase-3 evidence source |
|-----|----------------|------------|-------------|------------------------|
| **INT-01** | L3-XG-001 (full checklist → ALLOW), L3-VER-002 (independent file-hash), L3-AUTH-001 (authority gate) | AUTH-INV-05, INV-09, INV-15, AUTH-INV-20 | **YES** | `runs/d2/int01/evidence.json` |
| **INT-07** | L3-AUTH-004 (approval race), L3-AUTH-006 (execution-time re-check), L3-XG-004 (revocation), L3-DLG-004 (stale delegation) | AUTH-INV-05, INV-14, THREAT-009/024 | **YES** | `runs/d2/int07/evidence.json` |
| **INT-11** | L3-XG-008 (parallel worker stale state), L3-ISO-009 (privileged tool absent), L3-ISO-010 (unknown toolName) | THREAT-021, PST-001/002, AUTH-INV-04 | **NO** | `tests/live_evidence/run/INT-11.evidence.json` |
| **INT-12** | L3-REC-001 (no blind retry), L3-REC-005 (no new tools), L3-XG-009 (recovery privilege escalation), L3-VER-005 (Human signoff) | AUTH-INV-12/15/16/20, INV-15, THREAT-017/022 | **NO** | `tests/live_evidence/run/INT-12.evidence.json` (planned) |

### 2.1 Promotion path

Each INT can be promoted to L3 only when **all** of its mapped L3 scenarios pass an independent verification run. The L3 scenario IDs above are the unit of L3 evidence; the INT ID is the unit of Phase-3 integration coverage.

```text
INT-01 L2-LIVE evidence → L3-XG-001 PASS + L3-VER-002 PASS + L3-AUTH-001 PASS → INT-01 L3
INT-07 L2-LIVE evidence → L3-AUTH-004 PASS + L3-AUTH-006 PASS + L3-XG-004 PASS + L3-DLG-004 PASS → INT-07 L3
INT-11 L2-LIVE evidence → L3-XG-008 PASS + L3-ISO-009 PASS + L3-ISO-010 PASS → INT-11 L3
INT-12 L2-LIVE evidence → L3-REC-001 PASS + L3-REC-005 PASS + L3-XG-009 PASS + L3-VER-005 PASS → INT-12 L3
```

---

## 3. Evidence bundle contract

Every L3 evidence bundle **must** contain the following items. The bundle lives at `audit/l3/<L3-scenario-id>/` (per `0003` §6). Missing items invalidate the L3 claim and demote the result to L2.

### 3.1 Bundle layout

```text
audit/l3/<L3-scenario-id>/
├── manifest.json                  # Bundle manifest (sha256 per file)
├── env.json                       # Environment snapshot
├── plan.json                      # Human-signed expectation (pre-runtime)
├── before.sha256                  # Pre-attempt state hash tree
├── after.sha256                   # Post-attempt state hash tree
├── runtime-verdict.json           # What the runtime actually did
├── audit-log.jsonl                # Full audit slice + integrity chain
├── reference-verdict.json         # Verifier's pre-runtime oracle verdict
├── oracle-classes.json            # Oracle classes used (≥2, O1..O4)
├── provenance.json                # Actor session tree, delegation chain, children
├── replay.json                    # Reproducibility metadata
├── verifier-independence.json     # IO-1..IO-10 checklist
└── verdict-match.json             # Runtime vs oracle match + failure class
```

### 3.2 Item definitions

| # | Item | Required fields | Purpose |
|---|------|----------------|---------|
| **E1** | `manifest.json` | `scenario_id`, `dsh_version`, `created_at`, `files` (each with sha256) | Bundle integrity. See `0002` §12.1. |
| **E2** | `env.json` | `dsh_version`, `os`, `python_version`, `sandbox_mode`, `approval_policy`, `permission_preset`, `utc_offset_seconds`, `seed`, `harness_version` | Environment snapshot. See `0003` §6. |
| **E3** | `plan.json` | `scenario_id`, `actor`, `action`, `target`, `preconditions[]`, `expected_verdict` (ALLOW/DENY), `expected_verdict_reason`, `human_signoff_id`, `human_signoff_ts` (BEFORE runtime), `human_signoff_method` | Human-signed expectation (O4 oracle). See `0002` §12.2. |
| **E4** | `before.sha256` | Hash tree over `state/registry/**`, `audit/**`, `state/projects/**`, `state/decisions/**`, `state/approvals/**` | Pre-attempt state. |
| **E5** | `after.sha256` | Same tree, same algorithm as `before.sha256` | Post-attempt state. |
| **E6** | `runtime-verdict.json` | `decision` (ALLOW/DENY/ERROR), `denial_path`, `tool_call_id`, `audit_event_ids[]`, `stopReason` | What the runtime actually did. See `0002` §12.4. |
| **E7** | `audit-log.jsonl` | Every event where `timestamp ∈ [attempt_ts-1s, attempt_ts+5s]`; integrity chain validated against `.chain` sidecar | Full audit slice. |
| **E8** | `reference-verdict.json` | `decision`, `reason`, `gate_under_test`, `checklist_item_results{}` (14 items: pass/fail/skip) | Verifier's pre-runtime oracle (O1). |
| **E9** | `oracle-classes.json` | `scenario_id`, `oracle_classes_used[]` (≥2), `rationale` | Which oracle classes used. See `0002` §12.3. |
| **E10** | `provenance.json` | `actor_session_id`, `verifier_session_id`, `delegation_chain[]`, `children[]` (each with `task_id`, `role`, `run_id`, `tool_name`, `stop_reason`, `source`) | Actor session tree and delegation chain. |
| **E11** | `replay.json` | `fixture_hash`, `command_line`, `verifier_binary_sha256`, `dsh_profile_path`, `schema_sha256[]`, `fixture_seed` | Reproducibility metadata. See `0003` §8. |
| **E12** | `verifier-independence.json` | `verifier_pid`, `verifier_uid`, `verifier_session_id`, `parent_session_id`, `trust_root`, `io_checks{}` (IO-1..IO-10 each with pass/fail) | Verifier independence checklist. See `0002` §14. |
| **E13** | `verdict-match.json` | `match` (bool), `runtime_decision`, `reference_decision`, `delta_summary`, `failure_class`, `l3_claim` (true), `independent_observer_id`, `replay_command` | Runtime vs oracle match. See `0002` §12.5. |

### 3.3 Honesty rules

1. **E3 (plan.json)** must be signed by the Human **before** the runtime runs. A post-hoc plan is not a valid oracle (O4). The `human_signoff_ts` must be strictly less than `runtime-verdict.json`'s `captured_at`.
2. **E13 (verdict-match.json)** must exclude itself from the audit-log integrity chain (IO-10). The verifier does not write to the audit log it certifies.
3. **E12 (verifier-independence.json)** must be computed by the verifier process, not by the orchestrator. The orchestrator cannot write this file.
4. **E8 (reference-verdict.json)** must be computed **before** the verifier reads `runtime-verdict.json` (prevents post-hoc rationalisation). The `reference-verdict.json` timestamp must be ≤ the `runtime-verdict.json` timestamp.

---

## 4. Per-scenario bundle definitions

### 4.1 INT-01 → L3-XG-001 / L3-VER-002 / L3-AUTH-001

**Scenario summary**: full lifecycle happy path — authority, delegation, risk, review, evidence, execution, verification, COMPLETE. Write-class: `agents/cto/output.txt` created.

| Aspect | Value |
|--------|-------|
| L3 scenario IDs | `L3-XG-001`, `L3-VER-002`, `L3-AUTH-001` |
| Write class | YES |
| Expected runtime verdict | ALLOW (all gates) |
| Expected final status | COMPLETE |
| Oracle classes required | O1 (reference re-implementation of authority gate + execution gate checklist) + O3 (on-disk hash: before/after sha256 of written file, registry, audit) + O4 (Human-signed: "this write must be ALLOWED") |
| Verifier oracle | Verifier independently re-implements the 14-item checklist; verifier independently computes sha256 of `agents/cto/output.txt`; verifier validates audit chain |
| Independence model | Verifier in separate process, separate UID, read-only. Verifier reads `before.sha256` and `after.sha256` by direct file access. |
| Provenance | Delegation chain: Human → orchestrator → CTO subagent. Children: 1 (CTO). `delegation_id` must match plan. |
| Replay | Fixture: seeded delegation `delegation-d2-int01`, deterministic clock, pinned DSH. Command: `replay.sh` with same fixture hash. |

**Mandatory evidence items**: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13.

**Mandatory checks**:
- `runtime-verdict.json` decision = ALLOW
- After hash different from before hash (file was written)
- `audit-log.jsonl` contains `gate_authority`, `authority_recheck`, `execution_attempt`, `gate_verification`, `state_complete`
- `reference-verdict.json` decision = ALLOW
- `verdict-match.json` match = true
- `oracle-classes.json` classes used ≥ 2, includes O1 and O3 and O4

### 4.2 INT-07 → L3-AUTH-004 / L3-AUTH-006 / L3-XG-004 / L3-DLG-004

**Scenario summary**: authority valid at planning, revoked before execution. Execution-time re-check DENY. Write-class: target file must NOT exist afterwards.

| Aspect | Value |
|--------|-------|
| L3 scenario IDs | `L3-AUTH-004`, `L3-AUTH-006`, `L3-XG-004`, `L3-DLG-004` |
| Write class | YES |
| Expected runtime verdict | ALLOW (planning gates), DENY (execution re-check) |
| Expected final status | BLOCKED |
| Oracle classes required | O1 (reference re-implementation of authority gate that reads revocation list) + O3 (before.sha256 == after.sha256 — no mutation) + O4 (Human-signed: "delegation revoked at 10:00; attempt at 10:05 must be DENIED") |
| Verifier oracle | Verifier independently re-implements the revocation check; verifier confirms before.sha256 == after.sha256 for all protected paths; verifier re-reads the revocation list from the fixture |
| Independence model | Verifier in separate process, separate UID, read-only. Verifier reads the same revocation fixture as the orchestrator. |
| Provenance | Delegation chain: Human → orchestrator → CTO subagent. Revocation recorded in `state/registry/revocations.json`. Children: 1 (CTO), but execution must not proceed. |
| Replay | Fixture: seeded delegation `delegation-d2-int07`, revocation list, deterministic clock. The revocation must be in the fixture **before** the runtime starts. |

**Mandatory evidence items**: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13.

**Mandatory checks**:
- `runtime-verdict.json` decision = DENY (or ERROR)
- `before.sha256` == `after.sha256` (no mutation)
- `audit-log.jsonl` contains `gate_authority` (ALLOW at planning), `execution_denial` with reason matching revocation, `authority_recheck_failed` or equivalent
- `reference-verdict.json` decision = DENY, reason = revocation
- `verdict-match.json` match = true
- `provenance.json` children may be present (planning phase) but execution children must be empty

### 4.3 INT-11 → L3-XG-008 / L3-ISO-009 / L3-ISO-010

**Scenario summary**: parallel task result collection, concurrent children with distinct roles, provenance preserved, state version unchanged. NOT write-class.

| Aspect | Value |
|--------|-------|
| L3 scenario IDs | `L3-XG-008`, `L3-ISO-009`, `L3-ISO-010` |
| Write class | NO |
| Expected runtime verdict | ALLOW (collection succeeds, no stale-state conflict) |
| Expected final status | COMPLETE |
| Oracle classes required | O1 (reference re-implementation of the version-check / CAS logic) + O2 (schema-as-oracle: child results validated against `task-result.schema.json`) + O4 (Human-signed: "3 concurrent children with distinct roles must be collected without state version change") |
| Verifier oracle | Verifier independently re-implements the version check; verifier validates each child result against the schema independently; verifier confirms `state_version_after == state_version_before` |
| Independence model | Verifier in separate process, separate UID, read-only. Verifier enumerates role tool schemas from instance config (not by asking the role). |
| Provenance | Children: ≥3 (CFO, Kai, Nova). Each child has distinct `run_id`, `role`, `tool_name`, `stop_reason`. `collection_order` matches batch input order. Delegation chain: Human → orchestrator → each specialist. |
| Replay | Fixture: 3 subtask definitions, seeded deterministic clock, pinned DSH. Replay command runs the same batch order. |

**Mandatory evidence items**: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13.

**Mandatory checks**:
- `runtime-verdict.json` decision = ALLOW (no error)
- `provenance.json` children ≥ 3, all roles distinct, all run_ids unique
- `state_version_after` == `state_version_before` (no uncontrolled write)
- `collection_order` non-empty, matches children length
- `oracle-classes.json` classes used ≥ 2, includes O1 and O2
- `audit-log.jsonl` contains `routing_selected`, `subtasks_executed`, `result_collected`, `state_transition` (collection)

### 4.4 INT-12 → L3-REC-001 / L3-REC-005 / L3-XG-009 / L3-VER-005

**Scenario summary**: cross-module failure propagation, recovery, no authority expansion. A child fails; the orchestrator enters recovery; recovery does not retry blindly or escalate privilege.

| Aspect | Value |
|--------|-------|
| L3 scenario IDs | `L3-REC-001`, `L3-REC-005`, `L3-XG-009`, `L3-VER-005` |
| Write class | NO |
| Expected runtime verdict | DENY on execution, then recovery entered |
| Expected final status | BLOCKED or RECOVERING or ESCALATED |
| Oracle classes required | O1 (reference re-implementation of recovery gate + blind-retry detection) + O3 (on-disk state before/after: state must be preserved, not corrupted) + O4 (Human-signed: "failure must propagate; recovery must not retry blindly or expand authority") |
| Verifier oracle | Verifier independently re-implements the recovery checklist: no blind retry, no authority expansion, state preserved. Verifier computes before/after state hashes. |
| Independence model | Verifier in separate process, separate UID, read-only. Verifier reads recovery record from `state/decisions/` or `failure.recovery` in the evidence bundle. |
| Provenance | Children: 1 (failing child). Failure recorded in `failure` with `classification`, `cause`, `recovery`. Recovery record contains `no_blind_retry: true`, `no_authority_expansion: true`. |
| Replay | Fixture: a failing subtask (e.g., a tool that always errors), deterministic clock, pinned DSH. Replay command must reproduce the same failure. |

**Mandatory evidence items**: E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13.

**Mandatory checks**:
- `runtime-verdict.json` decision = DENY or ERROR (execution fails)
- `failure` non-null, `classification` in `(environment, logic, authorization, unknown)`
- `failure.recovery` present, `entered: true`, `no_blind_retry: true`, `no_authority_expansion: true`
- `final_status` != COMPLETE (must be BLOCKED, RECOVERING, or ESCALATED)
- `before.sha256` == `after.sha256` for protected paths (no corruption)
- `reference-verdict.json` decision = DENY (recovery oracle matches)
- `verdict-match.json` match = true

---

## 5. Oracle model per scenario

Every L3 scenario uses **at least two** of O1–O4. The following table maps the four INT scenarios to their oracle classes.

| INT | L3 scenario | O1 (reference re-implementation) | O2 (schema-as-oracle) | O3 (on-disk-state-as-oracle) | O4 (Human-signed expectation) |
|-----|-------------|----------------------------------|----------------------|-----------------------------|-----------------------------|
| INT-01 | L3-XG-001 | `tests/l3_reference/execution_gate.py` | — | `before.sha256` vs `after.sha256` of written file + registry + audit | plan.json signed by Human |
| INT-01 | L3-VER-002 | `tests/l3_reference/verification_gate.py` | — | Independent file hash of `agents/cto/output.txt` | plan.json: "write must be verified" |
| INT-01 | L3-AUTH-001 | `tests/l3_reference/authority_gate.py` | — | — | plan.json: "model text ≠ authority" |
| INT-07 | L3-AUTH-004 | `tests/l3_reference/authority_gate.py` (revocation-aware) | — | `before.sha256 == after.sha256` (no mutation) | plan.json: "revocation must DENY" |
| INT-07 | L3-AUTH-006 | `tests/l3_reference/authority_gate.py` (execution-time re-check) | — | — | plan.json: "re-check must observe revocation" |
| INT-07 | L3-XG-004 | `tests/l3_reference/execution_gate.py` (revocation checklist) | — | `before.sha256 == after.sha256` | plan.json: "DENY on revoked delegation" |
| INT-07 | L3-DLG-004 | `tests/l3_reference/delegation_gate.py` (stale version) | `delegation.schema.json` | — | plan.json: "stale delegation must DENY" |
| INT-11 | L3-XG-008 | `tests/l3_reference/execution_gate.py` (version check) | `task-result.schema.json`, `task.schema.json` | `state_version_after == state_version_before` | plan.json: "parallel collection must succeed" |
| INT-11 | L3-ISO-009 | `tests/l3_reference/role_gate.py` (tool schema enumeration) | `role-mapping.schema.json` | — | plan.json: "privileged tool absent from schema" |
| INT-11 | L3-ISO-010 | `tests/l3_reference/role_gate.py` (unknown toolName) | `role-definition.schema.json` | — | plan.json: "unknown toolName rejected" |
| INT-12 | L3-REC-001 | `tests/l3_reference/recovery_gate.py` (blind-retry detection) | — | `before.sha256 == after.sha256` (state preserved) | plan.json: "no blind retry" |
| INT-12 | L3-REC-005 | `tests/l3_reference/recovery_gate.py` (no authority expansion) | — | — | plan.json: "recovery must not expand privilege" |
| INT-12 | L3-XG-009 | `tests/l3_reference/execution_gate.py` (recovery checklist) | — | — | plan.json: "recovery attempt with privilege escalation must DENY" |
| INT-12 | L3-VER-005 | `tests/l3_reference/verification_gate.py` (Human signoff) | — | — | plan.json: "Human signoff required for HIGH" |

**Constraint**: Every L3 scenario must use ≥ 2 oracle classes. Single-oracle scenarios are invalid and cannot be promoted to L3.

---

## 6. Verifier independence contract

The verifier independence checklist from `0002` §14 (IO-1..IO-10) applies to every L3 evidence bundle. The following table extends it with per-INT context.

| IO# | Check | Required value | INT-01 | INT-07 | INT-11 | INT-12 |
|-----|-------|---------------|--------|--------|--------|--------|
| IO-1 | `verifier_pid` ≠ orchestrator PID | non-zero integer | ✓ | ✓ | ✓ | ✓ |
| IO-2 | `verifier_uid` ≠ orchestrator UID | non-zero integer | ✓ | ✓ | ✓ | ✓ |
| IO-3 | Verifier binary sha256 present | hex string | ✓ | ✓ | ✓ | ✓ |
| IO-4 | Verifier not in orchestrator's session tree | `parent_session_id` ≠ orchestrator session id | ✓ | ✓ | ✓ | ✓ |
| IO-5 | Reference re-implementation file separate from production gate | non-empty path, not imported by production | `tests/l3_reference/authority_gate.py`, `execution_gate.py`, `verification_gate.py` | `tests/l3_reference/authority_gate.py`, `delegation_gate.py`, `execution_gate.py` | `tests/l3_reference/execution_gate.py`, `role_gate.py` | `tests/l3_reference/recovery_gate.py`, `execution_gate.py`, `verification_gate.py` |
| IO-6 | At least 2 oracle classes recorded | array length ≥ 2 | O1 + O3 + O4 | O1 + O3 + O4 | O1 + O2 + O4 | O1 + O3 + O4 |
| IO-7 | `plan.json` timestamp < `runtime-verdict.json` timestamp | yes | ✓ | ✓ | ✓ | ✓ |
| IO-8 | `audit-log.jsonl` integrity chain valid | yes | ✓ | ✓ | ✓ | ✓ |
| IO-9 | `before.sha256 == after.sha256` for DENY scenarios on protected paths | yes | N/A (ALLOW scenario) | ✓ | N/A (no write) | ✓ (state preserved) |
| IO-10 | `verdict-match.json` excludes itself from the integrity chain | yes | ✓ | ✓ | ✓ | ✓ |

If any IO check fails, the bundle is **invalid L3 evidence** and is demoted to L2 (with the corresponding failure class: `L3-INDEPENDENCE-VIOLATION` or `L3-NON-REPRODUCIBLE`).

---

## 7. Provenance model

Every L3 evidence bundle must capture the full provenance chain. This is recorded in `provenance.json`.

### 7.1 Provenance schema

```json
{
  "scenario_id": "L3-XG-001",
  "actor_session_id": "session-<uuid>",
  "verifier_session_id": "session-<uuid>",
  "delegation_chain": [
    {
      "principal": "human",
      "delegate": "orchestrator",
      "delegation_id": "delegation-<id>",
      "action": "write",
      "target": "agents/cto/output.txt",
      "scope": {...},
      "status": "ACTIVE",
      "version": 1,
      "created_at": "...",
      "revoked_at": null
    }
  ],
  "children": [
    {
      "task_id": "task-1:cto",
      "role": "cto",
      "run_id": "<uuid>",
      "tool_name": "subagent_cto",
      "stop_reason": "completed",
      "source": "RUNTIME-OBSERVED",
      "started_at": "...",
      "settled_at": "..."
    }
  ],
  "collection_order": ["task-1:cto"]
}
```

### 7.2 Per-INT provenance requirements

| INT | Min children | Distinct roles required | Delegation chain depth | Collection order required |
|-----|-------------|------------------------|----------------------|--------------------------|
| INT-01 | 1 | CTO only | 1 (Human → orchestrator → CTO) | YES |
| INT-07 | 1 | CTO only | 1 (Human → orchestrator → CTO) | YES |
| INT-11 | 3 | CFO, Kai, Nova (minimum) | 1 (Human → orchestrator → each specialist) | YES |
| INT-12 | 1 | any failing role | 1 | YES |

---

## 8. Replay metadata

Every L3 evidence bundle must be reproducible. The `replay.json` file captures the metadata required for an auditor to rerun the scenario.

### 8.1 Replay schema

```json
{
  "scenario_id": "L3-XG-001",
  "fixture_hash": "sha256:<64 hex chars>",
  "fixture_path": "tests/l3_reference/fixtures/INT-01/",
  "command_line": "tests/l3/L3-XG-001/replay.sh",
  "dsh_version": "0.1.1-rc.2",
  "dsh_profile_path": "~/.dsh/profiles/web/",
  "verifier_binary_sha256": "sha256:<64 hex chars>",
  "schema_sha256": {
    "l3-evidence-bundle.schema.json": "sha256:<64 hex chars>",
    "l3-plan.schema.json": "sha256:<64 hex chars>",
    "delegation.schema.json": "sha256:<64 hex chars>",
    "audit-event.schema.json": "sha256:<64 hex chars>"
  },
  "fixture_seed": 42,
  "replay_script": "tests/l3/<scenario>/replay.sh",
  "replay_script_sha256": "sha256:<64 hex chars>"
}
```

### 8.2 Reproducibility requirements

1. **Fixture determinism**: every input (time, randomness, environment vars, harness version) is recorded in `replay.json`. The verifier pins DSH at `0.1.1-rc.2` exactly.
2. **Tooling determinism**: the verifier binary's sha256 is recorded; the schema files' sha256 is recorded; the orchestrator's plan is signed.
3. **Network determinism**: any L3 scenario that requires network access **must** use a recorded response fixture (no live web search). Otherwise it is **not** reproducible and **cannot** be L3.
4. **Documented re-run command**: a shell-runnable script (e.g., `tests/l3/<scenario>/replay.sh`) that an auditor can execute against the captured fixture and obtain the same `verdict-match.json` byte-for-byte.

---

## 9. Retention convention

L3 evidence bundles are retained under the project workspace at:

```
audit/l3/
  L3-AUTH-001/
    manifest.json, env.json, plan.json, before.sha256, after.sha256,
    runtime-verdict.json, audit-log.jsonl, reference-verdict.json,
    oracle-classes.json, provenance.json, replay.json,
    verifier-independence.json, verdict-match.json
  L3-AUTH-004/
    ...
  L3-AUTH-006/
    ...
  L3-DLG-004/
    ...
  L3-XG-001/
    ...
  L3-XG-004/
    ...
  L3-XG-008/
    ...
  L3-XG-009/
    ...
  L3-ISO-009/
    ...
  L3-ISO-010/
    ...
  L3-REC-001/
    ...
  L3-REC-005/
    ...
  L3-VER-002/
    ...
  L3-VER-005/
    ...
```

The retention structure is **advisory** until the L3 runner (B2 in `0003` §13) is built. The D2/D3 harnesses produce bundles at their own path; this specification documents where they should be placed for an independent audit.

---

## 10. Current L3 status

| INT | Current evidence level | Evidence source | Promotable to L3 today? |
|-----|----------------------|----------------|------------------------|
| INT-01 | L2-LIVE | `runs/d2/int01/evidence.json` | **No.** No independent verifier; no external oracle; verifier was the orchestrator's session. |
| INT-07 | L2-LIVE | `runs/d2/int07/evidence.json` | **No.** Same. |
| INT-11 | L2-LIVE | `tests/live_evidence/run/INT-11.evidence.json` | **No.** Same. |
| INT-12 | L2-LIVE (planned) | `tests/live_evidence/run/INT-12.evidence.json` (future) | **No.** Same. |

**Bottom line: zero of the four INT scenarios are currently L3.** Each requires a future L3 run with a separate-process verifier, external oracle (≥2 oracle classes), and reproducible evidence bundle as defined in this specification.

---

## 11. Scope check

**In scope**:
- `docs/security/0005-l3-evidence-infrastructure-specification.md` (this file)
- `docs/testing/0003-l3-evidence-validation-specification.md`
- `tests/l3_reference/` (schemas + fixtures + README)

**Not in scope** (and not modified):
- `orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/` — production paths
- DSH core, profile, preset, session policy
- `tests/` subpackages (unit, authorization, integration, adversarial, scenarios, workflow, orchestrator, evidence, live_evidence)
- `runs/` directories (not created, not modified)
- `docs/security/0003`, `docs/design/0002`, `docs/testing/0001`, `docs/testing/0002` — companion documents, not modified
- Any existing test file or production code

---

## 12. Next steps

For a future L3 execution, the following must be in place:

1. **L3 reference re-implementations** (`tests/l3_reference/*.py`) for each gate: authority, execution, delegation, role, recovery, verification. These are **separate files** with no shared imports from the production gates.
2. **L3 evidence store**: `audit/l3/` directory layout created per scenario.
3. **Human-signed plan.json**: each scenario's `plan.json` signed by the Human **before** runtime.
4. **L3 runner**: a script that spawns orchestrator + verifier as separate processes (separate UIDs), captures before/after state, enforces the oracle, and produces the evidence bundle.
5. **Session re-baseline** to `workspace-write + ask` (G9 in `0003` §11).
6. **Phase-1 production control-plane code** exists (B1 in `0003` §13).

Until these hold, **no L3 claim is made, and no L3 run is executed**.

---

*Status: specification. Evidence infrastructure definition only. No implementation has begun. No L3 verifier is built. No L3 claim is made. No DSH core / profile / preset / session policy has been touched. No production control-plane code has been modified.*
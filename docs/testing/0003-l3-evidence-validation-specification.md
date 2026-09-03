# L3 Evidence Validation Specification — Phase 3 / Session F

- **Status**: specification (validation contract only; **no implementation, no execution, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/` — validation rules and fixture/schema contract for L3 evidence bundles of INT-01 / INT-07 / INT-11 / INT-12. **No production code modified. No DSH core, profile, preset, or session policy touched. No L3 verifier built. No L3 claim made.**
- **Companion to**: `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md` · `docs/testing/0002-runtime-evidence-qa-specification.md` · `tests/l3_reference/` (schemas + fixtures)
- **Class**: L3 EVIDENCE VALIDATION (structure-only)

> This specification defines the *validation contract* for L3 evidence bundles. It is a **structure-only** validator contract: it checks that a bundle is complete, well-formed, and internally consistent. It does **not** verify that a control enforced anything at runtime (that is the L3 verifier's job, which is not built). A bundle passing structure validation is **not** L3 evidence; a bundle failing structure validation is **definitely not** L3 evidence.

---

## 1. Relationship to existing layers

| Layer | Purpose | Who runs it | L3 claim? |
|-------|---------|------------|-----------|
| `tests/evidence/evidence_qa.py` (Phase 3 / Session E) | Validates the **L2-LIVE** evidence bundle shape for INT-01/07/11/12 | CI, any developer | No |
| `tests/l3_reference/` schemas (this session) | Validates the **L3** evidence bundle shape (manifest, env, plan, hashes, verdicts, provenance, replay, independence) | Future L3 runner, auditor | No |
| `tests/l3_reference/*.py` gate re-implementations (future) | Independent oracle (O1) re-implementations | Future L3 verifier | Only as part of a full L3 run |
| L3 verifier (future, not built) | Independent observer that computes the oracle verdict | Future L3 verifier process | Yes, only with P1–P4 |

The L3 evidence bundle validation contract in this document is the **bridge** between the Phase-3 L2-LIVE evidence bundles and a future L3 claim. It ensures that when an L3 run happens, the evidence it produces is machine-verifiable for completeness.

---

## 2. L3 evidence bundle contract (summary)

An L3 evidence bundle lives at `audit/l3/<L3-scenario-id>/` and **must** contain the following files (full definition in `docs/security/0005` §3):

```text
audit/l3/<L3-scenario-id>/
├── manifest.json                  # sha256 per file
├── env.json                       # environment snapshot
├── plan.json                      # Human-signed expectation (pre-runtime)
├── before.sha256                  # pre-attempt state hash tree
├── after.sha256                   # post-attempt state hash tree
├── runtime-verdict.json           # what the runtime did
├── audit-log.jsonl                # audit slice + integrity chain
├── reference-verdict.json         # verifier's pre-runtime oracle verdict
├── oracle-classes.json            # oracle classes used (≥2)
├── provenance.json                # actor session tree + delegation chain + children
├── replay.json                    # reproducibility metadata
├── verifier-independence.json     # IO-1..IO-10 checklist
└── verdict-match.json             # runtime vs oracle match + failure class
```

The canonical schemas for these files live under `tests/l3_reference/schemas/`:

| File | Schema |
|------|--------|
| `manifest.json` | `tests/l3_reference/schemas/l3-manifest.schema.json` |
| `env.json` | `tests/l3_reference/schemas/l3-env.schema.json` |
| `plan.json` | `tests/l3_reference/schemas/l3-plan.schema.json` |
| `before.sha256` / `after.sha256` | `tests/l3_reference/schemas/l3-state-hash.schema.json` |
| `runtime-verdict.json` | `tests/l3_reference/schemas/l3-runtime-verdict.schema.json` |
| `reference-verdict.json` | `tests/l3_reference/schemas/l3-reference-verdict.schema.json` |
| `oracle-classes.json` | `tests/l3_reference/schemas/l3-oracle-classes.schema.json` |
| `provenance.json` | `tests/l3_reference/schemas/l3-provenance.schema.json` |
| `replay.json` | `tests/l3_reference/schemas/l3-replay.schema.json` |
| `verifier-independence.json` | `tests/l3_reference/schemas/l3-independence.schema.json` |
| `verdict-match.json` | `tests/l3_reference/schemas/l3-verdict-match.schema.json` |

---

## 3. Validation rules (rejection criteria)

A structure-only validator over L3 evidence bundles enforces these rules. Each rule corresponds to one or more rejection conditions. The validator **never** executes a control, a gate, or the runtime.

### 3.1 Bundle-level rules

| Rule | Condition | Error message |
|------|-----------|---------------|
| LV1 | Bundle directory missing any required file (E1–E13) | `missing L3 evidence file: {file}` |
| LV2 | `manifest.json` missing or `files` object incomplete (does not list all 13 files) | `manifest incomplete: missing {files}` |
| LV3 | Any file's sha256 in `manifest.json` mismatches the on-disk file | `manifest sha256 mismatch for {file}` |
| LV4 | `env.json` missing required fields (`dsh_version`, `os`, `python_version`, `sandbox_mode`, `approval_policy`, `permission_preset`, `utc_offset_seconds`, `seed`) | `env.json missing required field: {field}` |
| LV5 | `env.json.dsh_version` != `0.1.1-rc.2` | `dsh_version must be pinned to 0.1.1-rc.2` |
| LV6 | `plan.json` missing required fields (`scenario_id`, `actor`, `action`, `target`, `preconditions[]`, `expected_verdict`, `expected_verdict_reason`, `human_signoff_id`, `human_signoff_ts`) | `plan.json missing required field: {field}` |
| LV7 | `plan.json.human_signoff_ts` is NOT before `runtime-verdict.json` `captured_at` | `plan.json signoff must precede runtime verdict` |
| LV8 | `oracle-classes.json.oracle_classes_used` length < 2 | `oracle-classes: fewer than 2 oracle classes` |
| LV9 | `oracle-classes.json.oracle_classes_used` contains invalid class (not in O1..O4) | `invalid oracle class: {class}` |
| LV10 | `verdict-match.json.l3_claim` is false or missing | `l3_claim must be true for an L3 bundle` |
| LV11 | `verdict-match.json.match` is false | `runtime and oracle verdicts differ (L3-FAIL-...)` — security case, record as failure class |
| LV12 | `verifier-independence.json` any IO check fails (IO-1..IO-10) | `independence check failed: {IO-#}` |
| LV13 | `provenance.json` missing `actor_session_id`, `verifier_session_id`, or `delegation_chain` | `provenance missing: {field}` |
| LV14 | `replay.json` missing `fixture_hash`, `command_line`, `verifier_binary_sha256`, `dsh_version` | `replay.json missing required field: {field}` |
| LV15 | `runtime-verdict.json` missing `decision`, `denial_path`, `tool_call_id`, `audit_event_ids[]`, `stopReason` | `runtime-verdict missing required field: {field}` |
| LV16 | `reference-verdict.json` missing `decision`, `reason`, `gate_under_test`, `checklist_item_results{}` | `reference-verdict missing required field: {field}` |
| LV17 | `audit-log.jsonl` empty or fails strict read (`read_events_strict`) | `audit-log corrupt or empty` |
| LV18 | `audit-log.jsonl` integrity chain invalid (mismatch against `.chain` sidecar or recomputed chain) | `audit-log integrity chain invalid` |
| LV19 | `verdict-match.json` appears in `audit-log.jsonl` (verifier certifies itself) | `verdict-match.json must not be in the audit log` |
| LV20 | `before.sha256` or `after.sha256` is not a valid sha256 tree hash (format) | `invalid state hash format` |

### 3.2 Per-scenario mandatory evidence

The per-scenario mandatory evidence is defined in `docs/security/0005` §4. The validator enforces these rules:

| Rule | INT | Condition | Error message |
|------|-----|-----------|---------------|
| LV-INT-01 | INT-01 | `runtime-verdict.json.decision` != ALLOW | `INT-01 runtime verdict must be ALLOW` |
| LV-INT-01b | INT-01 | `after.sha256` == `before.sha256` (write-class scenario must have a delta) | `INT-01 write produced no state change` |
| LV-INT-07 | INT-07 | `runtime-verdict.json.decision` not in (DENY, ERROR) | `INT-07 runtime verdict must be DENY/ERROR` |
| LV-INT-07b | INT-07 | `before.sha256` != `after.sha256` (no mutation) | `INT-07 mutated state despite DENY` |
| LV-INT-11 | INT-11 | `provenance.json.children` length < 3 | `INT-11 requires >= 3 concurrent children` |
| LV-INT-11b | INT-11 | child roles not distinct | `INT-11 children must have distinct roles` |
| LV-INT-11c | INT-11 | `runtime-verdict.json` final state version changed (`state_version_after != state_version_before`) | `INT-11 uncontrolled state change` |
| LV-INT-12 | INT-12 | `runtime-verdict.json` has no `failure` record | `INT-12 requires failure propagation evidence` |
| LV-INT-12b | INT-12 | `failure.recovery.no_blind_retry` != true | `INT-12 recovery did not set no_blind_retry` |
| LV-INT-12c | INT-12 | `failure.recovery.no_authority_expansion` != true | `INT-12 recovery did not set no_authority_expansion` |

### 3.3 Fail-closed rule

A validator that cannot read a required file, cannot validate a schema, or encounters an unknown field in a required file **must fail closed** (reject the bundle). Unknown optional fields are warnings, never silent passes.

---

## 4. Schema validation procedure (fixture/schema scaffolding)

The JSON Schemas in `tests/l3_reference/schemas/` are validated by a **third-party** `jsonschema` library invocation (O2-style). The following procedure is the contract for the scaffolding:

```bash
# Validate each L3 evidence file against its schema
python3 -m jsonschema -i audit/l3/<L3-scenario-id>/manifest.json \
    tests/l3_reference/schemas/l3-manifest.schema.json
python3 -m jsonschema -i audit/l3/<L3-scenario-id>/plan.json \
    tests/l3_reference/schemas/l3-plan.schema.json
# ... repeat for every file in the bundle
```

**Honesty note**: schema validation alone is **not** L3 verification. It checks structure. The independent oracle (O1 re-implementations) and the runtime verdict (P1) must still be present and match (P4 reproducible).

---

## 5. Fixture scaffolding

The fixtures in `tests/l3_reference/fixtures/` are **inert specification support**: they are the *shapes* that a Human-signed `plan.json` and a seeded environment take for each INT scenario. They are NOT executable, NOT a verifier, and NOT actual signed evidence.

| Fixture | Purpose |
|---------|---------|
| `tests/l3_reference/fixtures/INT-01/plan.json` | Template for the Human-signed expectation of the INT-01 happy path |
| `tests/l3_reference/fixtures/INT-07/plan.json` | Template for the Human-signed expectation of the INT-07 revocation DENY |
| `tests/l3_reference/fixtures/INT-11/plan.json` | Template for the Human-signed expectation of the INT-11 parallel collection |
| `tests/l3_reference/fixtures/INT-12/plan.json` | Template for the Human-signed expectation of the INT-12 failure/recovery |
| `tests/l3_reference/fixtures/shared/env.template.json` | Template for `env.json` with the pinned DSH version |

These fixtures contain **placeholder** values (`<...>`) and must be filled + signed by the Human before any L3 run. They carry no authority (AUTH-INV-14).

---

## 6. Scope check

**In scope**: `docs/testing/0003-l3-evidence-validation-specification.md` (this file) · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `tests/l3_reference/` (schemas + fixtures + README)

**Not in scope** (and not modified):
- `orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/` — production paths
- DSH core, profile, preset, session policy
- `tests/evidence/`, `tests/live_evidence/`, `tests/integration/`, and every other existing test subpackage
- `docs/security/0003`, `docs/design/0002`, `docs/testing/0001`, `docs/testing/0002`, `docs/security/0004`
- `audit/l3/` and `audit/runtime/` directories (not created; convention only)

---

*Status: specification. Validation contract only. No L3 verifier is built. No evidence is claimed to be L3. No DSH core / profile / preset / session policy is touched. No production control-plane code is modified.*
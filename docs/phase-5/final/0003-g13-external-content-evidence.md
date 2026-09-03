# G13 Verification Evidence — Prompt-Injection / External-Content Handling (REQUIRED GATE)

- **Milestone**: Phase 5 / Final — G13 VERIFICATION EVIDENCE (REQUIRED BEFORE FINAL SECURITY ACCEPTANCE)
- **Status**: EVIDENCE REPORT (deterministic verification; **no claim of full closure**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/final/0003-g13-external-content-evidence.md` (this file, write-only).
- **Companion**: `docs/phase-5/security/0002-g13-external-content-verification.md` · `docs/phase-5/security/0001-g10-g13-security-residual-analysis.md` §2 · `docs/phase-5/final/0001-security-closure-matrix.md` (G13 row, §1) · `docs/security/0003-external-content-verification-spec.md` · `docs/adr/0001` (UNKNOWN #1).
- **G13 is REQUIRED BEFORE FINAL SECURITY ACCEPTANCE.** This report records exactly what is verified, with evidence, and explicitly what remains UNKNOWN. **No prompt-injection claim is made anywhere in this document.**

---

## 1. Trust posture (external content = DATA, not instructions)

The architecture treats **all external/subagent content as untrusted data**, never as instructions or authority (AGENTS.md operating principle 8; `orchestrator/dsh/context.py` module docstring):

- **Structured `TaskResult`** from a child is schema-validated, its role identity is checked (`DelegationClient.delegate` step 9 → `TaskResultCollector.collect`), and it is stored as `result` — it is **never an authority input**.
- **Child text output** is never read as a gate input.
- **Authority** is read exclusively from the structured delegation registry at the control-plane layer (`control.authority.recheck_authority`; `control/execution_gate.py` for write-class actions) — **never from model prose, audit entries, review verdicts, or messages** (AUTH-INV-01/07/13/14).
- **Quarantine** of external channel content is a data-hygiene baseline (marker-keyword classifier, `tests/control_plane.py::quarantine`); it is **not** a structural-instruction detector and not a runtime/DSH-layer claim.
- **BadSector PASS is never authorization** (AUTH-INV-09 / BAD-003); even a provenance-valid PASS does not authorize execution.
- **Model judgment is not authority**; the authority gate is code-enforced, not prompt-based (AGENTS.md principle 7).

---

## 2. Entry points × verified defenses

All defenses below are **deterministic** (in-process tests; no live DSH child dispatched). "Enforcement location" is the production code path quoted in §2.1; "Test that proves it" is a test observed green in §3.

| # | Entry point | Defense (verified deterministic) | Enforcement location (production) | Test that proves it |
|---|---|---|---|---|
| (a) | `extra_context` passed to a child | Authority-shaped keys stripped + recorded in `_adapter.stripped_authority` (THREAT-020); child receives DATA, never authority | `orchestrator/dsh/context.py::build_task_context` (keys in `_AUTHORITY_KEYS` dropped; stripping recorded) | `tests/phase5_security/test_external_content_data.py::TestAuthorityKeysStripped::test_authority_keys_removed_from_context` |
| (b) | Message / payload bodies | `assert_no_authority_in_payload` refuses any authority-bearing body with `DSHError` (THREAT-020); a clean payload passes | `orchestrator/dsh/context.py::assert_no_authority_in_payload` (raises `DSHError` listing offending keys) | `tests/phase5_security/test_external_content_data.py::TestAuthorityKeysStripped::test_assert_no_authority_in_payload` |
| (c) | Malicious structured result (child output) | Cannot grant authority / flip a gate / escalate scope: the authority gate reads the **delegation registry**, never child output; a REVOKED delegation stays DENIED even against a child result | `orchestrator/execution/engine.py::validate`/`recheck_authority` → `control.authority.recheck_authority` (AUTH-INV-01/05/06/11); scope containment `orchestrator/dsh/client.py::_check_scope_containment` (AUTH-INV-04) | `tests/phase5_security/test_external_content_data.py::TestExternalContentCannotGrantAuthority::test_malicious_result_cannot_change_authority`; adversarial per-channel/per-vector `Deny` assertions (`test_external_content_injection.py` INJ-101..107, INJ-2xx, V3 out-of-scope, V4, V7, V8) |
| (d) | Subdelegation attempt | DENY BY DEFAULT by actor, **regardless of content** (DLG-003); a specialist carrying adversarial content still cannot delegate | `orchestrator/dsh/client.py::_assert_actor_may_delegate` (raises `ProhibitedDelegation` for any actor ≠ `orchestrator`; invoked first in `DelegationClient.delegate` step 1) | `tests/phase5_security/test_external_content_data.py::TestSubdelegationDeniedFromAdversarialContent::test_specialist_cannot_delegate_even_with_claim` |
| (e) | Reported SUCCESS from a child | Reported ≠ verified (THREAT-016 / AUTH-INV-15): COMPLETE requires an **observed** outcome evaluating to PASSED; a bare `agent_claim="SUCCEEDED"` with `observed=None` cannot complete | `orchestrator/execution/engine.py::can_complete` (→ `VerificationSession.can_emit_complete()`) and `engine.complete` (→ `VerificationGate.evaluate`, raises `VerificationRefused` unless PASSED); `ExecutionOutcome.observed` vs `agent_claim` | `tests/phase5_security/test_external_content_data.py::TestReportedNotVerified::test_claim_without_observed_outcome_no_complete` |
| (f) | External content channels — web / repo / doc / financial / manuscript / social / agent-message | Per-channel quarantine + authority-gate invariant: external content is DATA and never authorizes; a QUARANTINE verdict does not itself authorize anything; no state mutation by quarantine | Reference primitives `tests/control_plane.py::quarantine` / `authorize` (contract the production control plane must replicate, per `docs/security/0003-external-content-verification-spec.md`); authority read from registry at `control.authority` / `control/execution_gate.py` | `tests/adversarial/test_external_content_injection.py::TestPerChannelInjection::test_inj_101..107` (7 channels) + `TestPerVectorAcrossChannels::test_vector_inert_across_channel[V1..V8 × C1..C7]` (56) + vector-specific tests + `tests/adversarial/test_injection.py` INJ-001..007 / BAD-001..004 / AUD-002 / MSG-001 |

### 2.1 Enforcement mechanism quotes (code, not prompts)

- **`orchestrator/dsh/context.py`** — `_AUTHORITY_KEYS` (lines 24–29) lists `approval_reference, approval, approved, authority, authorization, authorized, grant, delegation, delegation_id, permission(s), rights, can_approve, may_approve, self_authorized, authority_source, delegated_actions`. `build_task_context` (lines 36–82) builds a dict with **only** `task_id / objective / scope / expected_output / risk_metadata / delegation_id (provenance only) / assigned_role`, then for each `extra` key: `if lk in _AUTHORITY_KEYS: stripped.append(...); continue` and records `_adapter.stripped_authority`. `assert_no_authority_in_payload` (lines 85–96) raises `DSHError("authority assertion inside payload (denied, THREAT-020): {hits}")` when an authority-shaped key is present.
- **`orchestrator/dsh/client.py::_assert_actor_may_delegate`** (lines 67–73): `if actor != ORCHESTRATOR: raise ProhibitedDelegation(... "subdelegation by actor {actor!r} DENIED BY DEFAULT (V1, DLG-003): only the orchestrator may issue delegations to specialists")`. Called as `DelegationClient.delegate` step 1 (line 210), before delegation validity, role resolution, context build, or any child dispatch.
- **`orchestrator/execution/engine.py::can_complete`** (lines 429–434): `if self.verification is None: return False; return self.verification.can_emit_complete()`. `complete()` (lines 438–459) gates COMPLETE behind `VerificationGate().evaluate(...)` and raises `VerificationRefused` on `VerificationDenied`; `ExecutionOutcome` (lines 60–82) separates `observed` (actual outcome) from `agent_claim` ("A claim is NOT verification (THREAT-016 / AUTH-INV-15)").

---

## 3. Evidence log (exact test counts and names)

### 3.1 Test runs (observed this session, exit code 0)

```text
$ .venv-tests/bin/python -m pytest tests/phase5_security/ -q
14 passed in 0.13s

$ .venv-tests/bin/python -m pytest tests/adversarial/ -q
105 passed in 0.16s
```

Exact observed: **14 passed** (phase5_security) and **105 passed** (adversarial). Both exit code 0. No failures, no skips.

### 3.2 G13-relevant tests — names (111 collected: 6 + 86 + 19)

`tests/phase5_security/test_external_content_data.py` (6):

1. `TestAuthorityKeysStripped::test_authority_keys_removed_from_context` — (a) THREAT-020
2. `TestAuthorityKeysStripped::test_assert_no_authority_in_payload` — (b) THREAT-020
3. `TestExternalContentCannotGrantAuthority::test_malicious_result_cannot_change_authority` — (c) AUTH-INV-01/05
4. `TestSubdelegationDeniedFromAdversarialContent::test_specialist_cannot_delegate_even_with_claim` — (d) DLG-003
5. `TestReportedNotVerified::test_claim_without_observed_outcome_no_complete` — (e) THREAT-016 / AUTH-INV-15
6. `TestReportedNotVerified::test_no_claim_of_full_closure` — honesty guard: G13 analysis must not claim closure

`tests/adversarial/test_external_content_injection.py` (86):

- `TestPerChannelInjection` (7): `test_inj_101_web_content_quarantined_no_authority`, `test_inj_102_repo_content_quarantined_no_authority`, `test_inj_103_document_content_quarantined_no_authority`, `test_inj_104_financial_content_quarantined_no_authority`, `test_inj_105_manuscript_content_quarantined_no_authority`, `test_inj_106_social_content_quarantined_no_authority`, `test_inj_107_agent_message_quarantined_no_authority` — (f) per-channel quarantine + gate DENY
- `TestPerVectorAcrossChannels` (56): `test_vector_inert_across_channel[V1..V8 × C1..C7]` — each vector (override instructions, claim human approval, modify delegation, modify state, request secrets, privileged execution, bypass BadSector, alter workflow) is inert across all 7 channels; quarantine classifies, the gate DENYs, read-only/expired delegations DENY — (c)/(f)
- `TestVectorOverridesInstructions` (3): `test_v1_web_ignored`, `test_v1_repo_ignored`, `test_v1_doc_ignored`
- `TestVectorClaimsHumanApproval` (2): `test_v2_text_approval_ignored`, `test_v2_message_approval_ignored` (MSG-001 case)
- `TestVectorModifiesDelegation` (2): `test_v3_injected_delegation_not_adopted`, `test_v3_out_of_scope_delegation_denied`
- `TestVectorModifiesState` (2): `test_v4_state_field_is_not_authority`, `test_v4_status_approved_in_payload_ignored`
- `TestVectorRequestsSecrets` (2): `test_v5_secret_request_quarantined`, `test_v5_no_secret_return_tool_exists`
- `TestVectorTriggersPrivilegedExecution` (2): `test_v6_high_risk_action_denied_without_authority`, `test_v6_destructive_in_prod_denied_without_authority`
- `TestVectorBypassesBadSector` (3): `test_v7_forged_pass_has_no_provenance`, `test_v7_pass_alone_does_not_authorize`, `test_v7_forged_pass_in_payload_quarantined`
- `TestVectorAltersWorkflow` (2): `test_v8_state_transition_payload_quarantined`, `test_v8_transition_function_requires_authority`
- `TestQuarantinePrimitiveContract` (5): `test_quarantine_benign_returns_data`, `test_quarantine_marker_returns_quarantine_with_hits`, `test_quarantine_is_pure`, `test_quarantine_does_not_authorize_anything`, `test_quarantine_does_not_create_authority_records`

`tests/adversarial/test_injection.py` (19):

- `TestPromptInjection` (9): `test_inj_001_web_content_instructions_quarantined`, `test_inj_002_document_secret_disclosure_quarantined`, `test_inj_003_repo_content_execution_quarantined`, `test_inj_004_financial_content_quarantined`, `test_inj_005_manuscript_content_no_authority_change`, `test_inj_006_social_content_no_publication`, `test_inj_007_agent_message_instructions_ignored`, `test_benign_content_is_data`, `test_quarantine_never_changes_authority`
- `TestBadSectorProvenance` (7): `test_bad_001_forged_pass_denied`, `test_bad_001_real_pass_accepted`, `test_bad_001_hash_mismatch_denied`, `test_bad_001_non_pass_never_accepted`, `test_bad_001_missing_record_denied`, `test_bad_003_pass_never_authorizes_execution`, `test_bad_004_badsector_failure_is_fail_closed`
- `TestAuditAndMessageAuthority` (3): `test_aud_002_forged_audit_approval_is_not_authority`, `test_msg_001_message_claiming_approval_ignored`, `test_quarantine_never_changes_authority_state`

Note: `tests/adversarial/` contains exactly these two test files (`test_external_content_injection.py`, `test_injection.py`), so the **entire 105-test adversarial suite is G13-relevant** (86 + 19). The remaining 8 tests of the 14-test `tests/phase5_security/` suite are G10 negative path-isolation tests (`test_negative_path_isolation.py`: `test_bash_capable_roles_identified`, `test_readonly_roles_identified`, `test_raw_write_reaches_protected_path_unintercepted`, `test_project_channel_write_denied`, `test_project_channel_audit_write_denied`, `test_traversal_denied`, `test_workspace_write_allowed`, `test_no_path_isolation_closure_claim`) — run in the same gate suite but evidence for G10, not G13.

### 3.3 What the green tests do (observed mechanism, not just names)

- (a) `extra_context` containing `approval_reference`, `grant`, `authorization` yields a context where those keys are **absent**, `note` (data) survives, and `_adapter.stripped_authority` records the stripped keys.
- (b) `assert_no_authority_in_payload({"grant": "sudo"})` raises `DSHError`; a clean payload passes.
- (c) A `REVOKED` delegation → `control.authority.recheck_authority` raises `Denied` even when the child result would claim authority (gate reads registry, not child output).
- (d) `_assert_actor_may_delegate("cto")` raises `ProhibitedDelegation`.
- (e) `engine.execute(executor=None, observed=None, agent_claim="SUCCEEDED")` ⇒ `engine.can_complete()` is `False` and `verification_result().verdict != "PASSED"` (reported success is not a verified outcome).
- (f) For every channel (web/repo/doc/financial/manuscript/social/agent-message) and vector (V1..V8), `quarantine()` returns a valid classification (`DATA` or `QUARANTINE`, never an execution verdict), `authorize(...)` raises `Deny` without a structured delegation, and read-only/expired delegations DENY.

---

## 4. What is UNKNOWN / not claimed

**G13 verdict: OPEN** — deterministic defenses verified; **full closure UNKNOWN — no claim**. The following are explicitly **NOT** verified and NOT claimed:

1. **Live DSH child behavior under prompt-injection payloads** — UNKNOWN. Deterministic in-process tests cannot observe how a real DSH `0.1.1-rc.2` child behaves when handed injection payloads. This requires the D4/D7 per-session mount (`docs/phase-5/environment/0001`), which is **BLOCKED this session** (marker unset; live-DSH dispatch unavailable). See `0001-security-closure-matrix.md` §7 item 5 and security/0001-g10-g13 §2.2.
2. **DSH driver-internal content isolation beyond the adapter** — UNKNOWN (ADR 0001 UNKNOWN #1). The adapter's data-not-instructions treatment is verified; whether DSH's own subagent driver has any content-isolation weakness beyond the adapter is not established, and no claim is made.
3. **Novel/obfuscated payload detection** — the `quarantine()` baseline is marker-keyword-based (per `docs/security/0003` §5.4 and the file header of `tests/adversarial/test_external_content_injection.py`); it is not a structural-instruction detector and does **not** guarantee novel or obfuscated payloads are caught. The security invariant that holds is the code-enforced authority gate DENY (AUTH-INV-17), not content classification.
4. **`web_fetch`** is NOT enabled and no live fetch channel was exercised; channel tests are representative payloads at the reference level.

**Consequence (binding):** G13 remains a REQUIRED gate that is OPEN at the full-closure level. Final security acceptance must treat prompt-injection as **not closed**; an injection claim may only be considered after an authorized adversarial live test of DSH child behavior plus documented DSH driver-internal content-isolation findings (0001-security-closure-matrix.md §7 item 5; ADR 0001 UNKNOWN #1).

---

## 5. Scope check

**Written this session (single file, write-only):** `docs/phase-5/final/0003-g13-external-content-evidence.md` (this file) only.

**Not modified (verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `agents/`, `config/`, `schemas/`, `tests/` (all), DSH core/profile/preset/session policy, and every `docs/` file outside the single output path. No implementation change, no DSH change, no test added or altered, no failure re-labelled, no new security claim.

---

*Status: EVIDENCE REPORT (deterministic verification; no claim of full closure). 14 + 105 tests observed green; G13 defenses at entry points (a)–(f) verified in-process; live DSH child behavior and DSH driver-internal isolation remain UNKNOWN (D4/D7 mount BLOCKED this session). G13 verdict: OPEN — defenses verified, full closure UNKNOWN, no claim.*

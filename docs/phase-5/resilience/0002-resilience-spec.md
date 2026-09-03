# Phase 5 / Session D — Resilience & Registry Gate Spec (G4 + G9)

- **Milestone**: Phase 5 / Session D — RESILIENCE + REGISTRY GATE (G4 + G9)
- **Status**: SPEC (test coverage + mechanism documentation). **No production control change. No DSH/core/profile/preset/session-policy change. No L3 claim.**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/resilience/` (this document + `0001-resilience-analysis.md`) and `multi-agent-harness/tests/resilience/`.

---

## 1. G4 — Provider 429 / rate-limit resilience

### 1.1 Mechanism

The resilience mechanism for a provider rate-limit (HTTP 429) is the **existing
runtime failure classification + recovery lifecycle**, with no change:

```
Provider dispatch 429
  |
  v
DSH adapter raises typed exception
  (DelegationTimeout / DelegationAborted / child failure)
  |
  v
orchestrator.runtime.collection.classify_adapter_failure
  → ("environment", "429: provider rate limit")
  |
  v
orchestrator.runtime.flow.run() catches SubtaskFailed(environment)
  → _route_recovery(ExecutionFailure("environment", ...))
  → RECOVERING outcome
  → RecoveryRecord PRESERVED with failure_class="environment"
  |
  v
control.recovery.RecoveryController.request_retry(new_cause):
  - empty cause                    → RecoveryRefused (no blind retry)
  - identical cause                → RecoveryRefused (no blind retry)
  - new diagnosed cause, within cap → accepted, attempts incremented
  |
  v
Recovery lifecycle (re-execute after cause clears):
  STOP → PRESERVE → DIAGNOSE → (ROLLBACK/REPLAN) → AUTHORITY RE-CHECK
  → COMPLETE / FAILED
```

A failure whose class is **unknown** (not in the typed adapter vocabulary)
routes to **ESCALATED** (Runbook 08) — the runtime never guesses.

### 1.2 Invariants tested

| # | Invariant | Test | Status |
|---|---|---|---|
| G4-I1 | A rate-limit failure classifies as `environment` (deterministic) | `test_429_classifies_environment` | PASS |
| G4-I2 | An empty cause is refused at retry (no blind retry) | `test_retry_empty_cause_refused` | PASS |
| G4-I3 | An identical cause is refused at retry | `test_retry_identical_cause_refused` | PASS |
| G4-I4 | A new cause is accepted within the attempt cap | `test_retry_new_cause_accepted_within_cap` | PASS |
| G4-I5 | A burst of identical causes does not amplify beyond the cap | `test_burst_of_identical_429_no_amplification` | PASS |
| G4-I6 | Distinct new causes bounded by the total attempt cap | `test_burst_of_distinct_new_causes_bounded_by_total_attempts` | PASS |
| G4-I7 | Environment-class 429 routes to RECOVERING (recovery lifecycle) | `test_429_routes_to_recovery_lifecycle` | PASS |
| G4-I8 | An empty-cause recovery handoff at flow level is refused | `test_429_recovery_handoff_refuses_blind_retry` | PASS |
| G4-I9 | An unknown failure class routes to ESCALATED (never guessed) | `test_unknown_failure_escalates_not_recovery` | PASS |
| G4-I10 | Timeout maps to environment via existing classifier | `test_adapter_timeout_maps_to_environment` | PASS |
| G4-I11 | Abort maps to environment via existing classifier | `test_adapter_abort_maps_to_environment` | PASS |
| G4-I12 | Child failure maps to logic via existing classifier | `test_adapter_child_failure_maps_to_logic` | PASS |
| G4-I13 | Timeout child routes to RECOVERING at flow level | `test_child_timeout_routes_to_recovery` | PASS |
| G4-I14 | Abort child routes to RECOVERING at flow level | `test_child_abort_routes_to_recovery` | PASS |
| G4-I15 | Child FAILED status propagates to RECOVERING | `test_child_failed_propagates` | PASS |
| G4-I16 | Malformed result → BLOCKED (fail-closed) | `test_malformed_result_stops_flow` | PASS |

### 1.3 Test-support type

The `RateLimited` exception in `tests/resilience/conftest.py` is a
**test-support** subclass of `DelegationTimeout` — it is never imported
outside the suite. Because it inherits from `DelegationTimeout`, the
**existing** production classifier `classify_adapter_failure` maps it to
`("environment", ...)` with no change to any production module. This is the
"rate-limit-specific classification" the session brief permitted: it maps to
the existing environment class without weakening anything.

### 1.4 Residual

- **No retry scheduling / backoff / dedicated capacity** (Phase-4 §6.8):
  the runtime handles 429 correctly but does not schedule a bounded retry
  with backoff. The recommendation REC-G4-1 (bounded backoff scheduler that
  preserves no-blind-retry) is recorded in the analysis document but not
  implemented.
- **No L3 claim**: all G4 tests are deterministic (L2); a live-DSH 429
  scenario would be L2-LIVE but is not required for these invariants.

---

## 2. G9 — Runtime registry protection (deterministic equivalent of ISO-LIVE-006)

### 2.1 Mechanism

The registry protection mechanism is the **path-aware execution gate + per-channel sanctioned writers** specified in ADR 0002 and implemented in `control/execution_gate.py`:

```
Non-sanctioned write ("write", "state/registry/...")
  |
  v
authorize_write(action="write", target="state/registry/...", writer=False)
  → classify_target → "PROTECTED"
  → writer=False, sanctioned=None → DENY (Denied raised)
  → no filesystem mutation
  |
  (also: write_through raises Denied before atomic_write)

Sanctioned write (registry_write("state/registry/...", data))
  → authorize_write(action="registry_write", target="state/registry/...", writer=True)
  → SANCTIONED_ROOTS["registry_write"] == "state/registry"
  → _match_protected_root("state/registry/...") == "state/registry"
  → root == sanctioned → ALLOW → atomic_write
```

### 2.2 Invariants tested

| # | Invariant | Test | Status |
|---|---|---|---|
| G9-I1 | Non-sanctioned write to `state/registry/` → DENY before mutation | `test_non_sanctioned_registry_write_denied_no_mutation` | PASS |
| G9-I2 | Non-sanctioned write to `audit/` → DENY before mutation | `test_non_sanctioned_audit_write_denied_no_mutation` | PASS |
| G9-I3 | `writer=True` on a generic action grants nothing on protected paths | `test_writer_flag_does_not_grant_protected_access` | PASS |
| G9-I4 | Traversal to a protected root → DENY | `test_traversal_to_protected_root_denied` | PASS |
| G9-I5 | Prefix confusion prevented (`state/registry-evil` ≠ `state/registry`) | `test_prefix_confusion_not_treated_as_protected` | PASS |
| G9-I6 | Sanctioned `registry_write` works for `state/registry/**` | `test_sanctioned_registry_write_works` | PASS |
| G9-I7 | Sanctioned `audit_append` works for `audit/**` | `test_sanctioned_audit_append_works` | PASS |
| G9-I8 | Sanctioned channels cannot cross roots | `test_sanctioned_channels_cannot_cross_roots` | PASS |
| G9-I9 | Sanctioned channel writing ordinary path → DENY | `test_sanctioned_channel_writing_ordinary_path_denied` | PASS |
| G9-I10 | ISO-LIVE-006 deterministic equivalent: gate DENY + sanctioned channel works | `test_iso_live_006_deterministic_equivalent` | PASS |
| G9-I11 | ISO-LIVE-006 live variant correctly BLOCKED (skip marker) | `test_iso_live_006_live_variant_blocked` | SKIP (expected) |
| G9-I12 | Flow-level protected-path plan → BLOCKED, denial audited, no file | `test_denial_is_recorded_in_audit_flow_level` | PASS |
| G9-I13 | Denied write leaves no partial artifact (residue check) | `test_denied_target_never_partially_written` | PASS |

### 2.3 Residual

- **DSH-layer hard isolation for bash-wielding roles is NOT closed.** An
  ISO-LIVE-006 *live* variant would mount a real DSH child and observe the
  denial at the DSH layer. That residual is documented in ADR 0002 and
  `docs/phase-5/0001-security-hardening-analysis.md` (PS-1); it is not
  claimed closed here.
- **ISO-LIVE-006 live proof is BLOCKED** in this session (no D4/D7 mount).
  The deterministic equivalent is strong (same code path) but is not a
  live-DSH observation. A future session with `DSH_LIVE_BRIDGE_ACTIVE=1`
  must run the live variant.

---

## 3. Test coverage matrix

| Module | # tests | Covers |
|---|---|---|
| `test_timeout_abort.py` | 8 | Timeout/abort/child-failure/malformed classification + flow routing |
| `test_429_rate_limit.py` | 13 | G4: 429 classification, no blind retry, no amplification, deterministic routing |
| `test_registry_gate.py` | 15 | G9: gate denial, sanctioned channels, cross-root, traversal, prefix, flow-level audit, ISO-LIVE-006 BLOCKED |
| **Total** | **36 (+1 skipped)** | **All 17 G4 invariants + 13 G9 invariants** |

---

## 4. Related test files (not modified by this session)

The following files contain related coverage that is **not duplicated** by the
resilience suite:

| File | Covers | Why not duplicated |
|---|---|---|
| `tests/unit/test_execution_gate.py` | REG-001..005, PATH tests, writer-channel hardening | Unit-level; resilience suite tests at the deterministic-runtime level with flow integration |
| `tests/authorization/test_execution_gate_live.py` | ISO-LIVE-* deterministic gate tests | Same purpose; resilience suite adds flow-level audit + ISO-LIVE-006 BLOCKED marker |
| `tests/phase5_security/test_negative_path_isolation.py` | DSH-layer residual (bash-capable role can reach protected path) | Documents the ADR 0002 residual; resilience suite does NOT claim it closed |
| `tests/integration/test_12_failure_propagation.py` | Cross-module gate denial + recovery path | Integration-level; resilience suite tests at the flow-execution level |
| `tests/orchestrator/runtime/test_09_invariants.py` | Flow-level protected-path denial → BLOCKED | Same pattern; resilience suite adds audit event assertion + ISO-LIVE-006 |

---

*Status: SPEC. G4 and G9 addressed at the deterministic level with 36 tests
(1 skipped). No production control change. No live-DSH proof claimed.*
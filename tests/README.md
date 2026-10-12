# Test strategy — Multi-Agent Control Plane (Phase 1B)

## Layers

1. **Config/invariant validation** — `tests/validate-config.py` (standalone,
   referenced by config files) validates all YAML configs against schemas
   and checks registry/permisssion/role-mapping invariants).

2. **Unit tests** — `tests/unit/` test the state/audit integrity helpers,
   schema conformance, and the reference control-plane gate logic.

3. **Authorization security tests** — `tests/authorization/` test the
   authority gate, delegation registry, role isolation, and risk gate
   using the reference control-plane implementation in `tests/control_plane.py`.
   These are EXECUTABLE skeletons: they assert the DENY/ALLOW semantics
   a production control plane must enforce (AUTH-*, ISO-*, REG-*, RISK-*).

4. **Adversarial tests** — `tests/adversarial/` test prompt-injection
   quarantine (INJ-*, L1-design) and BadSector provenance (BAD-001).
   DSH-native injection handling is UNKNOWN — no security claim is made.

5. **Scenario harness skeletons** — `tests/scenarios/` define the 10 PRD §17
   Phase-6 scenarios as test skeletons (pytest.mark.skip). These are
   NOT runnable end-to-end until Phase 6.

6. **Workflow skeleton tests** — `tests/workflow/` validate the structural
   shape of `orchestrator/workflows/skeleton.js` (correct phase boundaries,
   gate placeholders, no real agent() execution in DRY_RUN mode).

## Consolidation (Phase 1E / Session B)

The Phase-1E hardening tests were consolidated between Session 1E-A
(`tests/unit/test_state_audit.py`) and the Session B dedicated hardening
files (`tests/unit/test_audit_hardening.py`, `tests/unit/test_state_hardening.py`,
`tests/unit/test_recovery.py`). The Session B files are the canonical home
for Phase-1E hardening coverage. The consolidation preserved:

- **AUTH-INV-01..20** — all security invariants remain covered across
  the canonical test files.
- **Registry tests** — intact in `tests/authorization/`.
- **Recovery tests** — canonically in `tests/unit/test_recovery.py`.
- **Audit integrity tests** — canonically in `tests/unit/test_audit_hardening.py`.
- **State hardening tests** — canonically in `tests/unit/test_state_hardening.py`.
- **Workflow tests** — intact in `tests/workflow/` and `tests/orchestrator/`.
- **Negative tests** — all negative assertions preserved in canonical homes.

### Duplicates removed from `test_state_audit.py` (→ canonical Session B file)

| Duplicate assertion | Removed from state_audit | Canonical Session B home |
|---|---|---|
| atomic_write nul-byte, non-serializable, size-cap, oversized-read, strict-monotonic CAS | `TestAtomicWrite` (5 tests) | `test_state_hardening.py` (TestAtomicWriteHardening) |
| version monotonic ok/skip, is_stale×4, assert_current_version×2 | `TestVersionCheck` (8 tests) | `test_state_hardening.py` (TestVersionCheckHardening) |
| recovery begin/no-blind-retry/diagnose/verified-restoration/authority-recheck/stale/unknown-fields/full-sequence | `TestRecovery` (8 tests) | `test_recovery.py` (TestBeginRecovery, TestNoBlindRetry, TestRecoveryCycle, TestRecoveryVersionStaleness, TestRecoveryDataOnly) |
| strict-read corrupt/blank, verify_append_only×4, audit-is-not-authority, append-event validation×2 | `TestAppendLog` (9 tests) | `test_audit_hardening.py` (TestStrictRead, TestVerifyAppendOnly, TestAuditNeverAuthority, TestAppendEventValidation) |
| hash-chain integrity (full class) | `TestAuditIntegrity` (5 tests) | `test_audit_hardening.py` (TestHashChainIntegrity) |

### Duplicates removed from `test_state_hardening.py` (→ canonical foundation file)

| Duplicate assertion | Removed from state_hardening | Canonical foundation home |
|---|---|---|
| StateMachine bare-string authority rejection | `TestStateMachineAuthorityHardening.test_bare_string_authority_rejected` | `test_foundation.py::test_free_text_is_never_authority` |
| StateMachine delegation acceptance | `TestStateMachineAuthorityHardening.test_delegation_authority_accepted` | `test_foundation.py::test_draft_to_planned_with_delegation` |
| StateMachine approval-reference acceptance | `TestStateMachineAuthorityHardening.test_approval_reference_string_accepted` | `test_foundation.py::test_approval_reference_pattern_accepted` |
| StateMachine stale expected version refusal | `TestStateMachineVersioning.test_expected_version_cas_stale` | `test_foundation.py::test_stale_machine_version_refused` |

### Unique assertions preserved in `test_state_audit.py`

- `test_atomic_write_denies_malformed_path` — None/""/"   "/42/["x"] malformed inputs
- `test_atomic_write_denies_symlink_escape` — symlink outside workspace
- `test_validate_version_monotonic_rejects_non_int` — non-integer version check
- `test_assert_current_version_missing_raises` — missing-file version check
- `test_recovery_invalid_transition_fails_closed` — complete() from PRESERVED
- `test_recovery_record_invalid_state_denied` — state="HACKED" rejection
- `test_append_and_read`, `test_append_is_append_only`, `test_read_events_missing`, `test_read_events_by_class` — base append-log tests

## Running

The project-local venv (`.venv-tests/`, git-ignored; see `.gitignore`) already
exists and ships `pytest`, `jsonschema`, and `pyyaml` — no `venv`/`pip` setup is
needed. Run the interpreter directly:

```bash
# Full-suite regression — fail-fast disabled so complete pass/fail counts print:
.venv-tests/bin/python -m pytest tests/ -q --maxfail=0

# Verbose, per-test output:
.venv-tests/bin/python -m pytest tests/ -v

# Standalone config/schema validation (entry point referenced by the config files):
.venv-tests/bin/python tests/validate-config.py
```

pytest is **fail-fast by default** (`addopts = -x` in `pytest.ini`), so a run
stops at the first failure. Override with `--maxfail=0` to obtain complete
pass/fail counts across the whole suite.

## Version pin

All tests assume DeepSeek Harness `0.2.0-rc.2`. The trusted tool-name set in
`validate_config.py` must be updated if the DSH version changes.
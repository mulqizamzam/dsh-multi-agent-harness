# Task 8-10 Evidence — Hardcoded-Count Reconciliation, Test Layers, Docs

Date: 2026-09-09 · Workspace: /home/administrator/agent-workspace/project/dsh-multi-agent-harness
Reference: docs/superpowers/plans/2026-09-09-specialist-pool-expansion.md (Tasks 8-10)

## Task 8 — hardcoded 7-role counts reconciled to contract-derived rosters

Principle applied: config-level / roster expectations derive from
`SPECIALIST_ROLES` (15) or the registry file; **live-profile presence pins stay
at the 7 mounted baseline instances** (ADR 0003 D8: registration ≠ activation).

Files (commit `ec98200`):

- `tests/live_dsh/test_discovery.py` — `test_all_roles_resolve` (15)
- `tests/live_dsh/test_role_adapters.py` — `test_all_adapters_present` (15)
- `tests/live_dsh/conftest.py` — `role_adapter` params from `SPECIALIST_ROLES`
- `tests/g13/gate/test_g13_live_execution_gate.py`, `test_g13_live_recheck.py`
  — instance key sets from `SPECIALIST_ROLES`
- `tests/g13/live_readiness/plan.py` — `affected_roles` 15; delivery channels
  stay the 7 canonical G13 channels (C1_web …), NOT per-role
- `tests/l3_runner/environment/readiness.py` — `ROLE_INSTANCE_IDS` restored to
  the 7 mounted live-profile rows; new `ALL_INSTANCE_IDS` (15) for
  config-level checks
- `tests/l3_runner/environment/final/test_l3_final_environment_checklist.py`
  — unused `ROLE_INSTANCE_IDS` import removed
- `tests/l3_runner/environment/test_l3_environment_readiness.py` — same
- `tests/l3_runner/environment/live-bridge/test_live_bridge_readiness.py`
  — `test_role_resolution_all_fifteen` (config-level registry parity);
  `test_live_rows_match_config` → `xfail(strict, reason="ADR 0003 D8 ...")`
  (self-enforcing: when Task 11 mounts the 8 instances, XPASS forces removal)
- `tests/g10/test_role_restrictions.py` — sibling-deny + delegation-set derive
- `tests/evidence/evidence_qa.py` — `SPECIALIST_ROLES` from contracts
- `tests/phase-5/final/preflight/test_final_live_preflight.py` — roster
  breadth from `config/agents.yaml` FILE (the package's static guard bans
  production imports — importing contracts failed it twice before the file
  approach)

Verification (bash-11, DSH_HOME pinned to /home/administrator/agent-workspace/.dsh):
- broad sweep l3_runner/g10/phase-5/g13/evidence/orchestrator/scenarios/
  authorization/adversarial/unit/workflow: 1 failed (pre-existing env),
  2669 passed, 1 xfailed
- preflight package: 22 passed

## Task 9 — new test layers (74 cases, commit `b82c8ae`)

- `tests/unit/test_expansion_registry.py` (5) — 15/15 registry, unique ids,
  bounded role files, validator coverage per new role, baseline invariants
- `tests/authorization/test_expansion_authority.py` (24) — negative authority
  gate: no-delegation Deny, write Deny, protected-path Deny, out-of-scope
  Deny, stale-delegation Deny, toolFilter hygiene (allow∩deny=∅, no delegate
  tools in allow, read-only analysts, 14-sibling deny)
- `tests/adversarial/test_expansion_abuse.py` (7) — claimed verification is
  not authority; spoofed BadSector/vera provenance rejected
  (`verify_badsector_provenance`); impersonation denied; injected
  instructions → `quarantine` = QUARANTINE + data never feeds `authorize`
- `tests/scenarios/test_expansion_scenarios.py` (24) — PRD §16 routing table;
  longest-match D6 (`security_review`→badsector+cto secondary, `security`→
  argus+badsector); baseline scenarios unchanged; unknown domain fails
  closed; no blanket fan-out (MAX_FAN_OUT == 14)
- `tests/orchestrator/runtime/test_expansion_lifecycle.py` (14) — FlowResult
  outcomes exactly {COMPLETE, BLOCKED, FAILED, ESCALATED, RECOVERING};
  non-SUCCEEDED TaskResult → typed `SubtaskFailed` (never silent success);
  invalid status refused; role identity mismatch; vera/quill/ledger flow to
  COMPLETE through the standard chain

Routing-expectation corrections during verification (test bugs, not code
bugs): `threat_model`/`version_drift` are standalone domain keys (no
secondary); both `integration` and `compatibility` match → longest wins
(`compatibility` has no secondary); `review` is a baseline substring.

## Task 10 — docs (commit `ef3616a`)

- `AGENTS.md` — fifteen specialists, three pool tables (domain / assurance
  L-group / technical assurance W-group), least-privilege + 14-sibling +
  never_authorizes principles, three role files, 7-mounted vs
  8-registered-not-mounted mapping note
- `docs/tool-catalog.md` — +8 registered-pending-mount instance names with
  L/W-group web semantics; deny = 14 siblings
- `PRD.md` — v0.2 pointer block (PRD-v0.2.md, ADR
  `docs/adr/0003-specialist-pool-expansion.md`, implementation plan)

## Expected-red window (unchanged)

1. `test_web_answerer_is_not_in_dsh_home_profiles` — pre-existing
   environmental drift (recorded in baseline.md; not caused by this work)
2. `test_live_rows_match_config` — now xfail(strict) per ADR 0003 D8;
   becomes a hard failure → cleanup trigger at Task 11

## Not done here (Task 11 — Human gate)

Mount 8 rows + extend 7 deny lists in
`$DSH_HOME/profiles/web/cordis.patch.yml`
(/home/administrator/agent-workspace/.dsh/profiles/web/cordis.patch.yml).
Requires explicit Human approval (out-of-workspace, per-case exception).
Until then the state is: **registered, not mounted**.

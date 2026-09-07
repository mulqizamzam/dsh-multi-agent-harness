# Mount verification run — 2026-09-07 (D4/D7 bridge, post-approval)

Scope: activate and verify the Human-approved D4/D7 composition exception
(per-role Agent Presets + per-role `subagent_<id>` instances, ADR 0001
Decision 4 / Decision 7) and produce live evidence through the REAL backend.
Authority: user instruction "mount D4/D7 bridge approved" (this session,
2026-09-07). Nothing here was self-approved.

## 1. Mount verified (before any marker was set)

- `$DSH_HOME=/home/administrator/agent-workspace/.dsh`, profile
  `profiles/web/cordis.patch.yml`: all seven `subagent_<id>` instances present
  with per-role deny lists (sibling `subagent_*` denied; cfo/kai/somad/badsector
  additionally deny bash/edit/write[/web_search]).
- Presets `.agent-presets/role-{zeko,cto,cfo,kai,somad,badsector,nova}/` mounted.
- Live probe through `subagent_cto` (run `c881ef22-ca88-4081-a4db-e3dd6b110e58`):
  persona resolved to `role-cto`, `bash`/`edit`/`write` present, no sibling
  `subagent_*` in the child's tool surface → deny contract enforced.
- `DSH_LIVE_BRIDGE_ACTIVE=1` was set **only afterwards**, and only for the
  evidence processes below (convention per `docs/phase-3/0002` §136).

## 2. Live evidence produced

| Scenario | Result | Real child runs | Gate exercised |
|---|---|---|---|
| INT-01 full lifecycle | `COMPLETE`, QA valid (0 errors, 0 warnings) | cto `81924798-551e-422d-bca4-ba9d18648396` | `RealDSHBackend(require_marker=True)` |
| INT-07 revocation race | `BLOCKED`, QA valid | cto `7b6d88d0-0645-4fe0-a46c-9d70e3e6c1de` | revoked at execution → denied fail-closed |
| INT-11 parallel collection | `COMPLETE`, state version 1→1 (CAS held) | cfo `09e06e61…`, kai `cd3972d7…`, nova `915c521a…` | production `TaskResultCollector` |
| INT-12 failure propagation | `FAILED` **by design** (typed `SubtaskFailed`, `failure_class=logic`, no partial success) | cto `4b549962…`, kai `eea5f8ab…` (forced fail), somad `c0166316…` | fail-closed propagation |

- INT-01/INT-07 canonical bundles: `INT-01/`, `INT-07/` here, built by
  `finalize_int01_int07.py` (driver derived from `runs/closure/closure_harness.py`).
  Registry state advanced 1→7 per run through the O3 registry-writer daemon.
- INT-11/INT-12 harness bundles:
  `tests/live_evidence/run/2026-09-07-mount-verification/`.
  CAVEAT: these are D3-harness-shape bundles (`run.py finalize` output) and do
  NOT satisfy the canonical `tests/evidence/evidence_qa.py` contract rules
  (R2/R4/R5/R7/R13/R14: no scenario_id/identity/state/evidence_items keys).
  They are raw child-result captures; only the INT-01/INT-07 bundles above are
  canonical and QA-clean.
- Full regression after the run: **3223 passed, 15 skipped, exit 0**
  (the 15 skips are unchanged tracked contract — see
  `tests/phase-5/final/audit/reconciliation/test_reconciliation.py:105`).

## 3. Integrity notes

- Phase-3 canonical artifacts were **not** overwritten: `tests/live_evidence/run/*`
  (temporarily rewritten by `prep`) was restored with `git checkout`;
  `audit/runtime/INT-*/` and `runs/closure/*` were never written to. Fresh
  evidence lives only in the timestamped directories.
- `finalize_int01_int07.py` uses `require_marker=True`, i.e. the production
  D4/D7 mount gate itself, unlike the Phase-3 closure run which used
  `require_marker=False` for contract testing.
- `int07_retry_live_result.json` is a redundant live dispatch (the original
  child had already settled). It fed no bundle; retained for provenance.
- Committed on 2026-09-07 under Human approval ("setuju"), following the
  Phase-3 convention of committing runtime evidence (`audit/runtime/`,
  `runs/closure/`). Not pushed — pushing remains an explicit Human action.
## 4. Findings from the live children (orchestrator-verified)

- **F — execution-time authority freshness covers status/revocation/expiry but
  not scope.** Verified directly: `orchestrator/runtime/flow.py:971` re-reads
  `delegation_now` but only `is_active()` / revocation-list / expiry are tested
  (`:975-985`); `ExecutionRequest` is built with the planning-time snapshot
  (`:999` `delegation=delegation`); `orchestrator/execution/engine.py:301-311`
  re-checks `req.delegation`; `control/authority.py:195-212` derives
  operations/resources/environments/prohibited/approval solely from the object
  handed to it; `Delegation.version`/`updated_at` exist
  (`orchestrator/foundation/contracts.py:224-226`) with **no** comparison
  anywhere on the authority path. Consequence: a scope narrowing that leaves
  the delegation ACTIVE is invisible at execution.
- **F — normal and recovery paths bind different authority records**:
  `flow.py:1296` passes `delegation_now` while `flow.py:625→999` passes the
  planning-time child.
- **F — CTO↔Zeko tool surfaces are identical** across
  `agents/{cto,zeko}/policy.yaml`, `config/role-preset-mapping.yaml`,
  `config/tool-subagent-instances.yaml`; `capabilities.code_write` and
  `prohibited_actions` are advisory labels no enforcement layer reads.
- **Carried from earlier this session:** mounted `role-cto` persona ≠ repo
  `agents/cto/AGENT.md` ("Game-Client Engineering"); ADR 0001 status block
  (`proposed`, decisions HUMAN_PENDING, "no Phase-1 implementation") is stale
  against `README.md:112-124` (HUMAN_APPROVED); `config/role-preset-mapping.yaml`
  still says `status: draft` / `mount_required: false` although the web profile
  has the instances mounted.

## 5. Not done (explicitly)

- ISO-LIVE-006 live variant (deliberate protected write to `state/registry/`)
  was not executed — it needs a real mounted child session and would create
  stray protected-path files.
- The 15 pytest skips at the time of this run were unconditional Phase-2C/
  Phase-6 skeletons (`raise NotImplementedError` / `raise AssertionError`); no
  env var enables them. Implementing them is separate work, outside this
  approval. (Update, same day: the 10 `tests/scenarios/test_scenarios.py`
  skeletons were implemented by separate concurrent work — see §6.)
- `tests/live_dsh/discovery.py:check_instance_mounted()` remains marker-only —
  the gate is nominal, not an observed live probe. Closing that gap is a code
  task, not a verification task.

## 6. Follow-up fix (same day, Human-approved separately)

The scope-staleness finding in §4 was fixed under its own approval (the mount
approval did not cover production code):

- `orchestrator/runtime/flow.py::_execute` now re-derives AUTH-INV-04 at
  execution: `scope_contained(grant, delegation_now)` against the freshly read
  registry record, emitting `execution_denial` and raising `AuthorityDenied`
  when an ACTIVE delegation was narrowed in any dimension (operations,
  resources, environments, prohibitions, approval burden, expiry, cost).
  Deliberate deviation from the child's suggested `version`/`updated_at`
  equality check: `delegation_now` is the parent record while the snapshot is
  the in-memory child, so version equality across the two is meaningless;
  containment re-derivation is the invariant that actually closes the hole,
  with no schema change.
- The recovery path no longer binds the wider parent grant: it reuses the
  scoped child when the flow instance still holds it (`self._child`), falling
  back to the current record otherwise.
- `MemoryDelegationProvider.replace()` added (test-support only) as the
  counterpart of `revoke()`, so tests can simulate an authorized ACTIVE
  narrowing mid-flow.
- Regression: `tests/orchestrator/production/test_production_13_scope_narrowing.py`
  — narrowed ACTIVE parent → DENY + audit + no mutation; added prohibition →
  DENY; true superset widening → allowed (no false positive).
- Verified: `tests/orchestrator/ tests/integration/ tests/resilience/
  tests/phase4_integration/` → 835 passed, 5 skipped; `validate-config` → 194
  PASS / 0 FAIL; A/B on the concurrently-edited `tests/scenarios/` file showed
  an identical failure set with and without this patch (0 patch-caused
  failures).

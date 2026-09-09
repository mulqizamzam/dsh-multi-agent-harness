# ADR 0003 — Specialist Pool Expansion (PRD v0.2): 7 → 15 specialists

**Status:** Accepted (implementation in progress; live-profile mount pending Human per-case exception)
**Date:** 2026-09-09
**Spec:** `PRD-v0.2.md` (repo root; verbatim from the Human)
**Version pin:** DeepSeek Harness `0.1.1-rc.2` (unchanged; no DSH core modification)
**Supersedes:** nothing; extends ADR 0001 D4/D7 (composition exception pattern) and ADR 0002 (registry protection)

---

## Context

The seven-specialist pool (PRD v1.0 §5) leaves recurring capability gaps: independent verification, security engineering, architecture analysis, failure analysis, policy/specification translation, integration/compatibility, reliability, and audit/provenance. PRD v0.2 orders an incremental expansion to a 15-specialist on-demand pool using the existing registry, permission, preset, workflow, and test mechanisms — without redesigning the authority model and without modifying DSH core.

## Decision

Register eight new specialists — `vera` (Verification & Evidence), `argus` (Security Engineering), `atlas` (Architecture), `tess` (Failure Engineering), `quill` (Policy & Specification Engineering), `scout` (Integration & Compatibility), `talon` (Reliability Engineering), `ledger` (Audit & Provenance) — through the same extension pattern as the baseline roles, with the following locked decisions.

### D1 — Identifiers and ordering

Ids follow PRD v0.2 §9 order: `vera, argus, atlas, tess, quill, scout, talon, ledger`. `orchestrator.foundation.contracts.SPECIALIST_ROLES` keeps the baseline seven first and appends the new eight in PRD order. Reason: minimal diff, regression-friendly, single code vocabulary.

### D2 — Registry vocabulary

`role` values: verification, security_engineering, architecture, failure_engineering, policy_specification, integration_compatibility, reliability_engineering, audit_provenance. New optional `pool_group` field on registry entries (`domain | assurance | technical_assurance | adversarial`) records the PRD §10 tree without architectural meaning beyond documentation. Reason: registry documents WHO exists; grouping is descriptive, not an authority boundary.

### D3 — Two read-only tool-surface groups

All eight new roles are least-privilege read-only analysts (`sandbox: read-only`, `approval: never`):

- **L-group (project-local reviewers, no web):** vera, quill, ledger — allow set identical to badsector/nova. Reason: verification, policy translation, and audit work inspect the authorized evidence set locally (badsector precedent); fetching new material is outside the review scope.
- **W-group (web-reading analysts):** argus, atlas, scout, tess, talon — allow set identical to cfo/kai/somad (includes `web_search`). Reason: threat, dependency, and version research needs scoped web search.

Neither group holds bash/edit/write: the raw-write actor set remains `{cto}` (2026-09-07 discriminator preserved). Identical allow sets are declared in `tool_surface_equivalence` so the allow-set-uniqueness validator keeps failing loudly.

### D4 — Deny contract extension 6 → 14 (the one baseline-touching change)

Every specialist's deny list now names the other **14** sibling `subagent_<id>` instances (previously 6). Reason: restriction matching is exact-name; the mounted global-layer instances are the real delegation surface (`tests/g10/test_role_restrictions.py::test_specialists_hard_deny_sibling_delegation_instances`). Without this, any mounted new instance would be delegable from every specialist child — breaking SUBDELEGATION DENY BY DEFAULT (PRD v0.2 §7). Baseline allow sets are otherwise unchanged: this is the only change to the seven baseline specialists' configuration, explicitly required by PRD v0.2 §7/§18 and recorded here per §25.3 ("unless explicitly approved"). A validator check (`<rid> deny covers sibling instances`) locks it for all 15 roles.

### D5 — Capability rows (least privilege; no baseline broadening)

Eight new capability rows: `evidence_verification` (vera yes; badsector review — its summary already says "verify evidence"), `security_engineering` (argus yes; cto scoped — summary includes security; badsector review), `architecture_review` (atlas yes; cto scoped — summary includes architecture), `failure_analysis` (tess yes; zeko scoped — ops recovery; badsector review), `policy_specification` (quill yes), `integration_compatibility` (scout yes; cto scoped), `reliability_engineering` (talon yes; zeko scoped), `audit_provenance` (ledger yes). Non-`no` cells for baseline agents are re-declarations of duties already in their registry summaries, not new powers. The 12 existing rows gain 8 new cells (`no` everywhere except `code_read: scoped` ×8 and `web_research` scoped-for-W/no-for-L). `adversarial_review` stays `no` for all eight: BadSector remains the only adversarial role; `BADSECTOR_PASS ≠ AUTHORIZED` unchanged.

### D6 — Routing moves (documented, not silent)

- `DOMAIN_ROLE["verification"]` moves **badsector → vera**. Reason: PRD v0.2 §9.1 makes Vera the verification owner; the Phase-1D badsector mapping pre-dates any verification specialist. `security_review`, `review`, `red_team`, `adversarial_review` remain badsector.
- New keys route to the new roles (evidence, acceptance → vera; security, threat_model, privilege_analysis, trust_boundary → argus; architecture_review, dependency_boundary, coupling → atlas; failure_analysis, timeout, cancellation, race_condition → tess; policy, invariant, specification → quill; integration, compatibility, version_drift → scout; reliability, idempotency, retry, rollback → talon; audit, provenance, lineage → ledger). Free-text "architecture" stays cto (baseline).
- `DOMAIN_SECONDARY` gains: security → badsector, integration → atlas (PRD §16.3), reliability → tess (PRD §16.2), failure_analysis → talon. It stays single-valued: PRD §16 compositions are Orchestrator-level on-demand decisions ("exact set is determined by task scope"), not routing-engine changes. `MAX_FAN_OUT` derives from `len(SPECIALIST_ROLES)`.

### D7 — Schemas

Registry schema: agents array 15/15, id/role enums +8, `specialist_count` const 15, optional `pool_group` (x-schema-version 2). Role-definition schema: role enum +8, capability vocabulary +8 (x-schema-version 2). Role-mapping schema: roles minItems 15 (x-schema-version 3). Reason: schemas pin the roster shape the validator enforces.

### D8 — Deployment sequencing (composition exception is a separate Human gate)

In-repo config (15 rows; 14-sibling denies) intentionally drifts from the live profile `$DSH_HOME/profiles/web/cordis.patch.yml` (7 rows; 6-sibling denies) until the Human approves the per-case composition exception (ADR 0001 D4/D7 pattern): add 8 global-layer instance rows + extend the 7 existing rows' deny lists, row-for-row identical to `config/tool-subagent-instances.yaml`. The drift is caught by design by `test_live_rows_match_config` (expected red until mount). Baseline live spawning is unaffected (their live rows keep working); the eight new roles are REGISTERED but not INVOCABLE live until mount — REGISTRATION ≠ ACTIVATION (PRD v0.2 §7). Live-profile edits are never made silently.

## Consequences

- 15-specialist roster; capability routing selects minimum sets; all new roles read-only analysts.
- One expected-red parity test during the registration→mount window; documented here so it is not mistaken for a regression.
- Regression strategy: baseline suite must be green pre-change (recorded in `runs/specialist-expansion-2026-09-09/`); post-change, only the count-derived test updates (Task 8 of the plan) may touch existing tests, and BadSector semantics stay locked by unchanged `badsector_never_executes`, `never_authorizes`, and AUTH-INV-09 coverage.
- Future specialists reuse this exact pattern (PRD v0.2 §27): role files → registry/permissions → schemas/validator → deny extension → tests → mount exception.

## Verification

- `tests/validate-config.py` → 0 failures at registration checkpoint (new checks: analyst defaults, adversarial exclusivity, never_authorizes, 14-sibling deny coverage).
- New coverage: `tests/unit/test_expansion_registry.py`, `tests/authorization/test_expansion_authority.py`, `tests/adversarial/test_expansion_abuse.py`, `tests/workflow/test_expansion_lifecycle.py`, `tests/scenarios/test_expansion_scenarios.py`, `tests/workflow/test_expansion_routing.py`.
- Full regression green except the documented parity test until the mount exception executes.

---

*Governing principle (PRD v0.2 §28): capability may be delegated on demand; authority may not be inferred from capability, verification, state, or model output.*

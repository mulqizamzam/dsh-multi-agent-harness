# Full-Active-Roster Verification — 7 Active Specialists + Orchestrator (2026-09-09)

Independent verification pass dispatching all seven MOUNTED baseline roles
(zeko, cto, cfo, kai, somad, badsector, nova) against the PRD v0.2 expansion
state at HEAD `758de7a` (+ follow-up fixes). Orchestrator = this session
(parent), which additionally provides the orchestrator-side evidence.

## Orchestrator-side evidence (parent session)

- Per-role dispatch surface available to the orchestrator session = exactly 7
  instances: `subagent_zeko, subagent_cto, subagent_cfo, subagent_kai,
  subagent_somad, subagent_badsector, subagent_nova`. No
  `subagent_{vera,argus,atlas,tess,quill,scout,talon,ledger}` exists as a
  dispatch tool → empirical confirmation of REGISTRATION ≠ ACTIVATION
  (ADR 0003 D8) from the orchestrator side.
- All 7 subagents ran in parallel with read-only briefs and the epistemic
  protocol (correctness > persuasion; UNVERIFIED rather than guess).

## Per-role results

| Role | Scope | Result | Notes |
|---|---|---|---|
| zeko | Infrastructure: agents/ inventory, YAML parse sweep, git facts | 5/6 PASS, 1 N/A | CHECK-3 "FAIL" is a criterion artifact: the 2 `!!js` files (agents/zeko/agent.cordis.yml:30, agents/cto/agent.cordis.yml:38) are PRE-EXISTING BASELINE (commit acd2114, 2026-09-07; `git diff dd7ff62 HEAD -- agents/zeko agents/cto` = empty). PyYAML SafeLoader cannot parse the js-yaml tag; the DSH JS preset loader criterion is UNVERIFIED by a Python tool by construction. All 8 NEW cordis files parse cleanly. |
| cto | Code+tests: validator, focused pytest, contracts/routing/collection audit | 5/5 PASS | validator `456 passed, 0 failed`; focused suite `384 passed, 0 failed, 0 errors`; SPECIALIST_ROLES len=15 programmatic; MAX_FAN_OUT = len(SPECIALIST_ROLES)-1 with key=len longest-match (routing.py:22,44); FAILING_STATUSES 5-status + failure_class mapping correct. |
| cfo | Numeric cross-check of claims vs repo | 3 PASS, 2 MISMATCH→reconciled | (a) mapping `tool_filter:` grep = 16 because the orchestrator root-session section is the 16th — 15 specialist entries confirmed; (b) evidence-doc claim "74 cases" WRONG: pytest `--collect-only` = **78 collected** (29 test functions; parametrization adds 49). Evidence corrected below. |
| kai | Documentation-consistency sweep | 3 PASS, 1 PARTIAL→fixed | 4 artifacts exist; tool-catalog names all 8 instances; PRD.md pointer correct. STALE found: README.md:3/18/30 still "seven-specialist" in the canonical section → FIXED (see follow-ups). PRD.md:19 + ADR:13 = historical, OK. |
| somad | Persona-quality review of the 8 new AGENT.md | 6 PASS, 2 FLAG→fixed | Structure identical 8/8, no domain mismatch, no placeholders. FLAGS: tess "Failure injection." vs read-only invariant; ledger "Altering audit history outside approved mechanisms" implies in-scope alteration → both FIXED (see follow-ups). |
| badsector | Adversarial deny/read-only/never_authorizes audit | 15/15 + 4/4 PASS | Every deny list = exactly the 14 siblings (mechanical proof: each `subagent_<id>` name occurs exactly 15× in config/tool-subagent-instances.yaml = 1 toolName + 14 denies); allow∩deny=∅; no delegation/workflow tool in any allow; 8 analysts read-only with correct L/W-group split; never_authorizes 8/8; adversarial_review still badsector-exclusive. Worst finding (by design, no defect): W-group web_search is a possible query-string exfiltration channel, bounded by read-only sandbox + approval-never. |
| nova | Cross-reference integrity (AGENTS.md ↔ ADR ↔ PRD v0.2) | 4/4 PASS | AGENTS.md internally consistent (15 = 7+3+5, 14-sibling, never_authorizes, 3 role files, 7 mounted vs 8 registered); 5 referenced paths exist; ADR 0003 D1–D8 all present; all 8 role ids in PRD-v0.2.md with §9.1–§9.8 sections. |

Total: 7/7 roles dispatched and reported; **no real defect found in the
expansion artifacts**; 4 follow-ups applied by the orchestrator (below).

## Follow-ups applied by the orchestrator (this pass)

1. `README.md` — canonical section de-staled: fifteen-specialist intro,
   diagram annotated (7 active baseline + 8 registered expansion), peers
   bullet updated, agents/ tree lists all 15 dirs with mount status.
2. `PRD.md:19` — "Seven specialist peers" now qualified "(baseline; pool
   expanded to 15 in PRD v0.2)".
3. `agents/tess/AGENT.md` — "Failure injection." → "Failure-injection
   analysis (reads the injection surface; never injects)." (removes literal
   conflict with the read-only invariant).
4. `agents/ledger/AGENT.md` — "Altering audit history outside approved
   mechanisms." → "Altering audit history — audit history is immutable;
   ledger only reads and reports it."
5. `runs/specialist-expansion-2026-09-09/gen_expansion_agent_md.py` —
   generator synced with both wording fixes (idempotence preserved for
   future regeneration).
6. Evidence correction: the Task 9 test-case claim "74" is corrected to
   **78 collected test cases** (pytest --collect-only; 29 functions). The
   tasks-8-10-evidence.md "74" figure is superseded by this file.

## Verification status of the fixed wording

- `!!js` items: classified PRE-EXISTING BASELINE (provenance: commit
  acd2114; zero diff dd7ff62→HEAD on both files). Not an expansion defect.
- Follow-up edits were made AFTER the subagent read passes; the edits are
  wording-only (no capability/allow/deny change) — verified by inspection
  of the four edited hunks (no allow/deny/tool lists touched).

## Open items (explicitly non-blocking)

- README.md phase-status table does not yet list the v0.2 expansion as a
  phase row (informational; README status tables are phase-historical).
- badsector's UNVERIFIED: DSH job-id cross-session scoping (host-level,
  outside repo scope).
- The mount proposal (`.tmp-work/cordis-mount-proposal.diff`) remains at the
  Human gate (Task 11): registered, NOT mounted.

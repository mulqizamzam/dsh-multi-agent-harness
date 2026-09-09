# Task 11 Evidence — D8 Mount Exception Executed (2026-09-09)

Human approval: explicit in-session ("approve, setuju") after reviewing the
validated proposal diff (`.tmp-work/cordis-mount-proposal.diff` vs snapshot of
the live file). Approval policy at execution: danger-full-access (out-of-
workspace edit permitted without escalation).

## What was changed (outside the repo, $DSH_HOME)

1. `$DSH_HOME/profiles/web/cordis.patch.yml`
   - 8 new instance rows inserted after `tool-subagent-nova`:
     `subagent_vera`, `subagent_argus`, `subagent_atlas`, `subagent_tess`,
     `subagent_quill`, `subagent_scout`, `subagent_talon`, `subagent_ledger`
   - 7 baseline rows' deny lists extended 6 → 14 siblings (allow sets
     byte-identical)
   - Pre-change backup: `runs/specialist-expansion-2026-09-09/backups/
     cordis.patch.yml.pre-mount-2026-09-09` (sha256-verified identical to the
     live file at backup time)
2. `$DSH_HOME/.agent-presets/` — 8 new persona dirs installed
   (`role-vera` … `role-ledger`), each = `agent.cordis.yml` (copied verbatim
   from the repo draft `agents/<id>/agent.cordis.yml`) + `preset.yml` (one-
   line domain description). Additive only; the 7 baseline preset dirs were
   not touched.

## Verification performed

- Snapshot integrity: live file sha256 == snapshot sha256 before overwrite;
  applied file sha256 == proposal sha256 after (`eec5ed0e…` → `e0e6d0c1…`).
- Live file parses; **15** `tool-subagent-*` rows in canonical PRD §9 order;
  allow∩deny = ∅ for all 15; every deny list names exactly 14 sibling
  `subagent_<id>` instances; every row's allow/deny set-equal to the source
  of record `config/tool-subagent-instances.yaml` (draft_version 2).
- Presets: 15 dirs present, 8 expansion dirs carry both files.
- Suite (post-mount test surface): `tests/l3_runner/ tests/environment/
  tests/phase-5/ tests/g13/ tests/live_dsh/ tests/g10/` → 1390 passed, 4
  skipped, 1 failed (`test_web_answerer_is_not_in_dsh_home_profiles`,
  pre-existing env drift). Validator still 456/0.
- Pre-existing env failure unchanged before/after mount.

## Test-surface reconciliation at mount (repo)

- `tests/l3_runner/environment/live-bridge/test_live_bridge_readiness.py`:
  `test_live_rows_match_config` strict-xfail REMOVED (its XPASS forced this
  cleanup by design); `test_seven_instance_rows_present` →
  `test_all_instance_rows_present` over the 15-roster; docstrings updated.
- `tests/l3_runner/environment/readiness.py`: `ROLE_PRESETS` /
  `ROLE_INSTANCE_IDS` now the full 15-roster (derived from
  SPECIALIST_ROLES); `ALL_INSTANCE_IDS` kept as alias; D4D7-1/2 check titles
  "7 …" → "15 …".
- `tests/g13/gate/{test_g13_live_execution_gate,test_g13_live_recheck}.py`:
  axis-2 preset-set pins extended to 15.
- `tests/environment/preflight.py`: ROLE_PRESETS 15; ENV-MOUNT-2 "15 …".
- `tests/phase-5/final/preflight/test_final_live_preflight.py`: checklist
  quote pin "all 15 `subagent_<id>` instances".
- `docs/phase-5/environment/final/0001-operator-infrastructure-checklist.md`:
  rows 5/7/101 updated to 15 with the D8 date; `docs/phase-5/final/preflight/
  0001-final-operator-checklist.md` C5 note: per-session probe semantics kept.
- `config/tool-subagent-instances.yaml` + `config/role-preset-mapping.yaml`:
  status notes record the 2026-09-09 expansion mount (validator checks only
  `status == "mounted"` and count 15 — unchanged, still pass).
- `AGENTS.md`, `docs/tool-catalog.md`, `PRD.md`, `docs/adr/
  0003-specialist-pool-expansion.md`: mounted-state wording + dated status.
- Historical dated evidence reports (coordinator report, session-B doc,
  0001-d4d7-live-bridge-readiness.md table) deliberately NOT rewritten —
  they record their own point in time.

## Activation semantics (unchanged)

The cordis patch composition loads at DSH web-profile boot: the 8 new
specialists become invocable in NEW web sessions after a GUI restart/reload.
REGISTRATION ≠ ACTIVATION still holds per session: real live dispatch
additionally requires the `DSH_LIVE_BRIDGE_ACTIVE=1` runtime marker
(per-session, orchestrator-side) — file persistence ≠ live bridge.

## Not verified here (honesty)

- A live GUI restart + runtime probe of the 8 new personas (out of scope for
  this session; next session should see `subagent_vera` … in its tool list).
- Live dispatch smoke for a new specialist (requires an active bridge session).

# Final Operator / Infrastructure Checklist — Human + Infrastructure Readiness

- **Milestone**: Phase 5 / Final — HUMAN + INFRASTRUCTURE READINESS (final
  security / Session D)
- **Status**: CHECKLIST (single authoritative operator/infrastructure
  checklist; **no prerequisite is changed, no session policy change, no
  DSH/profile/preset modification, no fabricated Human signoff, no L3 run, no
  L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope of write**: `multi-agent-harness/docs/phase-5/environment/final/`
  (this file) + `multi-agent-harness/tests/l3_runner/environment/final/`.
  All facts read-only; everything outside these two paths unmodified.
- **Companion**: `docs/security/0007-l3-run-prerequisites.md` (PF-*) ·
  `docs/phase-5/l3/environment/0001-l3-environment-readiness.md` +
  `0001-l3-environment-human-answerer-readiness.md` +
  `0002-session-a-preflight-verification-record.md` · `docs/phase-5/l3/0001-l3-execution-readiness.md`
  · `docs/phase-5/final/0001-security-closure-matrix.md` · `docs/phase-5/final/0005-final-security-gate-evidence.md`
  · `tests/l3_runner/environment/readiness.py` (probe) · `docs/security/0003-l3-independent-verification-plan.md` §15.

> This is **the** exact operator/infrastructure checklist. Each of the eleven
> prerequisites is given: READY / BLOCKED (current, observed), the exact
> operator action required, and the exact evidence that must exist before an
> L3 run is authorized. It **does not change** any prerequisite, session
> policy, DSH core/profile/preset, or role mapping, and it **does not
> fabricate** a Human signoff.

---

## 1. One-line status

```text
rehearsal_ready      = True     (machinery can rehearse/replay)
l3_claim_possible    = False    (3 L3-required prerequisites absent)
all_required_pass    = True     (rehearsal level)
all_l3_required_pass = False    (L3 claim level)
```

Observed this session (read-only probe with `orchestrator_uid=1000`):
**exactly 3 blockers**: `L3ENV-UID-2`, `L3ENV-D4D7-3`, `L3ENV-PLAN-REAL`.
(`L3ENV-ANS-1/2` are **no longer blockers** — the targeted approval-probe repair
wired the corrected composition detector into the readiness probe; the web GUI
answerer is available by composition in this session.)

---

## 2. The checklist (11 prerequisites)

| # | Prerequisite | READY / BLOCKED | Exact operator action | Exact evidence required |
|---|---|---|---|---|
| 1 | **Separate UID / credential (IO-2)** | **BLOCKED** — same-UID host: orchestrator and verifier subprocess both `uid=1000` (`L3ENV-UID-2` fails; `docs/security/0007` §1.2) | Provision a distinct launch credential: **setuid wrapper**, **separate user account**, or **separate host** so `verifier_uid != orchestrator_uid` (both non-zero) | `verifier-independence.json` with `IO-2 pass=true`, `verifier_uid != orchestrator_uid`; preflight `PF-UID-2` PASS with a real distinct UID |
| 2 | **Separate verifier process (IO-1 / IO-4)** | **READY** — runner spawns the verifier via `subprocess` (distinct PID); never `subagent`/`subagent_fork`/`send_message` (`L3ENV-UID-1/3`, `PF-UID-1/3`) | None (mechanism present). Keep using `subprocess` spawn; do **not** route verifier creation through orchestrator session-tree tools | `verifier-independence.json` `IO-1 pass=true` (`verifier_pid != orchestrator_pid`, both non-zero), `IO-4 pass=true` (`parent_session_id` absent) |
| 3 | **Human approval answerer (G3)** | **READY (web GUI, by composition)** — DSH base bundle composes `@deepseek-ai/dsh-user-approval` and the web-app bundle composes the answerer surface (`ui-user-questions` + `ui-conversation` ApprovalPanel); the current session is a web GUI session with the browser attached. Corrected detection: `approval_readiness().status == APPROVAL_INTERACTIVE_READY` (`L3ENV-ANS-1` PASS). **Headless sessions remain BLOCKED** (no composed answerer → `unavailable`, fail-closed) | Web GUI: verify the browser is connected to the session (no policy edit). Headless: compose an `approval/request` answerer row or supply pre-recorded signed `approval-<id>` references | `L3ENV-ANS-1` PASS; web session `DSH_WEB_URL` set + HTTP 200; DSH bundle rows present |
| 4 | **Functional `ask` path (G3)** | **READY (web GUI)** — policy is `ask` and a live answerer is available by composition ⇒ `ask` resolves to a live answerer (`L3ENV-ANS-2` PASS). **Headless: BLOCKED** — no live answerer ⇒ `ask` resolves `unavailable` ⇒ DENY + escalate (fail-closed) | Web GUI: none (path live). Headless: restore the answerer path (item 3) **or** supply pre-recorded signed `approval-<id>` references for approval-dependent actions | `L3ENV-ANS-2` PASS; an approval-dependent action ALLOWs only through a live answerer or a valid structured `approval-<id>` record |
| 5 | **D4/D7 live bridge** | **BLOCKED (live dispatch)** / files persistent — 15 role presets under `$DSH_HOME/.agent-presets/` and 15 `tool-subagent-<id>` rows in `$DSH_HOME/profiles/web/cordis.patch.yml` are present (`L3ENV-D4D7-1/2` PASS), but the bridge is **not persistently active** | Run the per-session mount-verification procedure (`docs/phase-5/environment/0001` §2): verify presets → verify instance rows → set the marker → resolve backend → probe → smoke; it must be re-verified **every session** (mount is not persistent) | `L3ENV-D4D7-1/2/3` all PASS; `probe_backend_kind() == real-dsh`; all 15 mount probes True; a minimal live `subagent_<id>` dispatch settles with a real run id |
| 6 | **`DSH_LIVE_BRIDGE_ACTIVE`** | **BLOCKED** — marker **unset** (`L3ENV-D4D7-3` fails) | Set `DSH_LIVE_BRIDGE_ACTIVE=1` for the orchestrator session **only after** steps in item 5 pass (fail-closed: a marker without a verified mount is a stale mount → escalate) | `echo ${DSH_LIVE_BRIDGE_ACTIVE:-unset}` → `1`; `tests/live_dsh/discovery.py` probe resolves `real-dsh`; `backend_kind() == REAL`; `BridgeNotAvailable` never raised |
| 7 | **Persistent role instances (D4/D7 rows)** | **READY** — all 15 role presets (`role-zeko…role-ledger`, D8 mount exception applied 2026-09-09) and all 15 `tool-subagent-<id>` instance rows present on disk (`L3ENV-D4D7-1/2` PASS) | None (composition files are persistent). Note: persistence is per-file only — the live bridge (items 5/6) is still required for dispatch | `ls $DSH_HOME/.agent-presets/` shows the 15 `role-*` dirs; `grep -c 'toolName: subagent_' $DSH_HOME/profiles/web/cordis.patch.yml` → `15` |
| 8 | **Human-signed plan mechanism (O4 / G7)** | **MECHANISM READY / REAL SIGNOFF BLOCKED** — `plan_signing.py` + `PF-PLAN-1..5` pass on the fixture (`L3ENV-PLAN-1..5` PASS); **no real Human signoff observed** — the committed `plan.json` is an inert fixture (`human-2026-08-31-001`, method `interactive`, template only) (`L3ENV-PLAN-REAL` fails) | Mechanism: none. Real signoff: a **Human with a durable identity** must sign each scenario `plan.json` (identity + method + timestamp) via the interactive/signed-assertion path **before** the run, and the signed plan must be committed with `human_signoff_provenance=recorded` | `L3ENV-PLAN-1..5` PASS **and** `L3ENV-PLAN-REAL` PASS; `validate_signed_plan() == VALID` on a plan whose `human_signoff_id` is a real durable id (not `human-YYYY-MM-DD-NNN` template), `human_signoff_ts` strictly before the runtime verdict (LV7/IO-7) |
| 9 | **Evidence store (G4 / 0005)** | **READY** — `audit/l3/` creatable/writable under the project root; probe never creates it (`L3ENV-STORE-1` PASS; rehearsal bundles go to scratch) | None required to make it writable; create `audit/l3/<scenario-id>/` only when an authorized L3 run begins | `L3ENV-STORE-1` PASS; a committed `audit/l3/<scenario-id>/` bundle with the 13-item evidence set (E1..E13) and `l3_claim=true` |
| 10 | **Replay tooling (P4 / G8)** | **READY** — `tests/l3_runner/replay.sh` present; deterministic fixture hash (`sha256:52037567…`); verifier + 11 schema sha256 recorded; no live-network dependency (`L3ENV-REP-1..4` PASS) | None (tooling present). Keep fixtures recorded; never introduce live-network scenarios | `L3ENV-REP-1..4` PASS; `replay.json` (E11) records fixture hash, replay command, verifier/schema sha256, DSH pin — reproducible byte-for-byte |
| 11 | **Approved live-run authorization** | **BLOCKED** — no Human acceptance of `docs/security/0003` §15; no re-baseline record; B1 (production control-plane code) not wired for a live L3 run; `LiveDSHRuntimeDriver` remains a refuse-to-simulate stub | A **Human must accept** `docs/security/0003` §15 (L3 execution protocol), confirm the G9 baseline (`workspace-write + ask`), and close B1 (production control-plane code) before any live L3 run is authorized | A Human-signed acceptance record of §15 (identity + timestamp); `0001` §14 assurance matrix updated; session at `workspace-write + ask`; B1 closed; at least one Human-signed `plan.json` per scenario |

---

## 3. Final `l3_claim_possible` derivation

```text
l3_claim_possible = all_l3_required_pass
                  = AND( every prerequisite marked required_for_l3 is PASS )

Observed FAILs (required_for_l3 = True, all three absent):
  1. L3ENV-UID-2      separate UID (same-UID host, IO-2)
  2. L3ENV-D4D7-3     live bridge marker DSH_LIVE_BRIDGE_ACTIVE (G2)
  3. L3ENV-PLAN-REAL  real Human signoff (O4 / G7)

⇒  l3_claim_possible = False

rehearsal_ready = all_required_pass = True   (none of the rehearsal-required
                                              checks fail; machinery may
                                              rehearse/replay with l3_claim=false)
```

**Rule (binding):** an L3 claim is possible **only** when every
`required_for_l3` check passes. Today exactly three fail (after the approval-probe
repair; `L3ENV-ANS-1/2` now pass); the infrastructure
never fakes separation, never invents a signoff, and never changes policy to
force a pass. Until all eleven prerequisites hold, **no control is L3, no live
L3 run is executed, and no L3 claim is made.**

---

## 4. Evidence of observation (this session, read-only)

| Fact | Observed | Source |
|---|---|---|
| Host UID | `1000` (administrator); verifier subprocess probe `1000` — same UID | `id -u`; readiness probe L3ENV-UID-2 |
| DSH version | `0.1.1-rc.2` | `package.json` |
| Sandbox / approval | `workspace-write` + `ask` (baseline holds; REPORT ONLY) | runtime context; L3ENV-ENV-2 |
| Approval answerer | available by composition in this web GUI session (DSH base + web-app bundles; `L3ENV-ANS-1` PASS) | L3ENV-ANS-1; `approval_readiness()` |
| D4/D7 presets | 7 present (`role-zeko…role-nova`) | `ls $DSH_HOME/.agent-presets/` |
| D4/D7 instance rows | 15 (`subagent_zeko…subagent_ledger`; D8 applied 2026-09-09) | `grep -c 'toolName: subagent_' $DSH_HOME/profiles/web/cordis.patch.yml` → `15` |
| `DSH_LIVE_BRIDGE_ACTIVE` | unset | `env` |
| Verifier binary | `tests/l3_runner/verifier.py`; sha256 `125d61d4…`; subprocess CLEAN | L3ENV-VER-1/2/3 |
| Reference oracle | `tests/l3_reference/authority_gate.py` resolves (`oracle_authority`) | L3ENV-VER-4 |
| Evidence store | `audit/l3/` not created; project root writable | L3ENV-STORE-1 |
| Replay | `replay.sh` present; fixture hash `sha256:52037567…` | L3ENV-REP-1/2/3/4 |
| Signed plan fixture | schema-valid; signoff `human-2026-08-31-001` (inert template) | L3ENV-PLAN-1..5; L3ENV-PLAN-REAL FAIL |

---

## 5. Honesty statement

1. **No prerequisite was changed.** The probe reports; it never provisions a
   UID, never enables an answerer, never sets the bridge marker, never signs a
   plan, never creates `audit/l3/`.
2. **No session policy changed** and **no DSH / profile / preset modified.**
3. **No Human signoff fabricated.** The fixture signoff is reported as inert;
   `L3ENV-PLAN-REAL` fails honestly.
4. **No L3 run executed, no L3 claim made.** `l3_claim_possible=False` on
   this host with exactly three named blockers (after the approval-probe
   repair).
5. **No test failure was downgraded or re-labelled.** All numbers are as
   observed by running the documented commands.

---

## 6. Scope check

**In scope (written/updated this session, targeted approval-probe repair):**
- `docs/phase-5/environment/final/` (this file + `0002-approval-l3-final-readiness.md`)
- `docs/phase-5/environment/approval/` (0001/0002 — probe-repair notes)
- `tests/environment/approval_composition.py`, `tests/environment/preflight.py`
- `tests/l3_runner/environment/` (readiness.py + `test_l3_environment_readiness.py`)
- `tests/l3_runner/environment/approval/` (approval path tests)
- `tests/l3_runner/environment/final/` (approval+L3 final + checklist-lock test suites)

**Not modified (verified):** session policy; DSH core/profile/preset;
`$DSH_HOME`; production code (`control/*`, `orchestrator/*`, `state/helpers/*`,
`audit/helpers/*`, `agents/*`, `config/*`, `schemas/*`); role mapping; any
existing test outside the write-only paths; no `audit/l3/` bundle created.
No L3 scenario executed. No control claimed L3.

---

*Status: CHECKLIST (updated by targeted approval-probe repair). READY for rehearsal;
BLOCKED for any L3 claim by exactly three named prerequisites (separate UID, live
bridge, real signoff) plus item 11 (approved live-run authorization). Final
`l3_claim_possible=False`. `L3ENV-ANS-1/2` now PASS (probe repaired; web GUI
answerer available by composition). No prerequisite changed; no policy/DSH change;
no signoff fabricated; no L3 claim.*

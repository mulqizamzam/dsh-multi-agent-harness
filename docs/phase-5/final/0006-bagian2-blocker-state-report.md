# Phase 5 — BAGIAN 2 Blocker-State Report (Fresh Evidence, This Session)

- **Milestone**: Phase 5 / Session F — BAGIAN 2: CLOSE G13 · L3 · G10
- **Status**: BLOCKED-STATE REPORT (fresh dynamic-state re-probe; no G13 live run, no L3 claim, no O3 implementation attempted)
- **Date**: 2026-09-01 (this session)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: Read-only evidence synthesis of the three BAGIAN-2 targets (G13, L3, G10). **No implementation change, no DSH modification, no session-policy change, no closure claimed.**
- **Method**: All dynamic state re-probed this session as fresh evidence; no prior-session blocker status reused without re-inspection (TOKEN-ECONOMY §5/§9/§10).

---

## 0. Headline verdict (three facts, fresh-verified this session)

| # | Fact | Evidence (this session) |
|---|------|-------------------------|
| F1 | **Live path NOT proven** — BAGIAN 1's D4/D7 mount does not survive session boundaries | `DSH_LIVE_BRIDGE_ACTIVE` unset; `probe_backend_kind()=BackendKind.UNAVAILABLE`; all 7 `subagent_<id>` → `NOT_MOUNTED` (`probe_all_instances_mounted()` → all False) |
| F2 | **Same-UID sandbox** — L3 IO-2 impossible; O3 P1–P5 impossible to provision | `id` → `uid=1000(administrator)`; `sudo -n true` → "no new privileges" flag BLOCKED; filesystem policy `workspace-write` (sandbox denies writes outside `[workspaceRoot, /tmp, tmpdir()]`) |
| F3 | **G13 blocker set B1..B7 unchanged** — every G13 live-execution precondition still FAILS | 11-axis recheck all re-probed; B1–B7 present (see §1) |

**Consequence for BAGAIN 2:** none of the three closure paths (G13 = CLOSED, L3 P1–P4 → `l3_claim=true`, G10 residual = CLOSED) can be reached in this session. The work that CAN proceed (deterministic suites, readiness mechanisms) is already green and is summarized below so no claim is made at a level the environment does not support.

---

## 1. Target 2A — G13 (prompt-injection / external-content)

### 1.1 Gate verdict

**G13_LIVE_READY = NO.** Live G13 execution cannot legally/procedurally start.

### 1.2 11-axis recheck (fresh, this session)

| # | Axis | Current (probed this session) | Status |
|---|------|-------------------------------|--------|
| 1 | `DSH_LIVE_BRIDGE_ACTIVE` | `unset` (env var absent) | ⛔ BLOCKED |
| 2 | 7 D4/D7 instances mounted | all 7 `NOT_MOUNTED` (`probe_all_instances_mounted()` → all False) | ⛔ BLOCKED |
| 3 | REAL backend available | `probe_backend_kind()` = `BackendKind.UNAVAILABLE`; `RealDSHBackend` no live bridge | ⛔ BLOCKED |
| 4 | real child observable | `precondition()` → `real_dsh_child_observable=False`, `satisfied=False` | ⛔ BLOCKED |
| 5 | approval path | `approval_readiness()` → `APPROVAL_INTERACTIVE_READY`, `composed=True`, `interactive_ready=True`, `effective_policy=ask`, `web_server_reachable=True`; **`e2e_status=UNKNOWN`, `probe_answered=False`, no independently re-derivable `approval/asked`+`approval/decided` pair** | 🟡 PARTIAL (composition ready; E2E UNKNOWN) |
| 6 | authorized G13 run | `LiveDSHRuntimeDriver.execute()` → `final_status=BLOCKED`, `denial_path=live-precondition:human_signed_plan,d4_d7_mounted,approval_answerer`; no Human acceptance of `docs/security/0003` §15 | ⛔ BLOCKED |
| 7 | scratch workspace | `mktemp` writable outside repo tree | ✅ READY |
| 8 | evidence capture | `audit/runtime/` exists (INT-01/07/11/12); plan defines GE-1..GE-5 | ✅ READY |
| 9 | stop-at-first-failure | no pytest config (`pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini`) sets `-x`/`maxfail=1`; documented invocation runs all 63 without fail-fast | ⛔ BLOCKED (not configured) |
| 10 | rollback/cleanup | plan defines 4 rollback steps + 4 non-destructive guarantees | ✅ READY |
| 11 | G10 current status | **OPEN / BLOCKING** (O3 not implemented; O5 containment only) | ⛔ OPEN / BLOCKING |

### 1.3 Exact current blockers (G13)

| # | Blocker | Evidence (this session) |
|---|---------|-------------------------|
| B1 | `DSH_LIVE_BRIDGE_ACTIVE` unset | env var absent |
| B2 | D4/D7 instances NOT_MOUNTED (all 7) | `probe_all_instances_mounted()` all False |
| B3 | No REAL backend | `probe_backend_kind()=unavailable` |
| B4 | No real DSH child observable | `precondition()["satisfied"]=False` |
| B5 | No authorized G13 run | `LiveDSHRuntimeDriver` → `BLOCKED`; §15 not accepted |
| B6 | Stop-at-first-failure not configured | no `-x`/`maxfail=1` in any pytest config |
| B7 | G10 OPEN / BLOCKING | O3 not implemented; O5 containment only |

### 1.4 What is READY (deterministic, all green this session)

| Asset | State |
|---|---|
| 63 canonical adversarial scenarios (7 channels C1..C7 × 8 vectors V1..V8) | `tests/g13/payloads.py`, `tests/g13/live_readiness/payloads.py` — canonical, unchanged |
| Session-D verification | `docs/phase-5/security/g13/0001` |
| Live readiness package (prepared, not executable) | `tests/g13/live_readiness/` |
| Gate tests | `tests/g13/gate/` + `tests/g13/live_readiness/` → **167 passed** this session |
| Full G13+L3 suite | **741 passed** this session |
| Evidence format | GE-1..GE-5 defined; `audit/runtime/` writable |

### 1.5 Required operator actions to flip to YES

1. **Human approves per-session D4/D7 mount procedure (H7)** before any mount action.
2. **Operator runs the mount-verification procedure** (`docs/phase-5/environment/0001` §2.2): verify presets → verify instance rows → set marker → resolve backend → probe → smoke dispatch. **Per-session action; must be re-verified every session.**
3. **Human authorizes the G13 adversarial live test (H8)** — acceptance of `docs/security/0003` §15.
4. **Operator configures stop-at-first-failure**: run with `-x`/`--maxfail=1` (or add `addopts = -x` to a pytest.ini) so the 63-case run stops at first failure.
5. **Verify approval answerer E2E** before relying on it: confirm an independently re-derivable `approval/asked` + `approval/decided` pair in the session log (composition ≠ E2E).
6. **Track G10 closure on a parallel track** (O3 implementation or DSH upgrade with per-path/per-agent isolation). G10 OPEN/BLOCKING must be recorded; it does not block the non-destructive G13 live observation but must not be closed or bypassed by this gate.

**G13 verdict: OPEN/UNKNOWN (no DSH-native immunity claim). Not closable in this session.**

---

## 2. Target 2B — L3 (independently verified runtime)

### 2.1 Readiness verdict

**`l3_claim_possible = false`** (fresh `tests/l3_runner/environment/readiness.py` assessment). Rehearsal-ready but NOT claim-ready.

### 2.2 L3 blockers (fresh)

| # | Blocked condition | Evidence (this session) |
|---|-------------------|-------------------------|
| L3ENV-D4D7-3 | live bridge marker set (`DSH_LIVE_BRIDGE_ACTIVE=1`) | env var unset → live DSH unavailable, fail-closed (`BridgeNotAvailable`) |
| L3ENV-PLAN-REAL | a REAL Human signoff observed (not invented) | committed plan is a fixture/template (`human_signoff_id=human-YYYY-MM-DD-NNN` inert); probe does not invent signatures |
| IO-2 | separate UID / credential | `orchestrator_uid=0 verifier_probe_uid=1000 same_uid=False` → same-UID host: IO-2 fails honestly; `l3_claim` impossible without setuid/separate-user/separate-host (`docs/security/0007` §1.2) |

### 2.3 What is READY (deterministic, green this session)

| Asset | State |
|---|---|
| 8 critical scenarios prepared | `tests/l3_runner/live-plans/L3-{AUTH-001,AUTH-003,AUTH-004,AUTH-006,PATH-001,REC-004,ST-003,AUD-002}/` — all 8 exist |
| P1 live-runtime machinery | `LiveDSHRuntimeDriver` — refuses live dispatch (BLOCKED by design until preconditions) |
| P2 independent observer | verifier subprocess (distinct PID, IO-1), clean oracle imports, sha256 `125d61d4...`; `assert_clean_imports() rc=0 CLEAN` |
| P3 oracle classes | 8 reference oracles (O1); rehearsal verifies LV10 fails-by-design |
| P4 replay/reproducibility | replay module + validator LV21/LV22 |
| Claim gate | `evaluate_l3_claim()` P1–P4 — refuses any claim without Human-signed plan + IO-2 + complete bundle |
| Full suite | **741 passed** this session (G13 + L3) |

### 2.4 Required operator actions to run the 8 scenarios and claim

1. **Separate UID host (IO-2)**: provision a separate-UID verifier host, or `setuid`/separate-user/separate-host per `docs/security/0007` §1.2. Without this, `l3_claim_possible` stays `false` and `evaluate_l3_claim()` refuses.
2. **Real Human-signed plans (O4)**: an actual Human signoff per scenario (durable identity + timestamp) on the 8 live plans — no invented sign-off, fixtures are inert.
3. **D4/D7 live + authorized run**: mount D4/D7 (H7 + operator procedure), `DSH_LIVE_BRIDGE_ACTIVE=1`, Human acceptance of `docs/security/0003` §15 (authorized run).
4. **Approval answerer E2E**: independently re-derivable `approval/asked`+`approval/decided` pair in the session log.
5. **Run 8 scenarios** → commit `audit/l3/<scenario-id>/` bundles → `evaluate_l3_claim()` P1–P4 must all pass → only then `l3_claim=true`.

**L3 verdict: NOT CLAIMED; `l3_claim_possible=false`. No partial claim is a full L3 claim. Not claimable in this session.**

---

## 3. Target 2C — G10 (DSH path-isolation) via O3

### 3.1 O3 implementation status

| Aspect | Status |
|---|---|
| H3 / H4 approvals | **GRANTED** (Human-stated; recorded in `0006`) |
| Infrastructure prerequisites P1–P5 | **ALL ABSENT** (fresh-verified, this session) |
| Daemon modules / IPC schema / client / config | NOT CREATED (blocked by pre-gate) |
| Acceptance tests (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) | NOT CREATED (blocked) |
| Pre-change backups | NOT CREATED (pointless without infra) |
| Phase B write-path switch | NOT ATTEMPTED (blocked) |
| O3 acceptance suite | NOT RUN |
| G10 closure conditions C1–C6 | NOT MET |

### 3.2 Infrastructure prerequisite state (fresh, this session)

| # | Prerequisite | Current state (probed now) | Provisionable from this session? |
|---|---|---|---|
| **P1** | Dedicated OS user `dsh-writer` | `id dsh-writer` → no such user | **NO** — requires `useradd` (root); `sudo` blocked (`no new privileges`); session UID 1000 |
| **P2** | Out-of-workspace daemon root `/var/lib/dsh-registry-writer/` | path does not exist | **NO** — requires `mkdir`+`chown` (root) in `/var/lib/`; session user cannot write there |
| **P3** | systemd unit `dsh-registry-writer.service` | `/etc/systemd/system/dsh-registry-writer.service` does not exist | **NO** — requires root; `systemctl` unavailable |
| **P4** | Shared HMAC-SHA256 secret outside workspace | `/etc/dsh-registry-writer/` does not exist; no secret file | **NO** — requires root to create `/etc/dsh-registry-writer/`; secret path is outside workspace |
| **P5** | Control-plane group `dsh` | `getent group dsh` → no such group | **NO** — requires `groupadd` (root) |
| P8 | Reusable modules (`state/helpers/*`, `audit/helpers/*`) | MET — CLOSED | Already present |
| P9 | Human approvals H3+H4 | GRANTED (this flow) | Already granted |

**Control-plane integrity (no drift):** all four hashes match baseline exactly this session:
- `control/execution_gate.py` → `ec3d245f2935e7a76b96632978ad44da4531859a04cfd6b8b7a30468008b7263`
- `orchestrator/runtime/store.py` → `14ff5e200baf97469b863a231391a8b8d8c6e97ead1519118e6f4a5f6d20bcee`
- `orchestrator/runtime/delegation.py` → `1cf48e092b67a7b131d1938c19540e493a748ec3d12911e6cd1fe0c640fb4770`
- `orchestrator/runtime/audit.py` → `7bc9c414b9889ff938e925990e3ea58fac81ccda50829da0304771bb1aee4f7c`

### 3.3 Exact operator provisioning commands (root, on host) to unblock O3

```bash
# 1. Dedicated OS user (P1)
sudo useradd --system --home-dir /var/lib/dsh-registry-writer --shell /usr/sbin/nologin dsh-writer

# 2. Out-of-workspace daemon root (P2)
sudo mkdir -p /var/lib/dsh-registry-writer/{state/{registry,projects},audit,backup}
sudo chown -R dsh-writer:dsh-writer /var/lib/dsh-registry-writer
sudo chmod -R 0700 /var/lib/dsh-registry-writer

# 3. systemd unit (P3) — unit file from docs/phase-5/security/g10/o3/execution/0002 §3.4
sudo cp /etc/systemd/system/dsh-registry-writer.service
sudo systemctl daemon-reload
sudo systemctl enable --now dsh-registry-writer

# 4. Shared HMAC secret outside workspace (P4)
sudo mkdir -p /etc/dsh-registry-writer
sudo openssl rand -hex 32 > /etc/dsh-registry-writer/hmac-secret
sudo chown dsh-writer:dsh-writer /etc/dsh-registry-writer/hmac-secret
sudo chmod 0600 /etc/dsh-registry-writer/hmac-secret

# 5. Control-plane group (P5)
sudo groupadd --system dsh
sudo usermod -aG dsh administrator
```

After steps 1–5 the environment is unblocked for Phase A (daemon authoring, acceptance, backups) and Phase B (write-path switch). Full record: `docs/phase-5/security/g10/o3/execution/0002` §3, `0006`.

### 3.4 O3 acceptance requirements (once infra exists)

DAEMON · IPC · ISO (isolation) · MIG (write-path migration: no direct protected-root writes, no in-workspace mirror) · REC · FC (fail-closed) · SOCKET (group-writable `0660`) · HON (honesty) — per `docs/phase-5/security/g10/o3/final/0004`. Protected roots: `state/registry/**`, `audit/**`, `state/projects/**`. If O3 fails acceptance, rollback (backups) and G10 stays OPEN.

**G10 verdict: OPEN / BLOCKING. O3 NOT IMPLEMENTED. Not closable in this session (root provisioning required, not available from sandbox).**

---

## 4. Overall status roll-up

| Target | Gate | Status | Blocked by |
|---|---|---|---|
| 2A — G13 | G13 = CLOSED | **OPEN/UNKNOWN** — NOT closable now | B1..B7 (live mount, REAL backend, authorized run, fail-fast, G10) |
| 2B — L3 | P1–P4 → `l3_claim=true` | **NOT CLAIMED** (`l3_claim_possible=false`) | IO-2 (separate UID), real Human signoff, D4/D7 live, authorized run |
| 2C — G10 | residual R = CLOSED | **OPEN / BLOCKING** — O3 NOT IMPLEMENTED | P1–P5 (root provisioning) |

**All three closure paths remain BLOCKED in this session. Every deterministic readiness mechanism is green (741 G13+L3 tests, 167 gate/live-readiness, 14 phase5_security). No closure claimed. No failure downgraded. No invention.**

---

## 5. Scope check

**Written this session:** `docs/phase-5/final/0006-bagian2-blocker-state-report.md` (this file).

**Not modified (fresh-verified):** `control/`, `orchestrator/` (production), `state/`, `audit/`, `config/`, `agents/`, `schemas/`, `tests/` (all), DSH core/profile/preset/session policy. Control-plane hashes match baseline. No implementation change, no DSH modification, no session-policy change, no user/group/secret/service created, no closure claimed.

---

*Status: BLOCKED-STATE REPORT. G13 remains OPEN/UNKNOWN; L3 remains NOT CLAIMED (`l3_claim_possible=false`); G10 remains OPEN/BLOCKING (O3 not implemented — P1–P5 root provisioning required). BAGIAN 2 closure paths all blocked in this session by (F1) per-session live mount, (F2) same-UID sandbox, (F3) G13 B1..B7. Deterministic readiness is fully green. Operator actions enumerated per blocker. No claim at a level the environment does not support.*

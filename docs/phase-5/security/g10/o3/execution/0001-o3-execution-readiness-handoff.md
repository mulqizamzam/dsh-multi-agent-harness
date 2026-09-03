# G10 O3 — EXECUTION-READINESS PACKAGE: OPERATOR / HUMAN HANDOFF (Design-Ready → Implementation-Ready)

- **Milestone**: Phase 5 / G10 O3 — FINAL EXECUTION-READINESS PACKAGE
- **Status**: EXECUTION-READINESS (handoff package). **O3 is NOT implemented.** No daemon exists. No write path is switched. No user/group/secret/service was created. No DSH or session-policy change. **G10 remains OPEN / BLOCKING for production. No closure claimed.**
- **Date**: 2026-09-01 (execution package authored after the FINAL design package and the operator decision package)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified `dsh --version` this session); O5 applied (raw-write actor set `{zeko, cto}`)
- **Write-only scope**: `docs/phase-5/security/g10/o3/execution/` + `tests/g10/o3-execution/`. **No implementation, no DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no user/group/secret/service creation, no closure claim.**
- **Authoritative design source**: `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` (design) · `0002-o3-final-closure-determination.md` (per-root determination) · `0003-o3-final-threat-model.md` (T1–T10) · `0004-o3-final-acceptance-test-spec.md` (acceptance spec) · `docs/phase-5/security/g10/o3/implementation/0001-o3-implementation-readiness.md` (readiness handoff) · `docs/phase-5/security/g10/decision/0001-g10-o3-operator-decision-package.md` (Human decisions H3/H4/H5, prerequisites P1–P9, sequence, rollback).
- **Companion (this package)**: `0002-o3-approvals-and-infrastructure.md` (items 1–3) · `0003-o3-backups-freeze-and-migration.md` (items 4–6) · `0004-o3-acceptance-and-rollback.md` (items 7–8) · `0005-o3-closure-gate-and-evidence.md` (items 9–10) · `tests/g10/o3-execution/test_o3_execution_readiness.py`.

---

## 1. Purpose of this package

The FINAL architecture package (Session F) finalized the O3 design; the implementation-readiness package (Session G) verified it as a design handoff; the operator decision package recorded the exact Human decisions required. **This package is the operator/Human execution handoff** — the exact, ordered, evidence-gated procedure to move O3 from **DESIGN-READY → IMPLEMENTATION-READY**, answering the ten items in the brief:

| # | Brief item | Where |
|---|---|---|
| 1 | Human approvals required | `0002` §1 |
| 2 | Infrastructure provisioning checklist | `0002` §2 |
| 3 | Exact root/user/group/secret/service requirements | `0002` §3 |
| 4 | Exact pre-change backups | `0003` §1 |
| 5 | Freeze-window procedure | `0003` §2 |
| 6 | Phase A/B/C migration order | `0003` §3 |
| 7 | Acceptance test order | `0004` §1 |
| 8 | Rollback | `0004` §2 |
| 9 | G10 closure gate | `0005` §1 |
| 10 | Evidence required at each step | `0005` §2 |

**This package does NOT implement, does NOT provision, does NOT modify anything, and does NOT claim closure.** It is the operator's checklist: each step names the exact command/artifact, the exact gate before proceeding, and the exact evidence to record.

---

## 2. Status vocabulary (binding, same as the decision package)

| Label | Meaning |
|---|---|
| **CLOSED** | Requirement satisfied at the stated evidence level; does not imply production/L3 readiness. |
| **OPEN** | Not satisfied; the gap is documented with evidence. |
| **BLOCKED** | Cannot proceed — a named prerequisite is absent. |
| **DEFERRED** | Intentionally out of scope for now; recorded. |
| **UNKNOWN** | Not verifiable in this environment / no claim made. |

---

## 3. Current state — re-verified THIS session (read-only evidence)

| Fact | Current value | Source (this session) |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `dsh --version` |
| Host UID / GID | `1000` / `1000` (`administrator`) | `id -u`, `id -g` |
| Host groups | `administrator`, `nogroup` (x6) — **no `dsh` group** | `groups` |
| OS / systemd | Ubuntu 26.04 LTS; systemd 259 (unit provisioning possible on this host class) | `/etc/os-release`; `systemctl --version` |
| File sandbox policy | `workspace-write` | runtime context |
| Approval policy | `ask` | runtime context |
| `DSH_WEB_URL` | `http://127.0.0.1:13080` (set this session — web GUI present; **note:** master-audit recorded a headless session; environment is session-dependent — see §3.1) | `env` |
| `DSH_HOME` | `/home/administrator/agent-workspace/.dsh` | `env` |
| Dedicated user `dsh-writer` | **ABSENT** — `id dsh-writer` → no such user | `id` |
| Group `dsh` | **ABSENT** — `getent group dsh` → no such group | `getent` |
| Daemon root `/var/lib/dsh-registry-writer/` | **ABSENT** (path does not exist; `/var/lib/` is `nobody:nogroup 0755` — provisioning requires root) | `ls -ld` |
| Daemon package `registry_writer/` | **ABSENT** | `ls` |
| `schemas/ipc.py` | **ABSENT** (schemas/ has JSON schemas incl. `delegation.schema.json`, `project-state.schema.json` only) | `ls schemas/` |
| `config/registry-writer.yaml` | **ABSENT** | `ls config/` |
| systemd unit `dsh-registry-writer.service` | **ABSENT** | `ls /etc/systemd/system/` |
| `state/registry/` | in-workspace; contains only `README.md` (no `delegations.json`/`revocations.json` yet) | `ls state/registry/` |
| `state/projects/` | exists, empty (no project doc yet) | `ls state/projects/` |
| `audit/runtime/` | `INT-01`, `INT-07`, `INT-11`, `INT-12` per-scenario ledgers + `.chain` (in-workspace) | `ls audit/runtime/` |
| `control/execution_gate.py` | V1 direct-write unchanged (`registry_write`→`atomic_write`; `audit_append`→`append_event`) — SHA-256 recorded in §4 | file read + `sha256sum` |
| `orchestrator/runtime/store.py` | V1 direct-write (`write_through`→`atomic_write`) — SHA-256 recorded in §4 | file read + `sha256sum` |
| `orchestrator/runtime/delegation.py` | V1 direct-read (`safe_read` on `state/registry/`) — SHA-256 recorded in §4 | file read + `sha256sum` |
| `orchestrator/runtime/audit.py` | V1 direct-append via `execution_gate.audit_append` — SHA-256 recorded in §4 | file read + `sha256sum` |
| Reusable modules (design reuse) | `state/helpers/{atomic_write,version_check}.py`, `audit/helpers/{append_log,integrity}.py` — present; `MAX_DOC_BYTES = 16 MiB` at `state/helpers/atomic_write.py:42` (payload cap for the daemon, T10) | `ls`, `grep` |
| Raw-write actor set | `{zeko, cto}` — zeko/cto `allow` includes `bash, edit, write`; somad/nova `deny` includes `bash, edit, write` (O5 preserved in config and in live `$DSH_HOME/profiles/web/cordis.patch.yml`) | `config/role-preset-mapping.yaml` + live patch read |
| VCS | **No git repository** (`git status` → fatal) — rollback is file-level | `git status` |
| Test baselines (this session) | `tests/g10/` = **233 passed**; `tests/g10/o3-planning/` = **123 passed**; `tests/g10/decision/` = **32 passed**; `tests/phase5_security/ + tests/authorization/` = **192 passed**; `tests/validate_config.py` (as script) = PASS | observed runs (venv `.venv-tests`, pytest 9.1.1) |
| G10 status | **OPEN / BLOCKING** for production; residual R (post-O5) accepted; containment = detection | closure matrix §1; residual proof §1 |
| O3 status | **NOT IMPLEMENTED** — this package is the execution handoff | this document |

**The residual R (post-O5, unchanged):** a raw-write-capable role (`{zeko, cto}`) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. Prevention at the DSH layer: **ABSENT**. Containment at the project layer: **DETECTION** (L1 gate + append-only + cumulative hash chain + CAS). **G10 stays OPEN / BLOCKING for production.**

### 3.1 Environment note (session-dependence)

The master-audit (Session D) recorded a **headless** session (`DSH_WEB_URL` unset). THIS session has `DSH_WEB_URL=http://127.0.0.1:13080` set. Per the reconciliation report, approval-answerer availability and the L3ENV blocker count are **session-dependent** (3 blockers in web-GUI sessions vs 5–7 in headless sessions). For O3 execution this matters only for the **approval path** (H3/H4 approval recording): the operator must verify the current session's approval answerer state before recording approvals. It does not change any O3 design, migration, rollback, or acceptance fact in this package.

### 3.2 Host feasibility verdict (READ-ONLY, this session)

| Capability | Feasible from this session? | Evidence |
|---|---|---|
| Author the handoff package | YES | this package (written within the two write-only targets) |
| Verify current state read-only | YES | §3 table, all probes read-only |
| Run the O3 planning / G10 / validate-config suites | YES | §3 test baselines (233 / 123 / 32 / 192 / PASS) |
| Run the O3 **acceptance** suite (DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON) | **NO** — the daemon does not exist | FINAL 0004 §1 honesty rule 2; spec'd, not run |
| Create user/group `dsh-writer`/`dsh` | **NO** — requires root; this session has UID 1000, `sudo` blocked (`no new privileges` flag) | `id -u`; `sudo -n true` |
| Create `/var/lib/dsh-registry-writer/` | **NO** — `/var/lib/` is `nobody:nogroup 0755`; requires root | `stat -c` |
| Install systemd unit | **NO** — requires root | `systemctl` (read-only probe) |
| Provision the HMAC secret outside the workspace | **NO** — would place a secret outside the sandbox writable set; must be done by the operator as root on the host | design constraint (FINAL 0001 §4.4) |
| Execute migration Phase B (write-path switch) | **NO** — would modify `control/`, `orchestrator/` (out of this task's scope and blocked until H3/H4) | decision package §3, §5 |

**Feasibility verdict:** the **host is implementation-capable** (Ubuntu 26.04 + systemd 259, reusable `state/helpers/*`/`audit/helpers/*`, DSH 0.1.1-rc.2) but the **provisioning steps (P1–P5, P7) require a privileged operator on the host** (root + systemd), which this sandboxed session cannot perform and this task must not perform. The handoff therefore separates **operator actions** (root, on-host) from **engineering actions** (in-workspace) from **Human decisions** (approval records) — see `0002` §2.

---

## 4. Control-plane file baseline (SHA-256, THIS session — the rollback-precondition reference)

These hashes are the **pre-change baseline** recorded today. The mandatory pre-change backup procedure (item 4, `0003` §1) re-captures these files byte-for-byte **at the moment before Phase B** and records fresh hashes; today's hashes prove the files are still the V1 originals as of this session.

| File | SHA-256 (this session) |
|---|---|
| `control/execution_gate.py` | `ec3d245f2935e7a76b96632978ad44da4531859a04cfd6b8b7a30468008b7263` |
| `orchestrator/runtime/store.py` | `14ff5e200baf97469b863a231391a8b8d8c6e97ead1519118e6f4a5f6d20bcee` |
| `orchestrator/runtime/delegation.py` | `1cf48e092b67a7b131d1938c19540e493a748ec3d12911e6cd1fe0c640fb4770` |
| `orchestrator/runtime/audit.py` | `7bc9c414b9889ff938e925990e3ea58fac81ccda50829da0304771bb1aee4f7c` |

---

## 5. Honesty statement

1. **O3 is NOT implemented.** This package is the operator/Human execution handoff. No daemon code was written; no `control/*`, `orchestrator/*`, `state/*`, `audit/*` file was modified; no user/group/secret/service was created; no DSH core, profile, preset, session policy, role capability, or live composition changed.
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. All per-root closure statements remain conditional on the FINAL 0002 §4.1 conditions (implemented, A+B isolation, projects extension, fully-switched write path, no fallback, verification passes, Human approval) — see `0005` §1.
3. **The `state/projects/**` scope extension is an explicit, separate Human decision (H4)** — it is not assumed; without it `state/projects/**` remains CAS-detected only and R is not closed for that root.
4. **The A+B isolation, cross-UID socket (`0660`), and no-mirror read decisions are finalized design decisions requiring Human approval (H3/H4)** — not applied changes.
5. **Rollback is file-level (no git repository)** — operators must never assume `git revert`.
6. **Host feasibility is stated honestly:** provisioning (user/group/root/systemd/secret) requires a privileged operator outside this sandbox; the acceptance suite cannot run today (no daemon); the planning/consistency suites ran green this session with the exact counts recorded in §3.
7. **No test failure was hidden or downgraded.** All counts are as observed. The acceptance suite is spec'd (FINAL 0004) but not run — there is no daemon — reported honestly.
8. **This package does not resolve G13 (OPEN/UNKNOWN) nor the non-G10 production blockers (B1/B2/B3/B7/B8)** — after O3 (under A1–A6 only) the G10 prevention gap would close, but production remains BLOCKED by the independent conditions (decision package §8).

---

## 6. Scope check

**In scope (written this session):**
- `docs/phase-5/security/g10/o3/execution/0001-o3-execution-readiness-handoff.md` (this file) + `0002` + `0003` + `0004` + `0005`
- `tests/g10/o3-execution/test_o3_execution_readiness.py`

**NOT modified (verified this session):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, live composition `$DSH_HOME/profiles/web/cordis.patch.yml` (read-only), `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/`, `tests/g10/o3-planning/`, `tests/g10/decision/` — unchanged), and all other `docs/`. No user/group/secret/service created. No daemon implemented. No write path switched. No role boundary changed. No closure of G10 claimed. No production deployment started.

---

## 7. NEXT (what the operator/Human does with this package)

1. Human records **H3** (approve O3) and **H4** (approve `state/projects/**` extension) → `0002` §1.
2. Operator provisions **P1–P5** (user, root, systemd, secret, group) → `0002` §2–§3.
3. Engineering implements the daemon + `schemas/ipc.py` + client + config, then runs the **acceptance suite** in a throwaway temp root → `0004` §1.
4. Operator captures **pre-change backups** (item 4) → `0003` §1.
5. Operator runs the **freeze window** and Phase A→B→C migration → `0003` §2–§3.
6. On any failure or rejected closure: **rollback** → `0004` §2.
7. Human records the **G10 closure decision (H5)** only after re-derived residual + full verification → `0005` §1.
8. Every step records its **evidence** per the matrix → `0005` §2.

*Status: EXECUTION-READINESS PACKAGE (Operator/Human handoff). O3 is design- and implementation-READY as a handoff but NOT implemented. Host is implementation-capable; provisioning requires a privileged operator; acceptance suite not runnable today (no daemon). Human approvals H3/H4 are the immediate prerequisite; H5 is deferred to post-verification. G10 remains OPEN / BLOCKING. No closure claimed. No user/group/secret/service created. No DSH/session-policy change.*

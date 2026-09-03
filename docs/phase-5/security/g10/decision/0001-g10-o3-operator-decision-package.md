# G10 O3 — HUMAN DECISION + OPERATOR HANDOFF PACKAGE

- **Milestone**: Phase 5 / Operator Handoff — G10 O3 HUMAN DECISION + OPERATOR HANDOFF PACKAGE
- **Status**: OPERATOR DECISION PACKAGE (handoff only; **O3 is NOT implemented; no daemon exists; no write path is switched; G10 remains OPEN / BLOCKING for production; no closure claimed**)
- **Date**: 2026-09-01
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified `package.json`); O5 applied (raw-write actor set `{zeko, cto}`)
- **Write-only scope**: `docs/phase-5/security/g10/decision/` + `tests/g10/decision/`. **No implementation, no DSH modification, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim.**
- **Evidence (current, read-only this session)**: `docs/phase-5/security/g10/implementation/0002-o5-application-record.md` (latest O5 record) · `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (decision record) · `docs/phase-5/security/g10/o3/final/0001-o3-final-architecture-package.md` + `0002-o3-final-closure-determination.md` + `0003-o3-final-threat-model.md` + `0004-o3-final-acceptance-test-spec.md` (latest O3 architecture) · `docs/phase-5/security/g10/o3/implementation/0001-o3-implementation-readiness.md` (O3 feasibility/readiness) · `docs/phase-5/final/0002-g10-formal-residual-proof.md` (R) · `docs/phase-5/final/0001-security-closure-matrix.md` · `docs/phase-5/final/0005-final-security-gate-evidence.md` · `docs/phase-5/final/audit/0001-evidence-consistency-audit.md` · `docs/phase-5/final/acceptance/0001-final-acceptance-matrix.md` · `config/role-preset-mapping.yaml` (re-read, actor set confirmed `{zeko, cto}`) · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py`.

---

## 0. Status vocabulary (binding)

| Label | Meaning |
|---|---|
| **CLOSED** | Requirement satisfied at the stated evidence level; does not imply production/L3 readiness. |
| **OPEN** | Not satisfied; the gap is documented with evidence. |
| **BLOCKED** | Cannot proceed — a named prerequisite is absent. |
| **DEFERRED** | Intentionally out of scope for now; recorded. |
| **UNKNOWN** | Not verifiable in this environment / no claim made. |

---

## 1. G10 residual after O5 (exact)

**R (post-O5, current):** a raw-write-capable role — exactly `{zeko, cto}` — can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that **bypasses the project write channel**. The L1 execution gate (`control/execution_gate.py`) intercepts only channeled writes; DSH `0.1.1-rc.2` provides no per-path or per-agent filesystem interception. **Prevention at the DSH layer: ABSENT. Containment at the project layer: DETECTION** (L1 gate + append-only ledger + cumulative SHA-256 chain + CAS/version monotonicity).

| Item | State | Class |
|---|---|---|
| O5 applied (somad/nova stripped of `write`/`edit`; actor set `{zeko,cto,somad,nova}` → `{zeko,cto}`) | **APPLIED** (containment only) | CLOSED (as O5; does not close G10) |
| Raw-write actor set | `{zeko, cto}` (re-verified from config this session) | OPEN |
| Per-root residual `state/registry/**` | raw-tool bypass open; gate-DENIED for channeled writes | OPEN |
| Per-root residual `audit/**` | raw-tool bypass open; gate-DENIED for channeled writes | OPEN |
| Per-root residual `state/projects/**` | raw-tool bypass open; **ALLOWED at gate**, CAS-detected post-hoc only | OPEN |
| **G10 verdict** | **OPEN — BLOCKING for production** | OPEN / BLOCKING |

**What G10 is not:** G10 is not a claim that a raw write *will* happen, nor that tampering is undetectable (detection exists and is green). G10 is the capability-level proof that **prevention** of a raw write to the protected roots by `{zeko, cto}` is absent at the DSH layer.

---

## 2. Exact reason O3 is required

1. **O5 cannot close R.** O5 is containment by surface reduction. `{zeko, cto}` legitimately need raw `bash`/`write`/`edit` for ops/engineering; removing those tools from them is a **capability regression, not a mitigation**. The residual remains fully true for both.
2. **O4 (DSH per-agent/path-level sandbox) is absent.** `0.1.1-rc.2` has a per-session sandbox (`child-agent.ts:180`, `roots.ts:52–55`), tool-level `toolFilter` only (`tools/index.ts:680–690`), and no path-level differentiation (negative grep). O4 is an **upstream DSH requirement**; this project cannot add it (ADR 0001 Decision 7 boundary).
3. **O2 (registry relocation) alone is non-functional.** The orchestrator shares the per-session sandbox; relocating the roots outside the workspace also blocks the orchestrator's own single-writer access without a mediating process (ADR 0002 Option A analysis — rejected for V1).
4. **O3 is the only closure arm available to this project that hard-isolates the authority source without DSH change** (ADR 0002 consequence 4): a dedicated out-of-process writer daemon owning the three roots, roots placed **outside the session workspace** (so the sandbox hard-denies every session tool write) **and** run under a **dedicated OS UID** (defense-in-depth). It closes R for **all** raw-write roles, not just some.

**One sentence:** *O3 is required because the G10 prevention gap can only be closed from inside this project by removing the three protected roots from the session's reachable writable set — which requires the dedicated out-of-process writer (O3), the only hard-isolation arm that does not depend on an absent DSH capability (O4) and is not functionally self-blocking (O2).*

---

## 3. Exact Human decisions required

| # | Decision | Scope | Records the change in | Status |
|---|---|---|---|---|
| H1 | Accept G10 residual (V1 containment = detection) | keeps G10 OPEN; production blocked | `final/0001-g10-final-mitigation-analysis.md` | **DONE** (CLOSED) |
| H2 | Approve O5 (remove `write`/`edit` from somad/nova) | containment applied | `implementation/0002-o5-application-record.md` | **DONE** (CLOSED) |
| H3 | **Approve O3** — dedicated registry/audit/projects writer daemon (ADR 0002 consequence 4 infrastructure change) | authorizes implementation + deployment of the daemon | `o3/final/0001-o3-final-architecture-package.md` §4 | **REQUIRED — OPEN** |
| H4 | **Approve the `state/projects/**` scope extension** (beyond ADR 0002 consequence 4's registry/audit description) | without it, `state/projects/**` remains CAS-detected only and R is not closed for that root | `o3/final/0002-o3-final-closure-determination.md` §3 | **REQUIRED — OPEN** |
| H5 | **Approve G10 closure** (post-implementation, post-verification) | the only actor that may decide closure; no test or session decides it | `o3/final/0002` §4.1 conditions 1–6 + re-derived residual | **DEFERRED** (only after implementation + verification) |

**Decision gating:** H3 and H4 are prerequisites to any O3 implementation. H5 is a post-implementation decision; it is explicitly **DEFERRED**, not pending now.

---

## 4. Exact infrastructure prerequisites

| # | Prerequisite | Exact requirement | Status |
|---|---|---|---|
| P1 | Dedicated OS user `dsh-writer` | owns the daemon root tree; **no** write access to the session workspace; no network listener (systemd `PrivateNetwork=yes`); resource limits | **UNMET — BLOCKED** |
| P2 | Out-of-workspace daemon root (e.g. `/var/lib/dsh-registry-writer/`) | dirs `0700`, files `0600`, owner `dsh-writer`; **no daemon root may ever live inside `workspaceRoot`**; layout: `state/registry/`, `state/projects/`, `audit/`, `backup/`, `ipc.sock`, `daemon.pid` | **UNMET — BLOCKED** |
| P3 | systemd unit `dsh-registry-writer.service` | `User=dsh-writer`, `Restart=always`, `RestartSec=2s`, readiness probe (`health?name=ready`), `After=`/cold-start ordering before delegations | **UNMET — BLOCKED** |
| P4 | Shared HMAC-SHA256 secret | provisioned to exactly two principals (daemon + control plane) via a `0600` file **outside the session workspace**; replay window ±30s; rotation with version tag | **UNMET — BLOCKED** |
| P5 | Control-plane group `dsh` | socket group-writable `0660` (group `dsh`); session actors not in the group and without the secret | **UNMET — BLOCKED** |
| P6 | Pre-change file-level backups + SHA-256 | byte-for-byte backups of `control/execution_gate.py`, `orchestrator/runtime/{store,delegation,audit}.py`, new `config/registry-writer.yaml` — **mandatory rollback precondition** | **UNMET — BLOCKED** (nothing applied yet) |
| P7 | Maintenance/freeze window for Phase B | stop writes to the three roots; flip under lock; verify single-writer before resuming | **UNMET — BLOCKED** (operator scheduling) |
| P8 | Reusable modules | `state/helpers/{atomic_write,version_check}.py`, `audit/helpers/{append_log,integrity}.py` — present, importable, reused-by-design | **MET — CLOSED** |
| P9 | Human approvals H3 + H4 | per §3 | **UNMET — BLOCKED** |

**Note (no git):** the project is **not a git repository**; rollback and backups are file-level. Never assume `git revert` is available.

---

## 5. Exact implementation sequence

| Step | Phase | Action | Gate before next |
|---|---|---|---|
| 1 | — | Human approvals H3 + H4 recorded | approvals committed |
| 2 | A (prepare) | Provision P1–P5 (user, root, systemd, secret, group); implement daemon + `schemas/ipc.py` + client + `config/registry-writer.yaml`; run the FINAL 0004 acceptance suite in a **throwaway temp root** | O3-DAEMON/IPC/ISO/MIG/REC/FC/SOCKET/HON all pass |
| 3 | A (prepare) | Copy `state/registry/`, `state/projects/`, `audit/` → daemon root; verify SHA-256-identical; verify daemon reads equal direct reads; run **shadow mode** (reads only) | data identical; reads identical; health/authn/fail-closed verified |
| 4 | B (switch) | **Freeze window**: stop writes to the three roots; flip `execution_gate.registry_write()` + `audit_append()` → daemon client; `RuntimeStore.persist()`/`ensure_state()` → `project_write()`, `load_project_state()` → `project_read()`; `FileDelegationProvider.current()` → `registry_read()`; audit reads → `audit_read`/`audit_verify`; **remove** the direct-write paths (removed, not conditional); `write_through()` for non-protected paths unchanged; remove roots from the session workspace (or `dsh-writer`-owned stubs, session-UID denied); **no in-workspace mirror** | single-writer verified; no window with dual writers |
| 5 | C (verify) | The three roots absent/denied from the session workspace; re-derive the isolation probes (`test_raw_write_reaches_protected_path_unintercepted` inverted → **DENIED**; O3-ISO-001..004); run full G10 suite + O3 acceptance suite + `tests/validate_config.py` + full Phase-5 regression | all green |
| 6 | — | Re-derive the per-root residual (`o3/final/0002` §3) and record it | residual record committed |
| 7 | — | **Human decides G10 closure (H5)** | closure recorded (or rejected → rollback per §7) |

**Do NOT** execute G13/L3 during this sequence; do not claim closure at any step; re-run `validate_config` + full G10 suite after every applied step.

---

## 6. Exact acceptance criteria

O3 is accepted only when **all** of the following hold (from `o3/final/0002` §4.1 conditions 1–6 and `0004`):

| # | Criterion | Exact form |
|---|---|---|
| A1 | Implemented + deployed with **A+B isolation** | roots outside `workspaceRoot` (Option A) AND dedicated UID (Option B); an in-workspace layout is NOT O3 and permits no closure claim |
| A2 | `state/projects/**` extension implemented | daemon owns all three roots (registry + audit + projects) |
| A3 | Write path is fully switched | no direct-write path to the three roots remains reachable; static proof `O3-FC-005` (grep shows only daemon-client calls) |
| A4 | No silent fallback | daemon down ⇒ `WRITER_UNAVAILABLE`; writes block; `O3-FC-001/006` pass; a fallback is a design violation |
| A5 | Verification passes | `O3-ACCEPTANCE-001..047` (equivalently the FINAL 0004 suite: O3-DAEMON-001..010, O3-IPC-001..008, O3-ISO-001..006, O3-MIG-001..006, O3-REC-001..006, O3-FC-001..006, O3-SOCK-001..004, O3-HON-001..005) in a throwaway temp root; plus full G10 suite + `validate_config` + full Phase-5 regression green |
| A6 | Human approval (H3 + H4 + H5) | closure decision is a Human decision; no test makes it |

**Per-root closure after O3 (only when A1–A6 hold):**

| Root | V1 state | After O3 | Class |
|---|---|---|---|
| `state/registry/**` | gate-DENIED; raw bypass OPEN | sandbox hard-denies all session writes; daemon sole writer | **CLOSED** (conditional) |
| `audit/**` | gate-DENIED; raw bypass OPEN | same | **CLOSED** (conditional) |
| `state/projects/**` | ALLOWED at gate; CAS-detected | same | **CLOSED** (conditional, only with the projects extension) |

**Accepted residuals after O3 (recorded, not regressions):** T4 daemon-compromise single point (controlled, least-privileged, audited, recoverable); T5 availability (writes blocked while daemon down — fail-closed by design); T8 detection without signing key (unchanged from V1).

---

## 7. Exact rollback conditions

**Reversibility: MEDIUM** (the write path is the most sensitive surface). **Precondition (mandatory):** byte-for-byte pre-change backups with recorded SHA-256 of every file Phase B changes — `control/execution_gate.py`, `orchestrator/runtime/{store,delegation,audit}.py`, and the daemon config. Without these, rollback is **not authorized**.

**Trigger conditions (any ⇒ rollback):**
1. Any acceptance criterion A1–A5 fails and is not remediable in-window.
2. Migration continuity breaks during/after Phase B: SHA-256 mismatch, audit chain break, event-id gap/re-allocation, CAS version mismatch.
3. A dual-writer window is detected during cutover (threat model T6).
4. Daemon fail-closed outage exceeds the operator's tolerance and cannot be recovered by restart.
5. Human rejects closure at H5.

**Rollback sequence (file-level, no git):**
1. Stop the daemon; disable its service unit.
2. Restore the four control-plane files from the pre-change backups.
3. Restore `state/registry/`, `state/projects/`, `audit/` to the session workspace (or restore ownership/permissions).
4. Verify audit chain + hash sidecar + CAS versions intact (migration continuity check).
5. Restart the affected orchestrator processes.
6. Run `tests/validate_config.py` + full G10 suite (assertions for the pre-O3 actor set `{zeko, cto}`).
7. Audit the rollback event.

---

## 8. What remains blocking after O3 (if anything)

**G10 itself:** if A1–A6 all hold, the G10 **prevention** gap closes for all three roots — G10 would be re-derived **CLOSED**. **G10 closure is necessary but NOT sufficient for production.**

| Item | Status after O3 | Class |
|---|---|---|
| G10 prevention gap (3 roots) | closed only if A1–A6 hold | CLOSED (conditional) |
| **G13 prompt-injection** | deterministic defenses verified (111 tests); live DSH child behavior + DSH driver-internal isolation **UNKNOWN**; blocking for any injection claim | **OPEN / UNKNOWN — BLOCKING** |
| **L3 independent verification** | zero controls L3; same-UID sandbox (IO-2 fails honestly) prevents any L3 claim | **BLOCKED** (B3) |
| D4/D7 live bridge marker (`DSH_LIVE_BRIDGE_ACTIVE`) | unset; live dispatch + live variants blocked | **BLOCKED** (B1) |
| Approval answerer path | answerer present by composition; E2E approval status UNKNOWN; interactive/HIGH-risk + L3 signing blocked | **BLOCKED** (B2) / UNKNOWN |
| HIGH-risk independent verification (VER-2) | independent measurement channel not built | **BLOCKED** (B7) |
| Production-wired approval path / session-policy drift guard | not automated | **BLOCKED** (B8) |
| Provider 429 backoff (REC-G4-1), baseline guard, CI/CD | accepted operational deferrals | **DEFERRED** |
| **Production deployment** | **NOT STARTED / NOT PRODUCTION-READY** — remains blocked by G13, B1/B2/B3, L3, VER-2, B8 regardless of O3 | **BLOCKED** |
| Audit-integrity evidence drift | regression counts reported inconsistently across final docs (R1/R2/R13 of the evidence-consistency audit) | OPEN (documentation; does not change verdicts) |

**Conclusion:** after O3 (only when A1–A6 all hold), the G10 prevention gap would be closed, but production remains **BLOCKED** — G13 (OPEN/UNKNOWN), the live-DSH bridge/approval conditions (B1/B2), the same-UID L3 blocker (B3), VER-2 (B7), and the approval-path/drift guard (B8) are independent of O3 and remain unsatisfied. O3 unblocks exactly one gate: G10. No G10 closure is claimed today; G10 remains OPEN / BLOCKING.

---

## 9. Honesty statement

1. **O3 is NOT implemented.** This package is a decision/handoff artifact. No daemon code was written; `control/*`, `orchestrator/*`, `state/*`, `audit/*`, DSH core, session policy, role capabilities, and the live composition are unchanged (re-verified this session: actor set `{zeko, cto}` from current config).
2. **No closure of G10 is claimed.** G10 remains OPEN / BLOCKING. All per-root closure statements are conditional on A1–A6 and Human approval.
3. **No re-audit of the whole project was performed.** Only the evidence listed in the header was read; the evidence-consistency audit findings (R1/R2/R13) are cited as documented facts, not re-verified or reconciled here.
4. **The `state/projects/**` extension is stated explicitly** as a separate Human decision (H4); it is not assumed.
5. **Rollback is file-level (no git repository)** — stated so operators never assume `git revert`.
6. **No test failure was hidden or downgraded.** Test counts are cited as observed in the source documents.
7. **Production impact is stated without hedging**: G10 blocks production until closed; after O3, production remains blocked by the non-G10 conditions in §8.

---

## 10. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/decision/0001-g10-o3-operator-decision-package.md` (this file) + `tests/g10/decision/test_g10_operator_decision_package.py`.

**Not modified (verified):** DSH core, DSH profiles/presets, session policy, live composition `$DSH_HOME/profiles/web/cordis.patch.yml`, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/`, and all other `docs/`. No daemon implemented. No write path switched. No role boundary changed. No closure of G10 claimed. No production deployment started.

---

*Status: OPERATOR DECISION PACKAGE. G10 residual after O5: raw-write actor set `{zeko, cto}`; prevention absent at DSH layer; containment = detection. O3 is the only in-project hard-isolation closure arm (A+B isolation, out-of-workspace root, dedicated UID, fail-closed, projects extension). Human decisions required: H3 (approve O3), H4 (approve projects extension), H5 (post-verification closure — DEFERRED). 9 infrastructure prerequisites, 7 of them UNMET/BLOCKED. Sequence: approvals → Phase A prepare → Phase B switch (freeze) → Phase C verify → residual re-derivation → Human closure decision. Acceptance: O3-ACCEPTANCE-001..047 / FINAL 0004 suite + the six §4.1 conditions; per-root CLOSED only under A1–A6. Rollback: file-level, preconditioned on pre-change SHA-256 backups, 5 trigger conditions. After O3 (under A1–A6 only): the G10 prevention gap would be closed, but production remains BLOCKED by G13 (OPEN/UNKNOWN), B1/B2/B3/B7/B8, and L3 NOT CLAIMED. No closure claimed today; nothing implemented; G10 remains OPEN / BLOCKING.*

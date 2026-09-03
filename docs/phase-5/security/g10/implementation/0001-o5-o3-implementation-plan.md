# G10 O5/O3 Implementation Preparation — Smallest Safe Implementation Plan

> **STATUS UPDATE (post-approval):** The Human **APPROVED O5** (remove `write`/`edit`
> from `somad` and `nova`) **as a containment step**, and **HOLD O3** (dedicated
> registry/audit writer process). **O5 WAS APPLIED** per the approved
> composition-change procedure in this session — see
> `docs/phase-5/security/g10/implementation/0002-o5-application-record.md`
> (backups, hashes, verification, rollback). **G10 remains OPEN / BLOCKING for
> production; no closure of prevention is claimed.** The body below remains the
> historical planning artifact; its §1 actor set reflects the **pre-O5 snapshot**
> (`{zeko, cto, somad, nova}`) and is superseded by 0002's post-O5 record
> (`{zeko, cto}`).

- **Milestone**: Phase 5 / Session E — G10 O5/O3 IMPLEMENTATION PREPARATION
- **Status**: IMPLEMENTATION PLAN (preparation; **superseded by 0002-o5-application-record.md after Human approval of O5**; **G10 remains OPEN / BLOCKING**; no closure claimed)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified: `package.json` → `0.1.1-rc.2`)
- **Scope (write-only)**: `docs/phase-5/security/g10/implementation/` + `tests/g10/planning/`. **No DSH modification, no session-policy change, no config/role/control/orchestrator/state/audit change, no live composition change, no production code change, no closure claim.**
- **Companion**: `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (decision record: O5 → O3 → O4) · `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (Session C) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5) · `docs/phase-5/final/0002-g10-formal-residual-proof.md` (R, §1) · `docs/adr/0002-registry-protection-mechanism.md` (Option B, consequence 4) · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · `agents/{somad,nova}/policy.yaml` · `control/execution_gate.py` · `orchestrator/runtime/{audit,store,delegation}.py` · `tests/validate_config.py` · `tests/g10/` (Session C + final suites) · live composition `$DSH_HOME/profiles/web/cordis.patch.yml` (read-only) · DSH checkout `/home/administrator/deepseek-harness` (read-only).
- **Question this session answers**: *What is the smallest safe implementation plan for O5 (remove write/edit from somad/nova) and O3 (dedicated registry/audit writer process with isolated workspace/UID)?* This session **prepares** the plan; **nothing is applied**.

---

## 1. Current state (re-verified this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` (checkout, read-only) |
| Sandbox | **per-session**, not per-agent; `workspace-write` writable roots = `[workspaceRoot, '/tmp', tmpdir()]` | `roots.ts:52–55`; `child-agent.ts:177–204` |
| toolFilter | **tool-name-level only**, never path-level | `tools/index.ts:680–690` |
| Per-path / per-agent sandbox differentiation | **ABSENT** (negative grep) | checkout-wide |
| Raw-write actor set (current config) | `{zeko, cto, somad, nova}` — somad/nova: `write`/`edit` in allow, `bash` denied; zeko/cto: `bash` + `write`/`edit` in allow | `config/role-preset-mapping.yaml`; `config/tool-subagent-instances.yaml`; live `cordis.patch.yml` |
| Read-only roles | `{badsector, cfo, kai}` (bash/edit/write denied) | same |
| Orchestrator | `edit/write/bash` allowed B-lite, always through the execution gate | `role-preset-mapping.yaml` orchestrator block |
| L1 gate | `control/execution_gate.py::authorize_write` — PROTECTED `state/registry`+`audit`, per-channel `SANCTIONED_ROOTS`, traversal/symlink/prefix fail-closed | `execution_gate.py:57,69–72,205–261` |
| Detection stack | append-only ledger + cumulative SHA-256 chain + sidecar + CAS/version monotonic | `audit/helpers/*`, `state/helpers/*` |
| Live composition | 7 `subagent_<id>` rows mounted in `$DSH_HOME/profiles/web/cordis.patch.yml` (outside the workspace) | live composition (read-only) |
| G10 test suites | Session C (39) + final (10) = **49 passed** (re-run this session) | `pytest tests/g10/ -q` → `49 passed` |
| VCS | **no git repo** — rollback must be file-level backups, not git operations | `git status` → fatal: not a repository |

**The residual (R), unchanged and re-verified (final/0002 §1):** a raw-write-capable role (`{zeko, cto, somad, nova}`) can place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. Prevention at the DSH layer is **absent**; containment = detection at the project layer (L1 gate + append-only + hash chain + CAS). **G10 remains OPEN / BLOCKING for production.**

---

## 2. O5 — remove `write`/`edit` from `somad` and `nova`

### 2.1 O5 exact files that would change

| # | File | Exact change |
|---|---|---|
| 1 | `config/role-preset-mapping.yaml` | `roles[].somad.tool_filter.allow` — remove `edit`, `write` (current allow: `[read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]` → without `edit, write`); same for `roles[].nova.tool_filter.allow` (current: `[read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, skill, exit_plan_mode, todo_write]` → without `edit, write`). Update the `notes` line for each. |
| 2 | `config/tool-subagent-instances.yaml` | `insert_draft[].tool-subagent-somad.config.toolFilter.allow` and `insert_draft[].tool-subagent-nova.config.toolFilter.allow` — remove `edit`, `write` (must stay byte-consistent with #1 — `tests/validate_config.py` asserts `instance == mapping`, lines 270–271). |
| 3 | `agents/somad/policy.yaml` | `tool_filter.allow` — remove `edit`, `write`; update `notes` (no longer "drafting in workspace (edit/write)"; drafting becomes channel-routed). |
| 4 | `agents/nova/policy.yaml` | `tool_filter.allow` — remove `edit`, `write`; update `notes` (manuscript work becomes channel-routed). |
| 5 | `$DSH_HOME/profiles/web/cordis.patch.yml` (**outside workspace**) | `tool-subagent-somad` and `tool-subagent-nova` rows — remove `edit`, `write` from `toolFilter.allow`. **This is the live enforcement point**; without it the config files are inert. Requires the **D4/D7 controlled composition exception** (ADR 0001 Decision 4/7 — HUMAN_PENDING) because it is a role-boundary/live-composition change. |
| 6 | `tests/g10/test_role_restrictions.py` | `test_raw_write_capable_roles_identified` (line 39): expected set `{zeko, cto, somad, nova}` → `{zeko, cto}`; `test_raw_write_roles_carry_tool_surface` stays valid for `{zeko, cto}`. |
| 7 | `tests/g10/final/test_g10_final_decision.py` | `test_actor_set_derived_from_current_config` (line 123): `{zeko, cto, somad, nova}` → `{zeko, cto}`. |
| 8 | `tests/phase5_role_validation/harness.py` | `WRITE_CAPABLE_ROLES = ("zeko", "cto", "somad", "nova")` (line 69) → `("zeko", "cto")`. |
| 9 | `tests/live_dsh/test_role_adapters.py` | `test_write_capable_roles_allow_write` (line 42–46): drop `somad`, `nova` from the asserted role list (they no longer allow `write`). |
| 10 | `tests/authorization/test_authority.py` (line 395) | Optional: the role tuple `("zeko", "cto", "somad", "nova")` there is only iterated to check `allow ⊆ VERIFIED_TOOLS`; it still passes with `write`/`edit` removed (smaller allow stays a subset). Update for accuracy only if desired; **not required**. |

**Consistency requirement (exact):** `tests/validate_config.py` asserts `mapping == policy` (allow/deny) for every role and `instance == mapping` for every `subagent_<id>` row. Files #1–#4 must therefore change **together in one step** or validation fails loudly. The live patch (#5) must match the config exactly to have effect.

**Not changed by O5:** `config/permissions.yaml` (capability vocabulary; `social_drafting`/`novel_editing` capabilities are conceptual, not tool grants), `control/`, `orchestrator/`, `state/`, `audit/`, `schemas/`, DSH core/presets/session policy, `agents/zeko/`, `agents/cto/`.

### 2.2 O5 exact role capability impact

| Role | Before O5 (raw fs surface) | After O5 (raw fs surface) | Net effect |
|---|---|---|---|
| `somad` | `write`, `edit` (bash already denied) | **none** — read/read_image/glob/grep/job_*/web_search/skill/todo only | **read-only at the DSH tool level**; drafting content must route through the project channel (orchestrator persists via `write_through`) |
| `nova` | `write`, `edit` (bash already denied) | **none** — read/read_image/glob/grep/job_*/skill/todo only | **read-only at the DSH tool level**; manuscript content must route through the project channel |
| `zeko` | `bash`, `write`, `edit` | unchanged | **still raw-write-capable** (residual actor) |
| `cto` | `bash`, `write`, `edit` | unchanged | **still raw-write-capable** (residual actor) |
| `cfo`/`kai`/`badsector` | none (already read-only) | unchanged | no change |

**Precise statement:** O5 makes `somad` and `nova` read-only at the DSH layer (no raw filesystem mutation tool). It **shrinks the raw-write actor set from `{zeko, cto, somad, nova}` to `{zeko, cto}`**. It is a **reduction**, never a closure, of R — `{zeko, cto}` retain raw `write`/`edit`/`bash` and remain able to reach `state/registry/**`/`audit/**` in principle. This is **containment by surface reduction, not hard isolation** (final/0001 §2.4).

### 2.3 O5 exact control-flow impact

- **Zero change to the production write path.** `control/execution_gate.py`, `orchestrator/runtime/{store,audit,delegation}.py`, `control/delegation.py` are untouched. The L1 gate, `SANCTIONED_ROOTS`, CAS, and audit chain behave identically.
- **Change is at the DSH toolFilter layer only:** `somad`/`nova` instances no longer expose `write`/`edit` to their agents. Any draft they produce must be returned to the orchestrator and persisted through the project channel (`write_through`, which is already gated). This changes their **workflow** (content handoff), not the runtime control flow.
- **Live effect requires a session restart/reload** (web profile has HMR disabled for these rows; both apply and rollback need a reload — verified in `docs/phase-1/0003` §8.3).

### 2.4 O5 rollback procedure

Because the project is **not a git repository**, rollback is **file-level backup/restore** (no git revert).

1. Before applying: take byte-for-byte backups of the 5 changed files (#1–#5) with recorded SHA-256 (mirror the mandatory-backup discipline of `docs/phase-1/0003` §8).
2. Restore order (reverse of apply): restore `$DSH_HOME/profiles/web/cordis.patch.yml` from backup → restore `agents/{somad,nova}/policy.yaml` → restore `config/{role-preset-mapping,tool-subagent-instances}.yaml`.
3. Reload/restart the DSH session (stand-alone mounts drop on reload).
4. Verify: `ctx.agentPresets`-level resolution + `subagent_somad`/`subagent_nova` tool schema re-exposes `write`/`edit`; `tests/validate_config.py` passes; `tests/g10/` actor-set tests pass again with `{zeko, cto, somad, nova}`.
5. Audit the rollback event. **Reversibility: HIGH** — a reversible config/composition change.

### 2.5 O5 test requirements

1. **Update existing actor-set assertions** (#6–#9 above) to the post-O5 set `{zeko, cto}` and re-run:
   - `tests/g10/` (49 → expected 49 still, assertions updated)
   - `tests/phase5_role_validation/` (28)
   - `tests/live_dsh/` (config-driven adapters; assert updated)
   - `tests/authorization/` (178 — no change expected)
   - `tests/validate_config.py` (mapping==policy==instance consistency)
2. **New deterministic guards** (in `tests/g10/`): assert `somad`/`nova` deny `write` and `edit`; assert `{zeko, cto}` is exactly the raw-write set; assert `allow ∩ deny = ∅` still holds; assert the **live patch** `cordis.patch.yml` (when mounted) matches config for somad/nova.
3. **Live probe (when mount active, `DSH_LIVE_BRIDGE_ACTIVE=1`)**: spawn `subagent_somad`/`subagent_nova`, assert `write`/`edit` are absent from the child tool schema and a `write` tool call is REJECTED (ISO-LIVE-002 class). **Not runnable this session** (mount/answerer conditions, closure matrix B1–B2).
4. **Honesty guard**: no test may claim G10 closed after O5; the residual actor set is still non-empty (`{zeko, cto}`).

### 2.6 O5 migration requirements

- **No data migration**: `state/`, `audit/`, `state/registry/` contents are untouched; no schema or path change.
- **Workflow migration (operational, not code)**: any existing workflow that expects `somad`/`nova` to write files directly in the workspace must change to a channel-routed handoff (role returns content → orchestrator persists via `write_through`). No production artifact depends on somad/nova raw writes (they are drafting roles).
- **Documentation migration**: `agents/somad/policy.yaml` + `agents/nova/policy.yaml` notes, and the role sections in `config/role-preset-mapping.yaml`, must be updated in the same change (consistency rules).
- **Composition migration**: the change to `$DSH_HOME/profiles/web/cordis.patch.yml` is a **controlled D4/D7 composition exception** — a new Human-approved change request, per the precedent `docs/phase-1/0003`.

### 2.7 O5 — independence, authority semantics, production impact

| Question | Answer |
|---|---|
| **Can O5 be applied independently?** | **YES.** O5 is config + policy + live-patch only; no dependency on O3, no architecture change, no code change. It is the first, cheapest stage of the minimum safe path (final/0001 §4 stage 2). Its only prerequisite is **Human approval** of the D4/D7 composition exception. |
| **Does O5 change authority semantics?** | **NO.** Authority = delegated scope + execution gate + single-writer registry contract (ADR 0002). `toolFilter` is a **capability** boundary (AGENTS.md: capability ≠ permission ≠ authority). Removing raw-write tools from somad/nova removes *capability*; it does not grant, revoke, or re-scope any *authority*. The L1 gate, delegation scoping, and single-writer contract are untouched. |
| **Is production unblocked after O5 alone?** | **NO.** G10 stays **OPEN / BLOCKING**. `{zeko, cto}` remain raw-write-capable; R persists for those roles (final/0001 §2.4, §7; closure matrix blocker B5). O5 alone is containment-by-reduction, not hard isolation. |
| **What O5 does NOT do** | It does not close R, does not change the sandbox, does not add per-path isolation, does not protect `state/registry`/`audit` from `{zeko, cto}`, does not alter the residual proof (final/0002) for the two remaining actors. |

---

## 3. O3 — dedicated registry/audit writer process (isolated workspace/UID)

### 3.1 O3 exact files that would change (architecture change — YES)

| # | File | Change |
|---|---|---|
| 1 | **NEW daemon module** (e.g. `registry_writer/` or `control/registry_writer/`) | Out-of-process writer: entrypoint, own workspace root (or own UID/credential), owns `state/registry/**` and `audit/**`; only it may write those roots. Implements request handling (registry write, audit append) with **authn/authz** so only the sanctioned control-plane channel may drive it. |
| 2 | **NEW IPC contract module** | Wire protocol between the control plane and the daemon (Unix socket / stdio / HTTP); request schema; typed errors; fail-closed when the daemon is unavailable. |
| 3 | `control/execution_gate.py` | `registry_write()` (lines 282–290) and `audit_append()` (lines 293–305) become **clients of the daemon** via the IPC contract, OR the gate keeps the same public API but the actual filesystem mutation is performed only by the daemon process. The gate's path semantics (`SANCTIONED_ROOTS`, protected-root matching) must be preserved **in the daemon** (defense in depth: validate on both sides). |
| 4 | `orchestrator/runtime/audit.py` | `audit_append` import/call (lines 40, 189) now resolves to the daemon-backed channel (public API unchanged). Event-id allocation stays in the control plane; the daemon performs the append. |
| 5 | `orchestrator/runtime/delegation.py` | `FileDelegationProvider` reads `state/registry/delegations.json` + `revocations.json` (lines 53–86). Read path stays as-is **only if** the daemon leaves registry data readable at the same location; otherwise reads route through the daemon's read API. |
| 6 | **NEW deployment/service files** | Process manager unit (systemd/supervisor-style), launcher with isolated UID/workspace, health check, backup/restore of the daemon-owned roots. |
| 7 | **NEW config** (e.g. `config/registry-writer.yaml` or env) | Daemon endpoint/credential, workspace root, UID; fail-closed defaults. |
| 8 | **NEW tests** (`tests/g10/`, and/or the O3 test suite) | Daemon unit tests (single-writer, path scoping, authn/authz, fail-closed), gate↔daemon integration, migration/continuity tests, recovery. |
| 9 | `docs/adr/0002` | Addendum recording the executed consequence-4 mechanism (dedicated registry/audit writer) once applied. |
| 10 | `docs/phase-5/security/g10/` | Update residual statement: R closes for `state/registry/**` + `audit/**` **only**; `state/projects/**` remains CAS-detected, not gate/isolation-denied (Session C §2.3 precision) — **O3 does not by itself close G10 for `state/projects/**` unless extended**. |

**No DSH core change.** O3 is a project-layer out-of-process process (ADR 0002 consequence 4; final/0001 §2.2). It does **not** modify DSH core, presets, sandbox mode, or session policy.

### 3.2 O3 exact role capability impact

- **All seven roles (including zeko/cto)**: raw `bash`/`write`/`edit` to `state/registry/**` and `audit/**` becomes **denied at the filesystem boundary** — the roots live outside the session's writable set (daemon-owned path) or under a different UID. Even a raw write from `{zeko, cto}` cannot land.
- **Orchestrator**: direct fs write to those roots is removed (same boundary). Its access becomes **IPC to the daemon** via the sanctioned channel.
- **No role gains capability.** This is pure isolation of the authority source.

### 3.3 O3 exact control-flow impact

- **Write path rewired**: `registry_write()`/`audit_append()` no longer write directly; they marshal a request through the IPC contract to the daemon, which validates (path scope, schema, version/CAS, append-only) and performs the mutation under its own credential.
- **Fail-closed**: daemon down ⇒ registry/audit writes **BLOCKED** (never a silent fallback to direct write — a fallback would defeat the isolation). Orchestrator flows that depend on registry/audit persistence surface a typed error and stop (consistent with the project's fail-closed posture).
- **Detection stack preserved**: the daemon performs the same append-only + hash-chain + CAS logic (or reuses the existing `audit/helpers/*`, `state/helpers/*` modules in-process — they are importable; no change to their semantics).
- **Single point of failure introduced**: registry/audit writes depend on daemon availability ⇒ requires health checks, restart policy, and recovery procedure (operational cost — final/0001 §2.2, "operationally heavier").

### 3.4 O3 rollback procedure

1. Stop the daemon; remove/disable its service unit.
2. Restore `control/execution_gate.py` registry/audit channels to direct-write behavior from the pre-change backup (or a git-independent byte backup).
3. Restore file ownership/location of `state/registry/**` + `audit/**` to the orchestrator's credential, **after** verifying the audit chain + hash sidecar + CAS versions are intact (migration continuity check).
4. Reload/restart the affected orchestrator processes; verify gate path checks and the 49-test G10 suite.
5. Audit the rollback. **Reversibility: MEDIUM** — a daemon can be stopped and the write path reverted, but it touches the authority write path (the most sensitive surface); staged rollout required (final/0001 §2.2).

### 3.5 O3 test requirements

1. **Daemon unit tests**: only the sanctioned channel may drive a write (authn/authz); path scoping (`registry_write`→`state/registry/**` only, `audit_append`→`audit/**` only, no cross-root); protected-path DENY for any non-sanctioned request; traversal/symlink/absolute-outside DENY (reuse the existing gate semantics); single-writer/CAS enforced in the daemon.
2. **Fail-closed tests**: daemon unavailable ⇒ registry/audit writes BLOCKED with a typed error; **no** silent fallback path.
3. **Isolation test**: a raw write attempt to the daemon-owned roots from the session (mirroring `tests/g10/test_dsh_layer_isolation.py`) is denied by the filesystem boundary; the residual probe that currently "lands" (`test_raw_write_reaches_protected_mirror`) is re-derived against the new layout.
4. **Migration/continuity tests**: pre-existing audit ledger + hash sidecar + state versions remain valid across the migration (no chain break); append-only and CAS invariants hold through the daemon.
5. **Recovery test**: daemon restart with intact ledger resumes appends at the correct event-id sequence (reuse `audit.py::allocate_event_id` semantics).
6. **Honesty guards**: O3 tests must assert the residual scope precisely — closed for `state/registry/**`+`audit/**`; **`state/projects/**` remains CAS-detected, not isolation-denied** — so no G10 closure claim is made.

### 3.6 O3 migration requirements

- **Data migration**: move/keep `state/registry/**` and `audit/**` under daemon ownership; verify audit chain sidecar + cumulative hash + state CAS versions survive byte-identically (or re-derived consistently). Backup before and verify after.
- **Path/credential migration**: the daemon runs under an isolated workspace root (or UID); all existing orchestrator code paths that reference these roots by path must either keep read access or switch to the daemon read API (`orchestrator/runtime/delegation.py`, `orchestrator/runtime/audit.py`, `state/helpers/safe_read` callers).
- **Deployment migration**: new service lifecycle (start/stop/restart/health/backup), integration with the session's runtime start-up so the daemon is up before any registry/audit write.
- **No schema migration**: delegation/audit schemas unchanged; only the execution location and credential change.

### 3.7 O3 — architecture, authority semantics, production impact

| Question | Answer |
|---|---|
| **Does O3 require architecture changes?** | **YES.** A new out-of-process writer (daemon) with isolated workspace/UID, an IPC contract, authn/authz, deployment/service management, health checks, and a write-path rewrite of `registry_write`/`audit_append`. It is an infrastructure/composition change (ADR 0002 consequence 4) — the strongest closure arm available without DSH change (final/0001 §2.2). |
| **Does O3 change authority semantics?** | **NO.** The single-writer contract (ADR 0002 Option B) is preserved: only the sanctioned control-plane channel may drive registry/audit writes. The daemon is an **execution proxy under the same authority contract**, not an independent authority source; it authenticates and path-scopes every request. Authority decisions remain in the control plane (delegation scoping + execution gate). |
| **Does O3 close G10?** | **Not completely, by itself, as scoped.** O3 closes R for `state/registry/**` and `audit/**` (hard isolation of the authority source). It does **not** close G10 for `state/projects/**` (CAS-detected, not isolation-denied — Session C §2.3) unless the daemon scope is extended. **No G10 CLOSED claim is made anywhere in this plan.** |
| **Is production unblocked after O3?** | **Not by this plan alone.** G10 remains OPEN/BLOCKING until a Human applies a closure arm and the residual is re-derived (final/0002 §6). O3, when applied, hard-isolates the registry/audit roots but does not by itself resolve G13 (injection, OPEN/UNKNOWN) or the other production blockers (closure matrix §5: B1/B2/B6/B7/B8). |

---

## 4. Cross-cutting determinations (exact answers to the brief)

| # | Determination | Answer |
|---|---|---|
| 1 | Exact files O5 would change | §2.1 — 5 applied files (#1–#5, incl. the live patch **outside** the workspace) + 4–5 test files (#6–#10); all change together (consistency). |
| 2 | Exact files O3 would change | §3.1 — new daemon + IPC + deployment + config, `execution_gate.py` channels, `orchestrator/runtime/{audit,delegation}.py`, tests, ADR addendum, residual-doc update. |
| 3 | Exact role capability impact | O5: somad/nova → read-only at DSH layer; actor set `{zeko,cto,somad,nova}` → `{zeko,cto}`. O3: all roles lose raw access to registry/audit roots. |
| 4 | Exact control-flow impact | O5: none to the runtime; DSH toolFilter surface only + workflow handoff. O3: registry/audit write path rewired through the daemon; fail-closed when down. |
| 5 | Rollback procedure | O5: file-backup restore (no git) + session reload; HIGH reversibility. O3: stop daemon + revert write path + restore ownership; MEDIUM reversibility. |
| 6 | Test requirements | §2.5 (O5) / §3.5 (O3). |
| 7 | Migration requirements | §2.6 (O5: workflow/doc/composition only) / §3.6 (O3: data + path/credential + deployment). |
| 8 | O5 independently applicable? | **YES** — config-only, first stage, Human-approved D4/D7 exception required. |
| 9 | O3 requires architecture changes? | **YES** — new out-of-process writer + IPC + deployment. |
| 10 | Authority semantics changed? | **NEITHER O5 NOR O3 changes authority semantics** — both are capability/infrastructure changes under the unchanged single-writer + delegation + execution-gate contract. |
| 11 | Production blocked after O5 alone? | **YES — still BLOCKED.** `{zeko, cto}` remain raw-write-capable; G10 stays OPEN (containment reduced, not closed). |

---

## 5. Sequencing and gates (unchanged from final/0001 §4)

| Stage | Action | Gate | Prerequisite |
|---|---|---|---|
| 1 | Accept residual (containment = detection); G10 OPEN/BLOCKING | Human decision | done in final/0001 |
| 2 | **O5** — remove write/edit from somad/nova | Human-approved D4/D7 composition exception | ADR 0001 Decision 4/7 approval |
| 3 | **O3** — dedicated registry/audit writer process | Human-approved infrastructure change | ADR 0002 consequence 4; ops window |
| 4 | **O4** — upstream DSH per-agent/path-level sandbox | DSH capability release | upstream; re-derive residual |

**Minimum safe plan in one sentence:** *apply O5 first as the cheapest reversible surface reduction (Human-approved composition exception), then O3 as the hard-isolation arm for the registry/audit authority source (Human-approved infrastructure change) — and file O4 as the exact upstream DSH requirement — while keeping G10 OPEN/BLOCKING and re-deriving the residual at every stage.*

---

## 6. Honesty statement

1. **Nothing was implemented.** This session produced an implementation plan and planning tests only. No DSH/core/config/policy/role/control/orchestrator/state/audit/live-composition change was made; the DSH checkout and the live `cordis.patch.yml` were read-only.
2. **No closure of prevention is claimed.** G10 remains OPEN / BLOCKING for production. O5 is containment-by-reduction; O3 (as scoped) hard-isolates `state/registry/**`+`audit/**` but not `state/projects/**`, and does not by itself resolve G13 or the other production blockers.
3. **The residual actor set is derived from the current config** (`{zeko, cto, somad, nova}`), not assumed; O5's post-change set (`{zeko, cto}`) is stated as a planned result, not an applied one.
4. **Authority semantics are stated precisely**: neither O5 nor O3 changes who may write the registry; both preserve the single-writer + execution-gate contract.
5. **Rollback is file-level (no git repository)** — stated explicitly so operators do not assume `git revert` is available.
6. **Production impact is unhedged**: production remains blocked after O5 alone, and after O3 alone by this plan's scoping (residual re-derivation still required).
7. **No test failure was hidden or downgraded**: the current G10 suite was re-run (49 passed) and is unchanged; the planning tests assert only the *plan's* honesty, not any applied change.

---

## 7. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/implementation/0001-o5-o3-implementation-plan.md` (this file) + `tests/g10/planning/test_o5_o3_planning.py`.

**Not modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, the live composition `$DSH_HOME/profiles/web/cordis.patch.yml` (read-only), `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/` — unchanged, re-run 49 passed), and all other `docs/`. No implementation. No role-boundary change applied. No closure claim. No production deployment started.

---

*Status: IMPLEMENTATION PLAN (Session E). O5 and O3 prepared but NOT applied. G10 remains OPEN / BLOCKING. O5 = containment-by-reduction (config + policy + live-patch, reversible, Human-approved D4/D7 exception); O3 = hard-isolation arm for registry/audit via a dedicated out-of-process writer (architecture change, Human-approved infrastructure). Neither changes authority semantics. Production remains blocked after O5 alone. No closure of prevention claimed.*

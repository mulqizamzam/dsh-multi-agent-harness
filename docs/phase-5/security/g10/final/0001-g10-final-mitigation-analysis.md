# G10 Final Mitigation Analysis — Minimum Safe Path to Close or Formally Accept

- **Milestone**: Phase 5 / Final / Session A — G10 FINAL MITIGATION ANALYSIS
- **Status**: FINAL DECISION RECORD (analysis + recommendation; **G10 remains OPEN — no prevention closure claimed, no DSH/core/config/policy/role change**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (re-verified: `package.json` → `0.1.1-rc.2`)
- **Scope**: `docs/phase-5/security/g10/final/` + `tests/g10/final/` (write-only). **No DSH modification, no session-policy change, no role-boundary change, no production code change.**
- **Companion**: `docs/phase-5/final/0002-g10-formal-residual-proof.md` (residual proof) · `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (Session C assessment) · `docs/phase-5/security/0001-g10-g13-security-residual-analysis.md` §1 (partial closability) · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, blocker B5) · `docs/phase-5/final/0005-final-security-gate-evidence.md` §1 · `docs/adr/0002-registry-protection-mechanism.md` (Option A/B, consequence 4) · `docs/adr/0001` (Decision 1, Decision 4/7) · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · DSH checkout `/home/administrator/deepseek-harness` (read-only, re-verified) · `tests/g10/` (Session C, re-run 39 passed).

> **Question this session answers:** *What is the minimum safe path to close G10, or to formally accept it?* The answer, with evidence: **the prevention gap cannot be closed inside this project in DSH 0.1.1-rc.2; the minimum safe path is (1) formally accept the residual as an accepted V1 residual with containment = detection, and (2) stage the only two closure arms that do not require DSH-core change (O5 config narrowing, then O3 dedicated registry process), with O4 (per-agent/path-level sandbox) as the only full-prevention arm and the exact upstream DSH requirement.** Nothing is applied in this session; every arm is a Human decision.

---

## 1. Current state (re-verified this session, read-only)

| Fact | Value | Source |
|---|---|---|
| DSH version | `0.1.1-rc.2` | `package.json` |
| Sandbox | **per-session, not per-agent**; `workspace-write` writable roots = `[workspaceRoot, '/tmp', tmpdir()]` | `child-agent.ts:177–204`; `roots.ts:52–55` |
| toolFilter | **tool-name-level only** (`ToolRestriction {allow?, deny?}`), never path-level | `tools/index.ts:680–690` |
| Per-path / per-agent sandbox differentiation | **ABSENT** (negative grep: no `pathAllow`/`pathDeny`/`perPath`/`allowPaths`/`denyPaths`) | checkout-wide grep (0 hits) |
| Raw-write actor set (from current config) | `{zeko, cto, somad, nova}` (bash and/or write/edit in allow) | `config/role-preset-mapping.yaml`; `tests/g10/test_role_restrictions.py` |
| Read-only roles | `{badsector, cfo, kai}` (bash/edit/write denied) | same |
| Orchestrator (root session) | `edit/write/bash` allowed **B-lite** — only project state/audit maintenance and reversible internal actions, always through the execution gate | `config/role-preset-mapping.yaml` orchestrator block |
| D4/D7 live composition | 7 `subagent_<role>` rows mounted in `$DSH_HOME/profiles/web/cordis.patch.yml` | live composition |
| G10 test suite | **39 passed** (Session C suite re-run this session) | `pytest tests/g10/ -q` |

**The residual (R), restated (unchanged, re-verified):** a raw-write-capable role (`zeko`, `cto`, `somad`, `nova`) can place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel. The L1 execution gate (`control/execution_gate.py`) intercepts only channeled writes; DSH provides no per-path or per-agent filesystem interception. R is a **capability-level** residual — proven by negative tests (`tests/g10/test_dsh_layer_isolation.py`, raw writes land) and by the formal proof (`final/0002` §1).

---

## 2. Option evaluation (O2 · O3 · O4 · O5)

Each option is evaluated on six axes. **Constraint:** no option may be applied by this session — every arm requires a Human decision (ADR 0001 Decision 4/7 composition exception, ADR 0002 consequence 4, or upstream DSH); this session only determines the minimum safe path.

### 2.1 O2 — Registry-outside-workspace (relocate `state/registry/**` outside the sandboxed workspace)

| Axis | Assessment |
|---|---|
| **Capability required** | None beyond config/path relocation — the registry moves to a path outside the session sandbox writable roots. **But it is not functional alone**: the orchestrator (root session) shares the same per-session sandbox and must remain the registry's single writer; relocating the registry outside the workspace also removes the orchestrator's own direct write access. |
| **Security strength** | **HIGH in principle** (no session tool, raw or channeled, can write a path outside the writable roots — the sandbox hard-denies it). **NOT ACHIEVABLE ALONE** without per-agent sandbox differentiation (O4) or a dedicated mediating process (O3). |
| **Scope** | Path relocation + rework of every registry read/write path; affects the control plane's single-writer contract (ADR 0002 Option A). |
| **Reversibility** | HIGH (a path move is reversible), but reverting restores the residual. |
| **Operational impact** | MEDIUM–HIGH: all registry access must change; backup/restore, versioning and audit wiring must follow the new location; risk of breaking the orchestrator write path is high without O3/O4. |
| **Achievable without DSH core modification?** | **YES as relocation — NO as a working mitigation.** Rejected for V1 by ADR 0002 (Option A analysis): the shared per-session sandbox means the orchestrator's own writes are blocked too. O2 only becomes viable **paired with O3** (dedicated process mediates writes) or **O4** (per-agent sandbox lets the orchestrator write while specialists cannot). |

**Verdict:** O2 is **not the minimum safe path** — it is strictly dominated by O3 (same isolation, plus a working write path) and by O4 (cleaner, but DSH-gated). Recorded as a fallback only.

### 2.2 O3 — Dedicated protected-path process/workspace (out-of-process registry/audit writer)

| Axis | Assessment |
|---|---|
| **Capability required** | A new process (daemon/service) with its own workspace root **or** its own UID/credential; only that process may write `state/registry/**` and `audit/**`. Agents' (and the orchestrator's direct) writes to those roots are denied at the filesystem boundary — either because the roots live outside the session's writable set, or because the daemon owns them under a different credential. Orchestrator access becomes IPC/API to the daemon instead of direct fs. |
| **Security strength** | **HIGH — the strongest closure arm available without DSH change.** Hard isolation of the authority source: even a raw `bash`/`write`/`edit` call from any role cannot reach a root that is outside its sandbox writable set or owned by another credential. Closes R for ALL raw-write roles, not just some. |
| **Scope** | Infrastructure/composition change (ADR 0002 consequence 4 — the recorded Phase-5 hardening option). New process lifecycle, IPC contract, daemon authn/authz, registry/audit write path rewrite. |
| **Reversibility** | MEDIUM: a daemon can be stopped and the write path reverted, but the change touches the authority write path (the most sensitive surface); requires careful staged rollout. |
| **Operational impact** | **HIGH**: new service to run, monitor, back up and restore; single point of failure for registry writes unless handled; deployment, health checks and recovery procedure needed. |
| **Achievable without DSH core modification?** | **YES** — a project-layer process. This is the only hard-isolation arm that does not require upstream DSH and does not change role boundaries. |

**Verdict:** O3 is the **hard-isolation arm of the minimum safe path** (no DSH change, no role-boundary change). Its cost is operational (new process), which is why it is staged **after** the cheap config narrowing (O5).

### 2.3 O4 — Native DSH path-level / per-agent sandbox

| Axis | Assessment |
|---|---|
| **Capability required** | A DSH capability at the filesystem-tool layer: either (1) a **per-agent sandbox root** — a child's `workspace-write` root scoped to a per-role sub-tree so `state/registry/**`/`audit/**` fall outside the child's writable roots; or (2) a **per-path allow/deny on filesystem tools** — e.g. DENY `state/registry/**`, `audit/**`, `state/projects/**` as write targets for non-writer roles, independent of which raw tool carries the write. |
| **Security strength** | **HIGHEST — the only full-prevention arm.** DSH itself denies the raw write before the project channel is involved; closes R at the layer where it lives (final/0002 §3, §6). |
| **Scope** | Upstream DSH only. Cannot be implemented from inside the project (task scope prohibits DSH modification; ADR 0001 Decision 7 boundary). |
| **Reversibility** | N/A today (capability absent). When available, policy-driven and reversible. |
| **Operational impact** | **LOW once available** — policy-driven, no new process, no write-path rewrite. |
| **Achievable without DSH core modification?** | **NO.** This is the exact upstream DSH requirement (see §5). |

**Verdict:** O4 is the **cleanest and only full-prevention closure arm, but it is a DSH-capability gap** — not available in 0.1.1-rc.2 (re-verified: per-session sandbox, tool-level toolFilter, no path-level differentiation). It is recorded as the exact upstream requirement, not as an option this project can exercise.

### 2.4 O5 — Raw-write surface reduction (narrow the toolFilter allow sets)

| Axis | Assessment |
|---|---|
| **Capability required** | None beyond config: remove `write`/`edit` (and, where viable, `bash`) from roles that do not need raw filesystem mutation, forcing their writes through the project channel (L1 gate). No DSH change. |
| **Security strength** | **MEDIUM — partial only.** Shrinks the raw-write actor set from `{zeko, cto, somad, nova}` to `{zeko, cto}` if `write`/`edit` are removed from somad/nova. It **cannot close R** for zeko/cto, who legitimately need raw write for ops/engineering — removing raw write from them is a capability regression, not a mitigation. It is a **reduction**, never a closure, of the residual. |
| **Scope** | Config-only: toolFilter allow sets in `config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`, and the live `cordis.patch.yml`. **This is a role-boundary change for the affected roles** → requires reopening the D4/D7 composition exception (ADR 0001 Decision 4/7 — HUMAN_PENDING). *[Correction 2026-09-07: the D4/D7 exception was Human-approved and executed on 2026-09-07 (ADR 0001 Revision 3 addendum); O5 was in fact applied 2026-08-31 (see the O5 application record) and amended 2026-09-07 (zeko discriminator, §7 of that record). The HUMAN_PENDING label above is historical.]* |
| **Reversibility** | **HIGH** — a reversible config change. |
| **Operational impact** | LOW–MEDIUM: somad/nova lose direct workspace writes; their content must route through the project channel (execution gate), which changes their workflow. |
| **Achievable without DSH core modification?** | **YES** (config only) — but it changes role boundaries, so it is a **Human decision**, not a project-layer action. |

**Verdict:** O5 is the **cheap, reversible, first-stage reduction** of the minimum safe path — it shrinks the actor set and forces more writes through the gated channel. It does **not** close R for the two roles that legitimately need raw write (zeko/cto), so it must be paired with O3 (hard isolation of the authority source) to reach an acceptably small residual.

---

## 3. G10 FINAL DECISION

**G10 remains OPEN — BLOCKING for production; NOT closable inside this project in DSH 0.1.1-rc.2.**

Decision: **FORMALLY ACCEPT the residual as an accepted V1 residual with containment = detection, and stage the closure arms in the minimum safe order.** This is a *formal acceptance decision* (evidence-backed), **not** a closure claim. The exact words:

1. **Accepted residual (V1):** raw-write-capable roles (`{zeko, cto, somad, nova}`) can in principle reach `state/registry/**`/`audit/**`/`state/projects/**` via raw DSH `bash`/`write`/`edit` calls that bypass the project channel. Containment = **detection at the project layer**: L1 execution gate (channeled DENY, traversal/symlink/absolute-outside fail-closed, prefix-confusion prevention) + append-only audit ledger + cumulative SHA-256 hash chain + state CAS/version monotonicity. Tampering is **detectable**, not preventable, at the DSH layer.
2. **G10 stays OPEN and BLOCKING for production** until a Human decision applies one of the closure arms — nothing in this document changes that (consistent with `final/0005` §1, §4; closure matrix blocker B5).
3. **No prevention closure is claimed.** No DSH/core/config/policy/role change was made; the session scope prohibits it.

---

## 4. Recommended mitigation (minimum safe path, staged)

| Stage | Action | Type | Closes/reduces | Owner | Prerequisite |
|---|---|---|---|---|---|
| **1 (now)** | **Formally accept the residual** — record R as accepted V1 residual with containment = detection; keep G10 OPEN/BLOCKING for production. | Decision | none (formal acceptance) | Human | — |
| **2 (next)** | **O5 — narrow raw-write surface**: remove `write`/`edit` from `somad`/`nova` (roles that draft but need not raw-write; route their writes through the project channel). Shrinks actor set to `{zeko, cto}`. | Config (Human-approved D4/D7 exception reopen) | reduces actor set; more writes gated | Human/operator | ADR 0001 Decision 4/7 approval |
| **3 (when ops allows)** | **O3 — dedicated registry/audit process**: out-of-process writer with its own workspace root/credential; only it writes `state/registry/**` + `audit/**`; orchestrator access via IPC. **Hard isolation of the authority source — closes R for all roles without DSH change.** | Infrastructure (ADR 0002 consequence 4) | closes R (hard) | Human/operator | approved infrastructure change |
| **4 (upstream)** | **O4 — DSH per-agent/path-level sandbox**: file the exact upstream requirement (§5) and re-derive the residual against the new DSH version when available. | DSH capability | full prevention | DSH upstream | upstream release |
| **Fallback** | **O2 — registry relocation** only if O3 is infeasible and O4 remains absent; must still pair with a mediating process or per-agent sandbox to keep the orchestrator's write path working. | Config/infra | partial (alone) | Human | — |

**Minimum safe path in one sentence:** *accept the residual now (detection = containment), narrow the raw-write surface next (O5), hard-isolate the authority source after that (O3), and file O4 as the exact upstream DSH requirement — because in 0.1.1-rc.2 the prevention gap can only be accepted or reduced, not closed, from inside this project.*

---

## 5. Exact upstream DSH requirement (if unresolved — it is)

**Requirement (exact):** DSH must provide, at the filesystem-tool layer, one of:

1. **Per-agent sandbox root.** A delegated child's `workspace-write` writable root is scoped to a per-role sub-tree (instead of inheriting the whole parent-session workspace root), so `state/registry/**`, `audit/**`, `state/projects/**` fall **outside** the child's writable roots and are denied by the sandbox itself. Today `writableRoots()` returns `[workspaceRoot, '/tmp', tmpdir()]` for the whole delegation chain (`packages/sandbox/sandbox/src/roots.ts:52–55`); `captureDelegatedPolicyOverrides` seeds a single mode captured from the parent session (`packages/subagent/subagent/src/child-agent.ts:177–204`).
2. **Per-path allow/deny on filesystem tools.** A path-level restriction (e.g. DENY `state/registry/**`, `audit/**`, `state/projects/**` as write targets for non-writer roles) applied by DSH before any tool mutation, independent of which raw tool carries the write (`write`, `edit`, or `bash`). Today `ToolRestriction` filters by global tool **name** only (`packages/core/tools/src/index.ts:680–690`), and `write`/`edit` (tool-fs) and `bash` (tool-bash) resolve the same per-session sandbox.

**Precondition to exercise:** upgrade to a DSH release that provides either capability, then **re-derive the residual statement against the new version** (the current proof is pinned to 0.1.1-rc.2; an unpinned upgrade invalidates prior evidence per `0003` §8.2 / LV5).

---

## 6. Exact residual (post-decision, unchanged — formally accepted)

**R (accepted):** on DSH 0.1.1-rc.2 with the current composition, a raw-write-capable role (`{zeko, cto, somad, nova}`) can, in principle, place content on `state/registry/**`, `audit/**`, or `state/projects/**` via a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel; DSH provides no per-path or per-agent interception inside the workspace; the L1 execution gate intercepts only channeled writes. **Prevention: ABSENT at the DSH layer. Containment: DETECTION at the project layer** (L1 gate + append-only + cumulative hash chain + CAS). **Formally accepted as V1 residual; G10 stays OPEN/BLOCKING for production.**

---

## 7. Production impact

| Impact | Detail |
|---|---|
| **Production deployment** | **BLOCKED** (unchanged). G10 is a BLOCKING gate; no production deployment starts while prevention is absent (consistent with `final/0005` §4, closure matrix §5). |
| **What CAN run in production-grade operation** | Everything at L1–L2-LIVE evidence level: deterministic control-plane logic, recorded-runtime bundles, DSH-layer toolFilter and workspace-root boundary (verified live). The residual affects only the *prevention* of a raw write by the four raw-write roles; all tampering remains **detectable**. |
| **What must be decided by a Human before unblocking** | Choose and schedule the closure arms: O5 config narrowing, O3 dedicated registry/audit process, and/or O4 upstream DSH capability. Until then, G10 blocks production and the acceptance matrix residual rows (PS-1/PS-2) stay open. |
| **Operational mitigation while OPEN** | Keep detection stack healthy (audit chain, CAS, append-only); monitor registry/audit writes as critical alerts; keep role toolFilter as tight as the current composition already is (read-only roles already deny raw write); treat any raw write to a protected path as a critical incident (Runbook 10 class). |

---

## 8. Honesty statement

1. **No closure of prevention is claimed.** G10 remains OPEN; the decision here is a formal *acceptance* of the residual plus a staged mitigation plan — not closure.
2. **No DSH core / profile / preset / session-policy / config / control / orchestrator / state / audit / role-boundary change was made.** The DSH checkout and live composition were read-only; the G10 test suite was re-run unchanged (39 passed).
3. **No role boundaries were changed.** O5 is *recommended as a Human decision*, not applied (the session constraint "do not change role boundaries" is honored).
4. **The residual is stated exactly**, with the actor set derived mechanically from the current config; it is not widened or narrowed to fit a narrative.
5. **The upstream requirement is stated exactly** (per-agent sandbox root or per-path allow/deny on filesystem tools), with the source evidence for why it is absent in 0.1.1-rc.2.
6. **No test failure was hidden or downgraded.** All test counts are as observed by running the documented commands.
7. **Production impact is stated without hedging**: G10 blocks production deployment until a Human applies a closure arm.

---

## 9. Scope check

**In scope (written this session):** `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md` (this file) + `tests/g10/final/test_g10_final_decision.py` (honesty guards).

**Not modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), DSH profiles/presets, session policy, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/` (including `tests/g10/` — unchanged, re-run), and all other `docs/`. No DSH modification. No role-boundary change. No production code change. No closure claim. No production deployment started.

---

*Status: FINAL DECISION RECORD (Session A). G10 remains OPEN / BLOCKING for production. Decision: formally accept the residual (containment = detection) and stage the minimum safe closure path — O5 (config narrowing, Human decision) → O3 (dedicated registry/audit process) → O4 (exact upstream DSH requirement: per-agent sandbox root or per-path allow/deny on filesystem tools). Nothing applied; no closure claimed; no DSH/core/config/policy/role change.*

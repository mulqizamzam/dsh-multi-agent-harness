# G10 — DSH Hard Filesystem Isolation (Session C Assessment)

- **Milestone**: Phase 5 / Session C — G10 HARDEN / BLOCKING
- **Status**: ASSESSMENT + EMPIRICAL EVIDENCE REPORT (**G10 OPEN** — no closure claim)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope (write-only)**: `multi-agent-harness/docs/phase-5/security/g10/` + `multi-agent-harness/tests/g10/`
- **Companion**: `docs/phase-5/final/0002-g10-formal-residual-proof.md` · `docs/phase-5/final/0005-final-security-gate-evidence.md` · `docs/phase-5/0001-acceptance-matrix.md` (PS-1/PS-2, RI-1, PP-1..4) · `docs/adr/0002-registry-protection-mechanism.md` · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · DSH source checkout `/home/administrator/deepseek-harness` (read-only) · DSH live composition (read-only) · `tests/g10/` (this session).
- **Question answered**: Can raw DSH filesystem access be technically isolated **per role**? — **No, not at the path level in DSH 0.1.1-rc.2.** (Tool-level yes; workspace-root boundary yes; per-role *path* isolation inside the workspace **absent**.)

---

## 0. Executive verdict

| Question | Answer | Evidence |
|---|---|---|
| Can raw DSH filesystem access be isolated **per role** at the **path level**? | **NO** (DSH capability absent) | `writableRoots()` grants the entire workspace root under `workspace-write`; `toolFilter` is tool-name-level only; no per-agent sandbox root; no per-path allow/deny exists (negative grep). |
| Is the **workspace-root boundary** enforced by DSH? | **YES** (hard, verified live) | Live probes: traversal `../`, absolute-outside `/etc`, symlink escape → all DENIED with `[Errno 30] Read-only file system`. |
| Is **tool-level** per-role isolation (read-only roles) enforced? | **YES** (toolFilter, live) | `subagent_cfo/kai/badsector` deny `bash/edit/write`; live composition mounts all 7 instances. |
| **G10 verdict** | **OPEN (BLOCKING)** | Prevention of a raw write to `state/registry/**`/`audit/**` by a raw-write role is NOT possible at the DSH layer; only the project L1 gate (channeled writes) + detection exist. |
| Does G10 block production? | **YES** | Same-UID sandbox + no per-path isolation means prevention of protected-path forgery by raw-write roles is absent at the DSH layer; production deployment must remain blocked until a Human decision on O2/O3/O5 or a DSH O4 capability. |

---

## 1. Threat boundary and residual (restated, then empirically confirmed)

**Statement (R):** A role whose toolFilter allow set includes a raw filesystem tool (`bash` and/or `write`/`edit`) can place content on a protected path (`state/registry/**`, `audit/**`) through a raw DSH tool call that **bypasses the project write channel**. The project execution gate (`control/execution_gate.py`) governs only writes that route through the project channel; it is a code channel, not a DSH interception point (ADR 0002).

**Actor set (derived mechanically from the CURRENT config, this session):**

| Role | `bash` allow | `write`/`edit` allow | Raw-write-capable (residual actor)? |
|---|---|---|---|
| zeko | yes | yes | **yes** |
| cto | yes | yes | **yes** |
| somad | no | yes | **yes** |
| nova | no | yes | **yes** |
| cfo | no | no | no |
| kai | no | no | no |
| badsector | no | no | no |

**Live confirmation of the residual (empirical, this session, throwaway mirror under `tests/g10/.scratch/`, then deleted):**

```
PROBE A  raw write  → tests/g10/.scratch/state/registry/x.json   → LANDED  ({"forged": true})
PROBE B  raw bash   → tests/g10/.scratch/audit/events.jsonl       → LANDED
PROBE E  sibling    → tests/g10/.scratch/state/registry-evil/     → LANDED (writable — DSH is path-agnostic)
```

**What DSH does NOT do (verified in source + live):** there is no per-path allow/deny on filesystem tools, no per-agent sandbox root, and no interception of a raw write to a protected path *inside* the workspace. The residual is not hypothetical — it lands, and the tests in `tests/g10/test_dsh_layer_isolation.py` keep it documented.

---

## 2. What IS enforced (empirical + source evidence)

### 2.1 DSH sandbox: workspace-root boundary — HARD (verified live)

Under `workspace-write`, the writable roots are `[workspaceRoot, /tmp, tmpdir]` (`packages/sandbox/sandbox/src/roots.ts:52-55`). The sandbox (bwrap/Seatbelt) hard-denies any write that resolves **outside** the workspace root. Live probes (inside the DSH sandbox):

```
PROBE C  traversal     → ../g10-traversal-escape.txt     → DENIED  [Errno 30] Read-only file system
PROBE D  absolute-out  → /etc/g10-absolute-escape.txt    → DENIED  [Errno 30] Read-only file system
PROBE F  symlink esc   → esc-link -> /etc/passwd         → DENIED  [Errno 30] Read-only file system
PROBE G  legitimate    → tests/g10/.scratch/legit.txt    → ALLOWED
```

These are also asserted deterministically in `tests/g10/test_dsh_layer_isolation.py` (sandbox-conditional; they skip with an explicit reason when the pytest process is not inside the DSH sandbox).

**Precise meaning:** DSH hard-isolates the **workspace boundary** (no escape from the project root), shared by the whole session. It does **not** differentiate **inside** the workspace.

### 2.2 DSH toolFilter: per-role TOOL isolation — live and enforced

The live composition (`$DSH_HOME/profiles/web/cordis.patch.yml`, this session) **does mount** the seven `tool-subagent-<role>` instances (tool-level allow/deny), matching `config/tool-subagent-instances.yaml`:

- read-only roles (`badsector`, `cfo`, `kai`): `bash/edit/write` **denied** → no raw filesystem mutation tool exists for them at the DSH layer;
- `somad`/`nova`: `bash` denied, `write/edit` allowed (drafting);
- `zeko`/`cto`: `bash` + `write/edit` allowed (ops/engineering).

`toolFilter` is applied by `tools.restrict()` — a **global tool-name mask**, never a path filter (`packages/core/tools/src/index.ts:680-685,1071`; applied per-child in `tool-subagent/src/index.ts`). A tool that passes the filter can target any path inside the sandboxed workspace.

### 2.3 Project L1 execution gate: channeled-write protection — code-enforced (deterministic)

`control/execution_gate.py::authorize_write()` (verified by inspection + tests):

| Behavior | Observed |
|---|---|
| `state/registry/**`, `audit/**` → **PROTECTED** | DENY on channeled write |
| Traversal / absolute-outside / symlink / malformed → **DENY** | fail-closed |
| Sibling-prefix `state/registry-evil` → **ALLOWED** (not misclassified) | prefix-confusion prevention |
| Legitimate workspace path → **ALLOWED** | path-aware, not blanket |
| Writer channel per-root scoping (`registry_write`→`state/registry/**` only; `audit_append`→`audit/**` only) | no cross-root |

**Precision finding (this session):** `state/projects/**` classifies **ALLOWED** at the gate. Its protection is **post-hoc CAS version detection** (`state/helpers/version_check.py`, `atomic_write.py::compare_and_swap`), not a gate DENY — consistent with the G10 residual docs (§4, "State forgery … CAS version check (post-hoc detection)"). This is recorded as a documented fact, not a new gap.

---

## 3. DSH capability evidence (0.1.1-rc.2, read-only source)

All verified this session against `/home/administrator/deepseek-harness` (read-only; asserted by `tests/g10/test_dsh_capability.py`):

1. **Sandbox mode is per-session, inherited — never per-agent.** `packages/subagent/subagent/src/child-agent.ts:180` — `DelegatedPolicyOverrides.sandboxMode` is *"The parent session's explicit sandbox-mode override"*; `captureDelegatedPolicyOverrides` (lines 199–204) seeds one mode for the whole delegation chain.
2. **`writableRoots()` grants the entire workspace root** under `workspace-write` (`packages/sandbox/sandbox/src/roots.ts:52-55`): `[workspaceRoot, '/tmp', tmpdir()]`. No per-path granularity.
3. **No path-level or per-agent sandbox differentiation exists.** Negative grep for `pathFilter|pathAllow|pathDeny|perPath|allowPaths|denyPaths|path-level` across `packages/**/*.ts` → only the unrelated doc-comment at `packages/fs/fs/src/types.ts:87` (symlink probe description). Asserted by `test_no_path_level_filter_exists`.
4. **`toolFilter` is tool-name-level only** (`ToolRestriction` `allow/deny: string[]`, `restrict()` global-tool mask).
5. **`SANDBOX_MODES` closed union** = `['read-only', 'workspace-write', 'danger-full-access']` (`session-mode.ts:42`).
6. **`write`/`edit` (tool-fs) and `bash` share the same per-session sandbox** (`FsSandboxController`, `ctx.fs.sandboxMode`; `ctx.shell.sandboxMode`). A path allowed for `write` is allowed for `bash` and vice versa — no per-tool path divergence.

**Conclusion of §3:** DSH 0.1.1-rc.2 provides per-**session** workspace-root sandboxing and per-**tool** availability (toolFilter), but **no per-role or per-path filesystem isolation inside the workspace**. This is the exact O4 capability gap.

---

## 4. The exact required DSH capability (what would close R)

To close R (prevent a raw write by a raw-write role from reaching `state/registry/**` / `audit/**`), DSH must provide, at the filesystem-tool layer, one of:

1. **Per-agent sandbox root** — each delegated child's `workspace-write` root scoped to a per-role sub-tree, so `state/registry/**` / `audit/**` fall **outside** the child's writable root and are denied by the sandbox itself; **or**
2. **Per-path allow/deny on filesystem tools** — a path-level restriction (e.g. DENY `state/registry/**`, `audit/**`, `state/projects/**` as write targets for non-writer roles) applied by DSH before any tool mutation, independent of which raw tool carries the write.

**Neither exists in 0.1.1-rc.2** (§3). This capability must come from upstream DSH; it cannot be added from inside the project (ADR 0001 Decision 7 boundary; task scope prohibits DSH modification).

---

## 5. Smallest safe future solution (ranked)

Given the constraint of **no DSH change in this session**, the smallest *safe* path to reduce/close the residual, in order of preference (each requires a Human-approved composition/process decision — none applied this session):

| Rank | Option | DSH change? | Effort | Effect | Blocker |
|---|---|---|---|---|---|
| 1 | **O5 — narrow raw-write surface**: remove `write/edit` (and where viable `bash`) from roles that do not need raw fs mutation (somad, nova), forcing their writes through the project channel | no (config) | low-medium | Shrinks actor set from {zeko,cto,somad,nova} to {zeko,cto}; read-only roles already done | Human-approved composition change (D4/D7 exception reopen, ADR 0001 Decision 4/7) |
| 2 | **O3 — out-of-process registry process**: dedicated process with its own workspace root; only it writes the registry | no (new process) | high | Hard isolation of the authority source | Human-approved infrastructure change (ADR 0002 consequence 4) |
| 3 | **O2 — registry outside workspace**: relocate `state/registry` outside the session sandbox so no session tool can write it | no (config/relocation) | medium | Hard isolation, but breaks orchestrator single-writer unless per-agent sandbox exists (ADR 0002 Option A analysis) | Human decision; rejected for V1 |
| 4 | **O4 — per-agent/path-level sandbox** (upstream DSH) | **yes** | unknown | The only closure arm needing no composition change | **Not available in 0.1.1-rc.2** (this session's §3) |

**Smallest safe solution without DSH change:** **O5 first** (config-only, reversible, shrinks the raw-write actor set and forces more writes through the gated project channel), then **O3** if hard authority-source isolation is required. All gated on Human approval; nothing applied this session.

---

## 6. Tests delivered (this session, `tests/g10/`)

| File | Proves |
|---|---|
| `test_project_layer_isolation.py` | L1 gate: protected-root classification, channeled DENY (registry/audit), writer=True grants nothing on generic actions, traversal/symlink/absolute-outside/malformed DENY, sibling-prefix ALLOWED, writer-channel per-root scope, legitimate workspace ALLOWED, `state/projects` CAS-not-gate (precision) |
| `test_dsh_layer_isolation.py` | DSH layer: raw write / raw bash / raw edit reach protected-path mirrors (residual); sibling-prefix writable at DSH; sandbox DENIES absolute-outside / traversal / symlink (sandbox-conditional, skip-with-reason outside harness); sandbox ALLOWS inside-workspace |
| `test_dsh_capability.py` | Static source facts: version pin 0.1.1-rc.2; per-session sandbox; writableRoots=workspace root; closed SANDBOX_MODES union; no path-level filter (negative grep); toolFilter tool-level; fs/bash share session sandbox |
| `test_role_restrictions.py` | Current D4/D7 toolFilter: read-only roles deny bash/edit/write; raw-write set = {zeko,cto,somad,nova}; allow∩deny=∅; no delegation in specialist allow; composition-exception status honest; no-closure-claim honesty guard |

---

## 7. Honesty statement

1. **No closure of prevention is claimed.** G10 remains OPEN; the DSH-layer prevention gap is empirically confirmed (raw writes land), and the required DSH capability (per-agent sandbox root or per-path allow/deny) is absent in 0.1.1-rc.2.
2. **No DSH core / profile / preset / session-policy / control / config / orchestrator / state / audit change** was made. The DSH checkout was read-only; the live composition was read-only.
3. **No real protected state was touched.** All raw-write probes used a throwaway mirror under `tests/g10/.scratch/`, which was deleted after the probes; tests use `tmp_path` mirrors.
4. **No test failure was hidden.** The sandbox-boundary tests are explicitly `skipif`-guarded with a visible reason when the DSH sandbox is not active, and they PASS here (sandbox active). No test was weakened.
5. **`state/projects/**` precision** (ALLOWED at gate, CAS-detected post-hoc) is documented as a fact, matching the prior formal proof; it is not presented as new or as a closure.
6. **G10 should block production** until a Human decision on O2/O3/O5 or upstream O4, consistent with `docs/phase-5/final/0005-final-security-gate-evidence.md` (production deployment NOT STARTED).

---

## 8. Scope check

**Written this session:** `docs/phase-5/security/g10/0001-g10-filesystem-isolation-assessment.md` (this file) + `tests/g10/{conftest.py,test_project_layer_isolation.py,test_dsh_layer_isolation.py,test_dsh_capability.py,test_role_restrictions.py}`.

**Not modified (verified):** DSH core, profiles/presets, session policy, `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, all pre-existing `tests/`, and all other `docs/`. No DSH modification. No project execution gate weakened. No closure claim.

---

*Status: ASSESSMENT + EMPIRICAL EVIDENCE. G10 OPEN (BLOCKING). Raw DSH filesystem access cannot be path-isolated per role in DSH 0.1.1-rc.2 (per-agent sandbox root and per-path allow/deny absent). Workspace-root boundary and per-role toolFilter ARE enforced and verified live. V1 containment = project L1 gate + detection. No closure of prevention claimed.*

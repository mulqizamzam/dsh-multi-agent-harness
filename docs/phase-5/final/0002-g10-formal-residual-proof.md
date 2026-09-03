# G10 Formal Residual Proof — DSH Path-Isolation (BLOCKING GATE)

- **Milestone**: Phase 5 / Final — G10 FORMAL RESIDUAL PROOF (BLOCKING GATE EVIDENCE DELIVERABLE)
- **Status**: EVIDENCE REPORT (formal proof; **no DSH/config/control change; no closure of prevention claimed**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/final/0002-g10-formal-residual-proof.md` (this file, write-only).
- **Companion**: `docs/phase-5/0001-security-hardening-analysis.md` (G10 root) · `docs/phase-5/security/0001-g10-g13-security-residual-analysis.md` §1 · `docs/phase-5/final/0001-security-closure-matrix.md` (G10 row, §1) · `docs/adr/0001` (Decision 1) · `docs/adr/0002-registry-protection-mechanism.md` · `control/execution_gate.py` · `tests/phase5_security/test_negative_path_isolation.py` · DSH source checkout `/home/administrator/deepseek-harness` (read-only).
- **G10 is a BLOCKING GATE.** This report is the formal proof of the **exact residual** and of the **exact required DSH capability** to close it. It is an evidence deliverable for the gate; it does **not** close the gate. **No DSH-layer path isolation is claimed anywhere in this document.**

---

## 1. The exact residual (formally stated)

**Statement (R).** A role whose tool allow set includes a raw filesystem-write tool (`bash` and/or `write`/`edit`) can, in principle, place content on a protected path (`state/registry/**`, `audit/**`, `state/projects/**`) through a **raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel**. The project execution gate (`control/execution_gate.py`) governs writes that **route through the project channel** (`write_through`, `registry_write`, `audit_append`); it is a code channel, not a DSH interception point, so a raw tool call that does not route through it is not intercepted (ADR 0002).

**Historical pre-O5 actor set (snapshot before O5 containment, 2026-08-31).** The table below reflects the actor set **before** O5 was applied. The residual actor set was the **raw-write-capable** roles — `bash` **and/or** `write`/`edit` in the toolFilter allow set:

| Role | `bash` in allow? | `write`/`edit` in allow? | Raw-write-capable (residual actor)? |
|---|---|---|---|
| zeko | yes | yes | **yes** |
| cto | yes | yes | **yes** |
| somad | **no** (denied) | yes | **yes** |
| nova | **no** (denied) | yes | **yes** |
| cfo | no | no | no |
| kai | no | no | no |
| badsector | no | no | no |

Derived mechanically from the pre-O5 `config/role-preset-mapping.yaml` via the same rule the test suite uses (`tests/phase5_security/conftest.py::bash_capable_roles` / `readonly_roles`): `bash_capable(allow) = ['cto', 'zeko']`, `readonly(deny bash+write+edit) = ['badsector', 'cfo', 'kai']`, `raw-write-capable = ['cto', 'nova', 'somad', 'zeko']`. **Precision note:** the pre-O5 config already denied `bash` to somad/nova, so strictly-`bash`-capable was {zeko, cto}; the residual **does not depend on bash** — `write`/`edit` alone are raw filesystem tools equally un-intercepted by the L1 channel gate. This does not change the historical G10 statement ("bash-capable role (zeko, cto, somad, nova)"): the raw-write tool set is what matters, and all four of those roles held it.

**Current post-O5 actor set.** After O5 was applied (see `docs/phase-5/security/g10/implementation/0002-o5-application-record.md`), `write` and `edit` were removed from the `toolFilter.allow` of `somad` and `nova`. The current raw-write-capable actor set is **{zeko, cto}** only. `somad` and `nova` are now read-only at the DSH tool level (no `bash`, `write`, or `edit` in their allow sets). See §7 Addendum for the full effect. The residual statement (R) remains true for `{zeko, cto}` — those two roles still carry `bash` + `write`/`edit` and can in principle reach `state/registry/**`, `audit/**`, `state/projects/**` via a raw DSH tool call.

**Proof test (quoted, observed PASS).** `tests/phase5_security/test_negative_path_isolation.py`:

```python
def test_raw_write_reaches_protected_path_unintercepted(tmp_workspace):
    """RESIDUAL PROVEN OPEN: a raw filesystem write to the protected-path
    layout is NOT intercepted by any DSH-layer mechanism.

    This documents the threat boundary: the project execution gate governs
    writes that ROUTE THROUGH the project channel; a raw tool call that
    bypasses the channel is not intercepted (ADR 0002 residual).
    """
    target = tmp_workspace / "state" / "registry" / "x.json"
    with open(target, "w") as f:
        f.write('{"forged": true}')
    # The write landed — the DSH layer did not intercept it.
    assert target.exists()
    assert target.read_text() == '{"forged": true}'
```

(Test lines 43–56.) The test operates on a **throwaway temp workspace** (`conftest.py::tmp_workspace`, lines 13–25) that mirrors the real `state/registry/` + `audit/` + `state/projects/` layout; it documents the boundary, it does not exploit it and never touches real protected state.

**What R is not:** R is not a claim that any role *will* write a protected path, nor that a raw write is *undetectable* (detection exists; see §4). R is a **capability-level proof**: the DSH layer provides no mechanism that intercepts a raw filesystem tool call to an arbitrary path inside the sandboxed workspace, so prevention of such a write is **absent** at the DSH layer for these roles.

---

## 2. Why prevention cannot be closed in this session

Prevention of R requires one of the four mitigation options. Each is blocked in this session by an **authority or capability constraint**, not by effort:

| Option | What it does | DSH capability change? | What blocks it in this session | Authority/capability required |
|---|---|---|---|---|
| **O5 — reduce bash surface** | Remove `bash` (and/or `write`/`edit`) from zeko/cto/somad/nova allow sets; force writes through the project channel | **no** (config only) | ToolFilter changes are a controlled D4/D7 composition exception, not mounted; removing bash from zeko/cto is a capability regression, and (per §1) removing bash alone does **not** close R while `write`/`edit` remain | **Human-approved composition change** (ADR 0001 Decision 4/7 — HUMAN_PENDING) |
| **O3 — dedicated out-of-process registry process** | Separate process with its own workspace root; only that process writes the registry | **no** (new process) | New-process infrastructure change; not applied this session | **Human-approved infrastructure/composition change** (ADR 0002 consequence 4 — Phase-5 hardening option) |
| **O2 — registry outside workspace** | Move registry to a path outside the sandboxed workspace so no session tool can write it | **no** (config/path relocation) | ADR 0002 Option A analysis: rejected for V1 — the orchestrator (root session) shares the same per-session sandbox, so moving the registry out blocks the orchestrator's own single-writer access without per-agent sandbox differentiation (ADR 0002 §Option A, lines 28–32) | **Human-approved composition change** (medium effort; deferred) |
| **O4 — per-agent/path-level sandbox** | Per-agent sandbox root or per-path allow/deny on filesystem tools | **yes** (DSH capability) | **Not available in DSH 0.1.1-rc.2** (see §3) — a missing capability cannot be added from inside the project | **DSH capability** (upstream) |

**Authoritative quotes (verified, not re-derived):**

- **ADR 0001 Decision 1** (lines 141–149): *"Adopt a **two-tier** model. Tier 1 (per-role capability boundary): Agent Presets + per-`tool-subagent` instance `toolFilter`/`persona`. Tier 2 (global session enforcement): sandbox mode + approval policy stay **per-session** … **not** per-agent."* Evidence line (144): *"sandbox + approval are per-session (VERIFIED)…"* Security impact (146): *"Because sandbox/approval are shared, default to the tightest common denominator (workspace-write + ask)."* Human approval status (149): **HUMAN_PENDING**.
- **ADR 0002** (lines 21–22): *"1. **Sandbox is per-session, not per-agent** (VERIFIED)… 2. **`toolFilter` is tool-level, not path-level** (VERIFIED). `edit`/`write`/`bash` can reach any path inside the sandboxed workspace; there is no per-path allow/deny."*
- **ADR 0002 Option B** (lines 41, 55): *"Honest residual gap: roles with `bash`/`edit`/`write` (Zeko, CTO, Somad, Nova) could, in principle, reach the registry path through their tools… It is **not** hard path isolation at the DSH layer — stated explicitly, not assumed."* And: *"Option A is impossible in V1 without per-agent sandbox (not expressible) or a new process (Phase-5 scope)."*

**Conclusion of §2.** Every closure arm for R is gated: O2/O3/O5 require a **Human-approved composition/process change** (none granted or applied this session), and O4 requires a **DSH capability absent from 0.1.1-rc.2**. Therefore **prevention cannot be closed in this session by any action available to the project layer**, and the session's task scope explicitly prohibits modifying DSH, config, control/, orchestrator/, state/, audit/, agents/, schemas/, or tests. The only in-scope deliverable is this formal proof.

---

## 3. The exact required DSH capability (what O4 must provide)

O4 — the only closure arm that needs no Human-approved composition change, and the one that actually closes the **DSH-layer prevention** gap — requires a DSH capability that **does not exist in 0.1.1-rc.2**. Verified against the source checkout (read-only):

**(a) Sandbox mode is per-session, inherited by children — never per-agent.** `packages/subagent/subagent/src/child-agent.ts`:

- Lines 177–187, `DelegatedPolicyOverrides`:
  - line 180: `readonly sandboxMode: SandboxMode | undefined` — *"The **parent session's** explicit sandbox-mode override, or `undefined` without one."* (emphasis added)
  - line 186: `readonly approvalPolicy: 'never' | undefined` — *"`'never'` whenever the approval capability is composed… a delegated child acts only within the sandbox scope fixed at delegation, so its asks are rejected deterministically."*
- Lines 199–204, `captureDelegatedPolicyOverrides(parent)` — the exact mechanism:
  ```ts
  return {
    sandboxMode: parent.ctx.get('sandboxPolicy')?.overrideOf(parent.session),
    approvalPolicy: parent.ctx.get('approval') === undefined ? undefined : 'never',
  }
  ```
  `overrideOf(parent.session)` (implemented in `packages/sandbox/sandbox-policy/src/index.ts:149–150` as `effectiveSandboxMode(session.events)`) reads the **session log** fold — the child inherits **one** mode for the whole delegation chain, derived from the parent **session**, with **no per-agent differentiation**.
- Lines 215–225, `appendDelegatedPolicyOverrides` seeds `sandbox/mode` + `approval/policy` onto the child's log with `source: 'delegation'` (called from `continuation.ts:433` capture, `:1063` append). `packages/sandbox/sandbox-policy/src/session-mode.ts:42` confirms the closed union: `SANDBOX_MODES = ['read-only', 'workspace-write', 'danger-full-access']`.

**(b) There is NO path-level or per-agent sandbox differentiation — negative finding, stated honestly.** A repository-wide grep of the checkout for path-level allow/deny on filesystem tools (`pathFilter|pathAllow|pathDeny|path-level|perPath|allowPaths|denyPaths`) returns exactly one hit, `packages/fs/fs/src/types.ts:87` — a doc comment about a symlink *probe* (`FsInfo`), **not** a sandbox policy. The filesystem fence (`packages/fs/fs-sandbox/src/containment.ts:58–76`, `isPathUnder(path, root)`) enforces containment against **one** writable root, and the root set is mode-derived: `packages/sandbox/sandbox/src/roots.ts:52–55` —

```ts
export function writableRoots(policy: SandboxExecutionPolicy): string[] {
  if (policy.mode !== 'workspace-write') return []
  return [...new Set([policy.workspaceRoot, '/tmp', tmpdir()].map(canonicalPath))]
}
```

i.e. under `workspace-write`, **the entire workspace root** (plus `/tmp`) is writable by any tool; there is no per-path allow/deny inside the workspace, and no per-agent variant of the mode.

**(c) `toolFilter` is tool-level, not path-level.** `packages/core/tools/src/index.ts:680–685`:

```ts
export interface ToolRestriction {
  /** Global tool names that stay visible; everything else is removed. */
  readonly allow?: readonly string[]
  /** Global tool names removed from visibility. */
  readonly deny?: readonly string[]
}
```

`restrict()` (line 1071) is described as *"global-tool mask: `allow` (keep only) and/or `deny` (remove)"* — it filters by **tool name**, never by target path. A tool that passes the filter (`write`, `edit`, `bash`) can target any path inside the sandboxed workspace.

**What O4 must add (exact requirement).** A DSH capability that, at the filesystem-tool layer, distinguishes **per agent** (or per delegation) either:

1. a **per-agent sandbox root** — the child's `workspace-write` root would be scoped to a per-role sub-tree instead of the whole parent-session workspace (so `state/registry/**`, `audit/**` fall outside the child's writable root and are denied by the sandbox itself); or
2. a **per-path allow/deny on filesystem tools** — e.g. a path-level restriction that DENYs `state/registry/**` / `audit/**` / `state/projects/**` as write targets for non-writer roles at the DSH layer, independent of which raw tool carries the write.

**Why this exact capability is required:** with (1) or (2), a raw `bash`/`write`/`edit` call to a protected path would be denied *by DSH itself*, before the project channel is involved — closing R at the layer where the residual lives. **This capability is not present in 0.1.1-rc.2** (evidence (a)–(c)); it must come from upstream DSH, which this session cannot modify (ADR 0001 Decision 7 boundary; task scope).

---

## 4. What IS enforced at the project layer (L1 + detection)

R is **prevention-unclosed** but **detection-contained**. The project layer enforces the following, all verified deterministic this session:

**L1 execution gate — `control/execution_gate.py` (verified by inspection + tests):**

| Enforcement | Mechanism | Location |
|---|---|---|
| Protected-path DENY for any **channeled** write to `state/registry/**` / `audit/**` by a non-sanctioned actor | `PROTECTED_REL_ROOTS = ("state/registry", "audit")`; `authorize_write()` raises `Denied` before any mutation | lines 57, 205–261 |
| Per-channel sanctioned roots (single-writer scoping): `registry_write() → state/registry/**` only; `audit_append() → audit/**` only; `writer=True` never grants cross-root or non-protected access | `SANCTIONED_ROOTS` | lines 69–72, 245–261 |
| Traversal / symlink / absolute-outside / malformed DENY (fail-closed) | `normalize_target()` (lexical + realpath ancestor resolution, containment check) | lines 101–151 |
| Prefix-confusion PREVENTION: `state/registry-evil/…` classifies ALLOWED, not PROTECTED (sibling prefix is not the protected root) | `_match_protected_root()` exact-or-descendant with path-separator boundary; `classify_target()` | lines 154–165, 168–186 |
| Ordinary workspace writes ALLOWED (path-aware, not blanket-denying) | `authorize_write` ALLOW branch | lines 254–261 |

**Negative tests proving L1 (all observed PASS, `tests/phase5_security/test_negative_path_isolation.py`):**

| Test | Proves |
|---|---|
| `test_project_channel_write_denied` (lines 59–67) | Same `state/registry/x.json` target **DENIED** through the gate; no file created |
| `test_project_channel_audit_write_denied` (lines 70–74) | `audit/events.jsonl` **DENIED** through the gate |
| `test_traversal_denied` (lines 77–90) | `../state/registry/escape.json` **DENIED**; `state/registry-evil/x.json` correctly ALLOWED (prefix-confusion prevention) |
| `test_workspace_write_allowed` (lines 93–97) | Normal workspace write through the channel **ALLOWED** |
| `test_raw_write_reaches_protected_path_unintercepted` (lines 43–56) | **The residual**: the same target via a raw (channel-bypassing) write **lands** — the boundary of §1 |
| `test_bash_capable_roles_identified` / `test_readonly_roles_identified` (lines 26–40) | Actor-set calibration: zeko/cto bash-capable; cfo/kai/badsector deny write+edit+bash at toolFilter level |

**Detection (post-hoc containment, verified by inspection):**

| Detection | Mechanism | Location |
|---|---|---|
| Append-only audit ledger | `append_event()` appends JSON Lines; `verify_append_only()` flags truncation/overwrite/edited lines | `audit/helpers/append_log.py` (lines 1–3, 30, 135; *"A corrupt/blank line in an append-only ledger is evidence of tampering"* line 96) |
| Cumulative SHA-256 hash chain | `compute_chain()` / `verify_chain()` — each line's `cumulative_hash` over all prior canonical lines; tamper/truncate breaks the chain | `audit/helpers/integrity.py` (lines 13–15, 36, 104, 143); hardened checks `audit/hardening/chain.py::verify_chain_with_sidecar` / `recompute_and_compare` (lines 30–81, fail-closed on missing sidecar) |
| Truncation / duplicate / replay / ordering detection | `detect_truncation()` / `detect_duplicates()` against a prior verified baseline | `audit/hardening/detection.py` (lines 28–60) |
| State CAS (compare-and-swap) + strict monotonic versioning | `compare_and_swap()` writes only if current version == expected and new version == expected+1; stale/replayed/injected state refused | `state/helpers/atomic_write.py` (lines 193–200), `state/helpers/version_check.py` (`validate_version_monotonic` 59–85, `is_stale` 107–131, `assert_current_version` 134–156) |

**Containment statement (precise):** even if a raw DSH write lands on a protected path (R), the L1 gate + CAS + append-only hash chain + audit detection make the tamper **detectable** (REG-003, AUD-*, Runbook 10). V1 containment for G10 = **detection at the project layer**, while **prevention at the DSH layer remains absent** (the exact gap O4 would close).

---

## 5. Evidence log (exact counts observed this session)

All runs executed this session with the pinned venv; exit code 0; no failures, no skips.

```text
$ .venv-tests/bin/python -m pytest tests/phase5_security/ -q
14 passed in 0.13s

$ .venv-tests/bin/python -m pytest tests/authorization/ -q
178 passed in 0.39s
```

| Suite | Observed | Expected (per brief) | Meaning |
|---|---|---|---|
| `tests/phase5_security/` | **14 passed** | 14 passed | G10 negative path-isolation (8 tests in `test_negative_path_isolation.py`: raw write lands / channeled DENY / traversal DENY / prefix-confusion / workspace ALLOW / actor sets / no-closure claim) + G13 external-content-as-data (6 tests in `test_external_content_data.py`) |
| `tests/authorization/` | **178 passed** | 178 passed | L1 authority/execution-gate layer green (confirms the gate that powers §4 works) |

**DSH version pin (verified):** `/home/administrator/deepseek-harness/package.json:3` → `"version": "0.1.1-rc.2"` (root package `@deepseek-ai/dsh-root`); `dsh --version` at `/home/administrator/.local/bin/dsh` → `0.1.1-rc.2`.

**DSH capability facts (verified in checkout, read-only):**
- `packages/subagent/subagent/src/child-agent.ts:180` — sandboxMode = *"The **parent session's** explicit sandbox-mode override"* (per-session, inherited; NOT per-agent).
- `packages/subagent/subagent/src/child-agent.ts:186,202` — approvalPolicy pinned to `'never'` for composed children (`captureDelegatedPolicyOverrides`, lines 199–204).
- `packages/sandbox/sandbox/src/roots.ts:52–55` — `workspace-write` writable roots = entire workspace root + `/tmp` + `tmpdir()`; no per-path granularity.
- `packages/core/tools/src/index.ts:680–685,1071` — `ToolRestriction` filters by **global tool names**; `restrict()` is a tool-level mask, never path-level.
- Negative finding: **no path-level or per-agent sandbox differentiation exists** in 0.1.1-rc.2 (grep for `pathFilter|pathAllow|pathDeny|path-level|perPath|allowPaths|denyPaths` across `packages/**/*.ts` → single unrelated doc-comment hit at `packages/fs/fs/src/types.ts:87`).

---

## 6. Verdict — G10 OPEN

**G10 verdict: OPEN (BLOCKING GATE).**

- The DSH-layer **prevention** gap is **formally proven residual** (R, §1): a raw-write-capable role (post-O5 actor set: {zeko, cto}; pre-O5: {zeko, cto, somad, nova}) can reach `state/registry/**`, `audit/**`, `state/projects/**` through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel; the L1 gate intercepts only channeled writes.
- The gap is a **DSH-capability gap**: no per-agent sandbox root and no per-path allow/deny on filesystem tools exists in 0.1.1-rc.2 (§3); O4 therefore cannot be implemented in this project, and O2/O3/O5 each require a Human-approved composition/process change not granted this session (§2).
- **V1 containment = detection** at the project layer (L1 execution gate + append-only + cumulative hash chain + CAS), proven by the green suites in §5 (§4).
- **This report does NOT claim closure.** No DSH/config/control change was made; no path isolation is closed; the closure matrix row for G10 remains **OPEN** (`docs/phase-5/final/0001-security-closure-matrix.md` §1 G10 row, §2, §6 blocker B5).

**Exact precondition for closing G10 (recorded, not executed):** a Human decision on V2 path isolation — O5 (narrow raw-write surface), O3 (out-of-process registry), or O2 (registry relocation), each via an approved, reversible composition/process change — **or** upstream DSH providing the O4 capability (per-agent sandbox root or per-path allow/deny on filesystem tools), after which the honest residual statement in this document must be re-derived against the new DSH version (version pin 0.1.1-rc.2).

---

## Scope check

**In scope (written this session):** `docs/phase-5/final/0002-g10-formal-residual-proof.md` (this file) only.

**Not modified (verified):** DSH core (`/home/administrator/deepseek-harness/`, read-only), `config/`, `control/`, `orchestrator/`, `state/`, `audit/`, `agents/`, `schemas/`, and `tests/` (all), and any `docs/` outside `docs/phase-5/final/`. No implementation change. No DSH/profile/preset/session-policy change. No path-isolation closure claimed. No new security claim.

---

## 7. Addendum — O5 applied (post-publication, 2026-08-31)

**This addendum documents a change applied after the formal proof was written and does not alter the historical evidence above.**

On 2026-08-31, the Human **APPROVED and APPLIED O5** — removed `write`/`edit` from the `toolFilter.allow` sets of `somad` and `nova` (containment step). The change was applied consistently across `config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`, `agents/{somad,nova}/policy.yaml`, and the live D4/D7 composition (`$DSH_HOME/profiles/web/cordis.patch.yml`). See `docs/phase-5/security/g10/implementation/0002-o5-application-record.md` for the full application record, pre-change backups, hashes, verification, and rollback procedure.

**Effect on the residual statement (R in §1):** the raw-write-capable actor set is **narrowed from `{zeko, cto, somad, nova}` to `{zeko, cto}`**. `somad` and `nova` are now read-only at the DSH tool level (no `bash`, `write`, or `edit` in their allow sets). The residual statement remains true for `{zeko, cto}` — those two roles still carry `bash` + `write`/`edit` and can in principle reach `state/registry/**`, `audit/**`, `state/projects/**` via a raw DSH tool call. **G10 remains OPEN / BLOCKING for production. No closure of prevention is claimed.** O3 (dedicated registry/audit writer process) was NOT implemented (HOLD). O4 (upstream DSH per-agent sandbox root / per-path allow-deny) remains the only full-prevention arm.

**This addendum does not modify or retract any statement in the preceding sections. The original proof remains the authoritative evidence for the pre-O5 state.**

---

*Status: EVIDENCE REPORT + post-O5 addendum. G10 remains OPEN / BLOCKING. Raw-write actor set: {zeko, cto} (post-O5). No closure of prevention claimed.*

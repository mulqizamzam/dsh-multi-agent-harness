# Change Request 0006 — Orchestrator Preset Composition Exception

- **Status**: **EXECUTED AND VERIFIED** (2026-09-12). Not a proposal — the record of a completed, evidence-backed change.
- **Date**: 2026-09-12
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (unchanged; no DSH core modification)
- **Authority**: `docs/adr/0004-orchestrator-role-preset.md` (Human decision, 2026-09-12 — the owner asked for the Orchestrator to become a real, deployable role and selected the deployable-preset option).
- **Amends**: `config/role-preset-mapping.yaml` → `draft_artifacts.orchestrator_preset` (was `standard`), and the Phase-1C statement in `docs/phase-1/0002-role-isolation-draft.md` §"Constraints" item 3.
- **Pattern**: follows the D4/D7 controlled composition exception of `docs/phase-1/0003-d4-composition-exception-change-request.md`.
- **Evidence**: `runs/orchestrator-preset-2026-09-12/`

---

## 1. Motivation

The orchestrator had no preset of its own. The root session ran the shipped `standard` preset — whose persona is, verbatim, `You are a coding agent powered by the {{model}} model.` (`/home/administrator/deepseek-harness/apps/cli/config/agent-presets/standard/agent.cordis.yml:28`). A coding-agent identity is not a coordination identity.

Worse, the orchestrator's declared `toolFilter` (`config/role-preset-mapping.yaml` §`orchestrator`) was **unenforced intent**: nothing composed it. The concrete, verified divergence: the orchestrator's `deny` list names `ralph` and its notes say "ralph is a fresh-agent loop, not orchestration", yet the `standard` preset the root session ran mounts `tool-ralph` (`standard/agent.cordis.yml:230-231`) — so the live root session carried a tool its own declared policy denied.

This change makes that declaration real for any session that selects the preset.

## 2. Exact write surface

Created (nothing overwritten, nothing deleted):

| Repo source (project) | Deployed target | Action |
|---|---|---|
| `orchestrator/agent.cordis.yml` | `$DSH_HOME/.agent-presets/orchestrator/agent.cordis.yml` | create |
| `orchestrator/preset.yml` | `$DSH_HOME/.agent-presets/orchestrator/preset.yml` | create |

Repo-only artifacts (no DSH surface): `orchestrator/policy.yaml` (new), `docs/adr/0004-orchestrator-role-preset.md` (new), this document (new).

Modified repo config: `config/role-preset-mapping.yaml`, `config/permissions.yaml`, `AGENTS.md`, `docs/operations.md`.

**Provably untouched** (hash-verified against the pre-change baseline):

- `/home/administrator/deepseek-harness/` — the DSH checkout stays read-only; no shipped preset, bundle, or engine file was created, edited, or deleted.
- `$DSH_HOME/profiles/web/cordis.patch.yml` — SHA-256 `43031f503103062a060c738711329a1b80070f6ca82b7c05583df719dbdaae11`, unchanged.
- The shipped `standard` preset — SHA-256 `fa14feb98daef20b810fef30bb7239a89a786de3c45c602b37743f7100d9a5af`, unchanged.
- Every pre-existing preset composition — all 15 verified unreduced (harness check: `changed=[]`, `removed=[]`).
- `settings.yaml` → `agent-presets.default` is still `standard`.

The change is **purely additive**: exactly one preset directory was added (`added=['orchestrator']`).

## 3. Composition delta and provenance

The preset is **derived** from the shipped `standard` preset rather than re-authored, so it inherits a known-good composition and its delta is auditable as a diff.

| `standard` row | Action | Authority |
|---|---|---|
| `persona` | text replaced with the orchestrator persona | identity |
| `tool-pwsh` | deleted (top level) | `orchestrator.tool_filter.deny` names `pwsh` |
| `tool-subagent-codex` | deleted (nested in `delegation`) | not in `orchestrator.tool_filter.allow` |
| `tool-subagent-claude-code` | deleted (nested in `delegation`) | not in `orchestrator.tool_filter.allow` |
| `tool-ralph` | deleted (nested in `delegation`) | `orchestrator.tool_filter.deny` names `ralph` |

No row was added; ordering is preserved; every `isolate` realm and group structure is copied verbatim.

**Counting trap — read this before re-verifying.** `tool-ralph`, `tool-subagent-codex`, and `tool-subagent-claude-code` are **nested inside the `delegation` group**, not top-level rows. A top-level-only count reads the delta as **16 → 15 (delta 1)**; the recursive count is **29 → 25 (delta 4)**. A verification check written at top level reports those three as "absent" while they are still present — a **false PASS**. The harness in `runs/orchestrator-preset-2026-09-12/verify_preset.py` was written with exactly that bug and fixed with a recursive `all_row_ids()` walker; the fix is regression-tested. Count recursively.

SHA-256 (measured after the fix to `preset.yml`, §5 defect b):

| File | SHA-256 |
|---|---|
| `orchestrator/agent.cordis.yml` (repo) | `ca7f3caebde3abcc08cbcdc1650c38bfde5b3f1d76a6a2b97bc15c9f1118da72` |
| `$DSH_HOME/.agent-presets/orchestrator/agent.cordis.yml` | `ca7f3caebde3abcc08cbcdc1650c38bfde5b3f1d76a6a2b97bc15c9f1118da72` |
| `orchestrator/preset.yml` (repo) | `09e6dc3c1b4f8ee8da9fc6a036708ac94b9ddfb6050339bf4fe317357f20076e` |
| `$DSH_HOME/.agent-presets/orchestrator/preset.yml` | `09e6dc3c1b4f8ee8da9fc6a036708ac94b9ddfb6050339bf4fe317357f20076e` |

Deployed directory mode `700`; both files mode `600` — mirroring the roster's own owner-only tightening of copied presets.

## 4. Risk analysis and honest residual gaps

- **A broken preset is surfaced, not silently skipped.** The roster reports a directory whose composition is missing or unloadable as a roster row carrying a `broken` reason, precisely so a malformed preset is visible rather than failing at first mount.
- **A broken or mis-rowed preset would fail any session that selects it.** Deployment was verified to avoid this, but the exposure is real for future edits.
- **Sessions already running are not disturbed.** A session keeps the standing composition it joined; the composition a running session joined outlives its file changing or disappearing.
- **Four capabilities were removed** from the orchestrator surface relative to `standard`: `ralph`, `pwsh`, and the `codex` / `claude-code` subagent variants. This is a deliberate cost of the delta, recorded as a cost.
- **Nothing changes by default.** Because `agent-presets.default` stays `standard`, the practical effect is nil until a Human selects the preset. Only a session that names it gets the narrowed surface.
- **Divergence is not self-healing.** A preset is a copy: a later change to the shipped `standard` preset does **not** propagate here. Re-derivation is manual; this change creates no mechanism that automates it.
- **The preset is not itself a security boundary.** The control plane (`orchestrator/contract.md`, THREAT-025) remains the boundary that holds regardless of which preset a session selects.

## 5. Verification

### 5.1 Harness

`runs/orchestrator-preset-2026-09-12/verify_preset.py` → **24 passed, 0 failed** (`verification.txt`). It asserts: repo sources exist; deployed files exist and match their sources byte-for-byte by SHA-256; the composition parses as a list of named, uniquely-identified rows (recursively); the four expected rows are absent **as rows**; the recursive delta is exactly 4 with nothing added; `standard`, the profile patch, and all pre-existing presets are unchanged; exactly one preset was added; and `agent-presets.default` is still `standard`.

Repo gate: `python3 tests/validate_config.py` → **456 passed, 0 failed** (exit 0) — identical to the pre-change baseline. `tests/unit/test_config.py` → 5 passed.

### 5.2 Live roster evidence

Through the real roster API (`@deepseek-ai/dsh-agent-presets`) against the live user preset root — recorded in `roster-discovery.json` and `roster-mount-readiness.txt`:

| Check | Result |
|---|---|
| Roster rows | **16** (was 15) |
| Rows reported `broken` | **0** |
| `orchestrator` present | yes — `trust: user`, `broken: none` |
| `writableRoot(roots)` | `/home/administrator/agent-workspace/.dsh/.agent-presets` — **equals the deployment target** |
| Metadata read via roster reader | description returned correctly |
| `readComposition` | 14 722 chars; 15 top-level rows |
| Row pattern `- id: tool-ralph` | **false** (correctly absent as a row) |

`broken: none` is the roster's own pre-mount health gate: a preset is reported broken when its composition is missing or unloadable under the Loader's own dialect (`!!js` included) or is not a list of named plugin rows.

### 5.3 Scope limit — stated, not hidden

**No in-session mount was performed.** `mountPreset()` needs a live agent context (the agent factory's `setup` hook) and `inactiveRows()` needs a Loader `EntryTree`; neither is reachable from outside a running session. What is proven is that the roster discovers the preset, resolves its directory, reads its composition with the loader's own dialect, and reports it mountable. What is **not** proven here is that a session has selected it. That is a per-session Human action in the Web GUI (`agentPreset.select`).

### 5.4 Two defects found by verification

Both produced silent false confidence and are recorded for that reason.

**(a) The nested-row counting trap** (§3). A top-level-only check passes while three denied rows are still present.

**(b) `preset.yml` malformed YAML, failing silently.** The first authored description was `description: Coordination and delegation layer: scopes objectives, ...`. The inner `": "` makes it invalid YAML (`ScannerError: mapping values are not allowed here`). Metadata read failure **degrades to no metadata by design**, so the preset still discovered and mounted cleanly while its description silently disappeared — and only asserting the *resolved value* through the roster API caught it. Fixed by single-quoting the value. Lesson: metadata correctness must be verified by reading the resolved description, never by asserting that the file exists.

### 5.5 Notes on two distracting signals

- `settings.yaml` is **not** whole-file-frozen and must not be hashed as an invariant: the `mnemon` section gained `displayMode`, `taskAgentModel`, and `embedding` from another subsystem while this change was in flight. An earlier harness check failed on the file hash; it was corrected to assert the actual invariant (`agent-presets.default == 'standard'`).
- The composition file contains the string `tool-ralph` exactly once — inside its own **header comment**, which documents the delta table. It is not a row. Structural (recursive row-id) checks are authoritative here; substring checks are not.
- Deployment was initially blocked by a **sandbox mount**, not by the host: `mountinfo` showed the `/dev/sdd` superblock as `rw` while the `/` mount flag was `ro`, so `touch $DSH_HOME/.probe` returned `Read-only file system`. That was a property of the session's file policy at the time and disappeared when the policy widened. It is not a standing constraint on the repository or on this change.

## 6. Rollback

Roster discovery is unmemoized, so removal takes effect on the next read, and sessions already joined keep the standing mount they joined.

```sh
rm -rf "$DSH_HOME/.agent-presets/orchestrator"
```

Then confirm: roster rows return to 15, `orchestrator` no longer resolves, and the 15 pre-existing presets are untouched (`runs/orchestrator-preset-2026-09-12/backups/presets-before.txt` records the pre-change set). Repo-side artifacts (`orchestrator/*`, the ADR, this document, the config edits) are independent of the deployment and remain valid documentation of a rolled-back deployment.

Pre-change backup held at `runs/orchestrator-preset-2026-09-12/backups/`: `presets-before.txt` (15 presets), `cordis.patch.yml.pre-orchestrator`, `settings.yaml.pre-orchestrator`.

## 7. Approval

This was executed under a controlled DSH composition exception pattern (ADR 0001 D4/D7; ADR 0003 D8), on the Human's explicit instruction (2026-09-12). The write surface was confined to the user preset root `$DSH_HOME/.agent-presets/` — the roster's own writable user root, verified equal to `writableRoot(roots)` — plus project files. The DSH checkout was not modified.

**Change the global default preset** — i.e. point `settings.yaml` `agent-presets.default` at `orchestrator` — is a **separate decision** and is explicitly **out of scope** here. It would alter the composition of every new session, and ADR 0004 D5 deliberately leaves it with the owner.

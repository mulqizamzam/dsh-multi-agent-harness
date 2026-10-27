# ADR 0004 — Orchestrator Role Preset (root-session composition)

- **Status**: accepted and **implemented** (2026-09-12, Human decision — the owner asked for the Orchestrator to become a real, deployable role and selected the "selectable/deployable preset" option over the documentation-only completion).
- **Date**: 2026-09-12
- **Architecture note (2026-10-10)**: the initial deployment model — copies placed under the user preset root `$DSH_HOME/.agent-presets/orchestrator/` — was **retired** by the plugin-registration cutover. As of that date the `dsh-multi-agent-harness` plugin (`index.js` + `cordis.patch.yml`) registers the presets **straight from the repo** at `agents/<id>/` and `orchestrator/`; `$DSH_HOME/.agent-presets/` no longer exists and `$DSH_HOME/.agent-presets/orchestrator/` is not a populated path. This ADR's *decision* (D1–D6) is unchanged; only the *deployment mechanism* changed. The verification block is updated to reflect the new gate.
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (unchanged; no DSH core modification)
- **Scope**: `multi-agent-harness/` plugin, registered straight from `agents/<id>/` and `orchestrator/` via `dsh-multi-agent-harness/index.js`. As of 2026-10-10 this no longer writes to or reads from `$DSH_HOME/.agent-presets/`. Does **not** modify the DSH checkout `/home/administrator/deepseek-harness/` (read-only), the profile layer `$DSH_HOME/profiles/web/cordis.patch.yml`, or any shipped preset.
- **Amends**: ADR 0001 Decision 3 (hybrid orchestrator) — **refines the composition of the root session; does not reverse the architecture.** Supersedes the recorded value `orchestrator_preset: standard` in `config/role-preset-mapping.yaml` (`draft_artifacts`) and the Phase-1C statement in `docs/phase-1/0002-role-isolation-draft.md` §"Constraints" item 3.

---

## Context

ADR 0001 Decision 3 established the **hybrid** orchestrator: the primary orchestrator is the **root/main session** acting as coordinator, with structured `workflow` scripts for deterministic fan-out. That decision is unchanged and is not revisited here.

It left one thing unspecified: **how the root session is composed.** The recorded answer was "the shipped `standard` preset" — `config/role-preset-mapping.yaml` (`draft_artifacts.orchestrator_preset: standard`) and `docs/phase-1/0002-role-isolation-draft.md` §"Constraints" item 3:

> "the orchestrator stays on the shipped `standard` preset (broad tool surface). The security boundary is the control plane (THREAT-025), not the session's tool list; the session `toolFilter` intent is recorded but the root session is not per-role narrowed in this draft."

The verified state that motivates this ADR:

1. **The orchestrator has no preset of its own.** At the time of this decision the user preset root `$DSH_HOME/.agent-presets/` held fifteen `role-*` directories (one per specialist) and no `orchestrator` directory. (That root was retired on 2026-10-10 by the plugin-registration cutover — see the Architecture note in Status — but the *finding* stands: there was no orchestrator preset.) The shipped presets were `standard`, `code`, `cordis`, `minimal` (`/home/administrator/deepseek-harness/apps/cli/config/agent-presets/`).
2. **The root session therefore runs the `standard` preset**, whose persona is `You are a coding agent powered by the {{model}} model.` (from `standard.patch.yml:14` — the shipped standard patch is the deployment source of truth). Note: the working directory is NOT referenced via `{{cwd}}` here; it is delivered separately as a runtime-context section. A coding-agent persona is not a coordination identity.
3. **The orchestrator's declared `toolFilter` is currently unenforced.** `config/role-preset-mapping.yaml:367-392` declares the orchestrator's `allow` and `deny` sets, but nothing **composes** them: the field is a recorded intent (`orchestrator/contract.md` treats the control plane, not the session tool list, as the security boundary — THREAT-025). The concrete, verified divergence: the orchestrator's deny list names `ralph` (`config/role-preset-mapping.yaml:375`) and its notes say "ralph is a fresh-agent loop, not orchestration" (`:390-392`), yet the `standard` preset the root session runs mounts `tool-ralph` (`standard/agent.cordis.yml:230-231`) — so the live root session carries a tool its own declared policy denies.

The owner's instruction resolves the open item: make the Orchestrator a real role that can be **selected and deployed**, not merely documented.

## Decision

### D1 — The orchestrator gets its own agent preset

A new preset with id `orchestrator`, containing `agent.cordis.yml` (composition) and `preset.yml` (display metadata). **Deployment mechanism (as amended 2026-10-10):** the preset lives in the repo at `orchestrator/` and is registered straight into DSH by the `dsh-multi-agent-harness` plugin (`index.js` + `cordis.patch.yml`) — there is no longer a copy step and no `$DSH_HOME/.agent-presets/orchestrator/` directory. The repo source is both the source of truth and the live artifact. This mirrors the `agents/<id>/` registration used for all fifteen specialists.

The user preset root was package-owned (`USER_PRESET_DIR = '.agent-presets'`) and auto-discovered with `includeUserRoot` enabled (verified: `docs/phase-1/0003-d4-composition-exception-change-request.md:30`). *(Amended 2026-10-10: under the current plugin-registration architecture discovery reads the repo sources directly, so this sentence describes the retired mechanism for historical continuity, not the active path.)*

**Where the binding is declared (and where it cannot be).** The orchestrator→preset binding is declared in `config/role-preset-mapping.yaml` under `draft_artifacts.orchestrator_preset`. It is deliberately **not** a `preset:` property on the `orchestrator:` entry, for two verified reasons: that entry's schema (`schemas/role-mapping.schema.json`, `$defs.orchestratorEntry`) is `additionalProperties: false` over a fixed property set, so an extra property fails `tests/validate_config.py` (observed: `Additional properties are not allowed ('preset' was unexpected) at ['orchestrator']`); and `preset_naming_convention: 'role-<id>'` does not derive the orchestrator's id, because that id is `orchestrator`, not `role-orchestrator`. The binding is therefore **not derivable from the convention** and must be stated explicitly somewhere — `orchestrator_preset` is that place. This ADR does not modify the mapping schema.

### D2 — The preset is DERIVED from `standard`, not re-authored

The composition is the shipped `standard` preset with a **minimal, enumerated delta**: the `persona` text is replaced with the orchestrator persona, and exactly four rows are deleted. Reason: a known-good composition that is copied and narrowed has a far smaller failure surface than a hand-built one, and the delta stays auditable as a diff. This follows the roster's own authoring model, where a new preset is a whole-directory copy of an existing one (verified: `packages/preset/agent-presets/README.md`, §"Authoring").

### D3 — Where declaration and `standard` disagree, the declaration wins

The four deletions are not stylistic; each is forced by the orchestrator's already-recorded policy:

| `standard` row | Action | Authority for the change |
|---|---|---|
| `tool-ralph` | delete | orchestrator `deny` names `ralph`; mapping notes: "ralph is a fresh-agent loop, not orchestration" |
| `tool-pwsh` | delete | orchestrator `deny` names `pwsh` |
| `tool-subagent-codex` | delete | not present in the orchestrator `allow` set |
| `tool-subagent-claude-code` | delete | not present in the orchestrator `allow` set |

This makes the preset the **first enforcement point** of the orchestrator's declared tool surface: for any session that selects it, the declared `toolFilter` stops being an aspiration and becomes the composed reality.

Two of the four deletions rest on "not present in the orchestrator `allow` set". That test was made unambiguous on 2026-09-12, when the allow set was completed to name all fifteen `subagent_<id>` instances. Before that it named only the eight expansion instances, leaving the seven baseline ones in **neither** `allow` nor `deny`, so for those names "deliberately absent from `allow`" and "simply overlooked" were indistinguishable. `tests/validate_config.py` now asserts the coverage (`orchestrator allow covers all 15 instances`), so this derivation can no longer be weakened by an incomplete allow set.

### D4 — The binding stays `root_session`

This ADR changes **how** the root session may be composed. It does **not**:

- make the orchestrator a spawned subagent (there is no `subagent_orchestrator` and this ADR creates none);
- alter `delegation_orchestrator_only: true` or SUBDELEGATION DENY BY DEFAULT (V1);
- add an `orchestrator` row to any specialist's delegation surface;
- move the authority gate, which remains code-enforced in the control plane and is never delegated to a subagent.

### D5 — The global default preset is NOT changed

`settings.yaml` keeps `agent-presets.default: standard`. The `orchestrator` preset is **selectable per session by the Human**; it does not become the default for sessions that name none. Changing the default alters the composition of every new session and is a separate, explicitly-scoped owner decision — deliberately out of scope here.

### D6 — The change is additive and reversible

Deployment creates one entry in the plugin's live registration table and is registered under the `orchestrator` id; no filesystem directory is touched by a deploy-copy step. Rollback is the removal of the plugin's `orchestrator` registration row (or reversion of the plugin commit); sessions already joined keep the standing mount they joined, as before.

## Consequences

**Positive**

- The Orchestrator has a real identity: a coordination persona replacing a coding-agent persona, for any session that selects it.
- The orchestrator's declared `toolFilter` becomes composable and therefore auditable against a concrete artifact, closing the divergence found in Context item 3.
- The change uses the existing, already-exercised extension mechanism (user preset root + per-role preset) with no new machinery.

**Negative / accepted**

- The orchestrator surface **loses** four capabilities relative to `standard`: `ralph`, `pwsh`, and the `codex` / `claude-code` subagent variants. This is a deliberate consequence of D3, recorded here as a cost rather than presented as a benefit.
- Divergence between policy and runtime remains **possible by choice**: a session that selects `standard` still receives the `standard` surface, including `ralph`. The preset narrows the orchestrator only where it is actually selected.
- Because D5 keeps `standard` as the default, the practical effect of this ADR is limited until a Human selects the preset (or a later decision changes the default). This is intentional for a first, low-risk step.

**Residual gaps (stated, not assumed)**

- The preset is only as sound as the `standard` composition it derives from. A future change to the shipped `standard` preset does **not** propagate into the `orchestrator` preset: presets are copies, and the composition a session joined outlives its source file changing. Divergence must be managed by re-deriving. This ADR originally created no mechanism that did so automatically; that gap was closed afterwards by `tests/unit/test_orchestrator_preset_derivation.py`, which asserts the composition is exactly the shipped preset minus the four documented rows (recursively, so the three nested deletions cannot hide) and fails with an `ACTION:` pointer when upstream drifts. It skips cleanly where the read-only DSH checkout is absent, so it is a signal in this environment rather than a universal gate.
- The preset does not, by itself, enforce anything for sessions that never select it. The control plane (THREAT-025) remains the only boundary that holds regardless of preset.

## Verification

## Verification

Under the current (post-2026-10-10) plugin-registration architecture, the preset is verified from the repo sources directly — there is no deploy-copy to byte-compare against. The evidence gate is composition integrity: the composition must be exactly the shipped `standard` preset minus the four documented deleted rows.

- `tests/unit/test_orchestrator_preset_derivation.py` — asserts the orchestrator preset is `standard` minus exactly `{tool-ralph, tool-pwsh, time-context, tool-plugin-market}`, counted **recursively** (the nested-row trap is guarded), and fails with an `ACTION:` pointer when upstream drifts.
- `tests/unit/test_preset_source_integrity.py` — asserts all 16 repo sources are mount-ready: dialect (every persona row carries `prefix`, never the legacy `text:` key), parse-shapes into a non-empty named-row list, and the registry id set == the `agents/` + `orchestrator` source set with the `role-<id>` mapping exactly derivable from `index.js`.
- `tests/validate_config.py` — schema + permission-matrix + tool-surface consistency (run in prior phase: 456 passed, 0 failed).

**Two defects were found by verification and fixed. They are recorded because both produce silent false confidence:**

1. **The nested-row counting trap.** `tool-ralph`, `tool-subagent-codex`, and `tool-subagent-claude-code` are nested inside the `delegation` group, not top-level rows. A top-level-only count reads the delta as 16→15 (delta 1) and reports those three rows as "absent" while they are still present — a **false PASS**. The true count is recursive: 29→25 (delta 4). The harness was first written with exactly that bug and was fixed with a recursive `all_row_ids()` walker; the fix is regression-tested. Any future verifier of this preset must count recursively.
2. **Malformed `preset.yml` fails silently.** The first authored description contained an inner `": "` and was invalid YAML (`ScannerError: mapping values are not allowed here`). Metadata read failure *degrades to no metadata* by design, so the preset still discovered and mounted cleanly while its description silently disappeared. It was caught only by asserting the description through the real roster API. Lesson: metadata correctness must be verified by reading the resolved value, never by asserting that the file exists.

**Two constraints on this verification, stated rather than hidden:**

- `settings.yaml` is **not** whole-file-frozen and must not be hashed as an invariant: while this change was in flight, the `mnemon` section gained `displayMode`, `taskAgentModel`, and `embedding` from another subsystem. The invariant is `agent-presets.default == 'standard'` (verified true), not a file hash. An earlier version of the harness failed on the file hash and was corrected.
- Deployment was blocked at first by a **sandbox mount**, not by the host: `mountinfo` showed the `/dev/sdd` superblock as `rw` while the `/` mount flag was `ro`, so `touch $DSH_HOME/.probe` returned `Read-only file system`. That was a property of the session's file policy at the time and disappeared when the policy widened; it is not a standing constraint on the repository.

**Post-acceptance follow-up (2026-09-12, later the same day).**

- **The per-session selection is now closed.** The one link this ADR could not verify for itself — a session actually running the preset — was exercised by the owner in a separate session. That is the owner's report, not an independently reproduced measurement here; recorded so the gap is not left looking open.
- **Six deployed compositions were stale, and the drift was in the comments.** Measuring the deployment found 6 of 16 `agent.cordis.yml` files (badsector, cfo, kai, nova, somad, zeko — the baseline seven less `cto`) differing from their repo sources. The recursive tool-row sets were **identical** in every one; the whole difference was a header comment. The repo said `Mounted 2026-09-07 …`; the deployed copies still said `DRAFT — NOT MOUNTED`, i.e. each deployed file asserted the opposite of its own true status. All six were re-synced from the repo. This is the concrete reason the repo, not the deployed tree, is the source of truth.
- **Permissions were split 8/8**, from two deployment batches: 7 baseline roles plus `orchestrator` at mode 600, the 8 expansion roles at 644. Unified to directories 700 / files 600 on the owner's instruction. Recorded as hygiene, **not** as a security fix: `$DSH_HOME` is itself mode 700, so no other principal could reach the preset root at either mode.
- **A deployment sync test now guards all of it** (`tests/unit/test_preset_source_integrity.py`, superseding the retired `test_preset_deployment_sync.py` at the 2026-10-10 cutover): source integrity for all 16 presets — every composition parses, every persona carries `prefix` not `text`, and the registry id set matches the `agents/` + `orchestrator` source set with `role-<id>` mapping derived from the plugin. As a consequence, comment drift cannot silently land (there is no deploy copy to drift from), and the dialect gate catches the exact failure mode that was observed during the cutover: every preset would mount broken if the persona key drifted back to the legacy `text:` format.

## References

- `orchestrator/AGENT.md` — orchestrator role definition (mission, capability boundary).
- `orchestrator/contract.md` — control-plane contract; the actual security boundary (THREAT-025).
- `orchestrator/agent.cordis.yml`, `orchestrator/preset.yml`, `orchestrator/policy.yaml` — the artifacts this decision creates.
- `config/role-preset-mapping.yaml` §`orchestrator`, §`draft_artifacts`.
- `config/permissions.yaml` — capability matrix (orchestrator row added alongside this ADR).
- `docs/adr/0001-multi-agent-control-plane-boundary.md` Decision 3.
- `docs/adr/0002-registry-protection-mechanism.md`.
- `docs/phase-1/0002-role-isolation-draft.md` §"Constraints" item 3.
- `docs/phase-1/0006-orchestrator-preset-composition-exception-change-request.md`.
- `packages/preset/agent-presets/README.md` (DSH checkout) — preset discovery, `broken` reporting, unmemoized reads, copy-only authoring.

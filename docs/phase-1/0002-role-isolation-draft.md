# Phase-1C — Role Isolation Draft (DRAFT ONLY)

- **Status**: DRAFT — nothing is mounted; no DSH composition, profile, preset, `$DSH_HOME`, or core change is executed.
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Inputs**: ADR 0001 (D4/D7) · `config/role-preset-mapping.yaml` (approved mapping) · `agents/<id>/policy.yaml` (Phase-1A) · `config/tool-subagent-instances.yaml` (this phase) · `docs/tool-catalog.md` (verified tool names) · DSH `apps/cli/config/agent-presets/{standard,minimal}/agent.cordis.yml` (composition reference, verified read-only).
- **Scope**: `multi-agent-harness/` only. Produces **draft artifacts only**.

> **Hard rule (this phase):** the drafts are review artifacts. The controlled DSH composition exception (ADR D4/D7) is **NOT executed**. No runtime role isolation is claimed, and **L2 isolation is not claimed until a live mounted-session negative-capability test passes.**

---

## 1. What the drafts are

| Artifact | Location | Purpose |
|---|---|---|
| Per-role Agent Preset (draft) | `agents/<id>/agent.cordis.yml` ×7 | The composition an agent on that role joins (persona + tool rows + plan/compaction realms). |
| Per-role tool-subagent instance (draft) | `config/tool-subagent-instances.yaml` (`insert_draft`) | The `- insert:` rows that expose `subagent_<id>` to the orchestrator with the role's `toolFilter`. |
| Mapping references | `config/role-preset-mapping.yaml` → `draft_artifacts` | Points the approved mapping at the drafts; status `draft`, `mount_required: false`. |

**Mechanism (verified):** the preset defines which tools an agent on that composition *can* have registered; the instance `toolFilter` defines which of those the spawned child actually *sees* and may call. `tool-fs` registers `read`/`read_image`/`edit`/`write` as one suite with no per-tool disable (VERIFIED from `packages/fs/tool-fs/src/index.ts`), so **read-only roles are enforced at the instance toolFilter, not by omitting tool-fs**.

---

## 2. Per-role register

Tool sets below are the instance `toolFilter` allow/deny (equal to the approved mapping + policy). All tool names VERIFIED against DSH 0.1.1-rc.2 catalog.

### Zeko — Operations & Infrastructure
- **Preset draft**: `agents/zeko/agent.cordis.yml`
- **Intended persona**: runtime/system ground truth; scoped operational actions; diagnosed recovery; escalate via orchestrator.
- **Allowed**: `bash`, `read`, `read_image`, `edit`, `write`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `web_search`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: all delegation/goal/ask tools, host-plane tools, `web_fetch`
- **Why bash**: ops diagnosis, process/log inspection, deployment ops (scoped). **Why scoped**: no standing server write; destructive = approval-gated HIGH.

### CTO — Engineering
- **Preset draft**: `agents/cto/agent.cordis.yml`
- **Intended persona**: coding/architecture/tests; verification-before-COMPLETE; no financial capability.
- **Allowed**: `bash`, `read`, `read_image`, `edit`, `write`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `web_search`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: delegation/goal/ask tools, host-plane, `web_fetch`
- **Unmounted candidates (not allowed yet)**: `lsp`, `str_replace_editor` — require a controlled exception + mount.
- **Why bash + write**: implement/test code within delegation; test/build evidence for verification.

### CFO — Finance (read-only)
- **Preset draft**: `agents/cfo/agent.cordis.yml`
- **Intended persona**: pricing/unit-economics/cost/ROI; analysis-only, never a transaction path.
- **Allowed**: `read`, `read_image`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `web_search`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: `bash`, `edit`, `write`, `str_replace_editor`, delegation/goal/ask, host-plane, `web_fetch`
- **Why read-only**: ISO-002; financial analysis is analysis-only; transactions always delegated + Human-approved (RISK-003).

### Kai — Research (read-only)
- **Preset draft**: `agents/kai/agent.cordis.yml`
- **Intended persona**: news/trend/competitor research; sourced evidence; read-only default.
- **Allowed**: `read`, `read_image`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `web_search`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: `bash`, `edit`, `write`, delegation/goal/ask, host-plane, `web_fetch`
- **Unmounted candidate**: `web_fetch` — disabled in the standard preset (SSRF posture); enabling requires SSRF review + controlled exception.
- **Why read-only**: ISO-003 (no project file write without explicit grant).

### Somad — Social (drafting, no infra)
- **Preset draft**: `agents/somad/agent.cordis.yml`
- **Intended persona**: social strategy/content/campaigns; drafts in workspace; never publishes on its own.
- **Allowed**: `read`, `read_image`, `edit`, `write`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `web_search`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: `bash`, `str_replace_editor`, delegation/goal/ask, host-plane, `web_fetch`
- **Why no bash**: ISO-004 (no infra execution). **Why write**: content drafting in workspace. **Publishing** is not a tool: `social_publishing` is capability-level `scoped_approval`, executed only through the control plane with Human approval.

### BadSector — Adversarial Review (review-only)
- **Preset draft**: `agents/badsector/agent.cordis.yml`
- **Intended persona**: challenge/red-team/verify; review-only; PASS never authorizes; never executes.
- **Allowed**: `read`, `read_image`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: `bash`, `edit`, `write`, `web_search`, `web_fetch`, delegation/goal/ask, host-plane
- **Why no web**: reviews inspect the proposal + evidence set locally, per policy.yaml; no new fetch surface.

### Nova — Writing (project-local)
- **Preset draft**: `agents/nova/agent.cordis.yml`
- **Intended persona**: novel writing/editing/continuity; manuscript work project-local only.
- **Allowed**: `read`, `read_image`, `edit`, `write`, `glob`, `grep`, `job_kill`, `job_list`, `job_output`, `skill`, `exit_plan_mode`, `todo_write`
- **Denied**: `bash`, `web_search`, `web_fetch`, delegation/goal/ask, host-plane
- **Why no bash/web**: ISO-005 (no infra), project-local manuscript work; web can be widened per delegation.

---

## 3. Why each capability is required (cross-role rationale)

| Capability | Roles | Why |
|---|---|---|
| `read`/`read_image`/`glob`/`grep` | all | Every role needs project-local evidence/context reads. |
| `edit`/`write` | Zeko, CTO, Somad, Nova | Domain work (ops config, code, content, manuscript) requires workspace writes. |
| `bash` | Zeko, CTO | Ops diagnosis/deployment and build/test execution. |
| `web_search` | Zeko, CTO, CFO, Kai, Somad | Technical, market, research, trend context. Excluded from review-only and manuscript-local roles. |
| `job_*` | all | Collect/stop background work (delegation task lifecycle). |
| `skill` | all | Load role/project skill instructions (non-executing). |
| `exit_plan_mode` | all | Cooperative planning surface. |
| `todo_write` | all | Per-task tracking. |
| Delegation/orchestration tools | **orchestrator only** | Subdelegation DENY BY DEFAULT (V1) — no specialist may spawn, fork, message, or run workflows. |
| `ask_user_question` / goals | **orchestrator only** | Escalation and objective tracking flow through the orchestrator; specialists report to it. |

---

## 4. Role isolation assumptions

1. **toolFilter is the capability boundary** (L2, config-level): a filtered tool vanishes from the child's schema and rejects execution. **This is not complete security isolation** (ADR 0001) — sandbox/approval remain session-level.
2. **Sandbox/approval are per-session, not per-agent**: all specialists share the orchestrator session's `workspace-write` + `ask` baseline. Read-only roles rely on toolFilter (no `edit`/`write`/`bash` in allow) for their no-mutation posture, not on a per-agent sandbox.
3. **Persona is a prompt, not a boundary**: a role's persona guides behavior; enforcement comes from toolFilter + gates + audit.
4. **`report` is child-scoped** (VERIFIED) and cannot be filtered out of a continuable child — acceptable: it only carries a result to the parent, it is not a capability.
5. **Spawn provider supports `persona` + `toolFilter` + `maxDepth`** (config keys VERIFIED in `tool-subagent/src/index.ts`); runtime capability acceptance is **ASSUMED** until a live mounted-session test passes.
6. **Roles do not read/write `state/registry/` or `audit/` directly** — protected paths per ADR 0002; even write-capable roles must not have them in delegation scope.

## 5. Inherited-composition risk (explicit)

1. **tool-fs atomicity**: `read`/`read_image`/`edit`/`write` register together; read-only roles therefore have `edit`/`write` *registered* in their preset and are protected only by the instance toolFilter. A mis-configured instance (missing deny) would silently widen CFO/Kai/BadSector. **Mitigation**: the validator asserts instance allow/deny == mapping == policy, and the live negative-capability tests below verify actual rejection.
2. **Session sandbox inheritance**: a specialist with `bash` can write anywhere in the shared workspace, including near protected paths. Contained by execution gate + audit (ADR 0002); **not** hard path isolation.
3. **Orchestrator root session**: the orchestrator stays on the shipped `standard` preset (broad tool surface). The security boundary is the control plane (THREAT-025), not the session's tool list; the session `toolFilter` intent is recorded but the root session is not per-role narrowed in this draft.
4. **`!!js` YAML tags** in drafts are DSH loader extensions; the validator parses them as opaque strings (never evaluates).

---

## 6. Exact DSH composition changes that WOULD be required to mount (NOT EXECUTED)

To go from draft to live, a **separate, reversible, Human-approved controlled exception** would:

1. **Copy the 7 preset drafts** into the user Agent-Preset root so the roster discovers them:
   - `$DSH_HOME/.agent-presets/role-zeko/agent.cordis.yml` … `role-nova/agent.cordis.yml`
   - (the roster is `dsh-agent-presets`; the writable root is `$DSH_HOME/.agent-presets`, carrying shell-access trust — VERIFIED from the web-app bundle patch.)
2. **Insert the 7 tool-subagent instance rows** (from `config/tool-subagent-instances.yaml` `insert_draft`) into a profile composition layer (e.g. a project overlay / the profile's `cordis.patch.yml`), exposing `subagent_<id>` to the orchestrator.
3. **Verify the roster** — `ctx.agentPresets.list()` shows the 7 role presets; instances resolve.
4. **Run the live negative-capability tests** (§8) in a mounted session.
5. **Record the exception** — reversible patch/record + per-case approval, per ADR D7.

**Files that WOULD be touched during the controlled exception** (outside `multi-agent-harness/`):
- `$DSH_HOME/.agent-presets/role-<id>/agent.cordis.yml` (7 new files, preset root)
- The profile's `cordis.patch.yml` (or a project overlay composition) — add 7 `tool-subagent-<id>` rows
- Optionally `$DSH_HOME/settings.yaml`/`agent-presets` default if the project requires joining a specific preset

**Files NOT touched, ever**: DSH core (`/home/administrator/deepseek-harness/`), DSH base/web bundle patches, the shipped `standard`/`minimal`/`code`/`cordis` presets.

## 7. Rollback procedure (for the later controlled exception)

1. **Revert the composition**: remove the 7 `tool-subagent-<id>` rows from the profile/overlay (keep the saved patch as the restore point).
2. **Remove the preset dirs**: delete `$DSH_HOME/.agent-presets/role-<id>/` (roster discovery is unmemoized — a deleted dir disappears on next read; a broken preset lists as `broken`, never auto-skips — VERIFIED).
3. **Restart / re-mount** the affected session so the standing mounts drop.
4. **Verify restoration**: `ctx.agentPresets.list()` no longer shows `role-*`; `subagent_<id>` no longer resolves; the standard preset is the active composition.
5. **Audit**: record the rollback event; confirm no session policy change occurred (the exception never touches sandbox/approval policy).

## 8. Live negative-capability tests required after mounting

Only after these pass in a **live mounted session** can runtime role isolation be claimed:

| Test | Setup | Expected |
|---|---|---|
| ISO-LIVE-001 | mount `role-cfo`; spawn `subagent_cfo` | child sees NO `bash`/`edit`/`write` in its schema |
| ISO-LIVE-002 | `subagent_cfo` attempts `write` | tool call REJECTED (absent from schema) |
| ISO-LIVE-003 | `subagent_badsector` attempts `web_search` | REJECTED (absent from schema) |
| ISO-LIVE-004 | `subagent_nova` attempts `bash` | REJECTED |
| ISO-LIVE-005 | any specialist attempts `subagent`/`workflow`/`send_message` | REJECTED (subdelegation DENY) |
| ISO-LIVE-006 | `subagent_zeko`/`subagent_cto` attempts write to `state/registry/` | REJECTED by execution gate + audit (ADR 0002) |
| ISO-LIVE-007 | spawn fails with unknown `toolName` | fails loudly (config rejects) |

Until ISO-LIVE-001..007 pass, isolation is **L1-design only** — no runtime claim.

---

## 9. Status

- **Drafts**: complete (this document + 7 `agent.cordis.yml` + `config/tool-subagent-instances.yaml`).
- **Validation**: `tests/validate-config.py` 162 checks pass (schema, tool-name, allow∩deny, instance==mapping==policy, preset draft parse).
- **Mounted**: none. **Runtime isolation claimed**: none. **L2 claimed**: none.
- **Next (not executed here)**: Human review of these drafts, then the controlled exception + live tests.

*Version-pinned to DeepSeek Harness 0.1.1-rc.2. Draft only — nothing mounted, no DSH core/profile/preset modified, no session policy change.*
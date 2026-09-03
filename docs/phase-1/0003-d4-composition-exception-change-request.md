# CHANGE REQUEST — Controlled DSH Composition Exception: D4 Role Isolation (MOUNT)

- **STATUS = PENDING_HUMAN_APPROVAL**
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Type**: Controlled DSH composition exception (ADR 0001 Decision 4/7; security spec §15 condition 5) — **the one approved-in-principle exception to the "DSH profile/preset change is a per-case exception" boundary.**
- **Prepared from**: ADR 0001 · ADR 0002 · `docs/phase-1/0001-phase-1-implementation-spec.md` · `docs/security/0001-control-assurance-spec.md` · `docs/security/0002-threat-model-and-control-architecture.md` · `docs/design/0001-control-design-and-test-plan.md` · `docs/phase-1/0002-role-isolation-draft.md` (Phase 1C) · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · `agents/<id>/agent.cordis.yml` (Phase-1C drafts).

> **This document is the single reviewable artifact.** Approval here authorizes the exact file changes in §1–§5 and the live tests in §9–§10. Nothing is executed before approval. On approval, the mount procedure (§6) runs as a **separate, reversible** step with a recorded rollback path (§8).

---

## 0. Scope statement

This exception:
- **Mounts** 7 role Agent Presets and **exposes** 7 per-role `tool-subagent` instances so the orchestrator can spawn role-isolated specialists (D4).
- **Does NOT** modify DSH core. **Does NOT** change sandbox/approval session policy. **Does NOT** touch anything outside the D4/D7-approved scope.

---

## 1. Exact files OUTSIDE `multi-agent-harness/` that would be changed

| # | Path | Change |
|---|---|---|
| 1–7 | `$DSH_HOME/.agent-presets/role-zeko/agent.cordis.yml` … `role-nova/agent.cordis.yml` (7 new files) | Create preset composition (verbatim copy of the Phase-1C drafts — checksums in §2) |
| 8 | `$DSH_HOME/profiles/web/cordis.patch.yml` | **Append** 7 `tool-subagent-<id>` rows to the existing `- insert:` block (§4) |

- `$DSH_HOME` = `/home/administrator/agent-workspace/.dsh` (this environment).
- **No other file** inside or outside `multi-agent-harness/` is changed. In particular: DSH checkout `/home/administrator/deepseek-harness/` is **read-only**; base/web bundle patches, shipped presets (`standard`/`minimal`/`code`/`cordis`), and `$DSH_HOME/settings.yaml` are untouched.
- The user Agent-Preset root `$DSH_HOME/.agent-presets` is **package-owned** (`USER_PRESET_DIR = '.agent-presets'`, VERIFIED) and auto-discovered by the roster with `includeUserRoot` default true — no roster reconfiguration needed.

## 2. Exact 7 Agent Preset files to mount

Each is a **verbatim copy** of the corresponding Phase-1C draft (already reviewed). SHA-256 pins the exact bytes the Human approved:

| Target file | Source draft | SHA-256 (source = mounted bytes) |
|---|---|---|
| `$DSH_HOME/.agent-presets/role-zeko/agent.cordis.yml` | `multi-agent-harness/agents/zeko/agent.cordis.yml` | `f676fd97…6a401da` |
| `$DSH_HOME/.agent-presets/role-cto/agent.cordis.yml` | `multi-agent-harness/agents/cto/agent.cordis.yml` | `1146229a…3f4b35` |
| `$DSH_HOME/.agent-presets/role-cfo/agent.cordis.yml` | `multi-agent-harness/agents/cfo/agent.cordis.yml` | `84e1dfac…6da314b` |
| `$DSH_HOME/.agent-presets/role-kai/agent.cordis.yml` | `multi-agent-harness/agents/kai/agent.cordis.yml` | `ff002fa5…199cbb3` |
| `$DSH_HOME/.agent-presets/role-somad/agent.cordis.yml` | `multi-agent-harness/agents/somad/agent.cordis.yml` | `6322d1d2…e43afff8` |
| `$DSH_HOME/.agent-presets/role-badsector/agent.cordis.yml` | `multi-agent-harness/agents/badsector/agent.cordis.yml` | `189c9f46…85f63` |
| `$DSH_HOME/.agent-presets/role-nova/agent.cordis.yml` | `multi-agent-harness/agents/nova/agent.cordis.yml` | `645b4bb7…55f2ff39` |

Each preset defines: persona, `agent-instructions`, `tool-fs` + `tool-fs-search`, `tool-jobs`, `skill-filesystem` + `tool-skill`, plan-mode realm (`isolate.planMode`), compaction realm (`isolate.compaction` + `toolResultPruner`), `tool-todo`; plus `tool-bash` (Zeko, CTO only) and `tool-web` (Zeko, CTO, CFO, Kai, Somad). **No specialist preset contains delegation/workflow/goal/ask-user rows** (subdelegation DENY BY DEFAULT).

## 3. Exact 7 `tool-subagent` instance rows to add

The 7 rows below are appended to the profile `- insert:` block. They are byte-identical to `config/tool-subagent-instances.yaml` (`insert_draft`, SHA-256 `d1866b6f…bfd1`). Config keys VERIFIED against `tool-subagent/src/index.ts` (provider, toolName, persona, toolFilter, backgroundMode, maxDepth, enableRunInBackground). Rows (allow/deny = approved mapping == policy.yaml):

- `subagent_zeko` — allow `bash, read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write`; deny all delegation/goal/ask/host-plane + `web_fetch`
- `subagent_cto` — same allow as zeko; deny delegation/goal/ask/host-plane + `web_fetch`
- `subagent_cfo` — allow `read, read_image, glob, grep, job_*, web_search, skill, exit_plan_mode, todo_write`; deny `bash, edit, write, str_replace_editor, run_code, pwsh, web_fetch` + delegation/goal/ask/host-plane
- `subagent_kai` — same allow as cfo; deny same
- `subagent_somad` — allow `read, read_image, edit, write, glob, grep, job_*, web_search, skill, exit_plan_mode, todo_write`; deny `bash, str_replace_editor, run_code, pwsh, web_fetch` + delegation/goal/ask/host-plane
- `subagent_badsector` — allow `read, read_image, glob, grep, job_*, skill, exit_plan_mode, todo_write`; deny `bash, edit, write, str_replace_editor, run_code, pwsh, web_search, web_fetch` + delegation/goal/ask/host-plane
- `subagent_nova` — allow `read, read_image, edit, write, glob, grep, job_*, skill, exit_plan_mode, todo_write`; deny `bash, str_replace_editor, run_code, pwsh, web_search, web_fetch` + delegation/goal/ask/host-plane

All instances: `provider: spawn`, `backgroundMode: continuable`, `maxDepth: 1`. Full YAML in §5 (diff) and in `config/tool-subagent-instances.yaml`.

## 4. Exact profile/overlay file to change

**`$DSH_HOME/profiles/web/cordis.patch.yml`** — the web profile's auto-loaded user patch layer (VERIFIED: profile-boot composes bundles → profile `cordis.patch.yml` → `$DSH_HOME/cordis.patch.yml` → `--patch` overlays). This is the standard DSH extension point ("Edit cordis.patch.yml, not this file"). Current content: the OMNI MCP insert only (SHA-256 `8e8bfa45…37cb054`). A pre-change backup is mandatory (§8).

## 5. Exact diff/patch representation

### 5a. 7 new preset files (new-file diffs)
For each `role-<id>`: `+++ b/$DSH_HOME/.agent-presets/role-<id>/agent.cordis.yml` = full content of `multi-agent-harness/agents/<id>/agent.cordis.yml` (checksums §2). No deletion, no edit — pure copy.

### 5b. Profile patch append (unified diff)
`--- a/$DSH_HOME/profiles/web/cordis.patch.yml` (current, backup kept)
`+++ b/$DSH_HOME/profiles/web/cordis.patch.yml` (after)

```diff
@@ -1,12 +1,88 @@
 - insert:
     - id: mcp-omni
       name: '@deepseek-ai/dsh-mcp-client'
       config:
         serverName: omni
         transport: stdio
         command: '/home/administrator/.local/bin/omni'
         args: ['--mcp']
         env:
           OMNI_AGENT_ID: 'dsh'
         cwd: '/home/administrator/agent-workspace'
         toolCallTimeoutMs: 60000
         failOnStartupError: true
+    - id: tool-subagent-zeko
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_zeko
+        persona: role-zeko
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [bash, read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]
+          deny: [subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, str_replace_editor, lsp, run_code, pwsh, web_fetch, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-cto
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_cto
+        persona: role-cto
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [bash, read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]
+          deny: [subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, str_replace_editor, lsp, run_code, pwsh, web_fetch, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-cfo
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_cfo
+        persona: role-cfo
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [read, read_image, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]
+          deny: [bash, edit, write, str_replace_editor, run_code, pwsh, web_fetch, subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, lsp, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-kai
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_kai
+        persona: role-kai
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [read, read_image, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]
+          deny: [bash, edit, write, str_replace_editor, run_code, pwsh, web_fetch, subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, lsp, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-somad
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_somad
+        persona: role-somad
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, web_search, skill, exit_plan_mode, todo_write]
+          deny: [bash, str_replace_editor, run_code, pwsh, web_fetch, subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, lsp, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-badsector
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_badsector
+        persona: role-badsector
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [read, read_image, glob, grep, job_kill, job_list, job_output, skill, exit_plan_mode, todo_write]
+          deny: [bash, edit, write, str_replace_editor, run_code, pwsh, web_search, web_fetch, subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, lsp, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+    - id: tool-subagent-nova
+      name: '@deepseek-ai/dsh-tool-subagent'
+      config:
+        provider: spawn
+        toolName: subagent_nova
+        persona: role-nova
+        backgroundMode: continuable
+        maxDepth: 1
+        toolFilter:
+          allow: [read, read_image, edit, write, glob, grep, job_kill, job_list, job_output, skill, exit_plan_mode, todo_write]
+          deny: [bash, str_replace_editor, run_code, pwsh, web_search, web_fetch, subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal, lsp, terminal_open, terminal_read, terminal_send, terminal_signal, terminal_list, terminal_close, schedule_create, schedule_delete, schedule_list, session_event_read, session_event_search, session_event_trace, session_search, session_trace, cordis_define, cordis_inspect_list, cordis_inspect_query, cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
```

## 6. Why each change is required

1. **7 preset files**: the roster (`dsh-agent-presets`, `includeUserRoot: true`) discovers presets from `$DSH_HOME/.agent-presets/`; a role preset is the only way to give a role-bound agent its own persona + tool composition in a standing, per-agent scope (ADR D4). Without them, all specialists would inherit the broad `standard` surface.
2. **7 instance rows**: `tool-subagent` instances are the orchestrator's delegation surface. Each row binds `toolName subagent_<id>` → role persona + `toolFilter` (the actual capability boundary; see §7). Without them, the orchestrator has no scoped, per-role delegation target, so role isolation cannot be exercised.
3. **Profile patch append**: `cordis.patch.yml` is the auto-loaded user layer of the active `web` profile; the 7 rows must live in a composed layer to register the instances at boot. Appending (not editing the OMNI row) preserves the existing environment.

## 7. Security impact

- **Positive — this is the D4 role-isolation enforcement point.** Once mounted + verified (ISO-LIVE), specialists get DSH-level capability boundaries (toolFilter) instead of prompt-only guidance; read-only roles lose `edit`/`write`/`bash`; no specialist gains delegation tools (subdelegation DENY BY DEFAULT preserved); BadSector stays review-only (no mutate/execute/web).
- **Residual (explicit, unchanged from Phase-1C §5)**: (a) `tool-fs` atomicity — `edit`/`write` stay *registered* for read-only roles, protected only by instance toolFilter (a mis-configured instance would silently widen CFO/Kai/BadSector; guarded by validator + ISO-LIVE-001/002); (b) bash roles share the session `workspace-write` sandbox — protected paths (`state/registry/`, `audit/`) rely on the execution gate + audit (ADR 0002); (c) the orchestrator root session remains on the broad `standard` preset — the control plane is the boundary (THREAT-025).
- **No new capability**: nothing is granted that the approved mapping does not list; `toolFilter` only *removes* tools from a child's surface. Mounting a preset is a composition change with shell-access trust — hence this exception is per-case approved + reversible.

## 8. Rollback steps

1. Restore `$DSH_HOME/profiles/web/cordis.patch.yml` from the mandatory pre-change backup (SHA-256 `8e8bfa45…37cb054`).
2. Delete the 7 preset dirs: `rm -rf $DSH_HOME/.agent-presets/role-{zeko,cto,cfo,kai,somad,badsector,nova}` (roster discovery is unmemoized — gone on next read; a broken preset lists `broken`, never silently persists).
3. Restart/reload the DSH session so standing mounts drop (web profile has HMR disabled — restart required for both apply and rollback).
4. Verify: `ctx.agentPresets.list()` no longer shows `role-*`; `subagent_<id>` no longer resolves; the `standard` preset is the active composition.
5. Audit the rollback event; confirm session sandbox/approval policy is unchanged (this exception never touches it — §13).

## 9. ISO-LIVE-001..007 test plan (after mount)

| # | Setup | Action |
|---|---|---|
| ISO-LIVE-001 | mount `role-cfo`; spawn `subagent_cfo` | inspect the child's tool schema |
| ISO-LIVE-002 | `subagent_cfo` | attempt `write` tool call |
| ISO-LIVE-003 | `subagent_badsector` | attempt `web_search` |
| ISO-LIVE-004 | `subagent_nova` | attempt `bash` |
| ISO-LIVE-005 | any specialist | attempt `subagent` / `workflow` / `send_message` |
| ISO-LIVE-006 | `subagent_zeko` / `subagent_cto` | attempt `write` targeting `state/registry/` |
| ISO-LIVE-007 | orchestrator | spawn with an unknown `toolName` (e.g. `subagent_doesnotexist`) |

Each recorded with evidence (schema dump / tool result / audit event). **L2 isolation is claimed only when 001–007 all pass.**

## 10. Expected denial behavior per live test

| Test | Expected denial |
|---|---|
| ISO-LIVE-001 | CFO schema contains NO `bash`/`edit`/`write` (absent from prompt + rejects execution) |
| ISO-LIVE-002 | `write` call REJECTED — tool not in the filtered surface |
| ISO-LIVE-003 | `web_search` REJECTED — tool not in the filtered surface |
| ISO-LIVE-004 | `bash` REJECTED — tool not in the filtered surface |
| ISO-LIVE-005 | delegation tool REJECTED — not in any specialist allow set (subdelegation DENY) |
| ISO-LIVE-006 | write to `state/registry/` DENIED by the execution gate + audit critical alert (ADR 0002) |
| ISO-LIVE-007 | spawn fails loudly (config rejects unknown tool name) — never a silent partial mount |

## 11. Remaining UNKNOWN / BLOCKED

- **UNKNOWN**: runtime acceptance of `persona`/`toolFilter`/`maxDepth` on the `spawn` provider — resolved only by ISO-LIVE-001/007; prompt-injection/external-content trust (no claim; unchanged); `web_fetch` for Kai (disabled; SSRF review required before any future enablement).
- **BLOCKED**: DSH `storage` hub, Agent Teams, out-of-process subagent backends (unmounted, out of scope — unchanged); per-role sandbox/approval differentiation (not natively expressible, ADR D1 — not requested here).

## 12. Confirmation — no DSH core modification

✅ **Confirmed.** `/home/administrator/deepseek-harness/` is read-only. No DSH package, bundle patch, shipped preset, or engine file is created, edited, or deleted. Only `$DSH_HOME/.agent-presets/` (user preset root) and `$DSH_HOME/profiles/web/cordis.patch.yml` (user profile layer) are touched — both are `$DSH_HOME`-scoped user surfaces, exactly what the D4/D7 exception covers.

## 13. Confirmation — sandbox/approval session policy NOT changed

✅ **Confirmed.** This exception mounts composition rows only. It does **not** touch the permission preset, `sandbox/mode`, or `approval/policy`. The session stays `workspace-write` + `ask`. Read-only roles are made read-only **by toolFilter**, never by a per-agent sandbox change (which is not natively expressible anyway, ADR D1).

## 14. Confirmation — only approved D4/D7 scope involved

✅ **Confirmed.** This exception is strictly the D4 role-isolation mechanism (per-role presets + per-role `tool-subagent`/toolFilter instances) within the D7-approved `multi-agent-harness/`-scope boundary + the per-case DSH composition exception. It does not: author production agent prompts, create production workflows, modify the registry/state/audit design (ADR 0002), alter gates, change the orchestrator contract, or begin any later phase.

---

## Decision block (for the Human)

- [ ] **APPROVE** — authorize §1–§5 mount + §9 ISO-LIVE tests, executed as a reversible step with §8 rollback on standby.
- [ ] **APPROVE WITH CHANGES** — specify modifications.
- [ ] **REJECT** — keep Phase-1C drafts; no external file touched.

*Prepared as the single change request. STATUS = PENDING_HUMAN_APPROVAL. Nothing mounted, no `$DSH_HOME`/profile/preset modified, no restart, no live test run, no session policy change, nothing outside `multi-agent-harness/` changed.*
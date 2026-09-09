# Tool Catalog — Scoped Capability Matrix

- **Status**: final (Phase 1A)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally from `/home/administrator/deepseek-harness/docs/tool-catalog.md` and the shipped `standard` agent preset composition)
- **Purpose**: the project's **scoped** capability matrix — which DSH tools exist, what they do, what capability class they belong to, and which roles may use them. Resolves the references in `config/permissions.yaml` and `config/role-preset-mapping.yaml`.
- **Scope**: `multi-agent-harness/`. Documentation only — nothing here mounts tools or changes DSH composition.

> This is a **project-authored** catalog. DSH ships its own generated catalog (`docs/tool-catalog.md` in the DSH checkout); this document is the project's scoped view of it, pinned to `0.1.1-rc.2`.

---

## 1. Capability classes

| Class | Meaning | Example tools |
|---|---|---|
| `read` | Read-only inspection | `read`, `read_image`, `glob`, `grep`, `web_search` |
| `write_fs` | Filesystem mutation | `edit`, `write`, `str_replace_editor` |
| `execute` | Command/shell execution | `bash`, `pwsh`, `run_code` |
| `delegate` | Spawn/control subagents | `subagent`, `subagent_fork`, `send_message`, `interrupt_agent`, `list_agents`, `report` |
| `orchestrate` | Workflow coordination | `workflow`, `ralph` |
| `job` | Background job control | `job_kill`, `job_list`, `job_output` |
| `track` | Goals / todos | `create_goal`, `get_goal`, `update_goal`, `todo_write` |
| `skill` | Load skill instructions | `skill` |
| `interact` | Human interaction | `ask_user_question`, `exit_plan_mode` |
| `host` | Host-plane / privileged surface | `lsp`, `terminal_*`, `schedule_*`, `session_*`, `cordis_*`, `run_code`, `str_replace_editor`, `pwsh` |
| `out_of_scope` | Not mounted / not for V1 | `web_fetch` (disabled), Agent-Team tools, out-of-process backends |

---

## 2. Verified tool inventory (DSH 0.1.1-rc.2)

The following names are taken from the verified DSH tool catalog. `mounted` = present in the shipped `standard` web preset composition (the model-facing surface of the current environment); `host` = host-plane row or not mounted in the standard preset; `disabled` = mounted but disabled.

### 2.1 Model-facing in the `standard` web preset

| Tool name | Package | Capability class | Description | Mounted |
|---|---|---|---|---|
| `bash` | `@deepseek-ai/dsh-tool-bash` | execute | Run shell commands in the sandboxed workspace; supports `run_in_background`, `timeoutMs` (60000 default), `sandbox_permissions` escalation | yes (non-Windows) |
| `read` | `@deepseek-ai/dsh-tool-fs` | read | Read a UTF-8 text file with line numbers | yes |
| `read_image` | `@deepseek-ai/dsh-tool-fs` | read | Read a PNG/JPEG/WebP/GIF image | yes |
| `edit` | `@deepseek-ai/dsh-tool-fs` | write_fs | Replace literal text in an existing file | yes |
| `write` | `@deepseek-ai/dsh-tool-fs` | write_fs | Create/replace a file's full content | yes |
| `glob` | `@deepseek-ai/dsh-tool-fs-search` | read | Find files by path pattern | yes |
| `grep` | `@deepseek-ai/dsh-tool-fs-search` | read | Search file contents (ripgrep) | yes |
| `job_kill` | `@deepseek-ai/dsh-tool-jobs` | job | Cancel a background job | yes |
| `job_list` | `@deepseek-ai/dsh-tool-jobs` | job | List background jobs | yes |
| `job_output` | `@deepseek-ai/dsh-tool-jobs` | job | Read a background job's output | yes |
| `skill` | `@deepseek-ai/dsh-tool-skill` | skill | Load a skill's full instructions | yes |
| `create_goal` | `@deepseek-ai/dsh-tool-goal` | track | Create a persisted same-session goal | yes |
| `get_goal` | `@deepseek-ai/dsh-tool-goal` | track | Read current goal | yes |
| `update_goal` | `@deepseek-ai/dsh-tool-goal` | track | Update goal state | yes |
| `exit_plan_mode` | `@deepseek-ai/dsh-plan-mode` | interact | Present plan / leave plan mode | yes |
| `subagent` | `@deepseek-ai/dsh-tool-subagent` | delegate | Spawn a continuable background subagent | yes |
| `subagent_fork` | `@deepseek-ai/dsh-tool-subagent` | delegate | Fork a one-shot child with inherited context | yes (continuable in web standard) |
| `interrupt_agent` | `@deepseek-ai/dsh-tool-subagent-control` | delegate | Cancel a background agent's current turn | yes |
| `list_agents` | `@deepseek-ai/dsh-tool-subagent-control/list-agents` | delegate | List continuable background subagents | yes |
| `send_message` | `@deepseek-ai/dsh-tool-subagent-control` | delegate | Continue a background subagent's conversation | yes |
| `workflow` | `@deepseek-ai/dsh-tool-workflow` | orchestrate | Run a JS workflow script (fan-out/collect) | yes |
| `ralph` | `@deepseek-ai/dsh-tool-ralph` | orchestrate | Fresh-agent Ralph iteration loop | yes |
| `ask_user_question` | `@deepseek-ai/dsh-tool-ask-user` | interact | Ask the Human a concise question | yes |
| `todo_write` | `@deepseek-ai/dsh-tool-todo` | track | Maintain structured task list | yes |
| `web_search` | `@deepseek-ai/dsh-tool-web` | read | Web search (server-side retrieval) | yes |
| `report` | `@deepseek-ai/dsh-tool-subagent-report` | delegate | Child→parent result channel (child-scoped, not filterable) | per continuable child |

### 2.2 Host-plane or not mounted in the `standard` preset

| Tool name | Package | Capability class | Notes |
|---|---|---|---|
| `web_fetch` | `@deepseek-ai/dsh-tool-web` | read | **Disabled** (`fetch: false` in the standard preset) — no fetch provider mounted (SSRF posture) |
| `pwsh` | `@deepseek-ai/dsh-tool-pwsh` | execute | Windows only; absent on this host |
| `str_replace_editor` | `@deepseek-ai/dsh-tool-str-replace-editor` | write_fs | Host-plane in web; TUI/code-mode surface |
| `lsp` | `@deepseek-ai/dsh-tool-lsp` | host | Language server protocol; not in standard preset |
| `run_code` | `@deepseek-ai/dsh-tools` | execute | Code-mode tool; not in standard preset |
| `terminal_open/read/send/signal/list/close` | `@deepseek-ai/dsh-tool-terminal` | host | Terminal surface; not in standard preset |
| `schedule_create/list/delete` | `@deepseek-ai/dsh-schedule` | host | Scheduling; not in standard preset |
| `session_event_read/search/trace`, `session_search`, `session_trace` | `@deepseek-ai/dsh-tool-session-query` | host | Session query; not in standard preset |
| `cordis_define/inspect_*/run/stop/undefine` | `@deepseek-ai/dsh-tool-cordis` | host | Cordis composition tools; not in standard preset |

### 2.3 Out of scope for V1 (verified disabled / not mounted)

| Tool group | Notes |
|---|---|
| Agent Teams (`spawn_teammate`, `team_task_*`, `followup_task`, `wait_agent`) | Experimental; **not mounted** in base/web (ADR UNKNOWN #3) |
| Out-of-process subagent backends (`subagent_codex`, `subagent_claude_code`) | **Disabled** rows in the standard preset (ADR UNKNOWN #4) |
| `storage` hub tools | **Not mounted** (`storage` row absent from base/web; BLOCKED per ADR) |
| OMNI MCP (`mcp__omni__*`) | Environment-specific MCP added by the web profile patch; not part of the DSH tool catalog and **excluded from role toolFilters** (orchestrator-session-only environment fact) |

---

## 3. Per-role availability

The authoritative role→tool mapping is `config/role-preset-mapping.yaml` (toolFilter allow/deny). Summary by capability class:

| Capability class | Zeko | CTO | CFO | Kai | Somad | BadSector | Nova | Orchestrator |
|---|---|---|---|---|---|---|---|---|
| `read` (fs) | yes | yes | yes | yes | yes | yes | yes | yes |
| `read` (web_search) | scoped | scoped | yes | yes | scoped | no | no | yes |
| `write_fs` | scoped | yes | no | no | yes | no | yes | B-lite only |
| `execute` (bash) | scoped | yes | no | no | no | no | no | B-lite only |
| `delegate` | no | no | no | no | no | no | no | **yes** (orchestrator-only, V1) |
| `orchestrate` | no | no | no | no | no | no | no | **yes** (orchestrator-only) |
| `job` | yes | yes | yes | yes | yes | yes | yes | yes |
| `track` | todo | todo | todo/get | todo/get | todo/get | todo/get | todo/get | full |
| `interact` (ask_user) | no | no | no | no | no | no | no | **yes** |
| `skill` | yes | yes | yes | yes | yes | yes | yes | yes |

Notes:
- **Delegation and orchestration tools are orchestrator-only in V1** — subdelegation is DENY BY DEFAULT (security docs §6.3; AUTH-INV-04). Every specialist deny list names all **14 sibling** `subagent_<id>` instances (exact-name matching — the real delegation surface; PRD v0.2 / ADR 0003 D4).
- `report` is child-scoped: it appears inside a continuable child regardless of the child's toolFilter (verified) and is therefore not listed in role toolFilters.
- `bash` grants the executor the full sandboxed surface (including escalation attempts); roles with `bash` must have it bounded by the session sandbox (`workspace-write`) and the execution gate.
- CFO and Kai are **read-only by design** (permissions.yaml: sandbox `read-only`, approval `never` intent) — no `write_fs`, no `execute`.
- BadSector is **review-only**: no `write_fs`, no `execute`, no `delegate`, no `web_search` (review reads project-local evidence; web evidence arrives via the evidence set).
- **PRD v0.2 expansion (ADR 0003)**: 8 new per-role instance tools — `subagent_vera`, `subagent_argus`, `subagent_atlas`, `subagent_tess`, `subagent_quill`, `subagent_scout`, `subagent_talon`, `subagent_ledger` — are **registered-pending-mount** (`config/tool-subagent-instances.yaml` draft_version 2): valid verified names in allow/deny sets, but **not present in the live composition** until the separate Human per-case mount exception (ADR 0003 D8). L-group (vera, quill, ledger): no web_search. W-group (argus, atlas, tess, scout, talon): scoped web_search, `fetch: false`. All 8 are read-only analysts (no write/exec tools).

---

## 4. Version pin and drift guard

- Every tool name above was verified against the DSH `0.1.1-rc.2` tool catalog (generated, boot-time schema) and the shipped `standard` preset composition in the DSH checkout.
- **Drift guard**: if the DSH version changes, re-run the catalog verification and update this document **and** `config/role-preset-mapping.yaml` together. A tool name in the mapping that no longer exists fails loudly at mount (config rejects unknown tool names — VERIFIED).
- `config/permissions.yaml` capability names are project-level abstractions; the tool names in this catalog are the DSH-level ground truth the control plane interprets.

---

*Version-pinned to DeepSeek Harness `0.1.1-rc.2`. No tool is mounted, disabled, or changed by this document; it records capability facts only.*
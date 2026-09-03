# CORRECTIVE CHANGE REQUEST #2 — D4/D7: Remove 25 VERIFIED_UNREGISTERED Deny Names

- **STATUS = PENDING_HUMAN_APPROVAL**
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Predecessors**: `0003-d4-composition-exception-change-request.md` (approved, rolled back) · `0004-d4-composition-exception-correction.md` (approved, `run_code` removal applied)
- **Scope**: resolve ONLY the remaining D4/D7 construction blocker — 25 tool names verified as **NOT REGISTERED** in the web+standard chain, which cannot be named in `tools.restrict()` (unknown-name rejection, `packages/core/tools/src/index.ts:1088-1091`).

> **This is a NEW approval.** The `0004` approval (run_code removal) does **NOT** authorize this correction. Nothing is executed here; this is the change request only.

---

## 1. Objective

Remove the 25 VERIFIED_UNREGISTERED names from the **seven role deny lists** (not the orchestrator entry) across 9 files, so that every name in every role deny list is a VERIFIED-REGISTERED name that `tools.restrict()` accepts. This unblocks the D4/D7 mount.

## 2. The 25-name audit

**Method**: each name verified against 5 independent sources — (1) DSH 0.1.1-rc.2 tool catalog, (2) base bundle (`packages/bundle/base/cordis.patch.yml`), (3) web profile composition (`packages/bundle/web-app/cordis.patch.yml`), (4) shipped `standard` agent preset (`apps/cli/config/agent-presets/standard/agent.cordis.yml`), (5) this session's live tool catalog.

**Classification rule**: a name is VERIFIED_UNREGISTERED only if it is present in the DSH catalog (real tool) but absent from every registered surface of the web+standard child's inherited chain (base bundle tool rows that are not web-disabled, web-app rows, standard preset rows, and the live catalog).

| Name | Package | In catalog? | Base bundle | Web-app | Standard preset | Live catalog | Classification |
|---|---|---|---|---|---|---|---|
| `str_replace_editor` | `@deepseek-ai/dsh-tool-str-replace-editor` | yes | row L384 | **disabled** (L339) | absent | absent | **VERIFIED_UNREGISTERED** |
| `lsp` | `@deepseek-ai/dsh-tool-lsp` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `pwsh` | `@deepseek-ai/dsh-tool-pwsh`(persistent) | yes | row L214 | **disabled** (L317) | present but `disabled: !!js process.platform !== 'win32'` (this host: Linux) | absent | **VERIFIED_UNREGISTERED** |
| `web_fetch` | `@deepseek-ai/dsh-tool-web` | yes | row L414 | disabled | present with `fetch: false` → **web_fetch not registered** | absent | **VERIFIED_UNREGISTERED** |
| `terminal_open` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `terminal_read` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `terminal_send` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `terminal_signal` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `terminal_list` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `terminal_close` | `@deepseek-ai/dsh-tool-terminal` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `schedule_create` | `@deepseek-ai/dsh-schedule` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `schedule_delete` | `@deepseek-ai/dsh-schedule` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `schedule_list` | `@deepseek-ai/dsh-schedule` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `session_event_read` | `@deepseek-ai/dsh-tool-session-query` | yes | backend only (`session-query-sqlite`, openAt:never) | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `session_event_search` | `@deepseek-ai/dsh-tool-session-query` | yes | backend only | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `session_event_trace` | `@deepseek-ai/dsh-tool-session-query` | yes | backend only | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `session_search` | `@deepseek-ai/dsh-tool-session-query` | yes | backend only | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `session_trace` | `@deepseek-ai/dsh-tool-session-query` | yes | backend only | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_define` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_inspect_list` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_inspect_query` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_inspect_self` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_run` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_stop` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |
| `cordis_undefine` | `@deepseek-ai/dsh-tool-cordis` | yes | absent | absent | absent | absent | **VERIFIED_UNREGISTERED** |

**Result**: 25/25 **VERIFIED_UNREGISTERED**. **VERIFIED_RESERVED: 0** (run_code already removed in 0004). **VERIFIED_REGISTERED in scope: 0 of the 25** (all safe-to-deny names remain). **UNKNOWN: 0** — none of the 25 was treated as unregistered by inference; each was verified absent from all four composition sources and the live catalog.

## 3. Proposed correction

Remove **only** the 25 VERIFIED_UNREGISTERED names from the **seven role deny lists** in these 9 files:
- `config/tool-subagent-instances.yaml`
- `config/role-preset-mapping.yaml` (role entries only)
- `agents/{zeko,cto,cfo,kai,somad,badsector,nova}/policy.yaml`

**Unchanged**: allow lists, provider, persona, backgroundMode, maxDepth, sandbox, approval, role boundaries, the **orchestrator entry** (see §4), and all unrelated configuration.

**Orchestrator entry — NOT modified.** The orchestrator is the root session (ADR Decision 3 hybrid: root session + workflow), **not** a `tool-subagent` instance. Its deny list in the mapping is documentation; it is never passed to `tools.restrict()` at construction (the root session's tool surface is the standard preset composition). None of the 25 prevents runtime construction of the orchestrator. Per the task rule, it is left unchanged.

## 4. Capability-impact analysis (per removed name)

| Name | Why not registered | Mounted anywhere? | Effective capability change on removal? | Expected runtime consequence |
|---|---|---|---|---|
| `str_replace_editor` | base row disabled by web-app; not re-mounted by standard preset | no (web) | **none** — already unreachable | deny accepted by `restrict()` (was previously rejected as unknown) |
| `lsp` | not present in base/web/standard | no | **none** | same |
| `pwsh` | web-disabled; standard row disabled on non-Windows (this host is Linux) | no (this host) | **none** — unreachable on Linux | same |
| `web_fetch` | tool-web mounted with `fetch: false` → tool not registered | no | **none** — fetch disabled by config | same |
| `terminal_*` (6) | not in base/web/standard | no | **none** | same |
| `schedule_*` (3) | not in base/web/standard | no | **none** | same |
| `session_*` (5) | only sqlite backend present (openAt:never); query **tools** not mounted | no | **none** | same |
| `cordis_*` (7) | not in base/web/standard | no | **none** | same |

**Demonstrated (not assumed)**: each name is absent from the four composition sources AND the live tool catalog (25/25 absent, verified in-session). An unregistered name in a deny list has no effective runtime capability to remove — removal changes nothing about what a role can actually do; it only makes the deny list expressible to `tools.restrict()`.

## 5. Exact diff summary

Only `deny:` flow-list hunks change. Each of the 7 role deny lists loses exactly the 25 names (the `, <name>` tokens). Representative unified diff (identical pattern in all 9 files at each role deny location):

```diff
--- config/tool-subagent-instances.yaml
+++ config/tool-subagent-instances.yaml
@@ deny (role) @@
         deny: [subagent, subagent_fork, send_message, interrupt_agent, list_agents,
                workflow, ralph, ask_user_question,
-               create_goal, get_goal, update_goal,
-               str_replace_editor, lsp, pwsh, web_fetch,
-               terminal_open, terminal_read, terminal_send, terminal_signal,
-               terminal_list, terminal_close,
-               schedule_create, schedule_delete, schedule_list,
-               session_event_read, session_event_search, session_event_trace,
-               session_search, session_trace,
-               cordis_define, cordis_inspect_list, cordis_inspect_query,
-               cordis_inspect_self, cordis_run, cordis_stop, cordis_undefine]
+               create_goal, get_goal, update_goal]
```

Full per-file unified diffs were generated and reviewed in preparation (all hunks confined to the deny lists; allow lists and all other rows untouched). No diff touches the orchestrator entry, notes, invariants, or unmounted_candidates.

## 6. Hash summary (per-file SHA-256, before → proposed-after)

| File | Before (current) | After (proposed) |
|---|---|---|
| `config/tool-subagent-instances.yaml` | `dfbe48fc53963685cb305f21ce078b7feacb5f05af0e77dd57f38eafffc94b51` | `360d9e405c013d3c8201513e4fd0d4951cd37ecae7f2ac05e217129d4f341103` |
| `config/role-preset-mapping.yaml` | `2255351d5b305137cec3223bb07a310f510d9ab9cbd162934743600b9fa997fd` | `d09418aeeb0ebc58dba9769ea554733486b4ffe6e1af897103217754b291abfd` |
| `agents/zeko/policy.yaml` | `82d385f1cc8bf89997cb036174f9f9a7b2c2ab4875f7985d1059961989eaeeb8` | `31ccde37868e36fed8d2826a69e86413caf47b3dd3d6946309e3e28e05e14d3a` |
| `agents/cto/policy.yaml` | `22c5beba28d60242acaa389add2daf2dd88b10bfad5a108fafcc13a28141ca96` | `92a747b2755cbbe32c399b5e856076c44df66f4fd03bd5657ba8ef323aca3224` |
| `agents/cfo/policy.yaml` | `18ea746f9d61b857a9afd9569b2c3d6e590b5b390768239334a6e58f382efffc` | `8402e9388ec7ae476716f33afc53cdb05ddb824ed329a52b380ea7ebdd621594` |
| `agents/kai/policy.yaml` | `d6716a5ddbf660253ad340798b527f00bdd1799044da6eff68d76669a1acd5f9` | `b99fd19062dabcb0355cbe3083408494125282ec387df4d7dd0fd8b5428cf106` |
| `agents/somad/policy.yaml` | `150783fcb2981ec22e2b6ca2fea96124e41a4b347b72ad2126d5fcef366ba430` | `54f111860ec9a311dad179ed87aac34f90434f0d18fcbeec6f676a78fb287681` |
| `agents/badsector/policy.yaml` | `996db79690ba24d372b543fcd28fee22bbe6b5a02d2f678d0bc519150a5cc3bc` | `35503a2a60bdea48448a6c36bfb5d48ded1b030d56eb62c491c6dee4264ea746` |
| `agents/nova/policy.yaml` | `1bd8903a4e6457162499a3a1bd735cd9e3dcde8ae422594821e95a35cbeef6c6` | `e470a4ba04f81857fef38f4cae230136ca5b793d8c7cd5fbeb9fac71838b2b18` |

**Proof only the approved removals occurred** (set-difference, all 7 roles, all 9 files):
```
corrected_deny == current_deny − VERIFIED_UNREGISTERED_NAMES   ✓ (removed == UNREG exactly)
allow          == unchanged                                    ✓
no new names introduced                                        ✓
```

## 7. Validation result

| Check | Result |
|---|---|
| YAML parsing (all 9 corrected documents) | ✅ valid |
| Schema validation (mapping → role-mapping.schema; each policy → role-definition.schema) | ✅ 8/8 pass |
| `allow ∩ deny` remains empty | ✅ all roles |
| mapping == policy == instance consistency (all 7 roles) | ✅ |
| Tool-name validation (every remaining deny name is VERIFIED-REGISTERED) | ✅ |
| Set-difference: `corrected_deny == current_deny − UNREG`, allow unchanged, no additions | ✅ |
| Existing suite (validator + pytest) still green on current files | ✅ (162 checks / 77 tests) |

## 8. Runtime plan (exact next sequence — NOT executed now)

1. **Backup**: snapshot all 9 files + `$DSH_HOME/profiles/web/cordis.patch.yml` (pre-change hashes recorded).
2. **Apply approved correction**: remove the 25 names from the 7 role deny lists (9 files); verify per-file SHA-256 equals the "After" column in §6.
3. **Mount seven presets**: copy `agents/<id>/agent.cordis.yml` → `$DSH_HOME/.agent-presets/role-<id>/agent.cordis.yml`; verify SHA-256 matches Phase-1C approved hashes.
4. **Resolve seven tool-subagent instances**: append the 7 `tool-subagent-<id>` rows to `$DSH_HOME/profiles/web/cordis.patch.yml`; verify resolution (`subagent_<id>` present).
5. **Run ISO-LIVE-001..007** (plan in `0003` §9 / `0004` §6).
6. **Capture runtime evidence** (schema dumps, exact denial messages, audit events) — no evidence = NOT PROVEN.
7. **Stop** — report milestone; no Phase 1D.

## 9. Rollback

**For the proposed correction (config/policy files)**: restore the 9 files from the backup made in §8 step 1 (pre-change SHA-256 = the "Before" column in §6); re-run validator + pytest to confirm green.

**For the later mount attempt**: (a) restore `$DSH_HOME/profiles/web/cordis.patch.yml` from backup (pre-change checksum); (b) delete the 7 `$DSH_HOME/.agent-presets/role-<id>/` dirs; (c) reload/restart DSH; (d) verify profile patch checksum restored, `.agent-presets` empty, session sandbox `workspace-write` + approval `ask`; (e) audit-record.

Rollback restores the exact pre-change state (byte-identical via recorded SHA-256).

## 10. UNKNOWN / BLOCKED

- **UNKNOWN**: runtime acceptance of `persona`/`toolFilter`/`maxDepth` on the `spawn` provider (resolved only by ISO-LIVE-001/007); prompt-injection handling (no claim, unchanged); any reserved name **beyond** `run_code` in the catalog (audit found none — `run_code` is the only `_NAME` reserved constant in the tools package).
- **BLOCKED**: the mount and all ISO-LIVE tests (require this correction approved + applied + DSH restart, which cannot be performed from within this session); ISO-LIVE-006 registry-write denial (execution gate is L1-design, not yet live — ADR 0002 residual gap).

---

**STATUS = PENDING_HUMAN_APPROVAL**

Previous approvals (0003, 0004) do NOT authorize this correction. No file was modified, no preset mounted, no `$DSH_HOME`/profile/preset/core changed, no restart, no session policy change, no live test run.

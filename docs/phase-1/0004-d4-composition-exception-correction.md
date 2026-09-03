# CORRECTIVE CHANGE REQUEST — D4/D7 Composition Exception (Revision 2)

- **STATUS = PENDING_HUMAN_APPROVAL**
- **Previous request**: `docs/phase-1/0003-d4-composition-exception-change-request.md` (APPROVED 2026-08-29; rolled back after ISO-LIVE-001)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Root cause of the previous failure**: every one of the 7 approved instance deny lists names `run_code`, which is the **reserved Code Mode presentation transport** in DSH 0.1.1-rc.2. `tools.restrict()` throws if any allow/deny name equals `RUN_CODE_NAME` (verified from `packages/core/tools/src/index.ts:1086`). The live error was:

  > `tools.restrict() cannot name reserved Code Mode presentation transport "run_code"; restrict end-capability tools instead`

- **Correction mandate**: remove **ONLY `run_code`** from the seven approved role deny lists; change nothing else (no other allow/deny entry, persona, provider, backgroundMode, maxDepth, sandbox, approval, or composition).
- **Audit finding (must be surfaced)**: a full reserved/unknown-name audit additionally found **25 names per deny list that are NOT registered** in the web+standard child's `restrictableNames` — these would also fail `restrict()`'s "unknown global tool" check (index.ts:1088–1091) right after `run_code` is removed. These 25 are reported for the Human decision, **not** silently applied. **The mount succeeds only if all 26 (run_code + 25) are removed.**

---

## 1. Reserved-name audit result

### 1.1 VERIFIED reserved (cannot appear in a restrict filter) — 1 name
- **`run_code`** — `RUN_CODE_NAME = 'run_code'` is the only reserved Code Mode presentation transport (`packages/core/tools/src/code-mode.ts:20`). `tools.restrict({ allow/deny: ['run_code'] })` throws at `packages/core/tools/src/index.ts:1086`. Confirmed by `packages/core/tools/tests/code-mode.spec.ts:291-292`.

### 1.2 VERIFIED not-registered in the web+standard chain — 25 names
These tools are NOT registered in a child's `restrictableNames` (the inherited global + standard-preset layers):
`str_replace_editor`, `lsp`, `pwsh`, `web_fetch`, `terminal_open`, `terminal_read`, `terminal_send`, `terminal_signal`, `terminal_list`, `terminal_close`, `schedule_create`, `schedule_delete`, `schedule_list`, `session_event_read`, `session_event_search`, `session_event_trace`, `session_search`, `session_trace`, `cordis_define`, `cordis_inspect_list`, `cordis_inspect_query`, `cordis_inspect_self`, `cordis_run`, `cordis_stop`, `cordis_undefine`.

Evidence (triple-verified):
- Absent from the base bundle tool rows (`packages/bundle/base/cordis.patch.yml`) — they are not globally registered.
- Absent from the web-app patch (its `disabled: true` rows list tool-bash/pwsh/fs/fs-search/str-replace-editor/skill/goal/plan/compaction/subagent/workflow/ralph; none of the 25 are re-mounted).
- Absent from the shipped `standard` agent preset (`apps/cli/config/agent-presets/standard/agent.cordis.yml`) — not registered at the agent plane.
- **Runtime**: all 25 are absent from this session's live tool catalog (VERIFIED, 25/25 absent).

### 1.3 VERIFIED registered (safe to deny — present in the standard preset chain)
`subagent`, `subagent_fork`, `send_message`, `interrupt_agent`, `list_agents`, `workflow`, `ralph`, `ask_user_question`, `create_goal`, `get_goal`, `update_goal`, `bash`, `edit`, `write`, `web_search`. Denying these is meaningful (they ARE reachable by a child that inherits the standard preset).

### 1.4 UNKNOWN / UNVERIFIED
**None remaining.** Every name in every deny list across all 7 roles falls into exactly one of the three categories above.

---

## 2. Exact correction (mandate: remove ONLY `run_code`)

The token `, run_code` is removed from the 7 role deny lists in **three files** to preserve three-way consistency (instance == mapping == policy):

### 2a. Instance file — `config/tool-subagent-instances.yaml`
Exact diff (7 deny lines, `-` approved / `+` corrected):

```diff
-              str_replace_editor, lsp, run_code, pwsh, web_fetch,
+              str_replace_editor, lsp, pwsh, web_fetch,        # zeko (L47), cto (L71)
-        deny: [bash, edit, write, str_replace_editor, run_code, pwsh, web_fetch,
+        deny: [bash, edit, write, str_replace_editor, pwsh, web_fetch,   # cfo (L92), kai (L116)
-        deny: [bash, str_replace_editor, run_code, pwsh, web_fetch,
+        deny: [bash, str_replace_editor, pwsh, web_fetch,                # somad (L140)
-        deny: [bash, edit, write, str_replace_editor, run_code, pwsh,
+        deny: [bash, edit, write, str_replace_editor, pwsh,              # badsector (L164)
-        deny: [bash, str_replace_editor, run_code, pwsh,
+        deny: [bash, str_replace_editor, pwsh,                           # nova (L189)
```

**Proof only `run_code` removed** (set analysis, all 7 roles): `corrected_deny == approved_deny − {run_code}`; allow sets unchanged; no new tool names introduced; `allow ∩ deny = ∅` still holds; every remaining deny name is a VERIFIED-registered name or one of the 25 reported (see §8).

- Original SHA-256: `d1866b6fc12cbc6c05fcb86580e040128c2124682a37b029d73248654530bfd1`
- **Corrected SHA-256: `dfbe48fc53963685cb305f21ce078b7feacb5f05af0e77dd57f38eafffc94b51`**

### 2b. Mapping file — `config/role-preset-mapping.yaml`
Same single-token removal at the 7 role deny locations (L50, L76, L99, L125, L151, L177, L204). (The orchestrator deny list also carries `run_code` at L235; it is not a "role" list — noted for completeness, unchanged by this mandate.)
- **Corrected SHA-256: `118507e71eb8a5680c7dacf625031c4c4e7068be205f8cb0dd7eb15a47f5bdbf`**

### 2c. Policy files — `agents/<id>/policy.yaml` (7 files)
Same single-token removal. **Corrected SHA-256:**
| Role | Corrected SHA-256 |
|---|---|
| zeko | `82d385f1cc8bf89997cb036174f9f9a7b2c2ab4875f7985d1059961989eaeeb8` |
| cto | `22c5beba28d60242acaa389add2daf2dd88b10bfad5a108fafcc13a28141ca96` |
| cfo | `18ea746f9d61b857a9afd9569b2c3d6e590b5b390768239334a6e58f382efffc` |
| kai | `d6716a5ddbf660253ad340798b527f00bdd1799044da6eff68d76669a1acd5f9` |
| somad | `150783fcb2981ec22e2b6ca2fea96124e41a4b347b72ad2126d5fcef366ba430` |
| badsector | `996db79690ba24d372b543fcd28fee22bbe6b5a02d2f678d0bc519150a5cc3bc` |
| nova | `1bd8903a4e6457162499a3a1bd735cd9e3dcde8ae422594821e95a35cbeef6c6` |

### 2d. Preset files (7 `agent.cordis.yml`)
**UNCHANGED.** They contain no toolFilter/deny lists, so they carry no `run_code` reference. Their SHA-256 values remain those recorded in the original change request (Phase 1C).

---

## 3. Why the correction does NOT broaden capability

- `run_code` was **never callable** in the standard web preset — it is reserved for the Code Mode presentation transport and cannot be registered/shadowed. Removing it from a deny list grants nothing.
- The 25 not-registered names were **never reachable** in the web+standard chain (not mounted). Denying an unmounted tool is a no-op; removing it from the deny list is a technical fix that grants nothing.
- After the full correction, the remaining deny names are exactly the registered tools a child could reach and must be denied for the role's security posture — unchanged.

## 4. Security impact
- **Neutral**: no capability is added, removed, or changed.
- **Positive**: resolves the reserved-name defect that prevented the mount entirely. No security-relevant deny is weakened (the 25 removed were never mounted).

## 5. Rollback procedure (identical to rev. 1)
1. Restore the profile patch (`$DSH_HOME/profiles/web/cordis.patch.yml`) from backup.
2. Delete the 7 preset dirs under `$DSH_HOME/.agent-presets/role-<id>/`.
3. Reload/restart DSH (web HMR disabled — restart required).
4. Verify: profile patch checksum back to pre-change; `.agent-presets` empty; session policy unchanged (`workspace-write` + `ask`).
5. Audit-record the rollback.

## 6. ISO-LIVE execution plan (conditional on FULL 26-name correction)

| Test | Setup | Expected |
|---|---|---|
| ISO-LIVE-001 | mount `role-cfo`; spawn `subagent_cfo`; inspect child tool schema | `bash`/`edit`/`write` absent; only the CFO allow set present |
| ISO-LIVE-002 | same child attempts `write` | REJECTED — tool not in child's filtered surface |
| ISO-LIVE-003 | mount `role-badsector`; spawn `subagent_badsector`; attempt `web_search` | REJECTED |
| ISO-LIVE-004 | mount `role-nova`; spawn `subagent_nova`; attempt `bash` | REJECTED |
| ISO-LIVE-005 | any specialist attempts `subagent`/`workflow`/`send_message` | REJECTED (subdelegation DENY BY DEFAULT) |
| ISO-LIVE-006 | `subagent_zeko` attempts write to `state/registry/` | expected REJECTED by protected-path control — **NOT ENFORCEABLE at runtime yet** (execution gate is L1-design, not live; ADR 0002 residual gap) → classified BLOCKED |
| ISO-LIVE-007 | unknown `toolName` (e.g. `subagent_doesnotexist`) | deterministic rejection at resolution (config rejects unknown tool names) |

## 7. L2 claim condition
**L2 role isolation is claimed ONLY when ISO-LIVE-001..005 and 007 all pass with actual runtime evidence.** ISO-LIVE-006 remains BLOCKED (execution gate not yet live). L3 is not claimed. Prompt injection remains UNKNOWN — no claim.

## 8. Additional collisions requiring Human decision

The audit found **25 not-registered names per deny list** that will also fail `restrict()`'s unknown-name check (same failure class as `run_code`). Removing `run_code` alone is therefore **insufficient to mount**. Recommended: approve removing all 25 (they are no-op denies — zero capability impact). The fully corrected deny lists would then contain only VERIFIED-registered names:
- zeko / cto (11 each): subagent, subagent_fork, send_message, interrupt_agent, list_agents, workflow, ralph, ask_user_question, create_goal, get_goal, update_goal
- cfo / kai (14 each): the 11 + bash, edit, write
- somad (12): the 11 + bash
- badsector (15): the 11 + bash, edit, write, web_search
- nova (13): the 11 + bash

---

## Decision block (for the Human)

- [ ] **APPROVE the FULL correction** — remove `run_code` (mandated) **and** the 25 not-registered names (audit-required) — **recommended**; the only configuration on which the mount can succeed.
- [ ] **APPROVE the mandated correction only** (run_code alone) — the mount will still fail on the 25 unknown names; a further correction would be required.
- [ ] **REJECT** — keep the approved-and-rolled-back state as-is.

---

*Prepared as the corrective change request. **STATUS = PENDING_HUMAN_APPROVAL.** No external file changed; no mount; no restart/reload; no `$DSH_HOME`/profile/preset modification; no session policy change; no live test run.*

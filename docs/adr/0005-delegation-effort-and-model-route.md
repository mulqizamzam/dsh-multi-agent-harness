# ADR 0005 — Delegation Effort Budget and Model Route

- **Status**: **ACCEPTED — "Approve as proposed"** (Human decision, 2026-09-13). Owner's instruction verbatim: *"APPROVE ADR 0005. REJECT perubahan implementasi tambahan yang belum diajukan di ADR ini. Status yang paling tepat: Approve as proposed."* The decisions below are now the record. **This approval carries no implementation authority**: the second sentence withholds approval from any change not stated in this file, so the lever in D6 stays unmounted.
- **Date**: 2026-09-13 (proposed and accepted the same day; the draft header's "2026-09-14" was an authoring error)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (checkout `/home/administrator/deepseek-harness`, `HEAD 7135b5958b`). Later releases require re-verification — see §Verification, "Boundary".
- **Scope**: `multi-agent-harness/`. Changes no composition, no schema, and no deployed preset. Documentation and one cross-reference only.
- **Resolves**: ADR 0001 §"UNKNOWN findings" item 5 — the `UNKNOWN` half of it ("whether they can ever be model-controlled") becomes **ANSWERED for the recorded host version**. The config-level half was already resolved in ADR 0001 and is unchanged.
- **Does not amend**: ADR 0001 Decision 1 (two-tier **permission** model), Decision 3 (hybrid orchestrator), Decision 4 (per-role preset + instance). All three stand as written.

---

## Context

A delegation policy authored **outside** this repository was put forward for evaluation. It asks for two things this project does not currently do: choosing an LLM **per assignment** (a model route per delegated task) and a **numeric threshold** at which work stops being delegated turn-by-turn and starts being fanned out as a workflow. The policy was evaluated against what the host can actually enforce in the pinned version, not against what would be desirable. The two asks do **not** have the same verdict: a per-role model route is **supported by the host and merely unmounted here** (item 2), while the numeric threshold is **not** adopted (Context item 7, Non-goals).

### 1. The call site cannot name a model — the instance scope can

The `subagent` tool schema accepts exactly three properties — `description`, `prompt`, `run_in_background` (DSH checkout `docs/tool-catalog.md:1508-1529`). There is no `model` argument and no `provider` argument, so "choose the model for this assignment" is **not expressible at the call site** by the orchestrator or by any specialist. This constrains the **call site only** — see item 2 for the instance-scope lever that does exist.

### 2. The host DOES provide a per-instance model lever; this repository has simply not mounted it

A loaded `tool-subagent` instance accepts `provider`, `toolName`, `enableRunInBackground`, `backgroundMode`, `agentOptions`, `persona`, `toolFilter`, `maxDepth` (DSH checkout `docs/config-catalog.md:2805-2825`). Note that `provider` here is the **subagent backend**, not an LLM provider.

**`agentOptions` is the model lever, and it is per instance.** The config comment reads "Agent options applied to every child; omitted fields use child-loop defaults" (`packages/subagent/tool-subagent/src/index.ts:49-52`), and its schema accepts exactly `{provider: string, model: string, maxTokens: number}`, defaulting to **undefined** so omission is preserved (`:87-91`). When a child starts, the instance passes `agentOptions`, `persona`, `toolFilter`, and `maxDepth` **together in the same request** (`:392-395`) — so **pinning a model per instance does not cost the role fence.** The base type is `AgentOptions { provider?; model?; maxTokens? }`, where `model` is the "Model id interpreted by the selected provider adapter" (`packages/core/agent/src/runtime-types.ts:24-31`).

This is the exact analogue of the Claude Code `model:` field cited in item 7: a model chosen in the **agent's own definition**, not passed at the call site. The host's equivalent of that definition is the **per-instance row**, not "deployment-time" in general.

**What actually holds this repository back is our own schema, not a host limit.** In this project, `config/tool-subagent-instances.yaml` (316 lines) carries all fifteen rows with `provider: spawn`, `toolName: subagent_<id>`, `persona: role-<id>`, `backgroundMode: continuable`, `maxDepth: 1`, and `toolFilter` — and **zero occurrences of `model`** (`grep -n model config/tool-subagent-instances.yaml` returns nothing); `agentOptions` is unused too. Adding it would not be a config-only edit: `schemas/role-mapping.schema.json:50-61` closes the `tool_instance` object with `additionalProperties: false` (line 52) over a fixed five-property set, so the field requires a schema change plus the validator that reads it. **Status: "not mounted yet", not "impossible".**

### 3. Children today inherit the parent's model route — because the lever in item 2 is unused

Absent an override, a child inherits the parent's provider/model/maxTokens route: `resolveChildAgentOptions()` spreads the parent's `provider`, `model`, and `maxTokens` **before** applying any requested override, so the override wins (`packages/subagent/subagent/src/child-agent.ts:68-83`), and the spawn provider README states the child "inherits the parent model unless overridden" (`packages/subagent/subagent-spawn-in-process/README.md:9`). **All fifteen roles currently run on the same model as the parent session.** Role differentiation in this project is persona + `toolFilter` + depth, and — because item 2's lever is unmounted — never model. This is a **consequence of a choice not yet made**, not a ceiling of the host: pinning a model per role becomes possible at the instance scope (item 2) and survives inheritance, since the instance's `agentOptions` is applied as the requested override.

### 4. The call-time model override — and the fence it drops

The workflow `agent(prompt, opts)` hook is the only place a model can be chosen **at call time, per assignment**, via independent `provider`/`model` overrides (DSH checkout `docs/tool-catalog.md:2088`; the supported set is literally `SUPPORTED_AGENT_OPTIONS = new Set(['label', 'phase', 'schema', 'provider', 'model'])` in `packages/workflow/workflow-worker-thread/src/runtime.ts:39`) — the per-instance path of item 2 is a different, static one.

That path **cannot carry a role fence**. The workflow host builds its child start request with only `prompt`, `parent`, `signal`, `outputSchema`, and `agentOptions` (`packages/workflow/workflow-worker-thread/src/host.ts:352-365`), while the subagent start request type supports `persona`, `toolFilter`, and `maxDepth` as well (`packages/subagent/subagent/src/types.ts:100-148`).

So that path trades away the role fence for a per-assignment model: a workflow child may pick a model but arrives **without its role's persona and without its role's `toolFilter`**. A workflow-dispatched `vera` or `badsector` is not the `role-vera`/`role-badsector` this repository defined — it is an unfenced agent wearing the task's wording. The instance-scope lever (item 2) is the opposite trade: a **static** model per role, with the fence fully intact.

### 5. Effect on ADR 0001

ADR 0001 UNKNOWN item 5 reads: per-call `persona`/`toolFilter`/`outputSchema` are config-level, not per-call model parameters, and "*Whether they can ever be model-controlled is UNKNOWN; assumed no* (config-only)". Items 1–3 above resolve it: the model route is controllable at the **instance scope** (`agentOptions`, carrying `persona`/`toolFilter` alongside it) and at the **call-time scope** only through the workflow hook, which is persona/`toolFilter`-blind. For `0.1.1-rc.2` the status changes from **UNKNOWN** to **ANSWERED**; ADR 0001 carries a pointer note rather than a rewrite.

### 6. Vocabulary: "tier" is already taken

"Tier" already names the **two-tier permission model** (ADR 0001 Decision 1; `README.md:118`, "two-tier model"). Separately, `LOW`/`MEDIUM`/`HIGH` are **risk classes** that a model cannot downgrade — an intrinsic HIGH has no code path down (`control/risk.py:10-22`, `orchestrator/foundation/gates.py`). Reusing "tier" for staffing choices would collide with both. This ADR therefore uses **effort budget** — how many agents, and how much scope each one carries — and nothing else.

### 7. External references (input, not authority)

Recorded as **references**, explicitly **not** decisions — none of these is adopted as a rule here. In particular, **no vendor documents a `>=3 subtask` threshold**, and no such number is stated as a rule anywhere in this ADR:

- Anthropic, *How we built our multi-agent research system* (2025-06-13): effort scaled to complexity (one agent with 3–10 tool calls; 2–4 subagents with 10–15; 10+ for complex research); multi-agent systems consume roughly **15×** the tokens of ordinary chat; and the post itself notes that coding tasks parallelize **less** readily than research. [source](https://www.anthropic.com/engineering/multi-agent-research-system)
- Claude Code's official sub-agent documentation presents `model:` as a field of the **agent definition** (frontmatter) — designating a model **per sub-agent** — not as a call argument. The host analogue is the **per-instance row** (`agentOptions.model` on `subagent_<id>`, item 2), not "deployment-time" in general and not a call argument.
- Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet*, ICLR 2024, [arXiv:2310.01798](https://arxiv.org/abs/2310.01798): self-correction without **external feedback** is unreliable — the basis for treating independent verification as a structural requirement, not a hoped-for model behavior.
- Chen et al., *FrugalGPT*, [arXiv:2305.05176](https://arxiv.org/abs/2305.05176): a model cascade can match a top-tier model at lower cost, or beat it at equal cost — the only one of these four that argues for heterogeneous model routing at all.

## Decision

### D1 — Role-bound work stays on `subagent_<id>`

Delegation of work that is **bound to a role** — verification, policy, audit, adversarial review, any task whose value depends on the role's persona, `toolFilter`, and read-only posture — goes through the per-role instance `subagent_<id>`. This is existing practice (ADR 0001 Decision 4); this ADR restates it as the **default route** precisely because a tempting alternative now exists.

### D2 — `agent()` in workflow is only for children that do not need a role fence

The workflow `agent()` hook is permitted **only** for children that genuinely require no role fence: homogeneous fan-out over independent items, structured-extraction passes, bulk collection — work where the child's identity carries no authority weight.

- Every use **must state in its own output or prompt** that the child runs **without the role persona and without the role `toolFilter`** (per Context item 4). Silent use is the failure this clause exists to prevent.
- `agent()` **must never** stand in for an assurance role (`vera`, `quill`, `ledger`, `badsector`, or any role whose read-only/no-web posture is the point). Such a call would produce an unfenced agent while the surrounding text claims a specific role ran.
- Model overrides on `agent()` do **not** buy a role boundary, and must never be used to substitute for one.

### D3 — Staffing is described as an effort budget, never as a model tier

A delegation decision is described in terms of the **effort budget**: how many agents, and how much scope each carries. Referencing an external post that recommends a specific number of agents is not a rule — this project sets **no** numeric agent-count threshold (see Non-goals).

The model route may be **pinned per role at the composition layer** (item 2), and doing so is a **controlled composition change**: it requires a per-case exception approved by the Human (the precedent is ADR 0001 Decision 4/Decision 7 and the mount verification recorded in `runs/mount-verification-2026-09-07/`), followed by the schema/validator adjustment (`schemas/role-mapping.schema.json:50-61`) and the byte-identical preset/instance sync test — **not** a change to `agent()` behavior. Until that is done, the route remains **inherited** from the parent session, and no per-role model claim may be made.

### D4 — The verification clause is referenced, not rewritten

The "reports success ≠ verified" rule and per-category verification independence **already exist** in `orchestrator/contract.md` and are **not restated** here:

- §10 "Verification & COMPLETE" (heading at line 95) — line 98 ("Agent reports success" is a claim; verified success is verification with evidence) and line 99 (independence by action category);
- §13 "Prohibitions (never)" (heading at line 142) — line 150, "Never emit COMPLETE without verification"; line 146, "Never treat BadSector PASS as authorization";
- §6 "Routing policy" (heading at line 67) — line 69 ("select the **minimum** relevant specialist set … no blanket fan-out"); §12 (heading at line 111) — line 136 (the script performs no enforcement; unresolved gate → STOP).

This ADR adds **no** parallel rule and no second source of truth for verification.

### D5 — The external policy is not adopted as written

It is **not** adopted. What survives is narrower and already shaped by this repository: role-bound delegation stays role-bound (D1), the fenced model-override path is confined to fence-free work (D2), and staffing is named honestly (D3).

### D6 — The unmounted lever is recorded as a gated open choice

The instance-scope model lever exists and is **not blocked by the host**; it is simply **unmounted here** (item 2), and it is recorded as an **available, gate-protected choice** so no reader concludes from this ADR that per-role model routing is impossible. Exercising it is a separate, explicitly-scoped decision taken through D3's gate. **Items 2 and 4 must be read together** — item 4 alone reads as "models cannot be chosen per role", item 2 alone as "just add a column"; the distinction that matters is **instance-scope vs call-time scope**. That distinction is why this ADR both forbids the `agent()` shortcut (D2) and refuses to call per-role routing impossible (D6).

**Recorded outcome (2026-09-13).** The owner accepted this ADR as proposed and, in the same instruction, rejected additional implementation changes not proposed in it. The lever is therefore **declined for now, not foreclosed**: it stays unmounted, and using it later takes a fresh owner decision plus everything D3 requires (schema change, validator, per-case composition exception, byte-identical sync test).

## Consequences

**Positive**

- One meaning per word: "tier" keeps meaning the permission model, and effort means staffing. No new ambiguity enters a config vocabulary that is validated by test.
- The tension found in Context item 4 is now **written down**. It was previously visible only to someone who read both `runtime.ts` and `workflow-worker-thread/src/host.ts`; the next person to consider "just pick a better model for the hard task" finds the cost stated next to the capability.
- The **per-role** option is recorded as available rather than foreclosed, and as **declined for now** by the owner's acceptance instruction: a reader who wants model heterogeneity learns that the host supports it at the instance scope with the fence intact (item 2), which gate must be opened to use it (D3), and that opening it is not implied by this ADR.
- ADR 0001 UNKNOWN item 5 stops being an open question that every reader must re-derive.

**Negative / accepted**

- **Cost-heterogeneous routing is not available today.** The lever that would deliver it (per-role `agentOptions`, the FrugalGPT argument in item 7) is unmounted, because mounting it means a composition change under Human-approved per-case exception **plus** a schema/validator change **plus** the sync test — a cost this ADR deliberately does not pay.
- **The call-time path is the wrong tool here, and looks like the right one.** `agent()` is the only place a model is chosen per assignment (item 4), so the instinct "route the hard task to a stronger model" leads straight into the one path that silently drops persona and `toolFilter`. Every workflow `agent()` call must therefore be justified in writing, and some legitimate uses will carry a note a reader finds redundant — accepted as the price of the guarantee.
- If D2 is violated, the failure is **silent and directionally wrong**: an unfenced child returns a plausible result while the surrounding text still claims a named role ran. Nothing in the harness detects this — no gate reads "which role did this child actually carry". And because the fenced instance path is unmounted, the only *currently active* model-override route is the unfenced one, so reaching for heterogeneity now would be a **posture regression presented as an improvement**; D2 holds that line until D3's gate is opened.

## Verification

**How to re-run this check.** Each claim above is reproducible by reading the named file at the named lines; the two DSH-generated catalogs live in the checkout, not in this repository:

```bash
# 1. the lever is unmounted here (both commands: expect no output)
grep -n 'model\|agentOptions' config/tool-subagent-instances.yaml
# 2. the DSH per-instance lever: field, schema, fence travelling with it, base type, catalog
DSH=/home/administrator/deepseek-harness
sed -n '24,31p' $DSH/packages/core/agent/src/runtime-types.ts                       # AgentOptions
sed -n '49,52p;87,91p;392,395p' $DSH/packages/subagent/tool-subagent/src/index.ts   # field, zod, start request
sed -n '2805,2825p' $DSH/docs/config-catalog.md                                     # documented config field
# 3. our schema closes tool_instance, so mounting needs a schema change (:52)
sed -n '50,61p' schemas/role-mapping.schema.json
# 4. child inherits the parent route, but an override wins
sed -n '68,83p' $DSH/packages/subagent/subagent/src/child-agent.ts
sed -n '9p'     $DSH/packages/subagent/subagent-spawn-in-process/README.md
# 5. the call-time override, and what the workflow host does NOT forward
sed -n '2088p' $DSH/docs/tool-catalog.md
sed -n '39p'   $DSH/packages/workflow/workflow-worker-thread/src/runtime.ts
sed -n '352,365p' $DSH/packages/workflow/workflow-worker-thread/src/host.ts
sed -n '100,148p' $DSH/packages/subagent/subagent/src/types.ts
# 6. contract anchors cited in D4 (heading lines: §6=67, §10=95, §12=111, §13=142)
grep -n '^## ' orchestrator/contract.md; sed -n '69p;98p;99p;136p;146p;150p' orchestrator/contract.md
# 7. re-run baselines
sha256sum orchestrator/contract.md | cut -c1-24     # fac1498147e61f51227edbf1 (unchanged by this ADR)
sha256sum docs/adr/0001-multi-agent-control-plane-boundary.md | cut -c1-24
#    was 1e4db5dcb93452b4ca2da1c8 before this ADR added its one-line pointer note; the
#    expected value is therefore whatever the pointer note produces, not the old hash.
```

**Boundary (stated, not hidden).**

- The finding is pinned to host **`0.1.1-rc.2`** (checkout `HEAD 7135b5958b`). Two of its facts belong to *this* build and each needs its own re-check on a later release: item 2's lever (if `agentOptions` stops being forwarded to the child) and item 4's gap (if the workflow host starts forwarding `persona`/`toolFilter`, D2's rationale weakens). The version pin is the trigger for re-checking, not a permanent claim.
- **Items 2 and 4 must be read together** (see D6): each is a property of *this* host build, and neither is a standing claim about the host in general.
- Line numbers for the two **DSH-generated catalogs** resolve against the **checkout**, not against this repository's own `docs/tool-catalog.md` — a different, project-authored document of **125 lines** where those numbers do not exist. Both catalogs are generated, so a regeneration can move every cited line while the content stands; prefer the surrounding heading text when re-locating. External references (item 7) are inputs recorded with their URLs and are not verifiable from this repository; only D1–D3 and D6 are decisions.

## Non-goals

- Does **not** change any `toolFilter`, `persona`, `maxDepth`, or `backgroundMode` value, and does not touch `config/tool-subagent-instances.yaml`, `config/role-preset-mapping.yaml`, `agents/`, or any deployed preset.
- **Does not mount `agentOptions` now** — no `agentOptions`/`model` field is added to any instance row, schema, mapping, or validator by this ADR. The lever is recorded as available and gated (D6), not exercised.
- Does **not** set a numeric agent-count, token, or cost threshold — no `>=3 subtask` rule, and no `15×` budget cap. Those numbers appear in this ADR only as cited external observations.
- Does **not** move any gate, change the authority boundary, or relax the read-only posture of any assurance role.
- Grants **no implementation authority**. The owner's 2026-09-13 acceptance ("Approve as proposed") came with an explicit rejection of additional implementation changes not proposed here, so nothing in `config/`, `schemas/`, `agents/`, or the deployed presets is approved by this file. For the record: the independence-gate and evidence-fabrication fixes committed the same day (`594b0ae`) were ordered by a separate direct instruction, not by this ADR, and this ADR neither ratifies nor extends them.

## References

- `docs/adr/0001-multi-agent-control-plane-boundary.md` — UNKNOWN findings item 5; Decision 1 (two-tier permission), Decision 3, Decision 4.
- `docs/adr/0003-specialist-pool-expansion.md`, `docs/adr/0004-orchestrator-role-preset.md`.
- `orchestrator/contract.md` §6, §10, §12, §13 — the routing, verification, workflow, and prohibition clauses referenced in D4.
- `config/tool-subagent-instances.yaml`; `schemas/role-mapping.schema.json:50-61`; `control/risk.py`; `orchestrator/foundation/gates.py`; `docs/authority.md`.
- DSH checkout `0.1.1-rc.2` (`HEAD 7135b5958b`): `docs/tool-catalog.md:1508-1529`, `:2088`; `docs/config-catalog.md:2805-2825`; `packages/subagent/tool-subagent/src/index.ts:49-52`, `:87-91`, `:392-395`; `packages/core/agent/src/runtime-types.ts:24-31`; `packages/subagent/subagent/src/child-agent.ts:68-83`; `packages/subagent/subagent/src/types.ts:100-148`; `packages/subagent/subagent-spawn-in-process/README.md:9`; `packages/workflow/workflow-worker-thread/src/runtime.ts:39`; `packages/workflow/workflow-worker-thread/src/host.ts:352-365`.
- Mount gate for D3/D6: ADR 0001 Decision 4/Decision 7; `runs/mount-verification-2026-09-07/`; `docs/phase-1/0006-orchestrator-preset-composition-exception-change-request.md`.
- External (inputs, not authority): [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system); [arXiv:2310.01798](https://arxiv.org/abs/2310.01798); [arXiv:2305.05176](https://arxiv.org/abs/2305.05176).

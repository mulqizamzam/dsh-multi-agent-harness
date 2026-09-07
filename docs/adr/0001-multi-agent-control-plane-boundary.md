# ADR 0001 — Multi-Agent Control Plane Boundary (Phase 0/1 Foundation)

- **Status**: accepted (2026-09-07 — see Revision 3 addendum at the end of this file)
- **Date**: 2026-08-29
- **Revision**: 3 (2026-09-07: decisions accepted by Human instruction; D4/D7 composition exception executed — see the Revision 3 addendum before relying on any HUMAN_PENDING label in the body below)
- **Source**: `PRD_Multi_Agent_DeepSeek_Harness_v1.0.md` (v1.0, Draft for implementation) + Phase-0 investigation of DeepSeek Harness running locally.
- **Scope**: `multi-agent-harness/`. Does **not** modify DSH core, `project/`, `obsidian-vault/`, `memorycore/`, or any other existing project.
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally; later releases require re-verification).

---

## Context

We are building a seven-specialist + orchestrator multi-agent system on DeepSeek Harness (`@deepseek-ai/dsh-root`, **version `0.1.1-rc.2`**, checkout at `/home/administrator/deepseek-harness`, `DSH_HOME=/home/administrator/agent-workspace/.dsh`, profile `web`).

The PRD is authority-first: it demands a strict separation of **capability / permission / authority**, a scoped delegation model, gates (risk / evidence / conflict / authority), adversarial review, verification-before-COMPLETE, and auditability, all under **Human as the ultimate authority**. The PRD is intentionally Harness-agnostic (Appendix C warns: *"Do not infer an API, permission mechanism, or workflow syntax from this PRD alone"*).

The Phase-0 investigation mapped the PRD against the **actual** DSH 0.1.1-rc.2 environment. The central finding: the PRD's control plane and DSH's native enforcement **do not overlap 1:1**, and the PRD assumes per-agent capability boundaries that DSH exposes as **per-session** controls and **config-level** tool scopes. A deliberate boundary must be drawn between *DSH-native enforcement*, the *project control plane*, and *Human authority* — before any code/config is written.

This ADR is a **boundary and scope** decision (matches the domain-modeling ADR criteria: hard to reverse, surprising without context, genuine alternatives). It records **recommendations** for the seven Human decisions; it does **not** assume they are approved and does **not** begin Phase 1.

## Evidence confidence vocabulary

Used throughout. The single source of truth for how strongly a claim is held.

| Label | Meaning |
|---|---|
| **VERIFIED** | Confirmed by reading the actual DSH 0.1.1-rc.2 source / docs / live runtime in this environment. |
| **INFERRED** | Derived logically from VERIFIED facts; not directly observed but well-grounded. |
| **ASSUMED** | Adopted as a working premise; not yet independently confirmed and may need later verification. |
| **UNKNOWN** | Not verifiable from the current environment / not yet investigated; deliberately **left open** here, not silently resolved. |
| **BLOCKED** | Cannot be done or verified in the current environment/session (e.g. disabled capability, missing permission). |

Human approval vocabulary for the seven decisions:

| Label | Meaning |
|---|---|
| **HUMAN_APPROVED** | Confirmed by the Human in this session / an explicit instruction. |
| **HUMAN_PENDING** | Recommended here; requires explicit Human sign-off before it becomes binding. |
| **NOT_APPLICABLE** | Not a Human-decision item in this ADR (a constraint, or a statement of fact, not a choice). |

---

## Canonical architecture (unchanged)

```text
Human                         ←  ultimate authority
  │
  ▼
Orchestrator                  ←  coordinator + delegated decision-maker
  │
  ▼
7 peer specialist agents:     ←  peers; no specialist manages another
  Zeko  CTO  CFO  Kai  Somad  BadSector  Nova
```

- **Human** is the ultimate authority: approves, delegates, revokes, and may override.
- **Orchestrator** coordinates and owns the project control plane; it does **not** own every domain and has no permanent authority.
- **Seven specialists are peers.** BadSector reviews/challenges; it never authorizes and never executes the reviewed plan.
- This architecture is **unchanged** from the PRD. Nothing in this ADR modifies it.

---

## Three enforcement layers

The architecture is enforced at **three distinct layers**. Their separation is the central point of this ADR.

### Layer 1 — DSH-native enforcement (the harness runs this; we do not reimplement)

| Concern | DSH primitive | Confidence |
|---|---|---|
| **Session sandbox** | `sandbox-policy` (`ctx.sandboxPolicy`, `sandbox/mode` = `read-only` / `workspace-write` / `danger-full-access`), local backends. Mode is **per-session** (last `sandbox/mode` event outranks the executor default). File-sandbox default is fail-safe `read-only`. | **VERIFIED** |
| **Session approval** | `approval` (`ctx.approval`, `approval/policy` = `ask` / `never`), closed outcomes `allowed-once / rejected / cancelled / unavailable`, fail-closed. **Per-session** binary policy; no per-tool or per-agent granular approval. `never` deterministically returns `rejected`. | **VERIFIED** |
| **Tool availability / toolFilter** | Tool registry + `toolFilter` (`allow`/`deny` global tool names) + `disabled` rows in an Agent Preset. `toolFilter` is **config-level** on a `tool-subagent` instance, **not** a per-call model parameter. Filtered tools vanish from prompt and reject execution. | **VERIFIED** |
| **Per-role composition** | **Agent Presets**: one `agent.cordis.yml` per preset (persona, agent-instructions, tool set, prompt sections). `agent-presets.default: standard`. A child subagent joins its parent's standing preset via `composeFrom()`. | **VERIFIED** |
| **Subagent execution** | `subagent` (spawn, continuable, background) / `subagent_fork` (fork, one-shot). In-process providers support `outputSchema`, `depthLimit`, `toolFilter`, `persona`. | **VERIFIED** |
| **Workflow execution** | `workflow` tool: model-authored JS orchestration (`parallel` / `pipeline` / `phase` / `agent()`). Worker-thread isolated, **not a security boundary**. Script has **no** filesystem/network/timers/Node APIs. | **VERIFIED** |
| **Native persistence/audit primitives** | Session JSONL persistence (`sessions/`), session projection, log-only audit events (`approval/asked`+`decided`, `goal/change`, `tool/call`, `todo/write`, `agent-preset/selected`, subagent/workflow events), `spill-store`. Durable per-*session* event log; audit events are log-only and model-invisible. | **VERIFIED** |
| **Goals** | `create_goal` / `get_goal` / `update_goal`, goal-round driver. **Session-scoped**; re-armed after resume/fork. | **VERIFIED** |
| **Cancellation / timeout** | `signal`/AbortController, `job_kill`, `interrupt_agent`, `tool-call-timeout-policy`, per-tool `timeoutMs` (bash 60000). Failure surfaces `stopReason` (`completed/aborted/error/max-tokens/refusal`) + separate `diagnostic`. Partial output is not success. | **VERIFIED** |

### Layer 2 — Project control plane (built in `multi-agent-harness/`; the orchestrator serves it)

| Concern | Who/where |
|---|---|
| **Role definitions** | `multi-agent-harness/` role files (logical) mapped to DSH Agent Presets. |
| **Routing** | Orchestrator task → minimum specialist set; no blanket fan-out. |
| **Delegation registry** | Project-level scoped delegation objects stored in project state. |
| **Authority gate** | Orchestrator/control plane before any consequential action. |
| **Risk policy** | Project-level classification + risk dimensions; no silent LOW downgrade. |
| **Evidence gate** | Project-level sufficiency/source-quality/claims review. |
| **Conflict gate** | Detect → cause → evidence → materiality → rework → escalate; no voting. |
| **BadSector review** | Project-level conditional review; verdict PASS/REWORK/REJECT; reviewer never authorizes. |
| **Project state** | `multi-agent-harness/state/` authoritative project state. |
| **Workflow state transitions** | PRD INTAKE→…→VERIFY machine, interpreted by the control plane. |
| **Project-level audit schema** | `multi-agent-harness/audit/` ledger (actor/action/target/authority_source/evidence/prev/new/result). |

### Layer 3 — Human authority (unchanged, highest)

| Authority | Meaning |
|---|---|
| **Ultimate authority** | Human is the final decision authority; no agent auto-overrides. |
| **Approval** | Human grants/denies approval for consequential actions. |
| **Delegation** | Human explicitly delegates scoped authority to the orchestrator. |
| **Revocation** | Human can revoke delegated authority at any time. |
| **Override** | Human can override an agent/orchestrator decision. |

---

## Boundary corrections (revised understanding)

These corrections are the substance of this revision. Each corrects a previously ambiguous or mis-stated claim:

1. **DSH sandbox/approval are session-level.** They are per-session, not per-agent. Do **not** claim per-agent sandbox/approval.
2. **`toolFilter` and Agent Presets are capability/role boundaries, not complete security isolation.** They scope *which tools* a role can call, but do **not** make a role a hard security sandbox. Sandbox mode and approval policy still apply at the session level; a role with `read`-only tools is still constrained by the *session's* sandbox/approval, not vice-versa.
3. **Project YAML/JSON policies are control-plane inputs, not native DSH authorization.** `config/permissions.yaml`, `agents.yaml`, `authority.yaml`, `risk-policy.yaml` are project-authored *inputs* that the control plane interprets. They are **not** consumed/enforced by DSH as authority. Writing them does not grant anything in the harness.
4. **Workflow scripts are orchestration mechanisms, not security boundaries.** A `workflow` script coordinates subagents and is model-authored, worker-thread executes it, and it has no FS/network access. It must **not** be relied on to enforce security; gates must be enforced by the control plane / Human, with the script limited to deterministic fan-out and collection.
5. **BadSector PASS is never authorization.** It is an advisory review verdict. A PASS does not grant execution authority; it only clears one review gate. Execution still requires the authority gate to pass.
6. **Model judgment alone cannot bypass an authority gate.** The orchestrator's model reasoning is not authority. Any consequential action requires an explicit authority check; a model's confidence or "I think this is fine" does not substitute for it.
7. **UNKNOWN capabilities remain UNKNOWN until verified.** Nothing that is UNKNOWN/BLOCKED is treated as available. See UNKNOWN findings below.
8. **No security claim is made for prompt-injection handling until verified.** Whether DSH treats external content (research/web/doc/repo/subagent output) as non-authoritative data has **not** been verified. Until it is, we make **no** security guarantee on that axis; the control plane must be designed to treat all external/subagent output as data, not instructions.

---

## UNKNOWN findings (deliberately not resolved)

1. **Prompt-injection / external-content-as-untrusted-data guardrail.** The PRD requires it (§12). A DSH-native guardrail was **not verified**. **UNKNOWN** — affects the Phase-1 security design; must be verified before any claim.
2. **DSH `storage` hub** (`ctx.storage`, json/sqlite) exists but is **not mounted** in base/web. Mounting it is a composition change → **BLOCKED** unless explicitly approved + reversible.
3. **Agent Teams** (`spawn_teammate`, `team_task_*`). Experimental, not mounted in base/web. **BLOCKED/UNKNOWN** — not used for V1.
4. **Out-of-process subagent backends** (acp/codex/claude-code/dsh-sdk). Disabled by default. **BLOCKED** unless the prerequisite bundle is installed.
5. **Per-call `persona`/`toolFilter`/`outputSchema`.** These are **config-level**, not per-call model parameters. Whether they can ever be model-controlled is **UNKNOWN**; assumed **no** (config-only).
6. **`web_fetch`** disabled in the standard preset (`fetch: false`) while `web_search` is active. Whether web-fetch is needed for Kai research is **UNKNOWN**.
7. **`config/permissions.yaml` per-agent `sandbox`/`approval` semantics.** These are intent in the file, non-enforceable per-agent. Their project-level accept is **INFERRED**, pending Human confirmation.

---

## Seven decisions (RECOMMENDATIONS, not approvals)

Each is a **recommendation**. None is binding until the Human marks it HUMAN_APPROVED.

### Decision 1 — Per-agent permission model vs DSH session-level sandbox/approval

- **Recommendation**: Adopt a **two-tier** model. Tier 1 (per-role capability boundary): Agent Presets + per-`tool-subagent` instance `toolFilter`/`persona`. Tier 2 (global session enforcement): sandbox mode + approval policy stay **per-session** and are set from the deployment baseline (`workspace-write` + `ask`), **not** per-agent.
- **Evidence**: sandbox + approval are per-session (VERIFIED); `toolFilter`/`persona` are config-level per tool instance (VERIFIED); Agent Presets give per-role persona/tool-set (VERIFIED). PRD §8 per-agent `sandbox`/`approval` is the CONFLICT — treat as intent only.
- **Trade-offs**: ✓ real per-role tool boundaries. ✗ sandbox/approval remain session-global, so a session hosting a low-trust role cannot be independently read-only while a sibling is read-write. ✗ PRD's per-agent sandbox/approval distinction becomes informational.
- **Security impact**: No agent self-widens; toolFilter is config-set and deny-list removes tools from prompt and execution. Because sandbox/approval are shared, default to the *tightest common denominator* (workspace-write + ask). Least-privilege for finance/research roles is expressed via toolFilter, not per-agent sandbox.
- **Reversibility**: Moderate. Switching to per-session-per-role isolation is a refactor of how agents run, not a data migration.
- **Implementation consequence**: Roles must be expressed as presets + per-role tool instances; sandbox/approval set once per session.
- **Human approval status**: **HUMAN_PENDING** (deviates from PRD §8; needs explicit accept).

### Decision 2 — Development approval/session safety policy

- **Recommendation**: Run the harness under **`workspace-write` + `ask`** (the DSH default) for all Phase-1 development and testing, **not** `danger-full-access` + `never`. High-impact/destructive actions go through the project authority gate to a Human.
- **Evidence**: Current session's runtime policy is `danger-full-access` + `never` (VERIFIED — runtime context snapshot, a deviation from the DSH-STATUS.md baseline). DSH default is `workspace-write` + `ask`; presets expose `workspace-write`(sandbox+ask) / `danger-full-access`(danger+never) (VERIFIED). `approval/never` returns `rejected`; `ask` delegates to a Human answerer (VERIFIED).
- **Trade-offs**: ✓ fail-closed, aligns with PRD §19.15. ✗ slower; high-impact actions need explicit Human sign-off during dev.
- **Security impact**: Strongest posture. The baseline must be explicitly set/verified and not silently drift to `danger-full-access`. Note this ADR is authored in a session currently at `danger-full-access` + `never` — a session fact, not the intended project baseline.
- **Reversibility**: Trivially reversible per session (permission-preset switch).
- **Implementation consequence**: Must confirm per-session policy before running high-impact tests; headless/CI runs have no Human answerer, so high-impact tests there would be BLOCKED.
- **Human approval status**: **HUMAN_PENDING** (user changed this session to `never`; needs explicit confirmation that the project baseline is `workspace-write` + `ask`).

### Decision 3 — Orchestrator architecture (main session vs dedicated vs workflow vs hybrid)

- **Recommendation**: **Hybrid.** The primary orchestrator is the **root/main session** (the Human-facing session) acting as delegated decision-maker and coordinator. The orchestrator uses **structured `workflow` scripts** to enforce the *deterministic, fan-out/collection* parts (decompose → select → execute in parallel → collect → synthesize → gate checks) because a script is reproducible and can validate structured outputs (`outputSchema`). Authority/risk/evidence/conflict gates stay in the orchestrator's control (Human-facing escalation); the orchestrator does **not** delegate its authority gate to a subagent.
- **Evidence**: `workflow` = JS script, `parallel`/`pipeline`/`phase`/`agent()`/`log`, per-agent `outputSchema`+provider/model override, no FS/network in script (VERIFIED). Subagent children join parent's preset via `composeFrom()` (VERIFIED). Subagents support `outputSchema`; non-completed stop reasons map to error results (VERIFIED). In-process providers (`subagent`, `subagent_fork`) are mounted in this session (VERIFIED).
- **Trade-offs**: ✓ reproducible fan-out + structured validation. ✓ authority gates remain Human-visible. ✗ model-authored scripts are not a security boundary. ✗ scripts cannot persist state directly (no FS). ✗ the "orchestrator owns gates vs script owns fan-out" split needs a crisp contract.
- **Security impact**: Workflow scripts are model-authored; treat gate-check decisions as data the orchestrator re-validates, not enforcement. Authority gates fail closed and escalate to Human; a workflow must stop (not proceed) when a gate is unresolved. Never let a script auto-authorize a high-impact action.
- **Reversibility**: Moderate. The root-session + workflow split is a convention; moving a gate from model to script is incremental.
- **Implementation consequence**: Define and document the orchestrator contract (who owns each gate) and a workflow skeleton for fan-out/collect.
- **Human approval status**: **HUMAN_PENDING** (the hybrid shape and the gate-ownership split need explicit accept).

### Decision 4 — Role isolation mechanism for the seven agents

- **Recommendation**: Model each of the seven specialists (+ orchestrator) as **Agent Presets** (one `agent.cordis.yml` per role) defining persona + role instructions + tool set, and expose each role to the orchestrator via a **per-role `tool-subagent` instance** (distinct `toolName`, with that instance's `toolFilter` and optionally `persona`). The role's tool set is bound at tool-config level.
- **Evidence**: Subagent children join the parent's preset via `composeFrom()` (VERIFIED), so a distinct role needs a distinct tool-subagent instance (its own `toolFilter`/`persona`). `tool-subagent` Config supports `toolFilter`/`persona`/`agentOptions`/`backgroundMode`/`maxDepth` (VERIFIED); numerical `maxDepth` requires `depthLimit` (spawn/fork have it — VERIFIED). Agent Presets are the native per-role composition (VERIFIED). The PRD §18 `agents/<id>/AGENT.md` + `policy.yaml` is a **project-level representation**; mapping it to DSH presets is **INFERRED**, not yet defined.
- **Trade-offs**: ✓ real per-role tool boundaries. ✓ declarative/auditable. ✗ N `tool-subagent` instance config rows to keep in sync. ✗ `persona`/`toolFilter` being config-level (not per-call) means the orchestrator cannot override a role's scope per task without another mechanism/instance.
- **Security impact**: Strong per-role tool boundary. The reviewer role (BadSector) must get **no** mutate/execute tools and no authorization path; executor roles only their domain tools. Per-role sandbox/approval in `config/permissions.yaml` are intent only (Decision 1).
- **Reversibility**: Moderate-to-low once built (declarative but many config rows).
- **Implementation consequence**: Define the role→preset→toolFilter mapping (Phase-1 work); mount per-role instances in the profile or a project profile.
- **Human approval status**: **HUMAN_PENDING** (the per-role preset + instance approach, and the not-yet-defined policy→preset conversion, need explicit accept).

### Decision 5 — Project state and audit persistence architecture

- **Recommendation**: Keep project state and the project-level audit ledger on the **project filesystem** under `multi-agent-harness/` (`state/` + `audit/`) as JSON/YAML the orchestrator reads/writes, as the *authoritative project state*. DSH session persistence stays the source of truth for harness/session-level facts only. Never derive project authority/state from the DSH session log; never push Human-required decisions to silent auto-writes.
- **Evidence**: Session JSONL persistence + log-only audit events exist (VERIFIED) but are *session* state, not *project* state. `storage` hub (`ctx.storage`, json/sqlite, `kv` facet) exists but is **not mounted** in base/web (VERIFIED — absent from base cordis.patch), so as a mounted primitive it is **BLOCKED/UNKNOWN**. Project skeleton already declares `state/`, `audit/`, `docs/`, `tests/` empty dirs (VERIFIED).
- **Trade-offs**: ✓ explicit/diffable/auditable. ✓ no dependency on unmounted DSH primitive. ✗ file writes must be safe (atomic temp-write+rename + version check; we own it). ✗ concurrency — orchestrator is the single writer; subagents return state to it. ✗ not automatically crash-safe without our implementation.
- **Security impact**: State files must not contain secrets; audit entries reference secret-backed config rather than echoing secrets (PRD §12). Project state is authoritative for this project's authority/decisions — written only by the orchestrator (single-writer) and read defensively (external = data).
- **Reversibility**: Moderate. File layout is easy to refactor early; moving to the `storage` hub later is a backend swap.
- **Implementation consequence**: Define state schema + audit event schema (versions) in Phase 1; atomic-write + version-check helpers.
- **Human approval status**: **HUMAN_PENDING** (file-based state + audit schema need accept; whether DSH `storage` hub is ever mounted is separate/BLOCKED).

### Decision 6 — Phase-0 documentation and Harness capability mapping artifacts

- **Recommendation**: Produce the Phase-0 docs under `multi-agent-harness/docs/`: `tool-catalog.md` (scoped capability matrix), `operations.md` (operator/deployment mapping), `architecture.md`, `authority.md`, `runbooks/` (intent now, details in Phase 5). These resolve the dangling refs already in `config/permissions.yaml`.
- **Evidence**: PRD §18 lists `docs/{architecture,authority,operations,runbooks}` (VERIFIED). `config/permissions.yaml` references `docs/tool-catalog.md` + `docs/operations.md` (VERIFIED) — both currently missing (VERIFIED). DSH ships its own generated `tool-catalog.md`, but the project's *scoped* catalog was never created (VERIFIED).
- **Trade-offs**: ✓ provides the capability matrix Phase-0 demands; unblocks config refs. ~~ document-maintenance burden. ✗ must be version-pinned to `0.1.1-rc.2`.
- **Security impact**: Low directly, but these docs must record the capability boundary explicitly so a reader does not assume DSH enforces something it does not (e.g. per-agent sandbox/approval). They are the anti-fantasy guardrail PRD Appendix C asks for.
- **Reversibility**: Fully reversible (docs).
- **Implementation consequence**: Version-pinned docs; produced as the first Phase-1 deliverable.
- **Human approval status**: **HUMAN_PENDING** (scope + location accept; version-pin acknowledgment).

### Decision 7 — Phase-1 authority/scope boundary

- **Recommendation**: Bound Phase-1 scope strictly to **`multi-agent-harness/`**. May create/modify: files under `multi-agent-harness/`. May touch a project profile/preset under `$DSH_HOME` **only** as a separately-approved, reversible exception (never DSH core). Must **not** modify DSH core (`/home/administrator/deepseek-harness/` source), `project/`, `obsidian-vault/`, `memorycore/`, `.omni/`, or any other existing project/workspace state. Persist state only under `multi-agent-harness/state/`; audit only under `multi-agent-harness/audit/`.
- **Evidence**: User instruction: "Do not modify `project/`, `obsidian-vault/`, `memorycore/`, or other existing projects", "Keep the implementation boundary at `multi-agent-harness/`" (VERIFIED). Workspace root + `multi-agent-harness/` are not git repos (VERIFIED); DSH checkout is a git repo (VERIFIED) but off-limits for modification.
- **Trade-offs**: ✓ protects sibling projects + DSH core. ✓ clear review surface. ✗ may force authoring DSH presets under `$DSH_HOME` if role composition needs it (a controlled exception — must be approved + reversible).
- **Security impact**: Confines blast radius. The controlled DSH profile/preset exception is a privileged composition change (presets carry the trust of shell access — VERIFIED from agent-presets README), so it must be reversible and reviewed.
- **Reversibility**: High (scope declaration; widen only with explicit permission).
- **Implementation consequence**: Constrains every Phase-1 write; no DSH core, no sibling projects, no state outside `multi-agent-harness/`.
- **Human approval status**: Boundary **HUMAN_APPROVED** (explicit instruction). The controlled DSH-profile/preset exception is **HUMAN_PENDING** per case.

---

## Explicit prerequisites / constraints (fixed — apply to Phase 1 and beyond)

1. **Development baseline should be `workspace-write + ask`**, not `danger-full-access + never`.
2. **Phase-1 implementation boundary is `multi-agent-harness/`.**
3. **No modification to DSH core** unless a later ADR explicitly approves it.
4. **NK-Agent-OS integration remains out of scope** unless separately approved.
5. **Agent Teams remains out of scope for V1** unless separately approved.
6. **Out-of-process subagent backends remain out of scope** unless separately approved.
7. **Prompt-injection/external-content trust behavior remains an unresolved security item** until verified.

---

## Decision table (formal)

> **Revision 3 note (2026-09-07)**: the per-decision statuses in this table
> are historical as of the original authoring. All seven decisions were
> accepted by Human instruction on 2026-09-07 — see the Revision 3 addendum
> at the end of this file for the acceptance record, authority provenance,
> and the residual documentation gap.

| Decision | Recommended | Evidence | Risk | Reversible? | Human approval |
|---|---|---|---|---|---|
| 1. Per-agent permission vs session sandbox/approval | Two-tier: per-role toolFilter + per-session sandbox/approval | sandbox/approval per-session (V); toolFilter/persona config-level (V); presets per-role (V) | Medium — PRD §8 per-agent sandbox/approval not natively expressible; shared session policy | Moderate | **HUMAN_PENDING** |
| 2. Dev approval/safety policy | `workspace-write` + `ask` baseline | DSH default + presets (V); current session is danger-full-access+never (V) | Low — misconfig to danger-full-access if not enforced; headless has no Human answerer | High (per-session) | **HUMAN_PENDING** |
| 3. Orchestrator architecture | Hybrid: root-session orchestrator + workflow fan-out; gates Human-facing | workflow JS + outputSchema (V); composeFrom (V); no FS in script (V) | Medium — model-authored scripts not a security boundary; gate split needs a contract | Moderate | **HUMAN_PENDING** |
| 4. Role isolation | Per-role Agent Presets + per-role tool-subagent instances | composeFrom (V); toolFilter/persona config-level (V); presets native (V) | Medium — config-level not per-call; many config rows to keep in sync | Moderate-to-low | **HUMAN_PENDING** |
| 5. State & audit persistence | File-based project state + audit under `multi-agent-harness/` | session persistence (V); storage hub unmounted (V/BLOCKED); skeleton dirs exist (V) | Medium — concurrency (single-writer) + must implement atomic-write/version-check | Moderate | **HUMAN_PENDING** |
| 6. Phase-0 docs | Create `tool-catalog.md`/`operations.md`/`architecture.md`/`authority.md`/`runbooks/` | PRD §18 lists them (V); config refs them but they're missing (V) | Low — maintenance + version-pin drift | High (docs) | **HUMAN_PENDING** |
| 7. Phase-1 scope | Strict `multi-agent-harness/`; controlled per-case DSH profile/preset exception | User instruction (V); workspace not a repo (V) | Low for boundary; Medium for the controlled DSH preset exception | High | Boundary **HUMAN_APPROVED**; exception **HUMAN_PENDING** |

Legend: V = VERIFIED; BLOCKED = unavailable in current env.

---

## What is enforced by DSH vs what is enforced by this project

This section names, per control, *where it lives* (which layer) and *what enforces it*.

| Control | Enforced by | Layer | How / notes |
|---|---|---|---|
| Filesystem/process confinement | **DSH** | DSH-native | Per-session `sandbox/mode`. Not per-agent. |
| Approval / denial of a tool action | **DSH** | DSH-native | Per-session `approval/policy` (`ask`/`never`), fail-closed. Not per-agent. |
| Which tools a role can call | **DSH** (scope) + **project** (role definition) | DSH-native + project | DSH `toolFilter`/preset `disabled` rows enforce the *availability*; the project decides, per role, what that set should be. |
| Role identity, persona, role instructions | **project** (authored) → **DSH** (composed) | Project → DSH | Project authors role files; DSH Agent Presets mount them. |
| Agent routing / selection | **project** (orchestrator) | Project control plane | Orchestrator decides the min specialist set. |
| Delegation (scoped authority) | **project** (control plane) | Project control plane | Project delegation registry, interpreted by the orchestrator. Not a DSH object. |
| Authority gate (is this action authorized?) | **project** (orchestrator/Human) | Project control plane | Enforced before consequential actions; a model's judgment alone cannot bypass it. |
| Risk policy / classification | **project** (control plane) | Project control plane | Project risk config; no silent LOW downgrade. |
| Evidence gate | **project** (control plane) | Project control plane | Orchestrator checks sufficiency/source/claims. |
| Conflict gate | **project** (control plane) | Project control plane | Orchestrator resolves by evidence/rework/escalate; no voting. |
| BadSector adversarial review | **project** (control plane) | Project control plane | Conditional; verdict PASS/REWORK/REJECT. PASS is **never** authorization. |
| Project state (authoritative) | **project** (`state/`) | Project control plane | Written by orchestrator (single-writer). Not in the DSH session log. |
| Workflow state transitions | **project** (control plane) | Project control plane | PRD machine interpreted by the control plane. |
| Project-level audit ledger | **project** (`audit/`) | Project control plane | Actor/action/target/authority_source/evidence/prev/new/result. |
| Harness session event log / audit events | **DSH** | DSH-native | Log-only, model-invisible, per-session. |
| Subagent execution & result delivery | **DSH** | DSH-native | spawn/fork; `outputSchema`; non-completed → error. |
| Workflow coordination (fan-out/collect) | **DSH** (`workflow`) | DSH-native | Script coordinates; **not** a security boundary. |
| Goal tracking | **DSH** | DSH-native | Session-scoped; not cross-session memory. |
| Cancellation / timeout / interruption | **DSH** | DSH-native | signal/AbortController, job_kill, interrupt_agent, timeouts. |

**Key takeaway.** DSH enforces *confinement, approval, tool availability, execution, coordination, and per-session audit* — all **per-session** or **config-level**. The project enforces *authority semantics, gates, routing, project state, and the project audit ledger* — the PRD's value-add. Authority is **never** granted by writing a project YAML/JSON, by a workflow script, or by model judgment; it is granted only by Human delegation and recognized by the control plane's authority gate.

---

## Phase-1 Entry Criteria

> **Revision 3 note (2026-09-07)**: criteria 1–3 are SATISFIED and criterion 4
> is PARTIAL as of 2026-09-07 — see the Revision 3 addendum. Phase 1 has in
> fact been executed through Phase 5 under Human supervision; the table below
> is retained as authored (historical).

Phase 1 may begin **only when all** of the following hold (each currently `HUMAN_PENDING` unless noted):

| # | Criterion | Current status |
|---|---|---|
| 1 | **ADR is accepted by Human** (status → `accepted`; decisions marked HUMAN_APPROVED or explicitly deferred) | **HUMAN_PENDING** |
| 2 | **Development session policy is safe** — running under `workspace-write` + `ask`, not `danger-full-access` + `never` | **HUMAN_PENDING** (current session is danger-full-access + never) |
| 3 | **Scope is confirmed** — `multi-agent-harness/` boundary accepted; NK-Agent-OS / Agent Teams / out-of-process backends explicitly out of scope; controlled DSH profile/preset exception approved (or declined) per case | **HUMAN_PENDING** (boundary already instructed; exceptions pending) |
| 4 | **Unresolved blockers are explicitly documented** — all UNKNOWN/BLOCKED items in this ADR are written down and either verified, deferred, or accepted as out-of-scope | **PARTIAL** — documented here, but UNKNOWN #1 (prompt-injection) is not verified; UNKNOWN #2 (storage) and #3/#4 (Agent Teams / out-of-process) are BLOCKED/out-of-scope |
| 5 | **Implementation plan exists** — `multi-agent-harness/docs/phase-1/0001-phase-1-implementation-spec.md` (produced alongside this ADR) | **SATISFIED** |

**Phase 1 must not start until criteria 1–4 are satisfied.** Criterion 5 is already satisfied by the spec document.

---

## Phase-1 Deliverables

The planned deliverables (produced during Phase 1, **not** yet). None of these are created now; no production agent prompts and no production workflows are authored.

- **Phase-0 documentation artifacts** — `tool-catalog.md`, `operations.md`, `architecture.md`, `authority.md`, `runbooks/` (version-pinned to `0.1.1-rc.2`).
- **Authority/delegation schema** — delegation object schema (scoped, project-bound, time-bound, auditable); capability/permission/authority separation.
- **Audit schema** — project-level audit event schema (actor/action/target/authority_source/evidence/prev/new/result).
- **Role definitions** — the seven specialist roles + orchestrator, as project role files.
- **Role-to-preset/toolFilter mapping** — the conversion from project role files to DSH Agent Presets + per-role `tool-subagent` instances.
- **Orchestrator contract** — which agent owns which gate; the delegation protocol; authority-gate semantics.
- **Workflow skeleton** — fan-out/collect skeleton (deterministic part), with gates as placeholders.
- **Project state structure** — `multi-agent-harness/state/` layout and schema; atomic-write + version-check.
- **Validation tests** — config/invariant validation (incl. the referenced `tests/validate-config.py`) + state/audit schema checks + scenario harness skeleton.

> **Deliberately excluded from Phase 1:** production agent prompts (per role), production workflows, any execution engine. These belong to later phases.

---

## Proposed Phase-1 implementation sequence (plan, not execution)

1. Write the **Phase-0 docs** (Decision 6) — `tool-catalog.md`, `operations.md`, `architecture.md`, `authority.md`, `runbooks/`, pinned to `0.1.1-rc.2`.
2. Define **authority/delegation schema** + **audit schema** + **project-state schema** (versioned).
3. Define the **role → preset → toolFilter** conversion (Decision 4).
4. Scaffold **per-role Agent Presets + per-role tool instances** (Decision 1) — declarative, no execution.
5. Implement the **orchestrator contract** (Decision 3) — delegation protocol + workflow skeleton (fan-out/collect) with gates as placeholders.
6. Set up **file-based state + audit** (Decision 5) — atomic-write helpers + version check, single-writer by orchestrator.
7. Add **validation tests** — config/intervants + state/audit schema checks.
8. Define the **scenario harness** — PRD §17 Phase-6 scenarios as test skeletons.
9. **Stop** before authoring production agent prompts/workflows — that is a later phase.

---

## Consequences

This ADR separates the PRD's control plane from DSH's enforcement, fixes the per-agent sandbox/approval expectation as *not natively expressible*, and makes the recommendation nature of all seven decisions explicit so nothing is treated as authority until the Human approves it. Any future decision that assumes per-agent sandbox/approval, that a workflow script is a security boundary, that a project YAML is native DSH authorization, that BadSector PASS is authorization, or that prompt-injection handling is solved, contradicts this ADR and must be reopened first.

---

*Status: [SUPERSEDED 2026-09-07 by the Revision 3 addendum — see below. Historical 2026-08-29 status:] proposed. Human approval statuses are all HUMAN_PENDING unless marked HUMAN_APPROVED (Decision 7 boundary, given by explicit instruction) or NOT_APPLICABLE. No Phase-1 implementation has begun; no production agent prompts or workflows are authored.*

---

## Revision 3 addendum (2026-09-07) — decisions accepted; D4/D7 exception executed

### What happened

Phase 1 through Phase 5 of the control plane were implemented in this
repository under continued Human supervision (commit history from
2026-08-30 onward). The original body above was written before any of that
work existed; its HUMAN_PENDING labels and "no implementation has begun"
footer are historical.

### Acceptance record (authority provenance)

- **Authority source**: direct Human instructions in the working session
  that owns this project (the Human is the principal, per the ADR's own
  approval vocabulary).
- **Instruction 1** (2026-09-07, exact words): *"mount D4/D7 bridge approved"*
  — Human authority for the **controlled DSH composition exception**
  (Decision 4 implementation + Decision 7's per-case exception). Executed the
  same day: the seven per-role tool-subagent rows and role presets were
  mounted in the live web profile composition
  (`$DSH_HOME/profiles/web/cordis.patch.yml`), verified read-only, and
  recorded in `runs/mount-verification-2026-09-07/` (INT-01..INT-12,
  REAL-backend live dispatches included).
- **Instruction 2** (2026-09-07, exact words): *"setuju"* — Human approval of
  the commit of that verification evidence.
- **Instruction 3** (2026-09-07, exact words): *"laksanakan 1 - 4"* — Human
  approval to execute the four-item follow-up plan that had been presented,
  which included the zeko write/edit discriminator, the reconciliation of
  stale HUMAN_PENDING/draft statuses, and this ADR's status transition.
- **Effect**: Decisions 1–7 are **accepted**; ADR status → **accepted**
  (Revision 3). Decision 7's boundary was already HUMAN_APPROVED
  (2026-08-29 instruction); its per-case exception was granted and executed
  2026-09-07.

### Residual gap (documented, not silently closed)

The approvals above were given as chat instructions in the owning session.
The ADR's original entry criteria anticipate a **dated, per-decision
approval record**; a chat transcript is a weaker, non-repo-verifiable form
of that record. This addendum is the in-repo best transcription: it quotes
the instructions verbatim with dates, but the verifiable approval channel
for D1–D7 remains an open documentation item. If a stronger record exists
outside the repo, it supersedes this transcription.

> **Resolved 2026-09-07 (same day)**: the Human ratified the decisions
> per-decision ("Daftar D1–D7 …" + *"setuju"*; *"(a) setuju"*). The
> authoritative in-repo approval record now lives at
> `docs/governance/0001-decision-approval-record.md` — per-decision table,
> verbatim dated instructions, scope-of-ratification, and the explicit note
> that G13/prompt-injection stays OPEN/UNKNOWN. This addendum remains the
> narrative transcription; that file is the record.

### Entry criteria — current status (2026-09-07)

| # | Criterion | Status |
|---|---|---|
| 1 | ADR accepted by Human | **SATISFIED** (2026-09-07 instructions 1–3; ratified per-decision — record: `docs/governance/0001-decision-approval-record.md`) |
| 2 | Development session policy is safe | **SATISFIED** (sessions run under `workspace-write` + `ask` per the project baseline; approval policy `ask` confirmed in current runtime context) |
| 3 | Scope confirmed, exceptions resolved | **SATISFIED** (boundary `multi-agent-harness/` — instruction of 2026-08-29; D4/D7 composition exception approved 2026-09-07 and executed; NK-Agent-OS / Agent Teams / out-of-process backends remain out of scope) |
| 4 | Unresolved blockers documented | **PARTIAL** — UNKNOWN #1 (prompt-injection trust boundary) remains OPEN *[evidence update 2026-09-07: a Human-authorized live run ("b izinkan", `docs/phase-5/security/g13/live/0002-g13-live-63-scenario-run.md`) observed REAL DSH children treat all 63 canonical injection payloads as data with zero implied actions and zero secret disclosures; formal closure is still a gate decision, not claimed]*; storage hub and Agent Teams remain BLOCKED/out-of-scope by choice |
| 5 | Implementation plan exists | **SATISFIED** (`docs/phase-1/0001-phase-1-implementation-spec.md`) |

### Related corrections (same date)

- `docs/phase-5/security/g10/final/0001-g10-final-mitigation-analysis.md`
  and `docs/phase-5/final/0005-final-security-gate-evidence.md` cited the
  D4/D7 exception as HUMAN_PENDING; both carry dated correction notes.
- `config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml`,
  the seven `agents/<id>/agent.cordis.yml` presets, and `AGENTS.md` were
  updated from draft/not-mounted wording to mounted status.

# Architecture — Multi-Agent Control Plane

- **Status**: final (Phase 1A)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally)
- **Companion**: `docs/adr/0001-multi-agent-control-plane-boundary.md` (revision 2) · `docs/security/0001-control-assurance-spec.md` · `docs/security/0002-threat-model-and-control-architecture.md` · `docs/design/0001-control-design-and-test-plan.md` · `docs/tool-catalog.md` · `docs/authority.md`
- **Scope**: `multi-agent-harness/`. Documentation only.

---

## 1. Canonical architecture

```
Human                         ←  ultimate authority
  │
  ▼
Orchestrator                  ←  coordinator + delegated decision-maker
  │
  ▼
7 peer specialist agents:     ←  peers; no specialist manages another
  Zeko  CTO  CFO  Kai  Somad  BadSector  Nova
```

- **Human** approves, delegates, revokes, and may override. No agent auto-overrides the Human.
- **Orchestrator** coordinates and owns the project control plane; it does **not** own every domain and has no permanent authority.
- **Seven specialists are peers.** BadSector reviews/challenges; it never authorizes and never executes the reviewed plan.

## 2. Three enforcement layers

| Layer | Owns | Primitives / mechanisms |
|---|---|---|
| **1. DSH-native enforcement** | DSH engine | Session `sandbox/mode`; session `approval/policy` (`ask`/`never`); tool registry + `toolFilter` + preset `disabled` rows; Agent Presets (`agent.cordis.yml`, `composeFrom()`); `subagent`/`subagent_fork`; `workflow`; session JSONL persistence + log-only audit events; goals; cancellation/timeouts |
| **2. Project control plane** | `multi-agent-harness/` | Role definitions, routing, delegation registry, authority/risk/evidence/conflict gates, BadSector review, project state (`state/`), audit ledger (`audit/`), workflow state transitions |
| **3. Human authority** | Human | Approval, delegation, revocation, override |

**Key separation (ADR 0001, rev 2):**
- DSH sandbox/approval are **per-session**, not per-agent.
- `toolFilter`/Agent Presets are **capability/role boundaries**, not complete security isolation.
- Project YAML/JSON policies are **control-plane inputs**, not native DSH authorization.
- Workflow scripts are **orchestration mechanisms**, not security boundaries.
- BadSector PASS is **never authorization**.
- Model judgment alone can **never bypass an authority gate**.

## 3. Enforcement mapping (what enforces what)

| Control | Enforced by | Layer |
|---|---|---|
| Filesystem/process confinement | DSH (per-session sandbox) | 1 |
| Approval/denial of a tool action | DSH (per-session approval, fail-closed) | 1 |
| Which tools a role can call | DSH (`toolFilter`/preset `disabled`) + project (role definition) | 1 + 2 |
| Role identity, persona, role instructions | Project (authored) → DSH (preset composition) | 2 → 1 |
| Routing / agent selection | Project (orchestrator) | 2 |
| Delegation (scoped authority) | Project (delegation registry) | 2 |
| Authority gate | Project (code-enforced, fail-closed, escalates to Human) | 2 |
| Risk / evidence / conflict gates | Project (control plane) | 2 |
| BadSector review | Project (conditional review; PASS ≠ authorization) | 2 |
| Project state (authoritative) | Project (`state/`, single-writer) | 2 |
| Workflow state transitions | Project (PRD machine, control-plane-interpreted) | 2 |
| Project audit ledger | Project (`audit/`, append-only) | 2 |
| Session event log / audit events | DSH (log-only, model-invisible) | 1 |
| Subagent execution & result delivery | DSH (spawn/fork; `outputSchema`; non-completed → error) | 1 |
| Workflow coordination (fan-out/collect) | DSH (`workflow`; **not** a security boundary) | 1 |
| Goal tracking | DSH (session-scoped) | 1 |
| Cancellation / timeout / interruption | DSH (signal, job_kill, interrupt_agent, timeouts) | 1 |

## 4. Control flow (task lifecycle)

```
INTAKE (objective from Human)
  → PLAN (orchestrator: decompose, select minimum specialist set)
  → AUTHORITY GATE (is this action authorized by a delegation? fail-closed)
  → DELEGATE (scoped task → per-role tool-subagent instance)
  → RISK GATE (deterministic classification; HIGH non-downgradable)
  → EVIDENCE GATE (source exists → relevant → supports → current → uncontradicted → sufficient)
  → CONFLICT GATE (detect → evidence → rework → synthesize → escalate when unresolved)
  → BADSECTOR REVIEW (conditional; mandatory for HIGH; PASS ≠ authorization)
  → EXECUTION GATE (re-check authority/scope/expiry/revocation/version immediately before DSH boundary)
  → EXECUTE (DSH sandbox + approval + toolFilter)
  → VERIFY (reported vs verified; COMPLETE requires verification evidence)
  → COMPLETE / BLOCKED / FAILED / ESCALATED / RECOVERING
```

Every transition is an audit event. Any gate denial stops the action (fail-closed).

## 5. Role architecture

- **Orchestrator (hybrid)**: root session acting as coordinator + delegated decision-maker; uses `workflow` scripts for the deterministic fan-out/collect parts; owns the authority/risk/evidence/conflict gates (never delegates its authority gate). B-lite carve-out: read-only / reversible internal actions within delegation; never direct HIGH-risk execution.
- **Seven specialists**: per-role Agent Presets + per-role `tool-subagent` instances. Peers; no specialist manages another; no specialist delegates (subdelegation DENY BY DEFAULT).
- **BadSector**: review-only, read-only tool set, no mutate/execute tools; verdict PASS/REWORK/REJECT; PASS clears review only.

## 6. State and audit

- `state/` — authoritative project state (projects/, tasks/, decisions/, approvals/), single-writer, atomic writes, versioned, CAS.
- `audit/` — project audit ledger: actor/action/target/authority_source/evidence/prev/new/result. Generated from runtime events, not agent prose.
- DSH session persistence is the source of truth for harness/session facts only; never derive project authority/state from it.

## 7. Open items (UNKNOWN / BLOCKED — not silently resolved)

- **Prompt injection / external-content trust** — UNKNOWN; no DSH-native guardrail verified; no security claim until INJ-001..003 pass.
- **DSH `storage` hub** — BLOCKED (not mounted).
- **Agent Teams / out-of-process subagent backends** — BLOCKED/out of scope for V1.
- **Registry protection mechanism** — open design item (path-exclusion vs registry-outside-workspace); decided + tested in Phase 1B.
- Nothing is L3 (no independently verified runtime enforcement exists); several controls are L1-design until Phase-1 code exists.

---

*Version-pinned to DeepSeek Harness `0.1.1-rc.2`. Documentation only; no architecture code, presets, or workflows are authored by this document.*
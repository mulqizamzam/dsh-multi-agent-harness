# Operations — Operator / Deployment Mapping

- **Status**: final (Phase 1A)
- **Date**: 2026-08-29
- **Version pin**: DeepSeek Harness `0.1.1-rc.2` (verified locally)
- **Purpose**: operator-facing mapping of how the project's control-plane intent maps onto the actual DSH runtime — session policy, permission presets, headless/CI behavior, role instantiation, state/audit operations, recovery. Resolves the reference in `config/permissions.yaml`.
- **Scope**: `multi-agent-harness/`. Documentation only; no deployment changes are made by this document.

---

## 1. Session policy (permission presets) — VERIFIED

DSH defines three permission presets (verified from `packages/bundle/base/cordis.patch.yml`):

| Preset | Sandbox mode | Approval policy | Intended use |
|---|---|---|---|
| `read-only` | `read-only` | `ask` | Inspection-only sessions |
| `workspace-write` | `workspace-write` | `ask` | **Project baseline for development** |
| `danger-full-access` | `danger-full-access` | `never` | Unrestricted; **never** the project baseline |

Derivation (verified): `sandbox-policy.mode = DSH_PERMISSION_MODE ?? 'workspace-write'`; `approval.policy = mode === 'danger-full-access' ? 'never' : 'ask'`. The file-sandbox default is fail-safe `read-only`.

### 1.1 Baseline and verification step

- **Baseline for this project: `workspace-write` + `ask`** (ADR Decision 2; security spec §15).
- **Verify before consequential action**: confirm the effective session policy (runtime context snapshot / `sandbox/mode` event) equals `workspace-write` + `ask`. If it is not, do **not** proceed with HIGH-risk work; escalate to the Human and reset the policy.
- A `never` approval policy deterministically returns `rejected` for any approval ask; a headless session with no Human answerer returns `unavailable` — both are **fail-closed** (DENY), never implicit allow (design doc §2; APP-001/003).

### 1.2 Session facts (this environment)

- Workspace root: `/home/administrator/agent-workspace` (`process.cwd()` of the session).
- Profile: `web`; the web surface mounts the shipped `standard` agent preset per session (agent-presets roster, default `standard`). The user preset root `$DSH_HOME/.agent-presets/` additionally supplies the fifteen `role-*` presets and, since ADR 0004, an `orchestrator` preset — all selectable per session. The default is unchanged: a session that names no preset still runs `standard`.
- The OMNI MCP client (`mcp__omni__*`) is added by the web profile patch — an environment fact, excluded from role toolFilters.
- DSH checkout (read-only reference): `/home/administrator/deepseek-harness`.

---

## 2. Role instantiation (planned, HUMAN_PENDING)

Per ADR Decision 4, each role maps to:

1. A **DSH Agent Preset** (`agent.cordis.yml` per role) — persona + role instructions + tool set. **Not yet authored/mounted**: mounting a preset under `$DSH_HOME` or a profile is a **controlled composition exception** (ADR Decision 7 — HUMAN_PENDING per case, reversible).
2. A **per-role `tool-subagent` instance** (`toolName: subagent_<role>` with that role's `toolFilter`, `persona`, `backgroundMode`, `maxDepth`) — the delegation surface the orchestrator calls. **Not yet mounted.**

The mapping is declared in `config/role-preset-mapping.yaml` and validated by `schemas/role-mapping.schema.json`. Mounting is Phase-1B/later work and requires the controlled-exception approval.

---

## 3. Project state and audit operations

- **Authoritative project state**: `multi-agent-harness/state/` (projects/, tasks/, decisions/, approvals/) — file-based JSON/YAML, **single-writer (orchestrator)**, atomic writes (temp-write + rename + fsync), monotonic `version`, compare-and-swap (CAS) concurrency.
- **Audit ledger**: `multi-agent-harness/audit/` — append-only event records generated from runtime/control-plane events (never from agent prose).
- **No secrets in state/audit files** — reference secret-backed config (`$DSH_HOME/.credentials.yaml` / env), never echo secrets (PRD §12).
- Schemas: `schemas/project-state.schema.json`, `schemas/audit-event.schema.json`, `schemas/delegation.schema.json`.
- The state/audit read/write helpers and atomic-write implementation are Phase-1B work (ADR Decision 5 — HUMAN_PENDING).

---

## 4. Headless / CI behavior

- No Human answerer exists in headless/CI → DSH approval resolves `unavailable` (fail-closed). The project authority gate must treat "no answerer" as **DENY + escalate**, never implicit allow (APP-001).
- High-impact tests requiring approval are **BLOCKED** in headless/CI until a Human answerer exists.
- All Phase-1A work is declarative (docs/config/schemas) — it neither requires nor triggers approval.

---

## 5. Recovery and rollback

- **Recovery flow**: `STOP → PRESERVE → DIAGNOSE → ROLLBACK/RECOVER → VERIFY RESTORATION → REPLAN → AUTHORITY RE-CHECK`.
- **Bounds**: `max_attempts: 1` (per diagnosed cause), `max_rework_cycles: 2`, per-tool timeouts (bash 60000 ms — VERIFIED), delegation `maximum_cost` if set.
- **No blind retries**; recovery does not acquire privilege automatically; recovery re-checks authority and detects obsolete state versions.
- Phase-1A artifacts are docs/config/schemas — rollback = remove the scaffolding. Nothing consequential executes.

---

## 6. Runbooks

Runbook details are Phase-5 hardening intent; see `docs/runbooks/` for the placeholder index. Intended runbook topics: sandbox verification, approval resolution, delegation lifecycle, BadSector review trigger, recovery, audit inspection, controlled DSH composition changes (preset mount/rollback).

---

## 7. Tool availability notes (VERIFIED)

- A tool that is `disabled` or absent from a preset's composition is **not in the model-facing schema and rejects execution**.
- `toolFilter` (`allow`/`deny`) is **config-level** on a `tool-subagent` instance, not a per-call model parameter; filtered tools vanish from the prompt and reject execution.
- An empty `allow` list with no `deny` is rejected at load; unknown tool names fail startup (config rejects `allow`/`deny` both undefined — VERIFIED).
- `toolFilter` is a **capability boundary, not complete security isolation**; sandbox/approval remain session-level.

---

*Version-pinned to DeepSeek Harness `0.1.1-rc.2`. No session policy is changed by this document; the development baseline is `workspace-write` + `ask`.*
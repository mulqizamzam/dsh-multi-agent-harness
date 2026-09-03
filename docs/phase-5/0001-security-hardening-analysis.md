# Session A — DSH / Role Security Hardening Analysis

- **Status**: HARDENING ANALYSIS (analysis + negative-test plan; **no DSH/core/profile/preset/session-policy change; no claim of path isolation closed**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/` + `multi-agent-harness/tests/phase5_security/` (write-only per session brief). No production code modified.
- **Companion**: ADR 0001 (Decisions 1, 2, 4/7) · ADR 0002 (registry protection) · `docs/security/0001-control-assurance-spec.md` · `docs/security/0002-threat-model-and-control-architecture.md` · `docs/phase-4/0001-acceptance-matrix.md` · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · `control/execution_gate.py`

---

## 1. Exact threat boundary

### 1.1 What the project layer enforces (VERIFIED by inspection)

| Layer | Enforces | Location |
|---|---|---|
| Project execution gate (L1) | Protected-path DENY for `state/registry/**` and `audit/**`; traversal/symlink/prefix DENY; writer-channel root scoping | `control/execution_gate.py` `authorize_write`, `SANCTIONED_ROOTS`, `PROTECTED_REL_ROOTS` |
| ToolFilter (L2, config) | Per-role tool availability (CFO/Kai/BadSector deny `bash`/`edit`/`write`; Zeko/CTO/Somad/Nova allow) | `config/role-preset-mapping.yaml`, `config/tool-subagent-instances.yaml` |
| Session sandbox | `workspace-write` — per-session, NOT per-agent (ADR 0001 Decision 1) | DSH session policy |

### 1.2 The residual (VERIFIED open — NOT closed)

**A bash-capable role (Zeko, CTO, Somad, Nova) CAN, in principle, reach a protected path (`state/registry/**`, `audit/**`) through a raw DSH `bash`/`write`/`edit` tool call that bypasses the project write channel.**

Root causes (all documented in ADR 0001/0002):
1. **Sandbox is per-session, not per-agent** (ADR 0001 Decision 1, VERIFIED): every child shares the orchestrator session's `workspace-write` sandbox; per-agent sandbox is not natively expressible.
2. **toolFilter is tool-level, not path-level** (ADR 0002, VERIFIED): `bash`/`edit`/`write` can reach any path inside the sandboxed workspace; there is no per-path allow/deny at the DSH layer.
3. **The project execution gate is a code channel, not a DSH interception point** (ADR 0002, VERIFIED): `authorize_write` governs writes that ROUTE THROUGH the project channel (`write_through`, `registry_write`, `audit_append`). A raw DSH `write`/`bash` that bypasses the channel is not intercepted.

### 1.3 What is NOT claimed

- **Path isolation is NOT closed at the DSH layer.** This analysis and the negative tests prove the residual is still open; they do not close it.
- **Per-agent sandbox differentiation is NOT available.** It would require a DSH capability or session-policy change — out of scope (prohibited).
- **No prompt-injection claim.** External content remains UNKNOWN.

### 1.4 Threat model

| Threat | Actor | Path | Current mitigation | Residual |
|---|---|---|---|---|
| Registry forgery (THREAT-004) | bash-capable role (Zeko/CTO/Somad/Nova) | raw `bash` → `state/registry/*` | L1 gate only for channeled writes; audit detection | DSH-layer bypass possible in principle |
| Audit tampering (THREAT-018) | bash-capable role | raw `bash`/`edit` → `audit/*` | append-only + hash-chain detection (post-hoc) | DSH-layer bypass possible in principle |
| State forgery (THREAT-007) | bash-capable role | raw `write` → `state/projects/*` | CAS version check (post-hoc detection) | DSH-layer bypass possible in principle |

**Why it is contained (not closed):** even if a raw DSH write lands on a protected path, the L1 gate + CAS + append-only hash chain + audit detection make the tamper DETECTABLE (REG-003, AUD-*, Runbook 10). The residual is: *prevention* at the DSH layer is absent; *detection* at the project layer is present.

---

## 2. Mitigation options

| Option | What it does | Effort | Reversibility | DSH change? | Phase |
|---|---|---|---|---|---|
| **O1 — Keep L1 gate + detection** (current) | Code-enforced path gate on channeled writes; append-only + hash-chain detection; audit alerting | none | n/a | no | V1 (current) |
| **O2 — Registry-outside-workspace** | Move registry to a path outside the sandboxed workspace so no session tool can write it | medium | moderate (path relocation) | no (config) | V2 candidate — rejected for V1 (ADR 0002 Option A analysis) |
| **O3 — Dedicated out-of-process registry process** | Separate process with its own workspace root; only the process writes the registry | high | low | no (new process) | V2/Phase-5+ hardening candidate (ADR 0002 consequence 4) |
| **O4 — Per-agent sandbox** (if DSH ever supports it) | Per-agent sandbox differentiation | unknown | high | **yes** (DSH capability) | blocked on DSH capability — not available |
| **O5 — Reduce bash surface** | Remove `bash` from Zeko/CTO/Somad/Nova allow sets; force all writes through the project channel | low-medium | high (reversible config change) | no (config) | **V2 candidate — requires Human-approved composition change** |

---

## 3. Recommended V1/V2 treatment

### V1 (current Phase-5 posture) — O1, explicitly documented

1. Keep the L1 project execution gate as the authoritative write channel.
2. Keep append-only audit + hash chain + CAS versioning as detection.
3. **Prove the residual open** with negative tests (below) so it is never silently assumed closed.
4. Record the residual in the acceptance matrix (PS-1/PS-2) as **HARDENED (residual proven open)** / **UNKNOWN**.
5. No DSH/core/profile/preset/session-policy change.

### V2 (future, gated on Human approval + composition change)

1. **O5 first** — narrow the bash surface for roles that do not need raw shell (Somad/Nova), forcing writes through the project channel. This is a config change requiring the approved D4/D7 composition exception to be reopened.
2. **O3 if needed** — a dedicated out-of-process registry process for hard path isolation (ADR 0002 consequence 4).
3. **O2 as fallback** — registry outside the workspace, if the process option is too heavy.
4. Each option is reversible, audited, and requires a new composition change request — never a silent change.

---

## 4. Executable negative-test plan

Under `tests/phase5_security/`:

| Test | What it proves | Outcome |
|---|---|---|
| `test_bash_capable_role_can_reach_protected_path` | A bash-capable role's raw filesystem write to `state/registry/**` is NOT intercepted by the DSH layer (only the project channel is gated) | PASS when the raw write lands (residual proven open) — the test documents the boundary, it does not exploit |
| `test_project_channel_write_denied` | The SAME target through the project execution gate (`authorize_write`) IS denied | PASS when DENY (L1 gate works) |
| `test_write_edit_denied_for_readonly_roles` | CFO/Kai/BadSector deny `write`/`edit`/`bash` at the toolFilter level | PASS when deny set excludes them |
| `test_traversal_denied` | `../` escape through the project channel is denied | PASS when DENY (no escape) |
| `test_no_claim_path_isolation_closed` | The analysis document + tests do NOT assert DSH-layer closure | PASS when no claim is made |

**Design note:** the negative tests operate on a THROWAWAY temp workspace (never the real `state/registry/` or `audit/`), so they document the residual without touching real protected state.

---

## 5. Remaining residuals

| Residual | Status | Phase |
|---|---|---|
| Raw DSH `bash`/`write`/`edit` can reach protected paths at the DSH layer | **OPEN** (proven by negative tests) | V2 (O5/O3/O2), gated on Human-approved composition change |
| Per-agent sandbox differentiation not natively expressible | **OPEN** (ADR 0001 Decision 1) | V2, blocked on DSH capability |
| toolFilter is tool-level, not path-level | **OPEN** (ADR 0002) | V2 |
| Prompt-injection / external-content guardrail | **UNKNOWN** (no claim) | until independently verified |

---

## 6. Scope check

**In scope (added):** `docs/phase-5/0001-security-hardening-analysis.md` (this file), `docs/phase-5/0001-acceptance-matrix.md` (Session F), `tests/phase5_security/` (negative-test plan).

**Not modified:** `control/*.py`, `orchestrator/*`, `state/*`, `audit/*`, `agents/*`, `config/*`, DSH core, profiles/presets, session policy. No new tools, no web_fetch, no Agent Teams, no out-of-process backends. No L3 claim. No path-isolation claim.

---

*Status: HARDENING ANALYSIS. The DSH-layer path-isolation residual is proven OPEN and documented; it is NOT closed by this session. No production or DSH change.*
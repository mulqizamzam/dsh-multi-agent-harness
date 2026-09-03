# Phase 5 / Session B — Runtime Environment Readiness Spec (G2 + G3)

- **Milestone**: Phase 5 / Session B — RUNTIME ENVIRONMENT READINESS
- **Status**: SPEC (operational mechanism defined; **no session-policy change, no DSH change, no readiness claimed without runtime evidence**)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/environment/` + `multi-agent-harness/tests/environment/` (write-only).
- **Companion**: `docs/phase-4/0003-approval-readiness.md` · `docs/phase-4/0005-production-readiness-assessment.md` (G2/G3, §4.1-4.2, §4.6, §6.3) · `docs/operations.md` · `docs/security/0007-l3-run-prerequisites.md` (PF-ENV-2 / G9) · `docs/phase-1/0003..0005` (D4/D7 change requests) · `tests/l3_runner/preflight.py`.

---

## 1. Current runtime facts (verified this session)

| Fact | Current value | Implication |
|---|---|---|
| File sandbox policy | `workspace-write` | Project baseline (PB-1) holds |
| Approval policy | `ask` | Baseline holds |
| Approval-answerer | **Approval prompts disabled**; no available answerer | `ask`-dependent operations **fail closed** (DENY + escalate) |
| DSH live bridge marker | `DSH_LIVE_BRIDGE_ACTIVE` **unset** | Live D4/D7 dispatch **unavailable** |
| DSH version pin | `0.1.1-rc.2` | Exact pin; later versions invalidate live/L3 results |
| D4/D7 presets dir | `$DSH_HOME/.agent-presets/` present (mounted in a prior session) | Mount is **not persistent** — must be re-verified per session |

**Bottom line**: the environment is currently **NOT ready** for (a) live DSH dispatch, (b) interactive/HIGH-risk execution, or (c) any L3 claim. Readiness is **conditional** on restoring the answerer path and re-verifying the mount.

---

## 2. G2 — Persistent D4/D7 availability

### 2.1 What "persistent availability" means

The D4/D7 composition (7 role presets + 7 `subagent_<id>` instances + `cordis.patch.yml` rows) was proven live in Phase-3 closure, but it is a **controlled composition exception** (ADR Decision 4/7): it must be Human-approved, mounted reversibly, and **re-verified before every session that needs it**. Availability is NOT automatic.

### 2.2 Per-session mount-verification procedure (the exact mechanism)

Run in this order, before any live-DSH work. Every step is a **detection** step — nothing here mounts or changes DSH:

1. **Preset presence**: check the 7 role presets exist under `$DSH_HOME/.agent-presets/` (`role-zeko`, `role-cto`, `role-cfo`, `role-kai`, `role-somad`, `role-badsector`, `role-nova`).
2. **Instance rows**: check `cordis.patch.yml` contains the 7 `tool-subagent` instance rows (`subagent_<id>`).
3. **Marker**: check `DSH_LIVE_BRIDGE_ACTIVE=1` is set for the orchestrator session.
4. **Resolution**: `RoleResolver` resolves all 7 roles; `tests/live_dsh/discovery.assert_role_resolution()` passes.
5. **Probe**: `probe_backend_kind() == real-dsh` and all 7 mount probes return True (the discovery module's probe).
6. **Live smoke**: a minimal live `subagent_<id>` dispatch settles with a real run id (the strongest signal; only run when steps 1-5 pass).

**Fail-closed rule**: if ANY of steps 1-5 fails, the session treats the bridge as **UNAVAILABLE** — no live dispatch is attempted, no silent fallback to the fake backend, and any flow that requires REAL dispatch **STOPS/BLOCKS** (`BridgeNotAvailable`).

**Stale-mount detection**: a marker set but presets absent (or vice versa) is a **stale mount** → treat as unavailable and escalate (do not half-run).

### 2.3 Making availability durable (recommendation, NOT applied here)

- Automate steps 1-5 in the orchestrator-session bootstrap (a preflight module under `tests/environment/` provides the checks; the recommendation is to invoke it at session start and gate live work on `all_required_pass`).
- Record a per-session availability record (session id, checks, result) into the observability layer / audit channel so operators can prove which sessions had the mount.
- Keep the rollback/unmount procedure from `docs/phase-1/0003 §8 / 0005 §9` documented and rehearsed; unmounting is always available and the marker disappearing forces fail-closed behavior.

---

## 3. G3 — Approval-answerer availability

### 3.1 Current state (degraded, fail-closed is correct)

`approval/policy=ask` is in force, but **approval prompts are disabled** and there is **no live answerer**. Per `docs/operations.md` §4 and `docs/authority.md` §6:
- A headless session with no Human answerer resolves approval as `unavailable` → **DENY + escalate** (never implicit allow).
- This is the **correct safety default**, but it blocks interactive and HIGH-risk execution.

### 3.2 Detection mechanism

`tests/environment/` implements a read-only probe that reports:
- whether an answerer is available (probe the approval surface; report only)
- the effective approval policy (`ask`)
- the fail-closed expectation (no answerer → DENY + escalate)

### 3.3 Restoration mechanism (the exact operational path to readiness)

For an approval-dependent action to ALLOW, **one** of these must hold (both are Human/operator actions, never agent actions):

1. **Enable the approval prompts + configure a live Human answerer** for the `ask` policy. This is an operator/environment action — out of scope for the harness to perform.
2. **Pre-record a structured `approval-<id>` reference** in the delegation registry for the specific action (destructive, financial_transfer, sensitive_publication, credential_change). The reference must:
   - be recorded in the sanctioned registry channel (single-writer, ADR 0002),
   - match the delegation record at execution-time re-check (`control/authority.py::_check_approval`),
   - be generated ONLY by the Human (or a documented Human-authorized process) — never by an agent, workflow output, audit entry, or model text.

### 3.4 HIGH-risk approval path

HIGH-risk execution (intrinsic HIGH: production change, destructive, credential change, financial commitment, material publication) is **not model-downgradable** (AUTH-INV-10) and requires ALL of:
- evidence-ladder sufficiency (`control/evidence.py`),
- BadSector review when mandatory (`control/badsector.py`),
- a valid Human approval record (`approval-<id>`),
- **independent verification for `independent` categories (VER-2)** — which is **NOT built** (L3-1). Until VER-2 exists, HIGH-risk `independent` execution stays **BLOCKED**.

### 3.5 Interactive Human approval flow

1. A consequential/HIGH action hits the `ask` backstop or the project approval gate.
2. If an answerer is live: surface to the Human → approval → `approval-<id>` recorded → execution proceeds.
3. If no answerer: resolve `unavailable` → **DENY + escalate** as an escalation record. Do NOT pause-and-poll in a tight loop; non-HIGH denials are records the Human reviews on their schedule (`docs/runbooks/01-authority-denial.md`).

---

## 4. Session preflight (read-only, REPORT ONLY)

Before any consequential session, the operator runs the environment preflight (implemented in `tests/environment/test_environment_preflight.py`, modeled on `tests/l3_runner/preflight.py`):

| Check | What it verifies | Required value | Current (this session) |
|---|---|---|---|
| `ENV-POLICY-1` | sandbox mode | `workspace-write` | **PASS** |
| `ENV-POLICY-2` | approval policy | `ask` | **PASS** |
| `ENV-APPROVAL-1` | answerer available | available for interactive ops | **FAIL** (prompts disabled) — reported, never faked |
| `ENV-MOUNT-1` | `DSH_LIVE_BRIDGE_ACTIVE` set | set | **FAIL** (unset) — reported |
| `ENV-MOUNT-2` | role presets present | 7 presets | depends on `$DSH_HOME` state — reported |
| `ENV-DSH-1` | DSH version pinned | `0.1.1-rc.2` | **PASS** |

**Rules**:
- The preflight **never modifies** session policy or DSH.
- A failed check is **reported** with its required value; it does not crash the suite (REPORT ONLY, like `PF-ENV-2`).
- Readiness is claimed only when the relevant checks pass AND runtime evidence exists.

---

## 5. Honesty / readiness verdict

| Requirement | Readiness | Why |
|---|---|---|
| Interactive Human approval | **BLOCKED** | approval prompts disabled; no live answerer |
| Approval-dependent tasks | **BLOCKED** | same root cause; no pre-recorded `approval-<id>` for any action in this session |
| HIGH-risk execution | **BLOCKED** | sign-off path + independent verifier (VER-2) absent |
| Persistent D4/D7 availability | **CONDITIONAL** | proven in a prior session; must be re-verified per session; marker currently unset |
| Session preflight | **READY (mechanism)** | harness implemented and passing; it reports, it does not fix |
| Fail-closed default when unavailable | **READY** | correct DENY + escalate behavior in place |

**G2 / G3 are OPEN**: the *mechanism* is now defined and testable, but availability is not restored and no readiness is claimed without runtime evidence.

---

*Status: SPEC. No session-policy change, no DSH change, no implementation. No readiness claimed for anything without runtime evidence.*

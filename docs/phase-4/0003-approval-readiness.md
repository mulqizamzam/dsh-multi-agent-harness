# Session B — Approval / Human-Answerer Readiness

- **Status**: ASSESSED (prerequisite analysis only; no implementation, no session-policy change, no DSH change)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `docs/phase-4/` (this document). Read-only inspection of the actual current execution/approval prerequisites.
- **Rule**: do not change session policy; do not modify DSH.

---

## 1. Current runtime facts (verified from the session runtime context)

| Fact | Current value |
|---|---|
| File sandbox policy | `workspace-write` |
| Approval policy | `ask` |
| Approval-answerer availability | **Answerers configured but approval prompts are disabled** (operations requiring approval fail closed without an available answerer) |
| DSH version pin | `0.1.1-rc.2` |

The session runs the project baseline (`workspace-write` + `ask`, ADR 0001 Decision 2). However, the **effective approval-answerer readiness is degraded**: `ask`-policy operations that would surface to a Human answerer currently fail closed because approval prompts are disabled.

---

## 2. How approval works in this system

### 2.1 Project-level approval gate (code-enforced)

`control/authority.py::_check_approval` — a delegation carrying `requires_approval` categories (destructive, financial_transfer, sensitive_publication, credential_change) needs a **matching structured Human approval reference** (`approval-<id>`) to ALLOW:

- no reference supplied → `NeedsApproval` (ESCALATE)
- free-text "Human approved" claim → `Denied` (AUTH-INV-01: text is never approval)
- reference mismatches the delegation record → `Denied` (wrong record)

Every denial is fail-closed (`Denied` / `NeedsApproval` → no partial allow).

### 2.2 DSH-layer approval backstop

Per `docs/authority.md` §6 and `docs/runbooks/01-authority-denial.md`:

- DSH `approval/policy = "ask"` is the runtime backstop for consequential/HIGH-risk actions; it surfaces to a Human answerer.
- **Headless rule**: with no Human answerer, approval resolves `unavailable` → **DENY + escalate** (never implicit allow).
- Do **not** pause-and-poll the Human in a tight loop; non-HIGH denials are escalation records the Human reviews on their schedule.

### 2.3 What is required for each approval class

| Approval class | Required for ALLOW | Current readiness |
|---|---|---|
| **Interactive Human approval** | A live Human answerer available to the `ask` backstop for the consequential action; or a structured `approval-<id>` reference in the delegation record. | **NOT READY** — approval prompts disabled; `ask` fails closed without a live answerer. |
| **Approval-dependent tasks** | The task's action ∈ delegation `requires_approval`; a matching structured `approval-<id>` reference at execution-time re-check (`control/authority.py::_check_approval`). | **NOT READY** — no live answerer to generate/confirm the reference; fail-closed behavior is the safe default. |
| **HIGH-risk execution** | Intrinsic HIGH (production change, destructive, credential change, financial commitment, material publication) is **not model-downgradable** (AUTH-INV-10); requires evidence ladder sufficiency + Human sign-off path + `approval-<id>`; independent verification for HIGH categories (VER-2). | **NOT READY** — sign-off path requires a live answerer / signed approval record; independent verifier not built. |
| **L3 Human-signed plan** | A Human-signed `plan.json` committed **before** the runtime run (E3; `human_signoff_ts` strictly before `runtime-verdict.json captured_at`); a real signing mechanism + durable signoff identity (`human_signoff_id`, `human_signoff_method`). | **NOT READY** — no signing mechanism, no durable Human identity, no pre-commit oracle process. |

---

## 3. Precise Phase-4 entry prerequisite

For Phase 4 execution to proceed, **each** of the following must hold:

1. **Approval prompts must be enabled and a Human answerer must be available** for the `ask` policy, OR every approval-dependent action must carry a valid structured `approval-<id>` reference already recorded in the delegation registry. Without one of these, `ask` resolves `unavailable` → fail-closed DENY + escalate (this is the correct safety behavior, but it blocks interactive and HIGH-risk execution).
2. **The project authority gate remains the authority source** — approval references are generated only by the Human (or a documented Human-authorized process); no agent, workflow output, audit entry, or model text may create one.
3. **HIGH-risk execution** additionally requires: evidence-ladder sufficiency, BadSector review when mandatory, the Human approval record, and — for `independent` categories — an independent verifier (VER-2) which is not yet built.
4. **L3 Human-signed plans** additionally require: a defined signing mechanism (how the Human signs `plan.json`), a durable signoff identity, and a pre-commit-oracle process that commits the signed expectation before any runtime attempt.
5. **Session policy must stay `workspace-write` + `ask`**; any drift to `danger-full-access` + `never` is a violation of the project baseline (PB-1) and must be reported, never silently accepted.
6. **No Phase-4/live/L3 scenario starts without an approved, isolated fixture** and a confirmed answerer/signing path for the specific action class.

---

## 4. Readiness verdict

| Requirement | Verdict |
|---|---|
| Interactive Human approval | **BLOCKED** (approval prompts disabled; no live answerer path) |
| Approval-dependent tasks | **BLOCKED** (same root cause) |
| HIGH-risk execution | **BLOCKED** (sign-off path + independent verifier absent) |
| L3 Human-signed plan | **BLOCKED** (no signing mechanism / identity / pre-commit oracle) |
| Fail-closed default when unavailable | **READY** (correct deny+escalate behavior in place) |

**Bottom line**: the deterministic control-plane approval logic is in place and fail-closed, but the **Human-answerer / signing infrastructure is not currently available** in this runtime context. Phase-4 entry requires restoring a live approval-answerer path and a Human signing mechanism before interactive, HIGH-risk, or L3 execution can proceed. Until then, only read-only and deterministic-runtime preparation may continue.

---

*Status: ASSESSED. No session-policy change, no DSH change, no implementation. No Phase 4 or L3 execution started.*
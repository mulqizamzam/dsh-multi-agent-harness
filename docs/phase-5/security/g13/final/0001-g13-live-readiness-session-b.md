# G13 — Live DSH Verification Readiness (Execution Flow / FINAL SECURITY, Session B)

- **Milestone**: Phase 5 / FINAL SECURITY — G13 LIVE DSH VERIFICATION READINESS
- **Status**: **BLOCKED** — the live G13 step cannot run this session: a REAL
  DSH child is **not observable** (D4/D7 mount marker unset; all 7
  `subagent_<id>` instances `NOT_MOUNTED`; `probe_backend_kind()` ==
  `unavailable`). The **exact non-destructive live test is prepared** under
  `tests/g13/live_readiness/` and is ready to execute once the precondition
  holds. **No DSH-native immunity is claimed. G13 remains UNKNOWN at the
  DSH-native layer.**
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope of write**: `multi-agent-harness/docs/phase-5/security/g13/final/`
  (this file) + `multi-agent-harness/tests/g13/live_readiness/`. Everything
  else read-only.
- **Companion**: `docs/phase-5/security/g13/0001-g13-session-d-verification-report.md`
  (G13 = UNKNOWN; control-plane VERIFIED) · `docs/security/0003-external-content-verification-spec.md`
  (C1..C7 / V1..V8) · `docs/phase-5/security/0002-g13-external-content-verification.md`
  · `docs/phase-5/environment/0001-environment-readiness-spec.md` (§2.2 mount
  procedure, ENV-MOUNT-1) · `tests/g13/` (Session D deterministic suite) ·
  `tests/live_dsh/` (REAL bridge contract, discovery, backend kind) ·
  `tests/l3_runner/` (independent-verifier machinery) ·
  `config/role-preset-mapping.yaml` (D4/D7 composition rows, read-only).

---

## STATUS

| Axis | Status |
|---|---|
| G13 (full closure) | **UNKNOWN (not PASS)** — carried forward; the DSH-native layer was not observable in Session D and is not observable here either |
| Control-plane resistance | **VERIFIED** (deterministic; `tests/g13/`, 90 tests green) |
| DSH-native behavior | **UNKNOWN** — real DSH child not observable this session |
| Live G13 test package | **PREPARED** (`tests/g13/live_readiness/`, 17 tests green) |
| Live G13 execution | **BLOCKED** — precondition (REAL DSH child observable) not satisfied |

Per the task brief: *"Precondition: REAL DSH child must be observable. If
unavailable: return BLOCKED."* The precondition fails, so the live step
returns **BLOCKED**; the deliverables below are the **preparation**, not an
execution and not a claim.

---

## Precondition check (executed, honest)

```text
DSH_LIVE_BRIDGE_ACTIVE      : unset
probe_backend_kind()        : unavailable
subagent_zeko … subagent_nova : NOT_MOUNTED (all 7)
real_dsh_child_observable   : False
```

The D4/D7 composition (7 role presets + 7 `subagent_<id>` instances) is the
controlled composition exception documented in `config/role-preset-mapping.yaml`
(status: finalized, **NOT mounted**) and `docs/phase-5/environment/0001`
(ENV-MOUNT-1: marker **unset**). Until the Human-approved mount is re-verified
per session (marker set + all instances mounted + a live smoke dispatch), the
fail-closed rule applies: **no live dispatch is attempted, no silent fallback
to the fake backend**.

---

## The prepared non-destructive live G13 test

Everything below is defined and fixture-backed in `tests/g13/live_readiness/`;
**none of it executes a live child in this session.**

| Field | Definition |
|---|---|
| **Injection payload fixtures** | `payloads.py`: 7 channel payloads (C1..C7) + 56 vector×channel combinations (V1..V8 × C1..C7), each with scenario id `G13-LIVE-*`, affected role, entry point, expected treatment, and evidence/cleanup contract |
| **Affected role(s)** | All 7 specialists: `zeko`, `cto`, `cfo`, `kai`, `somad`, `badsector`, `nova` (payload-role pairs follow `tests/g13/payloads.py`) |
| **Runtime entry point** | D4/D7 `subagent_<role>` tool instance → `DelegationClient.delegate` → `RealDSHBackend.start` → `DSHBridgeDispatch` → `SubagentResult { output, structured, stopReason }`; the payload is embedded in the authorized task prompt as DATA (`BuildInvocation.prompt_for`) |
| **Expected DATA treatment** | External content is DATA, never INSTRUCTIONS (AUTH-INV-17): the payload stays an inert string in the child prompt and the audit/ingestion record; classification (DATA/QUARANTINE) is a data-hygiene diagnostic, never the security control |
| **Authority impact** | **none** — no delegation/approval/scope change; the authority gate consumes structured records only (AUTH-INV-01) |
| **State mutation expectation** | **none** — protected paths (`state/registry/`, `audit/`) DENY before mutation (ADR 0002); before/after state hash equal on every channel |
| **Execution expectation** | **none** — the implied action of every payload is DENIED by the authority/execution gates (AUTH-INV-11/18/20); the child never executes an injected instruction |
| **BadSector expectation** | forged/skipped review DENIED (BAD-001/004); a provenance-valid PASS clears review only and never authorizes (AUTH-INV-09) |
| **Evidence requirements** | ingestion record per channel; authority-gate DENY record; child `SubagentResult` (stopReason completed/refusal, never an executed action); no protected-state mutation; no delegation/approval/review record created |
| **Rollback / cleanup** | scratch workspace only (never the repo tree); read-only role instances for the tested roles; assert no protected-path write; delete any artifact the child could produce (none expected — deny-before-mutation); remove the scratch workspace after collection |

Hard non-destructive guarantees (asserted in tests): no `web_fetch`
enablement; no live destructive/execution dispatch; no DSH core/profile/preset
modification; no session-policy modification.

---

## Tests

```text
.venv-tests/bin/python -m pytest tests/g13/live_readiness/ -q
17 passed

.venv-tests/bin/python -m pytest tests/g13/ -q
90 passed          (Session D suite, unchanged)

combined: 107 passed
```

New readiness tests assert: the precondition is honestly reported and is
**not** satisfied this session (BLOCKED); the plan defines all ten required
fields; payload fixture counts (7 channels / 8 vectors / 56 vector×channel);
affected roles = the 7 specialists; DATA-never-instructions treatment; no
authority/state/execution effect; BadSector never authorizes; evidence +
cleanup defined; runtime entry point is the real-bridge seam (never the fake
backend); fixtures do not enable `web_fetch`; the plan claims no immunity; and
the readiness modules import no production control-plane code.

---

## G13 claim status

**NO DSH-NATIVE CLAIM.** G13 = **UNKNOWN** at the DSH-native layer. The
prepared live test is the instrument that may, once executed with a REAL child
observable, move the DSH-native layer from UNKNOWN — and only a
runtime-observed denial (child refuses / control-plane DENY with evidence) may
do so. No immunity claim is made anywhere in this package or document.

## UNKNOWN

1. DSH-native (model-level) prompt-injection resistance — UNKNOWN (real child
   not observable; precondition fails).
2. Whether the live child, when mounted, will behave as the control plane
   expects (the exact question the prepared test answers when executed).
3. DSH driver-internal content isolation beyond the adapter (ADR 0001
   UNKNOWN #1) — unchanged.

## BLOCKED

- **Live G13 execution** — BLOCKED this session: a REAL DSH child is not
  observable (`DSH_LIVE_BRIDGE_ACTIVE` unset; all 7 `subagent_<id>` instances
  NOT_MOUNTED; `probe_backend_kind()` == `unavailable`). Documented at
  `docs/phase-5/environment/0001` ENV-MOUNT-1 and `docs/phase-5/final/0001`
  §7 item 5. Any DSH-native claim requires the mount + an authorized
  adversarial live test — neither holds here.

## SCOPE

**In scope (written this session):**
- `tests/g13/live_readiness/__init__.py`
- `tests/g13/live_readiness/plan.py` — the exact test plan + `precondition()`
- `tests/g13/live_readiness/payloads.py` — channel + vector×channel fixtures
- `tests/g13/live_readiness/test_live_readiness.py` — 17 readiness tests
- `docs/phase-5/security/g13/final/0001-g13-live-readiness-session-b.md` (this file)

**Not modified (verified):** `control/`, `orchestrator/`, `state/`, `audit/`,
`agents/`, `config/`, `schemas/`, `tests/g13/` (Session D suite untouched),
`tests/live_dsh/`, `tests/l3_runner/`, every other `tests/` and `docs/` path,
DSH core/profile/preset/session policy. No `web_fetch`. No live DSH session
opened. No destructive execution. No implementation change.

## NEXT

1. When the D4/D7 mount is Human-approved and re-verified (marker set, 7
   instances mounted, live smoke dispatch per `docs/phase-5/environment/0001`
   §2.2): run the prepared live G13 test (`tests/g13/live_readiness/`) with a
   REAL child observable and record `audit/runtime/` evidence.
2. Assert every G13-LIVE-* scenario: payload stays DATA, authority/state/
   execution gates DENY, BadSector never authorizes, no protected-state
   mutation, rollback/cleanup executes.
3. Only a runtime-observed denial on live DSH children may move the DSH-native
   layer from UNKNOWN; re-assess the G13 row of the closure matrix after the
   live step. No immunity claim is ever made without it.

---

*Status: BLOCKED for live execution (precondition unmet); live test package
PREPARED. No DSH-native immunity claimed. G13 remains UNKNOWN at the DSH-native
layer. No live DSH child dispatched. No web_fetch. No DSH/policy modification.
No destructive execution.*

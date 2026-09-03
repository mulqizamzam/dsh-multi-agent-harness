# tests/resilience — Phase 5 / Session D resilience suite (G4 + G9)

**TEST-SUPPORT ONLY.** This suite exercises the **existing** runtime and
control-plane modules (`orchestrator/runtime/*`, `control/execution_gate.py`,
`control/recovery.py`, `state/helpers/recovery.py`) with failure-injecting
subtask runners and throwaway workspaces. **No production code, no DSH core,
no profile/preset/session-policy, no config change, and no security control
weakening.** No live-DSH proof is claimed — `DSH_LIVE_BRIDGE_ACTIVE` is not set
in this session.

| File | Covers |
|---|---|
| `test_timeout_abort.py` | Child timeout / abort / child-failure / malformed-result classification + flow routing (RS-1, RS-2, RS-4) |
| `test_429_rate_limit.py` | **G4** — provider 429 / rate-limit resilience: environment-class classification, no blind retry, no retry amplification, deterministic routing (environment → recovery; unknown → escalate) |
| `test_registry_gate.py` | **G9** — runtime registry protection: non-sanctioned writes to `state/registry/` + `audit/` DENIED before mutation; sanctioned `registry_write`/`audit_append` channels still work; ISO-LIVE-006 live variant **BLOCKED**; no-regression (denial audited, no partial allow, no cross-root writer grant) |
| `conftest.py` | Fixtures + failure-injecting runners. Defines `RateLimited(DelegationTimeout)` — a **test-support** rate-limit type that maps to the **existing** `environment` class through the **existing** `collection.classify_adapter_failure`; no production classifier is added or weakened |

## G4 — provider 429 / rate-limit resilience

The observed Phase-3 HTTP 429 is an **environment-class** failure (Runbook
07/08). The deterministic runtime already handles it:

1. **Classification is deterministic** — a rate-limit failure is typed (the
   test-support `RateLimited` subclasses the adapter's `DelegationTimeout`),
   so `orchestrator/runtime/collection.py::classify_adapter_failure` maps it
   to `("environment", ...)` with **no classifier change**.
2. **No blind retry (AUTH-INV-16 / REC-001)** — `control/recovery.py::request_retry`
   refuses an empty cause and an identical cause; a retry happens only on a
   **new** diagnosed cause, within the existing attempt cap
   (`DEFAULT_MAX_ATTEMPTS = 1`).
3. **Deterministic routing** — `environment` → recovery lifecycle
   (`RECOVERING`, `RecoveryRecord` PRESERVED with `failure_class=environment`);
   `unknown` → `ESCALATED` (Runbook 08, never guessed).
4. **No retry amplification** — a burst of identical 429s consumes at most
   one retry per cause; distinct new causes are bounded by the total attempt
   cap.

## G9 — runtime registry protection (deterministic equivalent of ISO-LIVE-006)

ADR 0002 mechanism as tested: the path-aware execution gate
(`control/execution_gate.py::authorize_write`) denies any non-sanctioned write
to `state/registry/` or `audit/` **before any filesystem mutation** (no file
created, no directory entry added, no residue). The sanctioned single-writer
channels (`registry_write` → `state/registry/**`, `audit_append` → `audit/**`)
still work and **cannot cross roots**. `writer=True` on a generic action grants
nothing on protected paths.

**ISO-LIVE-006 (live variant) is BLOCKED in this session**: it requires a
mounted DSH session (`DSH_LIVE_BRIDGE_ACTIVE=1`), which is not set. The
deterministic equivalent is asserted here; do **not** claim live-DSH proof.

## Run

```bash
.venv-tests/bin/python -m pytest tests/resilience/ -q
```

## Scope check

**Added (this session):** `tests/resilience/` (this directory only).

**Not modified:** `control/`, `orchestrator/`, `state/`, `audit/`, `config/`,
`schemas/`, `agents/`, any existing test file, any `docs/` outside
`docs/phase-5/resilience/`. No DSH core/profile/preset/session-policy change.
No new tools. No Agent Teams.

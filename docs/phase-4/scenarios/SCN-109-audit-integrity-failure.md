# SCN-109 — Audit Integrity Failure (bounded)

- **Id**: `SCN-109`
- **Runbook**: `docs/runbooks/10-audit-integrity-failure.md`
- **PRD §17 skeleton**: #10 — Unauthorized destructive request (audit protection variant)
- **Anchors**: AUD-001..004 · AUTH-INV-14/20 · THREAT-018 · AUD-001..004
- **Test**: `tests/scenarios/test_executable_scenarios.py::TestAuditIntegrityFailure`
- **Status**: EXECUTABLE (deterministic runtime). Live-DSH variant **BLOCKED** (needs RDE-1 mount).

---

## Preconditions

- Workspace as in SCN-101, with the `audit/` directory and the project audit ledger.
- Sub-cases:
  - `SCN-109a` **chain break**: write events to the ledger, compute chain, then tamper (modify/remove an event line), then `verify_chain` → `AuditIntegrityError` on first divergence.
  - `SCN-109b` **blank line / corrupt line**: insert a blank line or non-JSON line into the JSONL ledger → `read_events_strict` → `AuditIntegrityError`.
  - `SCN-109c` **truncation**: truncate the ledger (remove trailing lines) → `detect_truncation` vs known-good cumulative hash → `(False, problems)`.
  - `SCN-109d` **duplicate event_id**: append an event with an already-used `event_id` → `verify_append_only` → `(False, problems)`.
  - `SCN-109e` **protected-path write DENY**: a plan targeting `audit/` or `state/registry/` is denied by the execution gate before any mutation (ADR 0002).
  - `SCN-109f` **audit does not grant authority**: `audit_is_authority_source(any_event)` → `False` always (AUTH-INV-14).

## Objective

Prove that the audit ledger's integrity is verifiable: tampering, truncation, and corruption are detected as `AuditIntegrityError` / `verify_append_only` problems, and the execution gate prevents writes to the protected `audit/` path. The ledger is **never authority** (AUTH-INV-14).

## Actors

- **orchestrator** — writes audit events through the sanctioned channel; verifies chain integrity.
- **checker** (the test / operator) — runs `verify_chain`, `read_events_strict`, `detect_truncation`, `verify_append_only`, `authorize_write`.
- **Human** — the only escalation path for a detected integrity failure (Runbook 10); no in-band recovery.

## Expected state

- `AuditIntegrityError` raised for 109a/b; `(False, problems)` for 109c/d.
- `authorize_write("write", "audit/events.jsonl", ...)` → `Denied` (protected path, ADR 0002).
- `audit_is_authority_source(...)` → `False` always.
- Flow targeting `audit/` → `BLOCKED` (execution gate DENY before any mutation).

## Expected gates

- `execution` gate: `authorize_write` → DENY for `audit/` and `state/registry/` targets.
- No other gates are involved in the audit integrity checks themselves (the checks are independent of the flow's authority/risk/evidence gates).

## Expected execution

- **No write to the audit path** from the orchestrator's execution gate (the protected-path guard fires before any mutation).
- Tampered events are never written through the sanctioned channel; the tampering is detected by the verifier, not prevented.

## Expected verification

- The audit integrity verifiers are **read-only checks**; they do not produce a `FlowResult` outcome.
- A flow that hits the protected-path gate produces `BLOCKED` (no COMPLETE).

## Expected failure / recovery

- `failure_class` per Runbook 10: `environment` for disk corruption; `logic` for writer bugs; `authorization` for tampering/forgery; `unknown` for unclassified (mandatory escalation).
- **No in-band recovery**: the ledger is quarantined; the Human decides restore/refresh/halt.
- The orchestrator does not auto-repair or auto-delete the quarantined ledger.

## Evidence requirements

- `AuditIntegrityError` exception message carries the first divergent line.
- `verify_append_only` returns `(False, problems)` with the specific violation named.
- `detect_truncation` returns `(False, problems)` with the line count mismatch.
- `authorize_write` for `audit/**` → `Denied` (protected path, ADR 0002).
- `audit_is_authority_source` → `False` for any input.
- No-mutation proof: the quarantined ledger is byte-identical to the original (sha256 check).

---

*Deterministic-runtime evidence only. No L3 claim. Live variant BLOCKED.*
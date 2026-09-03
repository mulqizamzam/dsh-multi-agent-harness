# Phase 5 / Session G — G13 External-Content Verification Detail

- **Status**: VERIFICATION (deterministic; **no new security claim**)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/docs/phase-5/security/` + `multi-agent-harness/tests/phase5_security/`.
- **Companion**: `docs/phase-5/security/0001-g10-g13-security-residual-analysis.md` §2.

---

## 1. The trust posture (external content is DATA, not instructions)

The architecture treats all external/subagent content as untrusted data:

- **Structured TaskResult** from a child is validated against a schema, its role identity is checked, and it is stored as `result` — it is never an authority input.
- **Child text** is never read as a gate input.
- **Authority** is read exclusively from the structured delegation registry at the control-plane layer — never from model prose, audit entries, or messages.

## 2. Enforcement points (code, not prompts)

| Enforcement | Where | Behavior |
|---|---|---|
| Authority keys stripped from child context | `orchestrator/dsh/context.py::build_task_context` | `extra` keys in `_AUTHORITY_KEYS` are dropped + recorded in `_adapter.stripped_authority` |
| Authority-bearing payload refused | `orchestrator/dsh/context.py::assert_no_authority_in_payload` | raises `DSHError` (THREAT-020) |
| Subdelegation denied by actor | `orchestrator/dsh/client.py::_assert_actor_may_delegate` | raises `ProhibitedDelegation` for any non-orchestrator actor (DLG-003) |
| Reported success ≠ verification | `orchestrator/execution/engine.py::can_complete` | COMPLETE requires an observed outcome (THREAT-016 / AUTH-INV-15) |

## 3. Verified (deterministic, this session)

All eight `tests/phase5_security/` tests pass:

1. authority-shaped keys removed from `extra_context` (THREAT-020);
2. `assert_no_authority_in_payload` refuses authority-bearing bodies;
3. a malicious/revoked delegation cannot be overridden by child output;
4. a specialist cannot delegate even under adversarial content (DLG-003);
5. a child claiming SUCCESS without an observed outcome does not reach COMPLETE (reported ≠ verified);
6. G10 negative path-isolation tests (raw write lands, channeled write DENIED, traversal DENIED, no closure claim).

## 4. Unverified (UNKNOWN — no claim)

- Live DSH child behavior under prompt-injection payloads (needs the D4/D7 mount; BLOCKED this session).
- DSH driver-internal content-isolation beyond the adapter (ADR 0001 UNKNOWN #1).

**No prompt-injection claim is made.** This session verifies the adapter's data-not-instructions treatment deterministically; it does not close G13.

---

*Status: VERIFICATION. Deterministic defenses verified; full closure UNKNOWN/not claimed. No DSH or production change.*

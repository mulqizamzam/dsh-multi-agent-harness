# L3 Verifier Implementation — G5 Security Note

- **Status**: IMPLEMENTED (verifier infrastructure complete + tested; **no L3 run, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/l3_runner/` · `tests/l3_reference/` · `docs/security/` · `docs/phase-5/l3/` (write-only per the G5 session brief).
- **Companion**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/security/0006-l3-implementation-report.md` · `docs/security/0007-l3-run-prerequisites.md` · `docs/testing/0003-l3-evidence-validation-specification.md` · `docs/phase-5/l3/0002-g5-verifier-implementation-report.md`.

---

## 1. What this note documents

G5 (the independent L3 verifier) is now implemented as code-enforced infrastructure. This note records the **security-relevant properties** of that implementation: what is verified, how independence is enforced in code (not by convention), and the honesty boundary (no L3 claim, no UID faking, no simulated PASS).

## 2. Security properties (code-enforced)

| Property | Enforcement | Location |
|---|---|---|
| Verifier is an independent OS process | runner spawns via `subprocess`; never a DSH subagent tool | `runner.py` R2, R5 |
| No production-gate imports in the verifier process | `assert_clean_imports()` refuses `control.*`, `orchestrator.foundation.*`, `audit.helpers`, `state.helpers`, `tests.control_plane`, `tests.execution_gate` | `verifier.py` |
| Reference verdict computed BEFORE the runtime verdict | strict ordering in `Verifier.run()` | `verifier.py` |
| Verifier does not read the orchestrator session log | reads only the bundle dir + captured fixture JSON | `verifier.py` |
| Verifier does not self-certify | IO-10: `verdict-match.json` excluded from the audit chain; pre-existing `verifier-independence.json` (orchestrator-written/stale) is removed before the verifier recomputes it | `verifier.py`, `independence.py` |
| Evidence provenance / replay metadata / state hashes verified | `Verifier.verify_evidence()` — malformed present items force evidence failure | `verifier.py` |
| UID separation never faked | IO-2 fails honestly on a same-UID host → `l3_claim_possible=False` | `uid_readiness.py`, `independence.py` |
| L3 claim gate is the single decision point | `evaluate_l3_claim()` — P1..P4 + conditions; rehearsal forces `l3_claim=false` | `claim_gate.py` |
| Live driver never simulates a PASS | precondition probes → BLOCKED; all-present → still refuses actual dispatch (`live-execution-not-authorized`) | `runtime_driver.py` |
| Evidence is DATA, never authority | audit events never grant authority (AUTH-INV-14); the claim gate requires the Human-signed plan, not evidence prose | `claim_gate.py`, runtime audit |

## 3. What is NOT claimed

- **No L3 claim.** No evidence bundle in this session satisfies P1–P4 (IO-2 fails on this same-UID host; no Human-signed live plan; no authorized live run). Rehearsals are machinery proof only (`l3_claim=false`).
- **G10 (DSH path isolation) and G13 (prompt injection) remain OPEN** — this implementation does not claim either.
- **No simulated PASS anywhere**: the live driver, the claim gate, and the rehearsal all fail closed.

## 4. Regression posture

- 131 L3 tests pass (`tests/l3_runner/` + `tests/l3_reference/`).
- No production control code, DSH core/profile/preset, or session policy modified.
- No new tool enabled; no web_fetch; no Agent Teams.

---

*Status: IMPLEMENTED. Verifier infrastructure complete and tested; no L3 run; no L3 claim; no security claim beyond the verified properties above.*

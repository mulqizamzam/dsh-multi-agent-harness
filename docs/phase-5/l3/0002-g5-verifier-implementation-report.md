# Phase 5 / G5 — Independent L3 Verifier Implementation Report

- **Milestone**: PHASE 5 / G5 — INDEPENDENT L3 VERIFIER
- **Status**: **PASS_WITH_CONDITIONS** (verifier infrastructure complete + tested; **no live L3 run, no L3 claim, no separate-UID promotion**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/l3_runner/` · `tests/l3_reference/` · `docs/security/` · `docs/phase-5/l3/` (write-only per the session brief).
- **Companion**: `docs/security/0003` (L3 plan) · `0005` (evidence infrastructure) · `0006` (implementation report) · `0007` (run prerequisites) · `docs/testing/0003` (validation) · `docs/phase-5/l3/0001-l3-execution-readiness.md` (G6/G7/G8) · `docs/phase-5/master-integration-gate.md` (G5 was BLOCKED).

---

## 1. What was implemented (closing G5)

The independent L3 verifier infrastructure required to close G5 is now **complete and code-enforced**. Prior sessions built the runner, collector, independence, preflight, replay, validator, rehearsal, plan-signing and UID-readiness modules (116 tests). This session closed the remaining G5 gaps:

| # | Gap | What this session added | File |
|---|---|---|---|
| 1 | **Claim gate (requirement 8)** | `evaluate_l3_claim()` — the single code-enforced P1–P4 gate (runtime, independent observer, external oracle, reproducible replay) + Human-signed plan + complete bundle + no unresolved UNKNOWN + no same-process/same-UID + verdict agreement. Rehearsal always forces `l3_claim=false`. | `tests/l3_runner/claim_gate.py` (new) |
| 2 | **Verifier evidence verification (requirement 2)** | Verifier now independently verifies **evidence provenance** (E10), **replay metadata** (E11) and **state hashes** (E4/E5); malformed present items force an evidence failure → match=false. | `tests/l3_runner/verifier.py` |
| 3 | **Verifier wiring** | `compute_match()` now routes `l3_claim` through the claim gate; `verdict-match.json` records `claim_gate` + `evidence_checks`; `exit_code()` requires the gate to pass. | `tests/l3_runner/verifier.py` |
| 4 | **Runner ordering fix** | `replay.json` (E11) is written **before** the verifier runs, so the verifier can independently verify replay metadata (previously it saw `replay_metadata=absent`). | `tests/l3_runner/runner.py` |
| 5 | **Safe live driver (requirement 7)** | `LiveDSHRuntimeDriver` is no longer a bare stub: it probes live preconditions (Human-signed plan, D4/D7 mount, approval answerer, baseline policy, execution gate as sole write channel) and **returns BLOCKED** naming the missing precondition — never a simulated PASS. | `tests/l3_runner/runtime_driver.py` |
| 6 | **G5 test suite** | 15 new tests covering fixture tampering, oracle disagreement, missing Human signature, evidence verification, claim-gate P1–P4, same-UID demotion, live-driver BLOCKED, classification table. | `tests/l3_runner/test_l3_g5_verifier.py` (new) |

---

## 2. Reference oracles (requirement 1) — VERIFIED

All eight independent reference gates exist and are **stdlib-only with no production imports** (verified by import scan):

| Gate | Module | Entrypoint | Stdlib-only |
|---|---|---|---|
| Authority | `tests/l3_reference/authority_gate.py` | `oracle_authority` | ✓ |
| Delegation | `tests/l3_reference/delegation_gate.py` | `oracle_delegation` | ✓ |
| Execution / path | `tests/l3_reference/execution_gate.py` | `oracle_execution_gate` | ✓ |
| Role capability | `tests/l3_reference/role_gate.py` | `oracle_role` | ✓ |
| Recovery | `tests/l3_reference/recovery_gate.py` | `oracle_recovery` | ✓ |
| Verification | `tests/l3_reference/verification_gate.py` | `oracle_verification` | ✓ |
| State transition | `tests/l3_reference/transition_gate.py` | `oracle_transition` | ✓ |
| Audit integrity | `tests/l3_reference/audit_chain.py` | `oracle_audit_chain` | ✓ |

Each uses independent data structures (rule tables / checklist decision tables), no shared production implementation.

---

## 3. Verifier (requirement 2) — VERIFIED

| Requirement | Enforcement |
|---|---|
| Separate OS process | runner spawns via `subprocess` (`runner.py` R2); never a DSH subagent tool |
| Reference verdict BEFORE runtime verdict | `Verifier.run()`: `compute_reference_verdict()` (oracle) → `read_runtime_verdict()` → `compute_match()` |
| Reject production-gate imports | `verifier.assert_clean_imports()` refuses `control.*`, `orchestrator.foundation.*`, `audit.helpers`, `state.helpers`, `tests.control_plane`, `tests.execution_gate` |
| Reject orchestrator process identity | IO-1 (distinct PID) in `independence.py` |
| Verify oracle count | IO-6 (≥2 oracle classes) + runner R6 |
| Verify evidence provenance | NEW — `Verifier.verify_evidence()` checks E10 (delegation_chain + children) |
| Verify before/after state hashes | IO-9 + NEW `evidence_checks.state_hashes` |
| Verify audit integrity | IO-8 via `tests/l3_reference/audit_chain.verify_ledger` |
| Verify replay metadata | NEW — `evidence_checks.replay_metadata` (fixture/verifier/schema pins) |
| Fail closed on any discrepancy | any `fail` evidence item → match=false; any gate/IO failure → `l3_claim=false` |

---

## 4. Independence (requirement 3) — IO-1..IO-10 VERIFIED

`tests/l3_runner/independence.py` computes IO-1..IO-10: distinct PID (IO-1), distinct UID (IO-2), verifier binary sha256 (IO-3), not in orchestrator session tree (IO-4), independent reference files (IO-5), ≥2 oracle classes (IO-6), signed-plan precedes runtime (IO-7), audit chain valid (IO-8), DENY-protected before==after hashes (IO-9), verdict-match excludes itself from audit chain (IO-10).

**Honesty rule preserved**: on this same-UID host IO-2 fails honestly → `l3_claim_possible=False` → rehearsal only; never upgraded to L3.

---

## 5. Evidence (requirement 4) — 13-item contract VERIFIED

The runner/collector produce the full bundle (manifest, env, plan, before/after hashes, runtime verdict, audit log, reference verdict, oracle classes, provenance, replay, independence, verdict match) under a scratch base for rehearsals. **Evidence is DATA; evidence never grants authority** — the claim gate requires the Human-signed plan + independent verifier; audit events never carry authority (AUTH-INV-14 preserved).

---

## 6. Replay (requirement 5) — VERIFIED

`tests/l3_runner/replay.py` pins schemas (sha256), verifier binary (sha256), and the deterministic fixture hash; `replay.json` records the replay command. The rehearsal reproduces the same verdict; **fixture drift changes the hash** (tested by `TestFixtureTampering`).

---

## 7. Human plan (requirement 6) — VERIFIED

`tests/l3_runner/plan_signing.py` validates signoff fields (`human_signoff_id`, `human_signoff_ts`, `human_signoff_method`), enforces pre-runtime ordering (LV7/IO-7), and provides a signing checklist + template. **No Human signature is invented**: absent/unsigned plans are `UNSIGNED` / the claim gate reports `human-signed-plan` failure → `l3_claim=false` (tested by `TestMissingHumanSignature`).

---

## 8. Live driver (requirement 7) — SAFE INTERFACE

`LiveDSHRuntimeDriver` returns **BLOCKED** (naming the missing precondition) whenever any live precondition is absent, and refuses an actual live dispatch even when all preconditions appear present (`live-execution-not-authorized`) — **never a simulated PASS**. It does not bypass approval, authority, D4/D7 boundaries, or the existing runtime gates.

---

## 9. L3 claim gate (requirement 8) — VERIFIED

`evaluate_l3_claim()` enforces P1 (runtime), P2 (independent observer + UID), P3 (external oracle ≥2), P4 (reproducible replay) plus Human-signed plan, complete bundle, IO-all-pass, no unresolved UNKNOWN, verdict agreement. Any failure → `l3_claim=false`.

---

## 10. Tests

```text
$ .venv-tests/bin/python -m pytest tests/l3_runner/ tests/l3_reference/ -q
131 passed
```

Coverage includes: clean verifier imports (AST + runtime), separate subprocess, PID difference, UID handling + honest demotion, oracle independence, verdict-before-runtime order, evidence integrity (provenance/replay/state hashes), audit chain, signed-plan timing, replay determinism, **fixture tampering**, **oracle disagreement**, verifier self-certification rejection, false L3 claim rejection, same-process rejection, missing UID demotion, **missing Human signature**, runtime verdict mismatch, incomplete bundle.

---

## 11. Security claim status

- **No L3 claim.** Rehearsal runs force `l3_claim=false`; no `audit/l3/` bundle committed; IO-2 fails honestly on this same-UID host.
- **G10 (path isolation) and G13 (prompt injection) remain OPEN** unless independently proven — no claim made here.
- No production code, DSH core/profile/preset, session policy, or new tool modified. No destructive/high-impact L3 scenario executed.

---

*Status: PASS_WITH_CONDITIONS — verifier infrastructure complete and tested (131 L3 tests green). Conditions: a real L3 claim requires a separate-UID host, Human-signed plans, an authorized live run (P1–P4). No L3 claim is made in this session.*

# L3 Critical-Control FINAL Readiness — Final Preflight Package

This directory documents the **exact remaining gap** between the current
rehearsal-ready L3 machinery and a **legitimate L3 claim** for the six
critical controls (authority, execution-time recheck, protected path, recovery
privilege bounding, stale state, audit integrity).

| Document | Content |
|---|---|
| [`0001-l3-critical-control-final-readiness.md`](0001-l3-critical-control-final-readiness.md) | The final readiness matrix: per-control P1–P4 status, the check-list verdict (PID, UID, verifier, signed plan, bundle, audit, hashes, replay, agreement), the exact blockers, the exact evidence needed, and the claim gate status. |
| [`0002-l3-critical-preflight-package.md`](0002-l3-critical-preflight-package.md) | The FINAL PREFLIGHT package: re-validates the six critical controls (authority, execution-time recheck, protected path, recovery privilege bounding, stale state, audit integrity) and the check items (P1–P4, separate UID, Human-signed plan, evidence bundle, replay, verdict agreement) against the current machinery; documents the LV16 evidence-contract resolution; exact blockers; claim gate status. **PREPARED-ONLY — no live L3, no claim, no invented signature.** |
| Tests | `tests/l3_runner/critical/final/` — `test_l3_final_readiness.py` (96 tests, Session C matrix) + `test_l3_critical_preflight.py` (final-preflight lock tests). Deterministic proof of every row below. |

## One-line status

**The machinery is READY to rehearse; NO control is L3; NO legitimate L3
claim is possible in this sandbox.** All 8 critical scenario bundles rehearse
green (oracle agreement, replay determinism, complete 13-file bundles,
`l3_claim=false`), but the claim gate fails honestly on: same-UID host
(IO-2), no live DSH runtime (P1-live / marker unset), no approval answerer,
no real Human signoff (O4), and an authorized run. The LV16 shape note was
**resolved (Session F)** — the recovery/state-transition/audit oracles now
emit the canonical `checklist_item_results` field, so those bundles pass LV16.

**NO L3 CLAIM IS MADE. NO LIVE L3 RUN HAS EXECUTED. NO SIGNATURE INVENTED.**

## Test counts (observed)

```text
$ .venv-tests/bin/python -m pytest tests/l3_runner/critical/final/ -q
203 passed   (96 final-readiness + 107 final-preflight lock tests)
```

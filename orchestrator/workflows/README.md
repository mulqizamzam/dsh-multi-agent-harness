# Workflow skeleton — fan-out/collect with gate placeholders

This is the **structural skeleton** of the orchestrator's deterministic
fan-out/collect workflow, per `orchestrator/contract.md` §12. It is **NOT a
production workflow**: the gate blocks are placeholders (no enforcement lives
in a script — see ADR 0001 correction #4), and `DRY_RUN` mode (default true)
performs decomposition/selection/collection over in-memory placeholder data
without spawning any subagent.

## Shape

The skeleton reports the full 15-phase chain (Phase 1E) and executes only the
deterministic fan-out/collect steps:

```text
INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT → DELEGATE
→ COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE → REVIEW_GATE
→ AUTHORITY_GATE → EXECUTE_GATE → VERIFY_GATE
```

Script-local phase calls:

```text
phase("decompose")    → structured task list
phase("select")       → minimum specialist set
phase("delegate")     → per-role agent() calls with outputSchema (DRY_RUN: placeholder intents)
phase("collect")      → gather structured results
phase("gate")         → placeholder boundaries (NO enforcement — re-validated by orchestrator)
phase("synthesize")   → consolidated result returned to the orchestrator
```

## Rules (contract §12 + Phase 1E hardening)

1. The script performs **no enforcement** — gates are placeholders.
2. The orchestrator **re-validates everything** the script returns.
3. The script has no FS/network access (VERIFIED).
4. A gate placeholder that is unresolved must **stop** the script, never
   auto-authorize.
5. **BadSector review is conditional**: mandatory for HIGH / intrinsic-high
   actions (skipping = transition violation, THREAT-015); a PASS clears review
   only and is **never** authorization (AUTH-INV-09).
6. **Execution requires an execution-time authority re-check** (AUTH-INV-05):
   the orchestrator re-validates authority immediately before the execute_gate,
   never relying on the planning-time check alone.
7. In `DRY_RUN: false`, `agent()` calls are uncommented by the orchestrator when
   wiring a real objective; the outputSchema contract is fixed here.

## Files

- `skeleton.js` — the skeleton (valid DSH workflow script, top-level await).
- `skeleton.schema.json` — the structured output schema (tasks / selected /
  results / gates / phases).

## Wiring (Phase 3+)

The orchestrator loads this skeleton, sets `DRY_RUN = false`, populates
`decompose()`/`selectSpecialists()` with the objective, and the delegate phase
spawns per-role `subagent_<id>` instances (the per-role tool instances defined
in `config/role-preset-mapping.yaml`). Gates remain placeholders that the
orchestrator re-checks after collection.

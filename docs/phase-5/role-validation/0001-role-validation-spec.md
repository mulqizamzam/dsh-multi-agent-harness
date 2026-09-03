# Phase 5 / Session E — Role Runtime Validation (G12)

- **Milestone**: Phase 5 / Session E — ROLE RUNTIME VALIDATION
- **Status**: PREPARED (harness + deterministic validation green; **live validation BLOCKED on the D4/D7 mount** — no fake evidence)
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/tests/phase5_role_validation/` + `multi-agent-harness/docs/phase-5/role-validation/` (write-only).
- **Companion**: `docs/phase-4/0005-production-readiness-assessment.md` (G12, §4.5, §7.5) · `docs/phase-3/0002-phase3-runtime-closure.md` (ASSUMED/UNKNOWN sections) · `config/role-preset-mapping.yaml` · `config/tool-subagent-instances.yaml` · `config/permissions.yaml` · `tests/live_dsh/` (discovery + adapters).

---

## 1. What this session proves

Only the **CTO** role was independently exercised live in Phase-3 closure (INT-01/INT-07 with `subagent_cto`). The remaining six roles — **Zeko, CFO, Kai, Somad, BadSector, Nova** — were resolved and mounted (all 7 probes passed) but their **live dispatch acceptance** (persona/toolFilter/maxDepth on the spawn provider, structured TaskResult capture, provenance) was **assumed uniform**, never independently verified (Phase-3 closure UNKNOWN section).

G12 is the harness + protocol to close that gap with real DSH only.

## 2. What is verified (deterministic, this session)

The harness (`tests/phase5_role_validation/harness.py`) runs **deterministic checks that must pass for all six target roles**:

| Role | Resolution | toolFilter consistent | Prohibited tools absent | Subdelegation denied |
|---|---|---|---|---|
| **Zeko** | PASS | PASS | PASS (none prohibited — write-capable) | PASS (DLG-003) |
| **CFO** | PASS | PASS | PASS (`bash/edit/write` denied) | PASS (DLG-003) |
| **Kai** | PASS | PASS | PASS (`bash/edit/write` denied) | PASS (DLG-003) |
| **Somad** | PASS | PASS | PASS (none prohibited — write-capable) | PASS (DLG-003) |
| **BadSector** | PASS | PASS | PASS (`bash/edit/write` denied) | PASS (DLG-003) |
| **Nova** | PASS | PASS | PASS (none prohibited — write-capable) | PASS (DLG-003) |

Check definitions (per role, from `config/tool-subagent-instances.yaml` + `config/permissions.yaml`):

1. **Role resolution** — role → `subagent_<id>` resolves with `tool_name == subagent_<role>`, `persona == role-<role>`, `provider == spawn`, `max_depth == 1`.
2. **toolFilter consistency** — `allow ∩ deny = ∅`; no delegation tool (`subagent*`, `send_message`, `workflow`, `ralph`) in allow; `max_depth == 1` (V1 subdelegation DENY BY DEFAULT).
3. **Prohibited tools** — read-only/review roles (CFO, Kai, BadSector) do NOT carry filesystem mutation tools (`bash`, `edit`, `write`) in their allow list (capability matrix: server_write/code_write = no).
4. **Subdelegation denial** — a specialist actor attempting to delegate raises `ProhibitedDelegation` (DLG-003).

**Result: 28 tests pass** (`tests/phase5_role_validation/test_role_validation.py`).

## 3. What is NOT verified (live, BLOCKED this session)

The **live checks** (`check_live_provenance`) require the D4/D7 mount marker (`DSH_LIVE_BRIDGE_ACTIVE=1`). The marker is **unset in this session** → the six live checks report **BLOCKED** and no fake live evidence is produced.

**What a future live run must verify per role** (the harness accepts an injected `bridge_dispatch` for this):

- a real `subagent_<role>` dispatch settles with a real run id and `stop_reason == completed`;
- the child produces a structured TaskResult satisfying `schemas/task-result.schema.json` (role identity preserved);
- provenance records `role`, `tool_name`, real `run_id`, `stop_reason`, `source=RUNTIME-OBSERVED`;
- toolFilter is enforced on the live surface (filtered tools absent from the child's tool schema, per `tests/live_dsh/` contract).

## 4. Role × check matrix (G12 status)

| Role | Resolution | toolFilter | Prohibited tools | Provenance (live) | Subdelegation denial |
|---|---|---|---|---|---|
| Zeko | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| CFO | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| Kai | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| Somad | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| BadSector | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| Nova | VERIFIED (deterministic) | VERIFIED (deterministic) | VERIFIED (deterministic) | PREPARED-PENDING-LIVE | VERIFIED |
| CTO (ref) | VERIFIED (live, Phase-3) | VERIFIED (live, Phase-3) | VERIFIED | VERIFIED (live) | VERIFIED |

## 5. How to run the live validation (once the mount is active)

```bash
# deterministic checks (always run, must pass):
.venv-tests/bin/python -m pytest tests/phase5_role_validation/ -q

# live run (only after D4/D7 mount + DSH_LIVE_BRIDGE_ACTIVE=1):
.venv-tests/bin/python -m tests.phase5_role_validation.harness --json \
  --report audit/runtime/phase5-role-validation.json
```

The harness exits `2` on a deterministic failure; live checks blocked are reported, not failed. The JSON report records per-check pass/blocked status for the audit trail.

## 6. Honesty boundary

- **No role is claimed live-validated without a real live run.** Only CTO has live evidence (Phase-3 closure).
- The harness **never fakes** a live result: with the mount absent, live checks are BLOCKED.
- **Role boundaries were NOT modified** to make tests pass. The deterministic checks validate against the declared D4/D7 config; a drift would be reported as a failure.

## 7. G12 verdict

**G12 is OPEN** — the validation protocol and deterministic harness are complete and green (28 tests), but the **live dispatch evidence for the six roles is still BLOCKED** on the D4/D7 mount. Closing G12 requires: mount → `DSH_LIVE_BRIDGE_ACTIVE=1` → run the harness live → record real provenance per role.

---

*Status: PREPARED. Deterministic validation green (28 tests). Live validation BLOCKED (no mount). No fake evidence. No role boundary modified.*

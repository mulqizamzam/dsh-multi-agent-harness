# Runtime Evidence QA — Security Note

- **Status**: note (evidence QA layer; no new security claims)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Scope**: `multi-agent-harness/` — documents the security posture of the runtime-evidence QA layer from Phase 3 / Session E. **No production code modified. No DSH core/profile/preset/session policy touched. No L3 claim made.**
- **Companion to**: `docs/testing/0002-runtime-evidence-qa-specification.md` · `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md`

---

## 1. What this layer does and does not claim

The runtime-evidence QA layer (`tests/evidence/`) is a **structure-only validator**. It checks that an evidence bundle is complete, well-formed, and internally consistent. It does **not**:

- verify that a control actually enforced anything at runtime (that is the L3 verifier's job — not built);
- claim that any control is L3;
- make any new security claim beyond the invariants already asserted in the existing test suite;
- expand the security posture of the project.

**L3 remains NOT CLAIMED.** The L3 plan (`docs/security/0003`) remains proposal-only; none of the nine critical controls is L3 today. This layer's rejection of `INDEPENDENTLY-VERIFIED` evidence without P1–P4 properties is precisely to keep that boundary honest.

## 2. Evidence is data, never authority (AUTH-INV-14)

An evidence bundle records what happened. It is consumed by the QA validator and by humans for review. It is **never** read by the authority gate, and the authority gate **never** treats an evidence item, an audit entry, a BadSector PASS, or agent text as a grant (AUTH-INV-01/07/09/13/14). The validator enforces the corresponding structure:

- `R7` — a bundle consisting only of agent text is rejected;
- `R10` — an `ALLOW` authority decision supported only by a BadSector PASS, with no delegation, is rejected (PASS ≠ authority, AUTH-INV-09);
- `R3` / `R15` — a false L3 claim, or `INDEPENDENTLY-VERIFIED` evidence without the full L3 property set, is rejected.

## 3. Rejection rules are structural, not conclusive

A rejected bundle means the **evidence is incomplete or inconsistent** — it does **not** prove that a control failed. Conversely, a passing bundle proves only that the evidence is structurally complete; it does **not** prove the control enforced anything. This distinction is load-bearing: QA output must never be misread as a security verdict.

## 4. Prompt injection remains UNKNOWN

The DSH-native handling of external/prompt-injected content is **UNKNOWN** (documented in `docs/security/0002` §17 and `docs/testing/0001` §9 U3). This session makes **no** claim on prompt injection, adds no evidence channel for it, and the QA layer does not test it. INJ-* remains L1 (quarantine) only.

## 5. No bypass, no subdelegation, no authority expansion

The QA layer touches no execution path:

- it does not invoke the DSH adapter, the ExecutionEngine, or the runtime flow;
- it does not write to protected paths (`state/registry/`, `audit/`);
- it validates bundle dicts in-process only;
- it cannot subdelegate (it holds no delegation tool), cannot expand authority (it holds none), and cannot bypass a gate (it never calls one).

All 12 QA tests are pure structure-validation tests over in-memory bundle dicts (plus, for hash validation, an optional temp file the test itself creates under `tmp_path`).

## 6. Retention

Evidence bundles are retained under `audit/runtime/<scenario>/` per `docs/testing/0002` §4. Retention is advisory; this layer does not create those directories. The `audit/l3/` store remains reserved for a future L3 run, which has not begun (B6 in the L3 plan).

## 7. Scope check

**In scope**: this file · `docs/testing/0002-runtime-evidence-qa-specification.md` · `tests/evidence/`

**Not touched**: `orchestrator/`, `control/`, `state/`, `audit/helpers/`, `agents/`, `config/`, `schemas/`, DSH core/profile/preset/session policy, D4/D7 composition, any existing test file, any D2/D3 test.

---

*Status: note. No security claim expansion. L3 remains NOT CLAIMED. Prompt injection remains UNKNOWN. No production or DSH changes.*
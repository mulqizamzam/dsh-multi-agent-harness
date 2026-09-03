# L3 Run Prerequisites — Separate UID/Process, Verifier, Preflight, Human-Signed Plan, Reproducibility

- **Status**: specification (run-prerequisites contract; **no L3 execution, no L3 claim**)
- **Date**: 2026-08-31
- **Version pin**: DeepSeek Harness `0.1.1-rc.2`
- **Companion to**: `docs/security/0003-l3-independent-verification-plan.md` · `docs/design/0002-l3-verification-specification.md` · `docs/security/0005-l3-evidence-infrastructure-specification.md` · `docs/testing/0003-l3-evidence-validation-specification.md` · `docs/security/0006-l3-implementation-report.md`
- **Scope**: `multi-agent-harness/docs/security/0007-l3-run-prerequisites.md` · `multi-agent-harness/tests/l3_runner/preflight.py` · `multi-agent-harness/tests/l3_runner/test_l3_preflight.py`. **No L3 run is executed. No session policy is changed. No DSH core/profile/preset/session policy is touched. No production control-plane code is modified. No control is claimed L3.**
- **Class**: L3 RUN PREREQUISITES

> This specification fixes, in one place, the **prerequisites that must hold *before* an L3 scenario is run**: why the verifier needs a separate UID/process, what the verifier requires to be valid, what the environment preflight checks, what a Human-signed plan must contain, and what reproducibility requires. It is enforced, read-only, by `tests/l3_runner/preflight.py` (check ids `PF-*`), which never runs L3.

---

## 1. The need for a separate UID / process (P2 — independent observer)

L3 property **P2** (`docs/security/0003` §1) requires the verifier to be **not the agent under test, not its orchestrator, and not any process owned by the acting agent's session tree**. The minimal viable environment is two processes on the same host, with the verifier in a **separate OS process under a separate UID/credential**, not spawned by the orchestrator (`0003` §4.1).

### 1.1 Why separate process (mandatory)

A verifier that runs **in the orchestrator's process** shares its memory, its sys.modules, its environment, and its ability to be influenced by the acting agent. It cannot provide independent observation: a single Python process holding both the actor and the observer collapses the trust boundary (`0003` §5.2). Therefore:

- **PF-UID-1 (IO-1)** — the verifier must run as a distinct OS process (`verifier_pid ≠ orchestrator_pid`, both non-zero). Enforced by `independence.py` IO-1 and probed by preflight `PF-UID-1`.
- **PF-UID-3 (IO-4)** — the verifier must not be spawned via the orchestrator's session tree (no `subagent` / `subagent_fork` / `send_message`). The runner spawns it via `subprocess`; preflight `PF-UID-3` documents this.

### 1.2 Why separate UID (mandatory for an L3 claim; honesty rule)

A separate **process** alone is insufficient: on a host where both processes run under the same UID, the verifier still shares filesystem read/write authority with the orchestrator's credential. A verifier that the orchestrator's UID could overwrite, truncate, or influence is not independent. Therefore:

- **PF-UID-2 (IO-2)** — the verifier must run under a separate UID/credential (`verifier_uid ≠ orchestrator_uid`, both non-zero).
- **Honesty rule (load-bearing):** if the host cannot run the verifier under a distinct UID, the preflight reports `PF-UID-2` **fail** and sets `l3_claim_possible=False`. The bundle is **demoted to L2** (`L3-INDEPENDENCE-VIOLATION`). The infrastructure **never fakes a credential separation it did not achieve** (`0006` §3, `independence.py` docstring).
- **Demote, never block a rehearsal:** a failed `PF-UID-2` is a *demotion* of the L3 claim, not a rehearsal blocker. `PF-UID-2` is `required=False` in `preflight.py`, so a rehearsal/replay run still reports `all_required_pass=True` (exit `0`) while `l3_claim_possible=False` (exit stays `0`, claim stays `false`). Separation is only treated as a hard `required` gate in the evidence validator (`LV12` / `IO-2`), which rejects an L3 bundle whose `verifier-independence.json` has any failing IO check.

**What this means for this sandbox:** orchestrator and verifier run under the same host UID, so `PF-UID-2` fails honestly and **no L3 claim is possible in this sandbox** — rehearsal/replay machinery only. A real L3 run requires the verifier to be launched under a separate credential (setuid, separate user, separate host) before any L3 claim.

---

## 2. Verifier prerequisites

Before the verifier can produce valid L3 evidence, all of the following must hold. Each is checked by preflight (`PF-VER-*`) and, where applicable, enforced in `verifier.py` / `independence.py`.

| Prerequisite | Check | Enforcement / probe |
|---|---|---|
| Verifier imports **no production gate** (`control.*`, `orchestrator.foundation.*`, `audit.helpers.*`, `state.helpers.*`) | `PF-VER-1` | `verifier.assert_clean_imports()` raises on a polluted process; AST scan in tests |
| Reference oracle (O1) resolves for the gate under test | `PF-VER-2` | `OracleRegistry.load(gate)` via `ORACLE_MODULES`; file exists and is not imported by production |
| Verifier binary sha256 computable (IO-3) | `PF-VER-3` | `sha256_file(verifier.py)` |
| Verifier spawns cleanly in a subprocess (P2 machinery) | `PF-VER-4` | subprocess run `assert_clean_imports(); print('CLEAN')` |
| At least 2 oracle classes declared (IO-6 / R6) | `PF-VER-5` | runner `_require_two_oracles`; verifier `classify_failure` → `L3-ORACLE-INADEQUATE` |

The verifier computes its verdict **before** reading the runtime verdict (no post-hoc rationalisation, `0003` §5.3) and reads only on-disk artifacts + the captured action fixture — never the orchestrator's session log.

---

## 3. Environment preflight

Before any L3 scenario, the environment must satisfy the baseline defined in `0003` §4 and G9. Preflight `PF-ENV-*` detects and reports; it **never modifies** session policy or DSH.

| Preflight | Required value | Notes |
|---|---|---|
| `PF-ENV-1` (LV5) | `dsh_version == 0.1.1-rc.2` | pin is exact; later versions invalidate L3 results |
| `PF-ENV-2` (G9) | `sandbox_mode == workspace-write` **and** `approval_policy == ask` | **REPORT ONLY** — preflight never changes policy; a non-baseline value flags the G9 gap as a required failure when an env snapshot is supplied |
| `PF-ENV-3` (LV4) | env snapshot has `dsh_version, os, python_version, sandbox_mode, approval_policy, permission_preset, utc_offset_seconds, seed` | missing fields flag the snapshot |
| `PF-ENV-4` | evidence store (`audit/l3/`) creatable/writable | advisory |

An **absent** env snapshot is treated as report-only (no claim either way) so rehearsal/preflight runs stay usable; a **present** snapshot is validated strictly.

---

## 4. Human-signed plan prerequisites

Every L3 scenario **requires a Human-signed `plan.json` committed before the runtime runs** (`0003` §15.8, G3; `0002` §12.2; `0005` §3.3). The plan is the O4 oracle — the Human's signed expectation, never a post-hoc rationalisation.

Preflight `PF-PLAN-*` enforces:

| Prerequisite | Check | Notes |
|---|---|---|
| `plan.json` exists for the scenario | `PF-PLAN-1` | a missing plan is a **required failure**; the runner refuses to run without one (`ScenarioNotFoundError`) |
| plan fields are schema-valid | `PF-PLAN-2` | `scenario_id, actor, action, target, preconditions[], expected_verdict, expected_verdict_reason, human_signoff_id, human_signoff_ts` (+ `human_signoff_method` per `l3-plan.schema.json`); `expected_verdict ∈ {ALLOW, DENY}`; `human_signoff_ts` parseable |
| `human_signoff_ts` precedes the runtime verdict | `PF-PLAN-3` (LV7 / IO-7) | a post-hoc plan is not a valid oracle; strict `<` ordering |
| expected verdict declared and an O4 oracle is used | `PF-PLAN-4` | the plan/fixture must declare `oracle_classes_used` containing `O4` |
| Human signoff fields schema-valid (`human_signoff_id` pattern, `human_signoff_ts` format, `human_signoff_method` enum) and strict pre-runtime ordering | `PF-PLAN-5` (G7) | `plan_signing.validate_signed_plan` — the full `l3-plan.schema.json` oracle (O2-style, structure only); closes G7 of `0003` §11 |

**Schema-purity:** the bundle's `plan.json` is the schema-pure plan; scenario-driving inputs (`gate_under_test`, `oracle_classes_used`, `oracle_context`, provenance) live in `fixture.json`, which the runner merges for evaluation but does not write into the evidence bundle's `plan.json` (see `fixtures/README.md`, `0005` §3.3).

---

## 5. Reproducibility requirements (P4)

A test is L3 only if a third party can rerun it and observe the same PASS/FAIL (`0003` §8). Preflight `PF-REP-*` verifies the reproducibility inputs are present and deterministic.

| Requirement | Check | Notes |
|---|---|---|
| Fixture hash deterministic and computable | `PF-REP-1` | `replay.fixture_hash` over the fixture dir (sorted walk, sha256) |
| Replay script present | `PF-REP-2` | `tests/l3_runner/replay.sh` (or per-scenario `replay.sh`) — the documented re-run command |
| Tooling determinism | `PF-REP-3` | verifier binary sha256 + schema sha256 set recorded (IO-3; `0003` §8.1) |
| No live-network dependency | `PF-REP-4` | all L3 scenarios must use **recorded response fixtures** (no live web search) or they are not reproducible (`0003` §8.1, U3) |

**What breaks reproducibility (and therefore L3):** an unanchored model verdict; an unknown environment variable; a DSH upgrade between run and rerun; clock drift large enough to flip an expiry check; a non-pinned dependency (`0003` §8.2). The `replay.json` (E11) records fixture hash, command line, verifier/schema sha256, and the DSH pin so an auditor can reproduce `verdict-match.json` byte-for-byte.

---

## 6. Preflight → evidence-bundle mapping

The preflight is the **gate before** the run; the evidence bundle is the **record after** the run. The tables below map each preflight check to the evidence-bundle field it protects.

| Preflight | Evidence field | Bundle item |
|---|---|---|
| `PF-UID-1` | `verifier_pid` | `verifier-independence.json` (IO-1) |
| `PF-UID-2` | `verifier_uid` | `verifier-independence.json` (IO-2) |
| `PF-UID-3` | `parent_session_id` | `verifier-independence.json` (IO-4) |
| `PF-VER-1` | clean-import guard | verifier process (code) |
| `PF-VER-2` | `gate_under_test` + reference file | `reference-verdict.json` (O1) |
| `PF-VER-3` | `verifier_binary_sha256` | `replay.json` (IO-3) |
| `PF-VER-5` | `oracle_classes_used` | `oracle-classes.json` (IO-6) |
| `PF-ENV-1` | `dsh_version` | `env.json` (LV5) |
| `PF-ENV-2` | `sandbox_mode`, `approval_policy` | `env.json` (G9) |
| `PF-PLAN-1..5` | plan fields + signoff ordering + signoff-field schema | `plan.json` (O4; LV6/7; G7) |
| `PF-REP-1..4` | fixture/replay metadata | `replay.json` (E11; LV14) |

---

## 7. What this specification does NOT do

- It does **not** run L3. `preflight.py` and `test_l3_preflight.py` are read-only; they never spawn a live DSH session and never execute a destructive/high-impact scenario.
- It does **not** change session policy. `PF-ENV-2` reports the baseline; it does not re-baseline (G9 remains a Human action, out of scope).
- It does **not** change DSH core, profiles, presets, or session policy (B4).
- It does **not** modify production control-plane code, any existing test file outside `tests/l3_runner/`, or any `tests/l3_reference/*` oracle/schema/fixture.
- It does **not** claim any control is L3. Zero controls are L3 today (`0006` §9).

---

## 8. Scope check

**In scope (written this session):**
- `docs/security/0007-l3-run-prerequisites.md` (this file)
- `tests/l3_runner/preflight.py` (new read-only preflight module, `PF-*` checks)
- `tests/l3_runner/test_l3_preflight.py` (new preflight test suite)
- `tests/l3_runner/__init__.py` (layout docstring) · `tests/l3_runner/__main__.py` (`preflight` subcommand + test-suite update)

**Not modified (verified):**
- Production control code: `control/*`, `orchestrator/*`, `state/helpers/*`, `audit/helpers/*`, `agents/*`, `config/*`, `schemas/*` — untouched.
- DSH core / profiles / presets / session policy — untouched.
- `tests/l3_reference/*` (oracles, schemas, fixtures) — untouched.
- Existing test files outside `tests/l3_runner/` — untouched.
- No L3 scenario executed; no session-policy change; no DSH change.

---

## 9. How to run the preflight (read-only)

```bash
# All checks, human-readable (direct module)
.venv-tests/bin/python -m tests.l3_runner.preflight \
    --scenario L3-TEST-001 --fixtures-root tests/l3_reference/fixtures

# Same via the package CLI subcommand (also available: rehearsal, validate, run)
.venv-tests/bin/python -m tests.l3_runner preflight \
    --scenario L3-TEST-001 --fixtures-root tests/l3_reference/fixtures

# JSON report (for tooling/audit)
.venv-tests/bin/python -m tests.l3_runner preflight \
    --scenario L3-TEST-001 --fixtures-root tests/l3_reference/fixtures --json

# Preflight test suite
.venv-tests/bin/python -m pytest tests/l3_runner/test_l3_preflight.py -q
```

Exit code: `0` when all required checks pass (rehearsal machinery OK — even if
`l3_claim_possible=False`); `2` when a required check fails (an L3 claim would
be invalid). When no orchestrator PID/UID is supplied, separation cannot be
proven, so `l3_claim_possible` stays `False` (honest default — never a claim
from unknown identity).

---

## 10. Honesty summary

The preflight is honest by construction:

1. `PF-UID-2` fails on a same-UID host, so `l3_claim_possible=False` and **no L3 claim is possible in this sandbox**.
2. `PF-ENV-2` reports the baseline but never modifies session policy.
3. `PF-PLAN-*` reject a post-hoc plan (signoff must precede the runtime verdict).
4. `PF-REP-*` reject a non-reproducible scenario (missing fixture hash / replay script / live-network dependency).

**Bottom line: the preflight is the run gate, not a promotion gate. It cannot make a control L3; it can only block a run whose prerequisites do not hold.**

---

*Status: specification. Run-prerequisites contract only. No L3 run executed. No session policy changed. No DSH core/profile/preset/session policy touched. No production control-plane code modified. No control claimed L3.*

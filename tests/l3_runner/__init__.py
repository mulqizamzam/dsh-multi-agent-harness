# tests/l3_runner — Independent L3 verification infrastructure (Phase 4 / Session B)
#
# PURPOSE
#   The L3 runner is the program that executes one L3 scenario with a fully
#   independent observer. It is NOT the orchestrator and NOT a DSH subagent.
#   It implements the runner contract of docs/design/0002 §13 and the evidence
#   bundle contract of docs/security/0005 §3.
#
# INDEPENDENCE (HARD REQUIREMENTS, enforced in code)
#   The verifier process:
#     - MUST NOT import any production gate under test
#       (no control.*, no orchestrator.foundation.gates, no audit/helpers,
#        no state/helpers) — it loads ONLY tests/l3_reference/* oracles;
#     - MUST NOT run as a DSH subagent (it is a standalone OS process started
#       by the runner's subprocess machinery, never via subagent tools);
#     - MUST NOT read the orchestrator's session log (it reads only on-disk
#       artifacts: state/registry, audit/, state/projects and the captured
#       action fixture);
#     - MUST NOT share the orchestrator's process (separate PID, separate UID
#       when the OS supports it);
#     - MUST NOT receive authority from the orchestrator (its verdict is
#       computed from the reference oracles + the Human-signed plan, before
#       reading the runtime verdict).
#
# SAFETY
#   This session implements the infrastructure and its tests. It does NOT run
#   any destructive / high-impact live L3 scenario. A Human-signed plan.json is
#   mandatory before any actual (non-recorded) L3 run; the runner refuses to
#   execute a live scenario without one.
#
# LAYOUT
#   runner.py            — scenario orchestration (P1 runtime + P4 replay)
#   collector.py         — evidence bundle collector (E1..E13)
#   verifier.py          — the independent verifier process (P2/P3 + verdict match)
#   independence.py      — IO-1..IO-10 independence checklist
#   replay.py            — reproducibility metadata (P4)
#   validator.py         — structure-only evidence bundle validator (LV1..LV20)
#   preflight.py         — run-prerequisites preflight (separate UID/process need,
#                          verifier prerequisites, environment preflight,
#                          Human-signed plan prerequisites incl. PF-PLAN-5,
#                          reproducibility) — read-only, never runs L3 (0007)
#   uid_readiness.py     — G6: separate-process/separate-UID readiness (honest
#                          IO-2 detection + separate-UID launch requirements)
#   plan_signing.py      — G7: Human-signed plan prerequisites (signoff-field
#                          schema validation, pre-runtime ordering, signing
#                          checklist + signing-request template)
#   rehearsal.py         — G8: end-to-end replay/inert rehearsal driver
#                          (runner -> verifier -> collector -> validator -> replay)
#   runtime_driver.py    — safe recorded runtime driver + live-driver seam
#   test_l3_infrastructure.py — pytest coverage of the whole infrastructure
#   test_l3_preflight.py      — pytest coverage of the preflight checks
#   test_l3_uid_readiness.py  — G6 readiness tests
#   test_l3_plan_signing.py   — G7 signed-plan tests
#   test_l3_rehearsal.py      — G8 end-to-end rehearsal tests

DSH_VERSION_PIN = "0.1.1-rc.2"
ORACLE_CLASSES = ("O1", "O2", "O3", "O4")

# Every bundle must contain these files (excluding manifest.json itself, which
# certifies the others and cannot self-reference). Order is canonical.
EVIDENCE_FILES = (
    "env.json",
    "plan.json",
    "before.sha256",
    "after.sha256",
    "runtime-verdict.json",
    "audit-log.jsonl",
    "reference-verdict.json",
    "oracle-classes.json",
    "provenance.json",
    "replay.json",
    "verifier-independence.json",
    "verdict-match.json",
)

# Reference oracle modules by gate (O1). The verifier maps a gate_under_test
# name to its independent reference implementation here. Each module must
# expose an `oracle_<gate>(context) -> dict` entrypoint.
ORACLE_MODULES = {
    "authority": "tests.l3_reference.authority_gate",
    "execution_gate": "tests.l3_reference.execution_gate",
    "delegation": "tests.l3_reference.delegation_gate",
    "role_isolation": "tests.l3_reference.role_gate",
    "recovery": "tests.l3_reference.recovery_gate",
    "verification": "tests.l3_reference.verification_gate",
    "state_transition": "tests.l3_reference.transition_gate",
    "audit_integrity": "tests.l3_reference.audit_chain",
}

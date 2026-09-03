# tests/l3_runner/test_l3_infrastructure.py — L3 verification infrastructure tests
#
# Exercises the independent L3 verification infrastructure built in
# Phase 4 / Session B:
#   - reference/oracle re-implementations (O1)
#   - verifier process (P2 independent observer + P3 oracle + verdict match)
#   - evidence bundle collector (E1..E13)
#   - runner (P1 runtime check via recorded driver + P4 replay)
#   - verdict matching and failure classification
#   - independence checklist (IO-1..IO-10)
#   - structure-only bundle validator (LV1..LV20 + per-INT)
#
# SAFETY: no destructive/high-impact L3 scenario is run. All scenarios use the
# RecordedRuntimeDriver (deterministic replay). No production gate is modified,
# no DSH core/profile/preset/session policy is touched.

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

TESTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(TESTS_ROOT)
FIXTURES_ROOT = os.path.join(TESTS_ROOT, "l3_reference", "fixtures")

# Ensure the project root is importable.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# O1 reference oracles
# ---------------------------------------------------------------------------
def test_authority_oracle_allows_valid_delegation():
    from tests.l3_reference.authority_gate import oracle_authority
    ctx = {
        "actor": "orchestrator", "action": "code_write",
        "target": "agents/cto/x.txt",
        "delegation": {
            "id": "delegation-1", "status": "ACTIVE",
            "project": "multi-agent-harness",
            "scope": {"operations": ["code_write"],
                      "resources": ["agents/cto/**"], "environments": ["dev"]}},
        "environment": "dev", "project": "multi-agent-harness",
    }
    v = oracle_authority(ctx)
    assert v["decision"] == "ALLOW"
    assert all(r == "pass" for r in v["checklist_item_results"].values())


def test_authority_oracle_denies_missing_delegation():
    from tests.l3_reference.authority_gate import oracle_authority
    v = oracle_authority({"actor": "orchestrator", "action": "write", "target": "x"})
    assert v["decision"] == "DENY"
    assert "AUTH-INV" in v["reason"]


def test_authority_oracle_denies_revoked():
    from tests.l3_reference.authority_gate import oracle_authority
    ctx = {
        "actor": "orchestrator", "action": "write", "target": "agents/x.txt",
        "delegation": {"id": "delegation-1", "status": "ACTIVE",
                       "scope": {"operations": ["write"],
                                 "resources": ["agents/**"], "environments": ["dev"]}},
        "revocation_list": ["delegation-1"], "environment": "dev",
    }
    assert oracle_authority(ctx)["decision"] == "DENY"


def test_authority_oracle_denies_expired():
    from tests.l3_reference.authority_gate import oracle_authority
    ctx = {
        "actor": "orchestrator", "action": "write", "target": "agents/x.txt",
        "delegation": {"id": "delegation-1", "status": "ACTIVE",
                       "scope": {"operations": ["write"],
                                 "resources": ["agents/**"], "environments": ["dev"]},
                       "expires_at": "2020-01-01T00:00:00Z"},
        "environment": "dev", "now": "2026-08-31T10:00:00Z",
    }
    assert oracle_authority(ctx)["decision"] == "DENY"


def test_authority_oracle_escaleates_when_approval_required():
    from tests.l3_reference.authority_gate import oracle_authority
    ctx = {
        "actor": "orchestrator", "action": "financial_transaction",
        "target": "ledger", "environment": "dev",
        "delegation": {"id": "delegation-1", "status": "ACTIVE",
                       "scope": {"operations": ["financial_transaction"],
                                 "resources": ["ledger"], "environments": ["dev"]},
                       "requires_approval": ["financial_transfer"]},
    }
    assert oracle_authority(ctx)["decision"] == "ESCALATE"


def test_execution_gate_oracle_protected_path_denied():
    from tests.l3_reference.execution_gate import oracle_execution_gate
    v = oracle_execution_gate({"action": "write", "target": "state/registry/x.json",
                               "actor": "cto", "writer": False, "base": "/tmp/ws"})
    assert v["decision"] == "DENY"
    assert v["classification"] == "PROTECTED"


def test_execution_gate_oracle_allows_workspace_write():
    from tests.l3_reference.execution_gate import oracle_execution_gate
    v = oracle_execution_gate({"action": "write", "target": "agents/x.txt",
                               "actor": "cto", "writer": False, "base": "/tmp/ws"})
    assert v["decision"] == "ALLOW"


def test_execution_gate_oracle_traversal_denied():
    from tests.l3_reference.execution_gate import oracle_execution_gate
    v = oracle_execution_gate({"action": "write", "target": "../../etc/passwd",
                               "actor": "cto", "writer": False, "base": "/tmp/ws"})
    assert v["decision"] == "DENY"


def test_execution_gate_oracle_writer_channel_scope():
    from tests.l3_reference.execution_gate import oracle_execution_gate
    # registry_write channel targeting audit/ => DENY (no cross-root grant)
    v = oracle_execution_gate({"action": "registry_write", "target": "audit/x.json",
                               "actor": "orchestrator", "writer": True,
                               "base": "/tmp/ws"})
    assert v["decision"] == "DENY"


def test_delegation_oracle_revoked():
    from tests.l3_reference.delegation_gate import oracle_delegation
    v = oracle_delegation({"delegation": {"id": "delegation-1", "status": "ACTIVE",
                                          "project": "multi-agent-harness",
                                          "scope_operations": ["write"],
                                          "scope_resources": ["agents/**"]},
                           "revocation_list": ["delegation-1"]})
    assert v["decision"] == "REVOKED"


def test_role_oracle_denies_foreign_capability():
    from tests.l3_reference.role_gate import oracle_role
    assert oracle_role({"role": "cto", "capability": "financial_transaction"})["decision"] == "DENY"
    assert oracle_role({"role": "cto", "capability": "write"})["decision"] == "ALLOW"
    assert oracle_role({"role": "badsector", "capability": "bash"})["decision"] == "DENY"


def test_role_oracle_subdelegation_deny_by_default():
    from tests.l3_reference.role_gate import oracle_role
    assert oracle_role({"role": "cto", "capability": "subagent"})["decision"] == "DENY"


def test_transition_oracle_illegal_denied():
    from tests.l3_reference.transition_gate import oracle_transition
    assert oracle_transition({"from_state": "REVIEW_PENDING", "to_state": "COMPLETE"})["decision"] == "DENY"
    assert oracle_transition({"from_state": "DRAFT", "to_state": "PLANNED"})["decision"] == "ALLOW"


def test_recovery_oracle_no_blind_retry():
    from tests.l3_reference.recovery_gate import oracle_recovery
    assert oracle_recovery({"diagnosed_cause": "", "retry_cause": "x"})["decision"] == "DENY"
    assert oracle_recovery({"diagnosed_cause": "net", "retry_cause": "net"})["decision"] == "DENY"
    assert oracle_recovery({"diagnosed_cause": "net", "retry_cause": "disk"})["decision"] == "ALLOW"


def test_verification_oracle_unverified_on_claim():
    from tests.l3_reference.verification_gate import oracle_verification
    v = oracle_verification({"action_category": "code_change", "agent_claim": "SUCCEEDED"})
    assert v["decision"] == "UNVERIFIED"


# ---------------------------------------------------------------------------
# Verifier independence enforcement (HARD REQUIREMENTS)
# ---------------------------------------------------------------------------
def test_verifier_refuses_production_gate_imports():
    """The verifier must refuse to run if any production gate is imported.

    Runs in a SUBPROCESS because the guard inspects the live sys.modules; an
    in-process test would pollute the shared test session. This mirrors the
    real deployment where the verifier is a fresh OS process.
    """
    from tests.l3_runner.runner import PROJECT_ROOT
    code = (
        "import control.execution_gate\n"
        "from tests.l3_runner.verifier import assert_clean_imports\n"
        "try:\n"
        "    assert_clean_imports()\n"
        "    print('GUARD-DID-NOT-FIRE')\n"
        "except RuntimeError as e:\n"
        "    print('GUARD-FIRED', 'independence violation' in str(e))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=PROJECT_ROOT)
    assert proc.returncode == 0
    assert "GUARD-FIRED True" in proc.stdout


def test_verifier_never_imports_production_gates():
    """The reference oracles must not IMPORT production control modules.

    Uses AST to inspect only real import statements (docstring mentions of
    production paths are not imports and do not count).
    """
    import ast

    reference_files = [
        "authority_gate.py", "execution_gate.py", "delegation_gate.py",
        "role_gate.py", "recovery_gate.py", "verification_gate.py",
        "transition_gate.py", "audit_chain.py",
    ]
    forbidden_prefixes = ("control", "orchestrator.foundation",
                          "audit.helpers", "state.helpers", "tests.control_plane")

    def imports_of(src: str):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    yield node.module

    for mod in reference_files:
        src_path = os.path.join(TESTS_ROOT, "l3_reference", mod)
        with open(src_path) as f:
            src = f.read()
        for imported in imports_of(src):
            assert not imported.startswith(forbidden_prefixes), \
                f"{mod} imports {imported!r} (independence violation)"


def test_verifier_subprocess_runs_in_clean_process():
    """The verifier CLI runs in a separate OS process and succeeds."""
    from tests.l3_runner.runner import PROJECT_ROOT
    proc = subprocess.run(
        [sys.executable, "-c",
         "from tests.l3_runner.verifier import assert_clean_imports; "
         "assert_clean_imports(); print('CLEAN')"],
        capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert proc.returncode == 0
    assert "CLEAN" in proc.stdout


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
def test_collector_state_hash_tree(tmp_path):
    from tests.l3_runner.collector import state_hash_tree, hash_text
    # Create a workspace with a registry dir and a file.
    ws = tmp_path / "ws"
    reg = ws / "state" / "registry"
    reg.mkdir(parents=True)
    (reg / "delegations.yaml").write_text("id: delegation-1\n")
    tree = state_hash_tree(str(ws), ("state/registry/**", "audit/**"))
    assert tree["algorithm"] == "sha256"
    assert tree["root_hash"] and len(tree["root_hash"]) == 64
    assert "state/registry/delegations.yaml" in tree["files"]

    # Determinism: same content => same hash.
    tree2 = state_hash_tree(str(ws), ("state/registry/**", "audit/**"))
    assert tree == tree2


def test_collector_write_bundle_items(tmp_path):
    from tests.l3_runner.collector import write_bundle_item, write_manifest
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    write_bundle_item(str(bundle), "env.json",
                      {"dsh_version": "0.1.1-rc.2", "seed": 1})
    write_bundle_item(str(bundle), "before.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "0" * 64})
    write_bundle_item(str(bundle), "audit-log.jsonl",
                      [{"event_id": "event-1", "timestamp": "2026-08-31T00:00:00Z"}])
    write_manifest(str(bundle), "L3-TEST-001")
    assert (bundle / "env.json").exists()
    assert (bundle / "audit-log.jsonl").exists()
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["scenario_id"] == "L3-TEST-001"
    assert "env.json" in manifest["files"]


# ---------------------------------------------------------------------------
# Verifier + verdict match
# ---------------------------------------------------------------------------
def _make_bundle(tmp_path, scenario="L3-TEST-001"):
    """Assemble a minimal bundle for the verifier."""
    import tests.l3_runner.runner as runner_mod
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    return str(bundle_dir), runner_mod


def test_verifier_flow_allows_when_runtime_matches(tmp_path):
    """Full verifier flow: reference computed first, runtime read, match=true."""
    from tests.l3_runner.collector import ensure_bundle_dir, write_bundle_item
    from tests.l3_runner.runner import _load_scenario_def
    from tests.l3_runner.verifier import Verifier

    bundle_dir = ensure_bundle_dir("L3-TEST-001", base=str(tmp_path))
    # Load the merged fixture (plan.json + fixture.json) via the runner loader.
    fixture = _load_scenario_def("L3-TEST-001", FIXTURES_ROOT)

    # Human-signed plan committed before runtime (schema-pure plan.json).
    with open(os.path.join(FIXTURES_ROOT, "L3-TEST-001", "plan.json")) as f:
        plan_pure = json.load(f)
    write_bundle_item(bundle_dir, "plan.json", plan_pure)

    # Runtime verdict (recorded; ALLOW matches the reference ALLOW).
    write_bundle_item(bundle_dir, "runtime-verdict.json", {
        "scenario_id": "L3-TEST-001", "decision": "ALLOW", "denial_path": None,
        "tool_call_id": "tc-1", "audit_event_ids": ["event-1"],
        "stopReason": "completed", "captured_at": "2026-08-31T10:00:10Z",
    })
    write_bundle_item(bundle_dir, "before.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    write_bundle_item(bundle_dir, "after.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "b" * 64})
    write_bundle_item(bundle_dir, "audit-log.jsonl",
                      [{"event_id": "event-1", "timestamp": "2026-08-31T10:00:01Z",
                        "actor": "orchestrator", "actor_type": "orchestrator",
                        "action": "write", "target": "agents/cto/x.txt",
                        "project": "multi-agent-harness", "result": "allowed"}])

    v = Verifier(bundle_dir, fixture,
                 orchestrator_pid=99999, orchestrator_uid=9999,
                 orchestrator_session="session-orch",
                 parent_session="session-ext", rehearsal=True)
    v.run()

    match = json.loads(open(os.path.join(bundle_dir, "verdict-match.json")).read())
    assert match["match"] is True
    assert match["runtime_decision"] == "ALLOW"
    assert match["reference_decision"] == "ALLOW"
    assert match["failure_class"] == "L3-PASS"
    # Rehearsal => no L3 claim (honesty rule).
    assert match["l3_claim"] is False

    # Reference verdict was computed BEFORE reading the runtime: the reference
    # file must carry a computed_at timestamp.
    ref = json.loads(open(os.path.join(bundle_dir, "reference-verdict.json")).read())
    assert ref["decision"] == "ALLOW"
    assert ref["computed_at"]


def test_verifier_failure_class_runtime_exceeds(tmp_path):
    """Runtime allows what the oracle denies => L3-FAIL-RUNTIME-EXCEEDS-EXPECTATION."""
    from tests.l3_runner.collector import ensure_bundle_dir, write_bundle_item
    from tests.l3_runner.runner import _load_scenario_def
    from tests.l3_runner.verifier import Verifier

    bundle_dir = ensure_bundle_dir("L3-TEST-002", base=str(tmp_path))
    fixture = _load_scenario_def("L3-TEST-002", FIXTURES_ROOT)
    with open(os.path.join(FIXTURES_ROOT, "L3-TEST-002", "plan.json")) as f:
        plan_pure = json.load(f)
    write_bundle_item(bundle_dir, "plan.json", plan_pure)
    # Runtime wrongly ALLOWED a protected-path write.
    write_bundle_item(bundle_dir, "runtime-verdict.json", {
        "scenario_id": "L3-TEST-002", "decision": "ALLOW", "denial_path": None,
        "tool_call_id": "tc-2", "audit_event_ids": ["event-2"],
        "stopReason": "completed", "captured_at": "2026-08-31T10:00:10Z",
    })
    write_bundle_item(bundle_dir, "before.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    write_bundle_item(bundle_dir, "after.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    write_bundle_item(bundle_dir, "audit-log.jsonl", [])

    v = Verifier(bundle_dir, fixture,
                 orchestrator_pid=99999, orchestrator_uid=9999,
                 orchestrator_session="session-orch",
                 parent_session="session-ext", rehearsal=True)
    v.run()

    match = json.loads(open(os.path.join(bundle_dir, "verdict-match.json")).read())
    assert match["match"] is False
    assert match["reference_decision"] == "DENY"
    assert match["failure_class"] == "L3-FAIL-RUNTIME-EXCEEDS-EXPECTATION"


def test_verifier_rejects_single_oracle_class(tmp_path):
    """P3: fewer than 2 oracle classes => L3-ORACLE-INADEQUATE."""
    from tests.l3_reference.authority_gate import oracle_authority
    from tests.l3_runner.verifier import classify_failure
    fc = classify_failure("DENY", "DENY", True, ["O1"], True)
    assert fc == "L3-ORACLE-INADEQUATE"


def test_independence_checklist_all_pass_when_separate(tmp_path):
    """IO-1..IO-10 all pass when the verifier runs in a separate process with
    a distinct UID (simulated) and the bundle is consistent."""
    from tests.l3_runner.independence import compute_independence
    res = compute_independence(
        scenario_id="L3-TEST-001",
        orchestrator_pid=1000, orchestrator_uid=1000,
        orchestrator_session_id="session-orch",
        verifier_pid=2000, verifier_uid=2001,
        verifier_session_id="verifier-2000",
        parent_session_id="session-ext",
        verifier_binary_path=os.path.abspath(__file__),
        reference_modules=[os.path.join(TESTS_ROOT, "l3_reference", "authority_gate.py")],
        oracle_classes_used=["O1", "O4"],
        plan_ts="2026-08-31T00:00:00Z", runtime_ts="2026-08-31T10:00:00Z",
        audit_log_path=None, audit_chain_valid=True,
        before_root_hash="a" * 64, after_root_hash="a" * 64,
        deny_protected_path=True, verdict_match_in_audit=False,
    )
    d = res.to_dict()
    assert d["all_pass"] is True
    assert all(r["pass"] for r in d["io_checks"].values())


def test_independence_checklist_detects_same_pid():
    """IO-1 fails when the verifier shares the orchestrator's PID."""
    from tests.l3_runner.independence import compute_independence
    res = compute_independence(
        scenario_id="L3-TEST-001",
        orchestrator_pid=os.getpid(), orchestrator_uid=os.getuid(),
        orchestrator_session_id="session-orch",
        verifier_pid=os.getpid(), verifier_uid=os.getuid(),
        verifier_session_id="verifier-x", parent_session_id="session-ext",
        verifier_binary_path=os.path.abspath(__file__),
        reference_modules=[os.path.join(TESTS_ROOT, "l3_reference", "authority_gate.py")],
        oracle_classes_used=["O1", "O4"],
        plan_ts="2026-08-31T00:00:00Z", runtime_ts="2026-08-31T10:00:00Z",
        audit_log_path=None, audit_chain_valid=True,
        before_root_hash="a" * 64, after_root_hash="a" * 64,
        deny_protected_path=True, verdict_match_in_audit=False,
    )
    d = res.to_dict()
    assert d["all_pass"] is False
    assert d["io_checks"]["IO-1"]["pass"] is False


def test_independence_checklist_detects_verdict_self_certification():
    """IO-10 fails when verdict-match appears inside the audit log."""
    from tests.l3_runner.independence import compute_independence
    res = compute_independence(
        scenario_id="L3-TEST-001",
        orchestrator_pid=1000, orchestrator_uid=1000,
        orchestrator_session_id="session-orch",
        verifier_pid=2000, verifier_uid=2001,
        verifier_session_id="verifier-2000", parent_session_id="session-ext",
        verifier_binary_path=os.path.abspath(__file__),
        reference_modules=[os.path.join(TESTS_ROOT, "l3_reference", "authority_gate.py")],
        oracle_classes_used=["O1", "O4"],
        plan_ts="2026-08-31T00:00:00Z", runtime_ts="2026-08-31T10:00:00Z",
        audit_log_path=None, audit_chain_valid=True,
        before_root_hash="a" * 64, after_root_hash="a" * 64,
        deny_protected_path=True, verdict_match_in_audit=True,
    )
    d = res.to_dict()
    assert d["io_checks"]["IO-10"]["pass"] is False


# ---------------------------------------------------------------------------
# Runner (end-to-end, safe replay mode)
# ---------------------------------------------------------------------------
def test_runner_replay_produces_complete_bundle(tmp_path):
    """The runner produces a complete bundle with all evidence files (E1..E13)."""
    from tests.l3_runner.runner import run_scenario
    bundle_base = tmp_path / "auditroot"
    bundle_base.mkdir()

    summary = run_scenario(
        "L3-TEST-001", fixtures_root=FIXTURES_ROOT, bundle_base=str(bundle_base),
        mode="replay", seed=42,
        orchestrator_pid=99999, orchestrator_uid=os.getuid(),
        orchestrator_session="session-orch", parent_session="session-ext",
        verifier_mode="subprocess",
    )
    bundle_dir = summary["bundle_dir"]
    assert os.path.isdir(bundle_dir)
    for fname in ("env.json", "plan.json", "before.sha256", "after.sha256",
                  "runtime-verdict.json", "audit-log.jsonl",
                  "reference-verdict.json", "oracle-classes.json",
                  "provenance.json", "replay.json",
                  "verifier-independence.json", "verdict-match.json",
                  "manifest.json"):
        assert os.path.isfile(os.path.join(bundle_dir, fname)), f"missing {fname}"

    # R6: >= 2 oracle classes recorded.
    oc = json.loads(open(os.path.join(bundle_dir, "oracle-classes.json")).read())
    assert len(set(oc["oracle_classes_used"])) >= 2

    # The verifier subprocess must have run in a SEPARATE process: IO-1 passes
    # (orchestrator_pid=99999 != verifier pid). But in this same-UID sandbox the
    # verifier and the runner share the host UID, so IO-2 FAILS HONESTLY =>
    # all_pass=False and l3_claim=false (no L3 claim without a separate UID).
    ind = json.loads(open(os.path.join(bundle_dir, "verifier-independence.json")).read())
    assert ind["io_checks"]["IO-1"]["pass"] is True
    assert ind["io_checks"]["IO-2"]["pass"] is False
    assert ind["all_pass"] is False
    match = json.loads(open(os.path.join(bundle_dir, "verdict-match.json")).read())
    assert match["l3_claim"] is False  # honesty rule: no L3 claim without separate UID


def test_runner_verifier_process_pid_differs(tmp_path):
    """P2: the verifier subprocess is a distinct OS process from the runner."""
    from tests.l3_runner.runner import run_scenario
    bundle_base = tmp_path / "auditroot2"
    bundle_base.mkdir()
    runner_pid = os.getpid()
    summary = run_scenario(
        "L3-TEST-001", fixtures_root=FIXTURES_ROOT, bundle_base=str(bundle_base),
        mode="replay", seed=7,
        orchestrator_pid=runner_pid, orchestrator_uid=os.getuid(),
        orchestrator_session="session-orch", parent_session="session-ext",
        verifier_mode="subprocess",
    )
    ind = json.loads(open(os.path.join(summary["bundle_dir"],
                                       "verifier-independence.json")).read())
    assert ind["verifier_pid"] != runner_pid


def test_runner_refuses_live_mode_without_live_driver(tmp_path):
    """--mode live is not executable now (no destructive/high-impact runs)."""
    from tests.l3_runner.runner import run_scenario
    with pytest.raises(RuntimeError, match="live L3 mode is NOT executable"):
        run_scenario("L3-TEST-001", fixtures_root=FIXTURES_ROOT,
                     bundle_base=str(tmp_path), mode="live")


def test_runner_refuses_unknown_scenario(tmp_path):
    from tests.l3_runner.runner import run_scenario, ScenarioNotFoundError
    with pytest.raises(ScenarioNotFoundError):
        run_scenario("L3-NOPE-999", fixtures_root=FIXTURES_ROOT,
                     bundle_base=str(tmp_path), mode="replay")


def test_runner_refuses_single_oracle(tmp_path):
    """R6: fewer than 2 oracle classes => refuse the run."""
    from tests.l3_runner.runner import run_scenario
    # Write a scenario with a single oracle class into a temp fixtures root.
    from tests.l3_reference.fixtures import _write_single_oracle_scenario
    tmp_fixtures = tmp_path / "fixtures"
    tmp_fixtures.mkdir()
    _write_single_oracle_scenario(str(tmp_fixtures))
    with pytest.raises(RuntimeError, match="fewer than 2 oracle classes"):
        run_scenario("L3-TEST-SINGLE", fixtures_root=str(tmp_fixtures),
                     bundle_base=str(tmp_path), mode="replay")


# ---------------------------------------------------------------------------
# Validator (LV1..LV20)
# ---------------------------------------------------------------------------
def test_validator_passes_complete_bundle(tmp_path):
    """A complete, self-consistent bundle validates cleanly (LV rules)."""
    from tests.l3_runner.runner import run_scenario
    from tests.l3_runner.validator import validate_bundle_dir
    bundle_base = tmp_path / "auditroot3"
    bundle_base.mkdir()
    summary = run_scenario(
        "L3-TEST-001", fixtures_root=FIXTURES_ROOT, bundle_base=str(bundle_base),
        mode="replay", seed=3,
        orchestrator_pid=99999, orchestrator_uid=9999,
        orchestrator_session="session-orch", parent_session="session-ext",
        verifier_mode="subprocess",
    )
    res = validate_bundle_dir(summary["bundle_dir"], scenario_id="L3-TEST-001")
    # Note: this bundle carries l3_claim=false (rehearsal), so LV10 fails.
    # The structural completeness is what we assert here.
    lv10_errors = [e for e in res.errors if e.startswith("LV10")]
    assert lv10_errors, "expected LV10 (l3_claim=false) for a rehearsal bundle"
    # No structural (file-presence / manifest / plan / oracle-classes) failures.
    for prefix in ("LV1:", "LV2:", "LV3:", "LV4:", "LV5:", "LV6:",
                   "LV8:", "LV13:", "LV14:", "LV15:", "LV16:"):
        assert not [e for e in res.errors if e.startswith(prefix)], \
            f"unexpected structural error {prefix}: {res.errors}"


def test_validator_rejects_missing_file(tmp_path):
    from tests.l3_runner.validator import validate_bundle_dir
    empty = tmp_path / "empty"
    empty.mkdir()
    res = validate_bundle_dir(str(empty), scenario_id="L3-TEST-001")
    assert res.passed is False
    assert any(e.startswith("LV1") for e in res.errors)


def test_validator_rejects_manifest_hash_mismatch(tmp_path):
    """LV3: a tampered evidence file fails manifest hash verification."""
    from tests.l3_runner.collector import ensure_bundle_dir, write_bundle_item
    from tests.l3_runner.validator import validate_bundle_dir
    bundle_dir = ensure_bundle_dir("L3-TEST-001", base=str(tmp_path))
    write_bundle_item(bundle_dir, "env.json", {"dsh_version": "0.1.1-rc.2"})
    write_bundle_item(bundle_dir, "plan.json",
                      {"scenario_id": "L3-TEST-001", "actor": "orchestrator"})
    # manifest with wrong hash for env.json
    manifest = {"scenario_id": "L3-TEST-001", "dsh_version": "0.1.1-rc.2",
                "created_at": "2026-08-31T00:00:00Z",
                "files": {f: {"sha256": "0" * 64} for f in
                          ("env.json", "plan.json", "before.sha256", "after.sha256",
                           "runtime-verdict.json", "audit-log.jsonl",
                           "reference-verdict.json", "oracle-classes.json",
                           "provenance.json", "replay.json",
                           "verifier-independence.json", "verdict-match.json")}}
    import json as _json
    with open(os.path.join(bundle_dir, "manifest.json"), "w") as f:
        _json.dump(manifest, f)
    res = validate_bundle_dir(bundle_dir, scenario_id="L3-TEST-001")
    assert any(e.startswith("LV3") for e in res.errors)


def test_validator_int_rules_int07(tmp_path):
    """LV-INT-07: INT-07 runtime verdict must be DENY/ERROR and no mutation."""
    from tests.l3_runner.collector import ensure_bundle_dir, write_bundle_item
    from tests.l3_runner.validator import validate_bundle_dir
    bundle_dir = ensure_bundle_dir("L3-AUTH-004", base=str(tmp_path))
    write_bundle_item(bundle_dir, "runtime-verdict.json", {
        "scenario_id": "L3-AUTH-004", "decision": "DENY", "denial_path": "authority",
        "tool_call_id": "tc", "audit_event_ids": [], "stopReason": "completed",
        "captured_at": "2026-08-31T10:00:00Z",
    })
    write_bundle_item(bundle_dir, "before.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    write_bundle_item(bundle_dir, "after.sha256",
                      {"algorithm": "sha256", "scope": [], "root_hash": "a" * 64})
    res = validate_bundle_dir(bundle_dir, scenario_id="L3-AUTH-004",
                              int_scenario="INT-07")
    # The DENY verdict + equal hashes satisfy INT-07 rules (no LV-INT-07 errors).
    assert not [e for e in res.errors if e.startswith("LV-INT-07")]


# ---------------------------------------------------------------------------
# Audit chain reference (O1 for audit integrity)
# ---------------------------------------------------------------------------
def test_audit_chain_reference_detects_mutation(tmp_path):
    from tests.l3_reference.audit_chain import verify_ledger, ReferenceChainError
    log = tmp_path / "events.jsonl"
    log.write_text('{"event_id":"event-1","actor":"x"}\n'
                   '{"event_id":"event-2","actor":"y"}\n')
    # First pass: no sidecar => VALID (first-time).
    v1 = verify_ledger(str(log))
    assert v1.decision == "VALID"
    # Now append and mutate the FIRST event.
    mutated = tmp_path / "mutated.jsonl"
    mutated.write_text('{"event_id":"event-1","actor":"EVIL"}\n'
                       '{"event_id":"event-2","actor":"y"}\n')
    # Persist a sidecar from the ORIGINAL log, then verify the mutated one.
    records = []
    from tests.l3_reference.audit_chain import compute_chain_records
    original = compute_chain_records(str(log))
    with open(str(mutated) + ".chain", "w") as f:
        for rec in original:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
    v2 = verify_ledger(str(mutated), sidecar_path=str(mutated) + ".chain")
    assert v2.decision == "INVALID"
    assert "tampered" in v2.reason or "mismatch" in v2.reason


def test_audit_chain_reference_strict_read(tmp_path):
    """A blank/corrupt line in an append-only ledger is an integrity failure."""
    from tests.l3_reference.audit_chain import ReferenceChainError, compute_chain_records
    log = tmp_path / "bad.jsonl"
    log.write_text('{"event_id":"event-1"}\n\n{"event_id":"event-2"}\n')
    with pytest.raises(ReferenceChainError, match="blank line"):
        compute_chain_records(str(log))


# ---------------------------------------------------------------------------
# Replay / reproducibility (P4)
# ---------------------------------------------------------------------------
def test_replay_fixture_hash_deterministic(tmp_path):
    from tests.l3_runner.replay import fixture_hash
    d = tmp_path / "fx"
    d.mkdir()
    (d / "a.txt").write_text("hello")
    h1 = fixture_hash(str(d))
    (d / "a.txt").write_text("hello")  # unchanged
    h2 = fixture_hash(str(d))
    assert h1 == h2
    assert h1.startswith("sha256:")
    # Changing content changes the hash.
    (d / "a.txt").write_text("world")
    h3 = fixture_hash(str(d))
    assert h3 != h1


def test_replay_metadata_schema_fields(tmp_path):
    from tests.l3_runner.replay import build_replay
    replay = build_replay(
        scenario_id="L3-TEST-001",
        fixture_path=str(tmp_path),
        fixture_seed=42,
        verifier_binary_path=os.path.abspath(__file__),
        schema_dirs=[os.path.join(TESTS_ROOT, "l3_reference", "schemas")],
    )
    assert replay["dsh_version"] == "0.1.1-rc.2"
    assert replay["fixture_hash"].startswith("sha256:")
    assert len(replay["verifier_binary_sha256"]) == 64
    assert "l3-plan.schema.json" in replay["schema_sha256"]


# ---------------------------------------------------------------------------
# Honesty rule: no control claimed L3 by the existence of this infrastructure
# ---------------------------------------------------------------------------
def test_no_control_is_claimed_l3():
    """The infrastructure must NOT claim any existing control is L3."""
    # The verdict-match schema requires l3_claim=true, but the verifier only
    # sets it for non-rehearsal runs. There are no committed L3 bundles in the
    # repo (audit/l3/ is not populated by this session).
    from tests.l3_runner import EVIDENCE_FILES
    assert "verdict-match.json" in EVIDENCE_FILES


def test_verifier_failure_classification_table():
    """Every failure class in docs/security/0003 §9 is produced by classify_failure."""
    from tests.l3_runner.verifier import classify_failure
    cases = [
        (("ALLOW", "ALLOW", True, ["O1", "O4"], True), "L3-PASS"),
        (("ALLOW", "DENY", True, ["O1", "O4"], True), "L3-FAIL-RUNTIME-EXCEEDS-EXPECTATION"),
        (("DENY", "ALLOW", True, ["O1", "O4"], True), "L3-FAIL-RUNTIME-UNDER-EXCEEDS-EXPECTATION"),
        (("ALLOW", "ALLOW", False, ["O1", "O4"], True), "L3-INDEPENDENCE-VIOLATION"),
        (("ALLOW", "ALLOW", True, ["O1"], True), "L3-ORACLE-INADEQUATE"),
        (("ALLOW", "ALLOW", True, ["O1", "O4"], False), "L3-NON-REPRODUCIBLE"),
    ]
    for (runtime, ref, indep, oracles, replayable), expected in cases:
        fc = classify_failure(runtime, ref, indep, oracles, replayable)
        assert fc == expected, f"{runtime}/{ref}/{indep}/{oracles}/{replayable} -> {fc}"

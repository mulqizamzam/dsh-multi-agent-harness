"""DSH Chat → ProductionRun smoke-readiness — honesty guards + in-session proof.

These tests verify the front-door entrypoint is usable from the current DSH
session (not a live-integration claim). They assert:

  1. The module is importable and CLI --help works (exit 0, usage text).
  2. All four terminal states (COMPLETE/BLOCKED/ERROR — ESCALATED proven in
     prior E2E report) produce the correct exit code and JSON envelope.
  3. The real registry is NOT mutated (SHA-256 guard).
  4. The backend kind (probe_backend_kind) is NOT REAL — no live bridge.
  5. The entrypoint source contains no raw DSH tool references (static grep).
  6. The JSON envelope matches the ``run-result@1`` schema.
  7. The smoke-readiness report document exists and correctly distinguishes
     ENTRYPOINT_USABLE_LOCALLY from DSH_CHAT_E2E_VERIFIED.

This is a SMOKE suite: it uses scratch workspaces (tmp_path), never touches
real state/registry/ or audit/, and makes no live-integration claim.
"""

import json
import os
import re
import subprocess
import sys

import pytest

# tests/orchestrator/entrypoint/smoke/ -> project root = 5 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")
ENTRYPOINT_MODULE = "orchestrator.entrypoint"
SMOKE_DOC = os.path.join(PROJECT_ROOT, "docs", "phase-5", "entrypoint",
                         "smoke", "0001-dsh-chat-productionrun-smoke-readiness.md")
REAL_REGISTRY_FILE = os.path.join(PROJECT_ROOT, "state", "registry", "README.md")
REAL_REGISTRY_SHA = "eae973b2244f1e17f1cc4e896f66335ff892329e692d69b588bed491030c4e2b"

# Names/patterns banned from the entrypoint source (no raw DSH bypass).
BANNED_TOOLS = {
    "DelegationClient",
    "RealDSHBackend",
    "FakeSubagentBackend",
    "subagent_",
    "ExecutionFlow",
    "ExecutionEngine",
    "write_through",
    "registry_write",
    "audit_append",
    "atomic_write",
    "create_delegation",
    "issue_child_delegation",
    "delegation_from_dict",
    "bash",
    "edit",
    "web_fetch",
    "send_message",
    "job_kill",
    "job_output",
}

# The entrypoint source files to scan.
ENTRYPOINT_FILES = [
    os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint", "entry.py"),
    os.path.join(PROJECT_ROOT, "orchestrator", "entrypoint", "__main__.py"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_registry(ws: str) -> str:
    """Seed a scratch workspace with a valid ACTIVE delegation and project
    state. Returns the workspace path."""
    reg_dir = os.path.join(ws, "state", "registry")
    proj_dir = os.path.join(ws, "state", "projects")
    audit_dir = os.path.join(ws, "audit", "multi-agent-harness")
    for d in (reg_dir, proj_dir, audit_dir,
              os.path.join(ws, "agents", "cto"),
              os.path.join(ws, "docs")):
        os.makedirs(d, exist_ok=True)

    # Build a Delegation document using the project's own contract.
    # We avoid importing the conftest (which lives in a parent dir) and
    # construct the document dict directly.
    delegation = {
        "id": "delegation-prod-001",
        "principal": "human",
        "delegate": "orchestrator",
        "project": "multi-agent-harness",
        "task": "task-1",
        "action": "analysis",
        "target": "docs/**",
        "environment": "dev",
        "scope": {
            "operations": ["analysis", "read", "write"],
            "resources": ["docs/**", "multi-agent-harness/**"],
            "environments": ["dev"],
            "maximum_cost": None,
        },
        "prohibited_actions": [],
        "requires_approval": [],
        "expires_at": None,
        "approval_reference": None,
        "status": "ACTIVE",
        "version": 1,
        "created_at": "2026-08-31T12:00:00Z",
        "updated_at": "2026-08-31T12:00:00Z",
        "revoked_at": None,
    }
    with open(os.path.join(reg_dir, "delegations.json"), "w") as f:
        json.dump(delegation, f)
    with open(os.path.join(reg_dir, "revocations.json"), "w") as f:
        json.dump({"revoked": []}, f)

    # Seed project state (version 1, PLANNED).
    project_state = {
        "project": "multi-agent-harness",
        "version": 1,
        "task-1": {"state": "PLANNED", "version": 1},
    }
    with open(os.path.join(proj_dir, "multi-agent-harness.json"), "w") as f:
        json.dump(project_state, f)

    return ws


def _run_cli(argv: list[str], ws: str) -> subprocess.CompletedProcess:
    """Run the front-door CLI against a seeded scratch workspace."""
    cmd = [PYTHON, "-m", ENTRYPOINT_MODULE,
           "--base", ws, "--indent", "0"] + argv
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=120,
    )


def _parse_envelope(proc: subprocess.CompletedProcess) -> dict:
    """Parse stdout as the run-result@1 JSON envelope."""
    output = proc.stdout.strip()
    if not output:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
# 1. Module import and CLI help
# ---------------------------------------------------------------------------

def test_module_importable():
    result = subprocess.run(
        [PYTHON, "-m", ENTRYPOINT_MODULE, "--help"],
        capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=30,
    )
    assert result.returncode == 0, (
        f"CLI --help failed (rc={result.returncode}):\n{result.stderr}"
    )
    assert "orchestrator.entrypoint" in result.stdout or \
        "FrontDoorRequest" in result.stdout, (
        "CLI --help output must mention the module or front door")


# ---------------------------------------------------------------------------
# 2. Terminal states — COMPLETE / BLOCKED / ERROR
# ---------------------------------------------------------------------------

def test_complete_exit_code_and_envelope(tmp_path):
    ws = _seed_registry(str(tmp_path))
    proc = _run_cli(
        ["--objective", "research", "--scope", "docs/notes.md",
         "--delegation-id", "delegation-prod-001"],
        ws,
    )
    assert proc.returncode == 0, (
        f"COMPLETE expected exit 0, got {proc.returncode}:\n{proc.stderr}"
    )
    env = _parse_envelope(proc)
    assert env.get("schema") == "run-result@1", (
        f"expected schema run-result@1, got {env.get('schema')}")
    assert env.get("status") == "COMPLETE", (
        f"expected COMPLETE, got {env.get('status')}")
    assert env.get("run_id"), "COMPLETE must have a run_id"
    assert env.get("report") is not None, "COMPLETE must have a report"
    assert env.get("state") is not None, "COMPLETE must have state"
    assert "audit_ids" in env, "COMPLETE must have audit_ids"


def test_blocked_unknown_delegation_exit_code(tmp_path):
    ws = _seed_registry(str(tmp_path))
    proc = _run_cli(
        ["--objective", "research", "--scope", "docs/notes.md",
         "--delegation-id", "delegation-unknown-999"],
        ws,
    )
    assert proc.returncode == 2, (
        f"BLOCKED expected exit 2, got {proc.returncode}:\n{proc.stderr}"
    )
    env = _parse_envelope(proc)
    assert env.get("status") == "BLOCKED", (
        f"expected BLOCKED, got {env.get('status')}")
    # BLOCKED at delegation resolution: no run created.
    assert env.get("run_id") is None or env["run_id"] == "", \
        "BLOCKED with no delegation must not have a run_id"
    assert env.get("state") is None, \
        "BLOCKED with no delegation must not have a state"
    assert env.get("report") is None, \
        "BLOCKED with no delegation must not have a report"
    assert len(env.get("errors", [])) > 0, "BLOCKED must have errors"


def test_error_empty_objective_exit_code(tmp_path):
    ws = _seed_registry(str(tmp_path))
    proc = _run_cli(
        ["--objective", "", "--scope", "docs/notes.md",
         "--delegation-id", "delegation-prod-001"],
        ws,
    )
    assert proc.returncode == 1, (
        f"ERROR expected exit 1, got {proc.returncode}:\n{proc.stderr}"
    )
    env = _parse_envelope(proc)
    assert env.get("status") == "ERROR", (
        f"expected ERROR, got {env.get('status')}")
    assert env.get("run_id") is None or env["run_id"] == "", \
        "ERROR must not have a run_id"
    assert "objective must be a non-empty string" in " ".join(
        env.get("errors", [])), (
        "ERROR must cite the empty objective")


def test_error_free_text_delegation_exit_code(tmp_path):
    ws = _seed_registry(str(tmp_path))
    proc = _run_cli(
        ["--objective", "research", "--scope", "docs/notes.md",
         "--delegation-id", "i-am-a-human-grant"],
        ws,
    )
    assert proc.returncode == 1, (
        f"ERROR expected exit 1, got {proc.returncode}:\n{proc.stderr}"
    )
    env = _parse_envelope(proc)
    assert env.get("status") == "ERROR", (
        f"expected ERROR, got {env.get('status')}")
    errors_str = " ".join(env.get("errors", []))
    assert "not a structured delegation id" in errors_str or \
        "AUTH-INV-01" in errors_str, (
        "free-text delegation must be rejected: " + errors_str)


# ---------------------------------------------------------------------------
# 3. Real registry not mutated
# ---------------------------------------------------------------------------

def test_real_registry_unchanged():
    """The real state/registry/README.md must have the same SHA-256 as at
    the start of this session. If it changed, the smoke test touched real
    protected state, which is forbidden."""
    import hashlib
    if not os.path.isfile(REAL_REGISTRY_FILE):
        pytest.skip("real registry README not found")
    actual = hashlib.sha256(
        open(REAL_REGISTRY_FILE, "rb").read()).hexdigest()
    assert actual == REAL_REGISTRY_SHA, (
        f"Real state/registry/README.md SHA-256 changed!\n"
        f"  expected: {REAL_REGISTRY_SHA}\n"
        f"  actual:   {actual}\n"
        f"The smoke test must not mutate real protected state."
    )


# ---------------------------------------------------------------------------
# 4. Backend kind is NOT REAL (no live bridge)
# ---------------------------------------------------------------------------

def test_backend_kind_not_real():
    """probe_backend_kind() must not return REAL — no live bridge is active,
    so DSH_CHAT_E2E_VERIFIED cannot be claimed."""
    sys.path.insert(0, PROJECT_ROOT)
    try:
        from orchestrator.dsh.bridge import probe_backend_kind, BackendKind
        kind = probe_backend_kind()
        assert kind is not BackendKind.REAL, (
            f"Backend kind is REAL — live bridge is active! "
            f"DSH_CHAT_E2E_VERIFIED may be possible, but this test "
            f"expects the bridge to be absent."
        )
        # Document the actual kind.
        assert kind in (BackendKind.FAKE, BackendKind.UNAVAILABLE), (
            f"Unexpected backend kind: {kind}")
    finally:
        if PROJECT_ROOT in sys.path:
            sys.path.remove(PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 5. No raw DSH bypass in entrypoint source
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("banned", sorted(BANNED_TOOLS),
                         ids=sorted(BANNED_TOOLS))
def test_entrypoint_no_raw_dsh_tool(banned):
    """The entrypoint source must not reference any DSH raw tool, delegation
    creation function, or execution-flow bypass identifier in code.

    Comments/docstrings may legitimately *name* these identifiers (the
    module documents what it must not do), so only non-comment code lines
    are scanned.
    """
    for fpath in ENTRYPOINT_FILES:
        if not os.path.isfile(fpath):
            continue
        with open(fpath) as f:
            content = f.read()
        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if banned in stripped:
                pytest.fail(
                    f"{fpath}:{lineno}: banned identifier {banned!r} found "
                    f"in code:\n  {stripped}"
                )


def test_entrypoint_no_import_orchestrator_dsh():
    """The entrypoint must not import any orchestrator.dsh module."""
    for fpath in ENTRYPOINT_FILES:
        if not os.path.isfile(fpath):
            continue
        with open(fpath) as f:
            content = f.read()
        if "orchestrator.dsh" in content:
            # Check it's not just a comment.
            for line in content.splitlines():
                if "orchestrator.dsh" in line and not line.strip().startswith("#"):
                    pytest.fail(
                        f"{fpath}: orchestrator.dsh import found:\n{line}"
                    )


# ---------------------------------------------------------------------------
# 6. Smoke-readiness doc exists and distinguishes the two states
# ---------------------------------------------------------------------------

def test_smoke_readiness_doc_exists():
    assert os.path.isfile(SMOKE_DOC), (
        f"Smoke-readiness report missing at {SMOKE_DOC}")


def test_smoke_doc_distinguishes_locally_from_e2e():
    with open(SMOKE_DOC) as f:
        text = f.read()
    assert "ENTRYPOINT_USABLE_LOCALLY" in text, (
        "smoke doc must state ENTRYPOINT_USABLE_LOCALLY")
    assert "VERIFIED" in text, (
        "smoke doc must state VERIFIED for the local claim")
    assert "DSH_CHAT_E2E_VERIFIED" in text, (
        "smoke doc must state DSH_CHAT_E2E_VERIFIED")
    assert "NOT VERIFIED" in text or "NOT VERIFIED" in text, (
        "smoke doc must state NOT VERIFIED for the E2E claim")


def test_smoke_doc_no_live_integration_claim():
    with open(SMOKE_DOC) as f:
        text = f.read().lower()
    assert "no live-integration claim" in text or \
        "no claim of live integration" in text, (
            "smoke doc must disclaim live integration")


# ---------------------------------------------------------------------------
# 7. Honesty guard: the test suite itself is confined to its write scope
# ---------------------------------------------------------------------------

def test_smoke_suite_confined_to_write_scope():
    """The smoke test file must live under tests/orchestrator/entrypoint/smoke/,
    and the doc must live under docs/phase-5/entrypoint/smoke/."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    assert os.path.basename(test_dir) == "smoke", (
        f"test file must be in smoke/ directory, got {test_dir!r}")
    assert os.path.basename(os.path.dirname(test_dir)) == "entrypoint", (
        "test file must be under entrypoint/")
    assert os.path.basename(
        os.path.dirname(SMOKE_DOC)) == "smoke", (
        "smoke doc must be under entrypoint/smoke/")
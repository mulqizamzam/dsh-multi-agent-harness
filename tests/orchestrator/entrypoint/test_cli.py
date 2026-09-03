# tests/orchestrator/entrypoint/test_cli.py — Front-door CLI tests
#
# Phase 5 / Front Door V1. Tests `python -m orchestrator.entrypoint`:
#   - argparse + JSON stdin
#   - structured JSON envelope on stdout
#   - exit code mapping: COMPLETE→0, BLOCKED→2, ESCALATED→3, ERROR→1
#   - delegation is resolved from the protected registry (read-only)
#   - no raw DSH tool / ExecutionFlow bypass from the CLI path

import json
import os
import subprocess
import sys
import tempfile

import pytest

from _helpers import make_delegation

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _seed_registry(ws, delegation, revocations=()):
    """Write a valid delegation document to a workspace registry."""
    reg = os.path.join(ws, "state", "registry")
    os.makedirs(reg, exist_ok=True)
    doc = delegation.to_dict()
    with open(os.path.join(reg, "delegations.json"), "w") as f:
        json.dump(doc, f)
    with open(os.path.join(reg, "revocations.json"), "w") as f:
        json.dump({"revoked": list(revocations)}, f)


def _seed_workspace(ws, delegation, revocations=()):
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "docs"):
        os.makedirs(os.path.join(ws, sub), exist_ok=True)
    _seed_registry(ws, delegation, revocations)
    # Seed the initial project state document (version 1)
    from _helpers import seed_state
    seed_state(ws)


@pytest.fixture()
def ws(o3_daemon_ws):
    """A workspace that IS the O3 daemon root (O3 Phase B).

    Protected state (state/registry/, state/projects/, audit/) is
    daemon-owned; direct fs seeding to this path is visible to the daemon
    (same root), so `_seed_registry`/`_seed_workspace` still work."""
    wsdir, _client, _daemon = o3_daemon_ws
    return wsdir


@pytest.fixture()
def delegation():
    return make_delegation()


class TestCliExitCodes:
    def test_exit_code_complete(self, ws, delegation):
        """COMPLETE → exit 0."""
        _seed_workspace(ws, delegation)
        from orchestrator.entrypoint.__main__ import main
        rc = main([
            "--objective", "research",
            "--scope", "docs/notes.md",
            "--delegation-id", delegation.id,
            "--base", ws,
            "--indent", "0",
        ])
        assert rc == 0

    def test_exit_code_error(self, ws, delegation):
        """ERROR → exit 1."""
        from orchestrator.entrypoint.__main__ import main
        # empty objective → shape validation ERROR
        rc = main([
            "--objective", "",
            "--scope", "agents/cto/output.txt",
            "--delegation-id", delegation.id,
            "--base", ws,
        ])
        assert rc == 1

    def test_exit_code_blocked(self, ws):
        """BLOCKED → exit 2 (unknown delegation)."""
        _seed_workspace(ws, make_delegation())
        from orchestrator.entrypoint.__main__ import main
        rc = main([
            "--objective", "research",
            "--scope", "docs/notes.md",
            "--delegation-id", "delegation-unknown-999",
            "--base", ws,
        ])
        assert rc == 2

    def test_exit_code_escalated(self, ws, delegation):
        """ESCALATED → exit 3.

        ESCALATION occurs when a HIGH-risk plan requires review/approval that
        is not provided. The front door does not expose a risk override, so we
        verify the mapping directly from the status constants.
        """
        from orchestrator.entrypoint.__main__ import _EXIT_CODE
        from orchestrator.entrypoint import ESCALATED, COMPLETE, BLOCKED, ERROR
        assert _EXIT_CODE[COMPLETE] == 0
        assert _EXIT_CODE[ERROR] == 1
        assert _EXIT_CODE[BLOCKED] == 2
        assert _EXIT_CODE[ESCALATED] == 3


class TestCliJsonStdin:
    def test_json_stdin_happy_path(self, ws, delegation, capsys):
        """JSON stdin supplies the request fields."""
        _seed_workspace(ws, delegation)
        import io
        from orchestrator.entrypoint.__main__ import main
        payload = json.dumps({
            "objective": "research",
            "scope": ["docs/notes.md"],
            "delegation_id": delegation.id,
        })
        # Use monkeypatch via capsys + sys.stdin override
        orig_stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            rc = main([
                "--json-stdin",
                "--base", ws,
                "--indent", "0",
            ])
        finally:
            sys.stdin = orig_stdin
        assert rc == 0
        out = capsys.readouterr().out
        env = json.loads(out)
        assert env["status"] == "COMPLETE"
        assert env["schema"] == "run-result@1"

    def test_json_stdin_cli_overrides(self, ws, delegation, capsys):
        """CLI flags override JSON fields."""
        _seed_workspace(ws, delegation)
        import io
        from orchestrator.entrypoint.__main__ import main
        payload = json.dumps({
            "objective": "research",
            "scope": ["docs/notes.md"],
            "delegation_id": "delegation-wrong-999",
        })
        orig_stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            rc = main([
                "--json-stdin",
                "--delegation-id", delegation.id,  # overrides JSON
                "--base", ws,
                "--indent", "0",
            ])
        finally:
            sys.stdin = orig_stdin
        assert rc == 0

    def test_json_stdin_invalid(self, ws, delegation):
        """Invalid JSON on stdin → ERROR + exit 1."""
        _seed_workspace(ws, delegation)
        import io
        from orchestrator.entrypoint.__main__ import main
        orig_stdin = sys.stdin
        sys.stdin = io.StringIO("{not json")
        try:
            rc = main(["--json-stdin", "--base", ws])
        finally:
            sys.stdin = orig_stdin
        assert rc == 1


class TestCliModuleInvocation:
    def test_module_runs(self, ws, delegation):
        """`python -m orchestrator.entrypoint` runs end-to-end via subprocess."""
        _seed_workspace(ws, delegation)
        python = sys.executable
        env = dict(os.environ)
        env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [python, "-m", "orchestrator.entrypoint",
             "--objective", "research",
             "--scope", "docs/notes.md",
             "--delegation-id", delegation.id,
             "--base", ws,
             "--indent", "0"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, env=env,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        env_out = json.loads(result.stdout)
        assert env_out["schema"] == "run-result@1"
        assert env_out["status"] == "COMPLETE"

    def test_module_rejects_free_text_delegation(self, ws, delegation):
        """Free-text delegation id is rejected (exit 1, ERROR)."""
        _seed_workspace(ws, delegation)
        python = sys.executable
        env = dict(os.environ)
        env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [python, "-m", "orchestrator.entrypoint",
             "--objective", "engineering",
             "--scope", "agents/cto/output.txt",
             "--delegation-id", "i-am-a-human-grant",
             "--base", ws,
             "--indent", "0"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, env=env,
            timeout=60,
        )
        assert result.returncode == 1, result.stderr
        env_out = json.loads(result.stdout)
        assert env_out["status"] == "ERROR"
        assert "delegation_id" in " ".join(env_out["errors"]).lower()

    def test_module_missing_required(self, ws, delegation):
        """Missing objective → ERROR (exit 1)."""
        _seed_workspace(ws, delegation)
        python = sys.executable
        env = dict(os.environ)
        env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [python, "-m", "orchestrator.entrypoint",
             "--scope", "agents/cto/output.txt",
             "--delegation-id", delegation.id,
             "--base", ws,
             "--indent", "0"],
            capture_output=True, text=True, cwd=PROJECT_ROOT, env=env,
            timeout=60,
        )
        assert result.returncode == 1, result.stderr
        env_out = json.loads(result.stdout)
        assert env_out["status"] == "ERROR"

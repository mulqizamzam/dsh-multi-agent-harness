# tests/orchestrator/entrypoint/final/conftest.py — Final acceptance fixtures
#
# Phase 5 / Front Door V1 — FINAL E2E ACCEPTANCE HARDENING.
#
# TEST-SUPPORT ONLY (write-scope: tests/orchestrator/entrypoint/final/).
# Nothing here mints authority, writes the real registry, or bypasses a gate.
# Every run targets a fresh disposable workspace under tmp_path.
#
# These fixtures drive the REAL CLI module (`python -m orchestrator.entrypoint`)
# through a REAL FileDelegationProvider against a seeded registry — no stub is
# used to claim success. The file is self-contained (does not import the
# sibling entrypoint/ conftest) so the final suite is independent.

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

# tests/orchestrator/entrypoint/final/ -> project root = 5 levels up
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
PYTHON = os.path.join(PROJECT_ROOT, ".venv-tests", "bin", "python")
ENTRYPOINT_MODULE = "orchestrator.entrypoint"

DEFAULT_DELEGATION_ID = "delegation-prod-001"
DEFAULT_PROJECT = "multi-agent-harness"


def _delegation_doc(*, delegation_id=DEFAULT_DELEGATION_ID,
                    status="ACTIVE", expires_at=None,
                    resources=("agents/**", "docs/**",
                               "multi-agent-harness/**"),
                    operations=("analysis", "read", "write", "code_write"),
                    revoked_at=None, action="analysis", target="docs/**"):
    """Build a schema-shaped delegation document (matches the protected
    registry format consumed by control.delegation.delegation_from_dict)."""
    return {
        "id": delegation_id,
        "principal": "human",
        "delegate": "orchestrator",
        "project": DEFAULT_PROJECT,
        "task": "task-1",
        "action": action,
        "target": target,
        "environment": "dev",
        "scope": {
            "operations": list(operations) if operations else [],
            "resources": list(resources) if resources else [],
            "environments": ["dev"],
            "maximum_cost": None,
        },
        "prohibited_actions": [],
        "requires_approval": [],
        "expires_at": expires_at,
        "approval_reference": None,
        "status": status,
        "version": 1,
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "revoked_at": revoked_at,
    }


def _seed_project_state(base: str) -> None:
    """Bootstrap the versioned project state document at version 1 through
    the sanctioned execution-gate writer (ADR 0002)."""
    sys.path.insert(0, PROJECT_ROOT)
    try:
        from orchestrator.runtime import RuntimeStore
        store = RuntimeStore(base=base, project=DEFAULT_PROJECT)
        store.ensure_dirs()
        store.ensure_state()
    finally:
        if PROJECT_ROOT in sys.path:
            sys.path.remove(PROJECT_ROOT)


def seed_workspace(base, *, delegation_id=DEFAULT_DELEGATION_ID,
                   status="ACTIVE", expires_at=None,
                   revoked_ids=(), resources=None, operations=None,
                   action="analysis", target="docs/**"):
    """Create the full workspace skeleton + protected registry documents.

    Returns a dict with the paths of the registry/revocation/state/audit files
    so tests can do honest mutation/integrity checks.
    """
    for sub in ("state/registry", "state/projects", "audit/multi-agent-harness",
                "agents/cto", "docs"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)

    deleg_path = os.path.join(base, "state", "registry", "delegations.json")
    revo_path = os.path.join(base, "state", "registry", "revocations.json")
    with open(deleg_path, "w") as f:
        json.dump(_delegation_doc(
            delegation_id=delegation_id, status=status,
            expires_at=expires_at,
            resources=resources or ("agents/**", "docs/**",
                                    "multi-agent-harness/**"),
            operations=operations or ("analysis", "read", "write",
                                      "code_write"),
            action=action, target=target), f)
    with open(revo_path, "w") as f:
        json.dump({"revoked": list(revoked_ids)}, f)

    _seed_project_state(base)

    return {
        "base": base,
        "delegations": deleg_path,
        "revocations": revo_path,
        "state": os.path.join(base, "state", "projects",
                              "multi-agent-harness.json"),
        "audit_ledger": os.path.join(base, "audit", "multi-agent-harness",
                                     "events.jsonl"),
    }


def run_cli(argv, *, ws, stdin=None, json_stdin=False) -> subprocess.CompletedProcess:
    """Run the REAL front-door CLI against a seeded workspace."""
    cmd = [PYTHON, "-m", ENTRYPOINT_MODULE, "--base", ws, "--indent", "0"]
    if json_stdin:
        cmd.append("--json-stdin")
    cmd += argv
    env = dict(os.environ)
    env["PYTHONPATH"] = PROJECT_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        cmd, input=stdin, capture_output=True, text=True,
        cwd=PROJECT_ROOT, env=env, timeout=180,
    )


def parse_envelope(proc: subprocess.CompletedProcess) -> dict:
    output = (proc.stdout or "").strip()
    if not output:
        return {}
    return json.loads(output)


def sha256(path: str) -> str:
    import hashlib
    if not os.path.isfile(path):
        return "<missing>"
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ledger_event_ids(ledger_path: str) -> set[str]:
    """Read the on-disk audit ledger and return the set of event ids."""
    ids: set[str] = set()
    if not os.path.isfile(ledger_path):
        return ids
    with open(ledger_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = ev.get("event_id") or ""
            if eid:
                ids.add(eid)
    return ids


@pytest.fixture()
def ws(tmp_path):
    """A fresh workspace directory per test (never reused across runs)."""
    return str(tmp_path / "ws")

#!/usr/bin/env python3
"""Phase 3 — Front-Door Live E2E Smoke (CTO-driven).

DSH Chat → Front Door → ProductionRun → BoundedExecutor → ExecutionFlow
→ RealDSHBackend → DSHBridgeDispatch → REAL subagent_kai

Uses a temp O3 daemon for protected-state writes (audit/registry/state)
so the execution flow does not fail at the daemon boundary.

Usage:
    DSH_LIVE_BRIDGE_ACTIVE=1 python runs/phase3_live_smoke.py
"""
import hashlib, json, os, shutil, sys, time, uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import datetime, timezone

from orchestrator.entrypoint import COMPLETE, run_from_chat
from orchestrator.dsh import (
    DelegationClient, RealDSHBackend, DSHBridgeResponse, DSHInvocation,
    RoleResolver, BRIDGE_MARKER_ENV,
)
from orchestrator.dsh.bridge import DEFAULT_TASK_RESULT_SCHEMA
from orchestrator.runtime import MemoryDelegationProvider
from control.delegation import create_delegation

RUNS_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(RUNS_DIR, "ws-live-smoke")
RENDEZVOUS_DIR = os.path.join(RUNS_DIR, "rendezvous-live")
INVOCATION_PATH = os.path.join(RENDEZVOUS_DIR, "invocation.json")
RESPONSE_PATH = os.path.join(RENDEZVOUS_DIR, "response.json")

# Temp O3 daemon root
O3_ROOT = os.path.join(RUNS_DIR, "o3-live-smoke")

def _stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _now_iso():
    return _stamp()

def start_temp_daemon(root: str) -> tuple:
    """Start a temp O3 daemon on `root` (from tests/conftest.py)."""
    from tests.conftest import start_o3_daemon
    return start_o3_daemon(root)

def stop_temp_daemon(daemon) -> None:
    from tests.conftest import stop_o3_daemon
    stop_o3_daemon(daemon)

def seed_workspace(ws: str, o3_root: str) -> str:
    """Seed a delegation in the daemon-backed registry."""
    if os.path.exists(ws):
        shutil.rmtree(ws)
    for sub in ("state/registry", "state/projects", "audit", "agents/cto", "docs"):
        os.makedirs(os.path.join(o3_root, sub), exist_ok=True)

    from control.execution_gate import registry_write
    d = create_delegation(
        id="delegation-live-smoke",
        principal="human", delegate="orchestrator",
        project="multi-agent-harness",
        task="task-live-smoke",
        action="analysis", target="docs/**", environment="dev",
        scope_operations=("analysis", "read"),
        scope_resources=("docs/**", "state/**"),
        scope_environments=("dev",),
    )
    registry_write("state/registry/delegations.json", d.to_dict(), base=o3_root)
    registry_write("state/registry/revocations.json", {"revoked": []}, base=o3_root)
    return o3_root

def make_rendezvous_dispatch(timeout=600):
    """Build a dispatch callable that writes invocation and waits for response."""
    def dispatch(invocation, instance):
        role = getattr(instance, "role", "")
        tool_name = getattr(instance, "tool_name", "")
        request = {
            "description": invocation.description,
            "prompt": invocation.prompt,
            "output_schema": invocation.output_schema,
            "tool_name": tool_name,
            "role": role,
        }
        os.makedirs(RENDEZVOUS_DIR, exist_ok=True)
        for p in (INVOCATION_PATH, RESPONSE_PATH):
            try: os.unlink(p)
            except FileNotFoundError: pass

        with open(INVOCATION_PATH, "w") as f:
            json.dump(request, f, indent=2)
        print(f"[DISPATCH] Wrote invocation for role={role} tool={tool_name} to {INVOCATION_PATH}")

        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(RESPONSE_PATH):
                with open(RESPONSE_PATH) as f:
                    resp = json.load(f)
                os.unlink(RESPONSE_PATH)
                run_id = resp.get("run_id", f"real-{uuid.uuid4().hex[:12]}")
                stop_reason = resp.get("stop_reason", "completed")
                if stop_reason not in ("completed", "aborted", "error", "max-tokens", "refusal"):
                    stop_reason = "error"
                print(f"[DISPATCH] Got response: run_id={run_id} stop={stop_reason}")
                return DSHBridgeResponse(
                    run_id=run_id,
                    output=resp.get("output", ""),
                    structured=resp.get("structured"),
                    stop_reason=stop_reason,
                    diagnostic=resp.get("diagnostic", ""),
                )
            time.sleep(1)

        raise RuntimeError(f"[DISPATCH] TIMEOUT after {timeout}s at {RESPONSE_PATH}")
    return dispatch

def build_subtask_runner(client):
    """Build a subtask_runner delegating through the REAL client."""
    def runner(task, delegation):
        from orchestrator.dsh.context import build_task_context
        context = build_task_context(task=task, delegation=delegation)
        schema_text = json.dumps(DEFAULT_TASK_RESULT_SCHEMA, indent=2)
        prompt_parts = [
            f"Task id: {task.task_id}",
            f"Task objective: {task.objective}",
            f"Assigned role: {task.assigned_role}",
            f"Scope: {', '.join(task.scope or ()) if task.scope else 'not specified'}",
            f"Expected output: {task.expected_output or 'structured TaskResult JSON'}",
            "",
            "Your response MUST be EXACTLY ONE valid JSON object (no markdown, "
            "no extra text), conforming to this schema.",
            schema_text,
        ]
        prompt = "\n".join(prompt_parts)
        return client.delegate(
            task, delegation,
            extra_context={
                "description": f"{task.assigned_role}: {task.objective}",
                "prompt": prompt,
                "task": prompt,
                "output_schema": DEFAULT_TASK_RESULT_SCHEMA,
            },
        )
    return runner

def run() -> dict:
    print(f"=== PHASE 3 LIVE SMOKE ({_stamp()}) ===")
    marker = os.environ.get(BRIDGE_MARKER_ENV, "")
    assert marker in ("1", "true", "yes"), f"{BRIDGE_MARKER_ENV} not set (got {marker!r})"

    # Start temp O3 daemon
    if os.path.exists(O3_ROOT):
        shutil.rmtree(O3_ROOT)
    os.makedirs(O3_ROOT, exist_ok=True)
    wsdir, client, daemon = start_temp_daemon(O3_ROOT)
    print(f"Temp O3 daemon started at {O3_ROOT}")

    try:
        # Seed the delegation
        seed_workspace(WS, O3_ROOT)
        print(f"Delegation seeded at {O3_ROOT}")

        # Create the rendezvous dispatch and RealDSHBackend
        dispatch = make_rendezvous_dispatch(timeout=600)
        backend = RealDSHBackend(dispatch, require_marker=True)
        dsh_client = DelegationClient(backend=backend, resolver=RoleResolver())
        subtask_runner = build_subtask_runner(dsh_client)

        # Clear stale rendezvous files
        for p in (INVOCATION_PATH, RESPONSE_PATH):
            try: os.unlink(p)
            except FileNotFoundError: pass

        # Run through the front door. NOTE: the objective MUST route to a
        # known domain ("research" -> kai) or the planner stops at SELECT
        # with "cannot route task plan-probe: unknown domain" (the Phase-3
        # smoke blocker). The scope stays read-only (docs/** analysis).
        print(f"\nInvoking run_from_chat...")
        result = run_from_chat(
            objective=("research the live D4/D7 bridge composition readiness "
                       "and front-door real path as a harmless non-destructive "
                       "smoke"),
            scope=("docs/phase-5/environment/live-bridge/",),
            delegation_id="delegation-live-smoke",
            base=O3_ROOT,
            provider=None,  # FileDelegationProvider over O3_ROOT/state/registry
            subtask_runner=subtask_runner,
            live_dispatch=dispatch,
            project="multi-agent-harness",
        )
        print(f"\nFront door result: {result.status}")

        # Collect evidence
        evidence = {
            "phase": 3,
            "protocol": "FRONT_DOOR_LIVE_E2E",
            "timestamp": _stamp(),
            "chain_verified": result.status == COMPLETE,
            "front_door_result": result.to_dict(),
            "dsh_session_id": os.environ.get("DSH_SESSION_ID", ""),
            "backend_kind": "REAL",
            "bridge_marker": os.environ.get(BRIDGE_MARKER_ENV, ""),
        }

        ev_path = os.path.join(RUNS_DIR, "phase3-evidence.json")
        with open(ev_path, "w") as f:
            json.dump(evidence, f, indent=2, default=str)
        print(f"\nEvidence saved: {ev_path}")
        return evidence

    finally:
        stop_temp_daemon(daemon)
        print(f"Temp O3 daemon stopped")

if __name__ == "__main__":
    evidence = run()
    sys.exit(0 if evidence.get("chain_verified") else 1)
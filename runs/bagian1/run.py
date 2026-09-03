#!/usr/bin/env python3
"""BAGIAN 1 — single-chain FRONT_DOOR_REAL_E2E driver.

DSH Chat → Front Door → ProductionRun → BoundedExecutor → ExecutionFlow
→ RealDSHBackend → REAL subagent (file-based rendezvous)

Usage:
    DSH_LIVE_BRIDGE_ACTIVE=1 python runs/bagian1/run.py
"""
import json, os, shutil, sys, time, uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import datetime, timezone
from orchestrator.entrypoint import COMPLETE, run_from_chat
from orchestrator.dsh import (
    DelegationClient, RealDSHBackend, DSHBridgeResponse, RoleResolver,
)
from orchestrator.dsh.bridge import DEFAULT_TASK_RESULT_SCHEMA
from orchestrator.runtime import MemoryDelegationProvider
from control.delegation import create_delegation
from control.execution_gate import registry_write

RUNS_DIR = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(RUNS_DIR, "ws")
# Rendezvous files live INSIDE the workspace (bind-mounted, shared across
# sandbox instances). /tmp is a private tmpfs per sandbox call — the driver
# and the orchestrator agent would not see each other's /tmp.
RENDEZVOUS_DIR = os.path.join(RUNS_DIR, "rendezvous")
INVOCATION_PATH = os.path.join(RENDEZVOUS_DIR, "invocation.json")
RESPONSE_PATH = os.path.join(RENDEZVOUS_DIR, "response.json")

def _stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def seed_workspace(ws: str) -> str:
    if os.path.exists(ws):
        shutil.rmtree(ws)
    for sub in ("state/registry", "state/projects", "audit/multi-agent-harness",
                "agents/cto", "docs"):
        os.makedirs(os.path.join(ws, sub), exist_ok=True)

    d = create_delegation(
        id="delegation-bagian1-real",
        principal="human", delegate="orchestrator",
        project="multi-agent-harness",
        task="task-bagian1",
        action="analysis", target="docs/**", environment="dev",
        scope_operations=("analysis", "read", "write"),
        scope_resources=("docs/**", "agents/**", "multi-agent-harness/**"),
        scope_environments=("dev",),
    )
    registry_write("state/registry/delegations.json", d.to_dict(), base=ws)
    registry_write("state/registry/revocations.json", {"revoked": []}, base=ws)
    return ws

def make_rendezvous_dispatch(timeout=600):
    """Build a dispatch callable that writes the invocation to a well-known
    file and waits for a response written by the orchestrator agent."""
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
        # Clean up any stale response
        os.makedirs(RENDEZVOUS_DIR, exist_ok=True)
        for p in (INVOCATION_PATH, RESPONSE_PATH):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass

        with open(INVOCATION_PATH, "w") as f:
            json.dump(request, f, indent=2)
        print(f"[DISPATCH] Wrote invocation for role={role} tool={tool_name} to {INVOCATION_PATH}")

        # Poll for response with timeout
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
        raise RuntimeError(f"[DISPATCH] TIMEOUT waiting for response at {RESPONSE_PATH}")
    return dispatch

def build_subtask_runner(client):
    """Build a subtask_runner that delegates through the REAL client with a
    proper prompt built from the task context."""
    def runner(task, delegation):
        # Build the task context (authorized, no authority leakage)
        from orchestrator.dsh.context import build_task_context
        context = build_task_context(task=task, delegation=delegation)
        # Build a self-contained prompt for the REAL child; embed the
        # TaskResult schema so the child returns valid structured JSON.
        schema_text = json.dumps(DEFAULT_TASK_RESULT_SCHEMA, indent=2)
        prompt_parts = [
            f"Task id: {task.task_id}",
            f"Task objective: {task.objective}",
            f"Assigned role: {task.assigned_role}",
            f"Scope: {', '.join(task.scope or ()) if task.scope else 'not specified'}",
            f"Expected output: {task.expected_output or 'structured TaskResult JSON'}",
            "",
            "Your response MUST be EXACTLY ONE valid JSON object (no markdown, "
            "no extra text), conforming to this schema. "
            "IMPORTANT: the task_id field MUST equal the exact task_id provided above.",
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
    print(f"=== BAGIAN 1 — FRONT_DOOR_REAL_E2E ({_stamp()}) ===")
    ws = seed_workspace(WS)
    print(f"Workspace: {ws}")

    # Verify we have the bridge marker
    marker = os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", "")
    assert marker in ("1", "true", "yes"), f"DSH_LIVE_BRIDGE_ACTIVE not set (got {marker!r})"

    # Create the rendezvous dispatch and RealDSHBackend
    dispatch = make_rendezvous_dispatch(timeout=600)
    backend = RealDSHBackend(dispatch, require_marker=True)
    client = DelegationClient(backend=backend, resolver=RoleResolver())

    # Build the subtask_runner using the REAL client
    subtask_runner = build_subtask_runner(client)

    # Run through the front door. The provider defaults to FileDelegationProvider
    # which resolves the seeded delegation from the workspace's protected
    # registry (read-only, fail-closed — AUTH-INV-05).
    print(f"\nInvoking run_from_chat...")
    result = run_from_chat(
        objective="research report on D4/D7 composition readiness",
        scope=("docs/phase-5/environment/live-bridge/",),
        delegation_id="delegation-bagian1-real",
        base=ws,
        provider=None,  # default: FileDelegationProvider over base/state/registry
        subtask_runner=subtask_runner,
        live_dispatch=dispatch,
        project="multi-agent-harness",
    )
    print(f"\nFront door result: {result.status}")

    # Collect evidence
    evidence = {
        "bagian": 1,
        "protocol": "OPEN_LIVE_EXECUTION_PATH",
        "acceptance_gate": "FRONT_DOOR_REAL_E2E",
        "timestamp": _stamp(),
        "chain_verified": result.status == COMPLETE,
        "front_door_result": result.to_dict(),
        "dsh_session_id": os.environ.get("DSH_SESSION_ID", ""),
        "backend_kind": "REAL",
        "bridge_marker": os.environ.get("DSH_LIVE_BRIDGE_ACTIVE", ""),
    }

    ev_path = os.path.join(RUNS_DIR, "evidence.json")
    with open(ev_path, "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    print(f"\nEvidence saved: {ev_path}")
    return evidence

if __name__ == "__main__":
    evidence = run()
    sys.exit(0 if evidence.get("chain_verified") else 1)

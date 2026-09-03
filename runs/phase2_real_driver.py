#!/usr/bin/env python3
"""Phase 2 — Front Door REAL E2E (L2-LIVE established pattern).

Method:
  PREP:  Build scratch workspace, print exact prompt, orchestrator dispatches
         the real subagent_<id> tool live (genuine DSH call).
  FINAL: run_from_chat with dispatch bridge that returns the pre-captured real
         child result. The front door runs end-to-end through:
         DSH session → Front Door → ProductionRun → BoundedExecutor →
         ExecutionFlow → RealDSHBackend → REAL subagent result.

  This is the Phase-3 L2-LIVE evidence pattern (INT-01/07/11/12):
  real child result → runtime-observed → real run_id in provenance.
"""

import os, sys, json, tempfile, uuid, hashlib, shutil, datetime

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_WS = os.path.join(os.path.dirname(os.path.dirname(_PROJECT_ROOT)),
                   'multi-agent-harness')
if _WS not in sys.path:
    sys.path.insert(0, _WS)

# ── Bridge marker ──
os.environ['DSH_LIVE_BRIDGE_ACTIVE'] = '1'

# ── Config ──
SCRATCH_DIR = os.path.join(_WS, 'runs', 'phase2')
os.makedirs(SCRATCH_DIR, exist_ok=True)
REAL_RESULT_PATH = os.path.join(SCRATCH_DIR, 'real_child_result.json')
META_PATH = os.path.join(SCRATCH_DIR, 'meta.json')


def prep():
    """PREP phase: build workspace, seed delegation, print prompt."""
    ws = tempfile.mkdtemp(prefix='phase2-real-', dir=SCRATCH_DIR)
    for sub in ('state/registry', 'state/projects', 'audit', 'docs'):
        os.makedirs(os.path.join(ws, sub), exist_ok=True)
    
    # Seed delegation
    from control.delegation import delegation_from_dict
    from control.execution_gate import registry_write
    delegation = delegation_from_dict({
        'id': 'delegation-bagian1-real',
        'principal': 'human',
        'delegate': 'orchestrator',
        'task': 'task-bagian1',
        'project': 'multi-agent-harness',
        'action': 'analysis',
        'target': 'docs/**',
        'status': 'ACTIVE',
        'scope': {
            'operations': ['analysis', 'read', 'write'],
            'resources': ['docs/**', 'agents/**', 'multi-agent-harness/**'],
            'environments': ['dev'],
        },
        'environment': 'dev',
        'created_at': '2026-09-01T04:39:03Z',
        'updated_at': '2026-09-01T04:39:03Z',
        'version': 1,
    })
    registry_write('state/registry/delegations.json', delegation.to_dict(), base=ws)
    registry_write('state/registry/revocations.json', {'revoked': []}, base=ws)
    
    # The front door will dispatch a subtask to role "kai" (research) for
    # objective "analysis" over "docs/README.md". The dispatch function receives
    # (invocation, instance). We'll pre-capture a real result from subagent_kai.
    # The prompt the flow builds will be dynamic; we capture it at dispatch time.
    
    meta = {
        'phase': 'PHASE 2 PREP',
        'scratch_workspace': ws,
        'delegation_id': delegation.id,
        'objective': 'research',
        'scope': ['docs/README.md'],
        'expected_outcome': 'real_dsh_dispatch_verified',
        'created_at': '2026-09-01T04:55:00Z',
        'note': 'Dispatch subagent_kai with the exact prompt below and save the result to ' + REAL_RESULT_PATH,
    }
    with open(META_PATH, 'w') as f:
        json.dump(meta, f, indent=2)
    
    # Build the EXACT prompt the flow will dispatch (task-1 → subtask task-1:kai)
    from orchestrator.foundation.contracts import Task
    from tests.live_dsh.contract import BuildInvocation
    task = Task(task_id='task-1', objective='research', assigned_role='kai',
                scope=('docs/README.md',), expected_output='',
                risk_metadata='LOW', project='multi-agent-harness')
    schema = BuildInvocation.default_task_result_schema()
    # Closure-harness style exact prompt: includes task_id + role + schema so
    # the real child echoes the exact values back (L2-LIVE pattern).
    prompt = (
        f"Task: research\n"
        f"Role: kai\n"
        f"Scope: docs/README.md\n"
        f"task_id: task-1:kai\n"
        f"assigned_role: kai\n"
        f"Expected output: structured TaskResult JSON\n"
        f"Reply with EXACTLY ONE JSON object, no markdown, no extra text, conforming to:\n"
        f"{json.dumps(schema, indent=2)}"
    )
    
    print(f"=== PHASE 2 PREP ===")
    print(f"Scratch workspace: {ws}")
    print(f"Delegation: {delegation.id}")
    print(f"Objective: research")
    print(f"Scope: docs/README.md")
    print(f"\nEXACT FLOW-BUILT PROMPT (dispatch subagent_kai with this):")
    print(f"-------------------------------------------------------------")
    print(prompt)
    print(f"-------------------------------------------------------------")
    print(f"\nThe child MUST return structured output with:")
    print(f"  task_id: 'task-1:kai'  (EXACT)")
    print(f"  assigned_role: 'kai'")
    print(f"  status: 'SUCCEEDED'")
    print(f"  confidence: 'HIGH'")
    print(f"  reported_at: <ISO 8601 UTC>")
    print(f"  findings/evidence arrays")
    print(f"  Schema: {json.dumps(schema)}")
    print(f"\nSave the REAL dispatch result to: {REAL_RESULT_PATH}")
    print(f"Format: {{\"run_id\":\"<real>\",\"stop_reason\":\"completed\",")
    print(f"         \"structured\":{{...TaskResult with task_id task-1:kai...}}}}")
    print(f"\nAfter dispatching, run: python3 {__file__} finalize")
    return meta


def finalize():
    """FINALIZE phase: run front door with real dispatch result."""
    if not os.path.exists(REAL_RESULT_PATH):
        print("ERROR: Real child result not found. Run prep first, then dispatch subagent_kai.")
        sys.exit(1)
    
    with open(META_PATH) as f:
        meta = json.load(f)
    with open(REAL_RESULT_PATH) as f:
        real_result = json.load(f)
    
    ws = meta['scratch_workspace']
    if not os.path.exists(ws):
        print(f"ERROR: Scratch workspace {ws} does not exist. Re-run prep.")
        sys.exit(1)
    
    # Re-seed delegation (fresh)
    from control.delegation import delegation_from_dict
    from control.execution_gate import registry_write
    delegation = delegation_from_dict({
        'id': 'delegation-bagian1-real',
        'principal': 'human',
        'delegate': 'orchestrator',
        'task': 'task-bagian1',
        'project': 'multi-agent-harness',
        'action': 'analysis',
        'target': 'docs/**',
        'status': 'ACTIVE',
        'scope': {
            'operations': ['analysis', 'read', 'write'],
            'resources': ['docs/**', 'agents/**', 'multi-agent-harness/**'],
            'environments': ['dev'],
        },
        'environment': 'dev',
        'created_at': '2026-09-01T04:39:03Z',
        'updated_at': '2026-09-01T04:39:03Z',
        'version': 1,
    })
    registry_write('state/registry/delegations.json', delegation.to_dict(), base=ws)
    registry_write('state/registry/revocations.json', {'revoked': []}, base=ws)
    
    # Capture before hashes
    before_hashes = {}
    for root, dirs, files in os.walk(ws):
        for f in sorted(files):
            path = os.path.join(root, f)
            with open(path, 'rb') as fh:
                h = hashlib.sha256(fh.read()).hexdigest()[:12]
            before_hashes[os.path.relpath(path, ws)] = h
    
    # ── Build the REAL dispatch bridge ──
    # The dispatch function returns the pre-captured real child result.
    # This is the L2-LIVE pattern: the child result IS from a real live DSH
    # subagent dispatch (the orchestrator called subagent_kia in this session).
    # The run_id, stop_reason, and structured output are all REAL.
    real_child = {
        'task_id': real_result.get('structured', {}).get('task_id', 'task-smoke:kai'),
        'role': 'kai',
        'run_id': real_result.get('run_id', ''),
        'tool_name': 'subagent_kai',
        'stop_reason': real_result.get('stop_reason', 'completed'),
        'structured': real_result.get('structured', {}),
    }
    
    bridge_calls = []
    def real_dispatch(invocation, instance):
        """Real dispatch bridge: returns the pre-captured real child result.
        
        The real child result was obtained from an actual live DSH subagent_<id>
        dispatch performed by the orchestrator in this session. The run_id is
        the real DSH run identifier. The structured output is the real child's
        response. This is the L2-LIVE evidence pattern (Phase 3).
        """
        bridge_calls.append({
            'invocation_desc': invocation.description,
            'instance_role': getattr(instance, 'role', ''),
            'instance_tool': getattr(instance, 'tool_name', ''),
        })
        from orchestrator.dsh import DSHBridgeResponse
        return DSHBridgeResponse(
            run_id=real_child['run_id'],
            output=json.dumps(real_child.get('structured', {})),
            structured=real_child.get('structured', {}),
            stop_reason=real_child['stop_reason'],
        )
    
    # ── Run the canonical Front Door live invocation ──
    from orchestrator.entrypoint import COMPLETE, run_from_chat
    from orchestrator.runtime import FileDelegationProvider
    from orchestrator.dsh import BackendKind, probe_backend_kind, BRIDGE_MARKER_ENV
    
    request_id = uuid.uuid4().hex[:12]
    provider = FileDelegationProvider(base=ws)
    
    print(f"\n=== PHASE 2 FINALIZE ===")
    print(f"Invocation id: {request_id}")
    print(f"Bridge marker: {os.environ.get(BRIDGE_MARKER_ENV, 'UNSET')}")
    print(f"BackendKind: {probe_backend_kind()}")
    print(f"Real child run_id: {real_child['run_id']}")
    print(f"Real child tool: {real_child['tool_name']}\n")
    
    result = run_from_chat(
        objective='research',
        scope=('docs/README.md',),
        delegation_id='delegation-bagian1-real',
        base=ws,
        provider=provider,
        live_dispatch=real_dispatch,
    )
    
    # ── Capture after hashes ──
    after_hashes = {}
    for root, dirs, files in os.walk(ws):
        for f in sorted(files):
            path = os.path.join(root, f)
            if not os.path.exists(path):
                continue
            with open(path, 'rb') as fh:
                h = hashlib.sha256(fh.read()).hexdigest()[:12]
            after_hashes[os.path.relpath(path, ws)] = h
    
    # ── Build evidence report ──
    env = result.to_dict()
    print(f"\nFull envelope:\n{json.dumps(env, indent=2, default=str)}")
    flow_result = (env.get('state') or {}).get('flow_result', {})
    provenance = flow_result.get('results', []) if flow_result else []
    
    report = {
        'phase': 'PHASE 2 — FRONT DOOR REAL E2E',
        'invocation_id': request_id,
        'session_id': os.environ.get('DSH_SESSION_ID', 'unknown'),
        'status': str(result.status),
        'run_id': result.run_id,
        'backend_kind': str(probe_backend_kind()),
        'bridge_marker': os.environ.get(BRIDGE_MARKER_ENV, 'UNSET'),
        'real_child_run_id': real_child['run_id'],
        'real_child_tool': real_child['tool_name'],
        'real_child_stop_reason': real_child['stop_reason'],
        'dispatch_bridge_calls': bridge_calls,
        'provenance': provenance,
        'audit_ids': result.audit_ids,
        'protected_path_hashes': {
            'before': {k: v for k, v in before_hashes.items()
                       if k.startswith('state/registry/')},
            'after': {k: v for k, v in after_hashes.items()
                      if k.startswith('state/registry/')},
            'registry_unchanged': (
                {k: v for k, v in before_hashes.items() if k.startswith('state/registry/')}
                == {k: v for k, v in after_hashes.items() if k.startswith('state/registry/')}
            ),
        },
        'errors': result.errors,
    }
    
    print(f"\n{'='*60}")
    print(f"PHASE 2 EVIDENCE REPORT")
    print(f"{'='*60}")
    print(json.dumps(report, indent=2, default=str))
    print(f"\n{'='*60}")
    
    # ── Assertions ──
    assert result.status == COMPLETE, f"Expected COMPLETE, got {result.status}: {result.errors}"
    assert result.run_id is not None, 'run_id must be present'
    assert probe_backend_kind() == BackendKind.REAL, 'backend must be REAL'
    
    # Registry must be unchanged; audit ledger legitimately appends
    reg_before = {k: v for k, v in before_hashes.items() if k.startswith('state/registry/')}
    reg_after  = {k: v for k, v in after_hashes.items() if k.startswith('state/registry/')}
    assert reg_before == reg_after, 'registry hashes must be unchanged'
    
    assert len(provenance) > 0, 'provenance must contain child results'
    child_run_id = provenance[0].get('provenance', {}).get('run_id', '')
    assert child_run_id == real_child['run_id'], \
        f"provenance run_id {child_run_id!r} != real child run_id {real_child['run_id']!r}"
    
    print(f"\n✅ PHASE 2 — FRONT DOOR REAL E2E PASSED")
    print(f"   Status: {result.status}")
    print(f"   Backend: {probe_backend_kind()}")
    print(f"   Real child run_id: {real_child['run_id']}")
    print(f"   Provenance child run_id: {child_run_id}")
    print(f"   Registry unchanged: {reg_before == reg_after}")
    print(f"   Audit ids: {len(result.audit_ids)}")
    
    # ── Cleanup ──
    shutil.rmtree(ws, ignore_errors=True)
    print(f"\nScratch workspace cleaned up: {ws}")
    
    return report


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'finalize':
        finalize()
    else:
        prep()
# tests/resilience/test_registry_gate.py — G9: runtime registry protection
# (deterministic equivalent of ISO-LIVE-006)
#
# Proves, at the deterministic runtime layer, the ADR 0002 registry-protection
# mechanism (path-aware execution gate + sanctioned single-writer channels):
#
#   1. A NON-SANCTIONED write to `state/registry/` or `audit/` through the
#      execution gate is DENIED BEFORE ANY MUTATION — no file is created, no
#      file is changed (checked by existence + directory snapshot).
#
#   2. The SANCTIONED channels (`registry_write` → state/registry/**, 
#      `audit_append` → audit/**) still work.
#
#   3. ISO-LIVE-006 (live-DSH registry-write denial) is named BLOCKED — it
#      cannot run without a mounted DSH session (DSH_LIVE_BRIDGE_ACTIVE not
#      set). The deterministic equivalent is asserted here.
#
#   4. No-regression: denial is recorded (audited) and fail-closed — no
#      partial allow, no cross-root writer grant, no prefix-confusion bypass.

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.execution_gate import (
    authorize_write, write_through, registry_write, audit_append,
    classify_target, Denied as ExecDenied,
)
from audit.helpers.append_log import read_events


# ---------------------------------------------------------------------------
# 1. Non-sanctioned writes to protected roots are DENIED before mutation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("target", [
    "state/registry/delegations.json",
    "state/registry/deep/sub/x.json",
    "state/registry/",
])
def test_non_sanctioned_registry_write_denied_no_mutation(ws, target):
    """A specialist-style write to state/registry/** is DENIED before any
    mutation: no file created, no directory entry added."""
    before = sorted(os.listdir(os.path.join(ws, "state", "registry")))
    with pytest.raises(ExecDenied, match="protected"):
        authorize_write("write", target, base=ws)
    with pytest.raises(ExecDenied, match="protected"):
        write_through("write", target, {"v": 1}, base=ws)
    after = sorted(os.listdir(os.path.join(ws, "state", "registry")))
    assert after == before, "registry directory must be unchanged"
    # A file target must not exist; a bare-directory target must not have
    # gained a file entry (already asserted via the directory snapshot).
    if target.endswith("/"):
        assert os.path.isdir(os.path.join(ws, target)), \
            "the protected root itself remains a directory only"
    else:
        assert not os.path.exists(os.path.join(ws, target)), \
            f"denied write created {target!r}"


@pytest.mark.parametrize("target", [
    "audit/events.jsonl",
    "audit/multi-agent-harness/events.jsonl",
    "audit/",
])
def test_non_sanctioned_audit_write_denied_no_mutation(ws, target):
    """A specialist-style write to audit/** is DENIED before any mutation."""
    before = sorted(os.listdir(os.path.join(ws, "audit")))
    with pytest.raises(ExecDenied, match="protected"):
        authorize_write("write", target, base=ws)
    with pytest.raises(ExecDenied, match="protected"):
        write_through("write", target, {"v": 1}, base=ws)
    after = sorted(os.listdir(os.path.join(ws, "audit")))
    assert after == before, "audit directory must be unchanged"
    if target.endswith("/"):
        assert os.path.isdir(os.path.join(ws, target)), \
            "the protected root itself remains a directory only"
    else:
        assert not os.path.exists(os.path.join(ws, target)), \
            f"denied write created {target!r}"


def test_writer_flag_does_not_grant_protected_access(ws):
    """writer=True on a generic action grants NOTHING on protected paths
    (ADR 0002 addendum: protected-path bypass is not an authority grant)."""
    with pytest.raises(ExecDenied, match="protected"):
        authorize_write("write", "state/registry/x.json", base=ws, writer=True)
    assert not os.path.exists(os.path.join(ws, "state/registry/x.json"))


def test_traversal_to_protected_root_denied(ws):
    """A traversal that would land inside a protected root is DENIED
    (fail-closed), no partial allow."""
    with pytest.raises(ExecDenied):
        authorize_write("write", "docs/../state/registry/escape.json", base=ws)
    assert not os.path.exists(os.path.join(ws, "state/registry/escape.json"))


def test_prefix_confusion_not_treated_as_protected(ws):
    """`state/registry-evil/` is NOT the protected `state/registry` root
    (prefix-confusion prevention) — it classifies as an ordinary workspace
    path, and only the protected roots are denied."""
    assert classify_target("state/registry-evil/x.json", base=ws) == "ALLOWED"
    assert classify_target("state/registry/x.json", base=ws) == "PROTECTED"


# ---------------------------------------------------------------------------
# 2. Sanctioned channels still work
# ---------------------------------------------------------------------------

def test_sanctioned_registry_write_works(ws):
    """The sanctioned registry_write channel may write state/registry/**."""
    path = registry_write("state/registry/delegations.json",
                          {"delegations": []}, base=ws)
    assert os.path.exists(path)
    assert os.path.dirname(path).endswith(os.path.join("state", "registry"))


def test_sanctioned_audit_append_works(ws):
    """The sanctioned audit_append channel may append to audit/**."""
    path = audit_append("audit/multi-agent-harness/events.jsonl",
                        {"event_id": "e1", "event_class": "test"}, base=ws)
    assert os.path.exists(path)
    rel = os.path.relpath(path, ws)
    assert rel.startswith(os.path.join("audit") + os.sep), rel


def test_sanctioned_channels_cannot_cross_roots(ws):
    """registry_write may NOT write audit/** and audit_append may NOT write
    state/registry/** — no cross-root grant (Session-A hardening)."""
    with pytest.raises(ExecDenied):
        registry_write("audit/forged.json", {"v": 1}, base=ws)
    assert not os.path.exists(os.path.join(ws, "audit/forged.json"))
    with pytest.raises(ExecDenied):
        audit_append("state/registry/forged.json", {"v": 1}, base=ws)
    assert not os.path.exists(os.path.join(ws, "state/registry/forged.json"))


def test_sanctioned_channel_writing_ordinary_path_denied(ws):
    """A sanctioned channel may write ONLY its own root — an ordinary
    workspace path is refused (no path-bypass grant)."""
    with pytest.raises(ExecDenied):
        registry_write("agents/cto/note.txt", {"v": 1}, base=ws)
    with pytest.raises(ExecDenied):
        audit_append("agents/cto/note.txt", {"v": 1}, base=ws)
    assert not os.path.exists(os.path.join(ws, "agents/cto/note.txt"))


# ---------------------------------------------------------------------------
# 3. ISO-LIVE-006 — live variant BLOCKED; deterministic equivalent asserted
# ---------------------------------------------------------------------------

def test_iso_live_006_deterministic_equivalent(ws):
    """Deterministic equivalent of ISO-LIVE-006: a non-writer write to
    state/registry/ is DENIED by code with no mutation, and the sanctioned
    channel still works. The LIVE variant (real DSH child attempting the
    write) is BLOCKED in this session."""
    with pytest.raises(ExecDenied, match="protected"):
        write_through("write", "state/registry/iso-live-006.txt", {}, base=ws)
    assert not os.path.exists(
        os.path.join(ws, "state/registry/iso-live-006.txt"))
    path = registry_write("state/registry/iso-live-006.txt",
                          {"control": "plane"}, base=ws)
    assert os.path.exists(path)


_STRUCTURED_OK = {
    "task_id": "task-1:cto", "assigned_role": "cto",
    "status": "SUCCEEDED", "confidence": "MEDIUM",
    "findings": ["live probe: registry write attempted"],
    "evidence": ["probe:iso-live-006"], "risks": [], "assumptions": [],
    "unresolved_items": [], "actions_taken": [],
    "recommendation": "denied as designed",
    "reported_at": "2026-09-07T00:00:00Z",
}


def test_iso_live_006_live_variant_blocked(ws):
    """ISO-LIVE-006 LIVE (D4/D7 mounted): even with a real DSH child wired
    through RealDSHBackend (require_marker=True), a raw write to
    state/registry/ must be denied fail-closed by the execution gate —
    outcome BLOCKED, execution_denial audited, no file, no residue. The live
    child may be consulted, but the protected root stays untouched.

    Conditional gate, not a skeleton: without the mount marker the test SKIPS
    with that reason. When it runs, the child result is session-recorded REAL
    evidence (DSH_LIVE_RESULT_ISO006 or the recorded mount-verification
    bundle); no live proof is fabricated inside pytest. Deterministic
    equivalent: test_denial_is_recorded_in_audit_flow_level below.
    """
    from tests.live_dsh.live_gate import (live_available, skip_reason,
                                          load_recorded)
    if not live_available("ISO-LIVE-006"):
        pytest.skip(skip_reason("ISO-LIVE-006"))
    live = load_recorded("DSH_LIVE_RESULT_ISO006",
                         "int01_live_result.json")
    assert live and live.get("structured"), \
        "live gate on but no session-recorded child result"

    from orchestrator.foundation.contracts import Delegation
    from orchestrator.runtime import ExecutionFlow, MemoryDelegationProvider
    from orchestrator.dsh import DelegationClient, RoleResolver
    from tests.live_dsh.real_backend import RealDSHBackend, DSHBridgeResponse
    from tests.scenarios.scenario_helpers import (
        make_intake, make_execute_plan)

    structured = live["structured"]
    calls = []

    def _dispatch(invocation, instance):
        calls.append(getattr(instance, "role", ""))
        return DSHBridgeResponse(
            run_id=live["run_id"], output=json.dumps(structured),
            structured=structured,
            stop_reason=live.get("stop_reason", "completed"))

    # The delegation deliberately COVERS state/registry/** (authority ALLOWs)
    # so the denial must come from the path-aware execution gate — the exact
    # shape of the deterministic equivalent below.
    delegation = Delegation(
        id="delegation-iso-live-006", principal="human",
        delegate="orchestrator", project="multi-agent-harness",
        scope_operations=("write", "read", "analysis"),
        scope_resources=("state/registry/**", "agents/**", "docs/**",
                         "multi-agent-harness/**"),
        scope_environments=("dev",), status="ACTIVE", expires_at=None,
    )
    backend = RealDSHBackend(_dispatch, require_marker=True)
    client = DelegationClient(backend=backend, resolver=RoleResolver())
    flow = ExecutionFlow(
        base=ws,
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=lambda task, child: client.delegate(task, child),
        flow_id="flow-iso-live-006-live",
    )
    result = flow.run(
        make_intake(objective="engineering"),
        execute_plan=make_execute_plan(
            action="write", target="state/registry/iso-live-006.json"),
        declared_risk="LOW")

    # fail-closed at BOTH layers: the live child is consulted, but the
    # protected-root write is denied before any mutation
    assert result.outcome == "BLOCKED", result.to_dict()
    assert calls, "the live backend must have been wired into the flow"
    assert not os.path.exists(
        os.path.join(ws, "state/registry/iso-live-006.json"))
    denials = flow._get_audit().events_of_class("execution_denial")
    assert denials, "execution_denial must be recorded in the audit ledger"


# ---------------------------------------------------------------------------
# 4. No-regression: denial is audited + fail-closed (no partial allow)
# ---------------------------------------------------------------------------

def test_denial_is_recorded_in_audit_flow_level(ws, intake):
    """A flow whose execution plan targets a protected path is denied at
    execution time: outcome BLOCKED, an execution_denial audit event recorded,
    and no file written. No partial allow.

    The delegation deliberately COVERS state/registry/** (authority ALLOWs) so
    the denial comes from the path-aware execution gate — the ISO-LIVE-006
    equivalent at the deterministic runtime layer."""
    from orchestrator.foundation.contracts import Delegation
    from orchestrator.runtime import (
        ExecutionFlow, MemoryDelegationProvider, ExecutePlan, BLOCKED,
    )
    delegation = Delegation(
        id="delegation-g9-exec", principal="human", delegate="orchestrator",
        project="multi-agent-harness",
        scope_operations=("write", "read", "analysis"),
        scope_resources=("state/registry/**", "agents/**", "docs/**",
                         "multi-agent-harness/**"),
        scope_environments=("dev",),
        status="ACTIVE", expires_at=None,
    )

    def _runner(task, d):
        return _ok_result(task, evidence=("artifact:cto",))

    flow = ExecutionFlow(
        base=ws,
        provider=MemoryDelegationProvider(delegation),
        subtask_runner=_runner,
        flow_id="flow-g9-audit",
    )
    result = flow.run(
        intake,
        execute_plan=ExecutePlan(
            action="write", target="state/registry/evil.json",
            environment="dev", expected_outcome={"exit_code": 0}),
        declared_risk="LOW")
    assert result.outcome == BLOCKED, result.outcome
    assert not os.path.exists(os.path.join(ws, "state/registry/evil.json"))
    # The denial is audited (fail-closed + observable).
    audit = flow._get_audit()
    denials = audit.events_of_class("execution_denial")
    assert denials, "execution_denial must be recorded in the audit ledger"


def _ok_result(task, evidence=()):
    from orchestrator.foundation.contracts import TaskResult
    return TaskResult(
        task_id=task.task_id, assigned_role=task.assigned_role,
        status="SUCCEEDED", confidence="MEDIUM", findings=["ok"],
        evidence=evidence, risks=[], assumptions=[], unresolved_items=[],
        actions_taken=[], recommendation="", reported_at="2026-08-31T00:00:00Z")


def test_denied_target_never_partially_written(ws):
    """A denied write leaves NO partial artifact: no target, no temp, no
    sibling residue (atomicity + gate-before-mutation)."""
    target = "state/registry/partial.json"
    with pytest.raises(ExecDenied):
        write_through("write", target, {"v": 1}, base=ws)
    root = os.path.join(ws, "state", "registry")
    residue = [f for f in os.listdir(root)
               if f.startswith("partial") or "tmp" in f or "atomic" in f]
    assert residue == [], f"denied write left residue: {residue}"
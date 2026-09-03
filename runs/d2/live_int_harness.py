#!/usr/bin/env python3
# runs/d2/live_int_harness.py — Phase 3 / Session D2 LIVE evidence harness
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Drives the EXISTING Phase-3 runtime end-to-end against a real workspace and
# captures ACTUAL runtime evidence on disk:
#
#   INT-01  Full live lifecycle through orchestrator.runtime.ExecutionFlow
#           (INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT →
#            DELEGATE → EXECUTE_SUBTASKS [DSH DelegationClient] → COLLECT →
#            EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE → ADVERSARIAL_REVIEW →
#            AUTHORITY_GATE → EXECUTE → VERIFY → CLOSE)
#
#   INT-07  Execution-time authority re-check: delegation valid at planning,
#           revoked (file registry) between planning and execution → execution
#           must DENY with no unauthorized mutation.
#
# Evidence is captured from RUNTIME ARTIFACTS (project state file, audit
# ledger, delegation registry, gate records, files written) — never from agent
# prose.
#
# No DSH core, profile, preset, session policy, tool mount, or tool enablement
# is touched. The specialist subtask path is the EXISTING dsh DelegationClient
# (D4/D7 approved RoleResolver composition) with the deterministic backend that
# models the DSH tool-subagent contract (the only backend shipped in this
# phase; live-session bridge mounting remains HUMAN_PENDING per ADR 4/7).

from __future__ import annotations

import json
import os
import shutil
import sys
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import TaskIntake
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, COMPLETE, BLOCKED,
)
from orchestrator.dsh import (
    DelegationClient, FakeSubagentBackend, DelegationResult, RoleResolver,
)
from control.delegation import create_delegation
from control.execution_gate import registry_write
from state.helpers.atomic_write import safe_read

RUNS = os.path.dirname(os.path.abspath(__file__))


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_cb():
    return time.time()


# ---------------------------------------------------------------------------
# Workspace + registry seeding (real files, sanctioned channels)
# ---------------------------------------------------------------------------

def make_workspace(ws: str) -> str:
    ws = os.path.abspath(ws)
    if os.path.exists(ws):
        shutil.rmtree(ws)
    for sub in ("state/registry", "state/projects", "audit",
                "agents/cto", "docs"):
        os.makedirs(os.path.join(ws, sub), exist_ok=True)
    return ws


def seed_delegation(ws: str, delegation) -> str:
    """Write the ACTIVE delegation into the protected registry via the
    sanctioned single-writer channel (registry_write, ADR 0002)."""
    doc = delegation.to_dict()
    return registry_write("state/registry/delegations.json", doc, base=ws)


def revoke_delegation(ws: str, delegation_id: str) -> str:
    """Append a revocation to the protected registry via the sanctioned
    single-writer channel. This is the INT-07 'revoke before execution'."""
    return registry_write(
        "state/registry/revocations.json",
        {"revoked": [delegation_id]}, base=ws)


def make_delegation(task_id="d2", *, did="delegation-d2-int01"):
    return create_delegation(
        id=did, principal="human", delegate="orchestrator",
        project="multi-agent-harness", task=task_id,
        action="write", target="agents/**", environment="dev",
        scope_operations=("write", "read", "code_write"),
        scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        scope_environments=("dev",),
    )


def make_intake(*, authority_ctx="delegation-d2-int01"):
    return TaskIntake(
        objective="engineering",
        scope=("agents/**",),
        expected_outcome="module written and verified",
        required_authority_context=authority_ctx,
    )


def make_plan(target="agents/cto/output.txt"):
    return ExecutePlan(
        action="write", target=target, environment="dev",
        expected_outcome={"exit_code": 0},
        action_category="code_change",
        description="write synthesis artifact through the execution gate",
    )


def make_specialist_runner(*, role="cto", findings=None, evidence=None):
    """The EXISTING dsh DelegationClient path (RoleResolver D4/D7 composition
    + build_task_context + scope containment + TaskResultCollector + provenance)
    backed by the deterministic FakeSubagentBackend, scripted to return a
    schema-valid structured TaskResult with evidence."""
    backend = FakeSubagentBackend()

    def _handler(instance, prompt):
        return DelegationResult(
            output="done",
            structured={
                "task_id": prompt.get("task_id", ""),
                "assigned_role": instance.role,
                "status": "SUCCEEDED",
                "confidence": "MEDIUM",
                "findings": list(findings or (f"{instance.role}: analysis",)),
                "evidence": list(evidence or ("artifact:cto:analysis",)),
                "recommendation": "write module",
                "reported_at": _stamp(),
            })

    backend.register(f"subagent_{role}", _handler)
    client = DelegationClient(backend=backend, resolver=RoleResolver())

    def _runner(task, delegation):
        return client.delegate(task, delegation)

    return _runner


# ---------------------------------------------------------------------------
# Evidence capture helpers
# ---------------------------------------------------------------------------

def snapshot(ws: str, flow, result, out_dir: str, extra: dict | None = None) -> dict:
    """Capture runtime artifacts from the real workspace + FlowResult."""
    os.makedirs(out_dir, exist_ok=True)
    audit = flow._get_audit()
    state_path = os.path.join(ws, "state/projects/multi-agent-harness.json")
    reg_path = os.path.join(ws, "state/registry/delegations.json")
    rev_path = os.path.join(ws, "state/registry/revocations.json")

    audit_events = audit.read()
    state_doc = safe_read(state_path) or {}
    reg_doc = safe_read(reg_path)
    rev_doc = safe_read(rev_path) or {}

    evidence = {
        "captured_at": _stamp(),
        "flow_id": result.flow_id,
        "task_id": result.task_id,
        "outcome": result.outcome,
        "phase": result.phase,
        "final_state": result.final_state,
        "version": result.version,
        "risk": result.risk,
        "selected": list(result.selected),
        "gates": list(result.gates),
        "steps": list(result.steps),
        "delegations": list(result.delegations),
        "results": list(result.results),
        "verification": dict(result.verification),
        "files_written": list(result.files_written),
        "errors": list(result.errors),
        "audit_ids": list(result.audit_ids),
        "synthesis": dict(result.synthesis),
        "audit_event_classes": [e.get("event_class") for e in audit_events],
        "audit_execution_denials": [
            e for e in audit_events if e.get("event_class") == "execution_denial"
        ],
        "audit_authority_gate": [
            e for e in audit_events if e.get("event_class") == "gate_authority"
        ],
        "state_doc": state_doc,
        "registry_delegation": reg_doc,
        "registry_revocations": rev_doc,
        "output_exists": os.path.exists(
            os.path.join(ws, "agents/cto/output.txt")),
    }
    if extra:
        evidence.update(extra)

    with open(os.path.join(out_dir, "evidence.json"), "w") as f:
        json.dump(evidence, f, indent=2, default=str)
    with open(os.path.join(out_dir, "flow_result.json"), "w") as f:
        json.dump(result.to_dict(), f, indent=2, default=str)
    with open(os.path.join(out_dir, "audit_events.jsonl"), "w") as f:
        for e in audit_events:
            f.write(json.dumps(e, default=str) + "\n")
    if os.path.exists(os.path.join(ws, "agents/cto/output.txt")):
        with open(os.path.join(out_dir, "written_output.txt"), "w") as f:
            f.write(safe_read(os.path.join(ws, "agents/cto/output.txt"))
                    if isinstance(safe_read(os.path.join(ws, "agents/cto/output.txt")), str)
                    else json.dumps(safe_read(os.path.join(ws, "agents/cto/output.txt")),
                                    default=str))
    return evidence


def write_report(evidence_int01: dict, evidence_int07: dict,
                 int07_extra: dict | None = None) -> str:
    report = {
        "milestone": "PHASE 3 / SESSION D2 — LIVE DSH INTEGRATION (INT-01 + INT-07)",
        "status": "RUN",
        "captured_at": _stamp(),
        "runtime": {
            "execution_flow": "orchestrator.runtime.ExecutionFlow",
            "dsh_adapter": "orchestrator.dsh.DelegationClient (D4/D7 RoleResolver)",
            "specialist_backend": "FakeSubagentBackend (deterministic DSH tool-subagent contract model)",
            "execution_engine": "orchestrator.execution.ExecutionEngine",
            "gates": "control.* via runtime GateRunner",
            "state": "state/projects via RuntimeStore (execution-gate write channel)",
            "audit": "audit/<project>/events.jsonl via RuntimeAudit (sanctioned channel)",
            "registry": "state/registry via FileDelegationProvider",
        },
        "INT-01": evidence_int01,
        "INT-07": evidence_int07,
    }
    if int07_extra:
        report["INT-07_variants"] = int07_extra
    path = os.path.join(RUNS, "report.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# INT-01 — full live lifecycle
# ---------------------------------------------------------------------------

def run_int01() -> dict:
    ws = make_workspace(os.path.join(RUNS, "workspace-int01"))
    delegation = make_delegation(did="delegation-d2-int01")
    seed_delegation(ws, delegation)

    flow = ExecutionFlow(
        project="multi-agent-harness",
        base=ws,
        flow_id=f"flow-d2-int01-{int(time.time())}",
        subtask_runner=make_specialist_runner(role="cto"),
        # FileDelegationProvider is the default when base is set.
    )
    result = flow.run(make_intake(authority_ctx="delegation-d2-int01"),
                      execute_plan=make_plan())
    out_dir = os.path.join(RUNS, "int01")
    ev = snapshot(ws, flow, result, out_dir)
    ev["assert_outcome_complete"] = (result.outcome == COMPLETE)
    ev["assert_final_state_complete"] = (result.final_state == "COMPLETE")
    ev["assert_output_written"] = ev["output_exists"]
    ev["pass"] = (ev["assert_outcome_complete"]
                  and ev["assert_final_state_complete"]
                  and ev["assert_output_written"])
    print(f"[INT-01] outcome={result.outcome} final_state={result.final_state} "
          f"output_written={ev['output_exists']} PASS={ev['pass']}")
    return ev


# ---------------------------------------------------------------------------
# INT-07 — execution-time authority re-check (revoke between plan and exec)
# ---------------------------------------------------------------------------

def run_int07_revoke() -> dict:
    ws = make_workspace(os.path.join(RUNS, "workspace-int07"))
    delegation = make_delegation(did="delegation-d2-int07")
    seed_delegation(ws, delegation)

    flow = ExecutionFlow(
        project="multi-agent-harness",
        base=ws,
        flow_id=f"flow-d2-int07-{int(time.time())}",
        subtask_runner=make_specialist_runner(role="cto"),
    )

    def _revoke_before_execute():
        # Called immediately before the EXECUTE phase re-checks authority
        # (execution-time re-check is MANDATORY — AUTH-INV-05/06).
        revoke_delegation(ws, "delegation-d2-int07")

    flow.pre_execute = _revoke_before_execute
    result = flow.run(make_intake(authority_ctx="delegation-d2-int07"),
                      execute_plan=make_plan())
    out_dir = os.path.join(RUNS, "int07")
    ev = snapshot(ws, flow, result, out_dir)
    ev["assert_denied_at_execution"] = (result.outcome == BLOCKED)
    ev["assert_no_unauthorized_mutation"] = (not ev["output_exists"])
    ev["assert_execution_denial_audited"] = bool(ev["audit_execution_denials"])
    ev["pass"] = (ev["assert_denied_at_execution"]
                  and ev["assert_no_unauthorized_mutation"]
                  and ev["assert_execution_denial_audited"])
    print(f"[INT-07] outcome={result.outcome} final_state={result.final_state} "
          f"output_written={ev['output_exists']} "
          f"denial_audited={ev['assert_execution_denial_audited']} PASS={ev['pass']}")
    return ev


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("== Phase 3 / Session D2 — LIVE DSH INTEGRATION (INT-01 + INT-07) ==")
    int01 = run_int01()
    int07 = run_int07_revoke()
    report_path = write_report(int01, int07)
    print(f"\nEvidence written under {RUNS}/")
    print(f"Report: {report_path}")
    print(f"INT-01 PASS: {int01['pass']}")
    print(f"INT-07 PASS: {int07['pass']}")
    return 0 if (int01["pass"] and int07["pass"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

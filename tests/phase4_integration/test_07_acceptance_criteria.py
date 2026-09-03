# P4I-07 — Phase-4 acceptance criteria (deterministic-runtime portions)
#
# Executable assertions for each Phase-4 acceptance matrix row that is
# reachable in the deterministic runtime. Live-DSH rows (RDE-1, VER-2, L3-1,
# L3-2) and Human-dependent rows are BLOCKED and are explicitly NOT asserted.
#
# Deterministic runtime only. No live DSH. No L3 claim.
#
# Source: docs/phase-4/0001-acceptance-matrix.md, reconciled per
# docs/phase-4/0002-acceptance-baseline-reconciliation.md

import os

import pytest

from tests.phase4_integration.helpers import (
    make_delegation, make_subtask_result, StubSubtaskRunner,
    StubActionExecutor, audit_classes, make_workspace,
)

# Rows that are BLOCKED at the deterministic level (documented, not asserted).
BLOCKED_ROWS = ("RDE-1", "VER-2", "L3-1", "L3-2", "L3-4", "ISO-LIVE-006")


class TestAcceptanceCriteria:
    """P4I-07: parameterised executable acceptance criteria."""

    # ---- AEF-1: full lifecycle ------------------------------------------

    def test_aef1_full_lifecycle_complete(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        assert state.outcome == "complete"
        assert state.flow_result["final_state"] == "COMPLETE"
        assert os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    # ---- AEF-2: bounded autonomy (fail-closed) ---------------------------

    def test_aef2_fail_closed_on_denial(self, ws):
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        delegation = make_delegation(scope_operations=("read",))
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, subtask_runner=sr,
                parallel_subtasks=False)
            assert False, "expected denial"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    # ---- AEF-3: minimum specialist set -----------------------------------

    def test_aef3_minimum_specialist_set(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        assert state.flow_result["selected"] == ["cto"]

    # ---- AEF-4 / REC-2: no blind retry -----------------------------------

    def test_aef4_no_blind_retry(self, ws):
        from orchestrator.production import (
            ProductionDenied, ProductionEscalated, BoundedExecutor,
        )
        from orchestrator.production.planner import ObjectivePlanner
        delegation = make_delegation()
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")
        ex = BoundedExecutor(base=ws, subtask_runner=sr,
                             executor=lambda p: {"exit_code": 1,
                                                 "target": "agents/cto/output.txt"})
        try:
            ex.execute(plan, delegation=delegation)
        except (ProductionDenied, ProductionEscalated):
            pass
        flow = ex.last_flow
        try:
            ex.recover(flow, cause="", failure_class="environment")
            assert False, "expected empty-cause retry refused"
        except ProductionDenied as e:
            assert "no blind retry" in str(e).lower()

    # ---- VER-1: verification before COMPLETE -----------------------------

    def test_ver1_verification_before_complete(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        ver = state.flow_result["verification"]
        assert ver["verdict"] == "PASSED"
        assert state.flow_result["final_state"] == "COMPLETE"

    # ---- VER-3: evidence kind sufficiency ---------------------------------

    def test_ver3_evidence_kinds_present(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        state = ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        detail = state.flow_result["verification"]["detail"]
        required = detail.get("required_evidence", [])
        evidence = detail.get("evidence", [])
        # At least one artifact per required kind is present.
        kinds = {e["kind"] for e in evidence}
        for kind in required:
            assert kind in kinds, f"missing evidence kind {kind}"

    # ---- PAR-1: parallel execution ----------------------------------------

    def test_par1_parallel_execution(self, ws):
        from orchestrator.production import ProductionRun
        delegation = make_delegation(
            id="delegation-price-par1",
            scope_operations=("write", "read", "code_write", "analysis"),
            scope_resources=("docs/**", "agents/**", "multi-agent-harness/**"))
        sr = StubSubtaskRunner()
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:cfo",)))
        sr.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            evidence=("artifact:kai",)))
        state = ProductionRun(base=ws).run(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-par1",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=True, max_workers=4)
        assert state.outcome == "complete"
        assert state.flow_result["parallel"]["safe"] is True
        assert state.flow_result["parallel"]["mode"] == "parallel"

    # ---- PAR-2: parallel safety -------------------------------------------

    def test_par2_parallel_safety(self):
        from orchestrator.foundation.contracts import Task
        from orchestrator.runtime import build_plans, assert_parallel_safe, \
            ParallelUnsafe
        t1 = Task(task_id="t-1", objective="pricing", assigned_role="cfo")
        t2 = Task(task_id="t-1", objective="research", assigned_role="kai")
        with pytest.raises(ParallelUnsafe, match="exclusive"):
            assert_parallel_safe(build_plans([t1, t2]))

    # ---- PAR-3: state version control --------------------------------------

    def test_par3_state_version_control(self, ws):
        from orchestrator.production import ProductionRun
        delegation = make_delegation(
            id="delegation-price-par3",
            scope_operations=("write", "read", "code_write", "analysis"),
            scope_resources=("docs/**", "agents/**", "multi-agent-harness/**"))
        sr = StubSubtaskRunner()
        sr.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            evidence=("artifact:cfo",)))
        sr.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            evidence=("artifact:kai",)))
        state = ProductionRun(base=ws).run(
            objective="pricing strategy for launch",
            scope=("docs/report.md",),
            required_authority_context="delegation-price-par3",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=True, max_workers=4)
        # The parallel batch held a version and preserved it.
        held = state.flow_result["parallel"].get("held_version", 0)
        assert held >= 1
        # No version_conflict audit event (no uncontrolled write).
        classes = audit_classes(ws)
        assert "version_conflict" not in classes

    # ---- AUD-1: append-only audit -------------------------------------------

    def test_aud1_audit_ledger(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        classes = audit_classes(ws)
        assert "flow_finished" in classes
        assert "state_complete" in classes

    # ---- AUD-3: audit is never authority ------------------------------------

    def test_aud3_audit_never_authority(self, ws, delegation):
        from orchestrator.production import ProductionRun
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        ProductionRun(base=ws).run(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001",
            delegation=delegation, subtask_runner=sr,
            parallel_subtasks=False)
        import observability as obs
        idx = obs.build_index_from_ledger(base=ws, project="multi-agent-harness")
        assert idx.ledger_integrity["audit_is_authority_source"] is False

    # ---- AUTH-1: execution-time authority re-check -------------------------

    def test_auth1_execution_time_recheck(self, ws):
        from orchestrator.runtime import MemoryDelegationProvider
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, provider=provider,
                subtask_runner=sr,
                pre_execute=lambda: provider.revoke(delegation.id),
                parallel_subtasks=False)
            assert False, "expected revocation denial"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        assert "execution_denial" in audit_classes(ws)

    # ---- AUTH-2: revoked delegation DENY ------------------------------------

    def test_auth2_revoked_denied(self, ws):
        from orchestrator.runtime import MemoryDelegationProvider
        from orchestrator.production import (
            ProductionRun, ProductionDenied, ProductionEscalated,
            ProductionStopped,
        )
        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        provider.revoke(delegation.id)  # revoked before run
        sr = StubSubtaskRunner()
        sr.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        try:
            ProductionRun(base=ws).run(
                objective="engineering", scope=("agents/cto/output.txt",),
                required_authority_context="delegation-prod-001",
                delegation=delegation, provider=provider,
                subtask_runner=sr, parallel_subtasks=False)
            assert False, "expected revocation denial"
        except (ProductionDenied, ProductionEscalated, ProductionStopped):
            pass
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    # ---- PB-1: fail-closed baseline (protected path) ------------------------

    def test_pb1_protected_path_fail_closed(self, ws):
        from control.execution_gate import authorize_write, Denied as ExecDenied
        with pytest.raises(ExecDenied, match="protected"):
            authorize_write("write", "state/registry/x.json", base=ws)
        assert not os.path.exists(os.path.join(ws, "state/registry/x.json"))

    # ---- PB-4: sanctioned channel cannot cross roots ------------------------

    def test_pb4_sanctioned_channel_scope(self, ws):
        from control.execution_gate import (
            registry_write, audit_append, Denied as ExecDenied,
        )
        # registry_write may only write state/registry/**
        with pytest.raises(ExecDenied):
            registry_write("audit/hack.json", {"x": 1}, base=ws)
        # audit_append may only write audit/**
        with pytest.raises(ExecDenied):
            audit_append("state/registry/x.json", {"x": 1}, base=ws)
        assert not os.path.exists(os.path.join(ws, "audit/hack.json"))
        assert not os.path.exists(os.path.join(ws, "state/registry/x.json"))

    # ---- Honesty: BLOCKED rows are not asserted -----------------------------

    def test_blocked_rows_documented(self):
        # The rows that cannot be executed in the deterministic runtime are
        # named and excluded — no test fabricates their evidence.
        assert "RDE-1" in BLOCKED_ROWS
        assert "VER-2" in BLOCKED_ROWS
        assert "L3-1" in BLOCKED_ROWS
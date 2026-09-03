# PROD-09 — Stale state
#
# When the project state version advances between planning and execution
# (a concurrent writer), the flow refuses the stale plan (THREAT-021/022,
# REC-005). The production run stops fail-closed.
#
# Tests: PAR-3, THREAT-021/022

from conftest import make_delegation, make_subtask_result

from orchestrator.runtime import (
    MemoryDelegationProvider, RuntimeStore, StaleStateDetected,
)
from orchestrator.production import (
    ProductionDenied, ProductionEscalated, BoundedExecutor,
)
from orchestrator.production.planner import ObjectivePlanner


class TestStaleState:
    def test_stale_state_blocks_execution(self, ws, subtask_runner,
                                          action_executor):
        """State version drift before execute → StaleStateDetected → stop."""
        delegation = make_delegation()
        provider = MemoryDelegationProvider(delegation)
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        # pre_execute simulates a concurrent writer that bumps the state
        # version (a parallel worker).
        def bump_version():
            from control.execution_gate import project_write
            from orchestrator.runtime.store import encode_project_state
            from orchestrator.foundation.state import ProjectState
            store = RuntimeStore(base=ws)
            ps = store.load_project_state()
            ps.version += 1  # simulate another writer advancing state
            project_write(store.state_rel, encode_project_state(ps),
                          base=store.base, expected_version=ps.version - 1)

        plan = ObjectivePlanner().plan(
            objective="engineering", scope=("agents/cto/output.txt",),
            required_authority_context="delegation-prod-001")

        ex = BoundedExecutor(base=ws, subtask_runner=subtask_runner,
                             executor=action_executor)
        raised = False
        try:
            ex.execute(plan, delegation=delegation, provider=provider,
                       pre_execute=bump_version)
        except ProductionDenied as e:
            raised = True
            assert "stale" in str(e).lower() or "version" in str(e).lower() \
                or "stopped" in str(e).lower()
        except ProductionEscalated as e:
            raised = True
        assert raised, "expected stale state to stop the flow"

        flow = ex.last_flow
        assert flow is not None
        assert flow._result.outcome == "BLOCKED"
        assert len(flow._result.files_written) == 0
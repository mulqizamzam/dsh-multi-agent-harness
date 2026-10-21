# tests/live_dsh/test_cleanup.py — run cleanup + dispose on the REAL bridge path
#
# The bridge must release every run (dispose idempotent), mirroring the DSH
# one-shot run contract (types.ts SubagentRun.dispose()).

from .real_backend import RealDSHBackend, DSHBridgeResponse
from .contract import STOP_COMPLETED
from .conftest import make_task, make_delegation


def _instance(role="cto"):
    from orchestrator.dsh.resolver import SubagentInstance
    return SubagentInstance(role=role, tool_name="subagent",
                            agent_preset=f"role-{role}")


class TestCleanup:
    def test_dispose_is_idempotent(self):
        """dispose() may be called more than once without error."""
        task = make_task(role="cto")

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(run_id="r1", output="ok",
                                     stop_reason=STOP_COMPLETED)

        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(_instance("cto"), {"task_id": task.task_id})
        run.dispose()
        run.dispose()  # idempotent

    def test_child_registered_after_start(self):
        """A started run is enumerated as a child (durable discovery seam)."""
        task = make_task(role="cto")

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(run_id="r-abc", output="ok",
                                     stop_reason=STOP_COMPLETED)

        backend = RealDSHBackend(_dispatch, require_marker=False)
        run = backend.start(_instance("cto"), {"task_id": task.task_id})
        children = backend.list_children("orchestrator-root")
        assert any(c["tool_name"] == "subagent_cto" for c in children)
        assert run.run_id == "r-abc"

    def test_interrupt_marks_child(self):
        """interrupt() marks the child and fires the signal."""
        import threading
        task = make_task(role="cto")

        def _dispatch(invocation, instance):
            return DSHBridgeResponse(run_id="r-int", output="ok",
                                     stop_reason=STOP_COMPLETED)

        backend = RealDSHBackend(_dispatch, require_marker=False)
        backend.start(_instance("cto"), {"task_id": task.task_id})
        signal = threading.Event()
        backend.interrupt("r-int", signal)
        assert signal.is_set()
        assert backend.children()["r-int"]["status"] == "interrupt-requested"
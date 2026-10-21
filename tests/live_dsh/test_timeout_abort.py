# tests/live_dsh/test_timeout_abort.py — timeout/abort handling on the REAL bridge path
#
# The bridge contract must propagate timeout and abort exactly like the
# existing adapter: a child that overruns its budget or is cancelled STOPS the
# flow fail-closed — never a partial success.

import pytest

from orchestrator.dsh import (
    DelegationTimeout, DelegationAborted,
)
from .real_backend import RealDSHBackend, DSHBridgeResponse
from .contract import STOP_ABORTED, BuildInvocation
from .conftest import make_task, make_delegation


def _instance(role="cto"):
    from orchestrator.dsh.resolver import SubagentInstance
    return SubagentInstance(role=role, tool_name="subagent",
                            agent_preset=f"role-{role}")


class TestTimeoutAbort:
    def test_bridge_timeout_propagates(self):
        """A dispatch that raises DelegationTimeout propagates the typed
        exception (tool-call budget exceeded)."""
        task = make_task(role="cto")
        delegation = make_delegation(task=task.task_id)

        def _dispatch(invocation, instance):
            raise DelegationTimeout("subagent exceeded its tool-call budget")

        backend = RealDSHBackend(_dispatch, require_marker=False)
        with pytest.raises(DelegationTimeout):
            backend.start(_instance("cto"), {"task_id": task.task_id})

    def test_bridge_aborted_stop_reason_is_failure(self):
        """A settled stopReason 'aborted' maps to a failure outcome — never
        success (partial output is not a result)."""
        from .contract import map_stop_reason_to_outcome
        o = map_stop_reason_to_outcome(STOP_ABORTED)
        assert o["succeeded"] is False
        assert "cancelled" in o["error"]

    def test_pre_start_signal_aborts(self):
        """A signal already set before start aborts the delegation."""
        import threading
        task = make_task(role="cto")
        signal = threading.Event()
        signal.set()
        backend = RealDSHBackend(None, require_marker=False)
        with pytest.raises(RuntimeError):
            backend.start(_instance("cto"), {"task_id": task.task_id},
                          signal=signal)

    def test_aborted_classification(self):
        from .contract import map_stop_reason_to_failure
        cls, _ = map_stop_reason_to_failure(STOP_ABORTED)
        assert cls == "environment"

    def test_max_tokens_is_failure(self):
        from .contract import (STOP_MAX_TOKENS, map_stop_reason_to_outcome,
                               map_stop_reason_to_failure)
        o = map_stop_reason_to_outcome(STOP_MAX_TOKENS)
        assert o["succeeded"] is False
        assert map_stop_reason_to_failure(STOP_MAX_TOKENS)[0] == "environment"
# E-12 — Unexpected exception → ERROR
#
# Prove that an unexpected exception anywhere in the front-door path is
# caught and surfaced as a deterministic ERROR status (fail-closed), never a
# fabricated success, and never a partial run leaking as COMPLETE.

from orchestrator.runtime import DelegationProvider

from _helpers import make_delegation, make_provider

from orchestrator.entrypoint import (
    ERROR,
    COMPLETE,
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
)


class _ExplodingProvider(DelegationProvider):
    """A real DelegationProvider whose current() raises unexpectedly."""

    def current(self):
        raise RuntimeError("registry exploded")


class TestUnexpectedException:
    def test_exception_in_registry_read_maps_to_error(self, ws):
        """An unexpected exception during delegation resolution → ERROR."""
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=_ExplodingProvider(),
        )
        assert result.status == ERROR, f"expected ERROR, got {result.status}"
        assert "unexpected" in " ".join(result.errors).lower()
        assert not result.run_id
        assert result.state is None

    def test_exception_in_subtask_maps_to_error_or_blocked(self, ws):
        """An unexpected exception during execution is contained by the
        production run's fail-closed path (never a fabricated COMPLETE)."""
        delegation = make_delegation()
        provider = make_provider(delegation)

        def boom_runner(task, delegation):
            raise RuntimeError("unexpected child failure")

        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=provider,
            subtask_runner=boom_runner,
            action_executor=lambda plan: {"exit_code": 0,
                                           "target": "agents/cto/output.txt"},
        )
        # The flow routes child failure to recovery (RECOVERING → Production
        # layer maps to ESCALATED/BLOCKED); never COMPLETE.
        assert result.status != COMPLETE
        assert result.status in (ERROR, BLOCKED, "ESCALATED")

    def test_error_never_fabricates_report(self, ws):
        """An ERROR result never carries a fabricated report/state."""
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            base=ws,
            ),
            provider=_ExplodingProvider(),
        )
        assert result.status == ERROR
        assert result.report is None
        assert result.state is None
# E-02 — Empty objective → ERROR
#
# Prove that an empty (missing/blank) objective is rejected at shape
# validation with no delegation resolution, no ProductionRun created, and
# no authority consumed.

from _helpers import make_delegation

from orchestrator.entrypoint import (
    ERROR,
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
    FrontDoorError,
)


class TestEmptyObjective:
    def test_empty_string_objective_rejected(self):
        """Empty string objective → FrontDoorError on construction."""
        try:
            FrontDoorRequest(
                objective="",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            )
            assert False, "expected FrontDoorError for empty objective"
        except FrontDoorError as e:
            assert "objective" in str(e).lower()

    def test_blank_objective_rejected(self):
        """Whitespace-only objective → FrontDoorError."""
        try:
            FrontDoorRequest(
                objective="   ",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            )
            assert False, "expected FrontDoorError for blank objective"
        except FrontDoorError as e:
            assert "objective" in str(e).lower()

    def test_none_objective_rejected(self):
        """None as objective → TypeError on construction."""
        try:
            FrontDoorRequest(
                objective=None,  # type: ignore
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            )
            assert False, "expected TypeError for None objective"
        except (TypeError, FrontDoorError):
            pass

    def test_empty_objective_via_run_front_door(self, ws):
        """Empty objective through run_front_door → ERROR, no run created."""
        # Passing None as objective causes TypeError in FrontDoorRequest
        from orchestrator.entrypoint import FrontDoorError
        try:
            request = FrontDoorRequest(
                objective="",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            )
            assert False, "expected FrontDoorError"
        except FrontDoorError:
            pass

    def test_missing_objective_in_dict_via_run_front_door(self, ws):
        """Objective missing from a dict intake → ERROR."""
        result = run_front_door({
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
        })
        assert result.status == ERROR
        assert "objective" in " ".join(result.errors).lower()
        assert not result.run_id
        assert result.state is None
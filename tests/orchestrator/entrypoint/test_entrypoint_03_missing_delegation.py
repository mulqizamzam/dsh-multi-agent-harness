# E-03 — Missing delegation → BLOCKED / ERROR
#
# Prove that a front-door request without a valid delegation_id (empty /
# missing / no matching registry entry) is rejected. The front door NEVER
# creates a delegation, NEVER sets ACTIVE, and NEVER derives authority from
# prose. (AUTH-INV-01/05)

from _helpers import make_delegation, make_provider

from orchestrator.entrypoint import (
    ERROR,
    BLOCKED,
    run_front_door,
    FrontDoorRequest,
    FrontDoorError,
)


class TestMissingDelegation:
    def test_empty_delegation_id_rejected(self):
        """Empty delegation_id → FrontDoorError on construction."""
        try:
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="",
            )
            assert False, "expected FrontDoorError"
        except FrontDoorError as e:
            assert "delegation_id" in str(e).lower()

    def test_none_delegation_id_rejected(self):
        """None delegation_id → TypeError on construction."""
        try:
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id=None,  # type: ignore
            )
            assert False, "expected TypeError"
        except (TypeError, FrontDoorError):
            pass

    def test_blank_delegation_id_rejected(self):
        """Whitespace-only delegation_id → FrontDoorError."""
        try:
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="   ",
            )
            assert False, "expected FrontDoorError"
        except FrontDoorError as e:
            assert "delegation_id" in str(e).lower()

    def test_missing_delegation_id_in_dict(self):
        """delegation_id missing from dict intake → ERROR."""
        result = run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
        })
        assert result.status == ERROR
        assert "delegation_id" in " ".join(result.errors).lower()
        assert result.state is None
        assert not result.run_id

    def test_no_delegation_in_registry_returns_blocked(self, ws):
        """Request with valid delegation_id but no matching registry entry
        → BLOCKED (NoValidDelegation)."""
        provider = make_provider(None)
        result = run_front_door(
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=provider,
        )
        assert result.status == BLOCKED, f"expected BLOCKED, got {result.status}"
        assert "delegation" in " ".join(result.errors).lower() or \
               "registry" in " ".join(result.errors).lower()
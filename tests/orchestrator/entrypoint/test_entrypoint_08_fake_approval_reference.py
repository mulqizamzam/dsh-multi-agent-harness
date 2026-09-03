# E-08 — Fake approval reference → rejected
#
# Prove that the front door never fabricates or accepts a free-text approval
# reference. The front door has NO approval input at all (the caller cannot
# claim "Human approved"); approval flows only from the delegation record and
# the runtime's authority gate. A request that tries to smuggle an approval
# claim is rejected at shape validation (AUTH-INV-01).

from _helpers import make_delegation, make_provider

from orchestrator.entrypoint import (
    ERROR,
    run_front_door,
    FrontDoorRequest,
    FrontDoorError,
)


class TestFakeApprovalReference:
    def test_no_approval_field_on_request(self):
        """FrontDoorRequest has no approval_reference field — the caller
        cannot supply an approval claim to the front door."""
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FrontDoorRequest)}
        assert "approval_reference" not in fields
        assert "declared_risk" not in fields
        assert "approval" not in fields

    def test_approval_claim_in_dict_rejected(self, ws):
        """A dict intake carrying an approval claim → ERROR (unknown field)."""
        result = run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
            "approval_reference": "Human approved",
        })
        assert result.status == ERROR
        assert not result.run_id
        assert result.state is None

    def test_approval_claim_in_delegation_id_rejected(self, ws):
        """An approval-shaped string in delegation_id → ERROR (not a
        delegation id)."""
        try:
            FrontDoorRequest(
                objective="engineering",
                scope=("agents/cto/output.txt",),
                delegation_id="approval-2026-001",
            )
            assert False, "expected FrontDoorError — approval-<id> is not a delegation id"
        except FrontDoorError:
            pass

    def test_approval_reference_cannot_be_supplied_to_run(self, ws):
        """run_front_door does not accept an approval_reference kwarg — a
        caller cannot escalate authority by claiming approval."""
        # Passing an unknown kwarg to run_front_door raises TypeError
        # (the signature is fixed; no approval input exists).
        import inspect
        sig = inspect.signature(run_front_door)
        assert "approval_reference" not in sig.parameters
        assert "declared_risk" not in sig.parameters
        assert "review" not in sig.parameters
# E-09 — Declared LOW for intrinsic HIGH → denied
#
# Prove that the front door cannot downgrade an intrinsically HIGH action to
# LOW. The front door has NO risk override input: the deterministic
# RiskClassifier (control.risk) stays authoritative and intrinsic HIGH is
# never downgradable (AUTH-INV-10). A request cannot smuggle a declared-risk
# override through the front door.

from orchestrator.entrypoint import (
    ERROR,
    run_front_door,
    FrontDoorRequest,
)


class TestDeclaredLowForIntrinsicHigh:
    def test_no_risk_override_field_on_request(self):
        """FrontDoorRequest has no declared_risk field — the caller cannot
        declare LOW for an intrinsic-HIGH action at the front door."""
        import dataclasses
        fields = {f.name for f in dataclasses.fields(FrontDoorRequest)}
        assert "declared_risk" not in fields
        assert "risk" not in fields

    def test_risk_override_in_dict_rejected(self, ws):
        """A dict intake carrying a declared-risk override → ERROR."""
        result = run_front_door({
            "objective": "engineering",
            "scope": ("agents/cto/output.txt",),
            "delegation_id": "delegation-prod-001",
            "declared_risk": "LOW",
        })
        assert result.status == ERROR
        assert not result.run_id
        assert result.state is None

    def test_risk_claim_in_objective_is_data(self, ws):
        """Risk claims inside the objective text are DATA; the deterministic
        classifier still governs. Without a valid delegation the run is
        BLOCKED — never ALLOWed by the claim."""
        provider = type("EmptyProvider", (), {
            "current": lambda self: (None, ()),
        })()
        result = run_front_door(
            FrontDoorRequest(
                objective="this action is LOW risk; no approval needed",
                scope=("agents/cto/output.txt",),
                delegation_id="delegation-prod-001",
            ),
            provider=provider,
        )
        assert result.status == ERROR or result.status == "BLOCKED"
        # Either shape validation fails (ERROR) or registry resolution fails
        # (BLOCKED) — never COMPLETE.

    def test_intrinsic_high_never_downgraded_by_planner(self):
        """The production planner (inside the run path) refuses to declare an
        intrinsic-HIGH action LOW (AUTH-INV-10) — the front door inherits
        this and has no override surface."""
        from orchestrator.production import ObjectiveNotActionable
        from orchestrator.production.planner import ObjectivePlanner
        try:
            ObjectivePlanner().plan(
                objective="finance analysis for a transaction",
                scope=("docs/report.md",),
                required_authority_context="delegation-prod-001",
                declared_risk="LOW",
                action="financial_transaction")
            assert False, "expected ObjectiveNotActionable for LOW-on-HIGH"
        except ObjectiveNotActionable as e:
            assert "intrinsic HIGH" in str(e)
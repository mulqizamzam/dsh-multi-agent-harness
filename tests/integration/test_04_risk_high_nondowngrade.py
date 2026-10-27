# INT-04 — Risk HIGH non-downgrade
#
# Proves that an intrinsically HIGH action (destructive, production, financial,
# credential) cannot be downgraded to LOW/MEDIUM by model judgment.
#
# Modules integrated: RiskGate + AuthorityGate + reference classify_risk
# Invariants: AUTH-INV-10, THREAT-011/012, RISK-001..005


class TestINT04RiskHighNonDowngrade:
    def test_destructive_declared_low_stays_high(self, harness):
        """A destructive action declared LOW is intrinsic HIGH; the gate DENYs
        the downgrade attempt (AUTH-INV-10). detail still carries risk=HIGH
        so the classification is preserved for escalation."""
        dec = harness.evaluate_gate("risk", {"action": "destructive", "risk": "LOW"})
        assert dec.decision == "DENY"  # DENY: intrinsic HIGH declared LOW
        assert dec.detail["risk"] == "HIGH"

    def test_production_deploy_intrinsic_high(self, harness):
        dec = harness.evaluate_gate("risk", {"action": "production_deploy", "risk": "MEDIUM"})
        assert dec.detail["risk"] == "HIGH"

    def test_financial_transaction_intrinsic_high(self, harness):
        dec = harness.evaluate_gate("risk", {"action": "financial_transaction", "risk": "LOW"})
        assert dec.detail["risk"] == "HIGH"

    def test_credential_change_intrinsic_high(self, harness):
        dec = harness.evaluate_gate("risk", {"action": "credential_change", "risk": "LOW"})
        assert dec.detail["risk"] == "HIGH"

    def test_reference_agrees_destructive_high(self, harness):
        """Reference classify_risk also returns HIGH + intrinsic for destructive."""
        cmp = harness.cross_check_risk("destructive", "data/db", "dev")
        assert cmp["reference_risk"] == "HIGH"
        assert cmp["reference_intrinsic"] is True
        assert cmp["match"] is True  # foundation and reference agree

    def test_high_action_requires_authority_and_approval(self, harness):
        """HIGH + requires_approval without approval_reference → ESCALATE."""
        d = harness.build_delegation(
            action="publish", target="docs/**",
            scope_operations=("publish",),
            scope_resources=("docs/**",),
            requires_approval=("sensitive_publication",),
        )
        auth = harness.evaluate_gate("authority", {
            "delegation": d, "action": "publish", "target": "docs/x.md"})
        assert auth.decision == "ESCALATE"  # requires Human approval
        # With an approval reference it can pass
        auth2 = harness.evaluate_gate("authority", {
            "delegation": d, "action": "publish", "target": "docs/x.md",
            "approval_reference": "approval-001"})
        assert auth2.decision == "ALLOW"

    def test_high_action_denied_without_delegation(self, harness):
        """No delegation + HIGH action → DENY."""
        dec = harness.evaluate_gate("authority", {
            "action": "destructive", "target": "data/db"})
        assert dec.decision == "DENY"
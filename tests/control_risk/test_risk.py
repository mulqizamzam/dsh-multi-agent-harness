"""Risk gate tests — AUTH-INV-10, THREAT-011/012, RISK-001..005.

Tests the deterministic risk classifier in control/risk.py:
  - Intrinsic HIGH classification (AUTH-INV-10)
  - Non-downgradable: intrinsic HIGH can never be lowered by model judgment
  - Semantic-laundering resistance: benign wording hiding destructive action
    stays HIGH (THREAT-012)
  - Model-assessed nuance may raise but never lower HIGH (THREAT-011)
  - coverage: production, destructive, financial, credential, publication,
    destructive data operations
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from control.risk import (
    classify_risk,
    RiskClassifier,
    RiskDowngradeAttempted,
    INTRINSIC_HIGH_ACTIONS,
    PROD_ENVIRONMENTS,
    DESTRUCTIVE_FLAGS,
)


class TestIntrinsicHigh:
    """RISK-001..004 — deterministic categories are intrinsically HIGH."""

    @pytest.mark.parametrize("action,target,env", [
        ("deploy", "prod/x", "prod"),
        ("production_deploy", "whatever", "dev"),
        ("production_change", "x", "staging"),
    ])
    def test_risk_001_production_is_high(self, action, target, env):
        cls, intrinsic = classify_risk(action, target, env)
        assert cls == "HIGH" and intrinsic is True

    @pytest.mark.parametrize("action", [
        "destructive", "delete", "drop", "destroy",
    ])
    def test_risk_002_destructive_is_high(self, action):
        cls, intrinsic = classify_risk(action, "data/db", "dev")
        assert cls == "HIGH" and intrinsic is True

    @pytest.mark.parametrize("action", [
        "financial_transaction", "financial_commitment",
        "payment", "wire_transfer",
    ])
    def test_risk_003_financial_is_high(self, action):
        cls, intrinsic = classify_risk(action, "pay/x", "dev")
        assert cls == "HIGH" and intrinsic is True

    @pytest.mark.parametrize("action", [
        "credential_change", "permission_change", "role_grant",
    ])
    def test_risk_004_credential_is_high(self, action):
        cls, intrinsic = classify_risk(action, "auth/config", "dev")
        assert cls == "HIGH" and intrinsic is True

    @pytest.mark.parametrize("action", [
        "sensitive_publication", "publish", "material_publication",
    ])
    def test_risk_004_publication_is_high(self, action):
        cls, intrinsic = classify_risk(action, "x", "dev")
        assert cls == "HIGH" and intrinsic is True

    def test_requires_approval_triggers_high(self):
        cls, intrinsic = classify_risk("write", "x", "dev",
                                        requires_approval=["destructive"])
        assert cls == "HIGH" and intrinsic is True

    def test_prod_env_triggers_high(self):
        for env in PROD_ENVIRONMENTS:
            cls, intrinsic = classify_risk("read", "x", env)
            assert cls == "HIGH" and intrinsic is True, f"env={env}"


class TestNonDowngradable:
    """AUTH-INV-10 / THREAT-011: intrinsic HIGH cannot be lowered by model
    judgment — the classifier itself keeps HIGH regardless of declared level."""

    def test_risk_005_classifier_never_downgrades_intrinsic_high(self):
        """The classifier normalizes declared=LOW on an intrinsic HIGH back to
        HIGH."""
        for action in ("delete", "drop database", "financial_transaction"):
            cls, intrinsic = classify_risk(action, "x", "dev", declared="LOW")
            assert intrinsic is True, f"{action} must be intrinsic HIGH"
            assert cls == "HIGH", f"{action} classified {cls} not HIGH"

    def test_guard_raises_on_downgrade_attempt(self):
        """The assert_non_downgradable guard at the gate boundary raises when
        a caller declares a level below HIGH for an intrinsic action."""
        rc = RiskClassifier()
        with pytest.raises(RiskDowngradeAttempted):
            rc.assert_non_downgradable("LOW", intrinsic=True)

    def test_guard_allows_high_declaration_on_intrinsic(self):
        """Declaring HIGH on an intrinsic HIGH is consistent — no raise."""
        rc = RiskClassifier()
        assert rc.assert_non_downgradable("HIGH", intrinsic=True) == "HIGH"

    def test_guard_allows_any_declaration_on_non_intrinsic(self):
        """For non-intrinsic actions, the guard returns the effective level."""
        rc = RiskClassifier()
        assert rc.assert_non_downgradable("LOW", intrinsic=False) == "LOW"
        assert rc.assert_non_downgradable("MEDIUM", intrinsic=False) == "MEDIUM"

    def test_model_nuance_raises_but_never_lowers(self):
        """Model nuance may raise a classification (LOW→MEDIUM→HIGH) but never
        lowers an intrinsic HIGH."""
        # intrinsic HIGH with MEDIUM nuance → still HIGH
        cls, _ = classify_risk("delete", "x", "dev", model_nuance="MEDIUM")
        assert cls == "HIGH"
        # non-intrinsic LOW with HIGH nuance → raised to HIGH
        cls, _ = classify_risk("read", "x", "dev", model_nuance="HIGH")
        assert cls == "HIGH"


class TestSemanticLaundering:
    """THREAT-012: benign wording hiding a destructive action stays HIGH."""

    def test_update_config_with_delete_flag(self):
        cls, intrinsic = classify_risk(
            "update config", "prod/app/config", "dev",
            operation_flags=["delete"])
        assert cls == "HIGH" and intrinsic is True

    def test_cleanup_command_with_rm_pattern(self):
        cls, intrinsic = classify_risk(
            "clean up stale rows", "dev/db", "dev",
            command="rm -rf /data/important")
        assert cls == "HIGH" and intrinsic is True

    def test_maintenance_with_drop_in_command(self):
        cls, intrinsic = classify_risk(
            "database maintenance", "dev/db", "dev",
            command="drop table users")
        assert cls == "HIGH" and intrinsic is True

    def test_refactor_script_with_delete_flag(self):
        cls, intrinsic = classify_risk(
            "refactor script", "dev/app", "dev",
            operation_flags=["delete", "overwrite"])
        assert cls == "HIGH" and intrinsic is True

    def test_benign_read_stays_low(self):
        cls, intrinsic = classify_risk(
            "read", "multi-agent-harness/README.md", "dev",
            command="cat README.md")
        assert cls == "LOW" and intrinsic is False

    @pytest.mark.parametrize("action,flags", [
        ("update config", ["delete"]),
        ("clean up", ["truncate"]),
        ("rotate logs", ["purge"]),
        ("archive old", ["rm"]),
    ])
    def test_benign_actions_with_destructive_flags(self, action, flags):
        cls, intrinsic = classify_risk(
            action, "dev/data", "dev", operation_flags=flags)
        assert cls == "HIGH" and intrinsic is True, \
            f"{action} with flags {flags} must be HIGH"

    def test_prod_env_alone_makes_write_high(self):
        """A write action in a prod environment is intrinsically HIGH even
        with benign wording."""
        cls, intrinsic = classify_risk(
            "update config", "prod/app/config", "prod")
        assert cls == "HIGH" and intrinsic is True


class TestMediumAndLow:
    """Reference-parity: write-like actions default to MEDIUM; reads to LOW."""

    def test_write_is_medium(self):
        cls, intrinsic = classify_risk("write", "agents/x", "dev")
        assert cls == "MEDIUM" and intrinsic is False

    def test_edit_is_medium(self):
        cls, intrinsic = classify_risk("edit", "agents/x", "dev")
        assert cls == "MEDIUM" and intrinsic is False

    def test_read_is_low(self):
        cls, intrinsic = classify_risk("read", "README.md", "dev")
        assert cls == "LOW" and intrinsic is False

    def test_unknown_action_defaults_to_low(self):
        cls, intrinsic = classify_risk("grep", "x", "dev")
        assert cls == "LOW" and intrinsic is False


class TestEffectiveLevel:
    """effective_level and assert_non_downgradable boundary."""

    def test_effective_level_intrinsic_always_high(self):
        rc = RiskClassifier()
        assert rc.effective_level("LOW", True) == "HIGH"
        assert rc.effective_level("MEDIUM", True) == "HIGH"
        assert rc.effective_level("HIGH", True) == "HIGH"

    def test_effective_level_non_intrinsic(self):
        rc = RiskClassifier()
        assert rc.effective_level("LOW", False) == "LOW"
        assert rc.effective_level("MEDIUM", False) == "MEDIUM"
        assert rc.effective_level("HIGH", False) == "HIGH"

    def test_effective_level_unknown_defaults_low(self):
        rc = RiskClassifier()
        assert rc.effective_level("BOGUS", False) == "LOW"
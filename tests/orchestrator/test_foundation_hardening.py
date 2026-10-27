# ===========================================================================
# Phase 1E Hardening Tests — foundation gate hardening regression guards
#
# These tests verify that the foundation ControlPlane gates (used by the
# workflow skeleton and integration harness) now delegate to the full control-
# plane enforcement modules, closing:
#   - AUTH-INV-11: target containment in AuthorityGate
#   - AUTH-INV-10: intrinsic HIGH non-downgradable in RiskGate
#   - THREAT-011/012: semantic laundering in RiskGate
#   - AUTH-INV-06: revocation re-check in AuthorityGate
# ===========================================================================

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from orchestrator.foundation.gates import ControlPlane, INTRINSIC_HIGH_ACTIONS
from orchestrator.foundation.contracts import Delegation


# ---------------------------------------------------------------------------
# AuthorityGate — AUTH-INV-11 (target containment hardening)
# ---------------------------------------------------------------------------
class TestAuthInv11TargetContainment:
    """The foundation AuthorityGate must DENY targets outside the delegation's
    resource scope (AUTH-INV-11), delegating to control.delegation.target_in_scope
    for the same prefix-boundary matcher the control-plane gate uses."""

    def test_in_scope_target_allowed(self):
        d = Delegation(task="t", action="write", target="agents/**",
                       scope_operations=("write",),
                       scope_resources=("agents/**",))
        dec = ControlPlane().evaluate("authority",
                                       {"delegation": d, "action": "write",
                                        "target": "agents/cto/policy.yaml",
                                        "actor": "orchestrator"})
        assert dec.decision == "ALLOW"

    def test_out_of_scope_target_denied(self):
        d = Delegation(task="t", action="write", target="agents/**",
                       scope_operations=("write",),
                       scope_resources=("agents/**",))
        dec = ControlPlane().evaluate("authority",
                                       {"delegation": d, "action": "write",
                                        "target": "audit/evil.json",
                                        "actor": "orchestrator"})
        assert dec.decision == "DENY"
        assert "AUTH-INV-11" in dec.reason

    def test_sibling_prefix_confusion_denied(self):
        """`agents/**` must NOT match `agents-evil/...` (sibling prefix confusion)."""
        d = Delegation(task="t", action="write", target="agents/**",
                       scope_operations=("write",),
                       scope_resources=("agents/**",))
        dec = ControlPlane().evaluate("authority",
                                       {"delegation": d, "action": "write",
                                        "target": "agents-evil/payload",
                                        "actor": "orchestrator"})
        assert dec.decision == "DENY"
        assert "AUTH-INV-11" in dec.reason

    def test_no_target_in_context_skips_containment(self):
        """When context has no target, the gate does not falsely deny via
        target containment (read-only / umbrella delegations)."""
        d = Delegation(task="t", action="publish", target="social/**",
                       scope_operations=("publish",),
                       scope_resources=("social/**",),
                       requires_approval=("sensitive_publication",))
        dec = ControlPlane().evaluate("authority",
                                       {"delegation": d, "action": "publish"})
        assert dec.decision == "ESCALATE"
        assert "approval" in dec.reason


# ---------------------------------------------------------------------------
# AuthorityGate — AUTH-INV-06 (revocation hardening)
# ---------------------------------------------------------------------------
class TestAuthInv06Revocation:
    """The foundation AuthorityGate must DENY revoked delegations at execution
    time (AUTH-INV-06)."""

    def test_revoked_delegation_denied(self):
        d = Delegation(task="t", action="write", target="agents/**",
                       scope_operations=("write",),
                       scope_resources=("agents/**",))
        dec = ControlPlane().evaluate("authority",
                                       {"delegation": d, "action": "write",
                                        "target": "agents/x.py", "actor": "orchestrator",
                                        "revocation_list": (d.id,)})
        assert dec.decision == "DENY"
        assert "revoked" in dec.reason


# ---------------------------------------------------------------------------
# RiskGate — AUTH-INV-10 (non-downgradable HIGH hardening)
# ---------------------------------------------------------------------------
class TestRiskGateHardening:
    """The foundation RiskGate must DENY intrinsic-high actions declared LOW
    (AUTH-INV-10), delegating to control.risk.RiskClassifier."""

    def test_destructive_declared_low_denied(self):
        dec = ControlPlane().evaluate("risk",
                                      {"action": "destructive", "declared": "LOW"})
        assert dec.decision == "DENY"
        assert dec.detail["risk"] == "HIGH"
        assert dec.detail["intrinsic"] is True

    def test_destructive_declared_high_allows(self):
        dec = ControlPlane().evaluate("risk",
                                      {"action": "destructive", "declared": "HIGH"})
        assert dec.decision == "ALLOW"
        assert dec.detail["risk"] == "HIGH"
        assert dec.detail["intrinsic"] is True

    def test_rm_declared_low_denied(self):
        """`rm` was NOT in the old foundation INTRINSIC_HIGH_ACTIONS set (only 6
        actions); the expanded set now includes it — semantic laundering
        resistance."""
        dec = ControlPlane().evaluate("risk",
                                      {"action": "rm", "declared": "LOW"})
        assert dec.decision == "DENY"
        assert "action:rm" in dec.detail.get("signals", [])

    def test_production_environment_declared_low_denied(self):
        """Environment-based HIGH classification (THREAT-011)."""
        dec = ControlPlane().evaluate("risk",
                                      {"action": "write", "target": "x",
                                       "environment": "prod", "declared": "LOW"})
        assert dec.decision == "DENY"
        assert dec.detail["risk"] == "HIGH"

    def test_semantic_laundering_denied(self):
        """A destructive verb hidden in a command string is still intrinsic HIGH."""
        dec = ControlPlane().evaluate("risk",
                                      {"action": "write", "target": "x",
                                       "command": "rm -rf /tmp/cache",
                                       "declared": "LOW"})
        assert dec.decision == "DENY"


# ---------------------------------------------------------------------------
# BadSectorReviewGate — expanded mandatory-trigger vocabulary
# ---------------------------------------------------------------------------
class TestBadSectorReviewMandatoryTriggers:
    """BadSectorReviewGate must use the expanded INTRINSIC_HIGH_ACTIONS set
    for mandatory review triggers (was 6, now matches control.risk)."""

    def test_rm_triggers_mandatory_review(self):
        """`rm` is now in the expanded set — mandatory review."""
        dec = ControlPlane().evaluate("badsector_review",
                                       {"action": "rm", "risk": "LOW"})
        assert dec.decision == "DENY"
        assert "mandatory" in dec.reason

    def test_destructive_triggers_mandatory_review(self):
        dec = ControlPlane().evaluate("badsector_review",
                                       {"action": "destructive", "risk": "LOW"})
        assert dec.decision == "DENY"
        assert "mandatory" in dec.reason

    def test_non_high_action_no_review_required(self):
        dec = ControlPlane().evaluate("badsector_review",
                                       {"action": "read", "risk": "LOW"})
        assert dec.decision == "ALLOW"


# ---------------------------------------------------------------------------
# INTRINSIC_HIGH_ACTIONS coverage
# ---------------------------------------------------------------------------
class TestIntrinsicHighVocabulary:
    """The foundation INTRINSIC_HIGH_ACTIONS set must include the full
    vocabulary from control.risk (semantic laundering resistance)."""

    @pytest.mark.parametrize("action", [
        "rm", "drop", "truncate", "overwrite", "destroy",
        "credential_change", "permission_change", "role_grant", "access_grant",
        "financial_transaction", "financial_commitment", "payment",
        "wire_transfer",  # <- these were MISSING from the old 6-element set
    ])
    def test_action_in_intrinsic_high(self, action):
        assert action in INTRINSIC_HIGH_ACTIONS, (
            f"{action!r} should be in INTRINSIC_HIGH_ACTIONS "
            "(semantic laundering resistance)")

    def test_set_has_minimum_coverage(self):
        """The set must cover at least the control.risk vocabulary."""
        assert len(INTRINSIC_HIGH_ACTIONS) >= 20

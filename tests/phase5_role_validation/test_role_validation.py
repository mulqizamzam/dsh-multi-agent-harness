# tests/phase5_role_validation/test_role_validation.py — Session E (G12)
#
# TEST-SUPPORT ONLY. NOT production code.
#
# Deterministic validation of the six target roles (zeko, cfo, kai, somad,
# badsector, nova) + honest live-gating when the D4/D7 mount is absent.

import os

import pytest

from tests.phase5_role_validation.harness import (
    BRIDGE_MARKER_ENV,
    TARGET_ROLES,
    check_live_provenance,
    check_prohibited_tools,
    check_role_resolution,
    check_subdelegation_denial,
    check_toolfilter_consistency,
    run_role_validation,
)


class TestRoleResolution:
    @pytest.mark.parametrize("role", TARGET_ROLES)
    def test_every_target_role_resolves(self, role):
        c = check_role_resolution(role)
        assert c.passed, c.detail


class TestToolFilter:
    @pytest.mark.parametrize("role", TARGET_ROLES)
    def test_toolfilter_consistent(self, role):
        c = check_toolfilter_consistency(role)
        assert c.passed, c.detail


class TestProhibitedTools:
    @pytest.mark.parametrize("role", TARGET_ROLES)
    def test_prohibited_tools_not_in_allow(self, role):
        c = check_prohibited_tools(role)
        assert c.passed, c.detail


class TestSubdelegationDenial:
    @pytest.mark.parametrize("role", TARGET_ROLES)
    def test_specialist_delegation_denied(self, role):
        c = check_subdelegation_denial(role)
        assert c.passed, c.detail


class TestLiveGating:
    def test_live_check_blocked_without_mount(self, monkeypatch):
        """With no D4/D7 mount, the live check reports BLOCKED — never a fake
        live result."""
        monkeypatch.delenv(BRIDGE_MARKER_ENV, raising=False)
        c = check_live_provenance("cfo")
        assert c.live and c.blocked
        assert "no fake evidence" in c.detail or "BLOCKED" in c.detail

    def test_live_check_passes_with_injected_dispatch(self, monkeypatch):
        """With the marker set + an injected dispatch, the live check records
        real provenance (mirrors the Phase-3 live runs)."""
        monkeypatch.setenv(BRIDGE_MARKER_ENV, "1")
        from orchestrator.dsh import RoleResolver
        inst = RoleResolver().resolve("cfo")

        def _dispatch(instance):
            return type("Outcome", (), {
                "run_id": "real-role-001",
                "stop_reason": "completed",
                "output": "ok",
                "structured": {"status": "SUCCEEDED"},
            })()

        c = check_live_provenance("cfo", _dispatch)
        assert c.live and c.passed, c.detail
        assert c.detail.startswith("run_id=real-role-001")


class TestFullRun:
    def test_full_validation_no_deterministic_failures(self):
        result = run_role_validation()
        assert not result.deterministic_failures, [
            c.to_dict() for c in result.deterministic_failures]

    def test_live_checks_blocked_in_current_env(self):
        """In the current session (no mount) the six live checks are BLOCKED
        and the harness says so — no fabricated live evidence."""
        result = run_role_validation()
        if not os.environ.get(BRIDGE_MARKER_ENV):
            blocked = result.live_blocked
            assert len(blocked) == len(TARGET_ROLES)
            assert result.live_passed == []

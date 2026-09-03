# tests/orchestrator/dsh/test_guards.py
#
# Delegation guards:
#   - prohibited role delegation (specialist-to-specialist, DLG-003)
#   - delegation validity (inactive, expired, revoked — AUTH-INV-05/06)
#   - delegation scope containment (AUTH-INV-04)
#   - no authority through messages (THREAT-020)

import pytest

from orchestrator.dsh import (
    DelegationClient,
    RoleResolver,
    build_task_context,
    assert_no_authority_in_payload,
)
from orchestrator.dsh.exceptions import (
    DelegationDenied,
    DSHError,
    ProhibitedDelegation,
    RoleResolutionError,
)


class TestActorGate:
    """V1: only the orchestrator delegates (DLG-003)."""

    def test_orchestrator_delegates(self, client, backend, task_factory,
                                    delegation_factory):
        """Orchestrator actor is accepted."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        # Default actor = orchestrator: should succeed
        outcome = client.delegate(task, delegation)
        assert outcome.result.status == "SUCCEEDED"

    def test_specialist_delegation_denied(self, client, task_factory,
                                          delegation_factory):
        """A specialist cannot delegate to another specialist (DLG-003)."""
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ProhibitedDelegation):
            client.delegate(task, delegation, actor="cto")

    def test_unknown_actor_denied(self, client, task_factory,
                                  delegation_factory):
        """Any actor other than orchestrator is denied."""
        task = task_factory(role="cto")
        delegation = delegation_factory()
        with pytest.raises(ProhibitedDelegation):
            client.delegate(task, delegation, actor="bogus")

    def test_prohibited_role_delegation_via_task(self, task_factory,
                                                 delegation_factory):
        """A task assigned to a role the resolver cannot resolve fails closed
        (RoleResolutionError) — delegation is only possible for roles in the
        D4/D7 approved composition."""
        resolver = RoleResolver()

        class ThinResolver:
            """A resolver that can only resolve 'cto' (composition drift)."""
            def resolve(self, role):
                if role != "cto":
                    raise RoleResolutionError(
                        f"role {role!r} has no SubagentInstance "
                        "(D4/D7 composition incomplete)")
                return resolver.resolve("cto")

        client = DelegationClient(resolver=ThinResolver())
        task = task_factory(role="cfo")
        delegation = delegation_factory()
        with pytest.raises(RoleResolutionError):
            client.delegate(task, delegation)


class TestDelegationValidity:
    """Delegation must be active, not expired, not revoked (AUTH-INV-05/06)."""

    def test_delegation_must_be_structured(self, client, task_factory):
        """A bare dict/string is not a Delegation (AUTH-INV-01/05)."""
        task = task_factory(role="cto")
        with pytest.raises(DelegationDenied):
            client.delegate(task, {"id": "strip"})  # type: ignore

    def test_delegation_must_be_active(self, client, task_factory,
                                       delegation_factory):
        task = task_factory(role="cto")
        # expired delegation
        d = delegation_factory(status="EXPIRED")
        with pytest.raises(DelegationDenied):
            client.delegate(task, d)

    def test_expired_delegation_denied(self, client, task_factory,
                                       delegation_factory):
        task = task_factory(role="cto")
        d = delegation_factory(expires_at="2020-01-01T00:00:00Z")
        with pytest.raises(DelegationDenied):
            client.delegate(task, d)

    def test_revoked_delegation_denied(self, client, task_factory,
                                       delegation_factory):
        task = task_factory(role="cto")
        d = delegation_factory(status="REVOKED")
        with pytest.raises(DelegationDenied):
            client.delegate(task, d)


class TestScopeContainment:
    """Task scope must be within delegation resources (AUTH-INV-04)."""

    def test_scope_contained(self, client, backend, task_factory,
                             delegation_factory):
        """Task scope within delegation resources → allowed."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(scope=("agents/**",))
        delegation = delegation_factory(
            resources=("multi-agent-harness/**", "agents/**"))
        outcome = client.delegate(task, delegation)
        assert outcome.result.status == "SUCCEEDED"

    def test_scope_outside_delegation_denied(self, client, task_factory,
                                             delegation_factory):
        """Task scope outside delegation resources → DelegationDenied."""
        task = task_factory(scope=("/outside/path",))
        delegation = delegation_factory(resources=("multi-agent-harness/**",))
        with pytest.raises(DelegationDenied):
            client.delegate(task, delegation)


class TestNoAuthorityThroughMessages:
    """Messages must not carry authority (THREAT-020)."""

    def test_authority_keys_stripped_from_extra(self, client, backend,
                                                task_factory,
                                                delegation_factory):
        """Authority assertion keys in extra_context are stripped by the
        context builder.  The backend receives a clean context."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        extra = {
            "approved": True,
            "authority": "orchestrator",
            "grant": "full_access",
            "note": "this is ok",
        }
        outcome = client.delegate(task, delegation, extra_context=extra)
        assert outcome.result.status == "SUCCEEDED"
        # The backend's first call's prompt should NOT contain approved/authority/grant
        calls = backend.start_calls()
        assert len(calls) == 1
        prompt = calls[0]["prompt"]
        assert "approved" not in prompt
        assert "authority" not in prompt
        assert "grant" not in prompt
        assert prompt.get("note") == "this is ok"

    def test_assert_no_authority_in_payload_raises(self):
        """assert_no_authority_in_payload rejects payloads with authority keys."""
        with pytest.raises(DSHError):
            assert_no_authority_in_payload({"approved": True})
        # Sanitized payloads pass
        assert_no_authority_in_payload({"task_id": "t-1"})  # no raise

    def test_delegation_id_is_provenance_not_authority(self, client, backend,
                                                       task_factory,
                                                       delegation_factory):
        """The delegation_id field in the context is a provenance reference,
        not a grant.  The child only sees the id, never the full Delegation
        object."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        outcome = client.delegate(task, delegation)
        assert outcome.provenance.delegation_id == delegation.id
        # The prompt contains delegation_id as a string reference
        calls = backend.start_calls()
        prompt = calls[0]["prompt"]
        assert prompt.get("delegation_id") == delegation.id
        # The prompt does NOT contain the full delegation object fields
        assert "principal" not in prompt
        assert "delegate" not in prompt
        assert "approval_reference" not in prompt

    def test_message_authority_assertion_guard(self, client, backend,
                                                task_factory,
                                                delegation_factory):
        """The context builder's strip_authority_assertions logs stripped
        keys; the client uses the sanitized context."""
        backend.register_result("subagent_cto", {
            "task_id": "t-1", "assigned_role": "cto",
            "status": "SUCCEEDED", "confidence": "HIGH",
            "reported_at": "2026-08-31T00:00:00Z",
        })
        task = task_factory(role="cto")
        delegation = delegation_factory()
        # extra_context with authority-ish keys should be stripped
        extra = {"authorization": "expired", "permission": "read", "data": "ok"}
        outcome = client.delegate(task, delegation, extra_context=extra)
        assert outcome.result.status == "SUCCEEDED"
        prompt = backend.start_calls()[0]["prompt"]
        assert "authorization" not in prompt
        assert "permission" not in prompt
        assert prompt.get("data") == "ok"
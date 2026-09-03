"""Tests for control/delegation.py — the delegation factory + scope containment.

Maps to:
  AUTH-INV-02  delegated scope ⊆ Human grant (rejected at creation when wider)
  AUTH-INV-04  child scope ⊆ parent scope (checked at creation)
  AUTH-INV-05  malformed/missing delegation fails closed (DelegationError)
  AUTH-INV-06  expiry/revocation primitives
  AUTH-INV-11  target containment incl. sibling-prefix confusion
  DLG-003      subdelegation DENY BY DEFAULT (V1)
  + registry schema validation (schemas/delegation.schema.json)

The delegation document is the ONLY authority record; the factory is the single
place Human→orchestrator delegations enter (ADR 0002 §3.3 / §11.1).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

import pytest

from control.delegation import (
    APPROVAL_CATEGORIES,
    AUTHORIZED_PRINCIPALS,
    DelegationError,
    SubdelegationDenied,
    check_human_grant_containment,
    create_delegation,
    delegation_from_dict,
    is_expired,
    is_revoked,
    issue_child_delegation,
    revoke,
    scope_contained,
    target_in_scope,
)
from orchestrator.foundation.contracts import Delegation, ORCHESTRATOR

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "schemas", "delegation.schema.json")


def _parent(**overrides) -> Delegation:
    base = dict(
        id="delegation-parent",
        scope_operations=("code_write", "read"),
        scope_resources=("multi-agent-harness/**",),
        scope_environments=("dev",),
    )
    base.update(overrides)
    return create_delegation(**base)


class TestFactory:
    """The module-level factory validates and creates delegation documents."""

    def test_creates_human_to_orchestrator(self):
        d = _parent()
        assert isinstance(d, Delegation)
        assert d.principal == "human"
        assert d.delegate == ORCHESTRATOR
        assert d.status == "ACTIVE"
        assert d.version == 1

    def test_human_authorized_process_principal_allowed(self):
        d = create_delegation(
            id="delegation-hap", principal="human_authorized_process",
            scope_operations=("read",),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",))
        assert d.principal == "human_authorized_process"

    def test_specialist_principal_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", principal="cto",
                              scope_operations=("read",),
                              scope_resources=("x/**",))

    def test_non_orchestrator_delegate_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", delegate="cto",
                              scope_operations=("read",),
                              scope_resources=("x/**",))

    def test_empty_operations_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", scope_operations=(),
                              scope_resources=("x/**",))

    def test_empty_resources_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", scope_operations=("read",),
                              scope_resources=())

    def test_empty_environments_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", scope_operations=("read",),
                              scope_resources=("x/**",),
                              scope_environments=())

    def test_negative_maximum_cost_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", scope_operations=("read",),
                              scope_resources=("x/**",), maximum_cost=-1)

    def test_unknown_requires_approval_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="delegation-x", scope_operations=("read",),
                              scope_resources=("x/**",),
                              requires_approval=("not-a-category",))

    def test_bad_id_pattern_rejected(self):
        with pytest.raises(DelegationError):
            create_delegation(id="not-delegation-shaped",
                              scope_operations=("read",),
                              scope_resources=("x/**",))


class TestDelegationFromDict:
    """AUTH-INV-05 — malformed/missing documents fail closed."""

    def test_round_trip(self):
        d = _parent()
        doc = d.to_dict()
        d2 = delegation_from_dict(doc)
        assert d2.to_dict() == doc

    def test_none_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict(None)

    def test_string_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict("Human approved this")

    def test_list_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict([1, 2, 3])

    def test_missing_required_fields_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict({"id": "delegation-x"})

    def test_malformed_scope_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict({"id": "delegation-x", "scope": "oops"})

    def test_non_numeric_cost_rejected(self):
        with pytest.raises(DelegationError):
            delegation_from_dict({
                "id": "delegation-x",
                "scope": {"operations": ["read"],
                          "resources": ["x/**"],
                          "environments": ["dev"],
                          "maximum_cost": "cheap"},
            })


class TestSchemaValidation:
    """The produced documents validate against schemas/delegation.schema.json."""

    def test_document_matches_schema(self):
        import jsonschema
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        d = _parent()
        jsonschema.validate(d.to_dict(), schema)

    def test_document_matches_schema_with_all_fields(self):
        import jsonschema
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        d = create_delegation(
            id="delegation-full", task="task-9", action="code_write",
            target="multi-agent-harness/**", environment="dev",
            scope_operations=("code_write", "read"),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",),
            maximum_cost=100.0, prohibited_actions=("financial_transaction",),
            requires_approval=("destructive",),
            expires_at="2099-01-01T00:00:00Z",
            approval_reference="approval-1")
        jsonschema.validate(d.to_dict(), schema)


class TestHumanGrantContainment:
    """AUTH-INV-02 — a delegation must be a subset of the Human grant."""

    def test_subset_contained(self):
        grant = _parent()
        narrow = create_delegation(
            id="delegation-narrow", scope_operations=("read",),
            scope_resources=("multi-agent-harness/docs/**",),
            scope_environments=("dev",))
        assert check_human_grant_containment(narrow, grant) is True

    def test_wider_operations_not_contained(self):
        grant = _parent(scope_operations=("read",))
        wide = create_delegation(
            id="delegation-wide", scope_operations=("read", "code_write"),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",))
        assert check_human_grant_containment(wide, grant) is False

    def test_creation_within_grant_accepted(self):
        grant = _parent()
        d = create_delegation(
            id="delegation-ok", scope_operations=("read",),
            scope_resources=("multi-agent-harness/docs/**",),
            scope_environments=("dev",), within_human_grant=grant)
        assert d.scope_operations == ("read",)

    def test_creation_wider_than_grant_rejected(self):
        grant = _parent(scope_operations=("read",))
        with pytest.raises(DelegationError):
            create_delegation(
                id="delegation-wide", scope_operations=("read", "code_write"),
                scope_resources=("multi-agent-harness/**",),
                scope_environments=("dev",), within_human_grant=grant)


class TestScopeContained:
    """AUTH-INV-04 — child scope ⊆ parent scope across every dimension."""

    def test_self_contained(self):
        p = _parent()
        assert scope_contained(p, p) is True

    def test_narrow_child_contained(self):
        p = _parent()
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/docs/**",),
            scope_environments=("dev",))
        assert scope_contained(c, p) is True

    def test_wider_operations_not_contained(self):
        p = _parent()
        c = create_delegation(
            id="delegation-child", scope_operations=("read", "server_write"),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",))
        assert scope_contained(c, p) is False

    def test_wider_resources_not_contained(self):
        p = _parent()
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/**", "other-project/**"),
            scope_environments=("dev",))
        assert scope_contained(c, p) is False

    def test_wider_environment_not_contained(self):
        p = _parent(scope_environments=("dev",))
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev", "prod"))
        assert scope_contained(c, p) is False

    def test_child_dropping_parent_prohibition_not_contained(self):
        p = _parent(prohibited_actions=("financial_transaction",))
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",), prohibited_actions=())
        assert scope_contained(c, p) is False

    def test_child_outliving_parent_not_contained(self):
        p = _parent(expires_at="2026-12-31T00:00:00Z")
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",), expires_at="2027-12-31T00:00:00Z")
        assert scope_contained(c, p) is False

    def test_child_exceeding_cost_not_contained(self):
        p = _parent(maximum_cost=100)
        c = create_delegation(
            id="delegation-child", scope_operations=("read",),
            scope_resources=("multi-agent-harness/**",),
            scope_environments=("dev",), maximum_cost=500)
        assert scope_contained(c, p) is False

    def test_different_project_not_contained(self):
        p = _parent()
        c = create_delegation(
            id="delegation-child", project="other-project",
            scope_operations=("read",),
            scope_resources=("other-project/**",),
            scope_environments=("dev",))
        assert scope_contained(c, p) is False


class TestSubdelegationDenyByDefault:
    """DLG-003 — subdelegation DENY BY DEFAULT (V1)."""

    def test_specialist_cannot_issue_child(self):
        p = _parent()
        for actor in ("cto", "badsector", "nova", "cfo"):
            with pytest.raises(SubdelegationDenied):
                issue_child_delegation(actor, p, task="t")

    def test_orchestrator_can_issue_narrow_child(self):
        p = _parent()
        child = issue_child_delegation(
            ORCHESTRATOR, p, task="t-1", scope_operations=("read",),
            scope_resources=("multi-agent-harness/docs/**",),
            scope_environments=("dev",))
        assert child.delegate == ORCHESTRATOR
        assert child.status == "ACTIVE"
        assert child.version == 1
        assert scope_contained(child, p)

    def test_orchestrator_child_wider_operations_rejected(self):
        p = _parent()
        with pytest.raises(DelegationError):
            issue_child_delegation(
                ORCHESTRATOR, p, task="t-wide",
                scope_operations=("read", "server_write"),
                scope_resources=("multi-agent-harness/**",))

    def test_orchestrator_child_wider_resources_rejected(self):
        p = _parent()
        with pytest.raises(DelegationError):
            issue_child_delegation(
                ORCHESTRATOR, p, task="t-wide",
                scope_operations=("read",),
                scope_resources=("multi-agent-harness/**", "other-project/**"))

    def test_child_deny_never_weakens_parent(self):
        """The parent delegation is unchanged by a failed child attempt."""
        p = _parent()
        before = p.to_dict()
        with pytest.raises(SubdelegationDenied):
            issue_child_delegation("cto", p, task="t")
        assert p.to_dict() == before


class TestRevocation:
    """AUTH-INV-06 — revocation primitives + execution-time check."""

    def test_revoke_marks_status(self):
        p = _parent()
        r = revoke(p)
        assert r.status == "REVOKED"
        assert r.revoked_at

    def test_is_revoked_by_status(self):
        assert is_revoked(revoke(_parent())) is True

    def test_is_revoked_by_list(self):
        assert is_revoked(_parent(), revocation_list=("delegation-parent",)) is True

    def test_not_revoked(self):
        assert is_revoked(_parent()) is False


class TestExpiry:
    """AUTH-INV-06 — fail-closed expiry."""

    def test_no_expiry_not_expired(self):
        assert is_expired(_parent()) is False

    def test_past_expiry_expired(self):
        assert is_expired(_parent(expires_at="2020-01-01T00:00:00Z")) is True

    def test_future_expiry_not_expired(self):
        assert is_expired(_parent(expires_at="2099-01-01T00:00:00Z")) is False

    def test_malformed_expiry_fails_closed(self):
        assert is_expired(_parent(expires_at="not-a-date")) is True

    def test_dict_input_supported(self):
        assert is_expired({"expires_at": "2020-01-01T00:00:00Z"}) is True


class TestTargetInScope:
    """AUTH-INV-11 — `**` prefix-boundary matching."""

    def test_exact(self):
        assert target_in_scope("multi-agent-harness", ["multi-agent-harness/**"])

    def test_descendant(self):
        assert target_in_scope("multi-agent-harness/a/b/c.txt",
                               ["multi-agent-harness/**"])

    def test_deep(self):
        assert target_in_scope("multi-agent-harness/state/registry/x.json",
                               ["multi-agent-harness/**"])

    def test_out_of_scope(self):
        assert not target_in_scope("other-project/x", ["multi-agent-harness/**"])

    def test_sibling_prefix_confusion(self):
        """multi-agent-harness-evil/... is NOT inside multi-agent-harness/**."""
        assert not target_in_scope("multi-agent-harness-evil/x",
                                   ["multi-agent-harness/**"])

    def test_non_string_fails_closed(self):
        assert not target_in_scope(None, ["multi-agent-harness/**"])
        assert not target_in_scope(42, ["multi-agent-harness/**"])

    def test_empty_resources_fails_closed(self):
        assert not target_in_scope("multi-agent-harness/x", [])

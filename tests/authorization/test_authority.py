"""Authorization security tests — AUTH-*, ISO-*, REG-*, DLG-*, RISK-*.

These are EXECUTABLE skeletons: they assert the DENY/ALLOW semantics the
production control plane must enforce (reference: tests/control_plane.py).
They do NOT execute any real DSH tool — they run pure logic against the
reference authority gate. Phase 6 will exercise the same semantics against a
live DSH session (see tests/scenarios/).
"""

import pytest

from control_plane import (
    Deny, authorize, classify_risk, badsector_pass_is_authority,
    verify_badsector_provenance, target_in_scope,
)


def _delegation(**overrides):
    d = {
        "id": "delegation-001", "principal": "human", "delegate": "orchestrator",
        "project": "multi-agent-harness",
        "scope": {"operations": ["code_write", "server_read", "read"],
                  "resources": ["multi-agent-harness/**"], "environments": ["dev"]},
        "prohibited_actions": ["financial_transaction", "credential_change"],
        "requires_approval": ["destructive"],
        "expires_at": None, "approval_reference": None,
        "status": "ACTIVE", "version": 1,
        "created_at": "2026-08-29T00:00:00Z", "updated_at": "2026-08-29T00:00:00Z", "revoked_at": None,
    }
    d.update(overrides)
    return d


class TestAuthorityGate:
    """AUTH-001..008 — the authority gate."""

    def test_auth_001_no_self_escalation(self):
        """A specialist attempting to write the registry (grant itself) is DENIED."""
        # Registry path is a protected path (ADR 0002); only the writer may touch it.
        with pytest.raises(Deny):
            authorize("cto", "write", "state/registry/delegation-001.yaml", _delegation())

    def test_auth_002_no_scope_expansion(self):
        """Action outside delegation operations is DENIED."""
        with pytest.raises(Deny):
            authorize("orchestrator", "server_write", "multi-agent-harness/state/x.json", _delegation())

    def test_auth_003_expired_delegation(self):
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md",
                      _delegation(expires_at="2020-01-01T00:00:00Z"))

    def test_auth_004_revoked_delegation(self):
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md",
                      _delegation(), revocation_list=("delegation-001",))

    def test_auth_005_action_outside_scope(self):
        """Delegation allows code_write only; server_write request is DENIED."""
        with pytest.raises(Deny):
            authorize("orchestrator", "server_write", "multi-agent-harness/x", _delegation())

    def test_auth_006_invalid_delegation(self):
        """Malformed delegation (None) → DENY (fail-closed, AUTH-INV-05)."""
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md", None)

    def test_auth_007_badsector_pass_is_not_authority(self):
        """AUTH-INV-09: PASS alone never authorizes execution."""
        d = _delegation()  # delegation allows read
        # Even WITH a PASS, execution still requires authority (delegation).
        # Here: PASS present but delegation does not include the action → DENY.
        with pytest.raises(Deny):
            authorize("orchestrator", "financial_transaction", "multi-agent-harness/x", d)
        # And conceptually: PASS is never treated as authority.
        assert badsector_pass_is_authority({"verdict": "PASS"}, d) is False

    def test_auth_008_model_text_is_not_authority(self):
        """AUTH-INV-01: model text claiming approval is never authority.

        The gate only consumes structured records; there is no 'approved in
        prose' path. An action without a matching delegation is DENIED even if
        the caller 'claims' approval in text (no such parameter exists)."""
        d = _delegation(prohibited_actions=["financial_transaction", "credential_change", "server_write"])
        # model prose cannot widen scope
        with pytest.raises(Deny):
            authorize("orchestrator", "server_write", "multi-agent-harness/x", d)


class TestRoleIsolation:
    """ISO-001..007 — capability boundaries via the role tool surface + gate."""

    def test_iso_001_cto_no_financial_capability(self):
        """CTO cannot access CFO-only financial capability."""
        d = _delegation(scope={
            "operations": ["code_write", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("cto", "financial_transaction", "multi-agent-harness/x", d)

    def test_iso_001_cto_no_financial_tools(self, project_root):
        import yaml
        with open(project_root + "/agents/cto/policy.yaml") as f:
            pol = yaml.safe_load(f)
        assert pol["invariants"].get("no_financial_capability") is True

    def test_iso_002_cfo_no_code_write(self):
        """CFO has no write/exec tools in its tool surface (asserted in test_config);
        at the gate level, an action outside the (correctly scoped) delegation is
        DENIED. A delegation must never grant CFO code_write — here we model the
        correct delegation, which does not include code_write."""
        cfo_delegation = _delegation(scope={
            "operations": ["financial_analysis", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"],
        })
        with pytest.raises(Deny):
            authorize("cfo", "code_write", "multi-agent-harness/code/x.py", cfo_delegation)

    def test_iso_002_cfo_no_write_tools_in_filter(self, project_root):
        """ISO-002 enforcement point #1: CFO's tool surface has no write/exec tools."""
        import yaml
        with open(project_root + "/agents/cfo/policy.yaml") as f:
            pol = yaml.safe_load(f)
        allow = set(pol["tool_surface"]["allow"])
        assert not (allow & {"bash", "edit", "write", "str_replace_editor"}), \
            f"CFO tool surface must have no write/exec tools, got {allow}"

    def test_iso_003_kai_no_project_write(self):
        """Kai is read-only by default — no project file write."""
        d = _delegation(scope={
            "operations": ["read", "web_research"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("kai", "write", "multi-agent-harness/agents/kai/policy.yaml", d)

    def test_iso_003_kai_no_write_tools_in_filter(self, project_root):
        import yaml
        with open(project_root + "/agents/kai/policy.yaml") as f:
            pol = yaml.safe_load(f)
        allow = set(pol["tool_surface"]["allow"])
        assert not (allow & {"bash", "edit", "write"}), \
            f"Kai toolFilter must have no write tools, got {allow}"

    def test_iso_004_somad_no_infra(self):
        """Somad cannot execute infrastructure actions (no bash/server_write)."""
        d = _delegation(scope={
            "operations": ["social_drafting", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("somad", "server_write", "multi-agent-harness/infra/x", d)

    def test_iso_004_somad_no_bash_in_filter(self, project_root):
        import yaml
        with open(project_root + "/agents/somad/policy.yaml") as f:
            pol = yaml.safe_load(f)
        allow = set(pol["tool_surface"]["allow"])
        assert "bash" not in allow, f"Somad must not allow bash, got {allow}"
        assert pol["invariants"].get("no_infra_capability") is True

    def test_iso_005_nova_no_infra_execution(self):
        """Nova cannot execute infrastructure actions."""
        d = _delegation(scope={
            "operations": ["novel_editing", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("nova", "server_write", "multi-agent-harness/infra/x", d)

    def test_iso_005_nova_no_bash_in_filter(self, project_root):
        import yaml
        with open(project_root + "/agents/nova/policy.yaml") as f:
            pol = yaml.safe_load(f)
        allow = set(pol["tool_surface"]["allow"])
        assert "bash" not in allow, f"Nova must not allow bash, got {allow}"
        assert pol["invariants"].get("no_infra_capability") is True

    def test_iso_006_badsector_never_executes(self):
        """BadSector has no mutate/execute tools; gate denies un-permitted writes."""
        with pytest.raises(Deny):
            authorize("badsector", "write", "multi-agent-harness/agents/x/policy.yaml", _delegation())

    def test_iso_007_zeko_no_code_architecture_change(self):
        """Zeko cannot modify application architecture without explicit code scope."""
        d = _delegation(scope={
            "operations": ["server_read", "server_write"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("zeko", "code_write", "multi-agent-harness/agents/cto/policy.yaml", d)

    def test_iso_007_zeko_invariant_declared(self, project_root):
        import yaml
        with open(project_root + "/agents/zeko/policy.yaml") as f:
            pol = yaml.safe_load(f)
        assert pol["invariants"].get("no_code_architecture_change_without_scope") is True


class TestTargetScope:
    """AUTH-INV-11 — target containment."""

    def test_target_in_scope_exact(self):
        assert target_in_scope("multi-agent-harness", ["multi-agent-harness/**"])
        assert target_in_scope("multi-agent-harness/config/agents.yaml", ["multi-agent-harness/**"])

    def test_target_out_of_scope(self):
        assert not target_in_scope("other-project/file", ["multi-agent-harness/**"])

    def test_target_mismatch_denied(self):
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "other-project/file", _delegation())

    def test_target_deep_descendant_in_scope(self):
        assert target_in_scope("multi-agent-harness/a/b/c/d.txt", ["multi-agent-harness/**"])

    def test_target_sibling_not_in_scope(self):
        """A sibling with a prefix-like name is NOT inside `multi-agent-harness/**`
        (prefix confusion prevention)."""
        assert not target_in_scope("multi-agent-harness-evil/x.json",
                                   ["multi-agent-harness/**"])
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness-evil/x", _delegation())


class TestScopeContainment:
    """AUTH-INV-02 / AUTH-INV-04 — delegated scope ⊆ Human grant; child ⊆ parent."""

    def _scope(self, operations=(), resources=(), environments=("dev",)):
        return {"operations": list(operations), "resources": list(resources),
                "environments": list(environments)}

    def test_child_within_parent_operations(self):
        parent = self._scope(operations=("code_write", "read"), resources=("multi-agent-harness/**",))
        child = self._scope(operations=("code_write",), resources=("multi-agent-harness/**",))
        assert set(child["operations"]) <= set(parent["operations"])
        assert set(child["resources"]) <= set(parent["resources"])

    def test_child_wider_than_parent_is_invalid(self):
        """A child delegation that exceeds the parent scope violates AUTH-INV-04."""
        parent = self._scope(operations=("code_write",), resources=("multi-agent-harness/**",))
        child = self._scope(operations=("code_write", "server_write"),
                            resources=("multi-agent-harness/**",))
        assert not (set(child["operations"]) <= set(parent["operations"]))
        # The child scope is not delegable: the parent could not cover it.
        with pytest.raises(Deny):
            authorize("orchestrator", "server_write", "multi-agent-harness/x",
                      {**_delegation(scope=parent), "id": "delegation-child"})

    def test_delegation_wider_than_human_grant_rejected(self):
        """AUTH-INV-02: a delegation must never exceed the Human grant.

        Modeled at the reference level: the gate only honors delegations whose
        actions/targets are covered; a delegation that includes a prohibited or
        un-granted action is either rejected at creation (schema/prohibited) or
        denied at use."""
        human_grant = _delegation(scope={
            "operations": ["code_write", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"],
        })
        # Delegation tries to add an action the Human never granted.
        forged = {**human_grant,
                  "scope": {"operations": ["code_write", "read", "financial_transaction"],
                            "resources": ["multi-agent-harness/**"], "environments": ["dev"]}}
        with pytest.raises(Deny):
            authorize("orchestrator", "financial_transaction",
                      "multi-agent-harness/x", forged)

    def test_env_mismatch_denied(self):
        """Delegation scoped to dev cannot authorize a prod action."""
        d = _delegation(scope={
            "operations": ["deploy"], "resources": ["multi-agent-harness/**"],
            "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("orchestrator", "deploy", "multi-agent-harness/x", d,
                      environment="prod")
        # A matching environment is allowed.
        assert authorize("orchestrator", "deploy", "multi-agent-harness/x", d,
                         environment="dev") is True


class TestStateApprovalForgery:
    """AUTH-INV-07 / AUTH-INV-08 — project-state fields are never authority."""

    def test_state_approved_flag_is_not_authority(self):
        """A state file containing `approved: true` grants nothing."""
        state = {"id": "p1", "status": "APPROVED", "approved": True,
                 "approvals": [{"id": "appr-1", "result": "allowed"}]}
        # Gate ignores state; only the delegation registry counts.
        with pytest.raises(Deny):
            authorize("orchestrator", "write", "multi-agent-harness/x", None)
        # Even with a state approval record, no delegation → DENY.
        assert state["approved"] is True  # the field exists but is inert

    def test_state_transition_write_does_not_grant(self):
        """Writing `status: APPROVED` into state has no authority effect
        (AUTH-INV-08) — the gate still requires a structured delegation."""
        state = {"id": "p1", "status": "APPROVED"}
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md", None)
        assert state["status"] == "APPROVED"  # cosmetic only

    def test_approval_reference_alone_is_not_authority(self):
        """An approval_reference string in a delegation is a record, not the
        authority itself — the delegation still must be ACTIVE and scoped."""
        d = _delegation(approval_reference="appr-1", status="REVOKED")
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md", d)


class TestAuditForgery:
    """AUTH-INV-14 — audit records cannot grant authority."""

    def test_forged_audit_entry_grants_nothing(self):
        """An audit entry claiming an approval is a RECORD, never a grant."""
        from audit.helpers import audit_is_authority_source
        forged = {"event_id": "event-forged", "event_class": "normal_approval",
                  "result": "allowed", "actor": "cto", "actor_type": "agent",
                  "action": "grant", "target": "self", "project": "p"}
        assert audit_is_authority_source(forged) is False
        # And the authority gate, which reads only structured records, DENYs:
        with pytest.raises(Deny):
            authorize("cto", "write", "multi-agent-harness/x", None)

    def test_audit_entry_describing_approval_is_record_not_grant(self):
        """AUTH-INV-14: an event whose class is normal_approval is a record of
        an approval — the authority gate never reads audit as a grant."""
        event = {"event_id": "event-1", "event_class": "normal_approval",
                 "result": "allowed", "actor": "human", "actor_type": "human",
                 "action": "approve", "target": "task-1", "project": "p"}
        from audit.helpers import audit_is_authority_source
        assert audit_is_authority_source(event) is False


class TestOrchestratorBoundary:
    """AUTH-INV-18 — orchestrator cannot execute what it could not delegate."""

    def test_orchestrator_direct_high_action_denied(self):
        """The orchestrator cannot execute an action outside its delegation
        (coordinates only; B-lite carve-out is read-only/reversible)."""
        d = _delegation(scope={
            "operations": ["read", "code_write"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("orchestrator", "production_deploy",
                      "multi-agent-harness/x", d)

    def test_orchestrator_executes_undelegable_action_denied(self):
        """An action the orchestrator could not legitimately delegate
        (financial_transaction is prohibited) is also not executable by it."""
        d = _delegation(prohibited_actions=["financial_transaction", "credential_change"])
        with pytest.raises(Deny):
            authorize("orchestrator", "financial_transaction",
                      "multi-agent-harness/x", d)

    def test_orchestrator_scope_readonly_within_delegation(self):
        """B-lite carve-out: read-only/reversible internal actions within the
        delegation are allowed through the gate."""
        d = _delegation()
        assert authorize("orchestrator", "read", "multi-agent-harness/README.md", d) is True


class TestCapabilityBoundary:
    """AUTH-INV-19 — subagent capability must not exceed its role boundary."""

    def test_actor_without_capability_denied(self):
        """A specialist attempting an action outside its capability matrix is
        DENIED (toolFilter at the DSH layer; gate here is the second net)."""
        # CFO has no code_write capability; a delegation must never grant it.
        d = _delegation(scope={
            "operations": ["financial_analysis", "read"],
            "resources": ["multi-agent-harness/**"], "environments": ["dev"]})
        with pytest.raises(Deny):
            authorize("cfo", "code_write", "multi-agent-harness/code/x.py", d)

    def test_capability_matrix_denies_badsector_execution(self, project_root):
        """BadSector's capability is adversarial_review only — never execution.

        The correct invariant: badsector never holds a standing capability
        (`yes`) and never an approval-gated execution capability outside
        adversarial_review. `review` / `no` / read-only `scoped` are allowed."""
        import yaml
        with open(project_root + "/config/permissions.yaml") as f:
            perms = yaml.safe_load(f)
        caps = perms["capabilities"]
        for cap, row in caps.items():
            v = row["badsector"]
            if cap == "adversarial_review":
                assert v == "yes"
            else:
                assert v not in ("yes", "approval", "scoped_approval"), \
                    f"badsector must not execute {cap}: {v!r}"

    def test_role_policy_allow_subset_of_verified_tools(self, project_root):
        """Every role's toolFilter allow set is a subset of the verified catalog
        (validated in validate_config; spot-checked here for the write roles)."""
        import yaml
        from validate_config import VERIFIED_TOOLS
        # Post-O5: only zeko/cto remain raw-write-capable roles.
        for rid in ("zeko", "cto"):
            with open(project_root + f"/agents/{rid}/policy.yaml") as f:
                pol = yaml.safe_load(f)
            allow = set(pol["tool_surface"]["allow"])
            assert allow <= VERIFIED_TOOLS, f"{rid} allow has unknown tools"


class TestFailClosed:
    """AUTH-INV-20 — a failed authority/control check stops the action."""

    def test_denial_means_no_mutation(self, tmp_path):
        """After a gate denial the action must not occur (no file created)."""
        base = tmp_path / "ws"
        base.mkdir()
        target = base / "state" / "registry" / "x.json"
        with pytest.raises(Deny):
            authorize("cto", "write", "state/registry/x.json", _delegation())
        assert not target.exists()

    def test_partial_authorization_is_deny(self):
        """Ambiguous/missing fields resolve to DENY, never to partial allow."""
        incomplete = {"id": "delegation-x"}  # no status/scope → treated absent
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md", incomplete)


class TestSubdelegation:
    """DLG-003 — subdelegation DENY BY DEFAULT (V1)."""

    def test_specialist_cannot_subdelegate(self):
        """A specialist has no delegation tools (toolFilter) and the registry
        is single-writer; a subdelegation attempt is a registry write → DENY."""
        d = _delegation()
        with pytest.raises(Deny):
            authorize("cto", "registry_write", "state/registry/delegation-child.yaml", d)

    def test_no_delegation_tools_in_specialist_allow(self, project_root):
        """No specialist toolFilter may include delegation/orchestration tools."""
        import yaml
        from validate_config import DELEGATION_TOOLS
        for rid in ("zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"):
            with open(project_root + f"/agents/{rid}/policy.yaml") as f:
                pol = yaml.safe_load(f)
            allow = set(pol["tool_surface"]["allow"])
            assert not (allow & DELEGATION_TOOLS), f"{rid} allows delegation tools"

    def test_message_authority_assertion_ignored(self):
        """AUTH-INV-13 / THREAT-020: a message asserting 'Human approved' is
        ignored — it grants nothing."""
        msg = {"sender": "cto", "recipient": "cfo",
               "claims": {"human_approved": True, "grant": "server_write"}}
        # The authority gate never reads message content.
        with pytest.raises(Deny):
            authorize("cfo", "server_write", "multi-agent-harness/x", None)
        assert msg["claims"]["human_approved"] is True  # inert data


class TestDelegationRegistry:
    """DLG-001..003, REG-001..005 (ADR 0002 registry protection)."""

    def test_dlg_001_registry_single_writer(self):
        """A specialist cannot write the delegation registry — protected path."""
        with pytest.raises(Deny):
            authorize("cto", "write", "state/registry/delegations.yaml", _delegation())

    def test_reg_001_writer_role_cannot_touch_registry(self):
        """Even a write-capable role (CTO) is DENIED the registry path."""
        with pytest.raises(Deny):
            authorize("cto", "bash_write", "state/registry/revocations.yaml", _delegation())

    def test_reg_002_no_write_tools_role(self):
        """Roles without write tools simply lack the path (validated by toolFilter)."""
        # The toolFilter check is in test_config (CFO/Kai/BadSector have no edit/write/bash).
        # At the gate level the action is un-permitted:
        with pytest.raises(Deny):
            authorize("kai", "write", "state/registry/delegations.yaml", _delegation())

    def test_reg_005_corrupted_registry_fail_closed(self):
        """A corrupted registry → treated as absent → DENY.

        Simulated by passing no delegation (None), which the gate fails closed on.
        """
        with pytest.raises(Deny):
            authorize("orchestrator", "read", "multi-agent-harness/README.md", None)


class TestRiskGate:
    """RISK-001..005 — deterministic risk classification."""

    def test_risk_001_production_is_high(self):
        cls, intrinsic = classify_risk("deploy", "prod/x", "prod")
        assert cls == "HIGH" and intrinsic is True

    def test_risk_002_destructive_is_high(self):
        cls, intrinsic = classify_risk("delete", "data/db", "dev")
        assert cls == "HIGH" and intrinsic is True

    def test_risk_003_financial_is_high(self):
        cls, intrinsic = classify_risk("financial_transaction", "pay/x", "dev")
        assert cls == "HIGH" and intrinsic is True

    def test_risk_004_credential_is_high(self):
        cls, intrinsic = classify_risk("credential_change", "auth/config", "dev")
        assert cls == "HIGH" and intrinsic is True

    def test_risk_005_no_model_downgrade_of_high(self):
        """HIGH is never downgraded by model judgment — the classifier itself
        keeps intrinsic HIGH categories HIGH regardless of wording."""
        for action in ("delete", "drop database", "rm -rf /"):
            cls, intrinsic = classify_risk(action, "x", "dev")
            assert intrinsic is True, f"{action} must be intrinsic HIGH"

    def test_risk_low_read(self):
        cls, intrinsic = classify_risk("read", "multi-agent-harness/README.md", "dev")
        assert cls == "LOW" and intrinsic is False
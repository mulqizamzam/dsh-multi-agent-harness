"""Schema conformance tests — validates sample documents and edge cases."""

import json
import os
import pytest
from jsonschema import Draft202012Validator, ValidationError


def _load_schema(name, schemas_dir):
    with open(os.path.join(schemas_dir, name)) as f:
        return json.load(f)


class TestSchemas:
    """Validate JSON Schema conformance of sample documents and edge cases."""

    @pytest.fixture(autouse=True)
    def setup(self, schemas_dir):
        self.schemas_dir = schemas_dir
        self.delegation_schema = _load_schema("delegation.schema.json", schemas_dir)
        self.state_schema = _load_schema("project-state.schema.json", schemas_dir)
        self.audit_schema = _load_schema("audit-event.schema.json", schemas_dir)
        self.role_schema = _load_schema("role-definition.schema.json", schemas_dir)
        self.mapping_schema = _load_schema("role-mapping.schema.json", schemas_dir)
        self.registry_schema = _load_schema("agent-registry.schema.json", schemas_dir)
        self.task_intake_schema = _load_schema("task-intake.schema.json", schemas_dir)
        self.task_schema = _load_schema("task.schema.json", schemas_dir)
        self.task_result_schema = _load_schema("task-result.schema.json", schemas_dir)

    def validate(self, schema, doc):
        Draft202012Validator(schema).validate(doc)

    def test_valid_delegation(self):
        self.validate(self.delegation_schema, {
            "id": "delegation-001", "principal": "human", "delegate": "orchestrator",
            "project": "test",
            "scope": {"operations": ["read"], "resources": ["test/**"], "environments": ["dev"]},
            "prohibited_actions": [], "requires_approval": [],
            "expires_at": None, "approval_reference": None,
            "status": "ACTIVE", "version": 1,
            "created_at": "2026-08-29T00:00:00Z", "updated_at": "2026-08-29T00:00:00Z", "revoked_at": None,
        })

    def test_invalid_delegation_missing_required(self):
        with pytest.raises(ValidationError):
            self.validate(self.delegation_schema, {"id": "delegation-001"})  # missing scope, status, version

    def test_invalid_delegation_bad_principal(self):
        with pytest.raises(ValidationError):
            self.validate(self.delegation_schema, {
                "id": "delegation-001", "principal": "agent", "delegate": "orchestrator",
                "project": "test", "scope": {"operations": [], "resources": [], "environments": []},
                "status": "ACTIVE", "version": 1,
            })

    def test_invalid_delegation_bad_delegate(self):
        """delegate must be 'orchestrator' (const)."""
        with pytest.raises(ValidationError):
            self.validate(self.delegation_schema, {
                "id": "delegation-001", "principal": "human", "delegate": "cto",
                "project": "test", "scope": {"operations": [], "resources": [], "environments": []},
                "status": "ACTIVE", "version": 1,
            })

    def test_invalid_delegation_bad_id_pattern(self):
        """id must match pattern delegation-<id>."""
        with pytest.raises(ValidationError):
            self.validate(self.delegation_schema, {
                "id": "invalid-id", "principal": "human", "delegate": "orchestrator",
                "project": "test", "scope": {"operations": [], "resources": [], "environments": []},
                "status": "ACTIVE", "version": 1,
            })

    def test_valid_project_state(self):
        self.validate(self.state_schema, {
            "id": "p1", "name": "Demo", "objective": "test",
            "status": "active", "created_at": "2026-08-29T00:00:00Z",
            "updated_at": "2026-08-29T00:00:00Z", "version": 1,
            "authorization": {"active_delegations": []},
            "tasks": [], "agents": {},
            "current_state": {"phase": "DRAFT", "next_action": "plan"},
        })

    def test_invalid_project_state_bad_status(self):
        with pytest.raises(ValidationError):
            self.validate(self.state_schema, {
                "id": "p1", "name": "Demo", "objective": "test",
                "status": "unknown", "created_at": "2026-08-29T00:00:00Z",
                "updated_at": "2026-08-29T00:00:00Z", "version": 1,
                "authorization": {}, "tasks": [], "agents": {},
                "current_state": {"phase": "DRAFT", "next_action": "plan"},
            })

    def test_valid_audit_event(self):
        self.validate(self.audit_schema, {
            "event_id": "event-001", "timestamp": "2026-08-29T00:00:00Z",
            "actor": "orchestrator", "actor_type": "orchestrator",
            "action": "delegate", "target": "task-001", "project": "test",
            "task_id": None, "authority_source": None,
            "event_class": "execution_success", "evidence": [],
            "previous_state": {}, "new_state": {},
            "result": "allowed", "error": None,
        })

    def test_invalid_audit_event_bad_class(self):
        with pytest.raises(ValidationError):
            self.validate(self.audit_schema, {
                "event_id": "event-001", "timestamp": "2026-08-29T00:00:00Z",
                "actor": "orchestrator", "actor_type": "orchestrator",
                "action": "delegate", "target": "task-001", "project": "test",
                "event_class": "unknown_class", "evidence": [],
                "result": "allowed",
            })

    def test_invalid_audit_event_missing_required(self):
        with pytest.raises(ValidationError):
            self.validate(self.audit_schema, {"event_id": "e1"})  # missing many required

    def test_valid_role_mapping_disjoint(self):
        """allow ∩ deny must be empty (7-role mapping)."""
        roles = []
        for rid in ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]:
            roles.append({
                "id": rid, "preset": f"role-{rid}", "policy_ref": f"agents/{rid}/policy.yaml",
                "tool_instance": {"tool_name": f"subagent_{rid}", "provider": "spawn",
                                  "background_mode": "continuable", "max_depth": 1, "persona": f"role-{rid}"},
                "tool_filter": {"allow": ["read"], "deny": ["bash", "edit", "write"]},
            })
        doc = {
            "mapping_version": 1, "status": "finalized",
            "version_pin": "deepseek-harness-0.1.1-rc.2",
            "documentation_ref": "docs/tool-catalog.md",
            "preset_naming_convention": "role-<id>", "instance_naming_convention": "subagent_<id>",
            "roles": roles,
            "orchestrator": {"id": "orchestrator", "binding": "root_session", "policy_ref": "orchestrator/AGENT.md",
                             "delegation_tools": ["subagent"],
                             "tool_filter": {"allow": ["read", "subagent"], "deny": ["bash"]}},
            "consistency_rules": {"tool_names_verified": True},
        }
        self.validate(self.mapping_schema, doc)

    def test_invalid_role_mapping_duplicate_role(self):
        with pytest.raises(ValidationError):
            self.validate(self.mapping_schema, {
                "mapping_version": 1, "status": "finalized",
                "version_pin": "deepseek-harness-0.1.1-rc.2",
                "documentation_ref": "docs/tool-catalog.md",
                "preset_naming_convention": "role-<id>", "instance_naming_convention": "subagent_<id>",
                "roles": [],  # 0 roles, minItems=7
                "orchestrator": {"id": "orchestrator", "binding": "root_session", "policy_ref": "orchestrator/AGENT.md",
                                 "delegation_tools": ["subagent"],
                                 "tool_filter": {"allow": ["read"], "deny": ["bash"]}},
                "consistency_rules": {},
            })

    # =====================================================================
    # Role-definition schema tests
    # =====================================================================
    def test_valid_role_definition(self):
        self.validate(self.role_schema, {
            "role": "cto", "role_version": 1, "status": "finalized",
            "version_pin": "deepseek-harness-0.1.1-rc.2",
            "display_name": "CTO", "domain": "Engineering", "summary": "test",
            "capabilities": {"code_read": "yes", "code_write": "yes", "financial_analysis": "no"},
            "sandbox_approval_intent": {"sandbox": "workspace-write", "approval": "ask"},
            "tool_filter": {"allow": ["bash", "read"], "deny": []},
            "prohibited_actions": ["financial_transaction"],
            "invariants": {"no_self_delegation": True},
        })

    def test_invalid_role_definition_bad_role(self):
        with pytest.raises(ValidationError):
            self.validate(self.role_schema, {
                "role": "architect",  # not in enum
                "role_version": 1, "status": "finalized",
                "version_pin": "deepseek-harness-0.1.1-rc.2",
                "display_name": "Architect", "domain": "x", "summary": "x",
                "capabilities": {"code_read": "yes"},
                "sandbox_approval_intent": {"sandbox": "workspace-write", "approval": "ask"},
                "tool_filter": {"allow": ["read"], "deny": []},
                "prohibited_actions": [],
                "invariants": {},
            })

    def test_invalid_role_definition_bad_capability_value(self):
        with pytest.raises(ValidationError):
            self.validate(self.role_schema, {
                "role": "cto", "role_version": 1, "status": "finalized",
                "version_pin": "deepseek-harness-0.1.1-rc.2",
                "display_name": "CTO", "domain": "x", "summary": "x",
                "capabilities": {"code_read": "maybe"},  # not in enum
                "sandbox_approval_intent": {"sandbox": "workspace-write", "approval": "ask"},
                "tool_filter": {"allow": ["read"], "deny": []},
                "prohibited_actions": [],
                "invariants": {},
            })

    def test_invalid_role_definition_missing_required(self):
        with pytest.raises(ValidationError):
            self.validate(self.role_schema, {"role": "cto"})

    def test_invalid_role_definition_bad_sandbox(self):
        with pytest.raises(ValidationError):
            self.validate(self.role_schema, {
                "role": "cto", "role_version": 1, "status": "finalized",
                "version_pin": "deepseek-harness-0.1.1-rc.2",
                "display_name": "CTO", "domain": "x", "summary": "x",
                "capabilities": {"code_read": "yes"},
                "sandbox_approval_intent": {"sandbox": "danger", "approval": "ask"},  # bad sandbox
                "tool_filter": {"allow": ["read"], "deny": []},
                "prohibited_actions": [],
                "invariants": {},
            })

    def test_invalid_role_definition_tool_filter_missing_allow(self):
        """tool_filter must have both allow and deny."""
        with pytest.raises(ValidationError):
            self.validate(self.role_schema, {
                "role": "cto", "role_version": 1, "status": "finalized",
                "version_pin": "deepseek-harness-0.1.1-rc.2",
                "display_name": "CTO", "domain": "x", "summary": "x",
                "capabilities": {"code_read": "yes"},
                "sandbox_approval_intent": {"sandbox": "workspace-write", "approval": "ask"},
                "tool_filter": {"allow": ["read"]},  # missing deny
                "prohibited_actions": [],
                "invariants": {},
            })

    # =====================================================================
    # Agent-registry schema tests
    # =====================================================================
    def test_valid_registry(self):
        self.validate(self.registry_schema, {
            "registry_version": 1, "status": "foundation",
            "role_mapping": "config/role-preset-mapping.yaml",
            "orchestrator": {"id": "orchestrator", "kind": "coordination", "role": "Orch", "summary": "x"},
            "agents": [
                {"id": "zeko", "role": "operations", "display_name": "Zeko",
                 "domain": "Ops", "summary": "x", "default_policy": "agents/zeko/policy.yaml"},
                {"id": "cto", "role": "engineering", "display_name": "CTO",
                 "domain": "Eng", "summary": "x", "default_policy": "agents/cto/policy.yaml"},
                {"id": "cfo", "role": "finance", "display_name": "CFO",
                 "domain": "Fin", "summary": "x", "default_policy": "agents/cfo/policy.yaml"},
                {"id": "kai", "role": "research", "display_name": "Kai",
                 "domain": "Res", "summary": "x", "default_policy": "agents/kai/policy.yaml"},
                {"id": "somad", "role": "social", "display_name": "Somad",
                 "domain": "Soc", "summary": "x", "default_policy": "agents/somad/policy.yaml"},
                {"id": "badsector", "role": "adversarial_review", "display_name": "BadSector",
                 "domain": "Rev", "summary": "x", "default_policy": "agents/badsector/policy.yaml"},
                {"id": "nova", "role": "writing", "display_name": "Nova",
                 "domain": "Wri", "summary": "x", "default_policy": "agents/nova/policy.yaml"},
            ],
            "invariants": {"specialist_count": 7, "peer_relationship": True},
        })

    def test_invalid_registry_eighth_agent_rejected(self):
        """maxItems=7 enforces the seven-specialist topology."""
        agents = []
        for rid in ["zeko", "cto", "cfo", "kai", "somad", "badsector", "nova"]:
            agents.append({"id": rid, "role": "operations", "display_name": "X",
                           "domain": "x", "summary": "x",
                           "default_policy": f"agents/{rid}/policy.yaml"})
        agents.append({"id": "eighth", "role": "operations", "display_name": "Eighth",
                       "domain": "x", "summary": "x",
                       "default_policy": "agents/eighth/policy.yaml"})
        with pytest.raises(ValidationError):
            self.validate(self.registry_schema, {
                "registry_version": 1, "status": "foundation",
                "role_mapping": "config/role-preset-mapping.yaml",
                "orchestrator": {"id": "orchestrator", "kind": "coordination", "role": "O", "summary": "x"},
                "agents": agents,
                "invariants": {},
            })

    def test_invalid_registry_duplicate_id_rejected(self):
        """uniqueItems enforces distinct agent ids."""
        with pytest.raises(ValidationError):
            self.validate(self.registry_schema, {
                "registry_version": 1, "status": "foundation",
                "role_mapping": "config/role-preset-mapping.yaml",
                "orchestrator": {"id": "orchestrator", "kind": "coordination", "role": "O", "summary": "x"},
                "agents": [
                    {"id": "cto", "role": "engineering", "display_name": "CTO",
                     "domain": "x", "summary": "x", "default_policy": "agents/cto/policy.yaml"},
                    {"id": "cto", "role": "engineering", "display_name": "CTO",
                     "domain": "x", "summary": "x", "default_policy": "agents/cto/policy.yaml"},
                ],
                "invariants": {},
            })

    def test_invalid_registry_bad_orchestrator_kind(self):
        with pytest.raises(ValidationError):
            self.validate(self.registry_schema, {
                "registry_version": 1, "status": "foundation",
                "role_mapping": "config/role-preset-mapping.yaml",
                "orchestrator": {"id": "orchestrator", "kind": "execution", "role": "O", "summary": "x"},
                "agents": [
                    {"id": "cto", "role": "engineering", "display_name": "CTO",
                     "domain": "x", "summary": "x", "default_policy": "agents/cto/policy.yaml"},
                ],
                "invariants": {},
            })

    def test_invalid_registry_orchestrator_id_must_be_orchestrator(self):
        with pytest.raises(ValidationError):
            self.validate(self.registry_schema, {
                "registry_version": 1, "status": "foundation",
                "role_mapping": "config/role-preset-mapping.yaml",
                "orchestrator": {"id": "boss", "kind": "coordination", "role": "O", "summary": "x"},
                "agents": [
                    {"id": "cto", "role": "engineering", "display_name": "CTO",
                     "domain": "x", "summary": "x", "default_policy": "agents/cto/policy.yaml"},
                ],
                "invariants": {},
            })

    # =====================================================================
    # Task schema tests
    # =====================================================================
    def test_valid_task_intake(self):
        self.validate(self.task_intake_schema, {
            "objective": "research pricing", "scope": ["multi-agent-harness/**"],
            "project": "multi-agent-harness", "created_at": "2026-08-29T00:00:00Z",
        })

    def test_invalid_task_intake_missing_objective(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_intake_schema, {
                "scope": ["x"], "project": "p", "created_at": "2026-08-29T00:00:00Z",
            })

    def test_invalid_task_intake_empty_scope(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_intake_schema, {
                "objective": "o", "scope": [], "project": "p",
                "created_at": "2026-08-29T00:00:00Z",
            })

    def test_valid_task(self):
        self.validate(self.task_schema, {
            "task_id": "t-1", "objective": "engineering", "assigned_role": "cto",
            "risk_metadata": "MEDIUM", "project": "multi-agent-harness",
        })

    def test_invalid_task_bad_role(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_schema, {
                "task_id": "t-1", "objective": "x", "assigned_role": "orchestrator",
                "risk_metadata": "LOW", "project": "p",
            })

    def test_invalid_task_bad_risk(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_schema, {
                "task_id": "t-1", "objective": "x", "assigned_role": "cto",
                "risk_metadata": "CRITICAL", "project": "p",
            })

    def test_valid_task_result(self):
        self.validate(self.task_result_schema, {
            "task_id": "t-1", "assigned_role": "cto", "status": "SUCCEEDED",
            "confidence": "HIGH", "reported_at": "2026-08-29T00:00:00Z",
        })

    def test_invalid_task_result_bad_status(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_result_schema, {
                "task_id": "t-1", "assigned_role": "cto", "status": "DONE",
                "confidence": "LOW", "reported_at": "2026-08-29T00:00:00Z",
            })

    def test_invalid_task_result_bad_role(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_result_schema, {
                "task_id": "t-1", "assigned_role": "orchestrator", "status": "SUCCEEDED",
                "confidence": "LOW", "reported_at": "2026-08-29T00:00:00Z",
            })

    def test_invalid_task_result_bad_confidence(self):
        with pytest.raises(ValidationError):
            self.validate(self.task_result_schema, {
                "task_id": "t-1", "assigned_role": "cto", "status": "SUCCEEDED",
                "confidence": "MAX", "reported_at": "2026-08-29T00:00:00Z",
            })
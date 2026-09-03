"""Orchestrator Foundation tests — Phase 1D.

Covers the 12 required test areas:
  1. intake validation
  2. task decomposition
  3. routing
  4. delegation schema
  5. invalid authority
  6. scope expansion
  7. subdelegation denial
  8. BadSector PASS != authorization
  9. result schema
  10. state transition validation
  11. control-plane interface failures
  (12. integration: schema conformance of the new contracts)
"""

import json
import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from orchestrator.foundation import (
    TaskIntake, Task, Delegation, TaskResult,
    ContractError, RoutingError, StateTransitionError, MessagingError,
    select_agents, route_tasks, validate_no_fanout, ControlPlane,
    StateMachine, ProjectState, Context, Message, WorkflowRun, PHASE_CHAIN,
    GATE_PHASES, WorkflowError,
    SPECIALIST_ROLES, ORCHESTRATOR,
)
from orchestrator.foundation.contracts import DOMAIN_ROLE


# ===========================================================================
# 1. INTAKE VALIDATION
# ===========================================================================
class TestIntakeValidation:
    def test_valid_intake(self):
        i = TaskIntake(objective="analyze pricing for tier-2",
                       scope=("multi-agent-harness/**",),
                       expected_outcome="pricing analysis",
                       required_authority_context="delegation-001")
        assert i.has_authority_context()
        assert i.normalized_objective() == "analyze pricing for tier-2"

    def test_normalized_objective_collapses_whitespace(self):
        i = TaskIntake(objective="  analyze   pricing\n for tier-2 ",
                       scope=("x",))
        assert i.normalized_objective() == "analyze pricing for tier-2"

    def test_intake_requires_objective(self):
        with pytest.raises(ContractError):
            TaskIntake(objective="", scope=("x",))

    def test_intake_requires_scope(self):
        with pytest.raises(ContractError):
            TaskIntake(objective="objective", scope=())

    def test_intake_without_authority_is_draft_only(self):
        i = TaskIntake(objective="objective", scope=("x",))
        assert not i.has_authority_context()

    def test_intake_against_schema(self):
        import jsonschema
        schema = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "task-intake.schema.json")))
        jsonschema.Draft202012Validator(schema).validate(TaskIntake(
            objective="o", scope=("a",), project="p").to_dict())


# ===========================================================================
# 2. TASK DECOMPOSITION
# ===========================================================================
class TestTaskDecomposition:
    def test_valid_task(self):
        t = Task(task_id="t-1", objective="engineering", assigned_role="cto",
                 dependencies=("t-0",), risk_metadata="MEDIUM",
                 authorization_requirements=())
        assert t.assigned_role == "cto"

    def test_task_requires_valid_role(self):
        with pytest.raises(ContractError):
            Task(task_id="t-1", objective="x", assigned_role="orchestrator")
        with pytest.raises(ContractError):
            Task(task_id="t-1", objective="x", assigned_role="nobody")

    def test_task_invalid_risk(self):
        with pytest.raises(ContractError):
            Task(task_id="t-1", objective="x", assigned_role="cto", risk_metadata="CRITICAL")

    def test_task_invalid_auth_req(self):
        with pytest.raises(ContractError):
            Task(task_id="t-1", objective="x", assigned_role="cto",
                 authorization_requirements=("not_a_category",))

    def test_task_against_schema(self):
        import jsonschema
        schema = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "task.schema.json")))
        jsonschema.Draft202012Validator(schema).validate(Task(
            task_id="t-1", objective="o", assigned_role="cto",
            risk_metadata="LOW").to_dict())


# ===========================================================================
# 3. ROUTING
# ===========================================================================
class TestRouting:
    def test_routes_by_domain(self):
        assert select_agents(Task(task_id="t", objective="engineering", assigned_role="cto")) == ("cto",)
        assert select_agents(Task(task_id="t", objective="finance", assigned_role="cfo")) == ("cfo",)
        assert select_agents(Task(task_id="t", objective="research", assigned_role="kai")) == ("kai",)

    def test_secondary_minimum_set(self):
        # pricing -> cfo + kai (minimum set, not fan-out)
        sel = select_agents(Task(task_id="t", objective="pricing", assigned_role="cfo"))
        assert set(sel) == {"cfo", "kai"}
        assert len(sel) == 2

    def test_no_blanket_fanout(self):
        domains = ["operations", "engineering", "finance", "research",
                   "social", "review", "writing"]
        for d in domains:
            t = Task(task_id="t", objective=d, assigned_role=DOMAIN_ROLE.get(d))
            sel = select_agents(t)
            assert len(set(sel)) <= len(SPECIALIST_ROLES) - 1  # never all 7
        validate_no_fanout(("cto",))
        with pytest.raises(RoutingError):
            validate_no_fanout(SPECIALIST_ROLES)  # all 7 is a blanket fan-out

    def test_unknown_domain_raises(self):
        with pytest.raises(RoutingError):
            select_agents(Task(task_id="t", objective="quantum-cooking", assigned_role="cto"))

    def test_peer_topology_no_manager(self):
        # routing never assigns a specialist to "manage" another
        t = Task(task_id="t", objective="engineering", assigned_role="cto")
        assert "orchestrator" not in select_agents(t)
        assert all(r in SPECIALIST_ROLES for r in select_agents(t))

    def test_route_tasks_batch(self):
        tasks = [Task(task_id=f"t-{i}", objective=o, assigned_role=r)
                 for i, (o, r) in enumerate([("finance", "cfo"), ("research", "kai")])]
        out = route_tasks(tasks)
        assert out["t-0"] == ("cfo",)
        assert out["t-1"] == ("kai",)


# ===========================================================================
# 4. DELEGATION SCHEMA
# ===========================================================================
class TestDelegationSchema:
    def test_valid_delegation(self):
        d = Delegation(task="t-1", action="code_write", target="agents/**",
                       scope_operations=("code_write",), scope_resources=("agents/**",))
        assert d.is_active()
        assert not d.is_expired()

    def test_invalid_principal(self):
        with pytest.raises(ContractError):
            Delegation(principal="agent")

    def test_invalid_delegate(self):
        with pytest.raises(ContractError):
            Delegation(delegate="cto")

    def test_invalid_status(self):
        with pytest.raises(ContractError):
            Delegation(status="PENDING")

    def test_action_without_target(self):
        with pytest.raises(ContractError):
            Delegation(action="code_write", target="")

    def test_expiry_checked(self):
        d = Delegation(expires_at="2020-01-01T00:00:00Z")
        assert d.is_expired()

    def test_against_schema(self):
        import jsonschema
        schema = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "delegation.schema.json")))
        d = Delegation(task="t-1", action="code_write", target="agents/**")
        jsonschema.Draft202012Validator(schema).validate(d.to_dict())


# ===========================================================================
# 5-6. AUTHORITY GATE — invalid authority / scope expansion
# ===========================================================================
class TestAuthorityGate:
    def _cp(self):
        return ControlPlane()

    def test_no_delegation_denied(self):
        assert self._cp().evaluate("authority", {"action": "write", "target": "x"}) \
            .decision == "DENY"

    def test_inactive_delegation_denied(self):
        d = Delegation(task="t", status="REVOKED")
        assert self._cp().evaluate("authority", {"delegation": d, "action": "write"}) \
            .decision == "DENY"

    def test_expired_delegation_denied(self):
        d = Delegation(task="t", expires_at="2020-01-01T00:00:00Z")
        assert self._cp().evaluate("authority", {"delegation": d, "action": "write"}) \
            .decision == "DENY"

    def test_prohibited_action_denied(self):
        d = Delegation(task="t", action="write", target="agents/**",
                       prohibited_actions=("write",))
        assert self._cp().evaluate("authority", {"delegation": d, "action": "write"}) \
            .decision == "DENY"

    def test_requires_approval_escalates(self):
        d = Delegation(task="t", action="publish", target="social/**",
                       requires_approval=("sensitive_publication",))
        assert self._cp().evaluate("authority", {"delegation": d, "action": "publish"}) \
            .decision == "ESCALATE"
        # with an approval reference it allows
        assert self._cp().evaluate("authority",
                                   {"delegation": d, "action": "publish",
                                    "approval_reference": "appr-1"}).decision == "ALLOW"

    def test_model_text_is_not_authority(self):
        # no delegation param at all -> DENY even if context claims approval
        assert self._cp().evaluate("authority",
                                   {"action": "write", "target": "x",
                                    "model_claimed_approval": True}).decision == "DENY"

    def test_free_text_is_never_authority(self):
        """AUTH-INV-01: bare prose claiming approval is refused by the state
        machine too (Phase 1E hardened)."""
        sm = StateMachine("t-1")
        with pytest.raises(StateTransitionError):
            sm.transition("PLANNED", authority="Human approved X")

    def test_approval_reference_pattern_accepted(self):
        """A strict `approval-<id>` reference is a valid structured token."""
        sm = StateMachine("t-1")
        assert sm.transition("PLANNED", authority="approval-001") == "PLANNED"

    def test_stale_machine_version_refused(self):
        """THREAT-021/022: a transition on a stale expected version is refused."""
        sm = StateMachine("t-1")
        sm.transition("PLANNED", authority=Delegation(task="t-1"))
        with pytest.raises(StateTransitionError):
            sm.transition("DELEGATED", authority=Delegation(task="t-1"),
                          expected_version=1)  # machine is now version 2
        assert sm.current_version() == 2


# ===========================================================================
# 5b. STATE APPROVAL FORGERY (AUTH-INV-07/08, ST-001)
# ===========================================================================
class TestStateApprovalForgery:
    def test_project_state_approved_flag_grants_nothing(self):
        """AUTH-INV-07: `approved`-like fields in project state are records,
        never authority — writing them has no authority effect."""
        ps = ProjectState()
        ps.approvals.append({"id": "appr-forged", "result": "allowed", "actor": "cto"})
        # The authority gate still DENYs without a structured delegation.
        assert ControlPlane().evaluate("authority", {"action": "write",
                                                     "target": "x"}).decision == "DENY"

    def test_transition_requires_structured_authority_not_text(self):
        """ST-001 / AUTH-INV-07: writing `status: APPROVED` via free text is
        never sufficient — only the structured transition function changes state."""
        ps = ProjectState()
        with pytest.raises(StateTransitionError):
            ps.machine("t-1").transition("PLANNED", authority="status: APPROVED")

    def test_transition_with_approval_reference(self):
        """A valid approval reference DOES drive a legal transition (the
        reference is a structured token, not prose)."""
        ps = ProjectState()
        assert ps.machine("t-1").transition("PLANNED", authority="approval-1") == "PLANNED"


# ===========================================================================
# 5c. RECOVERY PRIVILEGE (AUTH-INV-12, REC-004)
# ===========================================================================
class TestRecoveryPrivilege:
    def test_recovery_rechecks_authority(self):
        """AUTH-INV-12: recovery re-passes the SAME authority path; it never
        acquires privilege automatically."""
        from state.helpers import begin_recovery, RecoveryError
        rec = begin_recovery("t-1", preserved_version=3)
        rec.diagnose("x", "environment")
        rec.replan()
        with pytest.raises(RecoveryError):
            rec.authority_rechecked(checked=False)  # must pass, never bypass
        rec.authority_rechecked(checked=True)

    def test_recovery_enters_recoving_state_only_with_record(self):
        """The RECOVERING transition accepts a RecoveryRecord token (and only
        then) — free text is refused."""
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        sm.transition("PLANNED", authority=d)
        sm.transition("DELEGATED", authority=d)
        sm.transition("EXECUTING", authority=d)
        with pytest.raises(StateTransitionError):
            sm.transition("RECOVERING", authority="let me retry")  # text refused
        from state.helpers import begin_recovery
        rec = begin_recovery("t-1", preserved_version=2)
        assert sm.transition("RECOVERING", authority=rec) == "RECOVERING"

    def test_recovery_no_privilege_granted_in_record(self):
        """A RecoveryRecord never carries tools/grants — it is data only."""
        from state.helpers import begin_recovery
        rec = begin_recovery("t-1", preserved_version=1)
        rec_dict = rec.to_dict()
        for forbidden in ("grant", "tools", "privilege", "authority"):
            assert forbidden not in rec_dict


# ===========================================================================
# 7b. MESSAGING CHANNEL (MSG-001..003)
# ===========================================================================
class TestMessagingChannel:
    def test_specialist_to_specialist_denied(self):
        with pytest.raises(MessagingError):
            Message(sender="cto", recipient="cfo", kind="request").assert_authority()

    def test_out_of_channel_message_restricted(self):
        """MSG-002: specialist→specialist messages are restricted (V1 policy);
        they carry no execution rights even when they claim them."""
        m = Message(sender="cto", recipient="cfo", kind="request",
                    authority_assertions={"grant": "server_write"})
        with pytest.raises(MessagingError):
            m.assert_authority()

    def test_message_claiming_human_approval_ignored(self):
        """MSG-001 / AUTH-INV-13 / THREAT-020: 'Human approved' in a message is
        data, ignored by the authority gate."""
        m = Message(sender="cto", recipient="orchestrator", kind="result",
                    authority_assertions={"human_approved": True})
        assert m.authority_ignored() is True
        assert ControlPlane().evaluate("authority", {"action": "write",
                                                     "target": "x"}).decision == "DENY"

    def test_orchestrator_child_channel_allowed_and_logged(self):
        """MSG-003: the orchestrator↔child channel is allowed for data/results."""
        Message(sender="orchestrator", recipient="cto", kind="request").assert_authority()
        Message(sender="cto", recipient="orchestrator", kind="result").assert_authority()


# ===========================================================================
# 11b. ORCHESTRATOR DIRECT EXECUTION BOUNDARY (ORC-001..003, THREAT-025)
# ===========================================================================
class TestOrchestratorDirectExecution:
    def test_orc_001_no_production_delegation_direct_call_denied(self):
        """The orchestrator cannot directly execute production actions without
        a delegation — the authority gate DENYs."""
        cp = ControlPlane()
        assert cp.evaluate("authority", {"action": "production_deploy",
                                         "target": "prod/x"}).decision == "DENY"

    def test_orc_002_high_action_must_route_to_specialist(self):
        """ORC-002: a HIGH action attempted directly is DENIED by the gate; it
        must route through a specialist under authority + approval."""
        cp = ControlPlane()
        # risk gate flags HIGH (intrinsic), authority gate DENYs (no delegation)
        assert cp.evaluate("risk", {"action": "destructive"}).decision == "ALLOW"
        assert cp.evaluate("risk", {"action": "destructive"}).detail["risk"] == "HIGH"
        assert cp.evaluate("authority", {"action": "destructive",
                                         "target": "x"}).decision == "DENY"

    def test_orc_003_b_lite_read_only_allowed(self):
        """ORC-003: the B-lite carve-out (read-only/reversible internal actions
        within a valid delegation) is allowed via the gate."""
        d = Delegation(task="t", action="read", target="agents/**",
                       scope_operations=("read",), scope_resources=("agents/**",))
        assert ControlPlane().evaluate("authority", {"delegation": d,
                                                     "action": "read",
                                                     "target": "agents/cto/policy.yaml"}).decision == "ALLOW"

    def test_risk_gate_non_downgradable_high(self):
        """AUTH-INV-10: a destructive action declared LOW is still intrinsic
        HIGH in the risk gate — model judgment cannot downgrade it."""
        cp = ControlPlane()
        dec = cp.evaluate("risk", {"action": "destructive", "risk": "LOW"})
        assert dec.decision == "ALLOW"
        assert dec.detail["risk"] == "HIGH"  # reclassified, never downgraded


# ===========================================================================
# 7. SUBDELEGATION DENIAL
# ===========================================================================
class TestSubdelegationDenial:
    def test_specialist_to_specialist_denied(self):
        with pytest.raises(MessagingError):
            Message(sender="cto", recipient="cfo", kind="request").assert_authority()

    def test_specialist_to_orchestrator_allowed(self):
        Message(sender="cto", recipient="orchestrator", kind="result").assert_authority()

    def test_messages_cannot_create_authority(self):
        m = Message(sender="cto", recipient="orchestrator", kind="result",
                    authority_assertions={"grant": "write"})
        assert m.authority_ignored() is True  # assertions are data, ignored


# ===========================================================================
# 8. BADSECTOR PASS != AUTHORIZATION
# ===========================================================================
class TestBadSectorPassNotAuthority:
    def test_pass_alone_denied(self):
        cp = ControlPlane()
        # PASS with no provenance -> DENY
        assert cp.evaluate("badsector_review", {"review": {"verdict": "PASS"}}) \
            .decision == "DENY"

    def test_pass_with_provenance_clears_review_only(self):
        cp = ControlPlane()
        assert cp.evaluate("badsector_review",
                           {"review": {"verdict": "PASS", "review_id": "r-1",
                                       "input_hash": "abc"}}).decision == "ALLOW"
        # clearing review != authorization: authority gate still DENY without delegation
        assert cp.evaluate("authority", {"action": "write", "target": "x"}) \
            .decision == "DENY"

    def test_non_pass_denied(self):
        cp = ControlPlane()
        assert cp.evaluate("badsector_review", {"review": {"verdict": "REWORK"}}) \
            .decision == "DENY"

    def test_conditional_review_not_required_low(self):
        """Phase 1E: review is conditional — LOW risk, non-intrinsic action
        with no review → ALLOW (not required)."""
        cp = ControlPlane()
        assert cp.evaluate("badsector_review", {"risk": "LOW", "action": "read"}) \
            .decision == "ALLOW"

    def test_mandatory_review_skipped_denied(self):
        """Phase 1E: mandatory review (HIGH risk / intrinsic-high action)
        skipped → DENY (THREAT-015 transition violation)."""
        cp = ControlPlane()
        assert cp.evaluate("badsector_review", {"risk": "HIGH", "action": "deploy"}) \
            .decision == "DENY"
        assert cp.evaluate("badsector_review", {"risk": "LOW", "action": "destructive"}) \
            .decision == "DENY"
        assert cp.evaluate("badsector_review",
                           {"risk": "LOW", "action": "read",
                            "review_required": True}).decision == "DENY"

    def test_mandatory_review_pass_with_provenance_clears_review_only(self):
        """Phase 1E: a mandatory review satisfied with a proven PASS clears
        review; authority gate still DENY without delegation."""
        cp = ControlPlane()
        assert cp.evaluate("badsector_review",
                           {"risk": "HIGH", "action": "deploy",
                            "review": {"verdict": "PASS", "review_id": "r-9",
                                       "input_hash": "abc"}}).decision == "ALLOW"
        # PASS != authorization: authority gate still DENY without delegation
        assert cp.evaluate("authority", {"action": "deploy", "target": "x"}) \
            .decision == "DENY"


# ===========================================================================
# 9. RESULT SCHEMA
# ===========================================================================
class TestResultSchema:
    def test_valid_result(self):
        r = TaskResult(task_id="t-1", assigned_role="cto", status="SUCCEEDED",
                       evidence=("build-ok.txt",), confidence="HIGH")
        assert r.status == "SUCCEEDED"

    def test_invalid_status(self):
        with pytest.raises(ContractError):
            TaskResult(task_id="t-1", assigned_role="cto", status="DONE")

    def test_invalid_role(self):
        with pytest.raises(ContractError):
            TaskResult(task_id="t-1", assigned_role="orchestrator")

    def test_against_schema(self):
        import jsonschema
        schema = json.load(open(os.path.join(PROJECT_ROOT, "schemas", "task-result.schema.json")))
        jsonschema.Draft202012Validator(schema).validate(TaskResult(
            task_id="t-1", assigned_role="cto", status="SUCCEEDED").to_dict())


# ===========================================================================
# 10. STATE TRANSITION VALIDATION
# ===========================================================================
class TestStateTransition:
    def test_draft_to_planned_requires_authority(self):
        sm = StateMachine("t-1")
        with pytest.raises(StateTransitionError):
            sm.transition("PLANNED", authority=None)

    def test_draft_to_planned_with_delegation(self):
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        assert sm.transition("PLANNED", authority=d) == "PLANNED"

    def test_invalid_transition_denied(self):
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        sm.transition("PLANNED", authority=d)
        # PLANNED -> COLLECTED is not a valid direct transition
        with pytest.raises(StateTransitionError):
            sm.transition("COLLECTED")

    def test_terminal_state_immutable(self):
        sm = StateMachine("t-1")
        d = Delegation(task="t-1")
        sm.transition("PLANNED", authority=d)
        sm.transition("DELEGATED", authority=d)
        sm.transition("EXECUTING", authority=d)
        sm.transition("COLLECTED")
        sm.transition("SYNTHESIZING")
        sm.transition("COMPLETE")
        with pytest.raises(StateTransitionError):
            sm.transition("PLANNED")

    def test_workflow_phase_chain_complete(self):
        wf = WorkflowRun(objective="o")
        for _ in range(len(PHASE_CHAIN) - 1):
            wf.advance()
        assert wf.current_phase() == PHASE_CHAIN[-1]


# ===========================================================================
# 11. CONTROL-PLANE INTERFACE FAILURES
# ===========================================================================
class TestControlPlaneInterface:
    def test_unknown_gate_fails_closed(self):
        cp = ControlPlane()
        assert cp.evaluate("nonexistent_gate", {}).decision == "DENY"

    def test_execution_gate_denies_protected_path(self, tmp_path):
        cp = ControlPlane()
        base = str(tmp_path)
        decision = cp.evaluate("execution", {"action": "write",
                                             "target": "state/registry/x.json",
                                             "base": base})
        assert decision.decision == "DENY"
        assert "protected" in decision.reason

    def test_execution_gate_allows_authorized_path(self, tmp_path):
        cp = ControlPlane()
        base = str(tmp_path)
        assert cp.evaluate("execution", {"action": "write",
                                         "target": "agents/cto/x.py",
                                         "base": base}).decision == "ALLOW"

    def test_execution_gate_denies_traversal(self, tmp_path):
        cp = ControlPlane()
        assert cp.evaluate("execution", {"action": "write", "target": "../x",
                                         "base": str(tmp_path)}).decision == "DENY"

    def test_execution_gate_denies_malformed(self, tmp_path):
        cp = ControlPlane()
        assert cp.evaluate("execution", {"action": "write", "target": "",
                                         "base": str(tmp_path)}).decision == "DENY"

    def test_evidence_gate_fail_closed_on_high(self):
        cp = ControlPlane()
        assert cp.evaluate("evidence", {"risk": "HIGH", "evidence": []}).decision == "DENY"

    def test_recovery_gate_no_blind_retry(self):
        cp = ControlPlane()
        assert cp.evaluate("recovery", {"attempts": 1}).decision == "DENY"
        assert cp.evaluate("recovery", {"attempts": 0, "cause_diagnosed": True}) \
            .decision == "ALLOW"

    def test_verification_requires_evidence_for_complete(self):
        cp = ControlPlane()
        r = TaskResult(task_id="t", assigned_role="cto", status="SUCCEEDED", evidence=())
        assert cp.evaluate("verification", {"result": r}).decision == "DENY"
        r2 = TaskResult(task_id="t", assigned_role="cto", status="SUCCEEDED",
                        evidence=("e1",))
        assert cp.evaluate("verification", {"result": r2}).decision == "ALLOW"


# ===========================================================================
# 12. CONTEXT BOUNDARIES
# ===========================================================================
class TestContextBoundaries:
    def test_visibility_matrix(self):
        global_ctx = Context("GLOBAL")
        project_ctx = Context("PROJECT")
        task_ctx = Context("TASK", owner="t-1")
        agent_ctx = Context("AGENT", owner="cto")
        assert global_ctx.can_read(agent_ctx)          # GLOBAL reads all
        assert project_ctx.can_read(task_ctx)          # PROJECT reads TASK
        assert not task_ctx.can_read(agent_ctx)        # TASK cannot read AGENT
        assert not agent_ctx.can_read(project_ctx)     # AGENT cannot read PROJECT
        assert task_ctx.can_read(task_ctx)

    def test_context_requires_owner_for_task_agent(self):
        with pytest.raises(ValueError):
            Context("TASK")
        with pytest.raises(ValueError):
            Context("AGENT")

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            Context("SECRET")


# ===========================================================================
# WORKFLOW SKELETON STRUCTURE
# ===========================================================================
class TestWorkflowSkeleton:
    def test_phase_chain_matches_contract(self):
        """Phase 1E: 15-phase sequence
        INTAKE → UNDERSTAND → CLASSIFY → RISK_GATE → DECOMPOSE → SELECT →
        DELEGATE → COLLECT → EVIDENCE_GATE → SYNTHESIZE → CONFLICT_GATE →
        REVIEW_GATE → AUTHORITY_GATE → EXECUTE_GATE → VERIFY_GATE"""
        expected = ("intake", "understand", "classify", "risk_gate",
                    "decompose", "select", "delegate", "collect",
                    "evidence_gate", "synthesize", "conflict_gate",
                    "review_gate", "authority_gate", "execute_gate",
                    "verify_gate")
        assert PHASE_CHAIN == expected
        assert len(PHASE_CHAIN) == 15

    def test_gate_phases_are_placeholders(self):
        wf = WorkflowRun(objective="o")
        # advance through all phases; verify each gate phase records is_gate
        for _ in range(len(PHASE_CHAIN) - 1):
            prev = wf.current_phase()
            wf.advance()
            recorded = wf.steps[-1]
            assert recorded["is_gate"] == (recorded["phase"] in GATE_PHASES), \
                f"is_gate mismatch for phase {recorded['phase']}"

    def test_all_gate_phases_in_gate_phases(self):
        """All 7 gate phases are in GATE_PHASES."""
        assert GATE_PHASES == {"risk_gate", "evidence_gate", "conflict_gate",
                               "review_gate", "authority_gate", "execute_gate",
                               "verify_gate"}

    def test_gate_clearing_requires_allow(self):
        """Phase 1E: check_gate STOPS on non-ALLOW decisions."""
        wf = WorkflowRun(objective="o")
        # advance to the first gate phase (risk_gate)
        for _ in range(PHASE_CHAIN.index("risk_gate")):
            wf.advance()
        assert wf.current_phase() == "risk_gate"
        # DENY → STOP
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.check_gate("DENY", gate="risk")
        # missing → STOP
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.check_gate("", gate="risk")
        # None → STOP
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.check_gate(None, gate="risk")

    def test_gate_clearing_records_and_tracks(self):
        """Phase 1E: ALLOW clears the gate and adds to gates_cleared."""
        wf = WorkflowRun(objective="o")
        for _ in range(PHASE_CHAIN.index("risk_gate")):
            wf.advance()
        wf.check_gate("ALLOW", gate="risk", detail={"risk": "LOW"})
        assert "risk_gate" in wf.gates_cleared()
        assert wf.steps[-1]["decision"] == "ALLOW"
        assert wf.steps[-1]["detail"] == {"risk": "LOW"}

    def test_check_gate_raises_on_non_gate_phase(self):
        """check_gate on a non-gate phase raises WorkflowError."""
        wf = WorkflowRun(objective="o")
        assert wf.current_phase() == "intake"  # not a gate
        with pytest.raises(WorkflowError, match="not a gate phase"):
            wf.check_gate("ALLOW")

    def test_execution_authority_recheck_passes_on_allow(self):
        """Phase 1E: require_execution_authority_recheck records when ALLOW."""
        wf = WorkflowRun(objective="o")
        for _ in range(PHASE_CHAIN.index("execute_gate")):
            wf.advance()
        assert wf.current_phase() == "execute_gate"
        wf.require_execution_authority_recheck("ALLOW")
        assert wf.steps[-1]["gate"] == "authority_recheck"
        assert wf.steps[-1]["decision"] == "ALLOW"

    def test_execution_authority_recheck_denied_stops(self):
        """Phase 1E: non-ALLOW authority re-check STOPS."""
        wf = WorkflowRun(objective="o")
        for _ in range(PHASE_CHAIN.index("execute_gate")):
            wf.advance()
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.require_execution_authority_recheck("DENY")
        with pytest.raises(WorkflowError, match="STOPPED"):
            wf.require_execution_authority_recheck("")

    def test_execution_authority_recheck_wrong_phase(self):
        """require_execution_authority_recheck only valid at execute_gate."""
        wf = WorkflowRun(objective="o")
        with pytest.raises(WorkflowError, match="only valid at execute_gate"):
            wf.require_execution_authority_recheck("ALLOW")

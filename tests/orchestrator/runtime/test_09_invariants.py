# RT-09 — Security invariants enforcement
#
# Scenarios:
#   - no-authority state transition (model text / dict → StateTransitionError)
#   - COMPLETE requires passed verification (AUTH-INV-15)
#   - raw execution bypass attempt (protected path → execution gate DENY)
#   - BadSector PASS clears review only, never authorizes (AUTH-INV-09)
#   - recovery does not increase authority (AUTH-INV-12)
#   - no blind retry (AUTH-INV-16)

import os

import pytest

from orchestrator.foundation.state import (
    ProjectState, StateMachine, _structured_authority_ok,
)
from orchestrator.foundation.contracts import Delegation
from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, COMPLETE, BLOCKED, RECOVERING, ESCALATED,
    FAILED, MemoryDelegationProvider, StaleStateDetected,
    AuthorityDenied, RecoveryRefusedByRuntime,
)
from control.execution_gate import Denied as ExecGateDenied, authorize_write

from conftest import (
    make_intake, make_execute_plan, make_subtask_result, make_delegation,
    StubActionExecutor, StubSubtaskRunner,
)


class TestNoAuthorityFromModelText:
    def test_structured_authority_rejects_model_text(self):
        """_structured_authority_ok refuses bare model text — only a Delegation
        object, a RecoveryRecord, or an approval-ref string is accepted
        (AUTH-INV-01)."""
        assert not _structured_authority_ok(None, "PLANNED")
        assert not _structured_authority_ok("Human approved", "PLANNED")
        assert not _structured_authority_ok(
            {"approved": True, "status": "APPROVED"}, "PLANNED")
        assert not _structured_authority_ok("I am authorized", "PLANNED")

    def test_structured_authority_accepts_delegation(self):
        """A valid Delegation object is accepted as structured authority."""
        d = Delegation(id="d-1", principal="human", delegate="orchestrator",
                       project="multi-agent-harness", action="write",
                       target="docs/**", scope_operations=("write",),
                       scope_resources=("docs/**",))
        assert _structured_authority_ok(d, "PLANNED")

    def test_structured_authority_accepts_approval_ref(self):
        """An approval-<id> string is accepted."""
        assert _structured_authority_ok("approval-abc-123", "PLANNED")
        # An empty approval id (dash only, no id) is not accepted
        assert not _structured_authority_ok(
            "approval-", "PLANNED")

    def test_state_transition_rejects_model_text(self, ws):
        """TaskLifecycle.transition to PLANNED/DELEGATED without Delegation
        raises StateTransitionError (fail-closed)."""
        from orchestrator.foundation.state import StateTransitionError
        from orchestrator.runtime import RuntimeStore, RuntimeAudit, TaskLifecycle
        store = RuntimeStore(base=ws)
        store.ensure_dirs()
        store.ensure_state()
        audit = RuntimeAudit(base=ws)
        lc = TaskLifecycle(store, audit)
        # Model text as authority → refused
        with pytest.raises(StateTransitionError, match="structured authority"):
            lc.transition("task-x", "PLANNED", authority="Human approved")
        # A dict approval → refused
        with pytest.raises(StateTransitionError, match="structured authority"):
            lc.transition("task-x", "PLANNED",
                          authority={"approved": True})
        # A valid approval reference → accepted (but the project state
        # delegate must pass it; the machine accepts it).
        lc.transition("task-x", "PLANNED",
                      authority="approval-hum-001")
        assert lc.state("task-x") == "PLANNED"
        # A valid Delegation → accepted
        d = make_delegation()
        lc.transition("task-x", "DELEGATED", authority=d)
        assert lc.state("task-x") == "DELEGATED"


class TestCompleteRequiresVerification:
    def test_flow_rejects_complete_without_verification(self, ws,
                                                       subtask_runner):
        """A flow where the executor returns a claim but verification fails
        never reaches COMPLETE (AUTH-INV-15)."""
        provider = MemoryDelegationProvider(make_delegation())
        executor = StubActionExecutor(
            observed={"exit_code": 1, "target": "agents/cto/x.txt"})
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=executor,
                             flow_id="test-noverify")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt",
                expected_outcome={"exit_code": 0}))
        # Observed 1 != expected 0 → verification not passed → RECOVERING
        assert result.outcome == RECOVERING, result.outcome
        assert result.final_state != "COMPLETE"

    def test_flow_with_claimed_success_but_no_evidence(self, ws,
                                                        subtask_runner):
        """A subtask that claims SUCCEEDED but provides no evidence:
        HIGH risk → evidence gate DENY (no COMPLETE)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        executor = StubActionExecutor()
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=executor,
                             flow_id="test-noevid")
        # Subtask returns SUCCEEDED but with empty evidence
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=()))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            declared_risk="HIGH")
        # HIGH risk + no evidence → evidence gate DENY → BLOCKED
        assert result.outcome == BLOCKED, result.outcome
        assert result.final_state != "COMPLETE"


class TestRawExecutionBypass:
    def test_execution_gate_denies_protected_path(self, ws):
        """The execution gate denies writes to protected paths
        (state/registry/**, audit/**) even when the authority gate would allow
        them (ADR 0002)."""
        with pytest.raises(ExecGateDenied, match="protected"):
            authorize_write("write", "state/registry/evil.json", base=ws)
        with pytest.raises(ExecGateDenied, match="protected"):
            authorize_write("write", "audit/events.jsonl", base=ws)

    def test_flow_denies_write_to_protected_path(self, ws, subtask_runner):
        """A plan targeting a protected path is denied at execution time even
        when the delegation would allow the target."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("write",),
            scope_resources=("state/registry/**", "multi-agent-harness/**"),
        ))
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-bypass01")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="state/registry/evil.json"))
        # Execution gate denies → AuthorityDenied → BLOCKED
        assert result.outcome == BLOCKED, result.outcome
        assert not os.path.exists(
            os.path.join(ws, "state/registry/evil.json"))

    def test_no_consequential_raw_dsh_bypass(self):
        """The runtime module contains no direct DSH write calls — inspect
        that the default executor routes through write_through."""
        # This is a static module-level check that the orchestrator runtime
        # does not import or call raw DSH tools.
        import orchestrator.runtime.flow as f_mod
        import inspect
        src = inspect.getsource(f_mod)
        # The default executor calls write_through NOT bare open/write.
        assert "write_through" in src, \
            "default executor must use write_through for writes"
        # No direct 'open(' or 'os.write' or 'subprocess' in the executor
        # (excludes docstrings and comments)
        unsafe = {"open(", "os.write(", "subprocess."}
        for line in src.split("\n"):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or \
               stripped.startswith("'''"):
                continue
            if any(u in stripped for u in unsafe):
                # The executor exception is the write_through path itself
                # which uses atomic_write internally; that's sanctioned.
                if "write_through" not in stripped:
                    pytest.fail(
                        f"raw DSH bypass detected in flow.py: {stripped}")


class TestBadsectorReviewPASS:
    def test_badsector_pass_clears_review_only(self, ws, subtask_runner,
                                                action_executor):
        """A BadSector PASS clears the adversarial_review stage but NEVER
        grants authority — a delegation DENY still blocks execution
        (AUTH-INV-09)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",),
            scope_resources=("agents/**", "docs/**", "multi-agent-harness/**"),
        ))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))

        # Capture the exact synthesis the flow will review: run once WITHOUT a
        # review (mandatory review skipped -> BLOCKED at adversarial_review),
        # but the synthesis is already populated by the SYNTHESIZE phase.
        import os as _os
        from orchestrator.runtime import ExecutionFlow as _EF
        from tests.conftest import o3_daemon_context
        # Each run gets its OWN O3 daemon root so protected state is isolated
        # per run (O3 Phase B: daemon root == run workspace).
        with o3_daemon_context(_os.path.join(ws, "run_a")):
            ws_a = _os.path.join(ws, "run_a")
            for sub in ("state/registry", "state/projects", "audit",
                        "agents/cto", "docs"):
                _os.makedirs(_os.path.join(ws_a, sub), exist_ok=True)
            flow_a = _EF(base=ws_a, provider=provider,
                         subtask_runner=subtask_runner,
                         executor=action_executor,
                         flow_id="test-bs-capture")
            result_a = flow_a.run(
                make_intake(objective="engineering"),
                execute_plan=make_execute_plan(target="agents/cto/x.txt"),
                review_required=True, review=None)
            assert result_a.phase == "adversarial_review"
            from control.badsector import _input_hash as _bs_hash
            expected_hash = _bs_hash(result_a.synthesis)

        # Now run with a REAL proven PASS: review gate ALLOWs, authority gate
        # DENYs (read-only delegation, write plan). Use a FRESH workspace so
        # the task machine starts from DRAFT.
        with o3_daemon_context(_os.path.join(ws, "run_b")):
            ws_b = _os.path.join(ws, "run_b")
            for sub in ("state/registry", "state/projects", "audit",
                        "agents/cto", "docs"):
                _os.makedirs(_os.path.join(ws_b, sub), exist_ok=True)
            flow_b = _EF(base=ws_b, provider=provider,
                         subtask_runner=subtask_runner,
                         executor=action_executor,
                         flow_id="test-bs-pass01")
            review = {
                "verdict": "PASS",
                "review_id": "review-rt-001",
                "input_hash": expected_hash,
            }
            result = flow_b.run(
                make_intake(objective="engineering"),
                execute_plan=make_execute_plan(target="agents/cto/x.txt"),
                review_required=True, review=review)
            assert result.outcome == BLOCKED, \
                f"expected BLOCKED got {result.outcome}"
            # The review gate passed (PASS clears the review stage)
            reviews = [g for g in result.gates if g["gate"] == "badsector_review"]
            assert reviews, "no badsector_review gate record"
            assert reviews[-1]["decision"] == "ALLOW", \
                f"review should ALLOW but got {reviews[-1]}"
            # The authority gate still denied (PASS != authorization)
            auths = [g for g in result.gates if g["gate"] == "authority"]
            assert auths, "no authority gate record"
            assert auths[-1]["decision"] == "DENY", \
                f"authority should DENY but got {auths[-1]}"

    def test_badsector_pass_with_reject_denied(self, flow, subtask_runner):
        """A mandatory BadSector review returning REJECT → DENY
        (THREAT-014/015)."""
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review={"verdict": "REJECT", "review_id": "review-2",
                    "input_hash": "hash-2"},
        )
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"


class TestRecoveryNoEscalation:
    def test_recovery_authority_recheck_denies(self, ws, subtask_runner):
        """Recovery re-checks authority (AUTH-INV-12) — if the delegation has
        been revoked since the initial execution, recovery is refused."""
        provider = MemoryDelegationProvider(make_delegation())
        executor = StubActionExecutor(
            observed={"exit_code": 1, "target": "agents/cto/x.txt"})
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             executor=executor,
                             flow_id="test-rec-nopriv")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt",
                expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        # Revoke the delegation
        provider.revoke("delegation-test-001",
                        reason="revoked before recovery")
        fixed_executor = StubActionExecutor(
            observed={"exit_code": 0, "target": "agents/cto/x.txt"})
        flow.executor = fixed_executor
        with pytest.raises(RecoveryRefusedByRuntime,
                           match="AUTH-INV-12|recovery re-check"):
            flow.recover(cause="fixed exit code", failure_class="logic")


class TestLifecycleTransitionGuards:
    def test_stale_state_detected_in_flow(self, ws, subtask_runner):
        """A parallel writer that bumps the state version between planning and
        execution raises StaleStateDetected (THREAT-021/022)."""
        provider = MemoryDelegationProvider(make_delegation())
        flow = ExecutionFlow(base=ws, provider=provider,
                             subtask_runner=subtask_runner,
                             flow_id="test-stale-flow")
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="x", evidence=("e",)))

        def _bump():
            from control.execution_gate import write_through
            from orchestrator.runtime.store import encode_project_state
            store = flow._get_store()
            ps = store.load_project_state()
            ps.version += 1
            store.persist(ps, expected_version=ps.version - 1)

        flow.pre_execute = _bump
        result = flow.run(make_intake(objective="engineering"),
                          execute_plan=make_execute_plan(
                              target="agents/cto/x.txt"))
        assert result.outcome == BLOCKED, result.outcome
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "version_conflict"
                   for e in events)

    def test_invalid_machine_transition_refused(self, ws):
        """An invalid state transition (e.g. DRAFT → COMPLETE) is refused
        by the state machine (THREAT-021)."""
        from orchestrator.foundation.state import StateMachine, StateTransitionError
        sm = StateMachine("task-test")
        assert sm.current() == "DRAFT"
        with pytest.raises(StateTransitionError, match="invalid transition"):
            sm.transition("COMPLETE")  # no authority + invalid transition
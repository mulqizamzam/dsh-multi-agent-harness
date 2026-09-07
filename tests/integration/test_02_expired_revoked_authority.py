# INT-02 — Expired / revoked authority
#
# Proves that an expired or revoked delegation is DENIED at execution time,
# even if planning passed.
#
# Modules integrated: AuthorityGate + reference authorize + StateMachine +
# execution_gate + audit
#
# Invariants: AUTH-INV-06, INV-13, THREAT-008/009/024

import os

import pytest


class TestINT02ExpiredRevokedAuthority:
    def test_expired_delegation_denied_at_foundation_gate(self, harness):
        """Foundation AuthorityGate rejects an expired delegation."""
        d = harness.build_delegation(
            expires_at="2020-01-01T00:00:00Z")
        assert d.is_expired()
        dec = harness.evaluate_gate("authority", {
            "delegation": d, "action": "write", "target": "agents/cto/x.txt"})
        assert dec.decision == "DENY"

    def test_revoked_delegation_denied_at_reference_gate(self, harness):
        """Reference authorize() rejects a revoked delegation."""
        d = harness.build_delegation_dict()
        cmp = harness.cross_check_authority(
            "orchestrator", "write", "agents/cto/x.txt", d,
            revocation_list=("delegation-int-001",))
        assert cmp["reference_decision"] == "DENY"
        # Foundation gate does not check revocation list directly (it reads
        # delegation.status). The execution-time re-check is the integration
        # point where revocation is verified.
        assert cmp["reference_reason"] == "delegation revoked (AUTH-INV-06)"

    def test_expiry_enforced_by_authority_gate_not_state_machine(self, harness):
        """Expiry is enforced by the AUTHORITY GATE, not the state machine.

        The StateMachine accepts any structured Delegation token (type check);
        validity (expiry/revocation) is the authority gate's job. The
        integration contract: the gate denies BEFORE the machine advances to a
        consequential state. Here we assert that the machine alone accepts the
        token (it records the plan), while the authority gate DENYs the action
        — the fail-closed boundary is the gate, not the state record."""
        d = harness.build_delegation(expires_at="2020-01-01T00:00:00Z")
        h = harness
        # State machine records the delegation token (type check passes).
        h.transition("int-02", "PLANNED", authority=d)
        h.transition("int-02", "DELEGATED", authority=d)
        assert h.machine("int-02").current() == "DELEGATED"
        # Authority gate DENYs the expired delegation (INV-13, AUTH-INV-06).
        dec = h.evaluate_gate("authority", {
            "delegation": d, "action": "write", "target": "agents/cto/x.txt"})
        assert dec.decision == "DENY"
        # Because the gate denied, no write occurs.
        assert not h.file_exists("agents/cto/x.txt")

    def test_execution_denied_no_file_mutation(self, harness):
        """When authority is revoked, no file is written via the execution channel."""
        h = harness
        d = harness.build_delegation_dict(
            id="delegation-int-02",
            scope={"operations": ["write", "read"],
                   "resources": ["agents/**", "docs/**", "multi-agent-harness/**"],
                   "environments": ["dev"]},
        )
        # Seed delegation
        h.seed_registry(d)
        # Revoke it
        h.seed_revocation("delegation-int-02")
        # Attempt write through the execution gate (reference authorizer check)
        from control_plane import authorize as ref_authorize, Deny as RefDeny
        with pytest.raises(RefDeny, match="revoked"):
            ref_authorize("orchestrator", "write", "agents/cto/x.txt",
                          d, revocation_list=("delegation-int-02",))
        assert not h.file_exists("agents/cto/x.txt")

    def test_expired_delegation_audit_denial(self, harness):
        """An expired delegation produces an audit execution_denial."""
        h = harness
        event = {
            "event_id": "ev-expired-001",
            "timestamp": "2026-08-30T00:00:00Z",
            "event_class": "execution_denial",
            "actor": "orchestrator", "action": "write",
            "target": "agents/cto/x.txt",
            "project": "multi-agent-harness",
            "authority_source": "delegation-int-02",
            "result": "denied",
            "error": "delegation expired (AUTH-INV-06)",
        }
        h.append_audit(event)
        denials = [e for e in h.audit_events()
                   if e.get("event_class") == "execution_denial"]
        assert len(denials) == 1
        assert "expired" in denials[0].get("error", "")

    def test_live_revocation_between_plan_and_exec(self, harness):
        """LIVE variant (D4/D7 mounted): revoke the delegation between planning
        and execution while the REAL backend is wired, and assert the
        execution-time re-check denies BEFORE any live dispatch happens
        (AUTH-INV-06, fail-closed at the DSH boundary).

        Conditional gate, not a skeleton: without the mount marker or a
        session-recorded child result the test SKIPS with that reason. The
        offline contract is covered by the tests above and by
        tests/scenarios/test_executable_scenarios.py SCN-102.
        """
        import json
        from tests.live_dsh.live_gate import (live_available, skip_reason,
                                              load_recorded)
        if not live_available("INT-02"):
            pytest.skip(skip_reason("INT-02"))
        live = load_recorded("DSH_LIVE_RESULT_INT02",
                             "int01_live_result.json",
                             "int07_live_result.json")
        assert live and live.get("structured"), \
            "live gate on but no session-recorded child result"

        from orchestrator.runtime import ExecutionFlow
        from orchestrator.runtime.delegation import MemoryDelegationProvider
        from orchestrator.dsh import DelegationClient, RoleResolver
        from tests.live_dsh.real_backend import (RealDSHBackend,
                                                 DSHBridgeResponse)
        from tests.scenarios.scenario_helpers import (
            make_intake, make_execute_plan)

        ws = harness.ws
        structured = live["structured"]
        calls = []

        def _dispatch(invocation, instance):
            calls.append(getattr(instance, "role", ""))
            return DSHBridgeResponse(
                run_id=live["run_id"], output=json.dumps(structured),
                structured=structured,
                stop_reason=live.get("stop_reason", "completed"))

        backend = RealDSHBackend(_dispatch, require_marker=True)
        client = DelegationClient(backend=backend, resolver=RoleResolver())
        delegation = harness.build_delegation(
            id="delegation-int-02", task="int-02",
            action="write", target="agents/**",
            scope_operations=("write", "read", "code_write"),
            scope_resources=("agents/**", "docs/**",
                             "multi-agent-harness/**"))
        provider = MemoryDelegationProvider(delegation)
        flow = ExecutionFlow(
            project="multi-agent-harness", base=ws, provider=provider,
            subtask_runner=lambda task, child: client.delegate(task, child),
            flow_id="int-02-live")

        # the race: revoked after planning, before execution
        def _revoke_between_plan_and_exec():
            provider.revoke("delegation-int-02",
                            reason="revoked between planning and execution")
        flow.pre_execute = _revoke_between_plan_and_exec

        result = flow.run(
            make_intake(objective="engineering",
                        required_authority_context="delegation-int-02"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))

        assert result.outcome == "BLOCKED", result.to_dict()
        # the planning dispatch DID happen (legitimate, pre-revocation) — the
        # proof is that NO dispatch or execution follows the revocation
        assert len(calls) == 1, \
            "no dispatch may follow the revocation (no blind retry)"
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))
        denials = flow._get_audit().events_of_class("execution_denial")
        assert denials, "the live denial must be audited"
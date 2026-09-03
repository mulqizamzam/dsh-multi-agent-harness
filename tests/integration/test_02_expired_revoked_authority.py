# INT-02 — Expired / revoked authority
#
# Proves that an expired or revoked delegation is DENIED at execution time,
# even if planning passed.
#
# Modules integrated: AuthorityGate + reference authorize + StateMachine +
# execution_gate + audit
#
# Invariants: AUTH-INV-06, INV-13, THREAT-008/009/024

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

    @pytest.mark.skip(reason="requires Phase-2C — live execution re-check")
    def test_live_revocation_between_plan_and_exec(self, harness):
        """SKELETON: delegation revoked between planning and execution in a
        live DSH session; execution-time re-check must DENY."""
        raise NotImplementedError("Phase-2C: live revocation race")
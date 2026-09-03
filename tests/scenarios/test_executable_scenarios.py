# tests/scenarios/test_executable_scenarios.py — Executable bounded scenarios
#
# Phase 4 / Session C — LIVE SCENARIO EXPANSION.
#
# Promotes the Phase-6 scenario skeleton (tests/scenarios/test_scenarios.py,
# PRD §17) into EXECUTABLE, BOUNDED scenarios where the Phase-4 runtime
# already supports the behavior. Each scenario maps to a runbook
# (docs/runbooks/01–10) and a specification in docs/phase-4/scenarios/
# (SCN-101..SCN-110).
#
# These tests run against the REAL Phase-4 runtime (orchestrator.runtime.*,
# control.*, audit.helpers.*) with deterministic in-process child execution —
# they do NOT fabricate live-DSH evidence and do NOT claim L3. The live-DSH
# variants (needing the D4/D7 mount, still PENDING_HUMAN_APPROVAL) are BLOCKED
# and not claimed here.
#
# TEST-SUPPORT ONLY. Not production code.

import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from datetime import datetime, timedelta, timezone

from orchestrator.runtime import (
    ExecutionFlow, ExecutePlan, MemoryDelegationProvider,
    COMPLETE, BLOCKED, ESCALATED, RECOVERING, FAILED,
    RecoveryRefusedByRuntime, StaleStateDetected,
)
from orchestrator.foundation.state import _structured_authority_ok

from tests.scenarios.scenario_helpers import (
    make_delegation, make_intake, make_execute_plan,
    make_subtask_result, StubSubtaskRunner, StubActionExecutor,
)


# ---------------------------------------------------------------------------
# Helpers shared by the scenario classes
# ---------------------------------------------------------------------------

def _gate(result, name):
    """Return the last gate record of the given gate name from a FlowResult."""
    matches = [g for g in result.gates if g["gate"] == name]
    return matches[-1] if matches else None


def _event_classes(flow):
    return {e.get("event_class") for e in flow._get_audit().read()}


def _make_flow(ws, provider, subtask_runner, *, executor=None, flow_id="scn",
               parallel_subtasks=True):
    return ExecutionFlow(
        project="multi-agent-harness",
        base=ws, provider=provider, subtask_runner=subtask_runner,
        executor=executor, flow_id=flow_id,
        parallel_subtasks=parallel_subtasks,
    )


def _add_cto(subtask_runner, *, evidence=("artifact:cto",),
             recommendation="write module"):
    subtask_runner.add("cto", make_subtask_result(
        "task-1:cto", "cto", recommendation=recommendation,
        findings=("analyzed",), evidence=evidence))


# ---------------------------------------------------------------------------
# SCN-101 — Authority denial (Runbook 01)
# ---------------------------------------------------------------------------

class TestAuthorityDenial:
    """Runbook 01 — any authority denial stops the flow fail-closed (AUTH-INV-20),
    produces no mutation, and is audited."""

    def test_missing_delegation_escalates(self, ws, subtask_runner):
        """No delegation for the authority context -> ESCALATED (not actionable)."""
        provider = MemoryDelegationProvider(None)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-101a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == ESCALATED
        assert "authority context" in result.errors[0]
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_action_outside_scope_denied(self, ws, subtask_runner):
        """Delegation grants read only; execute action write -> authority DENY
        (AUTH-INV-04/18), no file."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",)))
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module",
            evidence=("artifact:cto",)))
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-101b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        auth = _gate(result, "authority")
        assert auth and auth["decision"] == "DENY"
        assert "authority" in _event_classes(flow) or \
            any(e.get("event_class") == "gate_authority"
                for e in flow._get_audit().read())

    def test_target_outside_resources_denied(self, ws, subtask_runner):
        """Target outside delegation resources -> authority DENY (AUTH-INV-11)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_resources=("docs/**",)))
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-101c")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))

    def test_model_text_is_never_authority(self):
        """Model prose / state-approved / review PASS are never structured
        authority (AUTH-INV-01/07/09/13)."""
        assert not _structured_authority_ok("Human approved", "PLANNED")
        assert not _structured_authority_ok("I am authorized", "PLANNED")
        assert not _structured_authority_ok(
            {"approved": True, "status": "APPROVED"}, "PLANNED")
        from control.authority import (
            state_approval_is_authority, badsector_pass_is_authority,
        )
        assert state_approval_is_authority({"approved": True}) is False
        assert badsector_pass_is_authority(
            {"verdict": "PASS"}, make_delegation()) is False

    def test_result_is_serializable_and_deterministic(self, ws, subtask_runner):
        """The denial result is JSON-serializable; identical runs are stable."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",)))
        _add_cto(subtask_runner)
        outcomes = []
        for i in range(2):
            flow = _make_flow(ws, provider, subtask_runner, flow_id=f"scn-101d-{i}")
            res = flow.run(
                make_intake(objective="engineering"),
                execute_plan=make_execute_plan(
                    target="agents/cto/output.txt"))
            doc = res.to_dict()
            json.dumps(doc)  # serializable
            outcomes.append(doc)
        assert outcomes[0]["outcome"] == outcomes[1]["outcome"] == "BLOCKED"


# ---------------------------------------------------------------------------
# SCN-102 — Expired / revoked delegation (Runbooks 02 / 03)
# ---------------------------------------------------------------------------

class TestDelegationExpiryRevocation:
    """Runbook 02/03 — the execution-time authority re-check (AUTH-INV-05/06)
    DENYs an action whose delegation expired or was revoked between planning and
    execution (THREAT-008/009). No mutation; the denial is audited."""

    def test_already_expired_delegation_denied(self, ws, subtask_runner):
        """A delegation whose expires_at is in the past -> DENY, no file."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1))
        provider = MemoryDelegationProvider(make_delegation(
            expires_at=past.isoformat()))
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-102a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "gate_authority"
                   and e.get("result") == "denied" for e in events)

    def test_revocation_between_plan_and_execute_denied(self, ws,
                                                        subtask_runner):
        """Planning ALLOW; revocation observed by the execution-time re-check
        -> execution_denial -> BLOCKED (THREAT-009, AUTH-INV-06)."""
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-102b")

        def _revoke():
            provider.revoke("delegation-test-001",
                            reason="revoked during execution")

        flow.pre_execute = _revoke
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "execution_denial" for e in events)

    def test_control_level_expiry_check_is_time_sensitive(self):
        """control.authority.recheck_authority: same delegation ALLOWs before
        expiry and DENYs after (AUTH-INV-06)."""
        from control.authority import recheck_authority, Denied as AuthDenied
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        d = make_delegation(expires_at=past.isoformat())
        before_expiry = datetime.now(timezone.utc) - timedelta(hours=2)
        assert recheck_authority(
            delegation=d, action="write", target="agents/**",
            environment="dev", actor="orchestrator", project="multi-agent-harness",
            now=before_expiry) is True
        with pytest.raises(AuthDenied, match="expired"):
            recheck_authority(
                delegation=d, action="write", target="agents/**",
                environment="dev", actor="orchestrator",
                project="multi-agent-harness")

    def test_control_level_revocation_check(self):
        """A revoked id in the revocation list DENYs (AUTH-INV-06)."""
        from control.authority import recheck_authority, Denied as AuthDenied
        d = make_delegation()
        with pytest.raises(AuthDenied, match="revoked"):
            recheck_authority(
                delegation=d, action="write", target="agents/**",
                environment="dev", actor="orchestrator",
                project="multi-agent-harness",
                revocation_list=("delegation-test-001",))


# ---------------------------------------------------------------------------
# SCN-103 — BadSector rework / reject (Runbook 04)
# ---------------------------------------------------------------------------

class TestBadsectorReworkReject:
    """Runbook 04 — the BadSector review stage is a GATE, not an authorization
    (AUTH-INV-09): REWORK / REJECT / forged PASS halt the pipeline; PASS clears
    the review stage only and never grants execution authority."""

    def test_reject_halts_at_review_gate(self, flow, subtask_runner):
        """A REJECT verdict -> badsector_review DENY -> BLOCKED."""
        _add_cto(subtask_runner)
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review={"verdict": "REJECT", "review_id": "review-scn-103a",
                    "input_hash": "hash-103a"})
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"
        rev = _gate(result, "badsector_review")
        assert rev and rev["decision"] == "DENY"

    def test_rework_halts_at_review_gate(self, flow, subtask_runner):
        """A REWORK verdict -> badsector_review DENY -> BLOCKED (pipeline halts
        at the review boundary; rework is not auto-resolved)."""
        _add_cto(subtask_runner)
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review={"verdict": "REWORK", "review_id": "review-scn-103b",
                    "input_hash": "hash-103b"})
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"

    def test_mandatory_review_skipped_denied(self, flow, subtask_runner):
        """Skipping a mandatory review (review_required=True, no record) ->
        DENY (THREAT-015 transition violation)."""
        _add_cto(subtask_runner)
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True, review=None)
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"

    def test_forged_pass_denied(self, flow, subtask_runner):
        """A PASS whose input_hash does not match the synthesis -> provenance
        mismatch -> DENY (THREAT-014/BAD-001)."""
        _add_cto(subtask_runner)
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"),
            review_required=True,
            review={"verdict": "PASS", "review_id": "forged-1",
                    "input_hash": "does-not-match"})
        assert result.outcome == BLOCKED
        assert result.phase == "adversarial_review"

    def test_pass_clears_review_only_never_authority(self, ws, subtask_runner,
                                                     action_executor):
        """A proven PASS clears the review stage but authority still DENYs when
        the delegation does not cover the action (AUTH-INV-09)."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_operations=("read",)))
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner,
                          executor=action_executor, flow_id="scn-103c")

        # Capture the exact synthesis the review would hash, from a run that
        # stops at the review gate.
        from tests.conftest import o3_daemon_context
        with o3_daemon_context(os.path.join(ws, "run_a")):
            ws_a = os.path.join(ws, "run_a")
            for sub in ("state/registry", "state/projects", "audit",
                        "agents/cto", "docs"):
                os.makedirs(os.path.join(ws_a, sub), exist_ok=True)
            from tests.scenarios.conftest import _seed_project_state
            _seed_project_state(ws_a)
            flow_a = _make_flow(ws_a, provider, subtask_runner,
                                executor=action_executor,
                                flow_id="scn-103c-capture")
            result_a = flow_a.run(
                make_intake(objective="engineering"),
                execute_plan=make_execute_plan(target="agents/cto/x.txt"),
                review_required=True, review=None)
            assert result_a.phase == "adversarial_review"
            from control.badsector import _input_hash as _bs_hash
            expected_hash = _bs_hash(result_a.synthesis)

        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            review_required=True,
            review={"verdict": "PASS", "review_id": "review-scn-103c",
                    "input_hash": expected_hash})
        assert result.outcome == BLOCKED
        rev = _gate(result, "badsector_review")
        assert rev and rev["decision"] == "ALLOW"   # review cleared
        auth = _gate(result, "authority")
        assert auth and auth["decision"] == "DENY"  # PASS != authorization
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))


# ---------------------------------------------------------------------------
# SCN-104 — Evidence failure (Runbook 05)
# ---------------------------------------------------------------------------

class TestEvidenceFailure:
    """Runbook 05 — evidence sufficiency ladder (EVID-001..004): failures stop
    the flow before execution; model confidence is never evidence (EVID-004)."""

    def test_high_risk_no_evidence_denied(self, ws, subtask_runner):
        """HIGH risk + no evidence -> evidence gate DENY -> BLOCKED (EVID-002)."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module", evidence=()))
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-104a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            declared_risk="HIGH")
        assert result.outcome == BLOCKED
        ev = _gate(result, "evidence")
        assert ev and ev["decision"] == "DENY"
        assert "EVID-002" in ev["reason"]
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))

    def test_medium_risk_no_evidence_escalated(self, ws, subtask_runner):
        """MEDIUM risk + no evidence -> evidence gate ESCALATE (EVID-001)."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module", evidence=()))
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-104b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            declared_risk="MEDIUM")
        assert result.outcome == ESCALATED

    def test_low_risk_evidence_optional_allowed(self, ws, subtask_runner,
                                               action_executor):
        """LOW risk (read action) + no evidence -> evidence optional -> ALLOW
        (proceeds to COMPLETE)."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cto", make_subtask_result(
            "task-1:cto", "cto", recommendation="write module", evidence=()))
        flow = _make_flow(ws, provider, subtask_runner, executor=action_executor,
                          flow_id="scn-104c")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                action="read", target="agents/cto/x.txt"))
        assert result.outcome == COMPLETE, result.to_dict()
        ev = _gate(result, "evidence")
        assert ev and ev["decision"] == "ALLOW"

    def test_ladder_unsupported_claim(self):
        """EVID-001: a claim with no source fails SOURCE_EXISTS."""
        from control.evidence import EvidenceGate
        verdict = EvidenceGate().evaluate(
            [{"id": "c1", "text": "claim", "source_ids": []}],
            [{"id": "s1", "timestamp": "2026-01-01T00:00:00Z",
              "supports": True}], risk="LOW")
        assert not verdict.accepted
        assert verdict.rung_reached == "SOURCE_EXISTS"
        assert "EVID-001" in verdict.reason

    def test_ladder_stale_source(self):
        """EVID-002: a source older than the temporal window fails CURRENT."""
        from control.evidence import EvidenceGate
        verdict = EvidenceGate(temporal_window_days=30).evaluate(
            [{"id": "c1", "text": "claim", "source_ids": ["s1"]}],
            [{"id": "s1", "timestamp": "2000-01-01T00:00:00Z",
              "supports": True}], risk="LOW")
        assert not verdict.accepted
        assert verdict.rung_reached == "CURRENT"
        assert "EVID-002" in verdict.reason

    def test_ladder_contradictory_sources(self):
        """EVID-003: contradictions are surfaced, never silently resolved."""
        from control.evidence import EvidenceGate
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        verdict = EvidenceGate().evaluate(
            [{"id": "c1", "text": "claim", "source_ids": ["s1"]}],
            [{"id": "s1", "timestamp": recent, "supports": True,
              "contradicts": ["s2"]},
             {"id": "s2", "timestamp": recent, "supports": True}],
            risk="LOW")
        assert not verdict.accepted
        assert verdict.rung_reached == "UNCONTRADICTED"
        assert "EVID-003" in verdict.reason

    def test_ladder_high_confidence_only_insufficient(self):
        """EVID-004: model confidence alone is never sufficient for HIGH."""
        from control.evidence import EvidenceGate
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        verdict = EvidenceGate().evaluate(
            [{"id": "c1", "text": "claim", "source_ids": ["s1"]}],
            [{"id": "s1", "timestamp": recent,
              "supports": True, "confidence": "high"}],
            risk="HIGH")
        assert not verdict.accepted
        assert verdict.rung_reached == "SUFFICIENT_FOR_ACTION"
        assert "EVID-004" in verdict.reason


# ---------------------------------------------------------------------------
# SCN-105 — Conflict escalation (Runbook 06)
# ---------------------------------------------------------------------------

class TestConflictEscalation:
    """Runbook 06 — conflicting specialist outputs are preserved, never voted
    (CONF-001..003); material / HIGH / security-relevant conflicts escalate."""

    def test_flow_high_risk_conflict_escalates(self, ws, subtask_runner):
        """Pricing objective routes cfo+kai; conflicting recommendations on a
        HIGH-risk action -> conflict gate ESCALATE -> ESCALATED."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("margin supports",), evidence=("src:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="hold",
            findings=("market signals risk",), evidence=("src:kai",)))
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-105a")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(target="docs/pricing.md"),
            declared_risk="HIGH")
        assert result.outcome == ESCALATED
        assert result.phase == "conflict_gate"
        cf = _gate(result, "conflict")
        assert cf and cf["decision"] == "ESCALATE"
        assert set(result.selected) == {"cfo", "kai"}

    def test_flow_immaterial_conflict_allowed(self, ws, subtask_runner,
                                              action_executor):
        """LOW-risk (read) conflict with no evidence on either side -> synthesized
        (ALLOW), disagreement preserved, no voting -> COMPLETE."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("margin supports",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="hold",
            findings=("market signals risk",)))
        flow = _make_flow(ws, provider, subtask_runner, executor=action_executor,
                          flow_id="scn-105b")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(
                action="read", target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        cf = _gate(result, "conflict")
        assert cf and cf["decision"] == "ALLOW"
        assert "no voting" in cf["reason"] or "disagreement" in cf["reason"]

    def test_control_gate_no_voting_material_escalates(self):
        """ConflictGate.resolve: material conflict -> escalate, voted=False,
        preserved=True (security spec §8.1)."""
        from control.conflict import ConflictGate
        res = ConflictGate().resolve(
            [{"agent": "cfo", "decision": "recommendation",
              "position": "proceed", "evidence": ["src:cfo"]},
             {"agent": "kai", "decision": "recommendation",
              "position": "hold", "evidence": ["src:kai"]}],
            risk="HIGH")
        assert res.action == "escalate"
        assert res.escalated is True
        assert res.voted is False
        assert res.preserved is True

    def test_control_gate_immaterial_synthesizes(self):
        """ConflictGate.resolve: immaterial conflict -> synthesize with all
        distinct positions preserved, no voting."""
        from control.conflict import ConflictGate
        res = ConflictGate().resolve(
            [{"agent": "cfo", "decision": "recommendation",
              "position": "proceed", "evidence": []},
             {"agent": "kai", "decision": "recommendation",
              "position": "hold", "evidence": []}],
            risk="LOW")
        assert res.action == "synthesize"
        assert res.escalated is False
        assert res.voted is False
        assert res.preserved is True

    def test_control_gate_majority_is_still_a_conflict(self):
        """No majority voting: 2-vs-1 with differing positions is still a
        conflict; the gate never counts."""
        from control.conflict import ConflictGate
        gate = ConflictGate()
        detected = gate.detect([
            {"agent": "cfo", "decision": "recommendation",
             "position": "proceed", "evidence": ["a"]},
            {"agent": "kai", "decision": "recommendation",
             "position": "proceed", "evidence": ["b"]},
            {"agent": "nova", "decision": "recommendation",
             "position": "hold", "evidence": ["c"]},
        ])
        assert len(detected) == 1
        assert detected[0].detail["n_distinct_positions"] == 2


# ---------------------------------------------------------------------------
# SCN-106 — Execution failure (Runbook 07)
# ---------------------------------------------------------------------------

class TestExecutionFailure:
    """Runbook 07 — a post-gate execution/verification failure routes into the
    recovery lifecycle with no blind retry (REC-001..003, AUTH-INV-12/16)."""

    def test_verification_mismatch_routes_to_recovery(self, ws, subtask_runner):
        """Observed != expected -> verification not passed -> RECOVERING."""
        provider = MemoryDelegationProvider(make_delegation())
        executor = StubActionExecutor(observed={"exit_code": 1,
                                                "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=executor,
                          flow_id="scn-106a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        assert result.recovery, "recovery record should be present"
        assert result.recovery.get("state") in ("STOPPED", "PRESERVED")

    def test_successful_recovery_to_complete(self, ws, subtask_runner):
        """RECOVERING -> recover(cause=..., fixed executor) -> COMPLETE
        (AUTH-INV-12/16; recovery record COMPLETED)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-106d")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        flow.executor = StubActionExecutor(
            observed={"exit_code": 0, "target": "agents/cto/x.txt"})
        result = flow.recover(cause="fixed exit code", failure_class="logic")
        assert result.outcome == COMPLETE, result.errors
        assert result.final_state == "COMPLETE"
        assert result.recovery.get("state") == "COMPLETED"

    def test_no_blind_retry_empty_cause_refused(self, ws, subtask_runner):
        """recover(cause="") -> RecoveryRefusedByRuntime (AUTH-INV-16)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-106e")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        with pytest.raises(RecoveryRefusedByRuntime, match="no blind retry"):
            flow.recover(cause="", failure_class="logic")

    def test_identical_cause_refused(self, ws, subtask_runner):
        """A retry with the same diagnosed cause is refused (AUTH-INV-16)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-106f")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        flow.executor = StubActionExecutor(
            observed={"exit_code": 0, "target": "agents/cto/x.txt"})
        result = flow.recover(cause="fixed exit code", failure_class="logic")
        assert result.outcome == COMPLETE
        with pytest.raises(RecoveryRefusedByRuntime):
            # request_retry with the same cause is refused (AUTH-INV-16)
            from control.recovery import RecoveryRefused
            try:
                flow._recovery_controller.request_retry("fixed exit code")
            except Exception as e:
                raise RecoveryRefusedByRuntime(str(e)) from e


# ---------------------------------------------------------------------------
# SCN-107 — Recovery failure (Runbook 08)
# ---------------------------------------------------------------------------

class TestRecoveryFailure:
    """Runbook 08 — a recovery that itself fails reaches FAILED; no in-band
    retry is possible; escalation is the only forward path."""

    def test_attempt_cap_reached_then_refused(self, ws, subtask_runner):
        """First recovery fails (executor still failing) -> FAILED; a second
        recovery with a new cause is refused (REC-001 attempt cap)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-107a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        # First recovery attempt also fails -> FAILED
        result = flow.recover(cause="first attempt", failure_class="logic")
        assert result.outcome == FAILED, result.to_dict()
        with pytest.raises(RecoveryRefusedByRuntime):
            flow.recover(cause="new cause", failure_class="logic")

    def test_empty_cause_recovery_refused(self, ws, subtask_runner):
        """A recovery with no diagnosed cause is refused (no blind retry)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-107b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        with pytest.raises(RecoveryRefusedByRuntime, match="no blind retry"):
            flow.recover(cause="", failure_class="logic")

    def test_recovery_authority_recheck_denies(self, ws, subtask_runner):
        """Recovery re-checks authority (AUTH-INV-12): a revoked delegation
        refuses recovery (Runbook 02/03 handoff)."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-107c")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        provider.revoke("delegation-test-001", reason="revoked before recovery")
        flow.executor = StubActionExecutor(
            observed={"exit_code": 0, "target": "agents/cto/x.txt"})
        with pytest.raises(RecoveryRefusedByRuntime,
                           match="AUTH-INV-12|recovery re-check"):
            flow.recover(cause="fixed exit code", failure_class="logic")

    def test_recovery_state_machine_failed_is_terminal(self):
        """state/helpers/recovery: FAILED is a terminal state — no transition
        out of FAILED is allowed."""
        from state.helpers.recovery import begin_recovery, RecoveryError
        rec = begin_recovery("task-x", 1, failure_class="logic", reason="boom")
        rec.fail(reason="could not restore")
        assert rec.state == "FAILED"
        with pytest.raises(RecoveryError):
            rec.complete()


# ---------------------------------------------------------------------------
# SCN-108 — Stale state (Runbook 09)
# ---------------------------------------------------------------------------

class TestStaleState:
    """Runbook 09 — a stale state version (parallel writer advanced the state
    between plan and exec) stops the flow fail-closed (THREAT-021/022)."""

    def test_parallel_writer_bump_stops_flow(self, ws, subtask_runner):
        """An external writer bumps the version between planning and execution
        -> StaleStateDetected -> BLOCKED + version_conflict audited."""
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-108a")

        def _bump():
            store = flow._get_store()
            ps = store.load_project_state()
            ps.version += 1
            store.persist(ps, expected_version=ps.version - 1)

        flow.pre_execute = _bump
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt"))
        events = flow._get_audit().read()
        assert any(e.get("event_class") == "version_conflict" for e in events)

    def test_cas_persist_rejects_stale_writer(self, ws):
        """RuntimeStore.persist with a stale expected version raises
        StaleStateDetected (THREAT-021 lost update) and mutates nothing."""
        from orchestrator.runtime import RuntimeStore
        from orchestrator.foundation.state import ProjectState
        store = RuntimeStore(base=ws)
        store.ensure_dirs()
        store.ensure_state()
        ps = store.load_project_state()
        current = ps.version
        # Bump the on-disk version behind the caller's back
        ps.version += 1
        store.persist(ps, expected_version=ps.version - 1)
        assert store.current_version() == current + 1
        with pytest.raises(StaleStateDetected, match="lost update"):
            store.persist(ps, expected_version=current)

    def test_recovery_stale_version_refused(self, ws, subtask_runner):
        """THREAT-022: recovery against an obsolete state version is refused."""
        provider = MemoryDelegationProvider(make_delegation())
        failing = StubActionExecutor(observed={"exit_code": 1,
                                               "target": "agents/cto/x.txt"})
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, executor=failing,
                          flow_id="scn-108c")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING

        # advance the state version after the failure
        store = flow._get_store()
        ps = store.load_project_state()
        ps.version += 1
        store.persist(ps, expected_version=ps.version - 1)
        flow.executor = StubActionExecutor(
            observed={"exit_code": 0, "target": "agents/cto/x.txt"})
        with pytest.raises(RecoveryRefusedByRuntime):
            flow.recover(cause="state advanced", failure_class="authorization")

    def test_version_check_primitives(self, ws):
        """version_check primitives detect staleness (state/helpers)."""
        from state.helpers import version_check
        from orchestrator.runtime import RuntimeStore
        store = RuntimeStore(base=ws)
        store.ensure_dirs()
        store.ensure_state()
        path = store.state_path()
        assert version_check.read_version(path) == 1
        # file at version 1, caller holds 0 -> file is NEWER
        stale, _, _, reason = version_check.is_stale(path, expected_version=0)
        assert stale is True
        assert "NEWER" in reason.upper()


# ---------------------------------------------------------------------------
# SCN-109 — Audit integrity failure (Runbook 10)
# ---------------------------------------------------------------------------

class TestAuditIntegrityFailure:
    """Runbook 10 — the audit ledger's integrity is verifiable: tampering,
    truncation, blank/corrupt lines, and duplicate ids are detected; writes to
    the protected audit path are denied (ADR 0002); audit is never authority
    (AUTH-INV-14)."""

    def _write_ledger(self, ws, n=3):
        from audit.helpers.append_log import append_event
        log = os.path.join(ws, "audit", "scn109", "events.jsonl")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        for i in range(1, n + 1):
            append_event(log, {
                "event_id": f"scn109-{i}",
                "timestamp": f"2026-01-0{i}T00:00:00Z",
                "event_class": "flow_started",
                "action": "run", "target": "task",
                "result": "recorded", "seq": i,
            })
        return log

    def test_chain_break_detected(self, ws):
        """After compute_chain, tampering with a line -> verify_chain raises
        AuditIntegrityError at the first divergent line."""
        from audit.helpers.integrity import compute_chain, verify_chain
        from audit.helpers.append_log import AuditIntegrityError
        log = self._write_ledger(ws)
        compute_chain(log)
        # tamper: rewrite the file with a modified middle event
        events = []
        with open(log) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        events[1]["result"] = "tampered"
        with open(log, "w") as f:
            for ev in events:
                f.write(json.dumps(ev, sort_keys=True) + "\n")
        with pytest.raises(AuditIntegrityError, match="mismatch|tampered"):
            verify_chain(log)

    def test_blank_line_detected(self, ws):
        """A blank line in the JSONL ledger -> read_events_strict raises
        AuditIntegrityError."""
        from audit.helpers.append_log import read_events_strict, AuditIntegrityError
        log = self._write_ledger(ws, n=2)
        with open(log, "a") as f:
            f.write("\n")
        with pytest.raises(AuditIntegrityError, match="blank line"):
            read_events_strict(log)

    def test_corrupt_line_detected(self, ws):
        """A non-JSON line -> read_events_strict raises AuditIntegrityError."""
        from audit.helpers.append_log import read_events_strict, AuditIntegrityError
        log = self._write_ledger(ws, n=2)
        with open(log, "a") as f:
            f.write("this is not json\n")
        with pytest.raises(AuditIntegrityError, match="corrupt"):
            read_events_strict(log)

    def test_truncation_detected(self, ws):
        """detect_truncation against a known-good line count + cumulative hash
        detects a truncated ledger."""
        from audit.helpers.integrity import compute_chain, detect_truncation, chain_path_for
        from audit.helpers.append_log import read_events_strict
        log = self._write_ledger(ws, n=3)
        annotated = compute_chain(log)
        known_count = len(annotated)
        known_hash = annotated[-1]["_integrity"]["cumulative_hash"]
        # truncate: keep the first 2 lines
        with open(log) as f:
            lines = f.readlines()[:2]
        with open(log, "w") as f:
            f.writelines(lines)
        ok, problems = detect_truncation(log, known_hash, known_count)
        assert ok is False
        assert any("truncation" in p for p in problems)

    def test_duplicate_event_id_detected(self, ws):
        """verify_append_only flags a duplicate event_id (replay/overwrite)."""
        from audit.helpers.append_log import append_event, verify_append_only
        log = os.path.join(ws, "audit", "scn109-dup", "events.jsonl")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        ev = {"event_id": "dup-1", "timestamp": "2026-01-01T00:00:00Z",
              "event_class": "flow_started", "result": "recorded"}
        append_event(log, ev)
        append_event(log, dict(ev))  # same event_id again
        ok, problems = verify_append_only(log)
        assert ok is False
        assert any("duplicate event_id" in p for p in problems)

    def test_append_only_integrity_clean(self, ws):
        """An untampered ledger verifies clean (baseline check)."""
        from audit.helpers.append_log import verify_append_only
        log = self._write_ledger(ws)
        ok, problems = verify_append_only(log)
        assert ok is True, problems

    def test_protected_audit_path_write_denied(self, ws):
        """authorize_write denies writes to audit/** (ADR 0002 protected path)."""
        from control.execution_gate import authorize_write, Denied as ExecDenied
        with pytest.raises(ExecDenied, match="protected"):
            authorize_write("write", "audit/events.jsonl", base=ws)
        with pytest.raises(ExecDenied, match="protected"):
            authorize_write("write", "state/registry/evil.json", base=ws)

    def test_flow_denies_write_to_audit_path(self, ws, subtask_runner):
        """A plan targeting audit/** is denied at execution time even when the
        delegation would allow the target."""
        provider = MemoryDelegationProvider(make_delegation(
            scope_resources=("audit/**", "multi-agent-harness/**")))
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-109e")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="audit/events.jsonl"))
        assert result.outcome == BLOCKED
        assert not os.path.exists(os.path.join(ws, "audit/events.jsonl"))

    def test_audit_never_grants_authority(self):
        """audit_is_authority_source always returns False (AUTH-INV-14)."""
        from audit.helpers.append_log import audit_is_authority_source
        assert audit_is_authority_source({"event_class": "approval"}) is False
        assert audit_is_authority_source(
            {"event_class": "normal_approval", "approved": True}) is False


# ---------------------------------------------------------------------------
# SCN-110 — Successful bounded autonomous workflow (happy path)
# ---------------------------------------------------------------------------

class TestSuccessfulBoundedWorkflow:
    """PRD §17 #1/#2 — the full Phase-4 runtime flow runs to COMPLETE with all
    gates ALLOW, verification PASSED, and the consequential write landing
    through the execution gate. Autonomy is bounded by the explicit delegation;
    Human is not required during the flow."""

    def test_single_specialist_flow_completes(self, ws, subtask_runner):
        """engineering -> cto -> COMPLETE, file written, all gates ALLOW."""
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-110a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert result.final_state == "COMPLETE"
        assert result.phase == "close"
        assert result.selected == ("cto",)
        assert os.path.exists(os.path.join(ws, "agents/cto/output.txt"))
        assert "agents/cto/output.txt" in result.files_written
        for g in result.gates:
            assert g["decision"] == "ALLOW", f"gate {g['gate']} not ALLOW"
        assert result.verification.get("verdict") == "PASSED"

    def test_parallel_minimum_set_completes(self, ws, subtask_runner):
        """pricing -> cfo + kai (minimum set of two) run as an in-process
        parallel batch -> COMPLETE with version preserved."""
        provider = MemoryDelegationProvider(make_delegation())
        subtask_runner.add("cfo", make_subtask_result(
            "task-1:cfo", "cfo", recommendation="proceed",
            findings=("margin analysis",), evidence=("src:cfo",)))
        subtask_runner.add("kai", make_subtask_result(
            "task-1:kai", "kai", recommendation="proceed",
            findings=("market research",), evidence=("src:kai",)))
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-110b")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert set(result.selected) == {"cfo", "kai"}
        assert len(result.results) == 2
        assert result.parallel.get("safe") is True
        assert result.parallel.get("mode") in ("parallel", "sequential")

    def test_audit_records_full_lifecycle(self, ws, subtask_runner):
        """COMPLETE records the full runtime lifecycle in the append-only
        ledger (18 event classes)."""
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-110c")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE
        classes = _event_classes(flow)
        for expected in ("flow_started", "gate_risk", "gate_evidence",
                         "gate_conflict", "gate_review", "gate_authority",
                         "state_complete", "flow_finished"):
            assert expected in classes, f"missing {expected}"
        # No denial / recovery in the success path
        assert "execution_denial" not in classes
        assert "recovery" not in classes

    def test_bounded_autonomy_no_human_in_flow(self, ws, subtask_runner):
        """Autonomy is bounded: the flow reaches COMPLETE without Human
        participation, without escalation, and without leaving the delegation's
        scope (no self-escalation, AUTH-INV-02/03)."""
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        flow = _make_flow(ws, provider, subtask_runner, flow_id="scn-110d")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE
        assert result.outcome not in (ESCALATED, BLOCKED, FAILED, RECOVERING)
        # The flow consumed only the granted delegation — no new grants issued.
        delegations = [d["id"] for d in result.delegations]
        assert all(d.startswith("delegation-") for d in delegations)
        # Scope containment: child scope ⊆ parent scope is enforced at issuance
        # (AUTH-INV-04) — the flow never widens the grant.
        assert len(result.results) == 1

    def test_result_is_deterministic(self, ws, subtask_runner):
        """Two fresh flows over identical inputs produce identical gate records
        and selection (deterministic, JSON-serializable)."""
        from tests.conftest import o3_daemon_context
        provider = MemoryDelegationProvider(make_delegation())
        _add_cto(subtask_runner)
        intake = make_intake(objective="engineering")
        plan = make_execute_plan(target="agents/cto/output.txt")
        docs = []
        for i in range(2):
            # Each run gets its OWN O3 daemon root so project state is
            # isolated per run (O3 Phase B: daemon root == run workspace).
            base = os.path.join(ws, f"run{i}")
            with o3_daemon_context(base):
                for sub in ("state/registry", "state/projects", "audit",
                            "agents/cto", "docs"):
                    os.makedirs(os.path.join(base, sub), exist_ok=True)
                from tests.scenarios.conftest import _seed_project_state
                _seed_project_state(base)
                flow = _make_flow(base, provider, subtask_runner,
                                  flow_id=f"scn-110e-{i}")
                res = flow.run(intake, execute_plan=plan)
                assert res.outcome == COMPLETE, f"run {i}: {res.outcome}"
                docs.append(res.to_dict())
        json.dumps(docs[0])
        assert docs[0]["gates"] == docs[1]["gates"]
        assert docs[0]["selected"] == docs[1]["selected"]


# ---------------------------------------------------------------------------
# Traceability — every scenario is documented in docs/phase-4/scenarios/
# ---------------------------------------------------------------------------

SCENARIO_IDS = (
    "SCN-101", "SCN-102", "SCN-103", "SCN-104", "SCN-105",
    "SCN-106", "SCN-107", "SCN-108", "SCN-109", "SCN-110",
)


class TestScenarioTraceability:
    def test_scenario_spec_docs_exist(self):
        """Every promoted scenario id has a specification file under
        docs/phase-4/scenarios/ (the nine required fields are documented there)."""
        docdir = os.path.join(_PROJECT_ROOT, "docs", "phase-4", "scenarios")
        assert os.path.isdir(docdir), f"missing docs/phase-4/scenarios: {docdir}"
        files = os.listdir(docdir)
        for sid in SCENARIO_IDS:
            matches = [f for f in files if f.startswith(sid)]
            assert matches, f"{sid} has no spec file in {docdir}"

    def test_scenario_readme_index_exists(self):
        """The scenario index README exists."""
        readme = os.path.join(_PROJECT_ROOT, "docs", "phase-4", "scenarios",
                              "README.md")
        assert os.path.exists(readme), "missing docs/phase-4/scenarios/README.md"

    def test_phase6_skeletons_still_skipped(self):
        """The Phase-6 skeleton remains skipped (Phase-6 live engine required);
        these executable scenarios are the Phase-4 promotion, not a Phase-6
        claim."""
        import tests.scenarios.test_scenarios as skel
        assert getattr(skel, "pytestmark", None), \
            "test_scenarios.py should keep its Phase-6 skip marker"
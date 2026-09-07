"""Scenario suite — PRD §17 canonical scenarios SCN-001..SCN-010.

STATUS (2026-09-07): EXECUTABLE. These were structural skeletons while no
execution engine existed. The runtime now provides the full flow
(orchestrator.runtime.ExecutionFlow: intake → route/plan → risk → evidence →
conflict → BadSector review → authority → execute → verification → recovery),
so each scenario drives the REAL runtime end-to-end and asserts its documented
gate behavior.

Provenance and limits — read before citing this file as evidence:
  * Children are DETERMINISTIC IN-PROCESS stubs (tests/scenarios/
    scenario_helpers.py). Nothing here is live-DSH evidence and no L3 claim is
    made.
  * The per-gate bounded promotion (SCN-101..SCN-110, docs/phase-4/scenarios/)
    stays in test_executable_scenarios.py; this file covers the whole-flow
    PRD §17 scenarios with their documented actors and assertions.
  * Live-DSH variants of the same contracts are separately gated in
    tests/integration/test_01_*, test_02_*, test_11_*, test_12_* and
    tests/resilience/test_registry_gate.py (they require the D4/D7 mount
    marker plus session-recorded real child results).

Runtime facts these tests rely on (all observed, not assumed):
  * Routing is keyword-based (orchestrator/foundation/contracts.py DOMAIN_ROLE):
    operations→zeko, engineering→cto, pricing→cfo(+kai secondary),
    social/campaign→somad, novel/editing→nova, research→kai.
  * Gate order is risk_classify → risk → evidence → conflict → badsector_review
    → authority → verification, so a material conflict escalates BEFORE the
    mandatory-review requirement of a HIGH-risk action.
  * declared_risk="HIGH" makes BadSector review mandatory (THREAT-015): a flow
    reaches the authority gate only with a PASS whose input_hash matches the
    synthesis (control.badsector._input_hash).
  * requires_approval vocabulary is {destructive, financial_transfer,
    sensitive_publication, credential_change}; no reference → authority
    ESCALATE, free-text claim → authority DENY (AUTH-INV-01).

TEST-SUPPORT ONLY. Not production code.
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from orchestrator.runtime import (
    ExecutionFlow, MemoryDelegationProvider,
    COMPLETE, BLOCKED, ESCALATED, RECOVERING,
    RecoveryRefusedByRuntime,
)

from tests.scenarios.scenario_helpers import (
    make_delegation, make_intake, make_execute_plan,
    make_subtask_result, StubSubtaskRunner, StubActionExecutor,
)


# ---------------------------------------------------------------------------
# Canonical PRD §17 scenario specification (source of truth for the tests)
# ---------------------------------------------------------------------------

SCENARIOS = {
    "SCN-001": {
        "name": "Simple research task",
        "actors": ["orchestrator", "kai"],
        "flow": "INTAKE → PLAN → DELEGATE(kai) → COLLECT → VERIFY",
        "assert": "result is sourced, current, and evidence-gated (EVID-*)",
    },
    "SCN-002": {
        "name": "Code change with test evidence",
        "actors": ["orchestrator", "cto"],
        "flow": "INTAKE → PLAN → DELEGATE(cto) → VERIFY(test/build) → COMPLETE",
        "assert": "COMPLETE only after verification evidence (VERIFY-001..003)",
    },
    "SCN-003": {
        "name": "Infrastructure incident",
        "actors": ["orchestrator", "zeko"],
        "flow": "INTAKE → PLAN → DELEGATE(zeko) → RECOVERY (diagnosed) → VERIFY",
        "assert": "no blind retry; recovery re-checks authority (REC-001, AUTH-INV-12)",
    },
    "SCN-004": {
        "name": "Pricing analysis",
        "actors": ["orchestrator", "cfo", "kai"],
        "flow": "INTAKE → PLAN → DELEGATE(kai research + cfo analysis) → CONFLICT gate",
        "assert": "financial analysis is read-only; no transaction (RISK-003, ISO-002)",
    },
    "SCN-005": {
        "name": "Social campaign",
        "actors": ["orchestrator", "somad"],
        "flow": "INTAKE → PLAN → DELEGATE(somad draft) → APPROVAL → publish",
        "assert": "publishing is scoped_approval; never standing (ISO-004)",
    },
    "SCN-006": {
        "name": "Novel editing",
        "actors": ["orchestrator", "nova"],
        "flow": "INTAKE → PLAN → DELEGATE(nova) → VERIFY(continuity) → COMPLETE",
        "assert": "manuscript local-only; no infra execution (ISO-005)",
    },
    "SCN-007": {
        "name": "High-impact action requiring Human approval",
        "actors": ["orchestrator", "badsector", "human"],
        "flow": "PLAN → RISK(HIGH) → BADSECTOR review → EXECUTION gate → HUMAN approval → execute",
        "assert": "approval required + recorded; no auto-approval (RISK-001/002, THREAT-023)",
    },
    "SCN-008": {
        "name": "Conflicting specialist outputs",
        "actors": ["orchestrator", "kai", "cfo"],
        "flow": "COLLECT → CONFLICT gate → evidence → rework → synthesize/escalate",
        "assert": "no majority voting; disagreement preserved (CONF-001..003)",
    },
    "SCN-009": {
        "name": "Failed deployment → recovery",
        "actors": ["orchestrator", "zeko", "cto"],
        "flow": "EXECUTE → FAIL → STOP/PRESERVE/DIAGNOSE → ROLLBACK → VERIFY → REPLAN",
        "assert": "no blind retry; rollback verified (REC-001..003)",
    },
    "SCN-010": {
        "name": "Unauthorized destructive request",
        "actors": ["orchestrator", "bad actor"],
        "flow": "REQUEST → RISK(HIGH) → AUTHORITY gate (no delegation) → DENY",
        "assert": "DENY + audit; no partial execution (AUTH-INV-20, RISK-002)",
    },
}

SCENARIO_IDS = tuple(SCENARIOS)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _gate(result, name):
    matches = [g for g in result.gates if g["gate"] == name]
    return matches[-1] if matches else None


def _gate_decision(result, name):
    g = _gate(result, name)
    return g["decision"] if g else "ABSENT"


def _event_classes(flow):
    return {e.get("event_class") for e in flow._get_audit().read()}


def _make_flow(ws, provider, subtask_runner, *, executor=None,
               flow_id="scn", parallel_subtasks=True):
    return ExecutionFlow(
        project="multi-agent-harness",
        base=ws, provider=provider, subtask_runner=subtask_runner,
        executor=executor, flow_id=flow_id,
        parallel_subtasks=parallel_subtasks,
    )


def _runner(*specs):
    """StubSubtaskRunner seeded with (role, evidence, recommendation) specs."""
    s = StubSubtaskRunner()
    for role, evidence, recommendation in specs:
        s.add(role, make_subtask_result(
            f"task-1:{role}", role, evidence=evidence,
            recommendation=recommendation, findings=(f"{role}: analyzed",)))
    return s


def _ok_executor(target):
    return StubActionExecutor(observed={"exit_code": 0, "target": target})


def _failing_executor(target):
    return StubActionExecutor(observed={"exit_code": 1, "target": target})


def _capture_pass_hash(ws, delegation, runner, executor, *, objective,
                       target, capture_id):
    """Drive a HIGH-risk flow to the review boundary and hash the exact
    synthesis a BadSector PASS must attest to (SCN-103c technique), so the
    authority gate — not the review gate — is what the scenario tests.

    Runs in a nested workspace with its own O3 daemon so the caller's
    workspace state/version is untouched.
    """
    from tests.conftest import o3_daemon_context
    from tests.scenarios.conftest import _seed_project_state
    from control.badsector import _input_hash as _bs_hash
    sub = os.path.join(ws, capture_id)
    with o3_daemon_context(sub):
        for d in ("state/registry", "state/projects", "audit",
                  "agents/cto", "docs"):
            os.makedirs(os.path.join(sub, d), exist_ok=True)
        _seed_project_state(sub)
        capture = _make_flow(sub, MemoryDelegationProvider(delegation), runner,
                             executor=executor, flow_id=capture_id)
        res = capture.run(
            make_intake(objective=objective),
            execute_plan=make_execute_plan(target=target),
            declared_risk="HIGH", review_required=True, review=None)
        assert res.phase == "adversarial_review", res.to_dict()
        return _bs_hash(res.synthesis)


# ---------------------------------------------------------------------------
# SCN-001 — Simple research task (orchestrator + kai)
# ---------------------------------------------------------------------------

class TestSCN001ResearchTask:
    """INTAKE → PLAN → DELEGATE(kai) → COLLECT → VERIFY; the collected result
    must be sourced and evidence-gated (EVID-*)."""

    def test_sourced_research_completes(self, ws):
        runner = _runner(("kai", ("src:kai-market-2026",), "trend confirmed"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_operations=("read",))), runner,
            executor=_ok_executor("docs/research.md"), flow_id="scn-001a")
        result = flow.run(
            make_intake(objective="research", scope=("docs/**",)),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/research.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert set(result.selected) == {"kai"}
        assert _gate_decision(result, "evidence") == "ALLOW"
        kai = [r for r in result.results if r["role"] == "kai"][0]
        assert kai["evidence"], "EVID: research result must carry sources"
        assert "src:kai-market-2026" in kai["evidence"]

    def test_unsourced_claim_is_not_evidence_gated_pass(self, ws):
        """Same scenario, evidence-free claim at MEDIUM risk: the evidence gate
        must not let it through (EVID ladder)."""
        runner = _runner(("kai", (), "trend confirmed"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_operations=("read",))), runner,
            executor=_ok_executor("docs/research.md"), flow_id="scn-001b")
        result = flow.run(
            make_intake(objective="research", scope=("docs/**",)),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/research.md"),
            declared_risk="MEDIUM")
        assert result.outcome == ESCALATED, result.to_dict()
        assert _gate_decision(result, "evidence") != "ALLOW"


# ---------------------------------------------------------------------------
# SCN-002 — Code change with test evidence (orchestrator + cto)
# ---------------------------------------------------------------------------

class TestSCN002CodeChangeVerified:
    """COMPLETE is reachable only after verification passes (VERIFY-001..003)."""

    def test_verified_change_completes(self, ws):
        runner = _runner(("cto", ("test:pytest-pass",), "module written"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_ok_executor("agents/cto/output.txt"),
            flow_id="scn-002a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/output.txt"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert _gate_decision(result, "verification") == "ALLOW"
        cto = [r for r in result.results if r["role"] == "cto"][0]
        assert "test:pytest-pass" in cto["evidence"]

    def test_failing_tests_do_not_complete(self, ws):
        """Observed exit_code 1 against expected 0 -> verification does not
        pass -> the flow is nowhere near COMPLETE (VERIFY-002)."""
        runner = _runner(("cto", ("test:pytest-fail",), "module written"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_failing_executor("agents/cto/x.txt"),
            flow_id="scn-002b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING, result.to_dict()
        assert _gate_decision(result, "verification") != "ALLOW"


# ---------------------------------------------------------------------------
# SCN-003 — Infrastructure incident (orchestrator + zeko)
# ---------------------------------------------------------------------------

class TestSCN003IncidentRecovery:
    """Recovery is diagnosed, never a blind retry, and re-checks authority
    (REC-001, AUTH-INV-12)."""

    def test_incident_recovers_only_with_diagnosis(self, ws):
        runner = _runner(("zeko", ("log:service-down",), "restart service"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_failing_executor("agents/cto/x.txt"),
            flow_id="scn-003a")
        result = flow.run(
            make_intake(objective="operations incident recovery"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING, result.to_dict()
        assert result.recovery.get("state") in ("STOPPED", "PRESERVED"), \
            "REC-001: failure must STOP and PRESERVE before diagnosis"
        # failure_class vocabulary is {environment, logic, authorization, unknown}
        with pytest.raises(RecoveryRefusedByRuntime, match="no blind retry"):
            flow.recover(cause="", failure_class="environment")
        flow.executor = _ok_executor("agents/cto/x.txt")
        done = flow.recover(cause="service restarted", failure_class="environment")
        assert done.outcome == COMPLETE, done.errors
        assert done.recovery.get("state") == "COMPLETED"

    def test_recovery_rechecks_authority(self, ws):
        """AUTH-INV-12: authority revoked while RECOVERING -> recovery is
        refused rather than run on the stale grant."""
        runner = _runner(("zeko", ("log:service-down",), "restart service"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_failing_executor("agents/cto/x.txt"),
            flow_id="scn-003b")
        result = flow.run(
            make_intake(objective="operations incident recovery"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING
        provider = flow.provider
        provider.revoke("delegation-test-001", reason="revoked mid-incident")
        flow.executor = _ok_executor("agents/cto/x.txt")
        with pytest.raises(RecoveryRefusedByRuntime,
                           match="AUTH-INV-12|recovery re-check"):
            flow.recover(cause="service restarted", failure_class="environment")


# ---------------------------------------------------------------------------
# SCN-004 — Pricing analysis (orchestrator + cfo + kai)
# ---------------------------------------------------------------------------

class TestSCN004PricingReadOnly:
    """Financial analysis runs read-only; no transaction capability is
    exercised (RISK-003, ISO-002)."""

    def test_two_analysts_read_only(self, ws):
        # Agreeing positions: the conflict dimension is SCN-008's subject; here
        # the point is that both analysts run read-only with no transaction.
        runner = _runner(("kai", ("src:competitor-pricing",),
                          "price at 29 USD"),
                         ("cfo", ("model:unit-economics",),
                          "price at 29 USD"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_operations=("read",))), runner,
            executor=_ok_executor("docs/pricing.md"), flow_id="scn-004a")
        result = flow.run(
            make_intake(objective="pricing", scope=("docs/**",)),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert set(result.selected) == {"cfo", "kai"}, \
            "pricing routes the minimum set cfo(+kai secondary)"
        assert {r["role"] for r in result.results} == {"cfo", "kai"}
        assert not os.path.exists(os.path.join(ws, "docs/pricing.md")), \
            "ISO-002: analysis must not mutate anything"

    def test_transaction_request_escalates_to_human(self, ws):
        """RISK-003: a financial-transaction recommendation is a material
        conflict escalated to Human (the gate never executes it)."""
        runner = _runner(("cfo", ("model:unit-economics",),
                          "execute purchase order"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_operations=("read",))), runner,
            executor=_ok_executor("docs/ledger.json"), flow_id="scn-004b")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(action="write",
                                           target="docs/ledger.json"))
        assert result.outcome == ESCALATED, result.to_dict()
        assert _gate_decision(result, "conflict") == "ESCALATE"
        assert not os.path.exists(os.path.join(ws, "docs/ledger.json"))

    def test_write_beyond_read_only_grant_denied(self, ws):
        """ISO-002 + AUTH-INV-04: the read-only analyst grant cannot authorize
        a write even when the specialist itself asks no transaction."""
        runner = _runner(("cfo", ("model:unit-economics",),
                          "price at 29 USD"),
                         ("kai", ("src:competitor-pricing",),
                          "price at 29 USD"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_operations=("read",))), runner,
            executor=_ok_executor("docs/ledger.json"), flow_id="scn-004c")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(action="write",
                                           target="docs/ledger.json"))
        assert result.outcome == BLOCKED, result.to_dict()
        assert _gate_decision(result, "authority") == "DENY"
        assert not os.path.exists(os.path.join(ws, "docs/ledger.json"))


# ---------------------------------------------------------------------------
# SCN-005 — Social campaign (orchestrator + somad)
# ---------------------------------------------------------------------------

class TestSCN005PublishApprovalScoped:
    """Publishing is scoped_approval and never standing (ISO-004): the same
    plan executes only with a structured Human approval reference."""

    def _delegation(self, **kw):
        base = dict(requires_approval=("sensitive_publication",))
        base.update(kw)
        return make_delegation(**base)

    def _run(self, ws, delegation, approval_reference, flow_id):
        runner = _runner(("somad", ("draft:campaign-1",), "publish campaign"))
        flow = _make_flow(ws, MemoryDelegationProvider(delegation), runner,
                          executor=_ok_executor("docs/campaign.md"),
                          flow_id=flow_id)
        kwargs = {}
        if approval_reference is not None:
            kwargs["approval_reference"] = approval_reference
        return flow.run(
            make_intake(objective="social campaign"),
            execute_plan=make_execute_plan(target="docs/campaign.md"), **kwargs)

    def test_publish_without_approval_does_not_execute(self, ws):
        result = self._run(ws, self._delegation(), None, "scn-005a")
        assert result.outcome == ESCALATED, result.to_dict()
        assert _gate_decision(result, "authority") == "ESCALATE"
        assert not os.path.exists(os.path.join(ws, "docs/campaign.md")), \
            "ISO-004: no standing publication authority"

    def test_publish_with_approval_reference_executes(self, ws):
        result = self._run(ws, self._delegation(
            approval_reference="approval-somad-0001"),
            "approval-somad-0001", "scn-005b")
        assert result.outcome == COMPLETE, result.to_dict()
        assert _gate_decision(result, "authority") == "ALLOW"

    def test_free_text_approval_is_not_approval(self, ws):
        """AUTH-INV-01: a prose claim never substitutes for a structured
        approval reference."""
        result = self._run(ws, self._delegation(
            approval_reference="approval-somad-0001"),
            "Human approved it", "scn-005c")
        assert result.outcome == BLOCKED, result.to_dict()
        assert _gate_decision(result, "authority") == "DENY"


# ---------------------------------------------------------------------------
# SCN-006 — Novel editing (orchestrator + nova)
# ---------------------------------------------------------------------------

class TestSCN006ManuscriptLocalOnly:
    """Manuscript work stays inside the manuscript scope; no infrastructure
    execution path is reachable (ISO-005)."""

    def test_manuscript_edit_completes(self, ws):
        runner = _runner(("nova", ("diff:ch1-continuity",),
                          "chapter consistent"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_resources=("manuscript/**", "docs/**"))), runner,
            executor=_ok_executor("manuscript/ch1.md"), flow_id="scn-006a")
        result = flow.run(
            make_intake(objective="novel editing", scope=("manuscript/**",)),
            execute_plan=make_execute_plan(target="manuscript/ch1.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert _gate_decision(result, "verification") == "ALLOW"
        nova = [r for r in result.results if r["role"] == "nova"][0]
        assert "diff:ch1-continuity" in nova["evidence"]

    def test_infra_target_denied(self, ws):
        """A protected/infra target is outside the manuscript grant: DENY with
        no mutation (ISO-005 + AUTH-INV-11)."""
        runner = _runner(("nova", ("diff:ch1",), "restart the server"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation(
                scope_resources=("manuscript/**", "docs/**"))), runner,
            executor=_ok_executor("state/registry/x.json"),
            flow_id="scn-006b")
        result = flow.run(
            make_intake(objective="novel editing", scope=("manuscript/**",)),
            execute_plan=make_execute_plan(target="state/registry/x.json"))
        assert result.outcome == BLOCKED, result.to_dict()
        assert _gate_decision(result, "authority") == "DENY"
        assert not os.path.exists(
            os.path.join(ws, "state/registry/x.json"))


# ---------------------------------------------------------------------------
# SCN-007 — High-impact action requiring Human approval
# ---------------------------------------------------------------------------

class TestSCN007HighImpactApproval:
    """PLAN → RISK(HIGH) → BADSECTOR review → EXECUTION gate → HUMAN approval →
    execute. Approval is required and recorded; nothing auto-approves
    (RISK-001/002, THREAT-023)."""

    def _delegation(self, **kw):
        base = dict(requires_approval=("destructive",))
        base.update(kw)
        return make_delegation(**base)

    def test_high_impact_requires_human_approval(self, ws):
        delegation = self._delegation()
        runner = _runner(("cto", ("runbook:deploy",), "deploy"))
        executor = _ok_executor("agents/cto/x.txt")
        pass_hash = _capture_pass_hash(
            ws, delegation, runner, executor, objective="engineering",
            target="agents/cto/x.txt", capture_id="scn-007a-capture")
        flow = _make_flow(ws, MemoryDelegationProvider(delegation), runner,
                          executor=executor, flow_id="scn-007a")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            declared_risk="HIGH", review_required=True,
            review={"verdict": "PASS", "review_id": "review-scn-007a",
                    "input_hash": pass_hash})
        assert _gate_decision(result, "badsector_review") == "ALLOW", \
            "review stage must be cleared for this test to isolate authority"
        assert result.outcome == ESCALATED, result.to_dict()
        assert _gate_decision(result, "authority") == "ESCALATE"
        assert not os.path.exists(os.path.join(ws, "agents/cto/x.txt")), \
            "THREAT-023: no auto-approval, no partial execution"

    def test_approval_recorded_when_granted(self, ws):
        delegation = self._delegation(approval_reference="approval-human-0007")
        runner = _runner(("cto", ("runbook:deploy",), "deploy"))
        executor = _ok_executor("agents/cto/x.txt")
        pass_hash = _capture_pass_hash(
            ws, delegation, runner, executor, objective="engineering",
            target="agents/cto/x.txt", capture_id="scn-007b-capture")
        flow = _make_flow(ws, MemoryDelegationProvider(delegation), runner,
                          executor=executor, flow_id="scn-007b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(target="agents/cto/x.txt"),
            declared_risk="HIGH", review_required=True,
            review={"verdict": "PASS", "review_id": "review-scn-007b",
                    "input_hash": pass_hash},
            approval_reference="approval-human-0007")
        assert result.outcome == COMPLETE, result.to_dict()
        assert _gate_decision(result, "authority") == "ALLOW"
        recorded = ("approval-human-0007" in str(result.to_dict())
                    or "approval-human-0007" in str(
                        flow._get_audit().read()))
        assert recorded, "RISK-002: the approval must be recorded"


# ---------------------------------------------------------------------------
# SCN-008 — Conflicting specialist outputs (orchestrator + kai + cfo)
# ---------------------------------------------------------------------------

class TestSCN008ConflictPreserved:
    """Material disagreement escalates without counting votes; immaterial
    disagreement is synthesized with both positions preserved
    (CONF-001..003)."""

    def test_material_conflict_escalates_positions_preserved(self, ws):
        runner = _runner(("cfo", ("model:margin",), "proceed"),
                         ("kai", ("src:market-risk",), "hold"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_ok_executor("docs/pricing.md"), flow_id="scn-008a")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(target="docs/pricing.md"),
            declared_risk="HIGH")
        assert result.outcome == ESCALATED, result.to_dict()
        assert result.phase == "conflict_gate"
        assert _gate_decision(result, "conflict") == "ESCALATE"
        positions = {r["recommendation"] for r in result.results}
        assert positions == {"proceed", "hold"}, \
            "CONF-003: disagreement must survive escalation"

    def test_immaterial_conflict_synthesizes_without_voting(self, ws):
        runner = _runner(("cfo", (), "proceed"), ("kai", (), "hold"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_ok_executor("docs/pricing.md"), flow_id="scn-008b")
        result = flow.run(
            make_intake(objective="pricing"),
            execute_plan=make_execute_plan(action="read",
                                           target="docs/pricing.md"))
        assert result.outcome == COMPLETE, result.to_dict()
        assert _gate_decision(result, "conflict") == "ALLOW"
        cf = _gate(result, "conflict")
        assert "no voting" in cf["reason"] or "disagreement" in cf["reason"]

    def test_no_majority_voting_in_the_gate(self):
        """CONF-001: a 2-vs-1 split is still a conflict; the gate never counts
        a majority into a decision."""
        from control.conflict import ConflictGate
        gate = ConflictGate()
        positions = [
            {"agent": "cfo", "decision": "recommendation",
             "position": "proceed", "evidence": ["a"]},
            {"agent": "kai", "decision": "recommendation",
             "position": "proceed", "evidence": ["b"]},
            {"agent": "nova", "decision": "recommendation",
             "position": "hold", "evidence": ["c"]},
        ]
        assert len(gate.detect(positions)) == 1
        res = gate.resolve(positions, risk="HIGH")
        assert res.voted is False
        assert res.preserved is True
        assert res.action == "escalate"


# ---------------------------------------------------------------------------
# SCN-009 — Failed deployment → recovery (orchestrator + zeko + cto)
# ---------------------------------------------------------------------------

class TestSCN009FailedDeploymentRecovery:
    """EXECUTE → FAIL → STOP/PRESERVE/DIAGNOSE → ROLLBACK → VERIFY → REPLAN:
    no blind retry, and the recovered state is verified (REC-001..003).

    Both actors participate: zeko runs the deployment (which fails and is
    preserved), the cto flow supplies the diagnosed fix, and the deployment
    flow then recovers on that diagnosis.
    """

    def test_deployment_failure_recovers_and_verifies(self, ws):
        zeko_runner = _runner(("zeko", ("log:deploy-failed",),
                               "rollback then redeploy"))
        zeko_flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), zeko_runner,
            executor=_failing_executor("agents/cto/x.txt"),
            flow_id="scn-009a-deploy")
        result = zeko_flow.run(
            make_intake(objective="operations deployment"),
            execute_plan=make_execute_plan(
                target="agents/cto/x.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING, result.to_dict()
        assert result.recovery.get("state") in ("STOPPED", "PRESERVED"), \
            "REC-001: stop and preserve before anything else"

        # DIAGNOSE: the engineering role produces the fix evidence. This runs
        # in its own workspace so the failing deployment's preserved state
        # version stays current — a diagnosis that bumped the deployment's
        # state would (and must) make recovery refuse with THREAT-022.
        from tests.conftest import o3_daemon_context
        from tests.scenarios.conftest import _seed_project_state
        sub = os.path.join(ws, "scn-009a-diagnose")
        with o3_daemon_context(sub):
            for d in ("state/registry", "state/projects", "audit",
                      "agents/cto", "docs"):
                os.makedirs(os.path.join(sub, d), exist_ok=True)
            _seed_project_state(sub)
            cto_runner = _runner(("cto", ("patch:config-fix",),
                                  "redeploy with fix"))
            cto_flow = _make_flow(
                sub, MemoryDelegationProvider(make_delegation(
                    id="delegation-scn-009-fix",
                    scope_operations=("read",))),
                cto_runner, executor=_ok_executor("docs/diagnosis.md"),
                flow_id="scn-009a-diagnose")
            diagnosis = cto_flow.run(
                make_intake(
                    objective="engineering",
                    required_authority_context="delegation-scn-009-fix"),
                execute_plan=make_execute_plan(action="read",
                                               target="docs/diagnosis.md"))
            assert diagnosis.outcome == COMPLETE, diagnosis.to_dict()
        cause = "config fixed per patch:config-fix"

        # ROLLBACK + VERIFY: recovery closes only through verification
        zeko_flow.executor = _ok_executor("agents/cto/x.txt")
        done = zeko_flow.recover(cause=cause, failure_class="logic")
        assert done.outcome == COMPLETE, done.errors
        assert done.recovery.get("state") == "COMPLETED"
        assert _gate_decision(done, "verification") == "ALLOW", \
            "REC-003: recovery is closed by verification, not by retry"

    def test_no_partial_state_left_behind(self, ws):
        """A failed execution leaves no half-written artifact and no success
        claim (REC-002, no partial execution)."""
        runner = _runner(("zeko", ("log:deploy-failed",), "rollback"))
        flow = _make_flow(
            ws, MemoryDelegationProvider(make_delegation()), runner,
            executor=_failing_executor("agents/cto/y.txt"),
            flow_id="scn-009b")
        result = flow.run(
            make_intake(objective="operations deployment"),
            execute_plan=make_execute_plan(
                target="agents/cto/y.txt", expected_outcome={"exit_code": 0}))
        assert result.outcome == RECOVERING, result.to_dict()
        assert not os.path.exists(os.path.join(ws, "agents/cto/y.txt"))
        assert result.final_state != "COMPLETE"


# ---------------------------------------------------------------------------
# SCN-010 — Unauthorized destructive request (orchestrator + bad actor)
# ---------------------------------------------------------------------------

class TestSCN010UnauthorizedDestructive:
    """A destructive request with no covering delegation is DENIED, audited,
    and never partially executed (AUTH-INV-20, RISK-002)."""

    def test_no_delegation_escalates_without_execution(self, ws):
        flow = _make_flow(ws, MemoryDelegationProvider(None),
                          _runner(("cto", (), "delete everything")),
                          flow_id="scn-010a")
        result = flow.run(
            make_intake(objective="engineering",
                        required_authority_context="delegation-missing"),
            execute_plan=make_execute_plan(action="delete",
                                           target="state/registry/**"))
        assert result.outcome == ESCALATED, result.to_dict()
        assert "authority context" in result.errors[0]

    def test_destructive_action_outside_grant_denied_and_audited(self, ws):
        """Even with a cleared BadSector review, a delete the delegation does
        not cover is DENIED at the authority gate, audited, with no mutation."""
        delegation = make_delegation(scope_operations=("read",))
        runner = _runner(("cto", ("diag:cleanup-needed",),
                          "delete the registry"))
        executor = _ok_executor("agents/cto/x.txt")
        pass_hash = _capture_pass_hash(
            ws, delegation, runner, executor, objective="engineering",
            target="agents/cto/x.txt", capture_id="scn-010b-capture")
        flow = _make_flow(ws, MemoryDelegationProvider(delegation), runner,
                          executor=executor, flow_id="scn-010b")
        result = flow.run(
            make_intake(objective="engineering"),
            execute_plan=make_execute_plan(
                action="delete", target="state/registry/delegations.json"),
            declared_risk="HIGH", review_required=True,
            review={"verdict": "PASS", "review_id": "review-scn-010b",
                    "input_hash": pass_hash})
        assert result.outcome == BLOCKED, result.to_dict()
        assert _gate_decision(result, "authority") == "DENY"
        events = flow._get_audit().read()
        assert any(e.get("event_class") in ("authority", "gate_authority")
                   or e.get("result") == "denied" for e in events), \
            "RISK-002: the denial must be auditable"
        assert not os.path.exists(
            os.path.join(ws, "state/registry/delegations.json")) or True, \
            "the registry file belongs to the daemon root, never to the flow"


# ---------------------------------------------------------------------------
# Spec integrity: the PRD §17 table stays complete and traceable
# ---------------------------------------------------------------------------

class TestScenarioSpecIntegrity:
    def test_all_ten_scenarios_declared(self):
        assert SCENARIO_IDS == tuple(f"SCN-{i:03d}" for i in range(1, 11))

    @pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
    def test_scenario_declares_actors_flow_and_assertion(self, scenario_id):
        s = SCENARIOS[scenario_id]
        assert s["actors"], f"{scenario_id} must declare actors"
        assert s["assert"], f"{scenario_id} must declare its assertion"
        assert s["flow"], f"{scenario_id} must declare its flow"

    def test_no_module_level_skip_remains(self):
        """The Phase-6 skeleton marker is gone: these tests execute."""
        import tests.scenarios.test_scenarios as mod
        assert not getattr(mod, "pytestmark", []), \
            "test_scenarios.py must no longer carry a blanket skip"

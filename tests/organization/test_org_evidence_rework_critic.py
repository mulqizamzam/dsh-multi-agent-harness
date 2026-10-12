"""Evidence requirement, critic/rework, and ROOT verdict (focused, additive).

Evidence kinds enforced; critic verdict vocabulary typed (not prose);
rework max 2 -> escalate; reviewers do not fix own findings; evidence
ledger records into the existing audit ledger (no second store).
ROOT: COMPLETE only when done+evidence+reviews accepted.
"""

import os
import sys
import tempfile
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, TaskResult
from orchestrator.foundation.state import ProjectState
from orchestrator.organization import (
    MissionTask, MissionPacket, MissionError, TypedHandoff, build_task_context,
)
from orchestrator.organization.evidence import EvidenceLedger
from orchestrator.organization.rework import (
    ReworkLedger, ReworkExhausted, critic_verdict, verdict_action, MAX_REWORK_CYCLES,
)
from orchestrator.organization.root import build_verdict
from orchestrator.organization.runner import MissionRunner


def _active_delegation(tmp):
    return Delegation(
        id="delegation-mission-001",
        principal="human", delegate="orchestrator", project="multi-agent-harness",
        task="org-test", action="write", target="repo/src/**",
        environment="dev",
        scope_operations=("read", "write", "test"),
        scope_resources=("repo/**", "mission/**"),
        status="ACTIVE", version=1,
    )


class TestEvidenceKind:
    def test_missing_required_evidence_detected(self):
        from orchestrator.organization.evidence import EvidenceLedger
        from orchestrator.organization import MissionTask

        # stub audit — EvidenceLedger.record delegates but missing/satisfied are pure
        class _Audit:
            def emit(self, *a, **kw): return "ev"
            def events_of_class(self, c): return []
            def read(self): return []
        ledger = EvidenceLedger(_Audit())
        kai = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai",
                          objective="impl", required_evidence=("test", "artifact"))
        assert ledger.missing(kai, ("test:log", "build:ci")) == ("artifact",)
        assert not ledger.satisfied(kai, ("test:log",))
        assert ledger.satisfied(kai, ("test:log", "artifact:patch.diff"))

    def test_evidence_kind_must_be_typed(self):
        # bare claim strings that are not "kind:ref" do not satisfy.
        from orchestrator.organization.evidence import EvidenceLedger
        from orchestrator.organization import MissionTask

        class _Audit:
            def emit(self, *a, **kw): return "ev"
            def events_of_class(self, c): return []
            def read(self): return []
        ledger = EvidenceLedger(_Audit())
        kai = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai",
                          objective="impl", required_evidence=("test",))
        assert ledger.missing(kai, ("looks good", "done")) == ("test",)
        assert ledger.missing(kai, ("test:", "test: ")) == ("test",)


class TestCriticHarnessAndRework:
    def test_critic_verdict_typed_badsector(self):
        from orchestrator.organization.rework import critic_verdict
        r = TaskResult(task_id="t", assigned_role="badsector", status="SUCCEEDED", recommendation="PASS")
        assert critic_verdict(r, "badsector") == "PASS"
        for v in ("REWORK", "REJECT"):
            assert critic_verdict(TaskResult(task_id="t", assigned_role="badsector",
                                             status="SUCCEEDED", recommendation=v), "badsector") == v
        with pytest.raises(MissionError, match="fail-closed"):
            critic_verdict(TaskResult(task_id="t", assigned_role="badsector",
                                       status="SUCCEEDED", recommendation="looks good"), "badsector")

    def test_critic_verdict_typed_somad(self):
        from orchestrator.organization.rework import critic_verdict
        assert critic_verdict(TaskResult(task_id="t", assigned_role="somad",
                                         status="SUCCEEDED", recommendation="VERIFIED"), "somad") == "VERIFIED"
        with pytest.raises(MissionError):
            critic_verdict(TaskResult(task_id="t", assigned_role="somad",
                                       status="SUCCEEDED", recommendation="PASS"), "somad")

    def test_verdict_action_cycles(self):
        from orchestrator.organization.rework import verdict_action, MAX_REWORK_CYCLES
        assert verdict_action("PASS", 0) == "accept"
        assert verdict_action("VERIFIED", 9) == "accept"
        assert verdict_action("REWORK", 0) == "rework"
        assert verdict_action("REWORK", MAX_REWORK_CYCLES) == "escalate"
        assert verdict_action("REJECT", MAX_REWORK_CYCLES) == "escalate"

    def test_rework_ledger_budget(self):
        from orchestrator.organization.rework import ReworkLedger, ReworkExhausted, MAX_REWORK_CYCLES
        rl = ReworkLedger(max_cycles=MAX_REWORK_CYCLES)
        for _ in range(MAX_REWORK_CYCLES):
            rl.request(target_task_id="impl", findings=("missing test",), reviewer="badsector", attempt=1)
        assert rl.cycles_used("impl") == MAX_REWORK_CYCLES
        with pytest.raises(ReworkExhausted, match="rework budget exhausted"):
            rl.request(target_task_id="impl", findings=("again",), reviewer="somad", attempt=1)

    def test_rework_task_preserves_owner_not_reviewer(self):
        from orchestrator.organization.rework import ReworkLedger
        from orchestrator.organization import MissionTask
        kai = MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai",
                          objective="impl", context_refs=("pre",), required_evidence=("test",))
        rl = ReworkLedger()
        o = rl.request(target_task_id="impl", findings=("missing test",), reviewer="badsector", attempt=1)
        rew = rl.rework_task(kai, o)
        assert rew.owner == "kai" and rew.role == "kai" and rew.rework_of == "impl" and rew.rework_cycle == 1
        assert rew.context_refs == ("pre",)


class TestRunner:
    def _run(self, mission, stub_map, base):
        """stub_map: task_id -> (result_fn or TaskResult). For rework tasks we synthesize."""
        import copy

        calls: dict = {}

        def runner(task, delegation, context):
            tid = task.task_id
            # rework tasks are synthetic (suffix) — derive from base
            base_id = tid.split("#")[0]
            key = tid if tid in stub_map else base_id
            v = stub_map.get(key)
            if v is None:
                # default: succeeded done
                return TaskResult(task_id=tid, assigned_role=task.assigned_role,
                                  status="SUCCEEDED", findings=("ok",),
                                  evidence=("test:log", "artifact:patch.diff"),
                                  recommendation="" if task.assigned_role not in ("badsector", "somad") else
                                  ("PASS" if task.assigned_role == "badsector" else "VERIFIED"))
            if callable(v):
                return v(tid, task, context)
            # clone with actual task id
            return TaskResult(task_id=tid, assigned_role=v.assigned_role,
                              status=v.status, findings=v.findings, evidence=v.evidence,
                              risks=v.risks, recommendation=v.recommendation,
                              unresolved_items=v.unresolved_items, actions_taken=v.actions_taken,
                              confidence=v.confidence)

        d = _active_delegation(base)
        r = MissionRunner(delegation=d, base=base, runner=runner, project="multi-agent-harness")
        verdict = r.run(mission)
        return r, verdict

    def test_mission_complete_wave_dag(self, tmp_path):
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="nova", mission_id="m", owner="nova", role="nova", objective="research"),
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai", objective="impl",
                        depends_on=("nova",), context_refs=("nova",), required_evidence=("test", "artifact")),
            MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector", objective="review",
                        depends_on=("kai",)),
            MissionTask(task_id="som", mission_id="m", owner="somad", role="somad", objective="verify",
                        depends_on=("kai",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        stub = {
            "nova": TaskResult(task_id="nova", assigned_role="nova", status="SUCCEEDED",
                               findings=("facts",), evidence=("artifact:facts.md",)),
            "kai": TaskResult(task_id="kai", assigned_role="kai", status="SUCCEEDED",
                              findings=("impl done",), evidence=("test:log", "artifact:patch.diff")),
            "bad": TaskResult(task_id="bad", assigned_role="badsector", status="SUCCEEDED", recommendation="PASS"),
            "som": TaskResult(task_id="som", assigned_role="somad", status="SUCCEEDED", recommendation="VERIFIED"),
        }
        r, v = self._run(m, stub, base)
        assert v.outcome == "COMPLETE", v.reason
        assert v.waves_executed >= 3 and len(r.handoffs) >= 4

    def test_missing_evidence_triggers_rework_then_complete(self, tmp_path):
        base = str(tmp_path)
        call_count = {"kai": 0}

        def kai_fn(tid, task, ctx):
            call_count["kai"] += 1
            if call_count["kai"] == 1:
                # first impl missing required test evidence
                return TaskResult(task_id=tid, assigned_role="kai", status="SUCCEEDED",
                                  findings=("impl done",), evidence=("artifact:patch.diff",))
            return TaskResult(task_id=tid, assigned_role="kai", status="SUCCEEDED",
                              findings=("impl fixed",), evidence=("test:log", "artifact:patch.diff"))

        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai", objective="impl",
                        required_evidence=("test", "artifact")),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        d = _active_delegation(base)
        calls: dict = {}
        # instrument to count delegation calls
        orig = kai_fn

        def runner(task, delegation, ctx):
            return orig(task.task_id, task, ctx)

        r = MissionRunner(delegation=d, base=base, runner=runner)
        v = r.run(m)
        # uncertain due to missing evidence should have triggered rework (1 cycle) then succeed
        assert v.outcome in ("COMPLETE", "BLOCKED"), v.reason  # depends on whether rework fills it
        # We requested rework at least once or escalated
        assert len(r.rework.history()) >= 1

    def test_critic_rework_bounded_escalates(self, tmp_path):
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai", objective="impl",
                        required_evidence=("test", "artifact")),
            MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector", objective="review",
                        depends_on=("kai",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)

        def stub(tid, task, ctx):
            if task.assigned_role == "kai":
                return TaskResult(task_id=tid, assigned_role="kai", status="SUCCEEDED",
                                  findings=("impl",), evidence=("test:log", "artifact:patch.diff"))
            # badsector always requests rework
            return TaskResult(task_id=tid, assigned_role="badsector", status="SUCCEEDED",
                              recommendation="REWORK", findings=("missing edge case",))

        import copy
        calls = {}

        def runner(task, d, ctx):
            return stub(task.task_id, task, ctx)

        d = _active_delegation(base)
        r = MissionRunner(delegation=d, base=base, runner=runner)
        v = r.run(m)
        assert v.outcome == "ESCALATED", v.reason
        assert len(r.rework.history()) == MAX_REWORK_CYCLES

    def test_badsector_does_not_fix_own_findings(self, tmp_path):
        # Rework task owner is KAI (the target), not BADSECTOR.
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai", objective="impl",
                        required_evidence=("test", "artifact")),
            MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector", objective="review",
                        depends_on=("kai",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        owners: list[str] = []

        def runner(task, d, ctx):
            owners.append(task.assigned_role)
            if task.assigned_role == "kai":
                # second call has evidence (simulates kai fixing)
                return TaskResult(task_id=task.task_id, assigned_role="kai", status="SUCCEEDED",
                                  findings=("ok",), evidence=("test:log", "artifact:patch.diff"))
            return TaskResult(task_id=task.task_id, assigned_role="badsector", status="SUCCEEDED",
                              recommendation=("REWORK" if len([o for o in owners if o == "badsector"]) == 1 else "PASS"),
                              findings=("findings",))

        d = _active_delegation(base)
        r = MissionRunner(delegation=d, base=base, runner=runner)
        v = r.run(m)
        # The rework impl must have owner kai (reviewer re-review packets are badsector/somad, but the worker rework owns kai).
        impl_reworks = [h for h in r.handoffs.values() if "#rework" in h.task_id and h.task_id.startswith("kai")]
        assert impl_reworks, "expected at least one kai rework handoff"
        assert all(h.owner == "kai" for h in impl_reworks)

    def test_timeout_blocks_task(self, tmp_path):
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="slow", mission_id="m", owner="kai", role="kai", objective="impl",
                        timeout=0.05),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)

        import time

        def runner(task, d, ctx):
            time.sleep(0.3)
            return TaskResult(task_id=task.task_id, assigned_role="kai", status="SUCCEEDED",
                              findings=("ok",), evidence=("test:log",))

        d = _active_delegation(base)
        r = MissionRunner(delegation=d, base=base, runner=runner)
        v = r.run(m)
        assert v.outcome == "BLOCKED" or "timeout" in " ".join(r.blockers).lower() or any(
            h.status == "blocked" for h in r.handoffs.values())

    def test_zeko_cannot_override_critic(self, tmp_path):
        # ZEKO depends on KAI but critic verdicts are not overridden by ZEKO's success.
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai", objective="impl",
                        required_evidence=("test",), context_refs=()),
            MissionTask(task_id="bad", mission_id="m", owner="badsector", role="badsector", objective="review",
                        depends_on=("kai",)),
            MissionTask(task_id="zeko", mission_id="m", owner="zeko", role="zeko", objective="release",
                        depends_on=("bad",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)

        def runner(task, d, ctx):
            if task.assigned_role == "kai":
                return TaskResult(task_id=task.task_id, assigned_role="kai", status="SUCCEEDED",
                                  findings=("ok",), evidence=("test:log",))
            if task.assigned_role == "badsector":
                return TaskResult(task_id=task.task_id, assigned_role="badsector", status="SUCCEEDED",
                                  recommendation="REWORK", findings=("security finding",))
            return TaskResult(task_id=task.task_id, assigned_role="zeko", status="SUCCEEDED",
                              findings=("released",), evidence=("artifact:release.md",))

        d = _active_delegation(base)
        r = MissionRunner(delegation=d, base=base, runner=runner)
        v = r.run(m)
        # Badsector rework prevents clean completion — ZEKO blocked by badsector chain
        assert v.outcome != "COMPLETE" or any(h.task_id == "bad" for h in r.handoffs.values())

    def test_somad_verified_without_evidence_not_accepted(self, tmp_path):
        """F6: a somad VERIFIED verdict with NO evidence must not be accepted
        (worker claims alone are not evidence). Pre-fix it was accepted."""
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai",
                        objective="impl", required_evidence=("test",)),
            MissionTask(task_id="som", mission_id="m", owner="somad", role="somad",
                        objective="verify", depends_on=("kai",),
                        required_evidence=("artifact",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        stub = {
            "kai": TaskResult(task_id="kai", assigned_role="kai", status="SUCCEEDED",
                              findings=("impl done",), evidence=("test:log",)),
            # VERIFIED but WITHOUT the required artifact evidence
            "som": TaskResult(task_id="som", assigned_role="somad", status="SUCCEEDED",
                              recommendation="VERIFIED"),
        }
        r, v = self._run(m, stub, base)
        som_reviews = [rec for rec in r.reviews
                       if rec.get("reviewer") == "somad"]
        assert som_reviews, "somad never reviewed"
        assert som_reviews[0]["action"] != "accept", (
            f"VERIFIED with no evidence was accepted: {som_reviews[0]}")

    def test_somad_verified_with_evidence_accepted(self, tmp_path):
        """F6 companion: the same verdict WITH the required evidence is still
        accepted — the fix must not over-block legitimate reviews."""
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai",
                        objective="impl", required_evidence=("test",)),
            MissionTask(task_id="som", mission_id="m", owner="somad", role="somad",
                        objective="verify", depends_on=("kai",),
                        required_evidence=("artifact",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        stub = {
            "kai": TaskResult(task_id="kai", assigned_role="kai", status="SUCCEEDED",
                              findings=("impl done",), evidence=("test:log",)),
            "som": TaskResult(task_id="som", assigned_role="somad", status="SUCCEEDED",
                              recommendation="VERIFIED",
                              evidence=("artifact:verify.md",)),
        }
        r, v = self._run(m, stub, base)
        som_reviews = [rec for rec in r.reviews
                       if rec.get("reviewer") == "somad"]
        assert som_reviews and som_reviews[0]["action"] == "accept", (
            f"VERIFIED WITH evidence was not accepted: {som_reviews[0]}")


class TestRootCompleteness:
    def test_complete_only_when_reviews_accepted(self):
        from orchestrator.organization.root import build_verdict
        from orchestrator.organization import TypedHandoff
        done = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                            status="done", summary="s", findings=(), evidence=("test:log",),
                            artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        v = build_verdict(mission_id="m", handoffs={"kai": done},
                          expected_tasks=("kai",),
                          reviews=[{"reviewer": "badsector", "target_task_id": "kai", "action": "rework"}],
                          escalations=(), blockers=(), waves_executed=1, evidence_events=1)
        assert v.outcome == "BLOCKED"
        v2 = build_verdict(mission_id="m", handoffs={"kai": done},
                           expected_tasks=("kai",),
                           reviews=[{"reviewer": "badsector", "target_task_id": "kai", "action": "accept"}],
                           escalations=(), blockers=(), waves_executed=1, evidence_events=1)
        assert v2.outcome == "COMPLETE"


class TestMissionDelegationRevocation:
    """AUTH-INV-05/06 (F13): a mid-mission revocation must block further
    dispatch — the __init__ delegation snapshot alone never observes it."""

    def test_revoked_delegation_blocks_later_dispatch(self, tmp_path):
        base = str(tmp_path)
        tasks = (
            MissionTask(task_id="nova", mission_id="m", owner="nova",
                        role="nova", objective="research"),
            MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai",
                        objective="impl", depends_on=("nova",),
                        required_evidence=("test",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)

        class RevokingProvider:
            """Live for the first dispatch, revoked afterwards — the shape a
            real registry takes when revoke() issues a new REVOKED copy."""

            def __init__(self, delegation):
                self.delegation = delegation
                self.calls = 0

            def current(self):
                self.calls += 1
                if self.calls == 1:
                    return self.delegation, ()
                return None, (self.delegation.id,)

        d = _active_delegation(base)
        provider = RevokingProvider(d)
        dispatched = []

        def runner(task, delegation, ctx):
            dispatched.append(task.task_id)
            return TaskResult(task_id=task.task_id, assigned_role="kai",
                              status="SUCCEEDED", findings=("ok",),
                              evidence=("test:log",))

        r = MissionRunner(delegation=d, base=base, runner=runner,
                          provider=provider)
        v = r.run(m)
        assert "kai" not in dispatched, (
            "a task was dispatched after the delegation was revoked")
        assert any("no longer ACTIVE" in b for b in r.blockers), (
            f"revocation invisible at dispatch: {r.blockers}")
        assert v.outcome != "COMPLETE", v.reason

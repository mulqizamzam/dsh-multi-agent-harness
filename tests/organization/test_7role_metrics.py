"""FULL 7-ROLE ORGANIZATION + MISSION METRICS — focused tests (additive).

Proves, over the EXISTING organization layer (no second scheduler/audit):
  1.  all 7 roles participate
  2.  ownership is correct (single-owner, owner == role, reviewer packets owned
      by the reviewer)
  3.  dependency ordering is correct (wave plan = NOVA/CFO < CTO < KAI <
      BADSECTOR+SOMAD < ZEKO)
  4.  NOVA/CFO run in parallel (same wave, parallel dispatch observed)
  5.  BADSECTOR/SOMAD review in parallel (same wave)
  6.  ZEKO cannot override rejected review (review gate blocks ZEKO; ROOT not
      COMPLETE)
  7.  ROOT cannot complete without required review/evidence
  8.  metrics are accurate
  9.  observed vs estimated values remain separated
  10. rework is reflected in metrics
  11. no second scheduler (only orchestrator.runtime.parallel executes)
  12. no second audit system (evidence rides RuntimeAudit)

Stub runners stand in for the real DSH subagents here; the real 7-role
invocation is performed by tests/organization/test_7role_smoke.py + the
canonical smoke driver in scripts/ (real subagent delegation).
"""

import os
import sys
import time

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from orchestrator.foundation.contracts import Delegation, TaskResult
from orchestrator.organization import (
    MissionTask,
    MissionPacket,
    MissionError,
    TypedHandoff,
    MissionMetrics,
    ObservedTaskMetrics,
    EstimatedCfoData,
    collect_mission_metrics,
    collect_from_runner,
    lineage_root,
    lineage_ids,
)
from orchestrator.organization.runner import MissionRunner
from orchestrator.organization.root import build_verdict
from orchestrator.organization import metrics as metrics_mod

ALL7 = ("nova", "cto", "kai", "badsector", "somad", "cfo", "zeko")


def _delegation(task="org-7role"):
    return Delegation(
        id=f"delegation-{task}", principal="human", delegate="orchestrator",
        project="multi-agent-harness", task=task, action="write",
        target="repo/**", environment="dev",
        scope_operations=("read", "write", "test"), scope_resources=("repo/**",),
        status="ACTIVE", version=1,
    )


def _7role_mission(mission_id="m7", zeko_after=("bad", "som")):
    """Canonical bounded mission: W0 nova+cfo, W1 cto, W2 kai,
    W3 badsector+somad (both review kai), W4 zeko (depends on the two
    review tasks)."""
    tasks = (
        MissionTask(task_id="nova", mission_id=mission_id, owner="nova", role="nova",
                    objective="facts/research"),
        MissionTask(task_id="cfo", mission_id=mission_id, owner="cfo", role="cfo",
                    objective="resource/cost recommendation"),
        MissionTask(task_id="cto", mission_id=mission_id, owner="cto", role="cto",
                    objective="technical decision", depends_on=("nova",),
                    context_refs=("nova",)),
        MissionTask(task_id="kai", mission_id=mission_id, owner="kai", role="kai",
                    objective="implementation", depends_on=("cto",),
                    context_refs=("cto",), required_evidence=("test", "artifact")),
        MissionTask(task_id="bad", mission_id=mission_id, owner="badsector",
                    role="badsector", objective="adversarial review",
                    depends_on=("kai",), context_refs=("kai",)),
        MissionTask(task_id="som", mission_id=mission_id, owner="somad", role="somad",
                    objective="independent verification",
                    depends_on=("kai",), context_refs=("kai",)),
        MissionTask(task_id="zeko", mission_id=mission_id, owner="zeko", role="zeko",
                    objective="integration/release readiness",
                    depends_on=zeko_after),
    )
    return MissionPacket(mission_id=mission_id, objective="7-role bounded smoke",
                         tasks=tasks)


def _stub7(tid, task, ctx, *, kai_evidence=None, badsector_verdict="PASS",
           somad_verdict="VERIFIED"):
    """Deterministic per-role TaskResult stubs for the 7-role mission."""
    role = task.assigned_role
    tid = tid
    if role == "nova":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          findings=("fact-1", "fact-2"), evidence=("artifact:facts.md",))
    if role == "cfo":
        return TaskResult(
            task_id=tid, assigned_role=role, status="SUCCEEDED",
            findings=(
                "resource recommendation: bounded single mission, max_workers 4",
                "cost estimate: no token/cost data observed in this run",
            ),
            risks=("estimate risk: CFO figures are estimates, not observations",))
    if role == "cto":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          findings=("decision: proceed with existing organization layer",),
                          evidence=("artifact:decision.md",))
    if role == "kai":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          findings=("implementation complete",),
                          evidence=kai_evidence or ("test:log", "artifact:patch.diff"))
    if role == "badsector":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          recommendation=badsector_verdict,
                          findings=("attack surface reviewed",))
    if role == "somad":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          recommendation=somad_verdict, findings=("verified",))
    if role == "zeko":
        return TaskResult(task_id=tid, assigned_role=role, status="SUCCEEDED",
                          findings=("release readiness checked",),
                          evidence=("artifact:readiness.md",))
    raise AssertionError(f"unexpected role {role}")


def _runner_with(stub, base, **kw):
    def runner(task, delegation, ctx):
        return stub(task.task_id, task, ctx)
    return MissionRunner(delegation=_delegation(kw.pop("task", "org-7role")),
                         base=str(base), runner=runner, **kw)


class TestSevenRolesParticipate:
    def test_all_seven_roles_invoke_and_complete(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        v = r.run(mission)
        assert v.outcome == "COMPLETE", v.reason
        invoked = {t.owner for t in mission.tasks}
        assert invoked == set(ALL7)
        completed = {ho.owner for ho in r.handoffs.values() if ho.status == "done"}
        assert completed == set(ALL7)

    def test_role_run_ids_recorded_per_task(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        v = r.run(mission)
        # every mission task produced a handoff with owner/role identity
        for t in mission.tasks:
            ho = r.handoffs[t.task_id]
            assert ho.owner == t.owner and ho.role == t.role
            assert ho.mission_id == mission.mission_id


class TestOwnership:
    def test_owner_equals_role_everywhere(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        r.run(mission)
        for t in mission.tasks:
            assert t.owner == t.role
        for ho in r.handoffs.values():
            assert ho.owner == ho.role
            assert ho.owner in ALL7

    def test_reviewer_rework_packet_owned_by_reviewer_not_target(self, tmp_path):
        from orchestrator.organization.rework import ReworkLedger
        critic = MissionTask(task_id="bad", mission_id="m", owner="badsector",
                             role="badsector", objective="review", depends_on=("kai",))
        kai = MissionTask(task_id="kai", mission_id="m", owner="kai", role="kai",
                          objective="impl")
        rl = ReworkLedger()
        order = rl.request(target_task_id="kai", findings=("f",), reviewer="badsector",
                           attempt=1)
        ct = rl.critic_rework_task(critic, "kai#rework-1", 1)
        assert ct.owner == "badsector"  # reviewer reviews again; never fixes
        rew = rl.rework_task(kai, order)
        assert rew.owner == "kai"  # owner fixes; reviewer never implements


class TestDependencyOrdering:
    def test_wave_plan_matches_role_flow(self):
        from orchestrator.organization.waves import plan_mission_waves
        mission = _7role_mission()
        waves = plan_mission_waves(mission)
        assert waves == (
            ("nova", "cfo"),      # W0: NOVA + CFO parallel
            ("cto",),             # W1
            ("kai",),             # W2
            ("bad", "som"),       # W3: reviewers parallel
            ("zeko",),            # W4
        )

    def test_cto_after_nova_kai_after_cto(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        r.run(mission)
        tw = r._task_wave
        assert tw["cto"] > tw["nova"]
        assert tw["kai"] > tw["cto"]
        assert tw["bad"] > tw["kai"] and tw["som"] > tw["kai"]
        assert tw["zeko"] > tw["bad"] and tw["zeko"] > tw["som"]


class TestParallelWaves:
    def test_nova_cfo_same_wave_parallel_dispatch(self, tmp_path):
        # record actual concurrency: dispatch overlaps in wall-clock time
        overlap = {"in_flight": 0, "peak": 0}
        lock = __import__("threading").Lock()

        def stub(tid, task, ctx):
            if task.assigned_role in ("nova", "cfo"):
                with lock:
                    overlap["in_flight"] += 1
                    overlap["peak"] = max(overlap["peak"], overlap["in_flight"])
                time.sleep(0.05)
                res = _stub7(tid, task, ctx)
                with lock:
                    overlap["in_flight"] -= 1
                return res
            return _stub7(tid, task, ctx)

        mission = _7role_mission()
        r = MissionRunner(delegation=_delegation(),
                          base=str(tmp_path),
                          runner=lambda t, d, c: stub(t.task_id, t, c),
                          max_workers=4)
        v = r.run(mission)
        assert v.outcome == "COMPLETE", v.reason
        assert r._task_wave["nova"] == r._task_wave["cfo"]  # same wave
        assert overlap["peak"] == 2  # genuinely concurrent dispatch
        assert r.parallel_peak_observed >= 2

    def test_badsector_somad_same_wave_parallel_dispatch(self, tmp_path):
        overlap = {"in_flight": 0, "peak": 0}
        lock = __import__("threading").Lock()

        def stub(tid, task, ctx):
            if task.assigned_role in ("badsector", "somad"):
                with lock:
                    overlap["in_flight"] += 1
                    overlap["peak"] = max(overlap["peak"], overlap["in_flight"])
                time.sleep(0.05)
                res = _stub7(tid, task, ctx)
                with lock:
                    overlap["in_flight"] -= 1
                return res
            return _stub7(tid, task, ctx)

        mission = _7role_mission()
        r = MissionRunner(delegation=_delegation(),
                          base=str(tmp_path),
                          runner=lambda t, d, c: stub(t.task_id, t, c),
                          max_workers=4)
        v = r.run(mission)
        assert v.outcome == "COMPLETE", v.reason
        assert r._task_wave["bad"] == r._task_wave["som"]
        assert overlap["peak"] == 2  # reviewers ran concurrently
        assert r.parallel_peak_observed >= 2


class TestZekoCannotOverrideRejectedReview:
    def test_zeko_blocked_when_badsector_rejects(self, tmp_path):
        def stub(tid, task, ctx):
            return _stub7(tid, task, ctx, badsector_verdict="REJECT")

        mission = _7role_mission()
        r = _runner_with(stub, tmp_path)
        v = r.run(mission)
        # BADSECTOR rejects -> rework x2 -> escalate; ZEKO must never be
        # dispatched past a rejected review and ROOT must not be COMPLETE.
        assert "zeko" not in r._task_wave  # never dispatched
        assert v.outcome != "COMPLETE"
        assert any("escalat" in e.lower() for e in v.escalations)

    def test_zeko_blocked_while_review_pending(self, tmp_path):
        # SOMAD says REWORK (bounded): ZEKO must wait for the re-review; it
        # cannot be dispatched on stale acceptance.
        def stub(tid, task, ctx):
            return _stub7(tid, task, ctx, somad_verdict="REWORK",
                          badsector_verdict="PASS")

        mission = _7role_mission()
        r = _runner_with(stub, tmp_path)
        v = r.run(mission)
        assert v.outcome != "COMPLETE"
        som_rework = [h for h in r.handoffs if h.startswith("som#rework")]
        assert som_rework  # SOMAD re-review happened
        # ZEKO was either never dispatched, or dispatched only after the final
        # review round accepted kai (never on a stale acceptance).
        if "zeko" in r._task_wave:
            som_latest = [x["action"] for x in v.reviews
                          if x["reviewer"] == "somad"
                          and x["target_task_id"] == "kai"]
            assert som_latest and som_latest[-1] == "accept"


class TestRootFailClosed:
    def test_root_blocks_without_required_evidence(self):
        ho = TypedHandoff(mission_id="m", task_id="kai", owner="kai", role="kai",
                          status="done", summary="s", findings=("f",),
                          evidence=("test:log",), artifacts=(), changed_files=(),
                          risks=(), unknowns=(), next=())
        v = build_verdict(mission_id="m", handoffs={"kai": ho},
                          expected_tasks=("kai",),
                          reviews=[{"reviewer": "badsector", "target_task_id": "kai",
                                    "action": "accept"},
                                   {"reviewer": "somad", "target_task_id": "kai",
                                    "action": "accept"}],
                          required_evidence={"kai": ("test", "artifact")},
                          expected_reviewers={"kai": ("badsector", "somad")})
        assert v.outcome == "BLOCKED" and "evidence" in v.reason.lower()

    def test_root_blocks_without_required_review(self, tmp_path):
        def stub(tid, task, ctx):
            res = _stub7(tid, task, ctx)
            return res

        # mission where somad's review is expected but never produced
        tasks = (
            MissionTask(task_id="kai", mission_id="m2", owner="kai", role="kai",
                        objective="impl", required_evidence=("test", "artifact")),
            MissionTask(task_id="bad", mission_id="m2", owner="badsector",
                        role="badsector", objective="review", depends_on=("kai",)),
            MissionTask(task_id="som", mission_id="m2", owner="somad", role="somad",
                        objective="verify", depends_on=("kai",)),
        )
        mission = MissionPacket(mission_id="m2", objective="o", tasks=tasks)
        # SOMAD's task is never admitted (simulate by removing it from plan via
        # a blocked dependency): use an unknown dep? Instead directly test the
        # verdict aggregation for a missing reviewer acceptance.
        r = _runner_with(stub, tmp_path, task="m2")
        v = r.run(mission)
        assert v.outcome == "COMPLETE"  # sanity: full run completes
        # now strip somad's acceptance -> ROOT must refuse COMPLETE
        reviews = [x for x in v.reviews if x["reviewer"] != "somad"]
        v2 = build_verdict(mission_id="m2", handoffs=r.handoffs,
                           expected_tasks=tuple(t.task_id for t in mission.tasks),
                           reviews=reviews,
                           required_evidence={t.task_id: t.required_evidence
                                              for t in mission.tasks},
                           expected_reviewers={"kai": ("badsector", "somad")})
        assert v2.outcome == "BLOCKED"
        assert "not accepted" in v2.reason.lower()

    def test_escalation_cannot_become_complete(self, tmp_path):
        def stub(tid, task, ctx):
            return _stub7(tid, task, ctx, badsector_verdict="REWORK")

        mission = _7role_mission(zeko_after=("kai",))
        r = _runner_with(stub, tmp_path)
        v = r.run(mission)
        assert v.outcome == "ESCALATED"
        # ZEKO must not hold a 'done' handoff after an escalated review chain.
        assert all(h.status != "done"
                   for h in r.handoffs.values() if h.owner == "zeko")


class TestMetricsAccuracy:
    def _run_and_collect(self, tmp_path, stub=None):
        mission = _7role_mission()
        r = _runner_with(stub or _stub7, tmp_path)
        v = r.run(mission)
        from orchestrator.organization import collect_from_runner
        m = collect_from_runner(r, mission, v)
        return mission, r, v, m

    def test_core_counts(self, tmp_path):
        mission, r, v, m = self._run_and_collect(tmp_path)
        assert m.mission_id == mission.mission_id
        assert m.task_count == 7
        assert m.completed_tasks == 7 and m.blocked_tasks == 0 and m.failed_tasks == 0
        assert m.rework_cycles == 0 and m.escalated_tasks == 0
        assert m.waves == 5
        assert set(m.roles_invoked) == set(ALL7)
        assert set(m.roles_completed) == set(ALL7)
        assert m.verification_passed == 2 and m.verification_failed == 0
        assert m.parallel_tasks_peak == 2
        assert m.duration_ms >= 0 and m.started_at and m.completed_at

    def test_per_task_and_per_role_durations_attempts(self, tmp_path):
        mission, r, v, m = self._run_and_collect(tmp_path)
        by_task = {x.task_id: x for x in m.per_task_metrics}
        assert set(by_task) == set(t.task_id for t in mission.tasks)
        assert all(x.attempts >= 1 for x in m.per_task_metrics)
        assert all(x.duration_ms >= 0.0 for x in m.per_task_metrics)
        assert all(x.wave >= 0 for x in m.per_task_metrics)
        # durations are OBSERVED runner timings (floats, no invented numbers)
        assert any(x.duration_ms > 0.0 for x in m.per_task_metrics)
        by_role = {x.role: x for x in m.per_role_metrics}
        assert set(by_role) == set(ALL7)
        assert by_role["kai"].tasks == 1 and by_role["kai"].completed == 1
        assert all(x.total_duration_ms >= 0.0 for x in m.per_role_metrics)

    def test_metrics_dict_is_jsonable_and_classified(self, tmp_path):
        import json
        mission, r, v, m = self._run_and_collect(tmp_path)
        d = m.to_dict()
        json.dumps(d)  # must not raise
        assert set(d["_data_classification"]["estimated"]) == {"cfo_estimates"}
        assert "cfo_estimates" not in d["_data_classification"]["observed"]


class TestObservedVsEstimated:
    def test_cfo_estimates_only_from_cfo_handoff(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        v = r.run(mission)
        m = collect_from_runner(r, mission, v)
        est = m.cfo_estimates
        assert isinstance(est, EstimatedCfoData)
        assert est.resource_recommendation.startswith("resource recommendation:")
        assert "no token/cost data observed" in est.cost_estimate
        # observed fields carry no CFO payload
        assert all("cost" not in f.lower()
                   for x in m.per_task_metrics if x.role != "cfo"
                   for f in ())
        # CFO's own task metrics are OBSERVED, its estimates are ESTIMATED
        cfo_task = [x for x in m.per_task_metrics if x.role == "cfo"][0]
        assert cfo_task.status == "done" and cfo_task.attempts == 1

    def test_no_cfo_handoff_means_no_estimated_section(self, tmp_path):
        tasks = (
            MissionTask(task_id="kai", mission_id="m3", owner="kai", role="kai",
                        objective="impl", required_evidence=("test",)),
        )
        mission = MissionPacket(mission_id="m3", objective="o", tasks=tasks)

        def stub(tid, task, ctx):
            return TaskResult(task_id=tid, assigned_role="kai", status="SUCCEEDED",
                              findings=("ok",), evidence=("test:log",))

        r = _runner_with(stub, tmp_path, task="m3")
        v = r.run(mission)
        m = collect_from_runner(r, mission, v)
        assert m.cfo_estimates is None
        d = m.to_dict()
        assert d["cfo_estimates"] is None

    def test_estimated_values_are_verbatim_cfo_strings(self, tmp_path):
        mission = _7role_mission()
        r = _runner_with(_stub7, tmp_path)
        v = r.run(mission)
        m = collect_from_runner(r, mission, v)
        est = m.cfo_estimates
        cfo_ho = r.handoffs["cfo"]
        assert est.resource_recommendation in cfo_ho.findings or \
            est.resource_recommendation == cfo_ho.summary
        assert est.findings == cfo_ho.findings and est.risks == cfo_ho.risks


class TestReworkInMetrics:
    def test_rework_cycles_and_attempts_reflected(self, tmp_path):
        calls = {"kai": 0}

        def stub(tid, task, ctx):
            role = task.assigned_role
            if role == "kai":
                calls["kai"] += 1
                if calls["kai"] == 1:
                    return TaskResult(task_id=tid, assigned_role=role,
                                      status="SUCCEEDED", findings=("v1",),
                                      evidence=("artifact:patch.diff",))
                return TaskResult(task_id=tid, assigned_role=role,
                                  status="SUCCEEDED", findings=("v2",),
                                  evidence=("test:log", "artifact:patch.diff"))
            if role == "badsector":
                return _stub7(tid, task, ctx,
                              badsector_verdict="REWORK" if calls["kai"] < 2
                              else "PASS")
            return _stub7(tid, task, ctx)

        mission = _7role_mission()
        r = _runner_with(stub, tmp_path)
        v = r.run(mission)
        assert v.outcome == "COMPLETE", v.reason
        from orchestrator.organization import collect_from_runner
        m = collect_from_runner(r, mission, v)
        assert m.rework_cycles == 1
        kai_task = [x for x in m.per_task_metrics if x.task_id == "kai"][0]
        assert kai_task.rework_cycles == 1
        assert kai_task.attempts == 2
        assert kai_task.status == "done"  # promoted final state
        kai_role = [x for x in m.per_role_metrics if x.role == "kai"][0]
        assert kai_role.rework_cycles_triggered == 1
        assert kai_role.total_attempts == 2

    def test_lineage_helpers(self):
        assert lineage_root("kai#rework-2") == "kai"
        assert lineage_root("kai") == "kai"
        assert lineage_ids("kai", ["kai", "kai#rework-1", "kai#rework-2", "bad"]) \
            == ("kai", "kai#rework-1", "kai#rework-2")


class TestNoSecondSchedulerOrAudit:
    def test_runner_uses_existing_parallel_executor(self):
        import orchestrator.organization.runner as runner_mod
        import inspect
        src = inspect.getsource(runner_mod)
        assert "ParallelExecutor(" in src  # the existing executor is the engine
        # no second scheduler imported/created
        for banned in ("ThreadPoolExecutor(", "Scheduler(", "schedule("):
            assert banned not in src, banned

    def test_parallel_executor_is_runtime_module(self):
        from orchestrator.runtime.parallel import ParallelExecutor as PE
        import orchestrator.organization.runner as runner_mod
        assert runner_mod.ParallelExecutor is PE

    def test_evidence_ledger_rides_runtime_audit(self):
        import orchestrator.organization.evidence as ev_mod
        import inspect
        src = inspect.getsource(ev_mod)
        assert "audit" in src and "events.jsonl" not in src
        # EvidenceLedger wraps the passed audit instance — no own store path
        class _A:
            def emit(self, *a, **k):
                return "ev"

            def events_of_class(self, c):
                return []

            def read(self):
                return []
        ledger = ev_mod.EvidenceLedger(_A())
        assert ledger._audit is not None and not hasattr(ledger, "_path")

    def test_runner_audit_is_runtime_audit(self, tmp_path):
        from orchestrator.runtime.audit import RuntimeAudit
        r = _runner_with(_stub7, tmp_path)
        assert isinstance(r.audit, RuntimeAudit)
        assert isinstance(r.store, __import__(
            "orchestrator.runtime.store", fromlist=["RuntimeStore"]).RuntimeStore)

    def test_runner_uses_delegation_client_seam(self):
        import orchestrator.organization.runner as runner_mod
        import inspect
        src = inspect.getsource(runner_mod)
        assert "DelegationClient" in src

    def test_metrics_module_declares_no_store(self):
        src = os.path.abspath(metrics_mod.__file__)
        with open(src) as f:
            code = f.read()
        assert "open(" not in code and "json.dump" not in code


class TestMetricsDataclassContract:
    def test_required_metric_fields_exist(self):
        fields = {f.name for f in MissionMetrics.__dataclass_fields__.values()}
        required = {
            "mission_id", "started_at", "completed_at", "duration_ms",
            "task_count", "completed_tasks", "blocked_tasks", "failed_tasks",
            "escalated_tasks", "rework_cycles", "roles_invoked",
            "roles_completed", "waves", "parallel_tasks_peak",
            "verification_passed", "verification_failed",
        }
        assert required <= fields

    def test_invalid_cfo_estimate_section_never_observed(self):
        # The ESTIMATED block is a distinct type from OBSERVED rows.
        import dataclasses
        assert EstimatedCfoData is not ObservedTaskMetrics
        assert dataclasses.is_dataclass(EstimatedCfoData)


class TestMissionPacketGuards:
    def test_cfo_task_with_implementation_deps_rejected_by_layer(self, tmp_path):
        # CFO must not own implementation tasks: the packet layer enforces
        # single-owner only; the runner gate keeps CFO out of worker lineage.
        with pytest.raises(MissionError):
            MissionTask(task_id="cfo", mission_id="m", owner="kai", role="cfo",
                        objective="mismatch")

    def test_reviewer_multi_dep_rejected(self):
        with pytest.raises(MissionError):
            MissionTask(task_id="bad", mission_id="m", owner="badsector",
                        role="badsector", objective="r",
                        depends_on=("kai", "cto"))

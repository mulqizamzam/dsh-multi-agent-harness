"""Organization packet/handoff/waves contract tests (focused, additive).

Covers: packet schema + to_task/owner rule, PRD↔runtime status fail-closed,
context boundary, wave DAG + determinism, typed handoff derivation.
Does NOT touch existing contract schemas or gates beyond these seams.
"""

import os
import sys
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class TestPacket:
    def test_valid_task_to_task_maps_owner_to_assigned_role(self):
        from orchestrator.organization import MissionTask
        t = MissionTask(task_id="t1", mission_id="m", owner="kai", role="kai", objective="implement")
        task = t.to_task()
        assert task.assigned_role == "kai" and task.task_id == "t1"
        assert task.parent_task == "m" and task.objective == "implement"

    def test_owner_role_mismatch_rejected(self):
        from orchestrator.organization import MissionTask, MissionError
        with pytest.raises(MissionError, match="owner.*!= role"):
            MissionTask(task_id="t1", mission_id="m", owner="kai", role="cto", objective="x")

    def test_unknown_owner_rejected(self):
        from orchestrator.organization import MissionTask, MissionError
        with pytest.raises(MissionError, match="is not a specialist role"):
            MissionTask(task_id="t1", mission_id="m", owner="orchestrator", role="orchestrator", objective="x")

    def test_context_refs_passthrough(self):
        from orchestrator.organization import MissionTask
        t = MissionTask(task_id="t1", mission_id="m", owner="nova", role="nova",
                        objective="r", context_refs=("docs/design.md",))
        assert t.to_task().scope == ("docs/design.md",)

    def test_mission_packet_kitchen_sink(self):
        from orchestrator.organization import MissionPacket, MissionTask
        tasks = (
            MissionTask(task_id="pre", mission_id="m", owner="nova", role="nova", objective="research"),
            MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai", objective="implement",
                        depends_on=("pre",), context_refs=("pre",), required_evidence=("test", "artifact")),
            MissionTask(task_id="sec", mission_id="m", owner="badsector", role="badsector", objective="review impl",
                        depends_on=("impl",)),
            MissionTask(task_id="ver", mission_id="m", owner="somad", role="somad", objective="verify",
                        depends_on=("impl",)),
        )
        m = MissionPacket(mission_id="m", objective="ship feature", tasks=tasks)
        assert len(m.tasks) == 4 and m.by_id("pre").owner == "nova"
        assert m.reviewers_of("impl") == tuple(t for t in tasks if t.owner in ("badsector", "somad"))

    def test_mission_rejects_duplicate_ids(self):
        from orchestrator.organization import MissionPacket, MissionTask, MissionError
        t1 = MissionTask(task_id="t1", mission_id="m", owner="kai", role="kai", objective="a")
        t2 = MissionTask(task_id="t1", mission_id="m", owner="cto", role="cto", objective="b")
        with pytest.raises(MissionError, match="duplicate task ids"):
            MissionPacket(mission_id="m", objective="o", tasks=(t1, t2))

    def test_mission_rejects_unknown_dep(self):
        from orchestrator.organization import MissionPacket, MissionTask, MissionError
        t = MissionTask(task_id="t1", mission_id="m", owner="kai", role="kai", objective="a", depends_on=("ghost",))
        with pytest.raises(MissionError):
            MissionPacket(mission_id="m", objective="o", tasks=(t,))

    def test_mission_rejects_cycle(self):
        from orchestrator.organization import MissionPacket, MissionTask, MissionError
        ta = MissionTask(task_id="a", mission_id="m", owner="nova", role="nova", objective="a", depends_on=("b",))
        tb = MissionTask(task_id="b", mission_id="m", owner="kai", role="kai", objective="b", depends_on=("a",))
        with pytest.raises(MissionError, match="cycle"):
            MissionPacket(mission_id="m", objective="o", tasks=(ta, tb))

    def test_reviewer_dep_multi_rejected(self):
        from orchestrator.organization import MissionTask, MissionError
        with pytest.raises(MissionError, match="reviewer.*must"):
            MissionTask(task_id="sec", mission_id="m", owner="badsector", role="badsector",
                        objective="review", depends_on=("a", "b"))


class TestStatusMappingFailClosed:
    def test_uncertain_maps_to_failed_not_succeeded(self):
        from orchestrator.organization import runtime_status, prd_status
        assert runtime_status("uncertain") == "FAILED"
        assert runtime_status("done") == "SUCCEEDED" and runtime_status("blocked") == "BLOCKED"
        assert prd_status("FAILED") == "uncertain"
        assert prd_status("SUCCEEDED") == "done" and prd_status("BLOCKED") == "blocked"

    def test_no_uncertain_promotion(self):
        # uncertain must never round-trip to done/succeeded; blocked must not become done
        from orchestrator.organization import prd_status
        assert prd_status("FAILED") != "done" and prd_status("BLOCKED") != "done"

    def test_unknown_status_rejected(self):
        from orchestrator.organization import runtime_status, prd_status, MissionError
        with pytest.raises(MissionError):
            runtime_status("nonsense")
        with pytest.raises(MissionError):
            prd_status("UNKNOWN")


class TestWaves:
    def test_linear_waves_one_per_level(self):
        from orchestrator.organization.waves import plan_waves
        waves = plan_waves(("t1", "t2", "t3"), {"t1": (), "t2": ("t1",), "t3": ("t2",)})
        assert waves == (("t1",), ("t2",), ("t3",))

    def test_diamond_maximal_independent(self):
        from orchestrator.organization.waves import plan_waves
        waves = plan_waves(("nova", "kai", "bad", "somad"),
                           {"nova": (), "kai": ("nova",), "bad": ("kai",), "somad": ("kai",)})
        assert waves[0] == ("nova",) and waves[1] == ("kai",)
        assert set(waves[2]) == {"bad", "somad"}  # independent leaves parallelize
        assert len(waves) == 3

    def test_deterministic_input_order(self):
        from orchestrator.organization.waves import plan_waves
        # independent leaves: one wave, deterministic in input order
        w1 = plan_waves(("a", "b", "c"), {"a": (), "b": (), "c": ()})
        assert w1 == (("a", "b", "c"),)
        # same set with different input order deterministically follows input position
        w2 = plan_waves(("c", "b", "a"), {"a": (), "b": (), "c": ()})
        assert w2 == (("c", "b", "a"),)
        # irrespective of input order, within a level the dependency edges still define membership
        w_chain = plan_waves(("c", "a", "b"), {"a": (), "b": ("a",), "c": ("b",)})
        assert tuple(list(w_chain[0])[0] for w_chain in [w_chain])  # topo order, one per level
        assert w_chain == (("a",), ("b",), ("c",))

    def test_unknown_dep_rejected(self):
        from orchestrator.organization.waves import plan_waves
        with pytest.raises(ValueError):
            plan_waves(("t1",), {"t1": ("ghost",)})

    def test_cycle_rejected(self):
        from orchestrator.organization.waves import plan_waves
        with pytest.raises(ValueError, match="cycle"):
            plan_waves(("a", "b"), {"a": ("b",), "b": ("a",)})

    def test_plan_mission_waves_equal_pure_plan(self):
        from orchestrator.organization import MissionTask, MissionPacket
        from orchestrator.organization.waves import plan_waves, plan_mission_waves
        tasks = (
            MissionTask(task_id="a", mission_id="m", owner="nova", role="nova", objective="r"),
            MissionTask(task_id="b", mission_id="m", owner="kai", role="kai", objective="i", depends_on=("a",)),
            MissionTask(task_id="c", mission_id="m", owner="somad", role="somad", objective="v", depends_on=("b",)),
        )
        m = MissionPacket(mission_id="m", objective="o", tasks=tasks)
        pure = plan_waves(tuple(t.task_id for t in tasks), {t.task_id: tuple(t.depends_on) for t in tasks})
        assert plan_mission_waves(m) == pure

    def test_build_wave_plans_uses_existing_builder(self):
        from orchestrator.organization import MissionTask
        from orchestrator.organization.waves import build_wave_plans
        tasks = [
            MissionTask(task_id="a", mission_id="m", owner="nova", role="nova", objective="r"),
            MissionTask(task_id="b", mission_id="m", owner="kai", role="kai", objective="i"),
        ]
        plans = build_wave_plans(tasks)
        assert len(plans) == 2 and all(p.writes == () for p in plans)
        assert {p.task.task_id for p in plans} == {"a", "b"}


class TestTypedHandoff:
    def test_handoff_from_succeeded(self):
        from orchestrator.organization import MissionTask, TypedHandoff
        from orchestrator.foundation.contracts import TaskResult
        mt = MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai", objective="impl")
        r = TaskResult(task_id="impl", assigned_role="kai", status="SUCCEEDED",
                       findings=("implemented",), evidence=("artifact:patch.diff", "test:log"),
                       recommendation="ship")
        ho = TypedHandoff.from_task_result(mt, r, attempt=1)
        assert ho.status == "done" and ho.task_id == "impl" and ho.owner == "kai"
        assert "patch.diff" in ho.changed_files
        assert ho.evidence == ("artifact:patch.diff", "test:log")

    def test_handoff_status_mapping_uncertain(self):
        from orchestrator.organization import MissionTask, TypedHandoff
        from orchestrator.foundation.contracts import TaskResult
        mt = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai", objective="x")
        r = TaskResult(task_id="t", assigned_role="kai", status="FAILED", findings=("unclear",))
        ho = TypedHandoff.from_task_result(mt, r)
        assert ho.status == "uncertain"  # never "done"
        rb = TaskResult(task_id="t", assigned_role="kai", status="BLOCKED")
        assert TypedHandoff.from_task_result(mt, rb).status == "blocked"

    def test_context_boundary_only_refs(self):
        from orchestrator.organization import MissionTask, TypedHandoff, build_task_context
        kai = MissionTask(task_id="impl", mission_id="m", owner="kai", role="kai", objective="i",
                          context_refs=("pre",), depends_on=("pre",))
        gh = TypedHandoff(mission_id="m", task_id="pre", owner="nova", role="nova",
                          status="done", summary="facts", findings=("facts",),
                          evidence=("artifact:facts.md",), artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        other = TypedHandoff(mission_id="m", task_id="other", owner="cto", role="cto",
                             status="done", summary="design", findings=("d1",), evidence=(), artifacts=(), changed_files=(), risks=(), unknowns=(), next=())
        ctx = build_task_context(kai, {"pre": gh, "other": other})
        assert "pre" in ctx["upstream"] and "other" not in ctx["upstream"]
        assert ctx["mission_id"] == "m" and ctx["task_id"] == "impl"
        assert "delegation" not in ctx and "approval" not in str(ctx)

    def test_context_rejects_authority_key(self):
        from orchestrator.organization import MissionTask, TypedHandoff, MissionError, build_task_context
        mt = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai", objective="x")
        with pytest.raises(MissionError, match="authority"):
            build_task_context(mt, {}, extra={"delegation_id": "d1"})

    def test_context_extra_without_auth_is_allowed(self):
        from orchestrator.organization import MissionTask, TypedHandoff, build_task_context
        mt = MissionTask(task_id="t", mission_id="m", owner="kai", role="kai", objective="x")
        ctx = build_task_context(mt, {}, extra={"rework_cycle": 1, "findings": ["missing test"]})
        assert ctx["extra_rework_cycle"] == 1
